import json
from unittest.mock import Mock
import threading

import pytest
import requests

import backfill
import bybit
import collector
from storage import candle_row


def response(rows, code=0, status=200):
    r = Mock(status_code=status)
    r.json.return_value={'retCode':code,'result':{'list':rows}}
    return r


def values(t=0):
    return [str(t),'100','102','99','101','10','1000']


def test_rest_reverse_order_and_duplicate_safe():
    s = Mock()
    s.get.return_value=response([values(60000),values(0),values(0)])
    rows = bybit.fetch_page(0,60000,session=s)
    assert [r[3] for r in rows]==[0,60000]


@pytest.mark.parametrize('failure',[requests.Timeout(),requests.ConnectionError(),
    response([], status=429),response([],status=503),response([],code=10006),response([])])
def test_rest_retries_transients_and_missing_pages(failure):
    s = Mock()
    s.get.side_effect=[failure,response([values()])]
    sleep = Mock()
    assert len(bybit.fetch_page(0,0,session=s,sleep=sleep))==1
    assert s.get.call_count==2 and sleep.call_count==1


def test_rest_retries_are_bounded():
    s = Mock()
    s.get.return_value=response([])
    with pytest.raises(requests.ConnectionError):
        bybit.fetch_page(0,0,session=s,sleep=Mock(),attempts=3)
    assert s.get.call_count==3


def test_permanent_api_error_does_not_retry():
    s = Mock()
    s.get.return_value=response([],code=10001)
    with pytest.raises(ValueError,match='10001'):
        bybit.fetch_page(0,0,session=s,sleep=Mock())
    assert s.get.call_count==1


def test_http_forbidden_is_not_silently_retried():
    s = Mock()
    s.get.return_value=response([],status=403)
    s.get.return_value.raise_for_status.side_effect=requests.HTTPError('Forbidden')
    with pytest.raises(requests.HTTPError):
        bybit.fetch_page(0,0,session=s,sleep=Mock())
    assert s.get.call_count==1


def test_backfill_pages_only_closed_candles_and_commits_each(monkeypatch):
    fetch,save = Mock(return_value=[('row',)]),Mock()
    monkeypatch.setattr(backfill,'fetch_page',fetch)
    monkeypatch.setattr(backfill,'save_rows',save)
    stop=Mock()
    stop.is_set.return_value=False
    stop.wait.return_value=False
    assert backfill.fill(1, now_ms=1440*60000+30000, stop=stop)==2
    assert [(c.args[0],c.args[1]) for c in fetch.call_args_list]==[(1000*60000,1439*60000),(0,999*60000)]
    assert save.call_count==2


def test_backfill_partial_failure_can_be_replayed(monkeypatch):
    fetch = Mock(side_effect=[[candle_row(0,values()[1:])], requests.Timeout()])
    save = Mock()
    monkeypatch.setattr(backfill,'fetch_page',fetch)
    monkeypatch.setattr(backfill,'save_rows',save)
    stop = Mock()
    stop.is_set.return_value=False
    stop.wait.return_value=False
    with pytest.raises(requests.Timeout):
        backfill.fill(1,now_ms=1440*60000,stop=stop)
    assert save.call_count==1


def test_websocket_unconfirmed_ignored_and_db_failure_reconnects(monkeypatch):
    save = Mock()
    monkeypatch.setattr(collector,'save_rows',save)
    assert collector.save_candle({'confirm':False}) is False
    save.assert_not_called()
    c = dict(zip(('start','open','high','low','close','volume','turnover'),values()))
    c['confirm']=True
    save.side_effect=RuntimeError('db unavailable')
    ws = Mock()
    collector.on_message(ws,json.dumps({'topic':f'kline.1.{collector.SYMBOL}','data':[c]}))
    ws.close.assert_called_once()


def test_malformed_websocket_message_closes_socket():
    ws = Mock()
    collector.on_message(ws,'invalid json')
    ws.close.assert_called_once()


def test_subscribe_and_close_heartbeat():
    ws = Mock()
    collector.on_open(ws)
    assert json.loads(ws.send.call_args.args[0])['op']=='subscribe'
    collector.on_close(ws,1000,'normal')
    assert ws.heartbeat_stop.is_set()


@pytest.mark.parametrize('start,vals',[(1,values()[1:]),(0,['nan']*6),
    (0,['100','99','98','101','1','2']),(0,['100','102','99','101','-1','2'])])
def test_invalid_candles_rejected(start,vals):
    with pytest.raises(ValueError):
        candle_row(start,vals)


def test_reconnection_delay_bounded():
    assert 1 <= collector.retry_delay(0) <= 2
    assert 60 <= collector.retry_delay(100) <= 61


def test_reconnect_after_transport_return_and_db_unavailable(monkeypatch):
    stop=Mock()
    stop.is_set.side_effect=[False,False,False,True]
    monkeypatch.setattr(collector,'STOP',stop)
    monkeypatch.setattr(collector.signal,'signal',Mock())
    setup=Mock(side_effect=[RuntimeError('DB down'),None,None])
    monkeypatch.setattr(collector,'setup',setup)
    factory=Mock()
    monkeypatch.setattr(collector,'WebSocketApp',factory)
    collector.main()
    assert setup.call_count==3
    assert factory.return_value.run_forever.call_count==2
    assert stop.wait.call_count==3


def test_stale_stream_reconnects_even_if_socket_stays_open(monkeypatch):
    monkeypatch.setattr(collector.time,'monotonic',lambda:1000)
    ws = Mock(last_closed_at=819)
    assert collector.heartbeat_tick(ws) is False
    ws.close.assert_called_once()
    ws.send.assert_not_called()


def test_fresh_stream_sends_application_ping(monkeypatch):
    monkeypatch.setattr(collector.time,'monotonic',lambda:1000)
    ws=Mock(last_closed_at=999)
    assert collector.heartbeat_tick(ws) is True
    assert json.loads(ws.send.call_args.args[0])=={'op':'ping'}
    ws.close.assert_not_called()
