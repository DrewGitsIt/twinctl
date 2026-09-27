"""Iterative demand calibration: route -> run -> measure -> adjust, until GEH target.

Adjustment is damped proportional fitting:
  turn weights  w_mv *= (field/sim)^0.7   (clamped per step)
  entry flows   vph  *= (field/sim of anchor approach)^0.7  (clamped vs original)
Only truly measured field movements steer the loop.
"""
from . import util
from .demandio import route
from .simrun import run as simrun, last_run_dirs
from .measure import movement_counts
from .validate import field_movements, scorecard

CLAMP_STEP = (0.6, 1.8)
CLAMP_TOTAL = (0.4, 2.5)
DAMP = 0.7

def _clamp(v, lo, hi):
    return max(lo, min(hi, v))

def _geh_summary(field, sim):
    gehs = []
    for (sig, d, mv), f in field.items():
        s = sim.get(sig, {}).get(d, {}).get(mv, 0.0)
        gehs.append(util.geh(s, f))
    ok = sum(1 for g in gehs if g < 5)
    return {'geh_lt5_pct': round(100 * ok / max(len(gehs), 1), 1),
            'geh_mean': round(sum(gehs) / max(len(gehs), 1), 2),
            'geh_max': round(max(gehs), 2) if gehs else 0}

def calibrate(world, iters=5, target_pct=85.0, seeds_final=(42, 7, 99), progress=print):
    util.require(world)
    demand = util.jload(util.wpath(world, 'demand.json'))
    field = field_movements(world)
    orig_vph = {fid: e['vph'] for fid, e in demand['entries'].items()}
    history = []
    for it in range(iters):
        util.jdump(util.wpath(world, 'demand.json'), demand)
        route(world)
        simrun(world, seeds=(42,), label=f'cal{it}')
        sim = movement_counts(world, last_run_dirs(world))
        summ = _geh_summary(field, sim)
        history.append(summ)
        progress(f'iter {it}: GEH<5 {summ["geh_lt5_pct"]}% mean {summ["geh_mean"]} max {summ["geh_max"]}')
        if summ['geh_lt5_pct'] >= target_pct:
            break
        # ---- adjust turn weights ----
        for (sig, d, mv), f in field.items():
            s = sim.get(sig, {}).get(d, {}).get(mv, 0.0)
            if s <= 0 or f <= 0:
                continue
            r = _clamp((f / s) ** DAMP, *CLAMP_STEP)
            moves = demand['signals'].get(sig, {}).get(d, {}).get('moves', {})
            if mv in moves:
                moves[mv] = round(moves[mv] * r, 1)
        # ---- adjust entry flows via their anchor approach ----
        for fid, e in demand['entries'].items():
            anchor = e.get('anchor')
            if not anchor:
                continue
            sig, d = anchor
            fs = {mv: f for (s2, d2, mv), f in field.items() if s2 == sig and d2 == d}
            if not fs:
                continue
            ss = sim.get(sig, {}).get(d, {})
            F = sum(fs.values())
            Sm = sum(ss.get(mv, 0.0) for mv in fs)
            if Sm <= 0:
                continue
            r = _clamp((F / Sm) ** DAMP, *CLAMP_STEP)
            new = _clamp(e['vph'] * r, orig_vph[fid] * CLAMP_TOTAL[0], orig_vph[fid] * CLAMP_TOTAL[1])
            e['vph'] = round(new, 1)
    util.jdump(util.wpath(world, 'demand.json'), demand)
    route(world)
    simrun(world, seeds=seeds_final, label='calibrated')
    sc = scorecard(world, last_run_dirs(world))
    m = util.meta(world)
    m['calibration'] = {'iterations': len(history), 'history': history,
                        'final': sc['summary']}
    util.save_meta(world, m)
    util.log_event(world, 'calibrate', m['calibration'])
    return {'history': history, 'final': sc}
