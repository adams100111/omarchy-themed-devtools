#!/usr/bin/env bash
# Install omarchy-themed-devtools: link the templates and the hook, then do all
# the one-time wiring. The hook never touches any of this -- keeping mutation of
# user-owned files here means uninstall is a single, auditable reversal.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
THEMED="$HOME/.config/omarchy/themed"
HOOKS="$HOME/.config/omarchy/hooks/theme-set.d"
THEME_DIR="$HOME/.local/state/omarchy/current/theme"
ENV_FILE="$HOME/.config/omarchy/themed-devtools.env"

# One removal mechanism for the whole project: everything this script adds to a
# user-owned file is wrapped in these markers, and uninstall deletes between
# them. Counting lines instead would over-delete whenever an addition is not
# exactly the length the remover assumed.
MARK_START="# >>> omarchy-theme >>>"
MARK_END="# <<< omarchy-theme <<<"

mkdir -p "$THEMED" "$HOOKS" "$(dirname "$ENV_FILE")"

for tpl in "$REPO"/templates/*.tpl; do
  ln -sfn "$tpl" "$THEMED/$(basename "$tpl")"
  echo "  linked $(basename "$tpl")"
done

ln -sfn "$REPO/hooks/apply-devtools-theme" "$HOOKS/apply-devtools-theme"
echo "  linked hook"

# append_block <file> <body> -- add a marker-wrapped block exactly once.
# Creates the file if absent. Idempotent: a file already carrying our start
# marker is left alone, so re-running install never duplicates anything.
append_block() {
  local file="$1" body="$2"
  mkdir -p "$(dirname "$file")"
  touch "$file"
  grep -qF "$MARK_START" "$file" && return 0
  printf '%s\n%s\n%s\n' "$MARK_START" "$body" "$MARK_END" >>"$file"
}

cat >"$ENV_FILE" <<EOF
# omarchy-themed-devtools -- source this from your shell rc
export FZF_DEFAULT_OPTS_FILE="$THEME_DIR/fzf.opts"
export LG_CONFIG_FILE="\$HOME/.config/lazygit/config.yml,$THEME_DIR/lazygit.theme.yml"
# eza wants ANSI codes with semicolons; Omarchy's {{ key_rgb }} renders commas.
# Converting here rather than in the hook keeps Omarchy's state dir read-only
# and means a shell opened before the first theme change still gets it right.
[ -r "$THEME_DIR/eza.colors" ] && export EZA_COLORS="\$(tr ',' ';' < "$THEME_DIR/eza.colors")"
true
EOF
echo "  wrote $ENV_FILE"

command -v delta >/dev/null 2>&1 &&
  append_block "$HOME/.config/git/config" "[include]
	path = $THEME_DIR/delta.gitconfig"

command -v tmux >/dev/null 2>&1 &&
  append_block "$HOME/.config/tmux/tmux.conf" "source-file -q $THEME_DIR/tmux.theme.conf"

# bat selects a theme by NAME, which it derives from the theme filename.
command -v bat >/dev/null 2>&1 &&
  append_block "$HOME/.config/bat/config" '--theme="Omarchy"'

cat <<EOF

Installed. Add this one line to your shell rc (~/.bashrc), then open a new shell:

  source $ENV_FILE

Then apply any theme to populate everything:

  omarchy theme set "\$(omarchy theme current)"

Note: hooks do not run when OMARCHY_THEME_HEADLESS=1 or OMARCHY_THEME_OFFLINE=1.
Re-run by hand with: bash $HOOKS/apply-devtools-theme --sync
EOF
