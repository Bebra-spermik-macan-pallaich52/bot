import json

import pytest

import health


def test_backfill_status_checks_rest_success_not_only_live_candles(tmp_path,monkeypatch):
    path = tmp_path/'backfill.json'
    monkeypatch.setenv('BACKFILL_STATE_PATH',str(path))
    now=10_000_000
    state={'last_full_success_ms':now-3600000,'last_recent_success_ms':now-60000,
           'symbol':health.SYMBOL,'category':health.CATEGORY}
    path.write_text(json.dumps(state))
    health.check_backfill_state(now)
    state['last_recent_success_ms']=now-300001
    path.write_text(json.dumps(state))
    with pytest.raises(RuntimeError,match='Recent REST'):
        health.check_backfill_state(now)
    state['last_recent_success_ms']=now
    state['last_full_success_ms']=0
    path.write_text(json.dumps(state))
    with pytest.raises(RuntimeError,match='Full REST'):
        health.check_backfill_state(now)


def test_missing_backfill_status_is_not_healthy(tmp_path,monkeypatch):
    monkeypatch.setenv('BACKFILL_STATE_PATH',str(tmp_path/'missing.json'))
    with pytest.raises(FileNotFoundError):
        health.check_backfill_state()


@pytest.mark.parametrize('failed',[False,True])
def test_worker_marks_only_successful_rest_repair(tmp_path,monkeypatch,failed):
    from unittest.mock import Mock
    import backfill
    path=tmp_path/'state.json'
    monkeypatch.setenv('BACKFILL_STATE_PATH',str(path))
    stop=Mock()
    stop.is_set.side_effect=[False,False,True]
    monkeypatch.setattr(backfill,'STOP',stop)
    monkeypatch.setattr(backfill.signal,'signal',Mock())
    monkeypatch.setattr(backfill,'setup',Mock())
    monkeypatch.setattr(backfill,'fill',Mock(side_effect=RuntimeError('REST denied') if failed else None))
    backfill.main()
    assert path.exists()
    data=json.loads(path.read_text())
    if failed:
        assert data['phase']=='error'
        assert data['last_recent_success_ms']==0
        with pytest.raises(RuntimeError,match='Last REST'):
            health.check_backfill_state()
    else:
        assert data['phase']=='ok'
        health.check_backfill_state()
