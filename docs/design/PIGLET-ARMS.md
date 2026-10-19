# Design: Piglet arms (arm kind `piglet`)

Status: design. Build after the launch gates and the flip. Today a Piglet arm is a derived arm (`[derive] base = "pig-tip"` plus a `prepare.py` that calls `prepare_pig.fused_binary`; see `arms/pig-standard`, `arms/pig-strip-min`, the ext-matrix arms) and its record carries `piglet` {label, slots, strip, runtime_slot, binary_bytes}.

## What the owner asked

A new arm kind `piglet`, pinned from Pigpen git now and from pi-in-go.dev (the npm package with keyword `pig-piglet`: version plus checksum) after 0.5.0; built with `pig piglet build` inside the arm's image; base, slots, strips and binary size recorded; every family runs on it.

## Manifest

```toml
name = "piglet-example"
[piglet]
base = "pig-tip"                         # the Stock PiG arm whose checkout and executable build it
source = "pigpen"                        # pigpen | npm
# pigpen: a git pin; the piglet YAML path inside the repository
repo_env = "BUFFON_SOURCE_REPO_PIGPEN"    # clone location (never a URL in the repo unless public); repo_url = "https://..." when public
commit = "<40 hex>"
tree = "<40 hex>"
yaml = "piglets/example/piglet.yaml"
# npm (after 0.5.0): the published package, pinned
# package = "@scope/name"; version = "1.2.3"; integrity = "sha512-..."; keyword = "pig-piglet"
[build]
format = "binary"                        # binary | script (script = a launcher, measured as stock PiG plus its Piglet resources)
```

Exactly one of `[artifact]`, `[npm]`, `[source]`, `[derive]`, `[piglet]`. `[piglet]` implies the derive mechanics (a copy of the base install tree, a source checkout of the base) and replaces `prepare.py` with a built-in step, so a Piglet arm is data, not code.

## Install

1. Resolve the pin. Pigpen: clone, check out `commit`, verify `tree`, as `Workspace._source` does (submodules, repo_url fallback already exist). npm: download the tarball with `npm pack` offline-capable, verify the `integrity` against the manifest, record the package's `pig-piglet` keyword and `version` (an unpinned `latest` is a manifest error).
2. Build in the arm's image: `pig piglet build <yaml> --format binary --out <install>/bin/pig-piglet` run by the base arm's executable, with `PIG_SOURCE_ROOT` at the base checkout and the pinned Go, inside the container envelope (the same image as the arms run in) so the build host does not leak into the binary. Build time is a `devloop/build` sample.
3. Record: `piglet` {label "base Piglet + slots, one binary", base arm and commit, yaml sha256, slots (extension names), strip block (keep or deny mode and its IDs), runtime slots, binary size, build argv, builder tree sha}. The report's "Piglet arms" table (`render.piglet_section`) prints it; a Piglet's strip IDs are the answer to "what did this binary drop".
4. Lock: `arms.lock` records the pin, the yaml hash and the built executable's sha256 (a rebuild at the same pin must produce the same bytes or the arm is flagged non-reproducible; PiG builds are expected to be reproducible, test it before relying on it).

## Capabilities and families

A Piglet arm declares what it can do from its slots: extension rows are N/A when it has no extension runtime (as `pig-strip-min`), `pi_session_format` and RPC follow the base. Every family (overhead, streaming, longsession, reliability, soak, devloop, scale, faithfulness) runs on it unchanged; an N/A row cites the missing slot. Faithfulness scores a Piglet like any arm and lists the strip IDs next to mismatches they explain (a stripped `/export-html` is an intentional divergence, counted).

## Tests

Manifest validation (exactly one install kind; npm needs version+integrity; pigpen needs commit+tree); install with a fake builder (the argv, env, and record); a rebuild-determinism test (two builds, equal sha256); the report row; lock regeneration.

## Open

The pi-in-go.dev registry layout is not specified yet; the npm path stays a documented stub until a published Piglet exists. Which Pigpen repository and commit are the first pins is the lead's call.
