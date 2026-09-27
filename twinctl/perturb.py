"""Shocks: what-if perturbations applied to a (usually forked) world."""
from . import util

SHOCKS = ('demand_surge', 'lane_closure', 'detector_dark')

def perturb(world, shock, **kw):
    util.require(world)
    if shock == 'demand_surge':
        entry, pct = kw.get('entry'), float(kw.get('pct', 20))
        demand = util.jload(util.wpath(world, 'demand.json'))
        targets = [entry] if entry else list(demand['entries'])
        for fid in targets:
            if fid not in demand['entries']:
                util.die(f'unknown entry "{fid}"; known: {", ".join(sorted(demand["entries"]))}')
            demand['entries'][fid]['vph'] = round(demand['entries'][fid]['vph'] * (1 + pct / 100), 1)
        util.jdump(util.wpath(world, 'demand.json'), demand)
        from .demandio import route
        route(world)
        detail = {'shock': shock, 'entries': targets, 'pct': pct}
    elif shock == 'lane_closure':
        edge = kw.get('edge')
        if not edge:
            util.die('lane_closure needs edge=<edge id>')
        # close via a vaporizing rerouter-free approach: cap the edge to walking pace
        xml = (f'<additional>\n  <variableSpeedSign id="close_{edge}" lanes="{edge}_0">\n'
               f'    <step time="0" speed="1.4"/>\n  </variableSpeedSign>\n</additional>\n')
        util_path = util.wpath(world, 'extra.add.xml')
        open(util_path, 'w').write(xml)
        detail = {'shock': shock, 'edge': edge, 'note': 'lane 0 capped to 1.4 m/s'}
    elif shock == 'detector_dark':
        sig = kw.get('signal')
        detail = {'shock': shock, 'signal': sig,
                  'note': 'marks field data stale for this signal (drift drill); no sim effect'}
    else:
        util.die(f'unknown shock "{shock}"; shocks: {", ".join(SHOCKS)}')
    util.log_event(world, 'perturb', detail)
    return detail
