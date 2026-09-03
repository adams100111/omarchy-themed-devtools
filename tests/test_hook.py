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
