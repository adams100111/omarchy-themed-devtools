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


import os
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Resolved once against the real environment PATH. The fixture below sets the
# child process's PATH to `path` (empty by default) so `command -v` inside the
# hook sees no dev tools installed — but an explicitly empty PATH also stops
# Python from finding a bare "bash" on exec (it does not fall back to the OS
# default path the way an *unset* PATH would). Invoking bash by its resolved
# absolute path keeps the "no tools on PATH" behavior for the hook's own
# lookups without that side effect on launching bash itself.
BASH = shutil.which("bash") or "/usr/bin/bash"


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

    return subprocess.run(
        [BASH, str(link), *args], capture_output=True, text=True,
        env=child_env(home, path=path),
    )


def child_env(home: Path, path: str | None = None) -> dict[str, str]:
    """The environment every script/hook under test runs in.

    XDG_CACHE_HOME and XDG_CONFIG_HOME are PINNED inside the temporary HOME
    rather than inherited. Without that the suite is only hermetic by accident:
    tools invoked by the scripts (`bat cache --build`) follow whatever the
    developer's shell exports, so the same test passes here and fails under
    `env -u XDG_CACHE_HOME -u XDG_CONFIG_HOME`. Pinning also guarantees nothing
    under test can write into the real user's cache or config.
    """
    env = dict(os.environ,
               HOME=str(home),
               XDG_CACHE_HOME=str(home / ".cache"),
               XDG_CONFIG_HOME=str(home / ".config"))
    if path is not None:
        env["PATH"] = path
    return env
