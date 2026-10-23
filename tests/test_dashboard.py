import json
from pathlib import Path
from unittest.mock import Mock

import pytest

import dashboard


def request(path='/',method='GET'):
    result={}
    def start(status,headers):
        result.update(status=status,headers=dict(headers))
    result['body']=b''.join(dashboard.application({'PATH_INFO':path,'REQUEST_METHOD':method},start))
    return result


def documents(tmp_path,monkeypatch):
    state=tmp_path/'state.json'; report=tmp_path/'report.json'
    monkeypatch.setenv('BACKFILL_STATE_PATH',str(state))
    monkeypatch.setenv('REPORT_PATH',str(report))
    monkeypatch.setenv('BACKFILL_DAYS','30')
    return state,report


def test_no_database_preserves_page_and_does_not_leak_password(tmp_path,monkeypatch):
    documents(tmp_path,monkeypatch)
    monkeypatch.setattr(dashboard,'audit',Mock(side_effect=RuntimeError('password=secret-test-value')))
    result=dashboard.build_status()
    assert result['database']['state']=='unavailable'
    assert result['ready'] is False
    assert 'secret-test-value' not in json.dumps(result)
    assert request()['status']=='200 OK'


def test_fresh_components_require_correct_instrument_and_window(tmp_path,monkeypatch):
    state,report=documents(tmp_path,monkeypatch)
    now=10_000_000
    state.write_text(json.dumps({'symbol':dashboard.SYMBOL,'category':dashboard.CATEGORY,
        'backfill_days':30,'phase':'ok','last_full_success_ms':now-1000,'last_recent_success_ms':now-1000}))
    report.write_text(json.dumps({'symbol':dashboard.SYMBOL,'category':dashboard.CATEGORY,
                                  'generated_at_ms':now-1000,'status':'insufficient_history','rows':5}))
    a,b=dashboard.component_status(now)
    assert a['state']==b['state']=='ok'
    monkeypatch.setenv('BACKFILL_DAYS','90')
    assert dashboard.component_status(now)[0]['reason']=='different_config'
    report.write_text(json.dumps({'symbol':'OTHER','category':dashboard.CATEGORY,'generated_at_ms':now}))
    assert dashboard.component_status(now)[1]['report'] is None


def test_failure_status_and_stale_report_are_not_green(tmp_path,monkeypatch):
    state,report=documents(tmp_path,monkeypatch)
    now=10_000_000
    state.write_text(json.dumps({'symbol':dashboard.SYMBOL,'category':dashboard.CATEGORY,
        'backfill_days':30,'phase':'error','last_error_kind':'http_403',
        'last_full_success_ms':now,'last_recent_success_ms':now}))
    report.write_text(json.dumps({'symbol':dashboard.SYMBOL,'category':dashboard.CATEGORY,
                                  'generated_at_ms':now-900001}))
    a,b=dashboard.component_status(now)
    assert a['state']=='error' and a['last_error_kind']=='http_403'
    assert b['state']=='stale' and b['report'] is None


@pytest.mark.parametrize('contents',['not json','[]','{"value":NaN}'])
def test_corrupt_state_does_not_break_dashboard(tmp_path,monkeypatch,contents):
    state,report=documents(tmp_path,monkeypatch)
    state.write_text(contents)
    report.write_text(contents)
    a,b=dashboard.component_status(10_000_000)
    assert a['state']==b['state']=='unknown'


def test_routes_readonly_path_allowlist_and_security_headers(monkeypatch):
    for path in ('/','/app.js','/style.css','/healthz'):
        r=request(path)
        assert r['status']=='200 OK'
        assert int(r['headers']['Content-Length'])==len(r['body'])
        assert 'frame-ancestors' in r['headers']['Content-Security-Policy']
    for path in ('/.env','/../storage.py','/reports/latest.json','/state/backfill.json'):
        assert request(path)['status']=='404 Not Found'
    assert request('/api/status','POST')['status']=='405 Method Not Allowed'
    assert request('/','HEAD')['body']==b''
    monkeypatch.setattr(dashboard,'current_status',lambda:{'ready':False,'database':{'state':'unavailable'}})
    assert request('/api/status')['status']=='200 OK'
    assert request('/readyz')['status']=='503 Service Unavailable'


def test_cache_does_not_query_database_on_every_poll(monkeypatch):
    monkeypatch.setattr(dashboard,'_cached',None)
    monkeypatch.setattr(dashboard,'_cached_at',0)
    build=Mock(return_value={'ready':False})
    monkeypatch.setattr(dashboard,'build_status',build)
    monkeypatch.setattr(dashboard.time,'monotonic',lambda:100)
    dashboard.current_status(); dashboard.current_status()
    assert build.call_count==1
    monkeypatch.setattr(dashboard.time,'monotonic',lambda:116)
    dashboard.current_status()
    assert build.call_count==2
