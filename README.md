# twinctl

Control surface for a traffic corridor digital twin built on SUMO. Terse text
out by default (one fact per line); `--json` everywhere.

Verbs: `worlds`, `observe`, `plan`, `demand`, `route`, `run`, `validate`,
`calibrate`, `experiment`, `promote`, `tod`, `perturb`, and friends —
`twinctl --help` for the full list.

## Install

```sh
pip install -e .
```

This installs a `twinctl` command; `python -m twinctl` works too.

## Where worlds live

twinctl operates on a *twin root* — a directory containing `worlds/` (one
subdirectory per world) and, optionally, a `venv/` whose `bin/` holds the SUMO
binaries. The root resolves in this order:

1. `TWIN_ROOT` environment variable, if set.
2. The package's parent directory, if it contains `worlds/` (a vendored,
   in-repo checkout keeps working unchanged).
3. The current working directory.

So from a project root that has `worlds/`, plain `twinctl worlds` just works.

SUMO binaries resolve from `<root>/venv/bin`, then `$SUMO_HOME/bin`, then
`$PATH`.

## Spec

`docs/twinctl-spec.html` is the CLI's design spec. The domain-agnostic
lifecycle library this CLI helped inspire lives separately as **twincore**.
