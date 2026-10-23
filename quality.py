"""Read-only quality audit of a bounded rolling history, including edge gaps."""
import time

from storage import CATEGORY, SYMBOL, MIN_MS, connect

DAY_MS = 86_400_000


def summarize(rows, now_ms, days=30, max_ranges=50):
    if not 1 <= days <= 90 or max_ranges < 1:
        raise ValueError('Invalid quality window')
    boundary = now_ms//MIN_MS*MIN_MS
    first, last = boundary-days*DAY_MS, boundary-MIN_MS
    present = set()
    invalid = 0
    for ts, invalid_ohlcv in rows:
        if first <= ts < boundary:
            if ts % MIN_MS or invalid_ohlcv:
                invalid += 1
            if ts % MIN_MS == 0:
                present.add(ts)
    ranges = []
    cursor = first
    for ts in sorted(present):
        if ts > cursor:
            ranges.append({'start_ms':cursor,'end_ms':ts-MIN_MS,
                           'minutes':(ts-cursor)//MIN_MS})
        cursor = ts+MIN_MS
    if cursor <= last:
        ranges.append({'start_ms':cursor,'end_ms':last,
                       'minutes':(last-cursor)//MIN_MS+1})
    daily = {}
    for ts in range(first, boundary, MIN_MS):
        day = ts//DAY_MS*DAY_MS
        entry = daily.setdefault(day, {'day_ms':day,'expected':0,'present':0})
        entry['expected'] += 1
        entry['present'] += int(ts in present)
    expected = days*1440
    settled_missing = sum(max(0, (min(r['end_ms'],boundary-3*MIN_MS)-r['start_ms'])//MIN_MS+1)
                          for r in ranges)
    recent_end = boundary-3*MIN_MS
    recent = sum(ts in present for ts in range(recent_end-9*MIN_MS,recent_end+1,MIN_MS))
    latest = max(present) if present else None
    age = (now_ms-latest-MIN_MS)/1000 if latest is not None else None
    for entry in daily.values():
        entry['missing'] = entry['expected']-entry['present']
    return {'window_days':days,'window_start_ms':first,'window_end_ms':last,
            'expected_candles':expected,'present_candles':len(present),
            'missing_candles':expected-len(present),'settled_missing_candles':settled_missing,
            'pending_recent_candles':expected-len(present)-settled_missing,
            'coverage_pct':round(100*len(present)/expected,4),
            'invalid_candles':invalid,'latest_closed_start_ms':latest,
            'latest_close_age_seconds':age,'recent_present':recent,'recent_expected':10,
            'fresh':age is not None and 0 <= age <= 180 and recent==10,
            'gap_ranges':ranges[:max_ranges],'gap_ranges_total':len(ranges),
            'ranges_truncated':len(ranges)>max_ranges,'daily':list(daily.values())}


def audit(days=30, now_ms=None):
    if not 1 <= days <= 90:
        raise ValueError('Quality days must be 1..90')
    now = int(time.time()*1000) if now_ms is None else now_ms
    boundary = now//MIN_MS*MIN_MS
    with connect() as conn:
        conn.execute('SET TRANSACTION READ ONLY')
        conn.execute("SET LOCAL statement_timeout = '5s'")
        # Snapshot consistency across summary and window queries.
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
        stats = conn.execute('''SELECT count(*), min(start_ms), max(start_ms),
          count(*) FILTER (WHERE start_ms >= %s),
          count(*) FILTER (WHERE start_ms %% 60000 != 0),
          max(received_at) FROM candles WHERE exchange='bybit'
          AND category=%s AND symbol=%s AND interval='1' ''',
          (boundary,CATEGORY,SYMBOL)).fetchone()
        rows = conn.execute('''SELECT start_ms,
          (open<=0 OR high<=0 OR low<=0 OR close<=0 OR
           low>LEAST(open,close) OR high<GREATEST(open,close) OR volume<0 OR turnover<0 OR
           open::text IN ('NaN','Infinity','-Infinity') OR
           high::text IN ('NaN','Infinity','-Infinity') OR
           low::text IN ('NaN','Infinity','-Infinity') OR
           close::text IN ('NaN','Infinity','-Infinity') OR
           volume::text IN ('NaN','Infinity','-Infinity') OR
           turnover::text IN ('NaN','Infinity','-Infinity')) AS invalid
          FROM candles WHERE exchange='bybit' AND category=%s AND symbol=%s
          AND interval='1' AND start_ms >= %s AND start_ms < %s ORDER BY start_ms''',
          (CATEGORY,SYMBOL,boundary-days*DAY_MS,boundary)).fetchall()
    result = summarize(rows, now, days)
    result.update({'total_candles':stats[0],'first_stored_start_ms':stats[1],
                   'last_stored_start_ms':stats[2],'unclosed_or_future_candles':stats[3],
                   'off_grid_candles_total':stats[4],
                   'last_write_ms':int(stats[5].timestamp()*1000) if stats[5] else None})
    result['ready'] = (result['fresh'] and result['settled_missing_candles']==0
                       and result['invalid_candles']==0 and stats[3]==0 and stats[4]==0)
    return result
