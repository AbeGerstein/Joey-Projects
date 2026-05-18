"""Tests for box scaling strategies."""

from __future__ import annotations

from decimal import Decimal

import pytest

from pnf_bot.pnf.box_scaling import PercentageScaling, TraditionalScaling

# ---------------------------------------------------------------------------
# TraditionalScaling — Dorsey's price-tiered table
# ---------------------------------------------------------------------------


class TestTraditionalScaling:
    """Tests for Dorsey's standard price-tiered box scaling."""

    @pytest.fixture
    def scaling(self) -> TraditionalScaling:
        return TraditionalScaling()

    @pytest.mark.parametrize(
        "price,expected_box",
        [
            ("0.50", "0.25"),    # under $5 → $0.25
            ("4.99", "0.25"),    # still under $5
            ("5.00", "0.50"),    # exactly $5 → $0.50 tier
            ("19.99", "0.50"),   # just under $20
            ("20.00", "1.00"),   # exactly $20 → $1 tier
            ("50.00", "1.00"),   # mid-range
            ("99.99", "1.00"),   # just under $100
            ("100.00", "2.00"),  # exactly $100 → $2 tier
            ("150.00", "2.00"),
            ("200.00", "4.00"),  # exactly $200 → $4 tier
            ("400.00", "4.00"),
            ("500.00", "5.00"),  # exactly $500 → $5 tier
            ("999.99", "5.00"),
            ("1000.00", "10.00"),  # exactly $1000 → $10 tier
            ("5000.00", "10.00"),  # very high price
        ],
    )
    def test_box_size_at_tiers(
        self, scaling: TraditionalScaling, price: str, expected_box: str
    ) -> None:
        assert scaling.box_size_at(Decimal(price)) == Decimal(expected_box)

    def test_box_size_at_negative_price_raises(self, scaling: TraditionalScaling) -> None:
        with pytest.raises(ValueError, match="negative price"):
            scaling.box_size_at(Decimal("-1"))

    def test_snap_floor_at_box_boundary(self, scaling: TraditionalScaling) -> None:
        """Snapping a price already on a box boundary returns the same price."""
        assert scaling.snap_floor(Decimal("50.00")) == Decimal("50.00")

    def test_snap_floor_between_boxes(self, scaling: TraditionalScaling) -> None:
        """Snapping between boxes returns the lower boundary."""
        assert scaling.snap_floor(Decimal("50.50")) == Decimal("50.00")
        assert scaling.snap_floor(Decimal("50.99")) == Decimal("50.00")

    def test_snap_ceiling_at_box_boundary(self, scaling: TraditionalScaling) -> None:
        assert scaling.snap_ceiling(Decimal("50.00")) == Decimal("50.00")

    def test_snap_ceiling_between_boxes(self, scaling: TraditionalScaling) -> None:
        assert scaling.snap_ceiling(Decimal("50.01")) == Decimal("51.00")
        assert scaling.snap_ceiling(Decimal("50.99")) == Decimal("51.00")

    def test_box_above(self, scaling: TraditionalScaling) -> None:
        assert scaling.box_above(Decimal("50.00")) == Decimal("51.00")
        assert scaling.box_above(Decimal("3.00")) == Decimal("3.25")
        assert scaling.box_above(Decimal("150.00")) == Decimal("152.00")

    def test_box_below(self, scaling: TraditionalScaling) -> None:
        assert scaling.box_below(Decimal("50.00")) == Decimal("49.00")
        assert scaling.box_below(Decimal("3.00")) == Decimal("2.75")

    def test_boxes_between(self, scaling: TraditionalScaling) -> None:
        """Number of boxes between two prices at the same tier."""
        assert scaling.boxes_between(Decimal("50.00"), Decimal("55.00")) == 5
        assert scaling.boxes_between(Decimal("50.00"), Decimal("50.00")) == 0
        assert scaling.boxes_between(Decimal("100.00"), Decimal("110.00")) == 5  # $2 boxes

    def test_label(self, scaling: TraditionalScaling) -> None:
        assert scaling.label() == "traditional"


# ---------------------------------------------------------------------------
# PercentageScaling — for RS charts
# ---------------------------------------------------------------------------


class TestPercentageScaling:
    """Tests for percentage box scaling."""

    @pytest.fixture
    def stock_rs(self) -> PercentageScaling:
        """The 6.5% scaling used for stock RS charts."""
        return PercentageScaling(Decimal("0.065"))

    @pytest.fixture
    def fund_rs(self) -> PercentageScaling:
        """The 3.25% scaling used for fund RS charts."""
        return PercentageScaling(Decimal("0.0325"))

    def test_box_size_at_grows_with_price(self, stock_rs: PercentageScaling) -> None:
        """A 6.5% box at $100 = $6.50; at $200 = $13."""
        assert stock_rs.box_size_at(Decimal("100")) == Decimal("6.5")
        assert stock_rs.box_size_at(Decimal("200")) == Decimal("13.0")

    def test_box_above_is_multiplicative(self, stock_rs: PercentageScaling) -> None:
        """Next box up at $100 with 6.5% boxes = $106.50."""
        assert stock_rs.box_above(Decimal("100")) == Decimal("106.5")

    def test_box_below_is_multiplicative(self, stock_rs: PercentageScaling) -> None:
        """Box below at $100 with 6.5% boxes = $100 / 1.065 ≈ $93.90."""
        result = stock_rs.box_below(Decimal("100"))
        expected = Decimal("100") / Decimal("1.065")
        assert abs(result - expected) < Decimal("0.0001")

    def test_boxes_between_log_spaced(self, stock_rs: PercentageScaling) -> None:
        """At 6.5% boxes, going from 100 to 130 covers ~4 boxes.

        log(1.30) / log(1.065) ≈ 4.17 → 4 full boxes.
        """
        assert stock_rs.boxes_between(Decimal("100"), Decimal("130")) == 4

    def test_boxes_between_zero_for_equal(self, stock_rs: PercentageScaling) -> None:
        assert stock_rs.boxes_between(Decimal("100"), Decimal("100")) == 0

    def test_boxes_between_zero_for_inverted(self, stock_rs: PercentageScaling) -> None:
        assert stock_rs.boxes_between(Decimal("130"), Decimal("100")) == 0

    def test_invalid_percentage_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            PercentageScaling(Decimal("0"))
        with pytest.raises(ValueError, match="positive"):
            PercentageScaling(Decimal("-0.065"))

    def test_invalid_base_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            PercentageScaling(Decimal("0.065"), base=Decimal("0"))

    def test_label_stock_rs(self, stock_rs: PercentageScaling) -> None:
        # 6.5% → "percentage:6.5"
        label = stock_rs.label()
        assert label.startswith("percentage:")
        # Ensure the percentage portion is recognizable
        assert "6.5" in label

    def test_label_fund_rs(self, fund_rs: PercentageScaling) -> None:
        assert "3.25" in fund_rs.label()

    def test_snap_floor_idempotent_on_boundary(self, stock_rs: PercentageScaling) -> None:
        """Snapping a value already on a box boundary should return it unchanged."""
        # Build a known box boundary: base * (1.065)^n
        boundary = Decimal("1") * (Decimal("1.065") ** 10)
        snapped = stock_rs.snap_floor(boundary)
        # Allow tiny rounding tolerance
        assert abs(snapped - boundary) < Decimal("0.0001")

    def test_snap_ceiling_above_floor(self, stock_rs: PercentageScaling) -> None:
        """Ceiling is always >= floor for any price > base."""
        for price_str in ["100", "150.50", "1000", "5"]:
            price = Decimal(price_str)
            assert stock_rs.snap_ceiling(price) >= stock_rs.snap_floor(price)


# ---------------------------------------------------------------------------
# Cross-strategy invariants
# ---------------------------------------------------------------------------


class TestBoxScalingInvariants:
    """Invariants that must hold for any BoxScaling implementation."""

    @pytest.fixture(params=[TraditionalScaling(), PercentageScaling(Decimal("0.065"))])
    def scaling(self, request):  # noqa: ANN001, ANN202
        return request.param

    def test_box_above_then_below_is_identity(self, scaling) -> None:  # noqa: ANN001
        """box_below(box_above(p)) should return approximately p for box-aligned p.

        Only checked for prices in a reasonable range to avoid edge cases.
        """
        for price_str in ["50", "100", "200"]:
            p = Decimal(price_str)
            up = scaling.box_above(p)
            back = scaling.box_below(up)
            # Allow tiny rounding tolerance
            assert abs(back - p) < Decimal("0.01")

    def test_box_size_is_positive(self, scaling) -> None:  # noqa: ANN001
        for price_str in ["1", "10", "100", "500"]:
            assert scaling.box_size_at(Decimal(price_str)) > Decimal("0")
