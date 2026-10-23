import numpy as np
import pandas as pd
import pytest

from analysis import build_features, evaluate, nonoverlap_events, daily_bootstrap_ci


def candles(n=1800):
    t = np.arange(n)
    # Positive trend with periodic breakout/volume events, large enough for
    # distinct training and test events at every candidate threshold.
    close = 100 + t*0.03 + np.sin(t/17)*0.2
    return pd.DataFrame({'start_ms': t*60000, 'open':close,
        'high':close+0.01,'low':close-0.01,'close':close,
        'volume':np.where(t%71==0, 40., 10.)})


def test_features_invariant_to_future_and_prefix():
    original = candles()
    changed = original.copy()
    changed.loc[1000:, ['open','high','low','close','volume']] *= 3
    cols = ['volume_ratio','ret_15m','volatility_60m','range_pct',
            'breakout_up','breakout_down','breakout_up_raw','breakout_down_raw']
    a,b = build_features(original),build_features(changed)
    pd.testing.assert_frame_equal(a.loc[:999,cols],b.loc[:999,cols])
    pd.testing.assert_frame_equal(a.loc[:999,cols],build_features(original.iloc[:1000])[cols])


def test_gap_invalidates_features_and_crossing_labels():
    f = build_features(candles(300).drop(index=100))
    before = f[f.start_ms==99*60000].iloc[0]
    after = f[(f.start_ms>100*60000)&(f.start_ms<=160*60000)]
    assert np.isnan(before.fwd_15m) and np.isnan(before.fwd_60m)
    assert after.volume_ratio.isna().all()
    assert not after.breakout_up.any()
    assert pd.notna(f[f.start_ms==161*60000].iloc[0].volume_ratio)


def test_outcomes_use_correct_endpoint_and_exclude_tail():
    data = candles(300)
    f = build_features(data)
    for h in (15,60):
        assert f.iloc[70][f'fwd_{h}m'] == pytest.approx((data.close[70+h]/data.close[70]-1)*100)
        assert f.tail(h)[f'fwd_{h}m'].isna().all()


def test_zero_volume_no_infinite_features():
    d = candles(200)
    d['volume'] = 0
    f = build_features(d)
    assert f.volume_ratio.isna().all()
    assert not f.breakout_up.any()


def test_holdout_changes_do_not_affect_train_selection_or_score():
    d = candles()
    split = 1200*60000
    a = evaluate(d, split_ms=split, minimum=2)
    d.loc[1200:, ['open','high','low','close']] *= np.linspace(1,2,len(d)-1200)[:,None]
    d.loc[1200:, 'volume'] *= 3
    b = evaluate(d, split_ms=split, minimum=2)
    assert a['train_rows'] == 1139  # label close strictly earlier than split
    for x,y in zip(a['patterns'],b['patterns']):
        assert x.get('volume_threshold') == y.get('volume_threshold')
        assert x.get('train') == y.get('train')
    assert a['patterns'][0]['test'] != b['patterns'][0]['test']


def test_purged_training_label_cannot_see_boundary():
    d = candles()
    a = evaluate(d, split_ms=1200*60000, minimum=2)
    # Alter just the last purged candle as well as the entire test period.
    d.loc[1199:, ['open','high','low','close']] *= 5
    b = evaluate(d, split_ms=1200*60000, minimum=2)
    assert a['patterns'][0]['train'] == b['patterns'][0]['train']


def test_insufficient_history_and_training_events():
    assert evaluate(candles(10))['status']=='insufficient_history'
    r = evaluate(candles(200),minimum=100)
    assert all(p['status']=='insufficient_training_events' for p in r['patterns'])


def test_nonoverlap_uses_wall_time_after_gap():
    d = pd.DataFrame({'start_ms':[0, 60000, 3600000, 7200000]})
    selected = nonoverlap_events(d,pd.Series([True]*4))
    assert selected.start_ms.tolist()==[0,3600000,7200000]


def test_bootstrap_requires_days_and_is_reproducible():
    d = pd.DataFrame({'start_ms':np.arange(8)*86400000,'fwd_60m':np.arange(8)*0.1})
    assert daily_bootstrap_ci(d.iloc[:4],'fwd_60m',1) is None
    assert daily_bootstrap_ci(d,'fwd_60m',1)==daily_bootstrap_ci(d,'fwd_60m',1)


def test_sort_and_dedup():
    d = candles(200)
    mixed = pd.concat([d.iloc[::-1],d.iloc[:20]])
    pd.testing.assert_frame_equal(build_features(d),build_features(mixed))


def test_down_pattern_uses_directional_price_change():
    d = candles()
    for col in ('open','high','low','close'):
        d[col] = 300-d[col]
    d[['high','low']] = d[['low','high']].to_numpy()
    r = evaluate(d, split_ms=1200*60000, minimum=2)
    down = r['patterns'][1]
    assert down['direction']=='down'
    assert down['test']['60m']['observations']>=2
    assert down['test']['60m']['directional_mean_pct']>0
    assert down['test']['60m']['cost_sensitivity_mean_pct']==pytest.approx(
        down['test']['60m']['directional_mean_pct']-0.1)
