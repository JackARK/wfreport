from pathlib import Path
from backend.charts import plotly_figures as pf


def fig_to_png(fig, out_path: str, width: int = 1200, height: int = 700):
    fig.write_image(out_path, width=width, height=height, scale=1)


def render_all_pngs(bundle, recent_weeks, out_dir: str) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    mapping = {
        "overview": pf.fig_overview(bundle),
        "daily": pf.fig_daily(bundle),
        "brand_combo": pf.fig_brand_combo(bundle),
        "brand_pie": pf.fig_brand_pie(bundle),
        "platform": pf.fig_platform(bundle),
        "shop_heatmap": pf.fig_shop_heatmap(bundle),
        "product_combo": pf.fig_product_combo(bundle),
        "product_heatmap": pf.fig_product_heatmap(bundle),
        "new_products": pf.fig_new_products(bundle),
        "three_weeks": pf.fig_three_weeks_table(recent_weeks),
    }
    paths = {}
    for name, fig in mapping.items():
        p = str(out / f"{name}.png")
        fig_to_png(fig, p)
        paths[name] = p
    return paths
