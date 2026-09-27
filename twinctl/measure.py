"""Movement counts at each signal from vehroute output (model-side counts)."""
import os
import xml.etree.ElementTree as ET
from . import util
from .geom import load_net, traffic_dir, movement, tls_nodes

def _edge_roles(net, mapping):
    """edge id -> (sig, role) with role in {'in','internal','out'}."""
    roles = {}
    for sig, m in mapping.items():
        nodes = {n.getID() for n in tls_nodes(net, m['tls'])}
        for e in net.getEdges():
            f, t = e.getFromNode().getID(), e.getToNode().getID()
            if t in nodes and f not in nodes:
                roles.setdefault(e.getID(), []).append((sig, 'in'))
            elif f in nodes and t in nodes:
                roles.setdefault(e.getID(), []).append((sig, 'internal'))
            elif f in nodes and t not in nodes:
                roles.setdefault(e.getID(), []).append((sig, 'out'))
    return roles

def movement_counts(world, run_dirs):
    """Mean hourly counts per signal/direction/movement across runs."""
    net = load_net(util.wpath(world, 'net.net.xml'))
    mapping = util.jload(util.wpath(world, 'tls_mapping.json'))
    roles = _edge_roles(net, mapping)
    def role(eid, sig=None):
        for s, r in roles.get(eid, []):
            if sig is None or s == sig:
                return s, r
        return None, None
    totals = {}
    for rd in run_dirs:
        for veh in ET.parse(os.path.join(rd, 'vehroutes.xml')).getroot().iter('vehicle'):
            route = veh.find('route')
            if route is None:
                rd_el = veh.find('routeDistribution')
                if rd_el is not None:
                    route = rd_el.findall('route')[-1]
            if route is None:
                continue
            edges = route.get('edges', '').split()
            i = 0
            while i < len(edges) - 1:
                s, r = role(edges[i])
                if r == 'in':
                    j = i + 1
                    while j < len(edges) and role(edges[j], s)[1] == 'internal':
                        j += 1
                    if j < len(edges):
                        s2, r2 = role(edges[j], s)
                        if r2 == 'out':
                            in_e, out_e = net.getEdge(edges[i]), net.getEdge(edges[j])
                            d = traffic_dir(in_e)
                            mv = movement(in_e, out_e)
                            key = (s, d, mv)
                            totals[key] = totals.get(key, 0) + 1
                    i = j
                else:
                    i += 1
    n = max(len(run_dirs), 1)
    out = {}
    for (s, d, mv), c in totals.items():
        out.setdefault(s, {}).setdefault(d, {})[mv] = round(c / n / 2.0, 1)  # veh/h over 2 h
    return out
