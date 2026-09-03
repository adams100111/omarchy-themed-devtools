#!/usr/bin/env bash
# Exact reversal of install.sh. Restores every *.pre-omarchy-theme backup,
# removes the managed block from herdr's config, and deletes the marker-wrapped
# lines this project added. Safe to run when nothing is installed.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
THEMED="$HOME/.config/omarchy/themed"
HOOKS="$HOME/.config/omarchy/hooks/theme-set.d"
ENV_FILE="$HOME/.config/omarchy/themed-devtools.env"

# One removal mechanism for the whole project: everything this script adds to a
# user-owned file is wrapped in these markers, and uninstall deletes between
# them. Counting lines instead would over-delete whenever an addition is not
# exactly the length the remover assumed.
MARK_START="# >>> omarchy-theme >>>"
MARK_END="# <<< omarchy-theme <<<"

for tpl in "$REPO"/templates/*.tpl; do
  rm -f "$THEMED/$(basename "$tpl")"
done
rm -f "$HOOKS/apply-devtools-theme" "$ENV_FILE"

# Restore anything link_owned replaced; drop symlinks it left behind.
for dest in "$HOME/.config/starship.toml" \
            "$HOME/.config/lazydocker/config.yml"; do
  if [[ -L $dest ]]; then
    rm -f "$dest"
  fi
  if [[ -e "$dest.pre-omarchy-theme" ]]; then
    mv -f "$dest.pre-omarchy-theme" "$dest"
    echo "  restored $dest"
  fi
done

rm -f "$HOME/.config/bat/themes/Omarchy.tmTheme"
command -v bat >/dev/null 2>&1 && bat cache --build >/dev/null 2>&1 || true

# strip_block <file> [--remove-if-empty]
#
# Delete everything between our markers, leaving every other byte alone. This is
# the ONLY removal mechanism in the project -- it works for a one-line addition
# and a ten-line one alike. An earlier draft counted a fixed number of lines
# after a tag and deleted a user's `set -g mouse on` along with our own.
strip_block() {
  local file="$1" remove_if_empty="${2:-}"
  [[ -f $file ]] || return 0
  awk -v mark_start="$MARK_START" -v mark_end="$MARK_END" '
    $0 == mark_start { inblock = 1; next }
    $0 == mark_end { inblock = 0; next }
    !inblock { print }
  ' "$file" >"$file.tmp" && mv "$file.tmp" "$file"
  # Only files this project may have created (gitconfig, tmux.conf, bat's
  # config) are removed when emptied; never herdr's config.toml, which the
  # user owns outright and merely contains a block of ours.
  [[ $remove_if_empty == "--remove-if-empty" && ! -s $file ]] && rm -f "$file"
  return 0
}

strip_block "$HOME/.config/git/config" --remove-if-empty
strip_block "$HOME/.config/tmux/tmux.conf" --remove-if-empty
strip_block "$HOME/.config/bat/config" --remove-if-empty
strip_block "$HOME/.config/herdr/config.toml"
echo "  removed managed blocks"

rmdir "$THEMED" "$HOOKS" 2>/dev/null || true

echo
echo "Uninstalled. Remove this line from your shell rc if you added it:"
echo "  source $ENV_FILE"
