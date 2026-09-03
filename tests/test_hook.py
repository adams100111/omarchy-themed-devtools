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
