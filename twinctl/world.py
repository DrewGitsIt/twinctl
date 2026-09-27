"""World lifecycle: init (from base assets), fork, observe, list."""
import os, shutil, time
from . import util

COPY = ['net.net.xml', 'tls_mapping.json', 'model.json', 'demand.json',
        'plan.tll.xml', 'routes.rou.xml', 'turns.xml', 'flows.xml']

def worlds():
    if not os.path.isdir(util.WORLDS):
        return []
    out = []
    for w in sorted(os.listdir(util.WORLDS)):
        if os.path.isfile(util.wpath(w, 'meta.json')):
            m = util.meta(w)
            out.append({'world': w, 'parent': m.get('parent'),
                        'corridor': m.get('corridor'),
                        'calibrated': bool(m.get('calibration')),
                        'geh_lt5_pct': (m.get('validation') or {}).get('geh_lt5_pct'),
                        'last_run': (m.get('last_run') or {}).get('label')})
    return out

def init(name, assets):
    """Create a base world from an asset dir holding COPY files (+ field/)."""
    if util.exists(name):
        util.die(f"world '{name}' exists")
    os.makedirs(util.wpath(name, 'runs'))
    for f in COPY:
        src = os.path.join(assets, f)
        if os.path.exists(src):
            shutil.copy(src, util.wpath(name, f))
    fsrc = os.path.join(assets, 'field')
    if os.path.isdir(fsrc):
        shutil.copytree(fsrc, util.wpath(name, 'field'))
    util.save_meta(name, {'world': name, 'parent': None,
                          'corridor': 'state-street-slc-800s-2100s',
                          'window': '2026-09-09 16:00-18:00',
                          'created': time.strftime('%Y-%m-%d %H:%M')})
    util.log_event(name, 'init', {'from': assets})
    return name

def fork(src, new):
    util.require(src)
    if util.exists(new):
        util.die(f"world '{new}' exists")
    os.makedirs(util.wpath(new, 'runs'))
    for f in COPY + ['extra.add.xml']:
        if os.path.exists(util.wpath(src, f)):
            shutil.copy(util.wpath(src, f), util.wpath(new, f))
    if os.path.isdir(util.wpath(src, 'field')):
        shutil.copytree(util.wpath(src, 'field'), util.wpath(new, 'field'))
    m = util.meta(src)
    m.update({'world': new, 'parent': src, 'last_run': None,
              'created': time.strftime('%Y-%m-%d %H:%M')})
    util.save_meta(new, m)
    util.log_event(new, 'fork', {'from': src})
    return new

def kill(name, purge=False):
    util.require(name)
    if purge:
        shutil.rmtree(util.wdir(name))
        return f'{name} purged'
    return f'{name} kept (only --purge deletes)'

def observe(name):
    util.require(name)
    m = util.meta(name)
    demand = util.jload(util.wpath(name, 'demand.json'))
    entry_vph = round(sum(e['vph'] for e in demand['entries'].values()))
    return {'world': name, 'parent': m.get('parent'), 'corridor': m.get('corridor'),
            'window': m.get('window'), 'entry_vph_total': entry_vph,
            'validation': m.get('validation'),
            'calibration': (m.get('calibration') or {}).get('final'),
            'last_run': m.get('last_run')}

def events(name, n=20):
    util.require(name)
    p = util.wpath(name, 'events.jsonl')
    if not os.path.exists(p):
        return []
    import json
    return [json.loads(l) for l in open(p).read().splitlines()[-n:]]
