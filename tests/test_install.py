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
