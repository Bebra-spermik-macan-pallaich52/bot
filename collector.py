"""Closed public candles only. Reconnect on transport AND persistence failures."""
import json
import logging
import random
import signal
import threading
import time

from websocket import WebSocketApp

from storage import CATEGORY, SYMBOL, candle_row, save_rows, setup

URL = f'wss://stream.bybit.com/v5/public/{CATEGORY}'
STOP = threading.Event()
current_ws = None


def save_candle(c):
    if c.get('confirm') is not True:
        return False
    row = candle_row(c['start'], [c[k] for k in ('open','high','low','close','volume','turnover')])
    if row[3] + 60_000 > int(time.time()*1000):
        raise ValueError('Confirmed candle is not yet closed')
    save_rows([row])
    logging.info('Saved %s closed candle %s', SYMBOL, row[3])
    return True


def on_open(ws):
    ws.send(json.dumps({'op':'subscribe','args':[f'kline.1.{SYMBOL}']}))
    # Bybit documents an application ping every 20s; use it in addition to
    # WebSocket ping/pong timeout detection. Each connection owns its thread.
    done = threading.Event()
    ws.heartbeat_stop = done
    ws.last_closed_at = time.monotonic()
    def heartbeat():
        while not done.wait(20) and not STOP.is_set():
            try:
                if not heartbeat_tick(ws):
                    return
            except Exception:
                ws.close()
                return
    threading.Thread(target=heartbeat, daemon=True).start()
    logging.info('Connected to %s', URL)


def heartbeat_tick(ws):
    if time.monotonic()-ws.last_closed_at > 180:
        logging.warning('No fresh closed candle for 180s; reconnecting')
        ws.close()
        return False
    ws.send(json.dumps({'op':'ping'}))
    return True


def on_close(ws, code, reason):
    if hasattr(ws, 'heartbeat_stop'):
        ws.heartbeat_stop.set()
    logging.warning('WebSocket closed: code=%s', code)


def on_message(ws, payload):
    try:
        message = json.loads(payload)
        if message.get('success') is False:
            raise RuntimeError('Bybit rejected websocket operation')
        if message.get('topic') == f'kline.1.{SYMBOL}':
            for candle in message.get('data', []):
                if save_candle(candle) and int(candle['start']) >= int(time.time()*1000)-120_000:
                    ws.last_closed_at = time.monotonic()
    except Exception:
        # A lost write must not leave a seemingly healthy socket. REST repair
        # recovers the uncommitted candle; reconnection rechecks database access.
        logging.exception('Message/persistence failure; reconnecting')
        ws.close()


def retry_delay(failures):
    return min(60, 2**min(failures, 6)) + random.uniform(0, 1)


def main():
    global current_ws
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    def stop(*_):
        STOP.set()
        if current_ws is not None:
            current_ws.close()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, stop)
    failures = 0
    while not STOP.is_set():
        started = time.monotonic()
        try:
            setup()
            current_ws = WebSocketApp(URL, on_open=on_open, on_message=on_message,
                on_close=on_close, on_error=lambda *_: logging.warning('WebSocket transport error'))
            current_ws.run_forever(ping_interval=20, ping_timeout=10)
        except Exception:
            logging.exception('Collector failure')
        finally:
            if current_ws is not None and hasattr(current_ws, 'heartbeat_stop'):
                current_ws.heartbeat_stop.set()
        failures = 0 if time.monotonic()-started > 120 else failures+1
        STOP.wait(retry_delay(failures))


if __name__ == '__main__':
    main()
