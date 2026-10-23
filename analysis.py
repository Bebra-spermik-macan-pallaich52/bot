"""Causal features, train-only pattern selection, purged chronological holdout.

This is an event study of price changes, not an executable trading strategy.
"""
import json
import logging
import os
from pathlib import Path
import signal
import threading
import time

import numpy as np
import pandas as pd

from storage import CATEGORY, SYMBOL, MIN_MS, connect, setup

WINDOW = 60
HORIZONS = (15, 60)
THRESHOLDS = (1.5, 2.0, 3.0)
STOP = threading.Event()


def build_features(df):
    df = df.sort_values('start_ms').drop_duplicates('start_ms').copy().reset_index(drop=True)
    if df.empty:
        return df
    for col in ('open','high','low','close','volume'):
        df[col] = df[col].astype(float)
    continuous = df.start_ms.diff().eq(MIN_MS)
    past_ok = continuous.rolling(WINDOW, min_periods=WINDOW).sum().eq(WINDOW)
    prev = df.shift(1)
    median_volume = prev.volume.rolling(WINDOW).median().replace(0, np.nan)
    df['volume_ratio'] = (df.volume/median_volume).where(past_ok)
    df['ret_15m'] = (df.close/df.close.shift(15)-1).where(past_ok)
    df['volatility_60m'] = df.close.pct_change(fill_method=None).rolling(WINDOW).std().where(past_ok)
    df['range_pct'] = ((df.high-df.low)/df.close*100).where(past_ok)
    df['breakout_up_raw'] = (df.close > prev.high.rolling(WINDOW).max()) & past_ok
    df['breakout_down_raw'] = (df.close < prev.low.rolling(WINDOW).min()) & past_ok
    df['breakout_up'] = df.breakout_up_raw & (df.volume_ratio >= 2)
    df['breakout_down'] = df.breakout_down_raw & (df.volume_ratio >= 2)
    for h in HORIZONS:
        # Labels are isolated from all feature and event definitions.
        valid = continuous.shift(-1).rolling(h, min_periods=h).sum().shift(-(h-1)).eq(h)
        df[f'fwd_{h}m'] = ((df.close.shift(-h)/df.close-1)*100).where(valid)
    return df


def nonoverlap_events(df, mask, cooldown=60):
    selected = []
    last_time = -float('inf')
    for i in np.flatnonzero(mask.fillna(False).to_numpy()):
        ts = int(df.iloc[i].start_ms)
        if ts-last_time >= cooldown*MIN_MS:
            selected.append(i)
            last_time = ts
    return df.iloc[selected]


def daily_bootstrap_ci(sample, column, direction, repetitions=1000):
    """Resample UTC day clusters, not individual dependent candles/events.

    Descriptive, unadjusted interval for event mean; not an excess-return test.
    Few days => no interval. Fixed seed makes saved reports reproducible.
    """
    valid = sample.dropna(subset=[column])
    values = pd.DataFrame({'day': valid.start_ms//86_400_000,
                           'value': direction*valid[column]})
    groups = values.groupby('day').value.agg(['sum','count'])
    if len(groups) < 5:
        return None
    rng = np.random.default_rng(42)
    choices = rng.integers(0, len(groups), size=(repetitions, len(groups)))
    sums, counts = groups['sum'].to_numpy(), groups['count'].to_numpy()
    means = sums[choices].sum(axis=1)/counts[choices].sum(axis=1)
    return [float(x) for x in np.quantile(means, [0.025, 0.975])]


def metrics(sample, baseline, direction, minimum=30, cost_bps=10):
    result = {}
    for h in HORIZONS:
        col = f'fwd_{h}m'
        v = sample[col].dropna()*direction
        b = baseline[col].dropna()*direction
        mean = float(v.mean()) if len(v) else None
        ref = float(b.mean()) if len(b) else None
        result[f'{h}m'] = {
            'observations': len(v), 'sufficient_sample': len(v) >= minimum,
            'directional_mean_pct': mean,
            'positive_fraction': float(v.gt(0).mean()) if len(v) else None,
            'baseline_mean_pct': ref,
            'excess_mean_pct': mean-ref if mean is not None and ref is not None else None,
            'cost_sensitivity_mean_pct': mean-cost_bps/100 if mean is not None else None,
            'mean_ci95_day_bootstrap_pct': daily_bootstrap_ci(sample, col, direction),
        }
    return result


def evaluate(df, split_ms=None, train_fraction=0.7, minimum=30, cost_bps=10):
    if not 0 < train_fraction < 1 or minimum < 1 or cost_bps < 0:
        raise ValueError('Invalid evaluation parameters')
    f = build_features(df)
    if len(f) < WINDOW+max(HORIZONS)+2:
        return {'status':'insufficient_history','rows':len(f),'patterns':[]}
    fixed = split_ms is not None
    split = int(split_ms) if fixed else int(f.iloc[int(len(f)*train_fraction)].start_ms)
    if not int(f.iloc[0].start_ms) < split <= int(f.iloc[-1].start_ms):
        raise ValueError('TEST_START_MS must be within available history')
    # The event is known at candle CLOSE, not its stored open timestamp.
    # Every training label closes strictly BEFORE the first test candle starts.
    train = f[f.start_ms+(max(HORIZONS)+1)*MIN_MS < split]
    test = f[f.start_ms >= split]
    patterns = []
    for name, direction in (('up',1), ('down',-1)):
        raw = f'breakout_{name}_raw'
        candidates = []
        for threshold in THRESHOLDS:
            events = nonoverlap_events(train, train[raw] & train.volume_ratio.ge(threshold))
            values = events['fwd_60m'].dropna()*direction
            baseline = train['fwd_60m'].dropna()*direction
            if len(values) >= minimum and len(baseline):
                candidates.append((float(values.mean()-baseline.mean()), threshold, events))
        if not candidates:
            patterns.append({'direction':name,'status':'insufficient_training_events'})
            continue
        # Select using training outcomes ONLY, with deterministic tie breaking.
        score, threshold, events = max(candidates, key=lambda x:(x[0], -x[1]))
        heldout = nonoverlap_events(test, test[raw] & test.volume_ratio.ge(threshold))
        patterns.append({'direction':name, 'volume_threshold':threshold,
            'training_score_excess_60m_pct':score,
            'train':metrics(events, train, direction, minimum, cost_bps),
            'test':metrics(heldout, test, direction, minimum, cost_bps)})
    return {'status':'evaluated', 'category':CATEGORY, 'symbol':SYMBOL,
        'rows':len(f), 'first_start_ms':int(f.iloc[0].start_ms),
        'last_start_ms':int(f.iloc[-1].start_ms), 'split_ms':split,
        'fixed_split':fixed, 'train_rows':len(train), 'test_rows':len(test),
        'purge_minutes':max(HORIZONS)+1, 'candidate_count':len(THRESHOLDS)*2,
        'cost_sensitivity_roundtrip_bps':cost_bps, 'patterns':patterns,
        'limitations':[
            'Descriptive price event study; no orders or profitability claim.',
            'Baseline uses all eligible bars, is not a matched independent control.',
            'Day bootstrap intervals are unadjusted; no multiple-testing significance claim.',
            'Repeated holdout inspection and adaptive split reuse compromise out-of-sample evidence.',
            'Costs are a sensitivity subtraction, not executable fills, funding or slippage modelling.']}


def load_candles():
    with connect() as conn:
        rows = conn.execute('''SELECT start_ms,open,high,low,close,volume FROM candles
          WHERE exchange='bybit' AND category=%s AND symbol=%s AND interval='1'
          ORDER BY start_ms DESC LIMIT 130000''', (CATEGORY,SYMBOL)).fetchall()
    return pd.DataFrame(rows, columns=['start_ms','open','high','low','close','volume'])


def run():
    split = os.getenv('TEST_START_MS')
    report = evaluate(load_candles(), split_ms=int(split) if split else None,
                      minimum=int(os.getenv('MIN_EVENTS','30')),
                      cost_bps=float(os.getenv('COST_BPS','10')))
    report['symbol'], report['category'] = SYMBOL, CATEGORY
    report['generated_at_ms'] = int(time.time()*1000)
    path = Path(os.getenv('REPORT_PATH','reports/latest.json'))
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    temp.replace(path)
    logging.info('Research report: %s', json.dumps(report, allow_nan=False))
    return report


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: STOP.set())
    while not STOP.is_set():
        try:
            setup()
            run()
        except Exception:
            logging.exception('Analysis failed')
        STOP.wait(300)


if __name__ == '__main__':
    main()
