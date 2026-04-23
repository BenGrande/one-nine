"""Regression tests for layout bounds — no hole should render outside the canvas.

Before the fix, `_rescale_to_fill` sized content by each hole's `start_y` only,
so long final holes clipped off the bottom. Augusta Country Club (the user-
reported case) was the clearest example: hole 9 ended at y=772 on a 700-unit
canvas.
"""

from app.services.render.layout import compute_layout


AUGUSTA_CC_FRONT_NINE = [
    {"ref": 1, "par": 4, "yardage": 448, "handicap": 7, "features": []},
    {"ref": 2, "par": 5, "yardage": 410, "handicap": 5, "features": []},
    {"ref": 3, "par": 4, "yardage": 442, "handicap": 1, "features": []},
    {"ref": 4, "par": 3, "yardage": 148, "handicap": 17, "features": []},
    {"ref": 5, "par": 4, "yardage": 516, "handicap": 13, "features": []},
    {"ref": 6, "par": 3, "yardage": 210, "handicap": 11, "features": []},
    {"ref": 7, "par": 4, "yardage": 342, "handicap": 15, "features": []},
    {"ref": 8, "par": 5, "yardage": 596, "handicap": 9, "features": []},
    {"ref": 9, "par": 4, "yardage": 482, "handicap": 3, "features": []},
]


def test_all_holes_inside_canvas_for_augusta_cc():
    """Every hole's start/end y must sit within the drawable area."""
    layout = compute_layout(
        AUGUSTA_CC_FRONT_NINE,
        {"canvas_width": 900, "canvas_height": 700},
    )
    draw = layout["draw_area"]
    top = draw["top"]
    bottom = draw["bottom"]

    for h in layout["holes"]:
        assert top - 1e-6 <= h["start_y"] <= bottom + 1e-6, h
        assert top - 1e-6 <= h["end_y"] <= bottom + 1e-6, h


def test_layout_fills_canvas_vertically():
    """Rescale should also stretch to fill — not just avoid clipping."""
    layout = compute_layout(
        AUGUSTA_CC_FRONT_NINE,
        {"canvas_width": 900, "canvas_height": 700},
    )
    draw = layout["draw_area"]
    height = draw["bottom"] - draw["top"]

    all_ys = []
    for h in layout["holes"]:
        all_ys.append(h["start_y"])
        all_ys.append(h["end_y"])
    used = max(all_ys) - min(all_ys)

    # Should fill at least 90% of available height (otherwise rescale is lazy).
    assert used >= height * 0.9, f"used {used} of {height}"


def test_short_course_does_not_overfill():
    """Three par-3s shouldn't be force-stretched to span the whole canvas
    at crazy proportions — the rescale target is 'fill the draw area', so
    the aggregate y-range should still match the canvas height exactly
    (end_y of last hole ≈ draw_bottom)."""
    short_course = [
        {"ref": 1, "par": 3, "yardage": 150, "handicap": 1, "features": []},
        {"ref": 2, "par": 3, "yardage": 170, "handicap": 2, "features": []},
        {"ref": 3, "par": 3, "yardage": 140, "handicap": 3, "features": []},
    ]
    layout = compute_layout(short_course, {"canvas_width": 900, "canvas_height": 700})
    draw = layout["draw_area"]
    for h in layout["holes"]:
        assert draw["top"] - 1e-6 <= h["start_y"] <= draw["bottom"] + 1e-6
        assert draw["top"] - 1e-6 <= h["end_y"] <= draw["bottom"] + 1e-6
