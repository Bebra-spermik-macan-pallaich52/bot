"""Immutable, prospective-only prediction journal. Public market data, no orders."""
import time

import numpy as np
from psycopg.types.json import Jsonb

from storage import CATEGORY, SYMBOL, MIN_MS, connect
from forecasting import CLASSES, HORIZON, classify, metric_summary


def setup_forecasts():
    with connect() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(7291043)')
        conn.execute('''CREATE TABLE IF NOT EXISTS forecasts (
          exchange TEXT NOT NULL DEFAULT 'bybit', category TEXT NOT NULL, symbol TEXT NOT NULL,
          protocol TEXT NOT NULL, asof_ms BIGINT NOT NULL, target_ms BIGINT NOT NULL,
          issued_at_ms BIGINT NOT NULL, snapshot JSONB NOT NULL,
          PRIMARY KEY(exchange,category,symbol,protocol,asof_ms),
          CHECK(target_ms=asof_ms+600000),
          CHECK(issued_at_ms>=asof_ms AND issued_at_ms<=asof_ms+90000))''')


def record_forecast(forecast,config,prior,now_ms=None):
    now=int(time.time()*1000) if now_ms is None else now_ms
    asof=int(forecast['asof_ms'])
    if not 0<=now-asof<=90_000 or forecast['target_ms']!=asof+HORIZON*MIN_MS:
        raise ValueError('Refusing stale/backdated prediction')
    probabilities=np.array([forecast['probabilities'][c] for c in CLASSES])
    if (not np.isfinite(probabilities).all() or (probabilities<0).any() or
        (probabilities>1).any() or not np.isclose(probabilities.sum(),1)):
        raise ValueError('Invalid probabilities')
    snapshot={**forecast,'issued_at_ms':now,'baseline_probabilities':dict(zip(CLASSES,map(float,prior)))}
    with connect() as conn:
        conn.execute('''INSERT INTO forecasts(category,symbol,protocol,asof_ms,target_ms,issued_at_ms,snapshot)
          VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING''',
          (CATEGORY,SYMBOL,config.protocol,asof,forecast['target_ms'],now,Jsonb(snapshot)))
        saved=conn.execute('''SELECT snapshot FROM forecasts WHERE exchange='bybit'
          AND category=%s AND symbol=%s AND protocol=%s AND asof_ms=%s''',
          (CATEGORY,SYMBOL,config.protocol,asof)).fetchone()[0]
    return saved


def prospective_summary(config,now_ms=None):
    now=int(time.time()*1000) if now_ms is None else now_ms
    with connect() as conn:
        conn.execute('SET TRANSACTION READ ONLY')
        conn.execute("SET LOCAL statement_timeout = '5s'")
        total=conn.execute('''SELECT count(*) FROM forecasts WHERE exchange='bybit'
          AND category=%s AND symbol=%s AND protocol=%s''',(CATEGORY,SYMBOL,config.protocol)).fetchone()[0]
        # Fixed UTC ten-minute grid avoids treating overlapping minute labels as
        # independent observations. Missing target bars stay unscored.
        rows=conn.execute('''SELECT f.snapshot,c.close FROM forecasts f JOIN candles c
          ON c.exchange=f.exchange AND c.category=f.category AND c.symbol=f.symbol
          AND c.interval='1' AND c.start_ms=f.target_ms-60000
          WHERE f.exchange='bybit' AND f.category=%s AND f.symbol=%s AND f.protocol=%s
          AND f.target_ms<=%s AND (f.asof_ms-60000) %% 600000=0
          ORDER BY f.asof_ms DESC LIMIT 10000''',(CATEGORY,SYMBOL,config.protocol,now)).fetchall()
    result={'issued_predictions':total,'observations':len(rows),'sampling':'fixed_10m_UTC_grid',
            'max_scored_samples':10000,'metrics':None,'status':'collecting'}
    if rows:
        records=[r[0] for r in rows]
        returns=np.array([(float(close)/s['reference_price']-1)*100 for s,close in rows])
        y=classify(returns,config.band_bps)
        p=np.array([[s['probabilities'][c] for c in CLASSES] for s in records])
        base=np.array([[s['baseline_probabilities'][c] for c in CLASSES] for s in records])
        expected=np.array([s['expected_return_pct'] for s in records])
        low=np.array([s['interval80_return_pct'][0] for s in records])
        high=np.array([s['interval80_return_pct'][1] for s in records])
        result['metrics']=metric_summary(y,p,base,returns,expected,low,high)
        result['observed_days']=len({s['asof_ms']//86_400_000 for s in records})
        result['status']='observing' if result['observed_days']>=7 and len(rows)>=100 else 'collecting'
    return result
