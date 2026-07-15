import json

from backend.charts import plotly_figures as pf


def build_report_json(bundle, recent_weeks) -> dict:
    figs = {
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
    return {
        "overview": {k: (float(v) if isinstance(v, (int, float)) else v)
                     for k, v in bundle.overview.items()},
        "recent_weeks": recent_weeks,
        "figures": {k: json.loads(fig.to_json()) for k, fig in figs.items()},
        "tables": {
            "brand": bundle.brand.to_dict("records"),
            "platform": bundle.platform.to_dict("records"),
            "factory": bundle.factory_top5.to_dict("records"),
            "new_products": bundle.new_products.to_dict("records"),
            "product_top15": bundle.product_top15.to_dict("records"),
        },
    }
