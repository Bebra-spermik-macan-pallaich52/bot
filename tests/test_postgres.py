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
