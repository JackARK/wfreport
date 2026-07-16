"""Render plotly figures to PNGs sized to match the PPT picture slots.

Each chart ends up in a specific slot on a specific slide; that slot has
its own W×H (in EMU / inches). If we always render at 1200×700 the
PPT stretches the resulting image to fill the slot, distorting the
chart. The cure is to read each slot's geometry from the template and
render each PNG at the same aspect ratio — width is fixed by a target
DPI, height is auto-computed.
"""
from pathlib import Path
from backend.charts import plotly_figures as pf

# Render resolution knobs. Width in pixels; height is computed from
# the slot's aspect ratio so the image never gets stretched.
_WIDTH_PX = 1400
_DPI = 150
_DEFAULT_W_IN, _DEFAULT_H_IN = 10.0, 5.0  # fallback for charts not in PPT


def _emu_to_in(emu):
    return emu / 914400 if emu is not None else None


def _first_picture(slide):
    """Return (w_in, h_in) of the FIRST picture shape on the slide, or
    None if there isn't one. Pictures sit at arbitrary positions in
    slide.shapes (after auto-shapes + text boxes), so we filter by
    shape_type instead of indexing."""
    for sh in slide.shapes:
        if sh.shape_type == 13:  # PICTURE
            w = _emu_to_in(sh.width)
            h = _emu_to_in(sh.height)
            if w and h:
                return (w, h)
    return None


def _slot_geometry(template_path: str):
    """Read each chart's target slot dimensions (in inches) from the
    template. Returns a dict keyed by the chart name used in build_ppt's
    png_paths mapping. Charts not present in the template fall back to
    the default aspect ratio."""
    from pptx import Presentation

    if not template_path:
        return {}

    prs = Presentation(template_path)
    S = prs.slides
    geom = {}

    # Slot layout — must mirror build_ppt() in ppt_builder.py:
    #   slide 4  (idx 3)  overview, three_weeks (2 pictures)
    #   slide 5  (idx 4)  daily
    #   slide 6  (idx 5)  brand_combo
    #   slide 7  (idx 6)  brand_pie
    #   slide 8  (idx 7)  shop_heatmap
    #   slide 9  (idx 8)  platform
    #   slide 10 (idx 9)  product_horizontal
    #   slide 11 (idx 10) factory
    #   new_products goes in the duplicate of slide 9 (same slot dims)
    def _pick(slide_idx, key):
        if len(S) <= slide_idx:
            return
        d = _first_picture(S[slide_idx])
        if d:
            geom[key] = d

    if len(S) > 3:
        pics = [sh for sh in S[3].shapes if sh.shape_type == 13]
        if len(pics) >= 2:
            geom["overview"]     = (_emu_to_in(pics[0].width), _emu_to_in(pics[0].height))
            geom["three_weeks"]  = (_emu_to_in(pics[1].width), _emu_to_in(pics[1].height))
        elif len(pics) == 1:
            geom["overview"]     = (_emu_to_in(pics[0].width), _emu_to_in(pics[0].height))

    _pick(4, "daily")
    _pick(5, "brand_combo")
    _pick(6, "brand_pie")
    _pick(7, "shop_heatmap")
    _pick(8, "platform")
    _pick(9, "product_horizontal")
    _pick(10, "factory")
    return geom


def _render_with_aspect(fig, out_path: str, slot_inches=None):
    """Render fig sized to slot_inches = (w_in, h_in). Width is fixed at
    _WIDTH_PX; height is derived so the PNG's aspect ratio matches the
    slot exactly — replace_picture() will then insert it at the slot's
    EMU dimensions and the chart won't be stretched/squished."""
    if slot_inches:
        w_in, h_in = slot_inches
        # The 200px floor only kicks in for absurdly thin strips
        # (aspect > 7:1) where kaleido refuses to render. For all
        # realistic slots the height comes straight from the slot's
        # aspect ratio, so width/height of the PNG matches the slot's
        # inch aspect within rounding.
        h_px = max(int(round(_WIDTH_PX * (h_in / w_in))), 200)
    else:
        h_px = int(_WIDTH_PX * (_DEFAULT_H_IN / _DEFAULT_W_IN))
    fig.write_image(out_path, width=_WIDTH_PX, height=h_px, scale=1)


def fig_to_png(fig, out_path: str, width: int = 1200, height: int = 700):
    """Legacy entry point kept for callers that don't care about slot
    sizing. New code should use render_all_pngs(template_path=...)."""
    fig.write_image(out_path, width=width, height=height, scale=1)


def render_all_pngs(bundle, recent_weeks, out_dir: str,
                    template_path: str | None = None) -> dict:
    """Render every chart PNG to `out_dir`. When template_path is given,
    each PNG is sized to match the slot it lands in on the PPT; the
    fallback keeps the legacy 1200×700 dimensions for tests / CLI uses
    that don't have a template at hand."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    geom = _slot_geometry(template_path) if template_path else {}
    mapping = {
        "overview": pf.fig_overview(bundle),
        "daily": pf.fig_daily(bundle),
        "brand_combo": pf.fig_brand_combo(bundle),
        "brand_pie": pf.fig_brand_pie(bundle),
        "platform": pf.fig_platform(bundle),
        "shop_heatmap": pf.fig_shop_heatmap(bundle),
        "product_horizontal": pf.fig_product_horizontal(bundle),
        "product_table": pf.fig_product_table(bundle),
        "product_heatmap": pf.fig_product_heatmap(bundle),
        "new_products": pf.fig_new_products(bundle),
        "three_weeks": pf.fig_three_weeks_table(recent_weeks),
        "factory": pf.fig_factory_table(bundle),
    }
    paths = {}
    for name, fig in mapping.items():
        p = str(out / f"{name}.png")
        _render_with_aspect(fig, p, geom.get(name))
        paths[name] = p
    return paths