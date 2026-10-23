"""Repair recent gaps and periodically sweep the full configured history."""
import json
import logging
import os
from pathlib import Path
import signal
import threading
import time

import requests

from bybit import fetch_page
from storage import CATEGORY, SYMBOL, MIN_MS, save_rows, setup

DAY_MS = 86_400_000
STOP = threading.Event()
DAYS = int(os.getenv('BACKFILL_DAYS', '30'))
if not 1 <= DAYS <= 90:
    raise ValueError('BACKFILL_DAYS must be between 1 and 90')


def fill(days=DAYS, now_ms=None, stop=STOP):
    cutoff = (int(time.time()*1000) if now_ms is None else now_ms)//MIN_MS*MIN_MS
    beginning = cutoff - int(days*DAY_MS)
    beginning = beginning//MIN_MS*MIN_MS
    total = 0
    with requests.Session() as session:
        for start in reversed(range(beginning, cutoff, 1000*MIN_MS)):
            if stop.is_set():
                return total
            end = min(cutoff-MIN_MS, start+999*MIN_MS)
            rows = fetch_page(start, end, session=session, sleep=interruptible_wait)
            save_rows(rows)  # Commit each page; replays after failure are safe.
            total += len(rows)
            if stop.wait(0.15):
                break
    logging.info('Repair complete: %d closed candles upserted', total)
    return total


def interruptible_wait(seconds):
    if STOP.wait(seconds):
        raise InterruptedError('Stopping backfill')


def read_state():
    try:
        data = json.loads(Path(os.getenv('BACKFILL_STATE_PATH','state/backfill.json')).read_text())
        if data.get('symbol')==SYMBOL and data.get('category')==CATEGORY and data.get('backfill_days')==DAYS:
            return data
    except (OSError, ValueError, AttributeError):
        pass
    return {'last_full_success_ms':0,'last_recent_success_ms':0,
            'symbol':SYMBOL,'category':CATEGORY,'backfill_days':DAYS}


def write_state(data):
    path = Path(os.getenv('BACKFILL_STATE_PATH','state/backfill.json'))
    path.parent.mkdir(parents=True,exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data,allow_nan=False))
    temp.replace(path)


def error_kind(err):
    # Keep credentials, DSNs and response bodies out of persisted/public status.
    if isinstance(err,requests.HTTPError):
        code = err.response.status_code if err.response is not None else None
        return f'http_{code}' if code in (403,429) else 'http_error'
    if isinstance(err,requests.RequestException):
        return 'network'
    from psycopg import Error as DatabaseError
    if isinstance(err,DatabaseError):
        return 'database'
    if isinstance(err,(ValueError,KeyError,TypeError)):
        return 'invalid_response'
    return 'internal'


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: STOP.set())
    next_full = 0
    state = read_state()
    while not STOP.is_set():
        try:
            state.update(phase='running',last_attempt_ms=int(time.time()*1000))
            write_state(state)
            setup()
            full = time.monotonic() >= next_full
            fill(DAYS if full else 10/1440)
            if STOP.is_set():
                state['phase']='stopped'
                write_state(state)
                break
            now_ms = int(time.time()*1000)
            if full:
                next_full = time.monotonic()+3600
                state['last_full_success_ms']=now_ms
            state.update(last_recent_success_ms=now_ms,phase='ok',last_error_kind=None)
            write_state(state)
        except Exception as err:
            if not STOP.is_set():
                logging.exception('Repair failed; next cycle retries from durable pages')
                state.update(phase='error',last_error_kind=error_kind(err),
                             last_error_at_ms=int(time.time()*1000))
                try:
                    write_state(state)
                except OSError:
                    logging.exception('Cannot persist REST status')
        STOP.wait(60)


if __name__ == '__main__':
    main()
