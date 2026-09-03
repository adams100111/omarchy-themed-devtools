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
        if value.startswith("#"):
            # theme_type ("dark"/"light") is not a color; only real hex
            # values have an _rgb variant.
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
