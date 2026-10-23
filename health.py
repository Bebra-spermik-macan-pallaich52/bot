"""Exit nonzero on stale candles, recent gaps or stale analysis reports."""
import json
import os
from pathlib import Path
import sys
import time

from storage import CATEGORY, SYMBOL, MIN_MS, connect


def check_ingestion(now_ms=None):
    now = int(time.time()*1000) if now_ms is None else now_ms
    # Allow 2 minutes of delivery latency; verify 10 consecutive older bars.
    end = now//MIN_MS*MIN_MS - 3*MIN_MS
    with connect() as conn:
        count, = conn.execute('''SELECT count(*) FROM candles
          WHERE exchange='bybit' AND category=%s AND symbol=%s AND interval='1'
          AND start_ms BETWEEN %s AND %s AND start_ms %% 60000=0''',
          (CATEGORY,SYMBOL,end-9*MIN_MS,end)).fetchone()
    if count != 10:
        raise RuntimeError(f'Ingestion stale or incomplete: {count}/10 recent candles')


def check_backfill_state(now_ms=None):
    now = int(time.time()*1000) if now_ms is None else now_ms
    data = json.loads(Path(os.getenv('BACKFILL_STATE_PATH','state/backfill.json')).read_text())
    if data.get('symbol') != SYMBOL or data.get('category') != CATEGORY:
        raise RuntimeError('Backfill state belongs to another instrument')
    if data.get('phase')=='error':
        raise RuntimeError('Last REST repair attempt failed')
    if not 0 <= now-data['last_full_success_ms'] <= 7_200_000:
        raise RuntimeError('Full REST repair has not succeeded in 2h')
    if not 0 <= now-data['last_recent_success_ms'] <= 300_000:
        raise RuntimeError('Recent REST repair has not succeeded in 5m')


def main():
    if len(sys.argv)>1 and sys.argv[1]=='forecaster':
        path=Path(os.getenv('FORECAST_REPORT_PATH','reports/forecast.json'))
        if time.time()-path.stat().st_mtime > 180:
            raise RuntimeError('Forecast report stale')
    elif len(sys.argv)>1 and sys.argv[1]=='analyst':
        path = Path(os.getenv('REPORT_PATH','reports/latest.json'))
        if time.time()-path.stat().st_mtime > 900:
            raise RuntimeError('Analysis report stale')
    else:
        if len(sys.argv)>1 and sys.argv[1]=='backfill':
            check_backfill_state()
        check_ingestion()


if __name__ == '__main__':
    main()
