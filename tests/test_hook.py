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
