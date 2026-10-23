"""Hourly model refresh, minute forecasts and an immutable prospective journal."""
import json
import logging
import os
from pathlib import Path
import signal
import threading
import time

import joblib

from analysis import load_candles
from forecasting import Config, HORIZON, InsufficientData, fit_before, latest_forecast, prepare, walk_forward
from forecast_store import prospective_summary, record_forecast, setup_forecasts
from storage import CATEGORY, SYMBOL, MIN_MS, setup

STOP=threading.Event()


def write_json(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(data,allow_nan=False,indent=2)+'\n')
    temp.replace(path)


def run(config=None):
    config=config or Config(band_bps=float(os.getenv('FORECAST_BAND_BPS','10')))
    now=int(time.time()*1000)
    report={'symbol':SYMBOL,'category':CATEGORY,'horizon_minutes':HORIZON,
            'band_bps':config.band_bps,'protocol':config.protocol,'generated_at_ms':now,
            'status':'waiting','reason':None,'forecast':None,'validation':None,'prospective':None}
    path=Path(os.getenv('FORECAST_REPORT_PATH','reports/forecast.json'))
    root=Path(os.getenv('FORECAST_STATE_DIR','forecast_state'))
    root.mkdir(parents=True,exist_ok=True)
    try:
        frame=prepare(load_candles())
        if frame.empty:
            raise InsufficientData('no_candles')
        if int(frame.iloc[-1].start_ms)+MIN_MS>now:
            raise InsufficientData('unclosed_or_future_candles')
        report['source_last_start_ms']=int(frame.iloc[-1].start_ms)
        cached=None
        validation_path=root/'validation.json'
        try:
            cached=json.loads(validation_path.read_text())
        except (OSError,ValueError):
            pass
        # Re-evaluate completed test blocks on a new day, a substantial backfill,
        # configuration change, or after six hours. Repeated views stay exploratory.
        if not (isinstance(cached,dict) and cached.get('protocol')==config.protocol and
                cached.get('symbol')==SYMBOL and cached.get('category')==CATEGORY and
                0<=now-cached.get('computed_at_ms',0)<6*3600_000 and
                cached.get('source_day')==report['source_last_start_ms']//86_400_000 and
                len(frame)<=cached.get('rows',0)+1440):
            cached={'protocol':config.protocol,'symbol':SYMBOL,'category':CATEGORY,'computed_at_ms':now,'rows':len(frame),
                    'source_day':report['source_last_start_ms']//86_400_000,
                    'validation':walk_forward(frame,config)}
            write_json(validation_path,cached)
        report['validation']=cached['validation']
        model=None
        model_path=root/'model.joblib'
        if model_path.exists():
            # Load only this worker's own trusted state volume, never uploaded models.
            try:
                bundle=joblib.load(model_path)
                candidate=bundle['model']
                if (bundle['symbol']==SYMBOL and bundle['category']==CATEGORY and candidate.metadata['protocol']==config.protocol and
                    0<=report['source_last_start_ms']-candidate.metadata['cutoff_ms']<3600_000):
                    model=candidate
            except Exception:
                logging.warning('Model cache unusable; fitting from data')
        if model is None:
            model=fit_before(frame,report['source_last_start_ms'],config)
            temp=model_path.with_suffix('.tmp')
            joblib.dump({'model':model,'symbol':SYMBOL,'category':CATEGORY},temp)
            temp.replace(model_path)
        # Recheck the clock AFTER fitting; a slow evaluation cannot backdate a quote.
        forecast,reason=latest_forecast(frame,model,config,int(time.time()*1000))
        if forecast is None:
            report['reason']=reason
        else:
            report['forecast']=record_forecast(forecast,config,model.prior)
            report['status']='experimental'
        report['training']=model.metadata
        report['prospective']=prospective_summary(config)
    except InsufficientData as err:
        report['reason']=str(err)
    except Exception:
        logging.exception('Forecast calculation failed')
        report.update(status='error',reason='calculation_failed',forecast=None)
    report['generated_at_ms']=int(time.time()*1000)
    write_json(path,report)
    logging.info('10m forecast status=%s reason=%s',report['status'],report['reason'])
    return report


def main():
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    for sig in (signal.SIGINT,signal.SIGTERM):
        signal.signal(sig,lambda *_:STOP.set())
    while not STOP.is_set():
        try:
            setup()
            setup_forecasts()
            run()
        except Exception:
            logging.exception('Forecaster startup/storage failure')
        STOP.wait(60)


if __name__=='__main__':
    main()
