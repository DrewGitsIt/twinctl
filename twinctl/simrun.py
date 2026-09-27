"""Run SUMO for a world (one or more seeds); summarize tripinfo KPIs."""
import os, statistics as st, subprocess
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from . import util

def _run_one(world, seed, label):
    rd = util.wpath(world, 'runs', f'{label}-s{seed}')
    os.makedirs(rd, exist_ok=True)
    cmd = [util.sumo_bin('sumo'),
           '-n', util.wpath(world, 'net.net.xml'),
           '-r', util.wpath(world, 'routes.rou.xml'),
           '-a', util.wpath(world, 'plan.tll.xml'),
           '--tripinfo-output', os.path.join(rd, 'tripinfo.xml'),
           '--vehroute-output', os.path.join(rd, 'vehroutes.xml'),
           '--vehroute-output.write-unfinished', 'true',
           '--vehroute-output.route-length', 'true',
           '-e', '7200', '--seed', str(seed),
           '--no-step-log', '--duration-log.disable', '--no-warnings',
           '--time-to-teleport', '300']
    extra = util.wpath(world, 'extra.add.xml')
    if os.path.exists(extra):
        cmd[cmd.index('-a') + 1] += ',' + extra
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        util.die(f'sumo failed (seed {seed}): {p.stderr[-400:]}')
    return rd

def kpis(run_dir):
    tis = ET.parse(os.path.join(run_dir, 'tripinfo.xml')).getroot().findall('tripinfo')
    if not tis:
        return {'arrived': 0}
    tl = [float(t.get('timeLoss')) for t in tis]
    return {'arrived': len(tis),
            'mean_delay_s': round(st.mean(tl), 1),
            'total_delay_vehh': round(sum(tl) / 3600, 1),
            'mean_stops': round(st.mean([int(t.get('waitingCount')) for t in tis]), 2),
            'mean_duration_s': round(st.mean([float(t.get('duration')) for t in tis]), 1)}

def run(world, seeds=(42,), label='run'):
    util.require(world)
    with ThreadPoolExecutor(max_workers=min(8, len(seeds))) as ex:
        dirs = list(ex.map(lambda s: _run_one(world, s, label), seeds))
    per_seed = {s: kpis(d) for s, d in zip(seeds, dirs)}
    agg = {}
    keys = [k for k in next(iter(per_seed.values())) if k != 'arrived']
    for k in ['arrived'] + keys:
        vals = [v[k] for v in per_seed.values()]
        agg[k] = round(st.mean(vals), 2)
        if len(vals) > 1:
            agg[k + '_sd'] = round(st.stdev(vals), 2)
    m = util.meta(world)
    m['last_run'] = {'label': label, 'seeds': list(seeds), 'kpis': agg}
    util.save_meta(world, m)
    util.log_event(world, 'run', m['last_run'])
    return {'per_seed': per_seed, 'aggregate': agg,
            'run_dirs': dirs}

def last_run_dirs(world, label=None):
    rd = util.wpath(world, 'runs')
    if not os.path.isdir(rd):
        return []
    m = util.meta(world).get('last_run')
    if m and (label is None or m['label'] == label):
        return [util.wpath(world, 'runs', f"{m['label']}-s{s}") for s in m['seeds']]
    return []
