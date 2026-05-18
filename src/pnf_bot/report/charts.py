"""P&F chart rendering — PNG images for inclusion in the daily report.

Produces visual P&F charts matching Dorsey's conventions:
- X cells in green, O cells in red
- Bullish support line (45° upward) in solid green
- Bearish resistance line (45° downward) in solid red
- Box-level grid lines for readability
- Signal annotations at fire dates
- Title with symbol, current signal posture, and as-of date

Output is a bytes object (PNG) so the renderer can be called from the
report compiler without writing intermediate files. The HTML template
embeds these as base64-encoded data URIs.
"""

from __future__ import annotations

import io

import matplotlib

matplotlib.use("Agg")  # noqa: E402  # non-interactive backend, no display required
import matplotlib.pyplot as plt  # noqa: E402

from pnf_bot.pnf.signals import detect_signals
from pnf_bot.pnf.trendlines import find_bearish_resistance_line, find_bullish_support_line
from pnf_bot.pnf.types import PnFChart

# Color and styling — matches Dorsey's published charts closely
X_COLOR = "#2E7D32"   # green
O_COLOR = "#C62828"   # red
SUPPORT_COLOR = "#2E7D32"
RESISTANCE_COLOR = "#C62828"
GRID_COLOR = "#E0E0E0"
BACKGROUND_COLOR = "#FFFFFF"
TEXT_COLOR = "#212121"


def render_pnf_chart(
    chart: PnFChart,
    *,
    title: str | None = None,
    show_trendlines: bool = True,
    show_signals: bool = True,
    width_inches: float = 10,
    height_inches: float = 6,
    dpi: int = 100,
) -> bytes:
    """Render a P&F chart as a PNG image (bytes).

    Embeds in HTML via data URI:
        f'<img src="data:image/png;base64,{base64.b64encode(png).decode()}">'

    `show_trendlines` adds the bullish support / bearish resistance lines.
    `show_signals` annotates the chart with signal fire markers.
    """
    if not chart.columns:
        return _render_empty_chart(title or chart.symbol, width_inches, height_inches, dpi)

    fig, ax = plt.subplots(figsize=(width_inches, height_inches), dpi=dpi)
    fig.patch.set_facecolor(BACKGROUND_COLOR)
    ax.set_facecolor(BACKGROUND_COLOR)

    # Determine price range across all columns
    all_tops = [float(c.top) for c in chart.columns]
    all_bottoms = [float(c.bottom) for c in chart.columns]
    price_min = min(all_bottoms)
    price_max = max(all_tops)
    price_span = price_max - price_min
    # Guard against degenerate single-bar charts where min == max
    if price_span <= 0:
        price_padding = max(1.0, price_max * 0.05) if price_max > 0 else 1.0
    else:
        price_padding = price_span * 0.05
    ax.set_ylim(price_min - price_padding, price_max + price_padding)
    ax.set_xlim(-0.5, len(chart.columns) - 0.5)

    # Render each column
    for col_idx, column in enumerate(chart.columns):
        _render_column(ax, col_idx, column)

    # Trendlines
    if show_trendlines:
        support = find_bullish_support_line(chart)
        resistance = find_bearish_resistance_line(chart)
        if support is not None:
            _render_trendline(ax, support, len(chart.columns), SUPPORT_COLOR)
        if resistance is not None:
            _render_trendline(ax, resistance, len(chart.columns), RESISTANCE_COLOR)

    # Signal annotations
    if show_signals:
        for signal in detect_signals(chart):
            if 0 <= signal.column_index < len(chart.columns):
                color = X_COLOR if signal.is_bullish else O_COLOR
                ax.annotate(
                    signal.type.replace("_", " ").upper(),
                    xy=(signal.column_index, float(signal.price_level)),
                    xytext=(8, 8),
                    textcoords="offset points",
                    fontsize=7,
                    color=color,
                    fontweight="bold",
                    arrowprops=dict(arrowstyle="->", color=color, lw=0.5),
                )

    # Title
    if title is None:
        signals = detect_signals(chart)
        sig_summary = signals[-1].type if signals else "no signal"
        title = f"{chart.symbol}  ·  {sig_summary}  ·  {chart.columns[-1].end_date}"
    ax.set_title(title, fontsize=12, color=TEXT_COLOR, pad=10)
    ax.set_xlabel("Column", fontsize=9, color=TEXT_COLOR)
    ax.set_ylabel("Price", fontsize=9, color=TEXT_COLOR)
    ax.grid(True, color=GRID_COLOR, linestyle="-", linewidth=0.5, alpha=0.5)
    ax.tick_params(labelsize=8, colors=TEXT_COLOR)

    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png", facecolor=BACKGROUND_COLOR, edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def render_rs_chart(
    rs_chart: PnFChart,
    *,
    title: str | None = None,
    width_inches: float = 10,
    height_inches: float = 4,
    dpi: int = 100,
) -> bytes:
    """Render an RS chart. Same conventions as render_pnf_chart but typically
    a shorter height (RS is a supporting visual).
    """
    if title is None:
        title = f"Relative Strength  ·  {rs_chart.symbol}"
    return render_pnf_chart(
        rs_chart, title=title,
        width_inches=width_inches, height_inches=height_inches, dpi=dpi,
    )


# ---------------------------------------------------------------------------
# Internal rendering helpers
# ---------------------------------------------------------------------------


def _render_column(ax, col_idx: int, column) -> None:  # noqa: ANN001
    """Render a single column's Xs or Os."""
    color = X_COLOR if column.type == "X" else O_COLOR
    text = column.type
    n_boxes = column.height_boxes
    box_size = float(column.box_size)
    bottom = float(column.bottom)

    for i in range(n_boxes):
        y_center = bottom + (i + 0.5) * box_size
        ax.text(
            col_idx, y_center, text,
            ha="center", va="center",
            fontsize=10, color=color, fontweight="bold",
        )


def _render_trendline(ax, trendline, n_columns: int, color: str) -> None:  # noqa: ANN001
    """Render a 45° trendline as a line from anchor extending forward."""
    xs = list(range(trendline.anchor_column_index, n_columns))
    if not xs:
        return
    ys = [float(trendline.price_at_column(x)) for x in xs]
    ax.plot(xs, ys, color=color, linewidth=1.5, linestyle="--", alpha=0.7)


def _render_empty_chart(title: str, w: float, h: float, dpi: int) -> bytes:
    """Render a placeholder chart for stocks with no chart history."""
    fig, ax = plt.subplots(figsize=(w, h), dpi=dpi)
    fig.patch.set_facecolor(BACKGROUND_COLOR)
    ax.set_facecolor(BACKGROUND_COLOR)
    ax.text(0.5, 0.5, "no chart data", ha="center", va="center",
            fontsize=14, color="#9E9E9E", transform=ax.transAxes)
    ax.set_title(title, fontsize=12, color=TEXT_COLOR)
    ax.set_xticks([])
    ax.set_yticks([])
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png", facecolor=BACKGROUND_COLOR, edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()
