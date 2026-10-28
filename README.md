# Herdr Theme Sync

Omarchy service plugin that generates explicit RGB colors for Herdr 0.9.1.
No bar widget, ANSI color mapping, polling, or external Python dependencies.

Plugin ID: `xvvhang.herdr-theme-sync`. Local directory: `~/.config/omarchy/plugins/herdr-theme-sync/`.

Enable: `omarchy plugin enable xvvhang.herdr-theme-sync`

Disable: `omarchy plugin disable xvvhang.herdr-theme-sync`

On enable, the service synchronizes immediately and installs its own
`theme-set.d/herdr-theme-sync` hook. The hook checks whether the plugin is still
enabled before every run. Disabling stops synchronization and leaves the last
generated colors in place. Other hooks are untouched.

Reads the active `~/.local/state/omarchy/current/theme/colors.toml`. Mixes subtle
surfaces from background/foreground/accent, corrects secondary text contrast,
and writes all Herdr color tokens as RGB. Also synchronizes `[ui].accent` to
avoid the old ANSI accent override. The `[theme]` subtree is managed by this
plugin, including disabling Herdr's independent light/dark auto-switch.
Other configuration values and their comments are preserved.

Generated fragment: `~/.local/state/omarchy/herdr-theme-sync/theme.toml`.
First-run full configuration backup:
`~/.local/state/omarchy/herdr-theme-sync/config.before-sync.toml`.
The fragment is exported for inspection, not loaded by Herdr as a separate file.

Changes are validated and atomically written. A running local Herdr server is
notified with `herdr server reload-config`; if Herdr is stopped, it reads the
colors on its next start. Existing panes and sessions are not restarted.

Manual synchronization: `python ~/.config/omarchy/plugins/herdr-theme-sync/sync.py sync`

Preview without modifying configuration:
`python ~/.config/omarchy/plugins/herdr-theme-sync/sync.py preview`

To restore manually, disable the plugin first and review the saved backup before
merging its `[theme]` and `[ui].accent` back into your current Herdr config.
Do not overwrite newer shortcuts or other settings with the full old backup.
