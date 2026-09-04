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
