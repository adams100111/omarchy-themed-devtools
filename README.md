# omarchy-themed-devtools

Omarchy themes ~17 surfaces from a single `colors.toml`. It does not theme the
command-line tools you actually work inside. This does — for every Omarchy
theme, not just one.

| Tool | Before | After |
|---|---|---|
| `herdr` | fixed `accent = "blue"` | your theme's accent |
| `bat` | Monokai Extended, always | your palette |
| `lazygit` / `lazydocker` | their own defaults | your palette |
| `starship` | hardcoded `cyan` | your theme's accent |
| `fzf` / `eza` / `tmux` | terminal defaults | your palette |

## How it works

Omarchy's `omarchy-theme-set-templates` renders **any** `.tpl` file in
`~/.config/omarchy/themed/` against the active palette on every theme change —
new filenames included, not just overrides of Omarchy's own built-in templates.
That is the entire mechanism this project rests on: it ships eight `.tpl`
files (one per tool, plus bat's `.tmTheme`) into that directory and a single
`theme-set.d` hook that wires each rendered file to wherever its tool reads
config from. Nothing in Omarchy is patched or forked.

## What it touches

**Owned** — the tool's whole config file is replaced with a symlink to the
generated one, and any real file already there is backed up once to
`<file>.pre-omarchy-theme`:
`~/.config/starship.toml`, `~/.config/lazydocker/config.yml`.

**Layered** — the user's own config is left alone; the tool is pointed at the
generated file alongside it via an environment variable or an appended
`source-file` line:
`lazygit` (`LG_CONFIG_FILE`), `fzf` (`FZF_DEFAULT_OPTS_FILE`), `eza`
(`EZA_COLORS`), `tmux` (`source-file` in `tmux.conf`).

**Spliced** — the tool mixes theme settings with other settings in one file
and offers no include mechanism, so only a marker-delimited block is rewritten
and everything else — including keybindings — is left byte-for-byte alone:
`~/.config/herdr/config.toml`.

Eight templates ship, but only seven have a hook adapter. `eza` has a
template with no adapter: its output uses comma-separated ANSI codes, but
`EZA_COLORS` needs semicolons, and that conversion happens once in
`install.sh` when it writes the env file, not in the hook. Doing it in the
hook would mean writing into Omarchy's own state directory on every theme
change, and would leave a shell opened before the *first* theme change with
the wrong value until the next change fired. Converting where the value is
consumed avoids both.

`delta` is declared as a dependency in the dev-boost `cli` profile this
project was built alongside, but it was not installed on the development
machine, so `install.sh` carries guarded wiring for a `delta.gitconfig`
include (`command -v delta && ...`) that simply never fires here and has not
been exercised end to end. It is not supported in v1.

## Herdr's accent does not round-trip

Every other file this project touches restores exactly — symlinks and their
`*.pre-omarchy-theme` backups, the marker blocks in `git/config`,
`tmux.conf`, and `bat/config`, the bat theme file, the env file. `herdr` is
the one exception.

herdr keeps a single `accent` key under `[ui]`, outside the block this
project manages, and the theme's accent color is applied there so herdr's UI
matches its border colors. `splice()` in `lib/herdr_patch.py` replaces that
key **in place** — there is no record of what it was before, so `uninstall.sh`
has nothing to restore it from. Concretely: a config with `accent = "blue"`
before install still reads `accent = "#c2a15a"` (or whatever the last active
theme's accent was) after `install.sh` + a theme change + `uninstall.sh`.
If you want that value back, note it down before installing.

## Install

```bash
git clone <this-repo> ~/repos/omarchy-themed-devtools
cd ~/repos/omarchy-themed-devtools
./install.sh
```

`install.sh` never edits your shell rc file. It prints a `source` line —
add it to `~/.bashrc` yourself, then open a new shell:

```bash
source ~/.config/omarchy/themed-devtools.env
```

Then apply any theme to populate everything:

```bash
omarchy theme set "$(omarchy theme current)"
```

## Uninstall

```bash
./uninstall.sh
```

Restores every `*.pre-omarchy-theme` backup, strips the marker-delimited
blocks it added to `git/config`, `tmux.conf`, `bat/config`, and
`herdr/config.toml`, removes the symlinked templates and hook, and deletes
the env file. See "Herdr's accent does not round-trip" above for the one
value it cannot restore. Safe to run when nothing is installed.

## Headless and offline theme changes

Omarchy skips `theme-set.d` hooks entirely when `OMARCHY_THEME_HEADLESS=1` or
`OMARCHY_THEME_OFFLINE=1` is set for the theme change. Nothing gets themed in
that case until you re-run the hook by hand:

```bash
bash ~/.config/omarchy/hooks/theme-set.d/apply-devtools-theme --sync --verbose
```

## Tests

```bash
uvx --with pyyaml pytest -v
```
