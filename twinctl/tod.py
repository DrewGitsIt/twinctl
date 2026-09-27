"""Time-of-day windows: which world is the twin of which hours.

A world declares its window in meta.json:

    "tod": {"window": "am", "label": "AM peak", "plan": "1 (2 at 7147)",
            "cycle_s": 120.0, "field_window": "2026-09-09 07:00-09:00"}

so the registry is discovered, not configured -- forking a TOD world and
re-pointing its `tod.window` is enough to register it.  The one exception is
the PM peak: ss-v2 predates the TOD work and carries no `tod` block, so it is
claimed below as the implicit 'pm' world if (and only if) no world declares
'pm' itself.

Order is chronological, not alphabetical, so `twinctl tod` reads like a day.
"""
import os
from . import util

ORDER = ['am', 'md', 'pm', 'ev', 'ni']
IMPLICIT = {'pm': 'ss-v2'}


def _meta_tod(world):
    m = util.meta(world)
    t = m.get('tod') or {}
    return m, (t.get('window') or None), t


def windows():
    """[{window, world, ...}] for every world that declares a TOD window."""
    rows, claimed = [], set()
    if not os.path.isdir(util.WORLDS):
        return rows
    for w in sorted(os.listdir(util.WORLDS)):
        if not os.path.isfile(util.wpath(w, 'meta.json')):
            continue
        m, win, t = _meta_tod(w)
        if not win:
            continue
        claimed.add(win)
        rows.append(_row(w, win, m, t))
    for win, w in IMPLICIT.items():
        if win in claimed or not util.exists(w):
            continue
        m = util.meta(w)
        rows.append(_row(w, win, m, {'label': 'PM peak',
                                     'plan': (m.get('control') or {}).get('plan'),
                                     'field_window': m.get('window'),
                                     'implicit': True}))
    rows.sort(key=lambda r: (ORDER.index(r['window']) if r['window'] in ORDER
                             else len(ORDER), r['window']))
    return rows


def _row(world, win, m, t):
    cyc = t.get('cycle_s')
    if cyc is None:
        c = ((m.get('control') or {}).get('cycle_s') or {})
        cyc = max(c.values()) if isinstance(c, dict) and c else None
    if cyc is None and os.path.exists(util.wpath(world, 'nema_config.json')):
        # ss-v2 records the cycle only in nema_config.json
        cs = [v.get('cycle') for v in util.jload(
            util.wpath(world, 'nema_config.json')).values() if v.get('cycle')]
        cyc = max(cs) if cs else None
    return {'window': win, 'world': world, 'label': t.get('label') or win,
            'plan': t.get('plan'), 'cycle_s': cyc,
            'field_window': t.get('field_window') or m.get('window'),
            'implicit': bool(t.get('implicit')),
            'geh_lt5_pct': (m.get('validation') or {}).get('geh_lt5_pct'),
            'mean_delay_s': ((m.get('last_run') or {}).get('kpis') or {}).get('mean_delay_s')}


def resolve(window):
    """Window name -> world name; dies with the available windows if unknown."""
    rows = windows()
    for r in rows:
        if r['window'] == window:
            return r['world']
    have = ', '.join(r['window'] for r in rows) or '(none)'
    util.die(f"unknown time-of-day window '{window}'; known: {have}")


def world_arg(a):
    """Resolve the world for a verb that accepts either a name or --window."""
    if getattr(a, 'window', None):
        if getattr(a, 'world', None):
            util.die('give a world OR --window, not both')
        return resolve(a.window)
    if not getattr(a, 'world', None):
        util.die('need a world name or --window ' + '|'.join(
            r['window'] for r in windows()))
    return a.world
