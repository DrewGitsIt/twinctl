"""Signal plan edits (retime) and inspection."""
import xml.etree.ElementTree as ET
from . import util

def load_plan(world):
    progs = {}
    for tl in ET.parse(util.wpath(world, 'plan.tll.xml')).getroot().iter('tlLogic'):
        phases = [(float(p.get('duration')), p.get('state')) for p in tl.iter('phase')]
        progs[tl.get('id')] = {'phases': phases, 'offset': float(tl.get('offset') or 0)}
    return progs

def nema_programs(world):
    """{tls id: element} for native-NEMA programs (empty for static worlds).

    NEMA phase `duration` is a placeholder (99) and the real timing lives in
    minDur/maxDur/vehext plus the ring/barrier params, so the static helpers
    below cannot read or rewrite these programs.
    """
    return {tl.get('id'): tl
            for tl in ET.parse(util.wpath(world, 'plan.tll.xml')).getroot().iter('tlLogic')
            if (tl.get('type') or '').upper() == 'NEMA'}

def save_plan(world, progs):
    with open(util.wpath(world, 'plan.tll.xml'), 'w') as f:
        f.write('<additional>\n')
        for tlsid, p in progs.items():
            f.write(f'  <tlLogic id="{tlsid}" type="static" programID="atspm" offset="{p["offset"] % 120:.1f}">\n')
            for dur, st in p['phases']:
                f.write(f'    <phase duration="{dur:.1f}" state="{st}"/>\n')
            f.write('  </tlLogic>\n')
        f.write('</additional>\n')

def retime(world, offsets=None, split_shift=None):
    """offsets: {sig: +/-seconds}. split_shift: {sig: seconds moved from cross
    through-green to mainline through-green (negative = toward cross)}."""
    util.require(world)
    nema = nema_programs(world)
    if nema:
        tod = (util.meta(world).get('tod') or {}).get('window')
        extra = (f" --plan <n> --expect assets/field/tod/plan_expect_{tod}.json"
                 if tod else '')
        util.die(f"{world} runs native-NEMA programs at {len(nema)} signal(s); "
                 "retime writes fixed-time programs and would flatten them. "
                 f"Rebuild instead: python3 -m pipeline.build_nema_plan --dst {world}"
                 f"{extra} --offset-adjust '{{\"7146\": 2}}'")
    mapping = util.jload(util.wpath(world, 'tls_mapping.json'))
    progs = load_plan(world)
    changed = []
    for sig, d in (offsets or {}).items():
        if sig not in mapping:
            util.die(f'unknown signal {sig}; known: {", ".join(sorted(mapping))}')
        progs[mapping[sig]['tls']]['offset'] += float(d)
        changed.append(f'{sig} offset {d:+g}s')
    for sig, d in (split_shift or {}).items():
        if sig not in mapping:
            util.die(f'unknown signal {sig}; known: {", ".join(sorted(mapping))}')
        p = progs[mapping[sig]['tls']]
        greens = [(i, dur) for i, (dur, st) in enumerate(p['phases']) if dur > 15 and 'G' in st]
        if len(greens) != 2:
            util.die(f'{sig}: cannot shift splits (needs exactly 2 long green groups, has {len(greens)})')
        (i1, g1), (i2, g2) = sorted(greens, key=lambda x: -x[1])  # i1 = mainline (longer)
        d = float(d)
        if g2 - d < 8 or g1 + d < 8:
            util.die(f'{sig}: split shift {d:+g}s would leave a green below 8 s')
        p['phases'][i1] = (g1 + d, p['phases'][i1][1])
        p['phases'][i2] = (g2 - d, p['phases'][i2][1])
        changed.append(f'{sig} split {d:+g}s toward mainline')
    save_plan(world, progs)
    util.log_event(world, 'retime', changed)
    return changed

def describe(world):
    mapping = util.jload(util.wpath(world, 'tls_mapping.json'))
    progs = load_plan(world)
    nema = nema_programs(world)
    rows = []
    for sig, m in sorted(mapping.items()):
        p = progs.get(m['tls'])
        if not p:
            continue
        tl = nema.get(m['tls'])
        if tl is not None:
            # splits, not the placeholder durations: maxDur + yellow + red
            def _prm(k, d=None):
                for e in tl.iter('param'):
                    if e.get('key') == k:
                        return e.get('value')
                return d
            spl = {}
            for ph in tl.iter('phase'):
                spl[int(ph.get('name'))] = (float(ph.get('maxDur'))
                                            + float(ph.get('yellow') or 0)
                                            + float(ph.get('red') or 0))
            coord = [int(x) for x in (_prm('barrier2Phases') or '2,6').split(',') if x != '0']
            cyc = float(_prm('total-cycle-length') or 120)
            main = max((spl[c] for c in coord if c in spl), default=None)
            cross = max((v for k, v in spl.items() if k in (4, 8)), default=None)
            rows.append({'signal': sig, 'offset': round(p['offset'] % cyc, 1),
                         'cycle': round(cyc, 1), 'type': 'NEMA',
                         'main_green': main, 'cross_green': cross})
            continue
        greens = sorted([dur for dur, st in p['phases'] if dur > 15 and 'G' in st], reverse=True)
        rows.append({'signal': sig, 'offset': round(p['offset'] % 120, 1),
                     'cycle': round(sum(d for d, _ in p['phases']), 1), 'type': 'static',
                     'main_green': greens[0] if greens else None,
                     'cross_green': greens[1] if len(greens) > 1 else None})
    return rows
