"""Bounded, verified HTTPS retries for public Bybit candles."""
import logging
import random
import time

import requests

from storage import CATEGORY, SYMBOL, MIN_MS, candle_row

API_URL = 'https://api.bybit.com/v5/market/kline'
RETRY_CODES = {10000, 10006, 10016, 10018}


def fetch_page(start, end, session=None, sleep=time.sleep, attempts=5):
    """Inclusive candle-start bounds, max 1000. Empty/partial pages are errors.

    Bounds must refer to closed candles; callers set the close cutoff once per sweep.
    Strict completeness avoids silently accepting a transient missing REST page.
    Assets listed after the requested start require a shorter BACKFILL_DAYS window.
    """
    if start % MIN_MS or end % MIN_MS or end < start or end-start >= 1000*MIN_MS:
        raise ValueError('Invalid page bounds')
    get = session.get if session is not None else requests.get
    for attempt in range(attempts):
        try:
            response = get(API_URL, params={'category': CATEGORY, 'symbol': SYMBOL,
                'interval': '1', 'start': start, 'end': end, 'limit': 1000}, timeout=(10, 25))
            if response.status_code == 429 or response.status_code >= 500:
                raise requests.ConnectionError(f'Transient HTTP {response.status_code}')
            response.raise_for_status()
            payload = response.json()
            code = payload.get('retCode')
            if code in RETRY_CODES:
                raise requests.ConnectionError(f'Transient Bybit code {code}')
            if code != 0:
                raise ValueError(f'Bybit rejected request, code={code}')
            rows = {}
            for value in payload['result']['list']:
                ts = int(value[0])
                if start <= ts <= end:
                    rows[ts] = candle_row(ts, value[1:7])
            if set(rows) != set(range(start, end+1, MIN_MS)):
                raise requests.ConnectionError('Incomplete candle page; refusing silent gap')
            return [rows[t] for t in sorted(rows)]
        except (requests.ConnectionError, requests.Timeout):
            if attempt+1 == attempts:
                raise
            delay = min(30, 2**attempt) + random.uniform(0, 0.5)
            logging.warning('REST retry %d/%d in %.1fs', attempt+1, attempts, delay)
            sleep(delay)
    raise RuntimeError('No REST attempts configured')
