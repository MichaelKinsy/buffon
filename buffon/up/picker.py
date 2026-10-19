# SPDX-License-Identifier: Apache-2.0
"""The interactive picker: arrow keys (or j/k) and space on a terminal, enter to accept; a plain numbered `input()` list when the terminal cannot do raw keys.

Nothing but the standard library. Every function takes its input and output so a test can feed it keys."""
import sys

UP, DOWN, SPACE, ENTER, QUIT, ALL, NONE = "up", "down", "space", "enter", "quit", "all", "none"
ESCAPES = {"\x1b[A": UP, "\x1b[B": DOWN, "\x1bOA": UP, "\x1bOB": DOWN}


class Aborted(Exception):
    pass


def read_key(fd=None):
    """One key from the terminal in raw mode: one of the names above, or the character itself."""
    import os
    import select
    import termios
    import tty
    fd = sys.stdin.fileno() if fd is None else fd
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = os.read(fd, 1).decode("utf-8", "replace")
        if ch == "\x1b":
            rest = ""
            while select.select([fd], [], [], 0.05)[0] and len(rest) < 2:
                rest += os.read(fd, 1).decode("utf-8", "replace")
            ch += rest
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    if ch in ESCAPES:
        return ESCAPES[ch]
    return {" ": SPACE, "\r": ENTER, "\n": ENTER, "q": QUIT, "\x03": QUIT, "\x04": QUIT, "\x1b": QUIT, "k": UP, "j": DOWN, "a": ALL, "n": NONE}.get(ch, ch)


def is_tty(stdin=None, stdout=None):
    stdin, stdout = stdin or sys.stdin, stdout or sys.stdout
    try:
        return stdin.isatty() and stdout.isatty()
    except (AttributeError, ValueError):
        return False


def is_header(item_id):
    """A group heading in a list of choices (a track's name): shown, never ticked, skipped by the arrow keys."""
    return str(item_id).startswith("#")


def checklist(title, items, chosen, key=read_key, out=None):
    """items: [(id, label, note)]. chosen: ids ticked at the start. Returns the ticked ids in the items' order. Enter accepts, q or ctrl-c aborts (Aborted)."""
    out = out or sys.stdout
    ticked = {i for i, _, _ in items if i in set(chosen) and not is_header(i)}
    at, height = next((n for n, (i, _, _) in enumerate(items) if not is_header(i)), 0), len(items) + 3
    first = True
    while True:
        if not first:
            out.write(f"\x1b[{height}A")
        first = False
        out.write(f"\x1b[2K\r{title}  (up/down move, space ticks, a all, n none, enter runs, q quits)\n")
        for n, (i, label, note) in enumerate(items):
            if is_header(i):
                out.write(f"\x1b[2K\r\x1b[1m{label}\x1b[0m\n")
                continue
            out.write(f"\x1b[2K\r{'>' if n == at else ' '} [{'x' if i in ticked else ' '}] {label}" + (f"  \x1b[2m{note}\x1b[0m" if note else "") + "\n")
        out.write(f"\x1b[2K\r  {len(ticked)} of {len([1 for i, _, _ in items if not is_header(i)])} ticked\n\x1b[2K\r\n")
        out.flush()
        k = key()
        if k in (UP, DOWN):
            step = -1 if k == UP else 1
            at = (at + step) % len(items)
            while is_header(items[at][0]):
                at = (at + step) % len(items)
        elif k == SPACE:
            ticked ^= {items[at][0]}
        elif k == ALL:
            ticked = {i for i, _, _ in items if not is_header(i)}
        elif k == NONE:
            ticked = set()
        elif k == ENTER:
            if ticked:
                return [i for i, _, _ in items if i in ticked]
        elif k == QUIT:
            raise Aborted()


def numbered(title, items, chosen, input_fn=input, out=None):
    """The fallback without raw keys: a numbered list; the answer is numbers or ids separated by commas, `a` for all, Enter for the ticked ones."""
    out = out or sys.stdout
    chosen = set(chosen)
    while True:
        out.write(f"{title}\n")
        numbered_items = [it for it in items if not is_header(it[0])]
        n = 0
        for i, label, note in items:
            if is_header(i):
                out.write(f"{label}\n")
                continue
            n += 1
            out.write(f"  {n:2}. [{'x' if i in chosen else ' '}] {label}" + (f"  {note}" if note else "") + "\n")
        out.flush()
        try:
            answer = input_fn("numbers or names, comma separated (a = all, Enter = the ticked ones, q = quit): ").strip()
        except EOFError:
            answer = ""
        if answer.lower() == "q":
            raise Aborted()
        if not answer:
            if chosen:
                return [i for i, _, _ in numbered_items if i in chosen]
            continue
        if answer.lower() == "a":
            return [i for i, _, _ in numbered_items]
        picked, bad = [], []
        by_id = {i: i for i, _, _ in numbered_items}
        for token in [t for t in answer.replace(" ", ",").split(",") if t]:
            if token.isdigit() and 1 <= int(token) <= len(numbered_items):
                picked.append(numbered_items[int(token) - 1][0])
            elif token in by_id:
                picked.append(token)
            else:
                bad.append(token)
        if bad:
            out.write(f"not in the list: {', '.join(bad)}\n")
            continue
        return [i for i, _, _ in numbered_items if i in set(picked)]


def choose(title, items, chosen, key=None, input_fn=input, out=None, tty=None):
    """The checklist on a terminal, the numbered list elsewhere."""
    tty = is_tty() if tty is None else tty
    if tty:
        return checklist(title, items, chosen, key or read_key, out)
    return numbered(title, items, chosen, input_fn, out)


def menu(title, options, default, input_fn=input, out=None):
    """options: [(id, text)]. Returns the id typed (number or id); Enter takes the default."""
    out = out or sys.stdout
    while True:
        out.write(f"{title}\n")
        for n, (i, text) in enumerate(options, 1):
            out.write(f"  {n}. {i:9} {text}" + ("   (default)" if i == default else "") + "\n")
        out.flush()
        try:
            answer = input_fn("choice: ").strip()
        except EOFError:
            answer = ""
        if not answer:
            return default
        if answer.lower() == "q":
            raise Aborted()
        if answer.isdigit() and 1 <= int(answer) <= len(options):
            return options[int(answer) - 1][0]
        if answer in [i for i, _ in options]:
            return answer


def pick(harness_rows, bench_rows, sel, estimator, input_fn=input, key=None, out=None, tty=None):
    """Walk a person through the choices: harnesses, then a preset or individual benchmarks, then evals; returns the changed selection. `estimator(sel)` gives the expected seconds shown next."""
    from .. import workloads as workloadlib
    from . import catalog, selection
    out = out or sys.stdout
    # The harnesses that run by default (the rest, built variants and experiments, are named with --harness; `buffon harnesses` lists all) keep the list on one screen.
    usable = [r for r in harness_rows if r["available"] and (r.get("runs_by_default", True) or r["name"] in sel.harnesses)]
    usable.sort(key=lambda r: (r["name"] not in sel.harnesses, r["name"]))
    items = [(r["name"], f"{r['name']} {r['version']}", r["state"]) for r in usable]
    sel.harnesses = choose("Harnesses (the others: --harness NAME; `buffon harnesses` lists all)", items, [h for h in sel.harnesses if any(h == r["name"] for r in usable)], key, input_fn, out, tty)
    options = [(p, f"{d['about']}  (about {selection.format_duration(estimator(sel.clone(workloads=d['workloads'], preset=p, apis=list(d['apis']), rounds=d['rounds'], adaptive=d['adaptive'], calibration_rounds=d['calibration_rounds'], evals=list(d['evals']))))})") for p, d in catalog.PRESETS.items()]
    from . import tracks as trackslib
    tracks = trackslib.load()
    for tid in trackslib.IDS:
        t = tracks[tid]
        options.append((tid, f"Track: {t['title']}. {t['about']}"))
    options.append(("pick", "choose individual benchmarks, grouped by track"))
    which = menu("Benchmarks", options, "quick", input_fn, out)
    if which == "pick":
        wb = []
        shown = set()
        for n, tid in enumerate(trackslib.IDS, 1):
            members = [r for r in bench_rows if tid in r.get("tracks", []) and r["seconds"] is not None]
            if members:
                wb.append((f"#{tid}", f"Track {n} - {tracks[tid]['title']}", ""))
            for r in members:
                if r["id"] not in shown:
                    shown.add(r["id"])
                    wb.append((r["id"], r["id"], f"{r['state']}, about {selection.format_duration(r['seconds'])}"))
        rest = [r for r in bench_rows if r["id"] not in shown and r["seconds"] is not None]
        if rest:
            wb.append(("#other", "Other benchmarks", ""))
            wb += [(r["id"], r["id"], f"{r['state']}, about {selection.format_duration(r['seconds'])}") for r in rest]
        sel.workloads = choose("Benchmarks", wb, sel.workloads or catalog.PRESETS["quick"]["workloads"], key, input_fn, out, tty)
        sel.preset, sel.track, sel.recipes = "", "", []
    elif which in trackslib.IDS:
        t = selection.from_track(which)
        sel.workloads, sel.track, sel.recipes, sel.apis, sel.rounds, sel.adaptive, sel.calibration_rounds, sel.evals, sel.isolation, sel.preset = (
            t.workloads, which, t.recipes, t.apis, t.rounds, t.adaptive, t.calibration_rounds, t.evals, t.isolation, "")
    else:
        d = catalog.PRESETS[which]
        sel.track, sel.recipes = "", []
        sel.workloads, sel.preset, sel.apis, sel.rounds, sel.adaptive, sel.calibration_rounds, sel.evals = list(d["workloads"]), which, list(d["apis"]), d["rounds"], d["adaptive"], d["calibration_rounds"], list(d["evals"])
        sel.workloads = selection._expand(sel.workloads, workloadlib.load_all())
    return sel
