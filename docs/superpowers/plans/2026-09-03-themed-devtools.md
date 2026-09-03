# omarchy-themed-devtools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend Omarchy's theming engine so it themes the command-line tools a developer works inside — for every Omarchy theme, not just one.

**Architecture:** Templates in `~/.config/omarchy/themed/*.tpl` are rendered by Omarchy against the active palette on every theme change. A single `theme-set.d` hook then wires each generated file to where its tool reads it and reloads that tool. Each tool is an independent, individually-skippable *adapter*. No Omarchy file is patched or forked.

**Tech Stack:** Bash (hook, install/uninstall), Python 3.11+ stdlib (the herdr splice), `uvx pytest` for tests. No runtime dependencies.

**Spec:** `docs/superpowers/specs/2026-09-03-themed-devtools-design.md` — read it before Task 1.

## Global Constraints

- **No Claude/Anthropic attribution** in any commit message or PR. See `~/.claude/CLAUDE.md`.
- **Never edit `/usr/share/omarchy/`.** Reading it is safe and encouraged.
- **Always invoke the `omarchy` Claude skill** before touching anything under `~/.config/omarchy/`; read `theming.md` and `hooks.md` first.
- **Python: stdlib only.** `tomlkit` is not installed and must not be added. `tomllib` is read-only and cannot round-trip comments — the splice is deliberately line-based.
- **Tests run as `uvx pytest`.** `bats` is not installed and must not be added.
- **Every adapter is guarded by `command -v`** and is a silent no-op when its tool is absent.
- **The hook must never write outside** `~/.config/<tool>/` paths named in the spec, and must never append to a file it has already appended to.
- **Verified environment:** omarchy 4.0.2-1, herdr 0.8.2, lazygit 0.64.1, fzf 0.74.3, uv 0.12.9, pytest 9.1.1.
- **`delta` is out of scope for v1** — not installed on the target machine.
- Generated-file names must be ones no Omarchy theme ships, or the template is silently ignored (precedence: theme-shipped > user `.tpl` > built-in `.tpl`).

---

## File Structure

| Path | Responsibility |
|---|---|
| `lib/herdr_patch.py` | The managed-block splice. The only delicate logic; pure functions, no I/O in the core. |
| `hooks/apply-devtools-theme` | The single `theme-set.d` hook. One bash function per adapter. |
| `templates/*.tpl` | One per tool. Pure colour, no logic. |
| `install.sh` | Links templates + hook; performs all one-time wiring; prints the shell snippet. |
| `uninstall.sh` | Exact reversal of `install.sh`, including restoring backups. |
| `tests/test_herdr_patch.py` | Unit tests for the splice. |
| `tests/test_hook.py` | Drives the hook via `subprocess` against a temp `HOME`. |
| `tests/conftest.py` | Fixtures: temp `HOME`, a fake live-theme dir, a realistic herdr config. |
| `pyproject.toml` | pytest config only. Not a package. |
| `README.md` | What it is, how to install, what each adapter does. |

---

### Task 1: The herdr splice

The most delicate code in the project. herdr's `config.toml` mixes theme with ~90 lines of commented keybindings and has no include mechanism, so we rewrite two owned sections and one key while leaving every other byte identical.

Two separate operations, because TOML forbids duplicate section headers:
1. A **managed block** owning `[theme]` and `[theme.custom]`, appended at the end.
2. An **in-place replacement** of `accent` inside the existing `[ui]` section.

**Files:**
- Create: `lib/herdr_patch.py`
- Create: `tests/test_herdr_patch.py`
- Create: `tests/conftest.py`
- Create: `pyproject.toml`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `splice(config_text: str, theme_block: str, ui_accent: str) -> str`
  - `SpliceError(Exception)`
  - `MARK_START: str`, `MARK_END: str`

- [ ] **Step 1: Create the pytest harness**

`pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

`tests/conftest.py`:

```python
import pytest

HERDR_CONFIG = '''onboarding = false
# Mirrors the Omarchy tmux config
# tmux session -> herdr workspace

[theme]
# tmux ran on the terminal's own palette
name = "terminal"

auto_switch = false
[theme.custom]
panel_bg = "black"

[terminal]
new_cwd = "follow"

[keys]
prefix = "ctrl+space"
reload_config = "prefix+q"

[ui]
accent = "blue"

# tmux drew single-line dividers
pane_gaps = false
mouse_capture = true
'''


@pytest.fixture
def herdr_config() -> str:
    return HERDR_CONFIG


@pytest.fixture
def theme_block() -> str:
    return '[theme]\nname = "terminal"\n\n[theme.custom]\naccent = "#c2a15a"\n'
```

- [ ] **Step 2: Write the failing tests**

`tests/test_herdr_patch.py`:

```python
import pytest

from lib.herdr_patch import MARK_END, MARK_START, SpliceError, splice


def test_adds_block_when_none_present(herdr_config, theme_block):
    out = splice(herdr_config, theme_block, "#c2a15a")
    assert MARK_START in out and MARK_END in out
    assert '[theme.custom]\naccent = "#c2a15a"' in out


def test_keybindings_preserved(herdr_config, theme_block):
    out = splice(herdr_config, theme_block, "#c2a15a")
    for line in ['prefix = "ctrl+space"', 'reload_config = "prefix+q"',
                 "# tmux drew single-line dividers", "pane_gaps = false"]:
        assert line in out


def test_idempotent(herdr_config, theme_block):
    once = splice(herdr_config, theme_block, "#c2a15a")
    twice = splice(once, theme_block, "#c2a15a")
    assert once == twice


def test_old_theme_sections_removed_not_duplicated(herdr_config, theme_block):
    out = splice(herdr_config, theme_block, "#c2a15a")
    assert out.count("[theme]") == 1
    assert out.count("[theme.custom]") == 1
    assert 'panel_bg = "black"' not in out
    assert "auto_switch = false" not in out


def test_ui_accent_replaced_other_ui_keys_kept(herdr_config, theme_block):
    out = splice(herdr_config, theme_block, "#c2a15a")
    assert 'accent = "blue"' not in out
    assert 'accent = "#c2a15a"' in out
    assert "mouse_capture = true" in out
    assert out.count("[ui]") == 1


def test_ui_accent_inserted_when_absent(theme_block):
    cfg = 'onboarding = false\n\n[ui]\nmouse_capture = true\n'
    out = splice(cfg, theme_block, "#c2a15a")
    ui = out.split("[ui]")[1]
    assert 'accent = "#c2a15a"' in ui
    assert "mouse_capture = true" in ui


def test_ui_section_created_when_absent(theme_block):
    out = splice('onboarding = false\n', theme_block, "#c2a15a")
    assert "[ui]" in out
    assert 'accent = "#c2a15a"' in out


def test_unterminated_marker_refuses(herdr_config, theme_block):
    broken = herdr_config + "\n" + MARK_START + "\n[theme]\n"
    with pytest.raises(SpliceError):
        splice(broken, theme_block, "#c2a15a")
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uvx pytest tests/test_herdr_patch.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'lib.herdr_patch'`

- [ ] **Step 4: Implement the splice**

`lib/__init__.py`: empty file.

`lib/herdr_patch.py`:

```python
"""Splice Omarchy theme colours into herdr's config.toml.

herdr mixes theme settings with the user's keybindings in one file and offers
no include mechanism, so we rewrite only what we own and leave every other byte
alone. tomlkit is not available and tomllib cannot round-trip comments, so this
is deliberately line-based rather than a parse-and-serialise.
"""

from __future__ import annotations

import re

MARK_START = "# >>> omarchy-theme >>>"
MARK_END = "# <<< omarchy-theme <<<"

# Any line that opens a new TOML table, e.g. "[ui]" or "[theme.custom]".
_SECTION = re.compile(r"^[ \t]*\[")
_ACCENT = re.compile(r"^[ \t]*accent[ \t]*=")


class SpliceError(Exception):
    """The target file is not in a shape we can safely rewrite."""


def _header(name: str) -> re.Pattern[str]:
    return re.compile(r"^[ \t]*\[" + re.escape(name) + r"\][ \t]*(#.*)?$")


def _drop_managed_block(lines: list[str]) -> list[str]:
    starts = [i for i, l in enumerate(lines) if l.strip() == MARK_START]
    ends = [i for i, l in enumerate(lines) if l.strip() == MARK_END]
    if not starts and not ends:
        return lines
    if len(starts) != 1 or len(ends) != 1 or ends[0] < starts[0]:
        raise SpliceError("managed block markers are missing or malformed")
    return lines[: starts[0]] + lines[ends[0] + 1 :]


def _drop_section(lines: list[str], name: str) -> list[str]:
    head = _header(name)
    out: list[str] = []
    i = 0
    while i < len(lines):
        if head.match(lines[i]):
            i += 1
            while i < len(lines) and not _SECTION.match(lines[i]):
                i += 1
            continue
        out.append(lines[i])
        i += 1
    return out


def _set_ui_accent(lines: list[str], value: str) -> list[str]:
    """Replace `accent` inside [ui], or insert it, or create [ui] entirely."""
    head = _header("ui")
    for i, line in enumerate(lines):
        if not head.match(line):
            continue
        j = i + 1
        while j < len(lines) and not _SECTION.match(lines[j]):
            if _ACCENT.match(lines[j]):
                lines[j] = f'accent = "{value}"'
                return lines
            j += 1
        return lines[: i + 1] + [f'accent = "{value}"'] + lines[i + 1 :]
    return lines + ["", "[ui]", f'accent = "{value}"']


def splice(config_text: str, theme_block: str, ui_accent: str) -> str:
    """Return config_text with our theme sections and [ui].accent replaced.

    Everything outside the managed block and the single accent key — comments,
    blank lines, keybindings — is preserved exactly.
    """
    if not theme_block.strip():
        raise SpliceError("refusing to splice an empty theme block")

    lines = config_text.splitlines()
    lines = _drop_managed_block(lines)
    lines = _drop_section(lines, "theme.custom")
    lines = _drop_section(lines, "theme")
    lines = _set_ui_accent(lines, ui_accent)

    while lines and not lines[-1].strip():
        lines.pop()

    block = [
        "",
        MARK_START,
        "# Generated by omarchy-themed-devtools. Do not edit inside the markers.",
        *theme_block.rstrip("\n").splitlines(),
        MARK_END,
    ]
    return "\n".join(lines + block) + "\n"
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uvx pytest tests/test_herdr_patch.py -v`
Expected: 8 passed

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml lib/ tests/
git commit -m "feat: managed-block splice for herdr config

herdr mixes theme with keybindings in one file and has no include mechanism,
so the splice rewrites [theme] and [theme.custom] plus the single accent key
inside [ui], leaving every other byte identical. Line-based rather than a TOML
round-trip because tomlkit is unavailable and tomllib cannot preserve comments."
```

---

### Task 2: Hook skeleton and adapter framework

The hook Omarchy runs after every theme change. It must survive missing tools, missing generated files, and a missing live theme directory without ever failing loudly.

**Files:**
- Create: `hooks/apply-devtools-theme`
- Create: `tests/test_hook.py`
- Modify: `tests/conftest.py` (add the temp-HOME fixture)

**Interfaces:**
- Consumes: `lib/herdr_patch.py` (used in Task 3).
- Produces: hook contract — invoked as `bash hooks/apply-devtools-theme [theme-slug] [--sync]`; honours `$HOME`; reads generated files from `$HOME/.local/state/omarchy/current/theme/`; always exits 0.

- [ ] **Step 1: Add the temp-HOME fixture**

Append to `tests/conftest.py`:

```python
import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def fake_home(tmp_path) -> Path:
    """A HOME with an Omarchy live-theme directory and no dev tools on PATH."""
    theme = tmp_path / ".local/state/omarchy/current/theme"
    theme.mkdir(parents=True)
    (tmp_path / ".config").mkdir()
    return tmp_path


def run_hook(home: Path, *args: str, path: str = "") -> subprocess.CompletedProcess:
    """Invoke the hook the way omarchy-hook does: through the INSTALLED symlink.

    Invoking the repo copy directly would hide any bug in how the hook locates
    files relative to itself — which is exactly the shape the real install has.
    """
    hookdir = home / ".config/omarchy/hooks/theme-set.d"
    hookdir.mkdir(parents=True, exist_ok=True)
    link = hookdir / "apply-devtools-theme"
    if not link.exists():
        link.symlink_to(REPO / "hooks/apply-devtools-theme")

    env = dict(os.environ, HOME=str(home), PATH=path)
    return subprocess.run(
        ["bash", str(link), *args], capture_output=True, text=True, env=env,
    )
```

- [ ] **Step 2: Write the failing tests**

`tests/test_hook.py`:

```python
from conftest import run_hook


def test_exits_zero_with_no_tools_installed(fake_home):
    assert run_hook(fake_home, "eltahir").returncode == 0


def test_exits_zero_when_theme_dir_missing(tmp_path):
    assert run_hook(tmp_path, "eltahir").returncode == 0


def test_reports_skipped_adapters_in_verbose_mode(fake_home):
    result = run_hook(fake_home, "eltahir", "--verbose")
    assert "starship" in result.stdout
    assert "skip" in result.stdout.lower()


def test_accepts_sync_flag(fake_home):
    assert run_hook(fake_home, "--sync").returncode == 0
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uvx pytest tests/test_hook.py -v`
Expected: FAIL — hook file does not exist

- [ ] **Step 4: Implement the hook skeleton**

`hooks/apply-devtools-theme`:

```bash
#!/usr/bin/env bash
# Wire Omarchy's generated theme files into dev tools that Omarchy does not
# theme itself. Installed into ~/.config/omarchy/hooks/theme-set.d/.
#
# omarchy-hook runs this as: bash <hook> <theme-slug>
#
# Every adapter is independent and guarded: a missing tool or a missing
# generated file skips that adapter only. The hook always exits 0 — a theme
# change must never fail because a dev tool could not be themed.

THEME_DIR="$HOME/.local/state/omarchy/current/theme"
VERBOSE=0

for arg in "$@"; do
  case "$arg" in
    --verbose) VERBOSE=1 ;;
    --sync) ;;   # accepted; the hook does the same work either way
  esac
done

log() { [[ $VERBOSE == 1 ]] && echo "$*"; return 0; }

# Usable <tool> <generated-file> — true when both the tool and its input exist.
usable() {
  if ! command -v "$1" >/dev/null 2>&1; then
    log "  skip $1: not installed"
    return 1
  fi
  if [[ ! -f "$THEME_DIR/$2" ]]; then
    log "  skip $1: $2 not generated"
    return 1
  fi
  return 0
}

adapter_starship() { usable starship starship.toml || return 0; }
adapter_lazygit()  { usable lazygit lazygit.theme.yml || return 0; }
adapter_bat()      { usable bat Omarchy.tmTheme || return 0; }
adapter_fzf()      { usable fzf fzf.opts || return 0; }
adapter_herdr()    { usable herdr herdr.theme.toml || return 0; }
adapter_lazydocker() { usable lazydocker lazydocker.theme.yml || return 0; }
adapter_tmux()     { usable tmux tmux.theme.conf || return 0; }

main() {
  log "omarchy-themed-devtools: applying theme '${1:-unknown}'"
  # eza has no adapter: its value is converted where it is consumed,
  # in the env file install.sh writes. See README.
  for adapter in starship lazygit bat fzf herdr lazydocker tmux; do
    "adapter_$adapter" || log "  warn $adapter: adapter returned non-zero"
  done
  return 0
}

main "$@"
exit 0
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uvx pytest tests/test_hook.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add hooks/apply-devtools-theme tests/
git commit -m "feat: theme-set hook skeleton with guarded adapters

Each adapter is independent and skips silently when its tool is absent or its
generated file is missing. The hook always exits 0; omarchy-hook swallows exit
status anyway, but a theme change must not appear to fail."
```

---

### Task 3: herdr adapter and template

The highest-value adapter: herdr frames every other surface, and currently runs a blue accent against a gold desktop.

`theme.name = "terminal"` is deliberate. herdr's built-in theme names are not documented, and `terminal` makes the base inherit the terminal's own palette — which Omarchy already themes — so any token we do not override is correct by construction, in light and dark alike.

**Files:**
- Create: `templates/herdr.theme.toml.tpl`
- Modify: `hooks/apply-devtools-theme` (replace `adapter_herdr`)
- Modify: `tests/test_hook.py` (append)

**Interfaces:**
- Consumes: `lib.herdr_patch.splice` from Task 1; the hook contract from Task 2.
- Produces: `$THEME_DIR/herdr.theme.toml`, spliced into `~/.config/herdr/config.toml`.

- [ ] **Step 1: Write the template**

`templates/herdr.theme.toml.tpl`:

```toml
[theme]
name = "terminal"
auto_switch = false

[theme.custom]
accent = "{{ accent }}"
panel_bg = "{{ dark_background }}"
sidebar_bg = "{{ dark_background }}"
active_row_bg = "{{ selection }}"
selection_bg = "{{ selection }}"
surface_dim = "{{ mix background foreground 6% }}"
surface0 = "{{ mix background foreground 10% }}"
surface1 = "{{ mix background foreground 16% }}"
overlay0 = "{{ mix background foreground 24% }}"
overlay1 = "{{ mix background foreground 32% }}"
text = "{{ foreground }}"
subtext0 = "{{ muted }}"
mauve = "{{ magenta }}"
green = "{{ green }}"
yellow = "{{ yellow }}"
red = "{{ red }}"
blue = "{{ blue }}"
teal = "{{ cyan }}"
peach = "{{ orange }}"
```

- [ ] **Step 2: Write the failing test**

Append to `tests/test_hook.py`:

```python
import shutil
from pathlib import Path

from conftest import REPO, run_hook

HERDR_STUB = '#!/usr/bin/env bash\nexit 0\n'


def _fake_tool(home: Path, name: str) -> str:
    """Put a no-op executable named `name` on a PATH the hook will see."""
    bindir = home / "bin"
    bindir.mkdir(exist_ok=True)
    tool = bindir / name
    tool.write_text(HERDR_STUB)
    tool.chmod(0o755)
    return f"{bindir}:/usr/bin:/bin"


def test_herdr_adapter_splices_config(fake_home):
    path = _fake_tool(fake_home, "herdr")
    theme = fake_home / ".local/state/omarchy/current/theme"
    (theme / "herdr.theme.toml").write_text(
        '[theme]\nname = "terminal"\n\n[theme.custom]\naccent = "#c2a15a"\n')

    cfg_dir = fake_home / ".config/herdr"
    cfg_dir.mkdir(parents=True)
    cfg = cfg_dir / "config.toml"
    cfg.write_text('onboarding = false\n\n[keys]\nprefix = "ctrl+space"\n\n'
                   '[ui]\naccent = "blue"\nmouse_capture = true\n')

    assert run_hook(fake_home, "eltahir", path=path).returncode == 0
    out = cfg.read_text()
    assert 'prefix = "ctrl+space"' in out          # keybindings survive
    assert 'accent = "blue"' not in out            # ui accent replaced
    assert 'accent = "#c2a15a"' in out
    assert "mouse_capture = true" in out


def test_herdr_adapter_is_idempotent(fake_home):
    path = _fake_tool(fake_home, "herdr")
    theme = fake_home / ".local/state/omarchy/current/theme"
    (theme / "herdr.theme.toml").write_text(
        '[theme]\nname = "terminal"\n\n[theme.custom]\naccent = "#c2a15a"\n')
    cfg_dir = fake_home / ".config/herdr"
    cfg_dir.mkdir(parents=True)
    cfg = cfg_dir / "config.toml"
    cfg.write_text('[ui]\naccent = "blue"\n')

    run_hook(fake_home, "eltahir", path=path)
    first = cfg.read_text()
    run_hook(fake_home, "eltahir", path=path)
    assert cfg.read_text() == first


def test_herdr_adapter_skips_when_no_config(fake_home):
    path = _fake_tool(fake_home, "herdr")
    theme = fake_home / ".local/state/omarchy/current/theme"
    (theme / "herdr.theme.toml").write_text('[theme]\nname = "terminal"\n')
    assert run_hook(fake_home, "eltahir", path=path).returncode == 0
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uvx pytest tests/test_hook.py -v`
Expected: FAIL — `config.toml` is unchanged; `accent = "blue"` still present

- [ ] **Step 4: Implement the adapter**

Replace `adapter_herdr` in `hooks/apply-devtools-theme`:

```bash
adapter_herdr() {
  usable herdr herdr.theme.toml || return 0

  local cfg="$HOME/.config/herdr/config.toml"
  if [[ ! -f $cfg ]]; then
    log "  skip herdr: no config.toml"
    return 0
  fi

  # The accent herdr uses for [ui] is the same signal colour as the theme's.
  local accent
  accent=$(sed -n 's/^accent[[:space:]]*=[[:space:]]*"\(.*\)"/\1/p' \
    "$THEME_DIR/herdr.theme.toml" | head -1)
  [[ -n $accent ]] || accent="#000000"

  # The splice refuses rather than half-writing, so a failure leaves the
  # user's config untouched. Write via a temp file for the same reason.
  local tmp
  tmp=$(mktemp) || return 0
  if python3 - "$cfg" "$THEME_DIR/herdr.theme.toml" "$accent" >"$tmp" <<'PY'
import sys
sys.path.insert(0, __import__("os").environ["DEVTOOLS_LIB"])
from herdr_patch import splice

cfg, block, accent = sys.argv[1], sys.argv[2], sys.argv[3]
with open(cfg, encoding="utf-8") as f:
    text = f.read()
with open(block, encoding="utf-8") as f:
    theme = f.read()
sys.stdout.write(splice(text, theme, accent))
PY
  then
    mv "$tmp" "$cfg"
    log "  herdr: spliced"
    herdr server reload-config >/dev/null 2>&1 || true
  else
    rm -f "$tmp"
    log "  warn herdr: splice refused; config left untouched"
  fi
}
```

Add near the top of the hook, after `THEME_DIR`:

```bash
# The hook is SYMLINKED into ~/.config/omarchy/hooks/theme-set.d/, so
# ${BASH_SOURCE[0]} is the link, not the file. Resolve it before deriving the
# repo path -- otherwise lib/ is looked for next to the link and never found,
# and the herdr adapter silently does nothing once installed.
SELF="$(readlink -f "${BASH_SOURCE[0]}")"
DEVTOOLS_LIB="${DEVTOOLS_LIB:-$(cd "$(dirname "$SELF")/../lib" 2>/dev/null && pwd)}"
export DEVTOOLS_LIB
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uvx pytest -v`
Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add templates/herdr.theme.toml.tpl hooks/apply-devtools-theme tests/
git commit -m "feat: herdr adapter

herdr frames every other surface and shipped a blue accent against a gold
desktop. theme.name stays 'terminal' so untouched tokens inherit the terminal
palette Omarchy already themes, which makes light and dark correct without
guessing at herdr's built-in theme names. The elevation ramp Omarchy does not
express is derived with the template's own mix function."
```

---

### Task 4: starship adapter and template

Omarchy's stock `starship.toml` hardcodes `cyan` in six places, which is why the prompt is teal on a gold desktop. starship supports named palettes, so the template keeps the prompt *structure* verbatim and varies only the palette block.

**Files:**
- Create: `templates/starship.toml.tpl`
- Modify: `hooks/apply-devtools-theme` (replace `adapter_starship`)
- Modify: `tests/test_hook.py` (append)

**Interfaces:**
- Consumes: hook contract from Task 2.
- Produces: `$THEME_DIR/starship.toml`, symlinked to `~/.config/starship.toml`; backup at `~/.config/starship.toml.pre-omarchy-theme`.

- [ ] **Step 1: Write the template**

`templates/starship.toml.tpl`:

```toml
add_newline = true
command_timeout = 200
format = "[$directory$git_branch$git_status]($style)$character"
palette = "omarchy"

[palettes.omarchy]
signal = "{{ accent }}"
fg = "{{ foreground }}"
alert = "{{ red }}"

[character]
error_symbol = "[✗](bold alert)"
success_symbol = "[❯](bold signal)"

[directory]
truncation_length = 2
truncation_symbol = "…/"
repo_root_style = "bold signal"
repo_root_format = "[$repo_root]($repo_root_style)[$path]($style)[$read_only]($read_only_style) "

[git_branch]
format = "[$branch]($style) "
style = "italic signal"

[git_status]
format     = '[$all_status]($style)'
style      = "signal"
ahead      = "⇡${count} "
diverged   = "⇕⇡${ahead_count}⇣${behind_count} "
behind     = "⇣${count} "
conflicted = " "
up_to_date = " "
untracked  = "? "
modified   = " "
stashed    = ""
staged     = ""
renamed    = ""
deleted    = ""
```

- [ ] **Step 2: Write the failing test**

Append to `tests/test_hook.py`:

```python
def test_starship_adapter_symlinks_and_backs_up(fake_home):
    path = _fake_tool(fake_home, "starship")
    theme = fake_home / ".local/state/omarchy/current/theme"
    (theme / "starship.toml").write_text('palette = "omarchy"\n')

    cfg = fake_home / ".config/starship.toml"
    cfg.write_text("original = true\n")

    assert run_hook(fake_home, "eltahir", path=path).returncode == 0
    assert cfg.is_symlink()
    assert cfg.resolve() == (theme / "starship.toml").resolve()
    backup = fake_home / ".config/starship.toml.pre-omarchy-theme"
    assert backup.read_text() == "original = true\n"


def test_starship_backup_written_once(fake_home):
    path = _fake_tool(fake_home, "starship")
    theme = fake_home / ".local/state/omarchy/current/theme"
    (theme / "starship.toml").write_text('palette = "omarchy"\n')
    cfg = fake_home / ".config/starship.toml"
    cfg.write_text("original = true\n")

    run_hook(fake_home, "eltahir", path=path)
    run_hook(fake_home, "eltahir", path=path)
    backup = fake_home / ".config/starship.toml.pre-omarchy-theme"
    assert backup.read_text() == "original = true\n"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uvx pytest tests/test_hook.py -k starship -v`
Expected: FAIL — `cfg.is_symlink()` is False

- [ ] **Step 4: Implement the shared owning helper and the adapter**

Add above the adapters in `hooks/apply-devtools-theme`:

```bash
# link_owned <generated-file> <destination>
#
# Replace a whole config file with a symlink to the generated one. Any real
# file already there is copied to <destination>.pre-omarchy-theme first. That
# backup is written once and never overwritten, so re-running is safe and the
# user's original is always recoverable.
link_owned() {
  local src="$THEME_DIR/$1" dest="$2" backup="$2.pre-omarchy-theme"

  if [[ -e $dest && ! -L $dest ]]; then
    if [[ ! -e $backup ]] && ! cp -p "$dest" "$backup"; then
      log "  warn $(basename "$dest"): could not back up; leaving it alone"
      return 0
    fi
  fi
  mkdir -p "$(dirname "$dest")"
  ln -sfn "$src" "$dest"
  log "  $(basename "$dest"): linked"
}

adapter_starship() {
  usable starship starship.toml || return 0
  link_owned starship.toml "$HOME/.config/starship.toml"
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uvx pytest -v`
Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add templates/starship.toml.tpl hooks/apply-devtools-theme tests/
git commit -m "feat: starship adapter

Omarchy's stock starship.toml hardcodes cyan in six places, so the prompt was
teal regardless of theme. starship supports named palettes, so the template
keeps the prompt structure verbatim and varies only [palettes.omarchy].

Adds link_owned, which backs a real config up to *.pre-omarchy-theme once
before replacing it with a symlink, so the original is always recoverable."
```

---

### Task 5: lazygit and lazydocker adapters

lazygit reads `LG_CONFIG_FILE` as a comma-separated list (confirmed in the 0.64.1 binary), so it is *layered* — the user's own config stays untouched and the theme goes last so it wins. It reloads changed config files on terminal focus, so no restart is needed. lazydocker has no such mechanism and is owned.

**Files:**
- Create: `templates/lazygit.theme.yml.tpl`, `templates/lazydocker.theme.yml.tpl`
- Modify: `hooks/apply-devtools-theme`, `tests/test_hook.py`

**Interfaces:**
- Consumes: `link_owned` from Task 4.
- Produces: `$THEME_DIR/lazygit.theme.yml` (referenced by `LG_CONFIG_FILE`, exported by `install.sh`); `~/.config/lazydocker/config.yml` symlink.

- [ ] **Step 1: Write the templates**

`templates/lazygit.theme.yml.tpl`:

```yaml
gui:
  theme:
    activeBorderColor: ["{{ accent }}", "bold"]
    inactiveBorderColor: ["{{ muted }}"]
    searchingActiveBorderColor: ["{{ accent }}", "bold"]
    optionsTextColor: ["{{ muted }}"]
    selectedLineBgColor: ["{{ selection }}"]
    inactiveViewSelectedLineBgColor: ["{{ selection }}"]
    cherryPickedCommitFgColor: ["{{ background }}"]
    cherryPickedCommitBgColor: ["{{ accent }}"]
    markedBaseCommitFgColor: ["{{ background }}"]
    markedBaseCommitBgColor: ["{{ yellow }}"]
    unstagedChangesColor: ["{{ red }}"]
    defaultFgColor: ["{{ foreground }}"]
```

`templates/lazydocker.theme.yml.tpl`:

```yaml
gui:
  theme:
    activeBorderColor: ["{{ accent }}", "bold"]
    inactiveBorderColor: ["{{ muted }}"]
    selectedLineBgColor: ["{{ selection }}"]
    optionsTextColor: ["{{ muted }}"]
```

- [ ] **Step 2: Write the failing test**

Append to `tests/test_hook.py`:

```python
def test_lazygit_adapter_does_not_touch_user_config(fake_home):
    path = _fake_tool(fake_home, "lazygit")
    theme = fake_home / ".local/state/omarchy/current/theme"
    (theme / "lazygit.theme.yml").write_text("gui:\n  theme:\n    defaultFgColor: []\n")

    user_cfg = fake_home / ".config/lazygit/config.yml"
    user_cfg.parent.mkdir(parents=True)
    user_cfg.write_text("gui:\n  language: en\n")

    assert run_hook(fake_home, "eltahir", path=path).returncode == 0
    # Layered, not owned: the user's file is untouched and not replaced.
    assert user_cfg.read_text() == "gui:\n  language: en\n"
    assert not user_cfg.is_symlink()


def test_lazydocker_adapter_owns_its_config(fake_home):
    path = _fake_tool(fake_home, "lazydocker")
    theme = fake_home / ".local/state/omarchy/current/theme"
    (theme / "lazydocker.theme.yml").write_text("gui:\n  theme:\n    optionsTextColor: []\n")

    assert run_hook(fake_home, "eltahir", path=path).returncode == 0
    cfg = fake_home / ".config/lazydocker/config.yml"
    assert cfg.is_symlink()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uvx pytest tests/test_hook.py -k "lazygit or lazydocker" -v`
Expected: FAIL — lazydocker config symlink does not exist

- [ ] **Step 4: Implement the adapters**

Replace both stubs in `hooks/apply-devtools-theme`:

```bash
# lazygit is layered via LG_CONFIG_FILE (exported by install.sh), so the hook
# has nothing to wire — regenerating the file is enough. lazygit reloads
# changed config files when the terminal regains focus.
adapter_lazygit() {
  usable lazygit lazygit.theme.yml || return 0
  log "  lazygit: theme regenerated (layered via LG_CONFIG_FILE)"
}

adapter_lazydocker() {
  usable lazydocker lazydocker.theme.yml || return 0
  link_owned lazydocker.theme.yml "$HOME/.config/lazydocker/config.yml"
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uvx pytest -v`
Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add templates/lazygit.theme.yml.tpl templates/lazydocker.theme.yml.tpl hooks/ tests/
git commit -m "feat: lazygit and lazydocker adapters

lazygit reads LG_CONFIG_FILE as a comma-separated list, so the theme layers on
top of the user's own config rather than replacing it, and lazygit reloads it
on terminal focus. lazydocker has no equivalent and is owned via link_owned."
```

---

### Task 6: bat and fzf adapters

Two small adapters. bat derives a theme's *name from its filename*, so the generated file must be `Omarchy.tmTheme` and never renamed.

**eza gets a template but no adapter.** It takes ANSI escape codes rather than hex — truecolor is `38;2;R;G;B` — while Omarchy's `{{ key_rgb }}` expands with commas. Rather than have the hook rewrite the generated file (which would mutate Omarchy's state directory, and would race a shell that starts before the hook first runs), the conversion happens where the value is consumed: `install.sh` writes `export EZA_COLORS="$(tr ',' ';' < …)"`. No adapter, no post-processing step, no race.

**Files:**
- Create: `templates/Omarchy.tmTheme.tpl`, `templates/fzf.opts.tpl`, `templates/eza.colors.tpl`
- Modify: `hooks/apply-devtools-theme`, `tests/test_hook.py`

**Interfaces:**
- Consumes: hook contract from Task 2.
- Produces: `~/.config/bat/themes/Omarchy.tmTheme`; `$THEME_DIR/fzf.opts` and `$THEME_DIR/eza.colors`, both referenced by env vars from `install.sh`.

- [ ] **Step 1: Write the templates**

`templates/fzf.opts.tpl`:

```
--color=fg:{{ foreground }},bg:{{ background }},hl:{{ accent }}
--color=fg+:{{ bright_foreground }},bg+:{{ selection }},hl+:{{ accent }}
--color=info:{{ muted }},prompt:{{ accent }},pointer:{{ accent }}
--color=marker:{{ green }},spinner:{{ accent }},header:{{ muted }}
--color=border:{{ mix background foreground 20% }},gutter:{{ background }}
```

`templates/eza.colors.tpl` — note every colour is written `38;2;{{ key_rgb }}`, which renders with commas and is corrected by the hook:

```
ur=38;2;{{ accent_rgb }}:uw=38;2;{{ red_rgb }}:ux=38;2;{{ green_rgb }}:ue=38;2;{{ green_rgb }}:gr=38;2;{{ muted_rgb }}:gw=38;2;{{ red_rgb }}:gx=38;2;{{ green_rgb }}:tr=38;2;{{ muted_rgb }}:tw=38;2;{{ red_rgb }}:tx=38;2;{{ green_rgb }}:su=38;2;{{ yellow_rgb }}:sf=38;2;{{ yellow_rgb }}:xa=38;2;{{ muted_rgb }}:sn=38;2;{{ cyan_rgb }}:sb=38;2;{{ muted_rgb }}:df=38;2;{{ muted_rgb }}:ds=38;2;{{ muted_rgb }}:uu=38;2;{{ accent_rgb }}:un=38;2;{{ muted_rgb }}:gu=38;2;{{ accent_rgb }}:gn=38;2;{{ muted_rgb }}:lc=38;2;{{ orange_rgb }}:lm=38;2;{{ orange_rgb }}:ga=38;2;{{ green_rgb }}:gm=38;2;{{ yellow_rgb }}:gd=38;2;{{ red_rgb }}:gv=38;2;{{ magenta_rgb }}:gt=38;2;{{ cyan_rgb }}:di=38;2;{{ blue_rgb }}:ex=38;2;{{ green_rgb }}:fi=38;2;{{ foreground_rgb }}:ln=38;2;{{ cyan_rgb }}:da=38;2;{{ muted_rgb }}:hd=38;2;{{ accent_rgb }}
```

`templates/Omarchy.tmTheme.tpl` — a minimal but valid Sublime `.tmTheme` plist:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>name</key><string>Omarchy</string>
  <key>settings</key>
  <array>
    <dict><key>settings</key><dict>
      <key>background</key><string>{{ background }}</string>
      <key>foreground</key><string>{{ foreground }}</string>
      <key>caret</key><string>{{ accent }}</string>
      <key>selection</key><string>{{ selection }}</string>
      <key>lineHighlight</key><string>{{ lighter_background }}</string>
    </dict></dict>
    <dict><key>name</key><string>Comment</string><key>scope</key><string>comment</string>
      <key>settings</key><dict><key>foreground</key><string>{{ muted }}</string></dict></dict>
    <dict><key>name</key><string>String</string><key>scope</key><string>string</string>
      <key>settings</key><dict><key>foreground</key><string>{{ green }}</string></dict></dict>
    <dict><key>name</key><string>Number</string><key>scope</key><string>constant.numeric</string>
      <key>settings</key><dict><key>foreground</key><string>{{ orange }}</string></dict></dict>
    <dict><key>name</key><string>Constant</string><key>scope</key><string>constant.language</string>
      <key>settings</key><dict><key>foreground</key><string>{{ orange }}</string></dict></dict>
    <dict><key>name</key><string>Keyword</string><key>scope</key><string>keyword, storage.type</string>
      <key>settings</key><dict><key>foreground</key><string>{{ magenta }}</string></dict></dict>
    <dict><key>name</key><string>Function</string><key>scope</key><string>entity.name.function</string>
      <key>settings</key><dict><key>foreground</key><string>{{ blue }}</string></dict></dict>
    <dict><key>name</key><string>Class</string><key>scope</key><string>entity.name.class, entity.name.type</string>
      <key>settings</key><dict><key>foreground</key><string>{{ yellow }}</string></dict></dict>
    <dict><key>name</key><string>Variable</string><key>scope</key><string>variable</string>
      <key>settings</key><dict><key>foreground</key><string>{{ foreground }}</string></dict></dict>
    <dict><key>name</key><string>Tag</string><key>scope</key><string>entity.name.tag</string>
      <key>settings</key><dict><key>foreground</key><string>{{ red }}</string></dict></dict>
    <dict><key>name</key><string>Invalid</string><key>scope</key><string>invalid</string>
      <key>settings</key><dict><key>foreground</key><string>{{ bright_red }}</string></dict></dict>
  </array>
  <key>uuid</key><string>6f1a4c0e-0f2f-4c1e-9a3d-omarchythemed</string>
</dict>
</plist>
```

- [ ] **Step 2: Write the failing test**

Append to `tests/test_hook.py`:

```python
def test_bat_adapter_installs_theme_by_filename(fake_home):
    path = _fake_tool(fake_home, "bat")
    theme = fake_home / ".local/state/omarchy/current/theme"
    (theme / "Omarchy.tmTheme").write_text("<plist></plist>\n")

    assert run_hook(fake_home, "eltahir", path=path).returncode == 0
    installed = fake_home / ".config/bat/themes/Omarchy.tmTheme"
    assert installed.exists()
    # bat derives the theme name from the filename, so it must not be renamed.
    assert installed.name == "Omarchy.tmTheme"


def test_eza_generated_file_is_never_mutated(fake_home):
    """The hook must not touch eza.colors -- conversion happens in the env file."""
    path = _fake_tool(fake_home, "eza")
    theme = fake_home / ".local/state/omarchy/current/theme"
    f = theme / "eza.colors"
    original = "ur=38;2;194,161,90:di=38;2;132,155,189\n"
    f.write_text(original)

    assert run_hook(fake_home, "eltahir", path=path).returncode == 0
    assert f.read_text() == original


def test_fzf_adapter_leaves_generated_file_alone(fake_home):
    path = _fake_tool(fake_home, "fzf")
    theme = fake_home / ".local/state/omarchy/current/theme"
    opts = theme / "fzf.opts"
    opts.write_text("--color=fg:#f3f0e7,bg:#14130d\n")

    assert run_hook(fake_home, "eltahir", path=path).returncode == 0
    # fzf reads the file directly via FZF_DEFAULT_OPTS_FILE; commas are valid here.
    assert opts.read_text() == "--color=fg:#f3f0e7,bg:#14130d\n"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uvx pytest tests/test_hook.py -k "bat or eza or fzf" -v`
Expected: FAIL — bat theme not installed

- [ ] **Step 4: Implement the adapters**

Replace the three stubs in `hooks/apply-devtools-theme`:

```bash
adapter_bat() {
  usable bat Omarchy.tmTheme || return 0

  # bat derives the theme's NAME from the filename, so this must stay
  # Omarchy.tmTheme; install.sh points bat's config at that name.
  local dir="$HOME/.config/bat/themes"
  mkdir -p "$dir"
  cp -f "$THEME_DIR/Omarchy.tmTheme" "$dir/Omarchy.tmTheme" || return 0
  bat cache --build >/dev/null 2>&1 || true
  log "  bat: theme installed and cache rebuilt"
}

# fzf reads the generated file directly through FZF_DEFAULT_OPTS_FILE, which is
# the lowest-precedence option layer, so a user's own FZF_DEFAULT_OPTS still wins.
adapter_fzf() {
  usable fzf fzf.opts || return 0
  log "  fzf: opts regenerated (layered via FZF_DEFAULT_OPTS_FILE)"
}

```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uvx pytest -v`
Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add templates/Omarchy.tmTheme.tpl templates/fzf.opts.tpl templates/eza.colors.tpl hooks/ tests/
git commit -m "feat: bat and fzf adapters, eza template

bat derives a theme's name from its filename, so the generated file is
Omarchy.tmTheme and the cache is rebuilt after every write.

eza needs ANSI escape codes rather than hex, and Omarchy's {{ key_rgb }}
expands with commas, but the conversion belongs where the value is consumed
rather than in the hook: rewriting the generated file would mutate Omarchy's
state directory and would race a shell started before the hook first ran.
install.sh does it with tr when exporting EZA_COLORS."
```

---

### Task 7: tmux adapter

tmux is layered through a `source-file` line that `install.sh` adds once. The hook only regenerates the file and tells a running server to reload it.

**Files:**
- Create: `templates/tmux.theme.conf.tpl`
- Modify: `hooks/apply-devtools-theme`, `tests/test_hook.py`

**Interfaces:**
- Consumes: hook contract from Task 2.
- Produces: `$THEME_DIR/tmux.theme.conf`, sourced from `~/.config/tmux/tmux.conf`.

- [ ] **Step 1: Write the template**

`templates/tmux.theme.conf.tpl`:

```tmux
set -g status-style "bg={{ dark_background }},fg={{ foreground }}"
set -g status-left-style "bg={{ accent }},fg={{ background }},bold"
set -g status-right-style "bg={{ dark_background }},fg={{ muted }}"
set -g window-status-current-style "fg={{ accent }},bold"
set -g window-status-style "fg={{ muted }}"
set -g pane-border-style "fg={{ mix background foreground 20% }}"
set -g pane-active-border-style "fg={{ accent }}"
set -g message-style "bg={{ selection }},fg={{ foreground }}"
set -g mode-style "bg={{ selection }},fg={{ foreground }}"
set -g copy-mode-match-style "bg={{ accent }},fg={{ background }}"
```

- [ ] **Step 2: Write the failing test**

Append to `tests/test_hook.py`:

```python
def test_tmux_adapter_runs_and_leaves_file_intact(fake_home):
    path = _fake_tool(fake_home, "tmux")
    theme = fake_home / ".local/state/omarchy/current/theme"
    conf = theme / "tmux.theme.conf"
    conf.write_text('set -g status-style "bg=#100f0a,fg=#f3f0e7"\n')

    assert run_hook(fake_home, "eltahir", path=path).returncode == 0
    assert conf.read_text() == 'set -g status-style "bg=#100f0a,fg=#f3f0e7"\n'
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uvx pytest tests/test_hook.py -k tmux -v`
Expected: PASS trivially against the Task 2 stub — this test guards the file is not mangled once the adapter does real work. Proceed to Step 4 and confirm it still passes.

- [ ] **Step 4: Implement the adapter**

Replace `adapter_tmux` in `hooks/apply-devtools-theme`:

```bash
# tmux sources the generated file from a line install.sh adds once. Reloading a
# running server is best-effort: there may not be one.
adapter_tmux() {
  usable tmux tmux.theme.conf || return 0
  if tmux has-session >/dev/null 2>&1; then
    tmux source-file "$HOME/.config/tmux/tmux.conf" >/dev/null 2>&1 || true
    log "  tmux: running server reloaded"
  else
    log "  tmux: theme regenerated (no running server)"
  fi
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uvx pytest -v`
Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add templates/tmux.theme.conf.tpl hooks/apply-devtools-theme tests/
git commit -m "feat: tmux adapter

Layered through a source-file line install.sh adds once; the hook regenerates
the file and reloads a running server if there is one."
```

---

### Task 8: install.sh

All one-time wiring lives here, never in the hook — so the hook stays fast, cannot append duplicates, and every mutation of a user-owned file is in one auditable place.

**Files:**
- Create: `install.sh`
- Create: `tests/test_install.py`

**Interfaces:**
- Consumes: `templates/`, `hooks/apply-devtools-theme`, `lib/`.
- Produces: symlinks in `~/.config/omarchy/themed/` and `~/.config/omarchy/hooks/theme-set.d/`; `~/.config/omarchy/themed-devtools.env`; managed lines in `~/.config/git/config`, `~/.config/tmux/tmux.conf`, `~/.config/bat/config`.

- [ ] **Step 1: Write the failing test**

`tests/test_install.py`:

```python
import os
import subprocess
from pathlib import Path

from conftest import REPO


def run_script(name: str, home: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ, HOME=str(home))
    return subprocess.run(["bash", str(REPO / name)],
                          capture_output=True, text=True, env=env)


def test_install_links_templates_and_hook(tmp_path):
    result = run_script("install.sh", tmp_path)
    assert result.returncode == 0

    themed = tmp_path / ".config/omarchy/themed"
    linked = {p.name for p in themed.iterdir()}
    assert "herdr.theme.toml.tpl" in linked
    assert "starship.toml.tpl" in linked

    hook = tmp_path / ".config/omarchy/hooks/theme-set.d/apply-devtools-theme"
    assert hook.is_symlink()


def test_install_writes_env_file_and_prints_source_line(tmp_path):
    result = run_script("install.sh", tmp_path)
    env_file = tmp_path / ".config/omarchy/themed-devtools.env"
    assert env_file.exists()
    body = env_file.read_text()
    assert "FZF_DEFAULT_OPTS_FILE" in body
    assert "EZA_COLORS" in body
    assert "LG_CONFIG_FILE" in body
    # The rc file is never edited; the user is told what to add.
    assert "source" in result.stdout
    assert not (tmp_path / ".bashrc").exists()


def test_install_is_idempotent(tmp_path):
    run_script("install.sh", tmp_path)
    gitconfig = tmp_path / ".config/git/config"
    first = gitconfig.read_text() if gitconfig.exists() else ""
    run_script("install.sh", tmp_path)
    second = gitconfig.read_text() if gitconfig.exists() else ""
    assert first == second
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uvx pytest tests/test_install.py -v`
Expected: FAIL — `install.sh` does not exist

- [ ] **Step 3: Implement install.sh**

```bash
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
$TAG -- source this from your shell rc
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uvx pytest tests/test_install.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add install.sh tests/test_install.py
git commit -m "feat: install script

All one-time wiring lives here rather than in the hook: env vars, the git
include, the tmux source-file line and bat's theme name. The hook only
regenerates contents, so it stays fast and cannot append duplicates.

The shell rc is never edited -- the exports go in a file and the source line is
printed for the user to add."
```

---

### Task 9: uninstall.sh and the round-trip guarantee

Uninstall is a first-class requirement: this project symlinks over configs, copies into bat's theme directory, splices a managed block into herdr's config, and adds lines to gitconfig, tmux.conf and bat's config. Without an exact reversal that footprint is unremovable.

**Files:**
- Create: `uninstall.sh`
- Modify: `tests/test_install.py` (append the round-trip test)

**Interfaces:**
- Consumes: `MARK_START`/`MARK_END` from Task 1; the `$TAG` convention from Task 8.
- Produces: nothing; it removes.

- [ ] **Step 1: Write the failing round-trip test**

Append to `tests/test_install.py`:

```python
def _snapshot(root: Path) -> dict[str, str]:
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and not p.is_symlink():
            out[str(p.relative_to(root))] = p.read_text(errors="replace")
    return out


def test_install_uninstall_round_trip_is_clean(tmp_path):
    # A pre-existing user config that must come back byte-identical.
    cfg = tmp_path / ".config/starship.toml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("original = true\n")
    before = _snapshot(tmp_path)

    run_script("install.sh", tmp_path)
    run_script("uninstall.sh", tmp_path)

    assert _snapshot(tmp_path) == before
    assert not (tmp_path / ".config/omarchy/themed").exists() or \
        not any((tmp_path / ".config/omarchy/themed").iterdir())
    assert cfg.read_text() == "original = true\n"
    assert not cfg.is_symlink()


def test_uninstall_never_eats_a_user_line(tmp_path):
    """Regression: a one-line addition followed immediately by a user line.

    An earlier remover deleted a fixed two lines after a tag and destroyed
    `set -g mouse on`. Markers make the addition's length irrelevant.
    """
    conf = tmp_path / ".config/tmux/tmux.conf"
    conf.parent.mkdir(parents=True)
    conf.write_text(
        "# >>> omarchy-theme >>>\n"
        "source-file -q /theme/tmux.theme.conf\n"
        "# <<< omarchy-theme <<<\n"
        "set -g mouse on\n"
        "set -g prefix C-Space\n")

    run_script("uninstall.sh", tmp_path)
    out = conf.read_text()
    assert "omarchy-theme" not in out
    assert "source-file" not in out
    assert "set -g mouse on" in out
    assert "set -g prefix C-Space" in out


def test_uninstall_removes_herdr_managed_block(tmp_path):
    cfg = tmp_path / ".config/herdr/config.toml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(
        'onboarding = false\n\n[keys]\nprefix = "ctrl+space"\n\n'
        '# >>> omarchy-theme >>>\n[theme]\nname = "terminal"\n'
        '# <<< omarchy-theme <<<\n')

    run_script("uninstall.sh", tmp_path)
    out = cfg.read_text()
    assert "omarchy-theme" not in out
    assert 'prefix = "ctrl+space"' in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uvx pytest tests/test_install.py -k "round_trip or managed_block" -v`
Expected: FAIL — `uninstall.sh` does not exist

- [ ] **Step 3: Implement uninstall.sh**

```bash
#!/usr/bin/env bash
# Exact reversal of install.sh. Restores every *.pre-omarchy-theme backup,
# removes the managed block from herdr's config, and deletes the tagged lines
# this project added. Safe to run when nothing is installed.
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
  awk '
    /^[[:space:]]*# >>> omarchy-theme >>>[[:space:]]*$/ { inblock = 1; next }
    /^[[:space:]]*# <<< omarchy-theme <<<[[:space:]]*$/ { inblock = 0; next }
    !inblock { print }
  ' "$file" >"$file.tmp" && mv "$file.tmp" "$file"
  # Only files this project may have created are removed when emptied; never a
  # config the user owns outright.
  [[ $remove_if_empty == "--remove-if-empty" && ! -s $file ]] && rm -f "$file"
  return 0
}

strip_block "$HOME/.config/git/config"
strip_block "$HOME/.config/tmux/tmux.conf"
strip_block "$HOME/.config/bat/config" --remove-if-empty
strip_block "$HOME/.config/herdr/config.toml"
echo "  removed managed blocks"

rmdir "$THEMED" "$HOOKS" 2>/dev/null || true

echo
echo "Uninstalled. Remove this line from your shell rc if you added it:"
echo "  source $ENV_FILE"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uvx pytest -v`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add uninstall.sh tests/test_install.py
git commit -m "feat: uninstall script with a round-trip guarantee

This project symlinks over configs, copies into bat's theme dir, splices a
block into herdr's config and adds lines to three rc files, so an exact
reversal is a requirement rather than a nicety. Covered by a test asserting
install then uninstall leaves the tree byte-identical."
```

---

### Task 10: Template rendering validation

Templates are where most of the project's surface area lives, and nothing so far
parses their output. A typo, an unbalanced quote, or a `{{ token }}` that no
palette defines would ship silently. The unresolved-token check matters most: it
is the exact failure mode when a template references a key Omarchy cannot
resolve.

**Files:**
- Create: `tests/test_templates.py`
- Modify: `pyproject.toml` (pyyaml for the YAML templates)

**Interfaces:**
- Consumes: `templates/*.tpl`.
- Produces: nothing; it validates.

- [ ] **Step 1: Add the YAML dependency**

Replace `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

Tests that need YAML are run with `uvx --with pyyaml pytest`.

- [ ] **Step 2: Write the failing test**

`tests/test_templates.py`:

```python
"""Render every template against a known palette and parse the result.

Mirrors what omarchy-theme-set-templates does: substitute {{ key }},
{{ key_strip }}, {{ key_rgb }} and {{ mix a b N% }}.
"""
import plistlib
import re
import tomllib

import pytest
import yaml

from conftest import REPO

PALETTE = {
    "background": "#14130d", "dark_background": "#100f0a",
    "darker_background": "#0c0b07", "lighter_background": "#1c1b14",
    "foreground": "#f3f0e7", "bright_foreground": "#f8f7f2",
    "light_foreground": "#b4ae9f", "dark_foreground": "#76705f",
    "muted": "#76705f", "accent": "#c2a15a", "selection": "#2e2716",
    "red": "#cf6f56", "green": "#94a55e", "yellow": "#c2a15a",
    "blue": "#849bbd", "magenta": "#ba859f", "cyan": "#74a69b",
    "orange": "#d28d4d", "brown": "#9c7d52", "bright_red": "#e58e75",
    "theme_type": "dark",
}


def _mix(a: str, b: str, pct: float) -> str:
    ca, cb = a.lstrip("#"), b.lstrip("#")
    parts = []
    for i in (0, 2, 4):
        x, y = int(ca[i:i + 2], 16), int(cb[i:i + 2], 16)
        parts.append(f"{round(x + (y - x) * pct):02x}")
    return "#" + "".join(parts)


def render(text: str) -> str:
    def mix_sub(m):
        a, b, amount = m.group(1), m.group(2), m.group(3)
        return _mix(PALETTE[a], PALETTE[b], float(amount.rstrip("%")) / 100)

    text = re.sub(r"\{\{\s*mix\s+(\w+)\s+(\w+)\s+([\d.]+%)\s*\}\}", mix_sub, text)
    for key, value in PALETTE.items():
        text = text.replace(f"{{{{ {key} }}}}", value)
        text = text.replace(f"{{{{ {key}_strip }}}}", value.lstrip("#"))
        rgb = ",".join(str(int(value.lstrip("#")[i:i + 2], 16)) for i in (0, 2, 4))
        text = text.replace(f"{{{{ {key}_rgb }}}}", rgb)
    return text


def _render_template(name: str) -> str:
    return render((REPO / "templates" / name).read_text())


ALL = [p.name for p in (REPO / "templates").glob("*.tpl")]


@pytest.mark.parametrize("name", ALL)
def test_no_unresolved_tokens(name):
    """A leftover {{ }} means the template references a key no palette defines."""
    out = _render_template(name)
    leftovers = re.findall(r"\{\{[^}]*\}\}", out)
    assert not leftovers, f"{name} left {leftovers} unresolved"


@pytest.mark.parametrize("name", ["herdr.theme.toml.tpl", "starship.toml.tpl"])
def test_toml_templates_parse(name):
    tomllib.loads(_render_template(name))


@pytest.mark.parametrize("name", ["lazygit.theme.yml.tpl", "lazydocker.theme.yml.tpl"])
def test_yaml_templates_parse(name):
    data = yaml.safe_load(_render_template(name))
    assert "gui" in data and "theme" in data["gui"]


def test_tmtheme_parses_as_plist():
    data = plistlib.loads(_render_template("Omarchy.tmTheme.tpl").encode())
    # bat matches the theme by filename, but the name key should agree.
    assert data["name"] == "Omarchy"
    assert data["settings"][0]["settings"]["background"] == PALETTE["background"]


def test_fzf_opts_are_well_formed():
    for line in _render_template("fzf.opts.tpl").splitlines():
        if not line.strip():
            continue
        assert line.startswith("--color="), line
        for pair in line[len("--color="):].split(","):
            assert re.fullmatch(r"[\w+-]+:#[0-9a-fA-F]{6}", pair), pair


def test_eza_colors_use_ansi_triplets():
    out = _render_template("eza.colors.tpl").strip()
    assert "#" not in out, "eza takes ANSI codes, never hex"
    for pair in out.split(":"):
        key, _, value = pair.partition("=")
        assert key and value.startswith("38;2;"), pair
        # Commas here are expected; install.sh converts them when exporting.
        assert re.fullmatch(r"38;2;\d{1,3},\d{1,3},\d{1,3}", value), pair


def test_herdr_template_covers_every_custom_token():
    data = tomllib.loads(_render_template("herdr.theme.toml.tpl"))
    expected = {
        "accent", "panel_bg", "sidebar_bg", "active_row_bg", "selection_bg",
        "surface0", "surface1", "surface_dim", "overlay0", "overlay1",
        "text", "subtext0", "mauve", "green", "yellow", "red", "blue",
        "teal", "peach",
    }
    assert set(data["theme"]["custom"]) == expected
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uvx --with pyyaml pytest tests/test_templates.py -v`
Expected: FAIL — collection error until every template from Tasks 3-7 exists

- [ ] **Step 4: Fix whatever the parsers reject**

No new implementation: this task validates work already done. Correct any template the parsers reject, then re-run. Typical findings are an unquoted hex in YAML, a `{{ token }}` whose key is absent from `PALETTE`, or an unescaped `&`/`<` in the plist.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uvx --with pyyaml pytest -v`
Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add tests/test_templates.py
git commit -m "test: render and parse every template

Templates carry most of the project's surface area and nothing parsed their
output, so a typo or a token no palette defines would have shipped silently.
Each rendered template is now parsed with the right parser -- tomllib, yaml,
plistlib -- and every template is checked for leftover {{ }} tokens."
```

---

### Task 11: README and live end-to-end verification

The final gate: prove the whole thing works against two real themes, not just in tmpdirs.

**Files:**
- Create: `README.md`

**Interfaces:**
- Consumes: everything.
- Produces: nothing.

- [ ] **Step 1: Write the README**

`README.md`:

````markdown
# omarchy-themed-devtools

Omarchy themes ~17 surfaces from a single `colors.toml`. It does not theme the
command-line tools you actually work inside. This does — **for every Omarchy
theme**, not just one.

| Tool | Before | After |
|---|---|---|
| `herdr` | fixed `accent = "blue"` | your theme's accent |
| `bat` | Monokai Extended, always | your palette |
| `lazygit` / `lazydocker` | their own defaults | your palette |
| `starship` | hardcoded `cyan` | your theme's accent |
| `fzf` / `eza` / `tmux` | terminal defaults | your palette |

## How it works

Omarchy's `omarchy-theme-set-templates` renders **any** `.tpl` in
`~/.config/omarchy/themed/` against the active palette — new filenames included,
not just overrides of built-ins. This project ships one template per tool plus a
single `theme-set.d` hook that wires each generated file to where its tool reads
it. Nothing in Omarchy is patched or forked.

## Install

```bash
git clone <this-repo> ~/repos/omarchy-themed-devtools
cd ~/repos/omarchy-themed-devtools
./install.sh
# add the printed `source` line to ~/.bashrc, then open a new shell
omarchy theme set "$(omarchy theme current)"
```

## Uninstall

```bash
./uninstall.sh
```

Restores every backup, removes the managed block from herdr's config, and
deletes the lines it added. A test asserts the round trip is byte-identical.

## What it touches

Owned via symlink, with a one-time `*.pre-omarchy-theme` backup:
`~/.config/starship.toml`, `~/.config/lazydocker/config.yml`.

Layered, leaving your config alone: `lazygit` (`LG_CONFIG_FILE`), `fzf`
(`FZF_DEFAULT_OPTS_FILE`), `eza` (`EZA_COLORS`), `tmux` (`source-file`).

Spliced between markers, keybindings untouched: `~/.config/herdr/config.toml`.

## Notes

- Hooks do not run under `OMARCHY_THEME_HEADLESS=1` / `OMARCHY_THEME_OFFLINE=1`.
  Re-run by hand: `bash ~/.config/omarchy/hooks/theme-set.d/apply-devtools-theme --sync`
- `delta` is not yet supported; it was not installed on the development machine
  and so could not be tested end to end.

## Tests

```bash
uvx pytest
```
````

- [ ] **Step 2: Run the full test suite**

Run: `uvx pytest -v`
Expected: all passed

- [ ] **Step 3: Install for real and verify against two themes**

```bash
./install.sh
source ~/.config/omarchy/themed-devtools.env

omarchy theme set Eltahir
bash ~/.config/omarchy/hooks/theme-set.d/apply-devtools-theme --sync --verbose
```

Confirm each is true before continuing:

```bash
# templates rendered into the live theme
ls ~/.local/state/omarchy/current/theme/ | grep -E 'herdr|starship|lazygit|Omarchy.tmTheme|fzf|eza'

# herdr got the gold accent and kept its keybindings
grep -A3 'omarchy-theme' ~/.config/herdr/config.toml
grep 'prefix = "ctrl+space"' ~/.config/herdr/config.toml

# bat knows the theme
bat --list-themes | grep Omarchy

# eza has no commas left
grep -c ',' ~/.local/state/omarchy/current/theme/eza.colors   # expect 0
```

- [ ] **Step 4: Prove it is theme-agnostic**

```bash
omarchy theme set Catppuccin
grep -A6 'theme.custom' ~/.config/herdr/config.toml   # expect Catppuccin colours, not gold
omarchy theme set Eltahir                             # switch back
```

This is the whole point of the project: the tools follow *any* theme.

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: README

Verified end to end against two themes: applying Eltahir then Catppuccin
re-themes herdr, bat, lazygit, starship, fzf and eza both ways."
```

---

## Self-Review

**Spec coverage.** Every adapter in the spec's table has a task: herdr (3),
starship (4), lazygit + lazydocker (5), bat + fzf + eza (6), tmux (7). `delta`
is deliberately excluded and the README says why. All eight spec decisions are
implemented: token mapping and derived ramp (Task 3), light/dark via
`theme.name = "terminal"` (Task 3), one-time wiring in `install.sh` (Task 8),
uninstall as first-class with a round-trip test (Task 9), scope (README),
MIT/public (`LICENSE`), `uvx pytest` only (Task 1), headless accepted with
`--sync` (Tasks 2, 8).

**One refinement to spec decision 2.** The spec said herdr's `theme.name` should
select a light or dark built-in. herdr's built-in names are not documented, and
`terminal` — already proven valid by the user's own config — makes the base
inherit the terminal palette Omarchy themes, so untouched tokens are correct in
both modes without guessing. Recorded here rather than silently changed.

**Placeholders.** None. Every step carries real code or a real command.

**Type and name consistency.** `splice(config_text, theme_block, ui_accent)` is
defined in Task 1 and called with those three arguments in Task 3.
`link_owned <generated> <dest>` is defined in Task 4 and reused in Task 5.
`usable <tool> <file>` is defined in Task 2 and used by every adapter. Generated
filenames match between templates, adapters and tests: `herdr.theme.toml`,
`starship.toml`, `lazygit.theme.yml`, `lazydocker.theme.yml`, `Omarchy.tmTheme`,
`fzf.opts`, `eza.colors`, `tmux.theme.conf`. `MARK_START`/`MARK_END` in Task 1
match the awk patterns in Task 9.

**Known gap accepted.** `install.sh` writes `EZA_COLORS` by reading
`eza.colors` at shell startup, so a theme change is picked up by new shells
rather than existing ones. Same for `fzf`, whose file is re-read per invocation
and so updates immediately. This asymmetry is inherent to env-var wiring and is
documented in the README rather than worked around.

## Review round 2 (2026-09-03)

Three defects were found by grilling this plan and are fixed above. Recorded so
they are not reintroduced.

1. **`DEVTOOLS_LIB` was dead once installed.** It derived the repo path from
   `${BASH_SOURCE[0]}`, which is the *symlink* omarchy invokes, so `lib/` was
   looked for beside the link and never found — the herdr adapter would have
   done nothing in production. Worse, every hook test called the repo copy
   directly, so the suite could not have caught it. Fixed with `readlink -f`,
   and `run_hook` now invokes the installed symlink so the whole class of bug is
   closed rather than this one instance.
2. **`uninstall.sh` deleted user lines.** It skipped a fixed two lines after a
   tag, but only the git `[include]` addition is two lines. Verified to destroy
   `set -g mouse on` from a tmux.conf. Replaced with one marker-based remover
   used for every file, herdr included, plus a regression test.
3. **The eza adapter mutated Omarchy's state directory** and raced a shell
   started before the first theme change. Removed entirely; the conversion now
   happens in `install.sh` where the value is consumed.

One prediction was **wrong** and is recorded to save the next reader the
detour: `set -e` does *not* abort `install.sh` when `command -v <tool>` fails in
an `&&` chain — bash exempts AND-lists. Verified empirically.

A fourth risk was **cleared**: `{{ orange }}` and `{{ brown }}` are absent from
some themes' `colors.toml` (Solitude, for one), but `omarchy-theme-color --all`
resolves them via fallbacks, so templates referencing them are safe everywhere.
