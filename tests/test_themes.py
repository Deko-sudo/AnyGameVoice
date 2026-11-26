"""Guard readable text and complete offline schemes across every shipped palette."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / 'ui' / 'themes.js').read_text(encoding='utf-8').split('window.AnyGameVoiceThemes = ', 1)[1].rstrip(';\n'))


def luminance(color):
    channels = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in channels]
    return sum(c * w for c, w in zip(linear, (.2126, .7152, .0722)))


def contrast(first, second):
    low, high = sorted((luminance(first), luminance(second)))
    return (high + .05) / (low + .05)


def test_120_distinct_palettes():
    assert len(CATALOG) == 120
    assert len({theme['id'] for theme in CATALOG}) == len(CATALOG)
    assert len({theme['name'] for theme in CATALOG}) == len(CATALOG)
    for mode in ('light', 'dark'):
        assert len({json.dumps(theme['schemes'][mode], sort_keys=True) for theme in CATALOG}) == len(CATALOG)


@pytest.mark.parametrize('theme', CATALOG, ids=lambda theme: theme['id'])
@pytest.mark.parametrize('mode', ['light', 'dark'])
def test_role_pairs_are_readable(theme, mode):
    scheme = theme['schemes'][mode]
    pairs = [('on-primary', 'primary'), ('on-primary-container', 'primary-container'),
             ('on-secondary-container', 'secondary-container'), ('on-tertiary-container', 'tertiary-container'),
             ('on-error-container', 'error-container')]
    for surface in ('surface', 'surface-container-low', 'surface-container', 'surface-container-high', 'surface-container-highest'):
        pairs.extend([('on-surface', surface), ('on-surface-variant', surface), ('primary', surface), ('error', surface)])
    for foreground, background in pairs:
        ratio = contrast(scheme[foreground], scheme[background])
        assert ratio >= 4.5, f'{theme["id"]}/{mode} {foreground} on {background}: {ratio:.2f}:1'
