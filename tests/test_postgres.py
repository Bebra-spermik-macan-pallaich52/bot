"""Integration: explicit isolated test database only, no production deletion."""
import os
from concurrent.futures import ThreadPoolExecutor
import time

import pytest

import storage
import analysis
import health

pytestmark = pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'),reason='Set TEST_DATABASE_URL for isolated PostgreSQL integration')


@pytest.fixture
def database(monkeypatch):
    monkeypatch.setenv('DATABASE_URL',os.environ['TEST_DATABASE_URL'])
    with storage.connect() as conn:
        assert conn.info.dbname.endswith('_test'), 'Use a dedicated *_test database'
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(lambda _:storage.setup(),range(3)))
    with storage.connect() as conn:
        conn.execute('TRUNCATE candles')
    yield


def row(ts,close='101'):
    return storage.candle_row(ts,['100','102','99',close,'10','1000'])


def test_upsert_and_real_analysis(database,tmp_path,monkeypatch):
    rows=[row(t*60000) for t in range(300)]
    storage.save_rows(rows)
    storage.save_rows(rows)
    storage.save_rows([row(0,'100.5')])
    with storage.connect() as conn:
        assert conn.execute('SELECT count(*) FROM candles').fetchone()[0]==300
        assert float(conn.execute('SELECT close FROM candles WHERE start_ms=0').fetchone()[0])==100.5
    monkeypatch.setenv('REPORT_PATH',str(tmp_path/'latest.json'))
    report=analysis.run()
    assert report['status']=='evaluated'
    assert (tmp_path/'latest.json').exists()
    assert report['rows']==300


def test_recent_gap_detection_and_repair(database):
    end=int(time.time()*1000)//60000*60000-3*60000
    rows=[row(t) for t in range(end-9*60000,end+1,60000)]
    storage.save_rows(rows[:-1])
    with pytest.raises(RuntimeError,match='9/10'):
        health.check_ingestion()
    storage.save_rows(rows[-1:])
    health.check_ingestion()


def test_repair_persists_after_connection_failure(database):
    storage.save_rows([row(0)])
    with pytest.raises(Exception):
        with storage.connect() as conn:
            conn.execute('SELECT 1/0')
    storage.save_rows([row(60000)])
    with storage.connect() as conn:
        assert conn.execute('SELECT count(*) FROM candles').fetchone()[0]==2


def test_live_candle_and_rest_gap_repair_roundtrip(database,monkeypatch):
    import collector
    import backfill
    candle={'confirm':True,'start':0,'open':'100','high':'102','low':'99',
            'close':'101','volume':'10','turnover':'1000'}
    assert collector.save_candle(candle)
    def fetch(start,end,**kwargs):
        return [row(t) for t in range(start,end+1,60000)]
    monkeypatch.setattr(backfill,'fetch_page',fetch)
    backfill.fill(10/1440, now_ms=10*60000)
    backfill.fill(10/1440, now_ms=10*60000)
    with storage.connect() as conn:
        assert conn.execute('SELECT count(*) FROM candles').fetchone()[0]==10
        assert conn.execute('SELECT max(start_ms) FROM candles').fetchone()[0]==9*60000


def test_real_quality_audit_and_read_only_dashboard(database,tmp_path,monkeypatch):
    import json
    import quality
    import dashboard
    now=2*quality.DAY_MS+30000
    begin=quality.DAY_MS
    storage.save_rows([row(ts) for ts in range(begin,2*quality.DAY_MS,60000)])
    result=quality.audit(days=1,now_ms=now)
    assert result['ready'] is True
    assert result['total_candles']==1440
    assert result['missing_candles']==0
    with storage.connect() as conn:
        conn.execute('DELETE FROM candles WHERE start_ms IN (%s,%s)',(begin,begin+60000))
    result=quality.audit(days=1,now_ms=now)
    assert result['ready'] is False
    assert result['missing_candles']==2
    assert result['gap_ranges'][0]['minutes']==2
    # An invalid externally imported row and a future row cannot be called ready.
    storage.save_rows([row(begin),row(begin+60000)])
    malformed=list(row(begin)); malformed[4]=-1
    storage.save_rows([tuple(malformed),row(2*quality.DAY_MS)])
    result=quality.audit(days=1,now_ms=now)
    assert result['invalid_candles']==1
    assert result['unclosed_or_future_candles']==1
    assert result['ready'] is False
    monkeypatch.setenv('BACKFILL_DAYS','1')
    monkeypatch.setenv('REPORT_PATH',str(tmp_path/'none.json'))
    monkeypatch.setenv('BACKFILL_STATE_PATH',str(tmp_path/'none-state.json'))
    monkeypatch.setattr(dashboard.time,'time',lambda:now/1000)
    status=dashboard.build_status()
    assert status['database']['state']=='ok'
    assert status['quality']['invalid_candles']==1
    assert status['ready'] is False
    with storage.connect() as conn:
        assert conn.execute('SELECT count(*) FROM candles').fetchone()[0]==1441


def test_forecast_journal_is_immutable_prospective_and_scores_only_after_target(database):
    from forecast_store import setup_forecasts,record_forecast,prospective_summary
    from forecasting import Config
    config=Config();setup_forecasts()
    with storage.connect() as conn:
        conn.execute('TRUNCATE forecasts')
    asof=6_060_000
    live={'asof_ms':asof,'target_ms':asof+600000,'reference_price':100.,
          'probabilities':{'down':.2,'flat':.6,'up':.2},'model_id':'fixture',
          'expected_return_pct':0.,'interval80_return_pct':[-.2,.2]}
    saved=record_forecast(live,config,[.3,.4,.3],now_ms=asof+1000)
    changed={**live,'probabilities':{'down':.1,'flat':.1,'up':.8}}
    assert record_forecast(changed,config,[.3,.4,.3],now_ms=asof+2000)==saved
    assert prospective_summary(config,now_ms=asof+599999)['observations']==0
    storage.save_rows([row(asof+600000-60000)])
    result=prospective_summary(config,now_ms=asof+600000)
    assert result['issued_predictions']==1 and result['observations']==1
    assert result['metrics']['class_counts']==[0,0,1]
    with pytest.raises(ValueError,match='stale/backdated'):
        record_forecast(live,config,[.3,.4,.3],now_ms=asof+90001)
    # An overlapping minute prediction exists in the journal but is not another
    # independent scored observation on the fixed ten-minute source grid.
    overlapping={**live,'asof_ms':asof+60000,'target_ms':asof+660000}
    record_forecast(overlapping,config,[.3,.4,.3],now_ms=asof+61000)
    storage.save_rows([row(asof+660000-60000)])
    result=prospective_summary(config,now_ms=asof+660000)
    assert result['issued_predictions']==2 and result['observations']==1


def test_forecast_worker_real_db_model_cache_and_waiting_state(database,tmp_path,monkeypatch):
    import json
    import forecaster
    from forecast_store import setup_forecasts
    from test_forecasting import market,CFG
    setup_forecasts()
    with storage.connect() as conn:
        conn.execute('TRUNCATE forecasts')
    monkeypatch.setenv('FORECAST_REPORT_PATH',str(tmp_path/'forecast.json'))
    monkeypatch.setenv('FORECAST_STATE_DIR',str(tmp_path/'models'))
    waiting=forecaster.run(CFG)
    assert waiting['status']=='waiting' and waiting['forecast'] is None
    assert waiting['reason']=='no_candles'
    data=market(1800)
    boundary=int(time.time()*1000)//60000*60000
    data['start_ms']+=boundary-1800*60000
    storage.save_rows([storage.candle_row(int(r.start_ms),[r.open,r.high,r.low,r.close,r.volume,1000])
                       for r in data.itertuples()])
    first=forecaster.run(CFG)
    assert first['status']=='experimental'
    assert first['forecast']['target_ms']==boundary+600000
    second=forecaster.run(CFG)
    assert second['forecast']==first['forecast']
    assert second['prospective']['issued_predictions']==1
    assert json.loads((tmp_path/'forecast.json').read_text())['protocol']==CFG.protocol
    assert (tmp_path/'models/model.joblib').exists()
