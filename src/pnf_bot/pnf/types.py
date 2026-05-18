"""Data structures for Point & Figure charts.

A P&F chart is a sequence of Columns, each holding either Xs (rising) or
Os (falling). Each column has a top and bottom price level, a fixed box
size used to construct it, and start/end dates spanning when price activity
contributed to the column.

All prices use Decimal to avoid floating-point drift. The chart's
correctness depends on exact arithmetic at box boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

ColumnType = Literal["X", "O"]


@dataclass(frozen=True)
class Column:
    """A single column of Xs or Os in a P&F chart.

    Convention:
    - `top` is the price level of the topmost box (highest X or topmost O).
    - `bottom` is the price level of the bottommost box (lowest X or bottom-most O).
    - For an X column, the highest box is the most recently plotted X.
    - For an O column, the bottommost box is the most recently plotted O.
    - `box_size` is fixed at the column's start and does NOT change mid-column,
      even if price crosses a traditional-scaling tier boundary. This matches
      Dorsey's rule (re-evaluate box size only when starting a new column).
    """

    type: ColumnType
    top: Decimal
    bottom: Decimal
    box_size: Decimal
    start_date: date
    end_date: date

    def __post_init__(self) -> None:
        if self.top < self.bottom:
            raise ValueError(
                f"Column top ({self.top}) must be >= bottom ({self.bottom})"
            )
        if self.box_size <= Decimal("0"):
            raise ValueError(f"Column box_size ({self.box_size}) must be positive")
        if self.start_date > self.end_date:
            raise ValueError(
                f"Column start_date ({self.start_date}) must be <= end_date ({self.end_date})"
            )

    @property
    def height_boxes(self) -> int:
        """Number of boxes in the column (inclusive of both ends).

        For an X column with X plotted at $100 only, height = 1.
        For an X column with X plotted at $100, $101, $102 (box=$1), height = 3.
        """
        span = self.top - self.bottom
        n = span / self.box_size
        # Round to nearest integer to avoid floating-point quantization issues
        return int(n.quantize(Decimal("1"))) + 1


@dataclass(frozen=True)
class PnFChart:
    """A complete P&F chart for a single security.

    The columns are ordered chronologically — `columns[0]` is the oldest,
    `columns[-1]` is the current column being formed by recent price action.

    `box_scaling_label` is a free-form string identifying the scaling used
    (e.g., "traditional", "percentage:6.5"). Useful for debugging and
    serialization; doesn't drive any logic.

    `reversal_boxes` is the number of boxes against the prevailing direction
    required to start a new column. Dorsey's default and our project default
    is 3.
    """

    symbol: str
    columns: tuple[Column, ...]
    box_scaling_label: str
    reversal_boxes: int = 3

    @property
    def current_column(self) -> Column | None:
        """The most recent column, or None if the chart is empty."""
        return self.columns[-1] if self.columns else None

    @property
    def column_count(self) -> int:
        return len(self.columns)
