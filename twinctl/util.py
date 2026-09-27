"""Shared plumbing: paths, config, world dirs, event log, output."""
import json, os, sys, time

PKG = os.path.dirname(os.path.abspath(__file__))

def _find_root():
    """Twin root: $TWIN_ROOT, else the package's parent if it holds worlds/
    (a vendored in-repo checkout), else the current working directory."""
    env = os.environ.get('TWIN_ROOT')
    if env:
        return os.path.abspath(env)
    parent = os.path.dirname(PKG)
    if os.path.isdir(os.path.join(parent, 'worlds')):
        return parent
    return os.getcwd()

ROOT = _find_root()
WORLDS = os.path.join(ROOT, 'worlds')

def sumo_bin(name='sumo'):
    cand = os.path.join(ROOT, 'venv', 'bin', name)
    if os.path.exists(cand):
        return cand
    env = os.environ.get('SUMO_HOME')
    if env and os.path.exists(os.path.join(env, 'bin', name)):
        return os.path.join(env, 'bin', name)
    return name  # hope for PATH

def wdir(world):
    return os.path.join(WORLDS, world)

def wpath(world, *parts):
    return os.path.join(wdir(world), *parts)

def exists(world):
    return os.path.isdir(wdir(world))

def require(world):
    if not exists(world):
        die(f"no world '{world}' (twinctl worlds)")

def meta(world):
    return jload(wpath(world, 'meta.json'))

def save_meta(world, m):
    jdump(wpath(world, 'meta.json'), m)

def jload(p):
    with open(p) as f:
        return json.load(f)

def jdump(p, obj):
    with open(p, 'w') as f:
        json.dump(obj, f, indent=1)

def log_event(world, kind, detail):
    with open(wpath(world, 'events.jsonl'), 'a') as f:
        f.write(json.dumps({'t': time.strftime('%Y-%m-%d %H:%M:%S'),
                            'kind': kind, 'detail': detail}) + '\n')

def die(msg, code=2):
    print(f'twinctl: {msg}', file=sys.stderr)
    sys.exit(code)

def out(payload, as_json, text_fn):
    """payload: dict for --json; text_fn() prints terse lines otherwise."""
    if as_json:
        print(json.dumps(payload, indent=1))
    else:
        text_fn()

def geh(m, c):
    """GEH statistic for hourly flows m (model) vs c (count)."""
    if m + c == 0:
        return 0.0
    return (2 * (m - c) ** 2 / (m + c)) ** 0.5
