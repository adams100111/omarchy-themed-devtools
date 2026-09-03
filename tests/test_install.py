import subprocess
from pathlib import Path

from conftest import REPO, child_env, run_hook
from test_hook import _fake_tool

MARK_START = "# >>> omarchy-theme >>>"


def run_script(name: str, home: Path,
               path: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(REPO / name)],
                          capture_output=True, text=True,
                          env=child_env(home, path=path))


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
    """Re-running install must not append a second managed block.

    This used to inspect ~/.config/git/config, which install.sh writes only
    when `delta` is on PATH -- and delta is deferred to v1.1, so the file never
    existed and the assertion compared "" to "". Assert on files install.sh
    actually creates, with the tools faked onto PATH so the test does not
    depend on what happens to be installed on the machine running it.
    """
    path = _fake_tool(tmp_path, "bat")
    _fake_tool(tmp_path, "tmux")

    assert run_script("install.sh", tmp_path, path=path).returncode == 0
    bat_cfg = tmp_path / ".config/bat/config"
    tmux_conf = tmp_path / ".config/tmux/tmux.conf"
    first_bat, first_tmux = bat_cfg.read_text(), tmux_conf.read_text()
    assert '--theme="Omarchy"' in first_bat
    assert "source-file -q" in first_tmux
    assert first_bat.count(MARK_START) == 1
    assert first_tmux.count(MARK_START) == 1

    assert run_script("install.sh", tmp_path, path=path).returncode == 0
    assert bat_cfg.read_text() == first_bat
    assert tmux_conf.read_text() == first_tmux


def _snapshot(root: Path) -> dict[str, str]:
    """Every real file under `root`, except the XDG cache.

    `uninstall.sh` runs `bat cache --build`, which regenerates bat's syntax and
    theme cache under $XDG_CACHE_HOME. That is a derived artifact bat rebuilds
    on demand, not user data, and it is written after the "before" snapshot is
    taken -- so it is excluded here rather than papered over by whatever
    XDG_CACHE_HOME the developer's shell happens to export.
    """
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and not p.is_symlink() \
                and ".cache" not in p.relative_to(root).parts[:1]:
            out[str(p.relative_to(root))] = p.read_text(errors="replace")
    return out


def test_install_uninstall_round_trip_is_clean(fake_home):
    tmp_path = fake_home

    # A pre-existing user config that must come back byte-identical.
    cfg = tmp_path / ".config/starship.toml"
    cfg.write_text("original = true\n")

    # install.sh never touches starship.toml -- only adapter_starship in the
    # hook does, via link_owned. Give the hook a fake `starship` on PATH and a
    # generated theme file so it actually symlinks and backs up the config;
    # otherwise this test would pass even with uninstall's restore loop
    # deleted, since the path it's meant to cover would never run.
    path = _fake_tool(tmp_path, "starship")
    theme = tmp_path / ".local/state/omarchy/current/theme"
    (theme / "starship.toml").write_text('palette = "omarchy"\n')

    before = _snapshot(tmp_path)

    run_script("install.sh", tmp_path)
    assert run_hook(tmp_path, "eltahir", path=path).returncode == 0

    # Confirm the symlink-and-backup path was actually exercised before we
    # rely on uninstall to reverse it.
    assert cfg.is_symlink()
    backup = tmp_path / ".config/starship.toml.pre-omarchy-theme"
    assert backup.read_text() == "original = true\n"

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


def test_uninstall_leaves_a_foreign_symlink_alone(tmp_path):
    """A dotfiles symlink we never created must survive `./uninstall.sh`.

    chezmoi is in this user's provisioning profile, so ~/.config/starship.toml
    being a symlink into a dotfiles repo is the normal case, not an edge case.
    An earlier version tested only `-L` and deleted it on a machine where this
    project had never been installed.
    """
    dotfiles = tmp_path / "dotfiles"
    dotfiles.mkdir()
    source = dotfiles / "starship.toml"
    source.write_text("mine = true\n")

    link = tmp_path / ".config/starship.toml"
    link.parent.mkdir(parents=True)
    link.symlink_to(source)

    assert run_script("uninstall.sh", tmp_path).returncode == 0
    assert link.is_symlink()
    assert link.resolve() == source.resolve()
    assert source.read_text() == "mine = true\n"


def test_uninstall_removes_only_its_own_symlink(tmp_path):
    """The other half of the ownership test: a link into the theme dir goes."""
    theme = tmp_path / ".local/state/omarchy/current/theme"
    theme.mkdir(parents=True)
    generated = theme / "lazydocker.theme.yml"
    generated.write_text("gui: {}\n")

    link = tmp_path / ".config/lazydocker/config.yml"
    link.parent.mkdir(parents=True)
    link.symlink_to(generated)

    assert run_script("uninstall.sh", tmp_path).returncode == 0
    assert not link.exists() and not link.is_symlink()


def test_uninstall_strips_through_a_symlinked_config(tmp_path):
    """A dotfiles-managed tmux.conf stays a symlink; its target is edited.

    Renaming a temp file over the link would detach it, leaving our block in
    the dotfiles copy forever while an orphaned regular file took over.
    """
    dotfiles = tmp_path / "dotfiles"
    dotfiles.mkdir()
    source = dotfiles / "tmux.conf"
    source.write_text(
        "set -g mouse on\n"
        "# >>> omarchy-theme >>>\n"
        "source-file -q /theme/tmux.theme.conf\n"
        "# <<< omarchy-theme <<<\n")
    source.chmod(0o644)

    conf = tmp_path / ".config/tmux/tmux.conf"
    conf.parent.mkdir(parents=True)
    conf.symlink_to(source)

    assert run_script("uninstall.sh", tmp_path).returncode == 0
    assert conf.is_symlink(), "the dotfiles link must survive"
    assert conf.resolve() == source.resolve()
    assert source.read_text() == "set -g mouse on\n"
    # mktemp creates 0600; the rename must not tighten the user's permissions.
    assert source.stat().st_mode & 0o777 == 0o644


def test_install_appends_to_legacy_tmux_conf(tmp_path):
    """With only ~/.tmux.conf present, install must not create the XDG file.

    tmux ignores ~/.tmux.conf entirely once ~/.config/tmux/tmux.conf exists
    (verified on tmux 3.7c), so creating one silently takes away the user's
    prefix, keybindings and plugins.
    """
    legacy = tmp_path / ".tmux.conf"
    legacy.write_text("set -g prefix C-Space\n")
    path = _fake_tool(tmp_path, "tmux")

    assert run_script("install.sh", tmp_path, path=path).returncode == 0
    assert not (tmp_path / ".config/tmux/tmux.conf").exists()
    body = legacy.read_text()
    assert "set -g prefix C-Space" in body
    assert "source-file -q" in body

    # ...and uninstall takes it back out without deleting the user's file.
    assert run_script("uninstall.sh", tmp_path, path=path).returncode == 0
    assert legacy.read_text() == "set -g prefix C-Space\n"


def test_install_says_when_it_creates_a_tmux_conf(tmp_path):
    path = _fake_tool(tmp_path, "tmux")
    result = run_script("install.sh", tmp_path, path=path)
    assert (tmp_path / ".config/tmux/tmux.conf").exists()
    assert "created" in result.stdout and "tmux.conf" in result.stdout
