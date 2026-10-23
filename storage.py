"""Shared configuration and idempotent PostgreSQL storage (no network on import)."""
import os
from decimal import Decimal

import psycopg

MIN_MS = 60_000
SYMBOL = os.getenv('SYMBOL', 'BTCUSDT').upper()
CATEGORY = os.getenv('CATEGORY', 'linear')
if CATEGORY not in ('linear', 'spot', 'inverse'):
    raise ValueError('CATEGORY must be linear, spot or inverse')


def connect():
    # Separate fields support passwords containing URL-reserved characters.
    if os.getenv('DATABASE_URL'):
        return psycopg.connect(os.environ['DATABASE_URL'], connect_timeout=10)
    return psycopg.connect(host=os.getenv('PGHOST', 'db'),
                          dbname=os.getenv('PGDATABASE', 'market'),
                          user=os.getenv('PGUSER', 'market'),
                          password=os.environ['DB_PASSWORD'], connect_timeout=10)


def setup():
    with connect() as conn:
        # Serializes concurrent first-start DDL across the three workers.
        conn.execute('SELECT pg_advisory_xact_lock(7291042)')
        conn.execute('''CREATE TABLE IF NOT EXISTS candles (
            exchange TEXT NOT NULL DEFAULT 'bybit', category TEXT NOT NULL,
            symbol TEXT NOT NULL, interval TEXT NOT NULL, start_ms BIGINT NOT NULL,
            open NUMERIC NOT NULL, high NUMERIC NOT NULL, low NUMERIC NOT NULL,
            close NUMERIC NOT NULL, volume NUMERIC NOT NULL, turnover NUMERIC NOT NULL,
            received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (exchange,category,symbol,interval,start_ms))''')


def candle_row(start, values):
    ts = int(start)
    numbers = tuple(Decimal(str(v)) for v in values)
    if ts < 0 or ts % MIN_MS or len(numbers) != 6 or not all(v.is_finite() for v in numbers):
        raise ValueError('Invalid candle timestamp or values')
    op, hi, lo, cl, vol, turnover = numbers
    if min(op, hi, lo, cl) <= 0 or lo > min(op, cl) or hi < max(op, cl) or min(vol, turnover) < 0:
        raise ValueError('Invalid candle OHLCV')
    return (CATEGORY, SYMBOL, '1', ts, *numbers)


def save_rows(rows):
    if not rows:
        return
    with connect() as conn, conn.cursor() as cur:
        cur.executemany('''INSERT INTO candles
          (category,symbol,interval,start_ms,open,high,low,close,volume,turnover)
          VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
          ON CONFLICT (exchange,category,symbol,interval,start_ms)
          DO UPDATE SET open=EXCLUDED.open,high=EXCLUDED.high,low=EXCLUDED.low,
            close=EXCLUDED.close,volume=EXCLUDED.volume,turnover=EXCLUDED.turnover,
            received_at=now()''', rows)
