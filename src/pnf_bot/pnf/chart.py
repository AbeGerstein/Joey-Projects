"""P&F chart construction from OHLC data.

Implements Dorsey's high/low method:

For each bar (one trading day):
    If currently in an X column (uptrend):
        If today's HIGH is >= one box above the column top:
            extend the X column up to the highest box reachable from today's high
        Else if today's LOW is >= reversal_boxes (default 3) below the column top:
            reverse: end the X column, start a new O column starting one box below
            the X top and extending down to today's low (in boxes)
        Else:
            no change to the chart today
    If currently in an O column (downtrend):
        Symmetric.

Edge case (Dorsey's rule): if a bar could BOTH extend the current column AND
trigger a reversal (rare; would require a very wide intraday range), extension
takes precedence — reversal is only considered if the bar cannot extend.

Box size for a column is locked at the column's start. It does NOT change
mid-column even if price crosses a traditional-scaling tier boundary.
This implementation enforces that rule.
"""

from __future__ import annotations

from decimal import Decimal

import pandas as pd

from pnf_bot.pnf.box_scaling import BoxScaling, TraditionalScaling
from pnf_bot.pnf.types import Column, ColumnType, PnFChart


def construct_chart(
    symbol: str,
    ohlc: pd.DataFrame,
    scaling: BoxScaling | None = None,
    reversal_boxes: int = 3,
) -> PnFChart:
    """Build a P&F chart from a DataFrame of daily OHLC.

    Arguments:
        symbol: the security's identifier (stored on the resulting PnFChart).
        ohlc: a pandas DataFrame indexed by trade date with columns
              "open", "high", "low", "close". "volume" is accepted but
              not used. The index must be sortable (date or pd.Timestamp);
              the function sorts ascending internally if not already.
        scaling: a BoxScaling strategy. Defaults to TraditionalScaling().
        reversal_boxes: number of boxes required to start a new column
                        against the prevailing direction. Project default 3.

    Returns:
        A PnFChart whose `columns` reflect the OHLC sequence.

    Raises:
        ValueError if the DataFrame is empty or missing required columns.
    """
    if scaling is None:
        scaling = TraditionalScaling()

    required = {"high", "low"}
    missing = required - set(ohlc.columns)
    if missing:
        raise ValueError(f"OHLC DataFrame missing required columns: {sorted(missing)}")
    if ohlc.empty:
        raise ValueError("Cannot construct a P&F chart from empty OHLC")

    # Ensure ascending date order
    df = ohlc.sort_index()

    builder = _ChartBuilder(scaling=scaling, reversal_boxes=reversal_boxes)
    for trade_date, row in df.iterrows():
        builder.process_bar(
            trade_date=_to_date(trade_date),
            high=Decimal(str(row["high"])),
            low=Decimal(str(row["low"])),
        )

    completed = builder.finalize()
    return PnFChart(
        symbol=symbol,
        columns=tuple(completed),
        box_scaling_label=scaling.label(),
        reversal_boxes=reversal_boxes,
    )


def _to_date(idx_value):  # noqa: ANN001, ANN202
    """Coerce a pandas index value to a date."""
    if hasattr(idx_value, "date"):
        return idx_value.date()
    return idx_value


# ---------------------------------------------------------------------------
# Internal builder — stateful column construction
# ---------------------------------------------------------------------------


class _ChartBuilder:
    """Stateful P&F chart builder.

    Maintains the current (in-progress) column and the list of completed
    columns. Each bar fed in via `process_bar` either extends the current
    column, reverses to a new column, or makes no change.
    """

    def __init__(self, scaling: BoxScaling, reversal_boxes: int) -> None:
        self._scaling = scaling
        self._reversal_boxes = reversal_boxes
        self._completed: list[Column] = []
        # Current column state (mutable during build, then frozen on completion)
        self._cur_type: ColumnType | None = None
        self._cur_top: Decimal | None = None
        self._cur_bottom: Decimal | None = None
        self._cur_box: Decimal | None = None
        self._cur_start: object | None = None
        self._cur_end: object | None = None

    def process_bar(self, trade_date, high: Decimal, low: Decimal) -> None:  # noqa: ANN001
        if self._cur_type is None:
            self._start_initial_column(trade_date, high, low)
            return

        assert self._cur_top is not None
        assert self._cur_bottom is not None
        assert self._cur_box is not None

        if self._cur_type == "X":
            self._process_x_column_bar(trade_date, high, low)
        else:
            self._process_o_column_bar(trade_date, high, low)

    def finalize(self) -> list[Column]:
        if self._cur_type is not None:
            self._commit_current()
        return self._completed

    # ------------------------------------------------------------------
    # Initial column
    # ------------------------------------------------------------------

    def _start_initial_column(
        self, trade_date, high: Decimal, low: Decimal  # noqa: ANN001
    ) -> None:
        """Bootstrap the first column from the first bar.

        Convention: start with an X column. The chart's first column type is
        somewhat arbitrary — we pick X by convention. Subsequent bars will
        quickly reverse to an O column if price action is bearish.
        """
        scaling = self._scaling
        # Anchor the column at the snapped low (the lowest box that contains today's low)
        bottom = scaling.snap_floor(low)
        # Top is the highest box reachable from today's high
        top = scaling.snap_floor(high)
        if top < bottom:
            top = bottom
        self._cur_type = "X"
        self._cur_bottom = bottom
        self._cur_top = top
        self._cur_box = scaling.box_size_at(bottom)
        self._cur_start = trade_date
        self._cur_end = trade_date

    # ------------------------------------------------------------------
    # X column processing
    # ------------------------------------------------------------------

    def _process_x_column_bar(self, trade_date, high: Decimal, low: Decimal) -> None:  # noqa: ANN001
        assert self._cur_top is not None and self._cur_box is not None
        scaling = self._scaling
        box = self._cur_box
        next_x = self._cur_top + box

        # Can we extend up? Yes if today's high is at or above the next-box level.
        if high >= next_x:
            new_top = self._snap_floor_with_box(high, box)
            self._cur_top = new_top
            self._cur_end = trade_date
            return

        # Can we reverse? Yes if today's low is at least reversal_boxes below the top.
        reversal_threshold = self._cur_top - (Decimal(self._reversal_boxes) * box)
        if low <= reversal_threshold:
            self._commit_current()
            # Start new O column: top is one box below the X column's top
            new_top = self._cur_top_for_reversal_o(box)
            new_bottom = self._snap_floor_with_box(low, box)
            if new_bottom > new_top:
                new_bottom = new_top
            self._cur_type = "O"
            self._cur_top = new_top
            self._cur_bottom = new_bottom
            # New column's box size: re-evaluate from current price (use new_top as ref)
            self._cur_box = scaling.box_size_at(new_top)
            # Re-anchor bottom to the new box size
            self._cur_bottom = self._snap_floor_with_box(low, self._cur_box)
            if self._cur_bottom > self._cur_top:
                self._cur_bottom = self._cur_top
            self._cur_start = trade_date
            self._cur_end = trade_date
            return

        # Otherwise: no change
        return

    # ------------------------------------------------------------------
    # O column processing
    # ------------------------------------------------------------------

    def _process_o_column_bar(self, trade_date, high: Decimal, low: Decimal) -> None:  # noqa: ANN001
        assert self._cur_bottom is not None and self._cur_box is not None
        scaling = self._scaling
        box = self._cur_box
        next_o = self._cur_bottom - box

        # Can we extend down? Yes if today's low is at or below the next-box level.
        if low <= next_o:
            new_bottom = self._snap_floor_with_box(low, box)
            self._cur_bottom = new_bottom
            self._cur_end = trade_date
            return

        # Can we reverse? Yes if today's high is at least reversal_boxes above the bottom.
        reversal_threshold = self._cur_bottom + (Decimal(self._reversal_boxes) * box)
        if high >= reversal_threshold:
            self._commit_current()
            new_bottom = self._cur_bottom_for_reversal_x(box)
            new_top = self._snap_floor_with_box(high, box)
            if new_top < new_bottom:
                new_top = new_bottom
            self._cur_type = "X"
            self._cur_bottom = new_bottom
            self._cur_top = new_top
            self._cur_box = scaling.box_size_at(new_bottom)
            # Re-anchor top with new box size
            self._cur_top = self._snap_floor_with_box(high, self._cur_box)
            if self._cur_top < self._cur_bottom:
                self._cur_top = self._cur_bottom
            self._cur_start = trade_date
            self._cur_end = trade_date
            return

        return

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _commit_current(self) -> None:
        """Freeze the current column and append to the completed list."""
        assert self._cur_type is not None
        assert self._cur_top is not None
        assert self._cur_bottom is not None
        assert self._cur_box is not None
        assert self._cur_start is not None
        assert self._cur_end is not None

        column = Column(
            type=self._cur_type,
            top=self._cur_top,
            bottom=self._cur_bottom,
            box_size=self._cur_box,
            start_date=self._cur_start,
            end_date=self._cur_end,
        )
        self._completed.append(column)

    def _cur_top_for_reversal_o(self, box: Decimal) -> Decimal:
        """Top of the new O column on reversal = X column top - 1 box."""
        assert self._cur_top is not None
        return self._cur_top - box

    def _cur_bottom_for_reversal_x(self, box: Decimal) -> Decimal:
        """Bottom of the new X column on reversal = O column bottom + 1 box."""
        assert self._cur_bottom is not None
        return self._cur_bottom + box

    def _snap_floor_with_box(self, price: Decimal, box: Decimal) -> Decimal:
        """Snap a price down to the nearest box boundary, using a fixed box size.

        Different from `BoxScaling.snap_floor` because here the box size is
        FIXED (locked in at the column's start) rather than re-evaluated from
        the price. This is the rule that prevents tier-crossing mid-column.
        """
        from decimal import ROUND_FLOOR

        n = (price / box).quantize(Decimal("1"), rounding=ROUND_FLOOR)
        return n * box
