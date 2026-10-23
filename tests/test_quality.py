import pytest

from quality import summarize, DAY_MS

MINUTE=60000
NOW=2*DAY_MS+30000
START=DAY_MS
END=2*DAY_MS-MINUTE


def complete():
    return [(ts,False) for ts in range(START,END+1,MINUTE)]


def test_complete_window_counts_partial_utc_days_and_recent_latency():
    result=summarize(complete(),NOW,days=1)
    assert result['missing_candles']==0
    assert result['coverage_pct']==100
    assert result['fresh'] is True
    assert result['latest_close_age_seconds']==30
    assert sum(d['expected'] for d in result['daily'])==1440
    assert result['daily'][0]['missing']==0


def test_leading_internal_trailing_gaps_counted_exactly():
    removed={START,START+MINUTE,START+10*MINUTE,END-MINUTE,END}
    result=summarize([r for r in complete() if r[0] not in removed],NOW,days=1)
    assert result['missing_candles']==5
    assert result['settled_missing_candles']==3
    assert result['pending_recent_candles']==2
    assert result['gap_ranges']==[
        {'start_ms':START,'end_ms':START+MINUTE,'minutes':2},
        {'start_ms':START+10*MINUTE,'end_ms':START+10*MINUTE,'minutes':1},
        {'start_ms':END-MINUTE,'end_ms':END,'minutes':2}]


def test_truncated_ranges_do_not_truncate_total():
    result=summarize(complete()[::2],NOW,days=1,max_ranges=3)
    assert result['gap_ranges_total']==720
    assert len(result['gap_ranges'])==3
    assert result['missing_candles']==720
    assert result['ranges_truncated'] is True


def test_no_candles_is_missing_history_not_100_percent():
    result=summarize([],NOW,days=1)
    assert result['present_candles']==0
    assert result['missing_candles']==1440
    assert result['fresh'] is False
    assert result['latest_close_age_seconds'] is None
    assert result['gap_ranges'][0]['minutes']==1440


def test_invalid_and_offgrid_do_not_hide_missing_grid_candle():
    result=summarize([(START,True),(START+MINUTE+1,False),(START-MINUTE,True),
                      (END+MINUTE,True)],NOW,days=1)
    assert result['present_candles']==1
    assert result['invalid_candles']==2
    assert result['missing_candles']==1439


def test_partial_days_preserve_exact_window_total():
    result=summarize([],NOW+12*60*MINUTE,days=1)
    assert len(result['daily'])==2
    assert sum(d['expected'] for d in result['daily'])==1440


@pytest.mark.parametrize('days',[0,91])
def test_invalid_window(days):
    with pytest.raises(ValueError):
        summarize([],NOW,days=days)
