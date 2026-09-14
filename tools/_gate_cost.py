"""Summarise what a gate run cost: wall clock, sampled peak memory and process fan-out.

The parallel gates are capped at eight workers because a concurrent run exhausted host memory, and
until now the retained evidence recorded duration only -- the one resource that actually failed was
the one nobody measured. `_gate_runner` samples it; this turns the raw record into the few lines a
reviewer reads, and refuses to summarise a run that did not finish.
"""
import json
import sys
from pathlib import Path


def summarise(path):
    path = Path(path)
    try:
        record = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        raise SystemExit(f'no gate report at {path}') from None
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f'unreadable gate report at {path}: {error}') from error
    status = record.get('status')
    if status not in ('complete', 'failed'):
        raise SystemExit(f'gate run is {status!r}; nothing to summarise until it finishes')
    gates = record.get('gates', [])
    sampled = [g for g in gates if g.get('peak_rss_bytes')]
    return dict(
        status=status,
        counts=record.get('counts'),
        gates=len(gates),
        total_seconds=round(sum(g.get('duration_seconds', 0.0) for g in gates), 3),
        peak_rss_bytes=max((g['peak_rss_bytes'] for g in sampled), default=None),
        peak_processes=max((g.get('peak_processes') or 0 for g in sampled), default=None) or None,
        by_duration=sorted(gates, key=lambda g: -g.get('duration_seconds', 0.0)),
        by_memory=sorted(sampled, key=lambda g: -g['peak_rss_bytes']),
    )


def render(summary, top=10):
    mib = 1024 * 1024
    lines = [f"{summary['gates']} gates, {summary['status']}, {summary['counts']}",
             f"total wall clock {summary['total_seconds']:.1f}s"]
    if summary['peak_rss_bytes'] is None:
        lines.append('memory not sampled (psutil unavailable, or every gate exited between samples)')
    else:
        lines.append(f"peak sampled RSS {summary['peak_rss_bytes'] / mib:,.1f} MiB across at most "
                     f"{summary['peak_processes']} processes; a sampled lower bound, not an exact peak")
    lines.append('slowest:')
    for row in summary['by_duration'][:top]:
        lines.append(f"  {row.get('duration_seconds', 0.0):8.1f}s  {row['gate']}")
    if summary['by_memory']:
        lines.append('largest:')
        for row in summary['by_memory'][:top]:
            lines.append(f"  {row['peak_rss_bytes'] / mib:8,.1f} MiB  {row['gate']}"
                         f" ({row.get('peak_processes')} processes)")
    return '\n'.join(lines)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: _gate_cost.py <.gate-results/summary.json>')
    print(render(summarise(sys.argv[1])))
