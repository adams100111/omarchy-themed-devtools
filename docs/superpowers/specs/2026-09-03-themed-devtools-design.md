# omarchy-themed-devtools — design

**Date:** 2026-09-03
**Status:** approved, ready for implementation planning
**Roadmap:** sub-project 1 of `omarchy-theme-eltahir/docs/superpowers/specs/2026-09-03-omarchy-dev-setup-roadmap.md`

## Problem

Omarchy themes ~17 surfaces from one `colors.toml`. It does not theme the
command-line tools a working developer spends the day inside. On a machine
running the Eltahir theme, verified 2026-09-03:

| Behaviour | Tools | Observed |
|---|---|---|
| Fixed palette, ignores the theme entirely | `bat`, `lazygit`, `lazydocker`, `herdr` | `bat` renders Monokai Extended; `herdr` runs `accent = "blue"` |
| Follows ANSI but hardcodes a non-accent hue | `starship`, `fzf`, `eza` | `starship.toml` hardcodes `cyan` in six places |

`herdr` is the worst case and the highest value: it is the terminal workspace
manager the user actually lives in, so its sidebar, tab bar and pane borders
frame every other surface — and its accent is blue while the desktop is gold.

## Goal

Extend Omarchy's theming engine to cover these tools **for every theme**, not
just Eltahir. Switching to Catppuccin must re-theme them too.

## Non-goals

- Theming anything Omarchy already covers.
- Any Eltahir-specific colour. This project reads whatever palette is active.
- Changing the user's keybindings, prompt structure, or tool behaviour. Colour only.

## Mechanism

Three steps, all using facilities Omarchy already has. Nothing is patched or
forked.

1. `install.sh` symlinks `templates/*.tpl` into `~/.config/omarchy/themed/`.
2. On any `omarchy theme set`, `omarchy-theme-set-templates` globs that
   directory — `template_files=("$USER_TEMPLATES_DIR"/*.tpl "$TEMPLATES_DIR"/*.tpl)`
   — renders each against the active palette, and writes the result into the
   theme state directory.
3. The installed `theme-set.d` hook wires each generated file to where its tool
   reads it, then reloads that tool.

Step 2 is the load-bearing discovery: the glob accepts **new** filenames, so a
template is not restricted to overriding an Omarchy built-in.

### Verified ordering (omarchy 4.0.2-1)

Read from `omarchy-theme-set`; this is what makes step 3 sound:

```
284  omarchy-theme-set-templates          # render into next-theme
292  rm -rf "$CURRENT_THEME_PATH"
293  mv "$NEXT_THEME_PATH" "$CURRENT_THEME_PATH"   # promote
336  run_parallel "${post_theme_commands[@]}"      # Omarchy's own retinting
339  omarchy-hook theme-set "$THEME_NAME"          # our hook
```

Hooks run **after** promotion, so the live theme directory already holds the new
theme's generated files. They also run after Omarchy's own retinting, so an
adapter never races it.

Also established:

- **Precedence is theme-shipped file > user `.tpl` > built-in `.tpl`.** A
  first-writer-wins guard (`if [[ ! -f $output_path ]]`) means a user template is
  ignored for any filename the active theme ships directly. Every filename this
  project introduces is new, so this does not bite — but a template must never be
  named after a file themes commonly ship.
- **Hooks are sequential in glob order**, run as `bash "$hook" "$slug"`; the exec
  bit is not needed and `*.sample` is skipped.
- **A failing hook cannot break a theme change** — `omarchy-hook` guards each call
  with `|| echo "Hook failed:"`, so exit status is swallowed. Exiting 0 remains
  good manners, not a load-bearing requirement.
- **Templates and hooks survive** `omarchy update`, `omarchy refresh` and all
  current migrations; nothing in the package touches those two directories.
- **Hooks do not run at all** when `OMARCHY_THEME_HEADLESS=1` or
  `OMARCHY_THEME_OFFLINE=1`, so adapters silently do not fire in those modes.
- No templates render for a theme with no `colors.toml`.

### Available template vocabulary

Keys resolved by `omarchy-theme-color --all`, plus `{{ key_strip }}` (no `#`),
`{{ key_rgb }}`, `{{ mix a b 30% }}`, `{{ hypr_gradient … }}`, `{{ shell_gradient … }}`.

## Architecture

```
omarchy-themed-devtools/
├── install.sh              link templates, install hook, print shell snippet
├── templates/*.tpl         one per tool — pure colour, no logic
├── hooks/apply-devtools-theme     the single theme-set.d hook
├── lib/herdr_patch.py      managed-block splice (the only delicate code)
└── tests/                  pytest throughout (see decision 7)
```

The hook is a sequence of independent **adapters**. Each is guarded by
`command -v`; a missing tool makes its adapter a silent no-op. One adapter
failing must not prevent the others from running.

## Adapters

Every row verified against the tool's own documentation (context7) or its binary,
2026-09-03. Tool versions: lazygit 0.64.1, fzf 0.74.3, herdr 0.8.2, omarchy 4.0.2-1.

| Tool | Generated file | Kind | Wiring | Reload |
|---|---|---|---|---|
| `herdr` | `herdr.theme.toml` | spliced | managed block in `config.toml` | `herdr server reload-config` |
| `starship` | `starship.toml` | owning | symlink `~/.config/starship.toml` | next prompt |
| `lazygit` | `lazygit.theme.yml` | layered | `LG_CONFIG_FILE` list, theme file last | on terminal focus |
| `bat` | `Omarchy.tmTheme` | owning | copy to `~/.config/bat/themes/` | `bat cache --build` |
| `fzf` | `fzf.opts` | layered | `FZF_DEFAULT_OPTS_FILE` | next invocation |
| `eza` | `eza.colors` | **template only — no adapter** | `EZA_COLORS`, converted by `install.sh` | next shell |
| `lazydocker` | `lazydocker.theme.yml` | owning | symlink | next launch |
| `tmux` | `tmux.theme.conf` | layered | `source-file` line | `tmux source-file` |
| `delta` | `delta.gitconfig` | layered | `[include]` in `~/.config/git/config` | immediate |

`delta` is **v1.1**: it is in the user's dev-boost `cli` profile but is not
installed on this machine (neither `delta` nor `git-delta`), so its adapter
cannot be tested end-to-end. Every other row is installed and testable today.

### Verified per-tool details

**starship** supports named palettes — `palette = 'omarchy'` plus a
`[palettes.omarchy]` table. The template therefore carries the user's existing
prompt *structure* verbatim and varies only the palette block, rather than
inlining colours throughout. Note Omarchy's stock `starship.toml` hardcodes
`cyan` in six places; those become palette references.

**lazygit** reads `LG_CONFIG_FILE` (confirmed present in the 0.64.1 binary) as a
comma-separated list, equivalent to `--use-config-file`. The generated theme goes
**last** so it wins. Theme keys are `gui.theme.*`:
`activeBorderColor`, `inactiveBorderColor`, `searchingActiveBorderColor`,
`optionsTextColor`, `selectedLineBgColor`, `inactiveViewSelectedLineBgColor`,
`cherryPickedCommitFgColor`, `cherryPickedCommitBgColor`,
`markedBaseCommitFgColor`, `markedBaseCommitBgColor`, `unstagedChangesColor`,
`defaultFgColor` — each a list of strings, and `#rrggbb` hex is explicitly
validated. lazygit reloads changed config files **on terminal focus**, so no
restart is needed.

**bat** derives the theme *name from the filename*, so the generated file must be
`Omarchy.tmTheme` and never renamed. It requires `bat cache --build` after every
write, and one-time wiring of `~/.config/bat/config` containing
`--theme="Omarchy"`.

**fzf** accepts truecolor hex in `--color`. `FZF_DEFAULT_OPTS_FILE` has the
**lowest** precedence of the three option layers (file < `FZF_DEFAULT_OPTS` <
CLI args), which is exactly right: the theme is a base the user can always
override.

**eza** takes `EZA_COLORS` as colon-separated `code=ansi` pairs using **ANSI
escape codes**, not hex — truecolor is `38;2;R;G;B`. Omarchy's `{{ key_rgb }}`
expands to comma-separated `R,G,B`, so the template cannot emit this directly.
The comma-to-semicolon conversion happens **in `install.sh`**, in the shell
snippet it writes for `EZA_COLORS`, not in the hook — see decision 5: eza gets
a template but no adapter. Converting where the value is consumed keeps
Omarchy's state directory read-only and means a shell opened before the first
theme change already gets the right value. This is the only post-processing
step in the project and must be confined to `eza.colors`.

## Decisions

Settled 2026-09-03 after verification. Recorded so they are not silently revisited.

1. **herdr token mapping.** Direct where an equivalent exists — `mauve`←`magenta`,
   `peach`←`orange`, `teal`←`cyan`, `text`←`foreground`, `subtext0`←`muted`,
   `accent`←`accent`. The four-level elevation ramp Omarchy does not express is
   *derived* with the template's own mix function:
   `surface_dim` `{{ mix background foreground 6% }}`, `surface0` 10%,
   `surface1` 16%, `overlay0` 24%, `overlay1` 32% — the same technique Omarchy's
   `shell.toml.tpl` uses for its own surfaces.
2. **Light/dark.** Templates branch on `{{ theme_type }}` where the format needs
   it, and herdr's `theme.name` picks a light or dark built-in accordingly.
   herdr's `theme.auto_switch` is deliberately **not** used: it follows the host
   terminal's appearance, a second source of truth that can disagree with
   Omarchy. `colors.toml` is the only authority.
3. **One-time wiring belongs to `install.sh`.** The env vars, the git `[include]`,
   the tmux `source-file` line and bat's `--theme` all point at stable paths and
   never change. The hook only regenerates *contents* and reloads, so it stays
   fast and cannot append duplicates.
4. **`uninstall.sh` is a first-class requirement**, not a nicety, and is covered
   by a test asserting install→uninstall returns the machine to a byte-identical
   state, with one accepted exception: herdr's `[ui] accent` (resolved — see below). `splice()`
   overwrites that key in place with no record of its prior value, so nothing
   can restore it. Documented in the README; not a bug to be fixed. Two
   non-content residues are also accepted: directories left empty after their
   files are removed, and bat's rebuilt cache (a derived artifact).
5. **Scope: eight templates, seven adapters, one deferred.** eza gets a
   template but **no adapter** — its conversion happens in `install.sh` where the
   value is consumed, so the hook never touches it (see decision 3). `delta` is
   deferred to v1.1: it is declared in the dev-boost `cli` profile but is not
   installed on this machine, so its adapter cannot be tested end to end.
6. **Public, MIT.** The project is theme-agnostic and carries no personal data —
   no palette, no signature, no identity — so it is publishable and is the
   natural precursor to an upstream Omarchy PR.
7. **Testing is `uvx pytest` only.** `bats` is not installed and will not be
   added; the hook is exercised from pytest via `subprocess`, invoking it exactly
   as Omarchy does (`bash <hook> <slug>`) against a temporary `HOME`.
8. **Headless mode is accepted, not worked around.** Hooks do not run under
   `OMARCHY_THEME_HEADLESS=1`/`OMARCHY_THEME_OFFLINE=1`; the hook takes a
   `--sync` flag for manual re-runs and `install.sh` notes it. Adding a second
   trigger would be over-engineering.

## Error handling

- Missing tool → adapter skips silently.
- Missing generated file (template not linked) → adapter skips with a warning.
- Splice cannot find or safely parse its target → **refuse, leave file
  untouched, warn**. Never a partial write.
- Owning adapter finds an unrecognised existing config → refuse and warn.
  Concretely: a destination that is already a symlink pointing anywhere other
  than the generated theme file is unrecognised (a dotfiles manager owns it).
  It is never replaced, because doing so would leave no backup and no record of
  its target. The warning is not verbose-gated.
- `uninstall.sh` removes a symlink only when it can prove ownership — the link
  points into the theme dir, or a `*.pre-omarchy-theme` backup sits beside it.
- Every block removal writes **through** a symlink (the resolved target is
  edited), never renames a temp file over it, so a dotfiles-managed config
  stays a symlink and its source keeps the edit.
- The hook always exits 0. A theme change must never fail because a dev tool
  could not be themed.

## Testing

`lib/herdr_patch.py` is written test-first. Cases:

1. Config with no markers → block added, keybindings byte-identical.
2. Run twice → second run is a no-op (idempotent).
3. Existing `[theme]`/`[theme.custom]` sections → replaced, not duplicated.
4. `[ui]` with `accent` among other keys → only `accent` changes.
5. `[ui]` without `accent` → key added inside that section.
6. Comments and blank lines outside the block → preserved exactly.
7. Malformed/truncated markers → refuses, file unchanged, non-zero from the lib.

The hook gets pytest coverage (via `subprocess`, per decision 7) for adapter
skipping, the exit-0 guarantee, the refusal to replace an unrecognised config,
and the install/uninstall round trip.

Verification for the whole project is a real theme switch: apply Eltahir, then
Catppuccin, and confirm each tool's colours follow both ways.

## Decided: shell env wiring

`fzf` and `eza` are wired by environment variables, which need a line in the
user's shell rc. `install.sh` **prints** the snippet rather than appending it to
`~/.bashrc`: that file is outside this project's ownership, and a theme project
silently editing a login shell's rc is a bad trade for two exports.

`install.sh` writes the exports to `~/.config/omarchy/themed-devtools.env` and
prints the single `source` line to add.


## Addendum — the herdr accent round-trip is resolved (2026-09-04)

The design originally accepted that herdr's `[ui] accent` could not round-trip:
`splice()` replaced that key in place, outside the managed block, with no record
of the prior value, so uninstall had nothing to restore.

That is fixed. `splice()` now writes `# omarchy-theme:prior-ui-accent = <value>`
inside the managed block and `uninstall.sh` reads it back before stripping the
block. The subtlety is the re-splice: the block is dropped before it is rebuilt,
so the recorded value is **carried forward** rather than re-captured — otherwise
after one theme change the record would describe the colour this project itself
wrote. Verified across three consecutive splices and by a full
install → hook → uninstall cycle.


## Addendum — delta is no longer deferred (2026-09-05)

delta was deferred on the grounds that it is not installed on the development
machine and so could not be tested end to end. That reasoning was wrong: every
other adapter is tested with a fake tool on `PATH`, and delta needs nothing
more. It is now a first-class adapter with a template, a layered `[include]`,
and the same tests the others get.

The template validation earned its place immediately — the first draft
referenced `{{ line }}`, which is a token from the *theme's* `palette.toml`, not
a key Omarchy's `colors.toml` resolves. It would have rendered literally into a
git config. Replaced with `{{ mix background foreground 20% }}`.

**Eight templates, eight adapters, none deferred.** Installing `git-delta`
activates it; until then its `command -v` guard skips it, like any absent tool.
