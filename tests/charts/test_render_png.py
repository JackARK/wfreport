# tests/charts/test_render_png.py
import os, tempfile
from backend.core.parser import load_excel
from backend.core.metrics import compute_all
from backend.charts.render_png import render_all_pngs

def test_render_all_pngs():
    b = compute_all(load_excel("resource/本周.xlsx"))
    d = tempfile.mkdtemp()
    paths = render_all_pngs(b, [], d)
    assert set(paths.keys()) == {"overview","daily","brand_combo","brand_pie","platform",
                                 "shop_heatmap","product_combo","product_heatmap","new_products","three_weeks"}
    for p in paths.values():
        assert os.path.exists(p) and os.path.getsize(p) > 0
