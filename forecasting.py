"""Fixed 10-minute probabilistic price model with purged chronological evaluation.

No execution, trading logic, parameter search on test, or synthetic price paths.
"""
from dataclasses import asdict, dataclass
import hashlib
import json

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

MINUTE = 60_000
HORIZON = 10
FEATURE_VERSION = 'ohlcv-10m-v1'
CLASSES = ('down','flat','up')
FEATURES = tuple([f'ret_{h}' for h in (1,3,5,10,30,60)] +
                 ['volatility_10','volatility_60','volume_ratio','range_pct','body_pct','range_position'])


@dataclass(frozen=True)
class Config:
    band_bps: float = 10.0
    train_minutes: int = 30*1440
    calibration_minutes: int = 5*1440
    test_minutes: int = 10*1440
    anchor_minutes: int = 1440
    min_train: int = 1000
    min_calibration: int = 200
    min_class: int = 20
    min_folds: int = 3

    def __post_init__(self):
        if not np.isfinite(self.band_bps) or not 0 < self.band_bps <= 100:
            raise ValueError('band_bps must be 0..100, exclusive of zero')
        if not 0 < self.calibration_minutes < self.train_minutes:
            raise ValueError('Calibration must be inside training window')
        if min(self.test_minutes,self.anchor_minutes,self.min_train,self.min_calibration,
               self.min_class,self.min_folds) < 1:
            raise ValueError('Invalid model configuration')

    @property
    def protocol(self):
        payload=json.dumps({'features':FEATURE_VERSION,'horizon':HORIZON,**asdict(self)},sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:20]


class InsufficientData(ValueError):
    pass


def prepare(df):
    f=df.sort_values('start_ms',kind='stable').drop_duplicates('start_ms',keep='last').copy().reset_index(drop=True)
    if f.empty:
        return f
    for col in ('open','high','low','close','volume'):
        f[col]=pd.to_numeric(f[col],errors='coerce').astype(float)
    valid=(np.isfinite(f[['open','high','low','close','volume']]).all(axis=1) &
           f[['open','high','low','close']].gt(0).all(axis=1) & f.volume.ge(0) &
           f.low.le(f[['open','close']].min(axis=1)) &
           f.high.ge(f[['open','close']].max(axis=1)) & f.start_ms.mod(MINUTE).eq(0))
    continuous=f.start_ms.diff().eq(MINUTE)
    past_ok=continuous.rolling(60).sum().eq(60) & valid.rolling(61).sum().eq(61)
    for h in (1,3,5,10,30,60):
        f[f'ret_{h}']=(f.close/f.close.shift(h)-1)*100
    returns=f.close.pct_change(fill_method=None)*100
    f['volatility_10']=returns.rolling(10).std()
    f['volatility_60']=returns.rolling(60).std()
    f['volume_ratio']=(f.volume/f.volume.shift(1).rolling(60).median().replace(0,np.nan)).clip(0,20)
    f['range_pct']=(f.high-f.low)/f.close*100
    f['body_pct']=(f.close/f.open-1)*100
    low=f.low.shift(1).rolling(60).min()
    span=f.high.shift(1).rolling(60).max()-low
    f['range_position']=((f.close-low)/span.replace(0,np.nan)).clip(-2,3)
    f.loc[~past_ok,list(FEATURES)]=np.nan
    f['features_valid']=np.isfinite(f[list(FEATURES)]).all(axis=1)
    future_ok=(continuous.shift(-1).rolling(HORIZON).sum().shift(-(HORIZON-1)).eq(HORIZON) &
               valid.shift(-1).rolling(HORIZON).sum().shift(-(HORIZON-1)).eq(HORIZON) & valid)
    f['target_return_pct']=((f.close.shift(-HORIZON)/f.close-1)*100).where(future_ok)
    # Stored timestamps are candle OPENS. An outcome is known only at its CLOSE.
    f['label_available_ms']=f.start_ms+(HORIZON+1)*MINUTE
    return f


def classify(values,band_bps):
    band=band_bps/100
    return np.where(values < -band,0,np.where(values > band,2,1)).astype(int)


def tempered(probabilities,temperature):
    logits=np.log(np.clip(probabilities,1e-12,1))/temperature
    logits-=logits.max(axis=1,keepdims=True)
    e=np.exp(logits)
    return e/e.sum(axis=1,keepdims=True)


def per_loss(y,probabilities):
    return -np.log(np.clip(probabilities[np.arange(len(y)),y],1e-12,1))


@dataclass
class Model:
    pipeline: object
    temperature: float
    prior: np.ndarray
    support: np.ndarray
    support_classes: np.ndarray
    class_means: np.ndarray
    metadata: dict

    def probabilities(self,frame):
        with threadpool_limits(limits=1):
            p=self.pipeline.predict_proba(frame[list(FEATURES)])
        return tempered(p,self.temperature)

    def distribution(self,p):
        # Approximate empirical class-conditional distribution with 101 quantile
        # support points per class. It describes endpoints, never the price path.
        weights=p[:,self.support_classes]/101
        cumulative=weights.cumsum(axis=1)
        low=self.support[(cumulative>=0.1).argmax(axis=1)]
        high=self.support[(cumulative>=0.9).argmax(axis=1)]
        return p@self.class_means,low,high


def fit_before(frame,cutoff_ms,config=Config()):
    if frame.empty or int(frame.start_ms.min()) > cutoff_ms-config.train_minutes*MINUTE:
        raise InsufficientData('training_history_too_short')
    calibration_start=cutoff_ms-config.calibration_minutes*MINUTE
    eligible=frame.features_valid & frame.target_return_pct.notna()
    fit=frame[eligible & frame.start_ms.ge(cutoff_ms-config.train_minutes*MINUTE) &
              frame.label_available_ms.lt(calibration_start)]
    calibration=frame[eligible & frame.start_ms.ge(calibration_start) &
                      frame.label_available_ms.lt(cutoff_ms)]
    if len(fit)<config.min_train or len(calibration)<config.min_calibration:
        raise InsufficientData('insufficient_contiguous_samples')
    y=classify(fit.target_return_pct.to_numpy(),config.band_bps)
    counts=np.bincount(y,minlength=3)
    if counts.min()<config.min_class:
        raise InsufficientData('insufficient_class_samples')
    pipeline=make_pipeline(StandardScaler(),LogisticRegression(C=0.3,max_iter=300,random_state=42))
    with threadpool_limits(limits=1):
        pipeline.fit(fit[list(FEATURES)],y)
        raw=pipeline.predict_proba(calibration[list(FEATURES)])
    cy=classify(calibration.target_return_pct.to_numpy(),config.band_bps)
    # Only past calibration labels select temperature; outer test never enters.
    temperatures=(1.0,0.75,1.5,2.0,3.0)
    temperature=min(temperatures,key=lambda t:float(per_loss(cy,tempered(raw,t)).mean()))
    all_past=pd.concat([fit,calibration])
    all_y=classify(all_past.target_return_pct.to_numpy(),config.band_bps)
    prior=(np.bincount(all_y,minlength=3)+1)/(len(all_y)+3)
    supports=[]; means=[]
    for cls in range(3):
        values=all_past.target_return_pct.to_numpy()[all_y==cls]
        means.append(float(values.mean()))
        supports.extend((float(v),cls) for v in np.quantile(values,(np.arange(101)+0.5)/101))
    supports.sort(key=lambda x:x[0])
    fingerprint=hashlib.sha256(pd.util.hash_pandas_object(
        all_past[['start_ms',*FEATURES,'target_return_pct']],index=False).values.tobytes()).hexdigest()
    model_id=hashlib.sha256(f'{config.protocol}:{cutoff_ms}:{fingerprint}'.encode()).hexdigest()[:24]
    metadata={'model_id':model_id,'protocol':config.protocol,'cutoff_ms':int(cutoff_ms),
        'fit_samples':len(fit),'calibration_samples':len(calibration),
        'fit_last_label_ms':int(fit.label_available_ms.max()),
        'calibration_start_ms':int(calibration_start),
        'calibration_last_label_ms':int(calibration.label_available_ms.max()),
        'temperature':temperature,'class_counts':np.bincount(all_y,minlength=3).tolist()}
    return Model(pipeline,temperature,prior,np.array([x[0] for x in supports]),
                 np.array([x[1] for x in supports]),np.array(means),metadata)


def metric_summary(y,p,baseline,returns,expected,low,high):
    pred=p.argmax(axis=1); reference=baseline.argmax(axis=1)
    onehot=np.eye(3)[y]
    def balanced(predicted):
        return float(np.mean([np.mean(predicted[y==c]==c) for c in range(3) if np.any(y==c)]))
    bins=[]
    confidence=p.max(axis=1)
    for lower,upper in zip((0,.4,.5,.6,.8),(.4,.5,.6,.8,1.000001)):
        mask=(confidence>=lower)&(confidence<upper)
        if mask.any():
            bins.append({'lower':lower,'upper':min(upper,1),'observations':int(mask.sum()),
                         'mean_probability':float(confidence[mask].mean()),
                         'observed_accuracy':float((pred[mask]==y[mask]).mean())})
    return {'observations':len(y),'log_loss':float(per_loss(y,p).mean()),
        'baseline_log_loss':float(per_loss(y,baseline).mean()),
        'brier':float(((p-onehot)**2).sum(axis=1).mean()),
        'baseline_brier':float(((baseline-onehot)**2).sum(axis=1).mean()),
        'accuracy':float((pred==y).mean()),'baseline_accuracy':float((reference==y).mean()),
        'balanced_accuracy':balanced(pred),'baseline_balanced_accuracy':balanced(reference),
        'return_mae_pct':float(np.abs(returns-expected).mean()),
        'zero_change_mae_pct':float(np.abs(returns).mean()),
        'interval80_coverage':float(((returns>=low)&(returns<=high)).mean()),
        'interval80_mean_width_pct':float((high-low).mean()),
        'class_counts':np.bincount(y,minlength=3).tolist(),'calibration_bins':bins}


def block_improvement_ci(timestamps,improvements):
    grouped=pd.DataFrame({'day':timestamps//86_400_000,'improvement':improvements}).groupby('day').improvement.agg(['sum','count'])
    if len(grouped)<10:
        return None
    rng=np.random.default_rng(42)
    choices=rng.integers(0,len(grouped),size=(1000,len(grouped)))
    means=grouped['sum'].to_numpy()[choices].sum(axis=1)/grouped['count'].to_numpy()[choices].sum(axis=1)
    return [float(v) for v in np.quantile(means,[.025,.975])]


def walk_forward(frame,config=Config()):
    report={'protocol':config.protocol,'horizon_minutes':HORIZON,'band_bps':config.band_bps,
            'config':asdict(config),'folds':[],'summary':None,'evaluated_folds':0,'evidence':'insufficient_history',
            'interpretation':'Exploratory historical validation; prospective predictions are recorded separately.'}
    if frame.empty:
        return report
    stride=config.anchor_minutes*MINUTE
    first=((int(frame.start_ms.min())+config.train_minutes*MINUTE+stride-1)//stride)*stride
    available_end=int(frame.start_ms.max())+MINUTE
    batches=[]
    for start in range(first,available_end,config.test_minutes*MINUTE):
        end=start+config.test_minutes*MINUTE
        if end>available_end:
            break
        fold={'test_start_ms':start,'test_end_ms':end}
        try:
            model=fit_before(frame,start,config)
            test=frame[frame.features_valid & frame.start_ms.ge(start) &
                frame.label_available_ms.lt(end) & frame.target_return_pct.notna() &
                frame.start_ms.mod(HORIZON*MINUTE).eq(0)]
            if len(test)<30:
                raise InsufficientData('insufficient_test_samples')
            p=model.probabilities(test)
            base=np.tile(model.prior,(len(test),1))
            expected,lo,hi=model.distribution(p)
            returns=test.target_return_pct.to_numpy()
            y=classify(returns,config.band_bps)
            fold.update(status='evaluated',training=model.metadata,
                        metrics=metric_summary(y,p,base,returns,expected,lo,hi))
            batches.append((test.start_ms.to_numpy(),y,p,base,returns,expected,lo,hi))
        except InsufficientData as err:
            fold.update(status='skipped',reason=str(err))
        report['folds'].append(fold)
    if batches:
        timestamps,y,p,base,returns,expected,lo,hi=[np.concatenate([b[i] for b in batches]) for i in range(8)]
        report['summary']=metric_summary(y,p,base,returns,expected,lo,hi)
        ci=block_improvement_ci(timestamps,per_loss(y,base)-per_loss(y,p))
        report['summary']['log_loss_improvement_ci95_day_bootstrap']=ci
        report['evaluated_folds']=len(batches)
        if len(batches)>=config.min_folds:
            report['evidence']='exploratory_edge' if (ci and ci[0]>0 and
                report['summary']['brier']<report['summary']['baseline_brier']) else 'no_edge_detected'
    return report


def latest_forecast(frame,model,config,now_ms):
    if frame.empty:
        return None,'no_candles'
    last=frame.iloc[[-1]]
    asof=int(last.iloc[0].start_ms)+MINUTE
    if not 0<=now_ms-asof<=90_000:
        return None,'stale_candles'
    if not bool(last.iloc[0].features_valid):
        return None,'gaps_or_invalid_features'
    if model.metadata['protocol']!=config.protocol or model.metadata['cutoff_ms']>int(last.iloc[0].start_ms):
        return None,'incompatible_model'
    p=model.probabilities(last)
    expected,lo,hi=model.distribution(p)
    price=float(last.iloc[0].close)
    return {'asof_ms':asof,'target_ms':asof+HORIZON*MINUTE,'reference_price':price,
            'probabilities':dict(zip(CLASSES,map(float,p[0]))),'most_likely':CLASSES[int(p[0].argmax())],
            'expected_return_pct':float(expected[0]),'interval80_return_pct':[float(lo[0]),float(hi[0])],
            'estimated_price':price*(1+float(expected[0])/100),
            'interval80_price':[price*(1+float(lo[0])/100),price*(1+float(hi[0])/100)],
            'model_id':model.metadata['model_id'],'model_cutoff_ms':model.metadata['cutoff_ms']},None
