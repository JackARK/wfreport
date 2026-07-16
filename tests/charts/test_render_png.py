# tests/charts/test_render_png.py
import os, struct, tempfile
from backend.core.parser import load_excel
from backend.core.metrics import compute_all
from backend.charts.render_png import render_all_pngs, _slot_geometry, _render_with_aspect


def _png_size(path):
    with open(path, "rb") as f:
        f.read(8); f.read(4); f.read(4)
        return struct.unpack(">II", f.read(8))


# ---- existing legacy test (no template) ----

def test_render_all_pngs_no_template():
    b = compute_all(load_excel("resource/本周.xlsx"))
    d = tempfile.mkdtemp()
    paths = render_all_pngs(b, [], d)
    assert set(paths.keys()) == {
        "overview", "daily", "brand_combo", "brand_pie", "platform",
        "shop_heatmap", "product_horizontal", "product_table",
        "product_heatmap", "new_products", "three_weeks", "factory",
    }
    for p in paths.values():
        assert os.path.exists(p) and os.path.getsize(p) > 0


# ---- regression test for the "PPT slot aspect ratio" bug ----

TEMPLATE = "resource/2026年第二十七周周报-王凡.pptx"


def test_slot_geometry_reads_real_template():
    """Each chart slot in the real template has its own W×H. We must
    read those (not hardcode 1200×700) so the rendered PNG's aspect
    ratio matches the slot — otherwise replace_picture stretches the
    chart and the user sees a horizontally squashed brand_combo
    + a vertically oversized brand_pie."""
    geom = _slot_geometry(TEMPLATE)
    assert geom, "slot geometry must be readable from the real template"
    # The two slots we hit in the bug report — brand_combo is wide,
    # brand_pie is roughly square.
    w_bc, h_bc = geom["brand_combo"]
    w_bp, h_bp = geom["brand_pie"]
    assert w_bc / h_bc > 1.8, f"brand_combo slot should be wide, got {w_bc:.2f}x{h_bc:.2f}"
    assert 0.9 < w_bp / h_bp < 1.2, f"brand_pie slot should be ~square, got {w_bp:.2f}x{h_bp:.2f}"
    # They must NOT match (otherwise the aspect fix is invisible)
    assert abs((w_bc / h_bc) - (w_bp / h_bp)) > 0.5


def test_render_pngs_match_slot_aspect_ratios(tmp_path):
    """Each PNG's pixel aspect ratio must match its slot's inch aspect
    ratio within 1%. This is the bug that motivated the fix: every
    PNG used to come out 1200×700 (1.71:1) regardless of the slot's
    real aspect, so the PPT stretched the image and the chart looked
    distorted."""
    b = compute_all(load_excel("resource/本周.xlsx"))
    out = tmp_path / "png"
    paths = render_all_pngs(b, [], str(out), template_path=TEMPLATE)

    geom = _slot_geometry(TEMPLATE)
    for name, path in paths.items():
        if name not in geom:
            continue
        w_in, h_in = geom[name]
        slot_aspect = w_in / h_in
        pw, ph = _png_size(path)
        png_aspect = pw / ph
        # We render at width=_WIDTH_PX, height derived from slot inches.
        # Aspect parity (within rounding tolerance) is what matters.
        assert abs(png_aspect - slot_aspect) < 0.02, (
            f"{name}: PNG aspect {png_aspect:.3f} != slot aspect "
            f"{slot_aspect:.3f} ({pw}x{ph}px vs {w_in:.2f}x{h_in:.2f}in)"
        )


def test_render_with_aspect_no_slot_uses_default():
    """When no template is provided the renderer must not crash and must
    fall back to the legacy default aspect ratio."""
    from backend.charts import plotly_figures as pf
    b = compute_all(load_excel("resource/本周.xlsx"))
    fig = pf.fig_overview(b)
    out = tempfile.mktemp(suffix=".png")
    _render_with_aspect(fig, out, slot_inches=None)
    pw, ph = _png_size(out)
    os.unlink(out)
    # default is _DEFAULT_W_IN / _DEFAULT_H_IN = 10/5 = 2.0
    assert abs(pw / ph - 2.0) < 0.05


# ---- regression test for the brand_combo data viz fix ----

def test_fig_brand_combo_drops_invisible_quantity_bar():
    """fig_brand_combo used to plot 销售数量 (units of pieces) on the
    SAME y-axis as 销售额 (yuan) — the values differ by ~100x so the
    quantity bars rendered as invisible sticks. The fix drops the
    quantity bar and surfaces the number as a text annotation inside
    the chart."""
    from backend.charts import plotly_figures as pf
    b = compute_all(load_excel("resource/本周.xlsx"))
    fig = pf.fig_brand_combo(b)
    # Exactly one bar trace (销售额), one line trace (毛利率).
    bar_traces = [t for t in fig.data if t.type == "bar"]
    scatter_traces = [t for t in fig.data if t.type == "scatter"]
    assert len(bar_traces) == 1, "should have exactly one bar series (销售额)"
    assert bar_traces[0].name == "销售额"
    assert len(scatter_traces) == 1
    assert scatter_traces[0].name == "毛利率"
    # Annotations should carry the 销售数量 figures (one per brand).
    qty_anns = [a for a in fig.layout.annotations
                if a.text and "销售数量" in a.text and "件" in a.text]
    assert len(qty_anns) == len(b.brand), \
        f"expected one 销售数量 annotation per brand, got {len(qty_anns)}: {[a.text for a in qty_anns]}"