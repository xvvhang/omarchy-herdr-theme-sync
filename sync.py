#!/usr/bin/env python3
"""Generate explicit Herdr RGB tokens from Omarchy's active semantic palette."""
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib

PLUGIN_ID = "alec.herdr-theme"
CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
STATE = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
HERE = Path(__file__).resolve().parent
HEX = re.compile(r"#[0-9a-fA-F]{6}\Z")


def rgb(color):
    if not isinstance(color, str) or not HEX.fullmatch(color):
        raise ValueError(f"Invalid palette color: {color!r}")
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


def mix(a, b, weight):
    return "#" + "".join(f"{round(x * (1 - weight) + y * weight):02X}"
                         for x, y in zip(rgb(a), rgb(b)))


def luminance(color):
    def linear(c):
        c /= 255
        return c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4
    return sum(w * linear(c) for w, c in zip((.2126, .7152, .0722), rgb(color)))


def contrast(a, b):
    x, y = sorted((luminance(a), luminance(b)))
    return (y + .05) / (x + .05)


def readable(color, background, fallback, minimum=4.5):
    rgb(color)
    for step in range(21):
        candidate = mix(color, fallback, step / 20)
        if contrast(candidate, background) >= minimum:
            return candidate
    return fallback


def palette(colors):
    bg, fg, accent = (colors[k] for k in ("background", "foreground", "accent"))
    for value in (bg, fg, accent):
        rgb(value)
    fallback = "#151515" if luminance(bg) > .35 else "#F4F4F4"
    text = readable(fg, bg, fallback)
    # Do not reuse ANSI black/white or saturated selection colors as surfaces.
    row = mix(bg, fg, .075)
    selection = mix(bg, accent, .16)
    # Some widgets render normal text over these surfaces.
    if contrast(text, selection) < 4.5:
        selection = mix(bg, fg, .12)
    tokens = {
        "panel_bg": bg, "sidebar_bg": mix(bg, fg, .025),
        "active_row_bg": row, "selection_bg": selection,
        "surface0": mix(bg, fg, .035), "surface1": mix(bg, fg, .10),
        "surface_dim": mix(bg, fg, .055),
        "overlay0": readable(colors.get("muted", fg), bg, text),
        "overlay1": text, "text": text,
        "subtext0": readable(mix(bg, fg, .65), bg, text),
        "accent": accent,
    }
    for token, source in {"mauve": "magenta", "green": "green", "yellow": "yellow",
                          "red": "red", "blue": "blue", "teal": "cyan",
                          "peach": "orange"}.items():
        tokens[token] = readable(colors.get(source, accent), bg, text)
    return tokens


def fragment(tokens):
    return ('[theme]\nname = "terminal"\nauto_switch = false\n\n'
            '[theme.custom]\n' + ''.join(f'{k} = "{v}"\n' for k, v in tokens.items()))


def update_config(original, tokens):
    before = tomllib.loads(original)
    # Preserve all non-theme tables and comments verbatim. Validate the semantic
    # result, refusing unusual table layouts rather than damaging user settings.
    chunks = re.split(r"(?m)^(?=\s*\[[^\n]+\]\s*(?:#.*)?$)", original)
    kept = []
    ui_seen = False
    for chunk in chunks:
        header = re.match(r"\s*\[([^\]\n]+)\]", chunk)
        name = header.group(1).strip() if header else ""
        if name == "theme" or name.startswith("theme."):
            continue
        if name == "ui":
            ui_seen = True
            chunk = re.sub(r'(?m)^[ \t]*accent[ \t]*=.*(?:\n|$)', '', chunk)
            pos = chunk.index('\n') + 1
            chunk = chunk[:pos] + 'accent = "' + tokens['accent'] + '"\n' + chunk[pos:]
        kept.append(chunk)
    if not ui_seen:
        kept.append('\n[ui]\naccent = "' + tokens['accent'] + '"\n')
    result = ''.join(kept).rstrip() + '\n\n' + fragment(tokens)
    after = tomllib.loads(result)
    expected = dict(before)
    expected['theme'] = tomllib.loads(fragment(tokens))['theme']
    expected['ui'] = dict(before.get('ui', {}), accent=tokens['accent'])
    if after != expected:
        raise ValueError("Unsupported config layout; no changes written")
    return result


def atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(text)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def enabled():
    config = json.loads((CONFIG / 'omarchy/shell.json').read_text())
    return (PLUGIN_ID not in config.get('disabledPlugins', []) and
            any(p.get('id') == PLUGIN_ID for p in config.get('plugins', [])))


def sync():
    if not enabled():
        return
    directory = STATE / 'omarchy/herdr-theme-sync'
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'sync.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not enabled():
            return
        colors = tomllib.loads((STATE / 'omarchy/current/theme/colors.toml').read_text())
        tokens = palette(colors)
        target = CONFIG / 'herdr/config.toml'
        original = target.read_text() if target.exists() else ''
        result = update_config(original, tokens)
        backup = directory / 'config.before-sync.toml'
        if not backup.exists():
            atomic_write(backup, original)
        # Export a standalone, inspectable fragment; Herdr itself reads config.toml.
        atomic_write(directory / 'theme.toml', fragment(tokens))
        hook = CONFIG / 'omarchy/hooks/theme-set.d/herdr-theme-sync'
        hook.parent.mkdir(parents=True, exist_ok=True)
        source = (HERE / 'herdr-theme-sync').read_text()
        if hook.exists() and hook.read_text() != source:
            raise ValueError(f"Refusing to overwrite another hook: {hook}")
        if not hook.exists():
            atomic_write(hook, source)
            hook.chmod(0o755)
        if result != original:
            # Avoid replacing a concurrent user edit with a stale snapshot.
            if target.exists() and target.read_text() != original:
                raise ValueError('Herdr config changed during generation; retry sync')
            atomic_write(target, result)
        if shutil.which('herdr') and (CONFIG / 'herdr/herdr.sock').exists():
            result = subprocess.run(['herdr', 'server', 'reload-config'],
                                    capture_output=True, text=True, timeout=10)
            if result.returncode:
                raise RuntimeError(result.stderr or result.stdout)
        print('Herdr theme synchronized from the active Omarchy palette.')


if __name__ == '__main__':
    try:
        if sys.argv[1:] == ['sync']:
            sync()
        elif sys.argv[1:] == ['preview']:
            print(fragment(palette(tomllib.loads(
                (STATE / 'omarchy/current/theme/colors.toml').read_text()))))
        else:
            raise ValueError('Usage: sync.py sync|preview')
    except Exception as error:
        print(f'Herdr Theme Sync: {error}', file=sys.stderr)
        sys.exit(1)
