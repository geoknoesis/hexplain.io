"""The cost of a gate run is evidence too; an unreadable or incomplete record is not a pass."""
import contextlib
import io
import json
import tempfile
from pathlib import Path

from _gate_cost import summarise, render

with tempfile.TemporaryDirectory() as temp:
    report = Path(temp) / 'summary.json'

    report.write_text(json.dumps(dict(status='complete', counts=dict(PASS=2, SKIP=0, FAIL=0), gates=[
        dict(gate='test_slow', status='PASS', duration_seconds=120.0,
             peak_rss_bytes=900 * 1024 * 1024, peak_processes=9, rss_samples=2400),
        dict(gate='test_fast', status='PASS', duration_seconds=1.5,
             peak_rss_bytes=30 * 1024 * 1024, peak_processes=1, rss_samples=30),
    ])), encoding='utf-8')
    summary = summarise(report)
    assert summary['total_seconds'] == 121.5, summary
    assert summary['peak_rss_bytes'] == 900 * 1024 * 1024, summary
    assert summary['peak_processes'] == 9, summary
    # Ordered by cost, so the gate worth attention is the first line and not the twentieth.
    assert [row['gate'] for row in summary['by_duration']] == ['test_slow', 'test_fast'], summary
    assert [row['gate'] for row in summary['by_memory']] == ['test_slow', 'test_fast'], summary
    text = render(summary)
    assert 'test_slow' in text and '900' in text.replace(',', ''), text

    # A run where nothing sampled memory must say so rather than report a peak of zero.
    report.write_text(json.dumps(dict(status='complete', counts=dict(PASS=1, SKIP=0, FAIL=0), gates=[
        dict(gate='test_fast', status='PASS', duration_seconds=1.0,
             peak_rss_bytes=None, peak_processes=None, rss_samples=0),
    ])), encoding='utf-8')
    summary = summarise(report)
    assert summary['peak_rss_bytes'] is None, summary
    assert 'not sampled' in render(summary), render(summary)

    # An incomplete run is not summarised as though it finished.
    report.write_text(json.dumps(dict(status='running', gates=[])), encoding='utf-8',newline='\n')
    try:
        summarise(report)
        raise AssertionError('summarised an unfinished run')
    except SystemExit as failure:
        assert 'running' in str(failure), failure

    missing = Path(temp) / 'absent.json'
    try:
        summarise(missing)
        raise AssertionError('summarised a missing report')
    except SystemExit:
        pass

with contextlib.redirect_stdout(io.StringIO()):
    pass
print('PASS: gate cost summary reports duration, sampled memory, process count and refuses partial runs')
