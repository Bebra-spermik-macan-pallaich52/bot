from dataclasses import replace
import json

import joblib
import numpy as np
import pandas as pd
import pytest

from forecasting import (Config,FEATURES,HORIZON,InsufficientData,block_improvement_ci,
    classify,fit_before,latest_forecast,prepare,walk_forward)

CFG=Config(train_minutes=600,calibration_minutes=120,test_minutes=360,anchor_minutes=60,
           min_train=200,min_calibration=50,min_class=5,min_folds=2)


def market(n=1800):
    rng=np.random.default_rng(42)
    t=np.arange(n)
    changes=.025*np.sin(t/30)+rng.normal(0,.02,n)
    close=100*np.exp(np.cumsum(changes)/100)
    return pd.DataFrame({'start_ms':t*60000,'open':close,'high':close*1.0005,
        'low':close*.9995,'close':close,'volume':100+2000*np.abs(changes)})


def test_features_are_prefix_invariant_and_never_include_labels():
    source=market()
    full=prepare(source)
    prefix=prepare(source.iloc[:1000])
    pd.testing.assert_frame_equal(full.loc[:999,list(FEATURES)],prefix[list(FEATURES)])
    assert 'target_return_pct' not in FEATURES
    changed=source.copy()
    changed.loc[1000:,['open','high','low','close','volume']]*=2
    pd.testing.assert_frame_equal(full.loc[:999,list(FEATURES)],prepare(changed).loc[:999,list(FEATURES)])


def test_gap_invalidates_past_features_and_ten_minute_labels():
    f=prepare(market(300).drop(index=100))
    assert not f[(f.start_ms>100*60000)&(f.start_ms<=160*60000)].features_valid.any()
    assert f[f.start_ms.eq(99*60000)].target_return_pct.isna().all()
    assert f.tail(HORIZON).target_return_pct.isna().all()
    assert f[f.start_ms.eq(161*60000)].features_valid.all()


def test_target_is_ten_minute_endpoint_at_close_not_candle_open():
    source=market(300); frame=prepare(source)
    assert frame.iloc[90].target_return_pct==pytest.approx((source.close[100]/source.close[90]-1)*100)
    assert frame.iloc[90].label_available_ms==(90+10+1)*60000
    assert classify(np.array([-.1001,-.1,0,.1,.1001]),10).tolist()==[0,1,1,1,2]


def test_future_test_changes_cannot_change_model_scaling_calibration_or_distribution():
    source=market(); cutoff=900*60000
    first=fit_before(prepare(source),cutoff,CFG)
    source.loc[900:,['open','high','low','close']]*=np.linspace(1,3,len(source)-900)[:,None]
    source.loc[900:,'volume']*=100
    second=fit_before(prepare(source),cutoff,CFG)
    assert first.metadata==second.metadata
    np.testing.assert_allclose(first.pipeline[0].mean_,second.pipeline[0].mean_)
    np.testing.assert_allclose(first.pipeline[1].coef_,second.pipeline[1].coef_)
    np.testing.assert_allclose(first.support,second.support)
    np.testing.assert_allclose(first.prior,second.prior)
    assert first.metadata['fit_last_label_ms'] < first.metadata['calibration_start_ms']
    assert first.metadata['calibration_last_label_ms'] < cutoff


def test_calibration_tail_is_purged_from_fit():
    f=prepare(market())
    model=fit_before(f,900*60000,CFG)
    boundary=model.metadata['calibration_start_ms']//60000
    source=market()
    # Mutating the first calibration candle cannot affect fitted coefficients.
    source.loc[boundary,['open','high','low','close']]*=1.1
    altered=fit_before(prepare(source),900*60000,CFG)
    np.testing.assert_allclose(model.pipeline[1].coef_,altered.pipeline[1].coef_)


def test_walk_forward_nonoverlap_and_future_fold_invariance():
    source=market(1800)
    a=walk_forward(prepare(source),CFG)
    assert a['evaluated_folds']>=2
    first=a['folds'][0]
    assert first['training']['calibration_last_label_ms']<first['test_start_ms']
    assert first['metrics']['observations']<=CFG.test_minutes//10
    source.loc[source.start_ms>=first['test_end_ms'],['open','high','low','close']]*=1.5
    b=walk_forward(prepare(source),CFG)
    assert a['folds'][0]==b['folds'][0]
    assert a['summary']['observations']==sum(f['metrics']['observations'] for f in a['folds'] if f['status']=='evaluated')
    json.dumps(a,allow_nan=False)


def test_model_learns_predictable_synthetic_series_without_claim_about_market():
    frame=prepare(market(1800))
    model=fit_before(frame,900*60000,CFG)
    test=frame[frame.features_valid & frame.start_ms.ge(900*60000)&frame.start_ms.lt(1200*60000)]
    from forecasting import per_loss
    y=classify(test.target_return_pct.to_numpy(),CFG.band_bps)
    p=model.probabilities(test)
    baseline=np.tile(model.prior,(len(y),1))
    assert per_loss(y,p).mean()<per_loss(y,baseline).mean()
    np.testing.assert_allclose(p.sum(axis=1),1)
    assert (p>=0).all() and (p<=1).all()


def test_live_forecast_target_freshness_and_cache_roundtrip(tmp_path):
    frame=prepare(market(1800)); model=fit_before(frame,1700*60000,CFG)
    now=1800*60000+1000
    live,reason=latest_forecast(frame,model,CFG,now)
    assert reason is None
    assert live['target_ms']==live['asof_ms']+600000
    assert live['interval80_price'][0]<=live['interval80_price'][1]
    assert sum(live['probabilities'].values())==pytest.approx(1)
    path=tmp_path/'model.joblib';joblib.dump(model,path)
    again,_=latest_forecast(frame,joblib.load(path),CFG,now)
    assert live==again
    assert latest_forecast(frame,model,CFG,now+100000)==(None,'stale_candles')
    assert latest_forecast(frame,model,replace(CFG,band_bps=20),now)==(None,'incompatible_model')


def test_no_fake_forecast_with_short_or_single_class_history():
    frame=prepare(market(200))
    with pytest.raises(InsufficientData,match='history'):
        fit_before(frame,199*60000,CFG)
    frame=prepare(market())
    with pytest.raises(InsufficientData,match='class'):
        fit_before(frame,900*60000,replace(CFG,band_bps=100))
    assert walk_forward(prepare(market(200)),CFG)['summary'] is None


def test_daily_block_interval_requires_days_not_overlapping_minute_count():
    assert block_improvement_ci(np.arange(5000)*60000,np.ones(5000)) is None
    result=block_improvement_ci(np.arange(20)*86400000,np.ones(20)*.1)
    assert result==pytest.approx([.1,.1])
