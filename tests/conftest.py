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
