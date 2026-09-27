"""Network geometry helpers: approach direction and movement classification."""
import math
from functools import lru_cache
import sumolib

@lru_cache(maxsize=4)
def load_net(path):
    return sumolib.net.readNet(path)

def heading(edge, at_end=True):
    sh = edge.getShape()
    (x1, y1), (x2, y2) = (sh[-2], sh[-1]) if at_end else (sh[0], sh[1])
    return math.degrees(math.atan2(x2 - x1, y2 - y1)) % 360  # 0=N, 90=E

def traffic_dir(edge):
    b = heading(edge)
    if b < 45 or b >= 315: return 'Northbound'
    if b < 135: return 'Eastbound'
    if b < 225: return 'Southbound'
    return 'Westbound'

def movement(in_e, out_e):
    diff = (heading(out_e, False) - heading(in_e) + 540) % 360 - 180
    if abs(diff) > 150: return 'L'
    return 'T' if abs(diff) < 40 else ('R' if diff > 0 else 'L')

def tls_nodes(net, tlsid):
    nodes = set()
    for c in net.getTLS(tlsid).getConnections():
        nodes.add(c[0].getEdge().getToNode())
    return nodes

def signal_node_map(net, mapping):
    """node id -> signal id for every node of every mapped tls cluster."""
    out = {}
    for sig, m in mapping.items():
        for n in tls_nodes(net, m['tls']):
            out[n.getID()] = sig
    return out
