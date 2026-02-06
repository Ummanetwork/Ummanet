from __future__ import annotations

from decimal import Decimal
from fractions import Fraction

from app.services.inheritance.calculator import (
    InheritanceInput,
    compute_inheritance,
    parse_money,
    parse_money_allow_zero,
)


def test_inheritance_spouse_and_children_distribution() -> None:
    comp = compute_inheritance(
        InheritanceInput(
            deceased_gender="male",
            spouse="wife",
            sons=2,
            daughters=1,
            father_alive=False,
            mother_alive=False,
            brothers=0,
            sisters=0,
        )
    )
    assert comp.fixed_shares["spouse"] == Fraction(1, 8)
    assert comp.children_asaba_share == Fraction(7, 8)
    assert comp.children_parts == 5


def test_inheritance_mother_one_third_of_remainder_case() -> None:
    # No children, spouse exists, both parents alive:
    # mother gets 1/3 of remainder after spouse share (common faraid case).
    comp = compute_inheritance(
        InheritanceInput(
            deceased_gender="male",
            spouse="wife",
            sons=0,
            daughters=0,
            father_alive=True,
            mother_alive=True,
            brothers=0,
            sisters=0,
        )
    )
    assert comp.fixed_shares["spouse"] == Fraction(1, 4)
    assert comp.fixed_shares["mother"] == Fraction(1, 4)
    assert comp.fixed_shares["father"] == Fraction(1, 2)


def test_inheritance_awl_scaling_applied_when_fixed_sum_exceeds_one() -> None:
    # Husband (1/4) + mother (1/6) + father (1/6) + 2 daughters (2/3) => 15/12 > 1 => awl
    comp = compute_inheritance(
        InheritanceInput(
            deceased_gender="female",
            spouse="husband",
            sons=0,
            daughters=2,
            father_alive=True,
            mother_alive=True,
            brothers=0,
            sisters=0,
        )
    )
    assert comp.awl_applied is True
    assert sum(comp.fixed_shares.values(), Fraction(0, 1)) == Fraction(1, 1)


def test_parse_money_rules() -> None:
    assert parse_money("0") is None
    assert parse_money_allow_zero("0") == Decimal("0")

