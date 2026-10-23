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


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: STOP.set())
    next_full = 0
    last_full_success_ms = 0
    while not STOP.is_set():
        try:
            setup()
            full = time.monotonic() >= next_full
            # Ten minute overlap repairs a dropped live message promptly; hourly
            # full sweeps recover longer outages even after process restarts.
            fill(DAYS if full else 10/1440)
            if STOP.is_set():
                break
            now_ms = int(time.time()*1000)
            if full:
                next_full = time.monotonic()+3600
                last_full_success_ms = now_ms
            path = Path(os.getenv('BACKFILL_STATE_PATH','state/backfill.json'))
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_suffix('.tmp')
            temp.write_text(json.dumps({'last_full_success_ms':last_full_success_ms,
                'last_recent_success_ms':now_ms,'symbol':SYMBOL,'category':CATEGORY}))
            temp.replace(path)
        except Exception:
            if not STOP.is_set():
                logging.exception('Repair failed; next cycle retries from durable pages')
        STOP.wait(60)


if __name__ == '__main__':
    main()
