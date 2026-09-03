# CONTEXT

Glossary for omarchy-themed-devtools. Terms only — no implementation details, no
decisions. Decisions live in `docs/superpowers/specs/`.

## Template

A `*.tpl` file in `~/.config/omarchy/themed/`. Omarchy's
`omarchy-theme-set-templates` globs that directory on every theme change and
renders each file against the **palette**, writing the result — named by
stripping `.tpl` — into the **staging directory**.

Templates are **not** limited to overriding Omarchy's built-ins. A template with
a new filename produces a new generated file. That is the mechanism this project
is built on.

## Palette

The set of colour keys a template may reference. **Not** the same as the theme's
`colors.toml`: Omarchy resolves that file into a larger set via
`omarchy-theme-color --all`, adding derived and alias keys the raw file never
contains — `color0`–`color15`, `bg`/`fg`, `purple`, `selection_foreground`,
`theme_type`. When this project says *palette* it means the resolved set.

## Staging directory

`~/.local/state/omarchy/current/next-theme/`. Where a theme change is assembled:
theme files are copied in, then every template renders into it. **Templates
write here, never to the live theme.**

## Live theme directory

`~/.local/state/omarchy/current/theme/`. The theme currently in effect, and the
path every adapter reads its generated file from.

These two are distinct and the distinction is load-bearing: an adapter that
reads the live theme directory before the staging directory has been promoted
would wire up the *previous* theme's colours. Whether the `theme-set.d` hook
runs before or after promotion therefore decides whether this project works at
all.

## Adapter

The pairing of one template with the wiring that gets its output to the tool
that reads it. Every adapter is independent and individually skippable: if the
tool is not installed, its adapter is a no-op.

An adapter is **layered** when the tool can read theme colors alongside the
user's own config (`fzf` via `FZF_DEFAULT_OPTS_FILE`, `delta` via git
`[include]`, `tmux` via `source-file`), and **owning** when the template
produces the tool's whole config file (`starship`, `lazygit`).

## Managed block

A region of a user-owned config file delimited by
`# >>> omarchy-theme >>>` / `# <<< omarchy-theme <<<` markers, whose contents
this project rewrites and whose surroundings it must never touch. Used only
where a tool mixes theme with non-theme settings in one file and offers no
include mechanism — currently `herdr` alone.

## Splice

The operation that replaces a managed block's contents in place. A splice is
**idempotent** (running twice changes nothing the second time) and
**non-destructive** (every byte outside the markers survives). A splice that
cannot guarantee both refuses and leaves the file untouched.

## Hook

An executable in `~/.config/omarchy/hooks/theme-set.d/`, run by Omarchy after a
theme change with the theme slug as `$1`. This project installs exactly one.
