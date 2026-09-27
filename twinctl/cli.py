"""twinctl — control surface for a traffic corridor digital twin.

Terse text out by default (one fact per line); --json everywhere.

Verbs that read or drive a single world (observe, plan, demand, route, run,
validate, calibrate) take either a world name or `--window <am|md|pm>`, which
resolves against the time-of-day registry (`twinctl tod`).
"""
import argparse, json, sys
from . import util


def _world(a):
    """World name from the positional arg or from --window."""
    from .tod import world_arg
    return world_arg(a)

def _wpos(p):
    """A world positional that --window can stand in for."""
    p.add_argument('world', nargs='?')
    p.add_argument('--window', '-w', help='time-of-day window (twinctl tod)')
    return p


def main(argv=None):
    ap = argparse.ArgumentParser(prog='twinctl', description=__doc__)
    ap.add_argument('--json', action='store_true', dest='as_json')
    sub = ap.add_subparsers(dest='cmd', required=True)

    sub.add_parser('worlds', help='list worlds')
    p = sub.add_parser('init', help='create base world from an asset directory')
    p.add_argument('name'); p.add_argument('--from', dest='assets', required=True)
    p = sub.add_parser('fork', help='clone a world'); p.add_argument('src'); p.add_argument('new')
    p = sub.add_parser('kill', help='remove a world'); p.add_argument('name'); p.add_argument('--purge', action='store_true')
    p = sub.add_parser('observe', help='world summary'); _wpos(p)
    p = sub.add_parser('events', help='world audit log'); p.add_argument('world'); p.add_argument('-n', type=int, default=20)
    p = sub.add_parser('demand', help='show demand w/ provenance'); _wpos(p)
    p = sub.add_parser('plan', help='show signal plan'); _wpos(p)
    p = sub.add_parser('route', help='rebuild routes from demand'); _wpos(p)
    p = sub.add_parser('run', help='simulate'); _wpos(p)
    p.add_argument('--seeds', default='42'); p.add_argument('--label', default='run')
    p = sub.add_parser('validate', help='GEH scorecard vs field'); _wpos(p)
    p.add_argument('--seeds', default='42')
    p = sub.add_parser('calibrate', help='iterative demand calibration'); _wpos(p)
    p.add_argument('--iters', type=int, default=5); p.add_argument('--target-pct', type=float, default=85.0)
    p = sub.add_parser('retime', help='edit signal plan'); p.add_argument('world')
    p.add_argument('--offsets'); p.add_argument('--split-shift')
    p = sub.add_parser('perturb', help='inject a shock'); p.add_argument('world'); p.add_argument('shock')
    p.add_argument('--entry'); p.add_argument('--pct', type=float, default=20)
    p.add_argument('--edge'); p.add_argument('--signal')
    p = sub.add_parser('experiment', help='fork+apply+run+rank in one step'); p.add_argument('world')
    p.add_argument('--candidates', required=True); p.add_argument('--seeds', default='42,7,99')
    p = sub.add_parser('compare', help='KPIs side by side'); p.add_argument('worlds_', nargs='+')
    p.add_argument('--baseline', required=True)
    p = sub.add_parser('promote', help='write recommendation package'); p.add_argument('world')
    p.add_argument('--baseline'); p.add_argument('--out')
    sub.add_parser('shocks', help='available shocks')
    sub.add_parser('tod', help='time-of-day windows and the world twinning each')

    a = ap.parse_args(argv)
    J = a.as_json

    if a.cmd == 'worlds':
        from .world import worlds
        ws = worlds()
        util.out({'worlds': ws}, J, lambda: [print(f"{w['world']:28} parent={w['parent'] or '-':14} "
            f"geh<5={w['geh_lt5_pct'] if w['geh_lt5_pct'] is not None else '-':>5}% "
            f"calibrated={'yes' if w['calibrated'] else 'no'}") for w in ws] or (ws or print('no worlds')))
    elif a.cmd == 'init':
        from .world import init
        init(a.name, a.assets); print(f'{a.name} created (paused; twinctl run {a.name})')
    elif a.cmd == 'fork':
        from .world import fork
        fork(a.src, a.new); print(f'{a.new} forked from {a.src}')
    elif a.cmd == 'kill':
        from .world import kill
        print(kill(a.name, a.purge))
    elif a.cmd == 'observe':
        from .world import observe
        o = observe(_world(a))
        util.out(o, J, lambda: [print(f'{k}: {json.dumps(v) if isinstance(v,(dict,list)) else v}')
                                for k, v in o.items()])
    elif a.cmd == 'events':
        from .world import events
        ev = events(a.world, a.n)
        util.out({'events': ev}, J, lambda: [print(f"{e['t']}  {e['kind']:10} {json.dumps(e['detail'])[:110]}") for e in ev])
    elif a.cmd == 'demand':
        d = util.jload(util.wpath(_world(a), 'demand.json'))
        def txt():
            for fid, e in sorted(d['entries'].items()):
                print(f"entry {fid:10} {e['vph']:7.0f} vph  edge {e['edge']}")
            for sig, dirs in sorted(d['signals'].items()):
                for dr, v in dirs.items():
                    print(f"{sig} {dr:10} {v['source']:9} {v['moves']}")
        util.out(d, J, txt)
    elif a.cmd == 'plan':
        from .plan import describe
        rows = describe(_world(a))
        util.out({'plan': rows}, J, lambda: [print(f"{r['signal']}  cycle {r['cycle']:g}s  offset {r['offset']:g}s  "
            f"main {r['main_green']:g}s  cross {r['cross_green'] or 0:g}s") for r in rows])
    elif a.cmd == 'route':
        from .demandio import route
        n = route(_world(a)); print(f'{n} vehicles routed')
    elif a.cmd == 'run':
        from .simrun import run
        seeds = tuple(int(s) for s in a.seeds.split(','))
        r = run(_world(a), seeds=seeds, label=a.label)
        util.out(r, J, lambda: [print(f'{k}: {v}') for k, v in r['aggregate'].items()])
    elif a.cmd == 'validate':
        from .validate import scorecard
        seeds = tuple(int(s) for s in a.seeds.split(','))
        r = scorecard(_world(a), seeds=seeds)
        def txt():
            for row in r['rows']:
                flag = '' if row['geh'] < 5 else '  <-- FAIL'
                print(f"{row['signal']} {row['dir'][:2]:2} {row['move']}  field {row['field_vph']:6.0f}  "
                      f"sim {row['sim_vph']:6.0f}  GEH {row['geh']:5.2f}{flag}")
            s = r['summary']
            print(f"GEH<5 on {s['geh_lt5_pct']}% of {s['movements']} measured movements "
                  f"(mean {s['geh_mean']}, max {s['geh_max']}) -> {'PASS' if s['passing'] else 'NOT PASSING'}")
        util.out(r, J, txt)
    elif a.cmd == 'calibrate':
        from .calibrate import calibrate
        r = calibrate(_world(a), iters=a.iters, target_pct=a.target_pct)
        s = r['final']['summary']
        util.out(r, J, lambda: print(f"calibrated: GEH<5 {s['geh_lt5_pct']}% mean {s['geh_mean']} "
                                     f"({'PASS' if s['passing'] else 'NOT PASSING'})"))
    elif a.cmd == 'retime':
        from .plan import retime
        ch = retime(a.world, json.loads(a.offsets) if a.offsets else None,
                    json.loads(a.split_shift) if a.split_shift else None)
        print('; '.join(ch) if ch else 'no changes')
    elif a.cmd == 'perturb':
        from .perturb import perturb
        kw = {k: v for k, v in [('entry', a.entry), ('pct', a.pct), ('edge', a.edge),
                                ('signal', a.signal)] if v is not None}
        print(json.dumps(perturb(a.world, a.shock, **kw)))
    elif a.cmd == 'experiment':
        from .experiment import experiment
        seeds = tuple(int(s) for s in a.seeds.split(','))
        r = experiment(a.world, json.loads(a.candidates), seeds=seeds)
        def txt():
            if r['warning']: print(r['warning'])
            for row in r['rows']:
                sig = {True: ' *', False: '  ', None: '  '}[row['significant']]
                print(f"{row['candidate']:14} delay {row['mean_delay_s']:7.1f}"
                      f"{('±' + str(row.get('mean_delay_s_sd', 0))):8} {row['delta_delay_s']:+7.1f}s{sig}"
                      f"  stops {row['mean_stops']}")
            if r['verdict']: print(r['verdict'])
        util.out(r, J, txt)
    elif a.cmd == 'compare':
        from .experiment import compare
        rows = compare(a.worlds_, a.baseline)
        util.out({'rows': rows}, J, lambda: [print(f"{r['world']:22} delay {r['mean_delay_s']:7.1f} "
            f"({r['delta_delay_s']:+.1f})  stops {r['mean_stops']}  arrived {r['arrived']:.0f}") for r in rows])
    elif a.cmd == 'promote':
        from .promote import promote
        p, text = promote(a.world, a.baseline, a.out)
        print(text); print(f'\nwritten: {p}')
    elif a.cmd == 'shocks':
        from .perturb import SHOCKS
        print('\n'.join(SHOCKS))
    elif a.cmd == 'tod':
        from .tod import windows
        rows = windows()
        def txt():
            if not rows:
                print('no world declares a time-of-day window')
                return
            for r in rows:
                print(f"{r['window']:3} {r['world']:12} {r['label']:9} "
                      f"plan {str(r['plan'] or '-'):13} "
                      f"cycle {(str(r['cycle_s']) + 's') if r['cycle_s'] else '-':7} "
                      f"field {r['field_window'] or '-':24} "
                      f"geh<5 {str(r['geh_lt5_pct'] or '-'):>5}%  "
                      f"delay {str(r['mean_delay_s'] or '-'):>6}s"
                      f"{'  (implicit)' if r['implicit'] else ''}")
        util.out({'windows': rows}, J, txt)

if __name__ == '__main__':
    main()
