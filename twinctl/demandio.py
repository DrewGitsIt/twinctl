"""demand.json -> turns.xml + flows.xml -> jtrrouter -> routes.rou.xml.

demand.json:
  entries: {flow_id: {edge, vph}}
  signals: {sig: {Direction: {moves: {L,T,R}, source}}}
"""
import os, subprocess
from . import util
from .geom import load_net, traffic_dir, movement, heading, tls_nodes

DEFAULT_W = {'L': 1.5, 'T': 97.0, 'R': 1.5}

def build_turns(world):
    net = load_net(util.wpath(world, 'net.net.xml'))
    mapping = util.jload(util.wpath(world, 'tls_mapping.json'))
    demand = util.jload(util.wpath(world, 'demand.json'))
    lines = ['<turns>', '  <interval begin="0" end="7200">']
    covered = set()
    for sig, m in mapping.items():
        for node in tls_nodes(net, m['tls']):
            for in_e in node.getIncoming():
                d = traffic_dir(in_e)
                dm = demand['signals'].get(sig, {}).get(d)
                if not dm:
                    continue
                moves = dm['moves']
                avail = {}
                for out_e in in_e.getOutgoing():
                    if in_e.getToNode() != node:
                        continue
                    avail.setdefault(movement(in_e, out_e), []).append(out_e.getID())
                if not avail:
                    continue
                carry = sum(v for mv, v in moves.items() if mv not in avail)
                outs = {}
                for mv, edges_ in avail.items():
                    w = moves.get(mv, 0) + (carry if mv == 'T' else 0)
                    if 'T' not in avail and mv == 'L':
                        w += carry
                    for oid in edges_:
                        outs[oid] = outs.get(oid, 0) + w / len(edges_)
                tot = sum(outs.values())
                if tot <= 0:
                    continue
                covered.add(in_e.getID())
                for oid, v in outs.items():
                    if v > 0:
                        lines.append(f'    <edgeRelation from="{in_e.getID()}" to="{oid}" probability="{v/tot:.4f}"/>')
    # geometry-aware defaults everywhere else (jtrrouter's own classifier
    # fails at joined-cluster junctions)
    for e in net.getEdges():
        if e.getID() in covered:
            continue
        cands = []
        for out_e in e.getOutgoing():
            mv = movement(e, out_e)
            same = 1 if (e.getName() and e.getName() == out_e.getName()) else 0
            diff = abs((heading(out_e, False) - heading(e) + 540) % 360 - 180)
            cands.append((out_e.getID(), mv, diff, same))
        if not cands:
            continue
        ts = [c for c in cands if c[1] == 'T']
        best_t = min(ts, key=lambda c: (1 - c[3], c[2]))[0] if ts else None
        weights = {}
        for oid, mv, adiff, same in cands:
            if mv == 'T':
                weights[oid] = 97.0 if oid == best_t else 1.5
            else:
                weights[oid] = 50.0 if best_t is None else DEFAULT_W[mv]
        tot = sum(weights.values())
        for oid, wv in weights.items():
            lines.append(f'    <edgeRelation from="{e.getID()}" to="{oid}" probability="{wv/tot:.4f}"/>')
    lines += ['  </interval>', '</turns>']
    open(util.wpath(world, 'turns.xml'), 'w').write('\n'.join(lines))

def build_flows(world):
    demand = util.jload(util.wpath(world, 'demand.json'))
    vtype = ('  <vType id="car" accel="2.6" decel="4.5" sigma="0.5" length="4.8" minGap="2.2" '
             'maxSpeed="33" speedFactor="normc(1,0.08,0.8,1.2)"/>')
    rows = [vtype]
    # definition order is part of the routing RNG stream — keep it stable
    for fid, e in demand['entries'].items():
        if e['vph'] > 5:
            rows.append(f'  <flow id="{fid}" from="{e["edge"]}" begin="0" end="7200" '
                        f'vehsPerHour="{e["vph"]:.0f}" departLane="best" departSpeed="max" type="car"/>')
    open(util.wpath(world, 'flows.xml'), 'w').write('<routes>\n' + '\n'.join(rows) + '\n</routes>\n')

def route(world, seed=42):
    build_turns(world)
    build_flows(world)
    net = load_net(util.wpath(world, 'net.net.xml'))
    sinks = [e.getID() for e in net.getEdges() if not e.getOutgoing()]
    r = subprocess.run([util.sumo_bin('jtrrouter'),
        '--net-file', util.wpath(world, 'net.net.xml'),
        '--route-files', util.wpath(world, 'flows.xml'),
        '--turn-ratio-files', util.wpath(world, 'turns.xml'),
        '--output-file', util.wpath(world, 'routes.rou.xml'),
        '--sink-edges', ','.join(sinks),
        '--turn-defaults', '1,98,1', '--accept-all-destinations', 'false',
        '--allow-loops', 'false', '--randomize-flows', 'true',
        '--seed', str(seed), '--remove-loops', 'true', '--ignore-errors', 'true'],
        capture_output=True, text=True)
    n = sum(1 for l in open(util.wpath(world, 'routes.rou.xml')) if '<vehicle' in l)
    util.log_event(world, 'route', {'vehicles': n, 'seed': seed})
    return n
