"""One-shot experiment: fork per candidate, apply, run seeds, rank.

A candidate: {"name": str, "retime": {"offsets": {...}, "split_shift": {...}}}
          or {"name": str, "perturb": {"shock": ..., ...}}
Validated fully before anything is forked.
"""
from concurrent.futures import ThreadPoolExecutor
from . import util, world as W, plan, perturb as P
from .simrun import run as simrun

def _validate(world_name, cands):
    mapping = util.jload(util.wpath(world_name, 'tls_mapping.json'))
    problems = []
    names = set()
    for i, c in enumerate(cands, 1):
        if not isinstance(c, dict):
            problems.append(f'[{i}] candidate must be an object'); continue
        name = c.get('name') or f'c{i}'
        if name in names:
            problems.append(f'[{i}] duplicate name "{name}"')
        names.add(name)
        if not ('retime' in c or 'perturb' in c):
            problems.append(f'[{i}] needs "retime" or "perturb"')
        for key in ('offsets', 'split_shift'):
            for sig in (c.get('retime', {}).get(key) or {}):
                if sig not in mapping:
                    problems.append(f'[{i}] {key}: unknown signal "{sig}"; known: {", ".join(sorted(mapping))}')
        if 'perturb' in c and c['perturb'].get('shock') not in P.SHOCKS:
            problems.append(f'[{i}] perturb.shock must be one of {", ".join(P.SHOCKS)}')
    if problems:
        util.die('experiment: %d problem(s), nothing was run:\n  ' % len(problems)
                 + '\n  '.join(problems))
    return [c.get('name') or f'c{i}' for i, c in enumerate(cands, 1)]

def _freshness_gate(world_name):
    m = util.meta(world_name)
    v = m.get('validation')
    if not v:
        return 'WARNING: world has never been validated against field data (twinctl validate)'
    if not v.get('passing'):
        return f'WARNING: validation not passing (GEH<5 on {v["geh_lt5_pct"]}% of movements) — treat deltas, not absolutes'
    return None

def experiment(world_name, cands, seeds=(42, 7, 99), keep=False):
    util.require(world_name)
    names = _validate(world_name, cands)
    warn = _freshness_gate(world_name)
    clones = {}
    none = f'{world_name}-none'
    if util.exists(none):
        W.kill(none, purge=True)
    W.fork(world_name, none)
    clones['none'] = none
    for name, c in zip(names, cands):
        cl = f'{world_name}-{name}'
        if util.exists(cl):
            W.kill(cl, purge=True)
        W.fork(world_name, cl)
        if 'retime' in c:
            plan.retime(cl, c['retime'].get('offsets'), c['retime'].get('split_shift'))
        if 'perturb' in c:
            P.perturb(cl, **c['perturb'])
        clones[name] = cl
    with ThreadPoolExecutor(max_workers=4) as ex:
        results = dict(zip(clones, ex.map(
            lambda cl: simrun(cl, seeds=seeds, label='exp')['aggregate'], clones.values())))
    base = results['none']
    rows = []
    for name, agg in results.items():
        d = agg['mean_delay_s'] - base['mean_delay_s']
        sd = max(agg.get('mean_delay_s_sd', 0), base.get('mean_delay_s_sd', 0))
        rows.append({'candidate': name, 'world': clones[name], **agg,
                     'delta_delay_s': round(d, 2),
                     'significant': abs(d) > 2 * sd if len(seeds) > 1 else None})
    rows.sort(key=lambda r: r['mean_delay_s'])
    winner = next((r for r in rows if r['candidate'] != 'none'), None)
    verdict = None
    if winner:
        if winner['mean_delay_s'] < base['mean_delay_s'] and (winner['significant'] or len(seeds) == 1):
            verdict = f"winner: {winner['candidate']} ({winner['delta_delay_s']:+.1f} s/veh) — promote with: twinctl promote {winner['world']}"
        else:
            verdict = 'no candidate significantly beats doing nothing'
    if not keep:
        pass  # clones kept until purged, like simctl
    util.log_event(world_name, 'experiment', {'candidates': names, 'seeds': list(seeds),
                                              'verdict': verdict})
    return {'warning': warn, 'rows': rows, 'verdict': verdict}

def compare(worlds_, baseline):
    rows = []
    base_kpis = None
    for w in [baseline] + [x for x in worlds_ if x != baseline]:
        util.require(w)
        m = util.meta(w)
        agg = (m.get('last_run') or {}).get('kpis')
        if not agg:
            util.die(f'{w}: no run yet (twinctl run {w})')
        if base_kpis is None:
            base_kpis = agg
        rows.append({'world': w, **agg,
                     'delta_delay_s': round(agg['mean_delay_s'] - base_kpis['mean_delay_s'], 2)})
    return rows
