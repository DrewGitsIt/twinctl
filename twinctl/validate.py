"""Twin-vs-field scorecard: GEH per measured movement."""
from . import util
from .measure import movement_counts
from .simrun import run as simrun, last_run_dirs

def field_movements(world):
    """Measured (not estimated) field movements: {(sig,dir,mv): veh/h}."""
    model = util.jload(util.wpath(world, 'model.json'))
    out = {}
    for sig, dirs in model['field_demand'].items():
        for d, v in dirs.items():
            if v['source'] in ('measured', 'partial'):
                for mv, val in v['moves'].items():
                    out[(sig, d, mv)] = val
    return out

def scorecard(world, run_dirs=None, seeds=(42,)):
    util.require(world)
    if not run_dirs:
        run_dirs = last_run_dirs(world)
    if not run_dirs:
        simrun(world, seeds=seeds, label='validate')
        run_dirs = last_run_dirs(world)
    sim = movement_counts(world, run_dirs)
    field = field_movements(world)
    rows = []
    for (sig, d, mv), f in sorted(field.items()):
        s = sim.get(sig, {}).get(d, {}).get(mv, 0.0)
        rows.append({'signal': sig, 'dir': d, 'move': mv,
                     'field_vph': f, 'sim_vph': s, 'geh': round(util.geh(s, f), 2)})
    gehs = [r['geh'] for r in rows]
    ok = sum(1 for g in gehs if g < 5)
    summary = {'movements': len(rows), 'geh_lt5': ok,
               'geh_lt5_pct': round(100 * ok / max(len(rows), 1), 1),
               'geh_mean': round(sum(gehs) / max(len(gehs), 1), 2),
               'geh_max': max(gehs) if gehs else 0,
               'passing': ok / max(len(rows), 1) >= 0.85}
    m = util.meta(world)
    m['validation'] = summary
    util.save_meta(world, m)
    util.log_event(world, 'validate', summary)
    return {'summary': summary, 'rows': rows}
