"""Read-only WSGI dashboard. Served by Gunicorn; no Docker socket or write API."""
import json
import logging
import os
from pathlib import Path
import threading
import time
from urllib.parse import urlsplit

from storage import CATEGORY, SYMBOL
from quality import audit

ROOT = Path(__file__).resolve().parent/'web'
CACHE_SECONDS = 15
_lock = threading.Lock()
_cached = None
_cached_at = 0.0


def read_document(path):
    try:
        # Bound external/generated input; do not expose file errors or secrets.
        if path.stat().st_size > 2_000_000:
            return None, 'invalid'
        data = json.loads(path.read_text(), parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if not isinstance(data, dict):
            return None, 'invalid'
        return data, None
    except FileNotFoundError:
        return None, 'missing'
    except (OSError, ValueError, UnicodeError):
        return None, 'invalid'


def component_status(now):
    state, error = read_document(Path(os.getenv('BACKFILL_STATE_PATH','state/backfill.json')))
    backfill = {'state':'unknown','reason':error or 'no_success','last_full_success_ms':None,
                'last_recent_success_ms':None,'last_error_kind':None,'phase':None}
    if state is not None:
        identity_ok = state.get('symbol')==SYMBOL and state.get('category')==CATEGORY
        window_ok = state.get('backfill_days')==int(os.getenv('BACKFILL_DAYS','30'))
        for key in ('last_full_success_ms','last_recent_success_ms'):
            val = state.get(key)
            if isinstance(val,int) and not isinstance(val,bool) and 0 < val <= now:
                backfill[key] = val
        # Explicit allowlists: never pass arbitrary persisted strings to clients.
        backfill['phase'] = state.get('phase') if state.get('phase') in ('running','ok','error','stopped') else None
        backfill['last_error_kind'] = state.get('last_error_kind') if state.get('last_error_kind') in (
            'http_403','http_429','http_error','network','database','invalid_response','internal') else None
        full, recent = backfill['last_full_success_ms'], backfill['last_recent_success_ms']
        if not identity_ok or not window_ok:
            backfill.update(state='unknown',reason='different_config')
        elif state.get('phase')=='error':
            backfill.update(state='error',reason='last_attempt_failed')
        elif full is not None and recent is not None and now-full<=7_200_000 and now-recent<=300_000:
            backfill.update(state='ok',reason=None)
        else:
            backfill.update(state='pending' if state.get('phase')=='running' else 'stale',reason='no_recent_success')
    report, error = read_document(Path(os.getenv('REPORT_PATH','reports/latest.json')))
    analyst = {'state':'unknown','reason':error,'generated_at_ms':None,'report':None}
    if report is not None:
        generated = report.get('generated_at_ms')
        same_instrument = report.get('symbol')==SYMBOL and report.get('category')==CATEGORY
        # Older insufficient_history reports had no instrument fields. Never attach
        # their contents to the current stream until generated with an identity.
        if not same_instrument:
            analyst.update(reason='different_config')
        elif not isinstance(generated,int) or isinstance(generated,bool) or not 0<=now-generated<=900_000:
            analyst.update(state='stale',reason='old_report')
        else:
            analyst.update(state='ok',reason=None,generated_at_ms=generated,report=report)
    return backfill, analyst


def forecast_status(now):
    report,error=read_document(Path(os.getenv('FORECAST_REPORT_PATH','reports/forecast.json')))
    result={'state':'unknown','reason':error,'report':None}
    if report is None:
        return result
    if (report.get('symbol')!=SYMBOL or report.get('category')!=CATEGORY or
        report.get('horizon_minutes')!=10 or
        report.get('band_bps')!=float(os.getenv('FORECAST_BAND_BPS','10'))):
        result['reason']='different_config'
        return result
    generated=report.get('generated_at_ms')
    if not isinstance(generated,int) or isinstance(generated,bool) or not 0<=now-generated<=180_000:
        result.update(state='stale',reason='old_forecast_report')
        return result
    result.update(state='waiting',reason=report.get('reason'),report=report)
    forecast=report.get('forecast')
    if report.get('status')=='error':
        result['state']='error'
    elif forecast is not None:
        asof,target=forecast.get('asof_ms'),forecast.get('target_ms')
        if (not isinstance(asof,int) or not isinstance(target,int) or
            target-asof!=600_000 or not asof<=now<target):
            result.update(state='expired',reason='expired_forecast',report={**report,'forecast':None})
        else:
            result.update(state='ok',reason=None)
    return result


def build_status():
    now = int(time.time()*1000)
    backfill, analyst = component_status(now)
    status = {'generated_at_ms':now,'symbol':SYMBOL,'category':CATEGORY,
              'database':{'state':'ok'},'quality':None,'backfill':backfill,'analyst':analyst,'forecast':forecast_status(now)}
    try:
        status['quality'] = audit(int(os.getenv('BACKFILL_DAYS','30')),now_ms=now)
    except Exception as err:
        logging.warning('Quality query failed: %s', type(err).__name__)
        status['database'] = {'state':'unavailable','reason':'query_failed'}
        forecast=status['forecast']
        if forecast['report'] is not None:
            status['forecast']={**forecast,'state':'unknown','reason':'database_unavailable',
                                'report':{**forecast['report'],'forecast':None}}
    status['ready'] = bool(status['quality'] and status['quality']['ready'] and
                           backfill['state']=='ok' and analyst['state']=='ok')
    return status


def current_status():
    global _cached, _cached_at
    # Serialize cache refresh in each Gunicorn process; no polling connection pool.
    with _lock:
        now = time.monotonic()
        if _cached is None or now-_cached_at>=CACHE_SECONDS:
            _cached = build_status()
            _cached_at = time.monotonic()
        return _cached


def application(environ, start_response):
    path = urlsplit(environ.get('PATH_INFO','/')).path
    method = environ.get('REQUEST_METHOD','GET')
    headers = [('Cache-Control','no-store'),('X-Content-Type-Options','nosniff'),
               ('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"),
               ('Referrer-Policy','no-referrer')]
    code = '200 OK'
    mime = 'application/json; charset=utf-8'
    if method not in ('GET','HEAD'):
        code,body = '405 Method Not Allowed',b'{"error":"method_not_allowed"}'
        headers.append(('Allow','GET, HEAD'))
    elif path=='/healthz':
        body = b'{"status":"alive"}'
    elif path in ('/api/status','/readyz'):
        try:
            data = current_status()
            if path=='/readyz' and not data['ready']:
                code='503 Service Unavailable'
            body=json.dumps(data,allow_nan=False).encode()
        except Exception:
            logging.exception('Dashboard status generation failed')
            code,body='503 Service Unavailable',b'{"error":"status_unavailable"}'
    elif path in ('/','/app.js','/style.css'):
        filename,mime = {'/':('index.html','text/html; charset=utf-8'),
                         '/app.js':('app.js','text/javascript; charset=utf-8'),
                         '/style.css':('style.css','text/css; charset=utf-8')}[path]
        body=(ROOT/filename).read_bytes()
    else:
        code,body='404 Not Found',b'{"error":"not_found"}'
    headers.extend([('Content-Type',mime),('Content-Length',str(len(body)))])
    start_response(code,headers)
    return [b'' if method=='HEAD' else body]
