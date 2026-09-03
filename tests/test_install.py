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
