from caramelo.banner import DOG, NAME, full_width, render


def test_full_banner_has_portrait_name_and_hud():
    text = render(full_width(), sites=641, version="0.1.0").plain
    assert DOG[0] in text and NAME[0] in text
    assert "641 sites · 0 API keys" in text and "v0.1.0" in text


def test_narrow_terminal_drops_the_portrait_and_fits():
    text = render(80).plain
    assert DOG[5] not in text and NAME[0] in text
    assert max(len(line) for line in text.splitlines()) <= 80


def test_hud_box_lines_are_aligned():
    hud = [line for line in render(80).plain.splitlines() if line and line[0] in "╭│╰"]
    assert len({len(line) for line in hud}) == 1
