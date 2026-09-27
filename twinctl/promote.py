"""Promote a scenario: human-readable recommendation package (never touches the street)."""
import os
from . import util, plan

def promote(world, baseline=None, out_path=None):
    util.require(world)
    m = util.meta(world)
    base = baseline or m.get('parent')
    lines = [f'# Timing recommendation — {world}',
             f'Corridor: {m.get("corridor")}  ·  window: {m.get("window")}', '']
    if base and util.exists(base):
        bp = {r['signal']: r for r in plan.describe(base)}
        wp = plan.describe(world)
        lines.append('| Signal | Offset (was → rec) | Main green (was → rec) | Cross green (was → rec) |')
        lines.append('|---|---|---|---|')
        for r in wp:
            b = bp.get(r['signal'], {})
            def cell(k):
                was, now = b.get(k), r.get(k)
                if was is None or now is None:
                    return '—'
                return f'{was:g} s' if abs(was - now) < 0.05 else f'**{was:g} → {now:g} s**'
            lines.append(f"| {r['signal']} | {cell('offset')} | {cell('main_green')} | {cell('cross_green')} |")
        lines.append('')
    lr = m.get('last_run')
    if lr:
        k = lr['kpis']
        lines.append(f"Simulated ({len(lr['seeds'])} seeds): mean delay {k['mean_delay_s']} s/veh"
                     + (f" ± {k.get('mean_delay_s_sd', 0)}" if 'mean_delay_s_sd' in k else '')
                     + f", stops {k['mean_stops']}, total delay {k['total_delay_vehh']} veh-h.")
    v = m.get('validation')
    if v:
        lines.append(f"Twin validation: GEH<5 on {v['geh_lt5_pct']}% of measured movements "
                     f"(mean {v['geh_mean']}).")
    lines += ['', '_This is a recommendation for engineering review — twinctl never writes to field equipment._']
    text = '\n'.join(lines)
    p = out_path or util.wpath(world, 'recommendation.md')
    open(p, 'w').write(text)
    util.log_event(world, 'promote', {'path': p})
    return p, text
