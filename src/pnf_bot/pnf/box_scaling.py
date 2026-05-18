"""Box scaling strategies for Point & Figure charts.

Two strategies are supported:

1. **TraditionalScaling** — Dorsey's price-tiered table from
   *Point and Figure Charting*. Box size depends on the security's price.
   Used for all stock price charts.

2. **PercentageScaling** — each box is a fixed percentage of price. Boxes
   are exponentially spaced (multiplicative rather than additive). Used for
   Relative Strength charts (6.5% for stocks, 3.25% for funds) and for
   very-high-priced indexes where traditional scaling becomes coarse.

Both strategies expose the same interface so the chart construction
algorithm can be agnostic to which scaling is in use.

Decimal arithmetic is used throughout to avoid floating-point drift at
box boundaries.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal


class BoxScaling(ABC):
    """Abstract interface for box scaling strategies.

    The chart construction algorithm calls these methods to determine box
    sizes and snap prices to box boundaries.
    """

    @abstractmethod
    def label(self) -> str:
        """A free-form identifier for the strategy. Stored on PnFChart."""

    @abstractmethod
    def box_size_at(self, price: Decimal) -> Decimal:
        """Return the box size appropriate for a security at the given price."""

    @abstractmethod
    def snap_floor(self, price: Decimal) -> Decimal:
        """Snap a price DOWN to the nearest box boundary.

        For traditional scaling at $1 boxes, snap_floor($100.50) = $100.
        For percentage scaling, snaps to the largest box-boundary below price.
        """

    @abstractmethod
    def snap_ceiling(self, price: Decimal) -> Decimal:
        """Snap a price UP to the nearest box boundary.

        For traditional scaling at $1 boxes, snap_ceiling($100.50) = $101.
        For percentage scaling, snaps to the smallest box-boundary above price.
        """

    @abstractmethod
    def box_above(self, price: Decimal) -> Decimal:
        """Return the price level of the box immediately above `price`."""

    @abstractmethod
    def box_below(self, price: Decimal) -> Decimal:
        """Return the price level of the box immediately below `price`."""

    @abstractmethod
    def boxes_between(self, lower: Decimal, upper: Decimal) -> int:
        """Number of full boxes strictly between `lower` and `upper`.

        Useful for the reversal check: "is today's low at least 3 boxes
        below the current X column's top?"
        """


# ---------------------------------------------------------------------------
# Traditional scaling — Dorsey's price-tiered table
# ---------------------------------------------------------------------------


class TraditionalScaling(BoxScaling):
    """Dorsey's standard price-tiered scaling for stock price charts.

    Table from *Point and Figure Charting* (4th edition):

        Price range          Box size
        Under $5             $0.25
        $5  - $20            $0.50
        $20 - $100           $1.00
        $100 - $200          $2.00
        $200 - $500          $4.00
        $500 - $1,000        $5.00
        Over $1,000          $10.00

    Tier boundaries: $5, $20, $100, $200, $500, $1000. The tier "Under $5"
    applies strictly to prices below $5.00 — at exactly $5 the box size is
    $0.50.

    Per Dorsey's rule, the box size for a column is fixed at the column's
    start and does not change mid-column even if price crosses a tier. This
    rule is enforced at the chart construction level, not here — this
    strategy answers "what box size for THIS price right now".
    """

    # Tiers as (upper_bound_exclusive, box_size). The last tier is open-ended.
    _TIERS: tuple[tuple[Decimal, Decimal], ...] = (
        (Decimal("5"), Decimal("0.25")),
        (Decimal("20"), Decimal("0.50")),
        (Decimal("100"), Decimal("1.00")),
        (Decimal("200"), Decimal("2.00")),
        (Decimal("500"), Decimal("4.00")),
        (Decimal("1000"), Decimal("5.00")),
    )
    _TOP_TIER_BOX: Decimal = Decimal("10.00")

    def label(self) -> str:
        return "traditional"

    def box_size_at(self, price: Decimal) -> Decimal:
        if price < Decimal("0"):
            raise ValueError(f"Cannot compute box size for negative price {price}")
        for upper_excl, box in self._TIERS:
            if price < upper_excl:
                return box
        return self._TOP_TIER_BOX

    def snap_floor(self, price: Decimal) -> Decimal:
        box = self.box_size_at(price)
        n = (price / box).quantize(Decimal("1"), rounding=ROUND_FLOOR)
        return n * box

    def snap_ceiling(self, price: Decimal) -> Decimal:
        box = self.box_size_at(price)
        floor = self.snap_floor(price)
        return floor if floor == price else floor + box

    def box_above(self, price: Decimal) -> Decimal:
        box = self.box_size_at(price)
        return price + box

    def box_below(self, price: Decimal) -> Decimal:
        box = self.box_size_at(price)
        return price - box

    def boxes_between(self, lower: Decimal, upper: Decimal) -> int:
        """Number of boxes between two prices, using the box size at the lower price.

        Caveat: traditional scaling has variable box sizes across tiers, but
        for the chart construction algorithm we typically use this function
        within a single column where box size is fixed. The result is
        computed using the box size at the lower endpoint.
        """
        if upper < lower:
            return 0
        box = self.box_size_at(lower)
        return int(((upper - lower) / box).quantize(Decimal("1"), rounding=ROUND_FLOOR))


# ---------------------------------------------------------------------------
# Percentage scaling — for RS charts and high-priced securities
# ---------------------------------------------------------------------------


class PercentageScaling(BoxScaling):
    """Percentage box scaling — each box is a fixed multiplicative step.

    Used for Relative Strength charts. Project conventions:
    - 6.5% for stock RS charts (PercentageScaling(Decimal("0.065")))
    - 3.25% for fund RS charts (PercentageScaling(Decimal("0.0325")))

    Box boundaries are at base * (1 + pct)^n for integer n, anchored to a
    base price (default $1). Boxes grow with price.

    Math: a box at level p has top p * (1 + pct). The "n-th box up" from
    price p is p * (1 + pct)^n; "n-th box down" is p / (1 + pct)^n.
    """

    def __init__(self, percentage: Decimal, base: Decimal = Decimal("1")) -> None:
        if percentage <= Decimal("0"):
            raise ValueError(f"Percentage must be positive, got {percentage}")
        if base <= Decimal("0"):
            raise ValueError(f"Base must be positive, got {base}")
        self._pct = percentage
        self._multiplier = Decimal("1") + percentage
        self._base = base

    def label(self) -> str:
        # Format percentage as "6.5" rather than "0.065" for readability
        pct_str = (self._pct * Decimal("100")).quantize(Decimal("0.01")).normalize()
        return f"percentage:{pct_str}"

    def box_size_at(self, price: Decimal) -> Decimal:
        """Box size at a given price = price * percentage.

        Note: this is the "box height" at that level. Boxes are NOT equal in
        absolute size — they grow with price. The chart construction uses
        this when locking in a box size at the start of a column.
        """
        if price <= Decimal("0"):
            raise ValueError(f"Cannot compute box size for non-positive price {price}")
        return price * self._pct

    def snap_floor(self, price: Decimal) -> Decimal:
        """Snap a price down to the nearest box boundary.

        Box boundaries are at base * (1 + pct)^n. Solve for the largest
        integer n such that base * (1+pct)^n <= price.

        Uses Decimal's natural ln/exp via Decimal arithmetic — but Decimal
        doesn't have ln/exp natively, so we use float conversion for the
        log step. Precision loss here is acceptable since we snap to an
        integer n and reconstruct with Decimal arithmetic afterward.
        """
        if price <= self._base:
            return self._base
        ratio = float(price / self._base)
        mult = float(self._multiplier)
        # n such that base * mult^n <= price
        from math import log

        n = int(log(ratio) / log(mult))
        # Reconstruct in Decimal arithmetic
        snapped = self._base * (self._multiplier ** n)
        # Handle floating-point edge: if reconstruction overshoots due to
        # accumulated error, step back one box
        while snapped > price:
            n -= 1
            snapped = self._base * (self._multiplier ** n)
        return snapped

    def snap_ceiling(self, price: Decimal) -> Decimal:
        if price <= self._base:
            return self._base
        floor = self.snap_floor(price)
        if floor == price:
            return floor
        return floor * self._multiplier

    def box_above(self, price: Decimal) -> Decimal:
        # Assume price is already a box boundary; return next box up.
        return price * self._multiplier

    def box_below(self, price: Decimal) -> Decimal:
        return price / self._multiplier

    def boxes_between(self, lower: Decimal, upper: Decimal) -> int:
        if upper <= lower:
            return 0
        from math import log

        ratio = float(upper / lower)
        mult = float(self._multiplier)
        return max(0, int(log(ratio) / log(mult)))
