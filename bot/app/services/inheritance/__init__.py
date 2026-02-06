"""Inheritance (faraid) calculation services."""

from .calculator import (
    INHERITANCE_MAX_RELATIVES,
    InheritanceComputation,
    InheritanceInput,
    inheritance_currency_hint,
    parse_count,
    parse_money,
    parse_money_allow_zero,
    render_inheritance_calculation,
)

__all__ = [
    "INHERITANCE_MAX_RELATIVES",
    "InheritanceComputation",
    "InheritanceInput",
    "inheritance_currency_hint",
    "parse_count",
    "parse_money",
    "parse_money_allow_zero",
    "render_inheritance_calculation",
]

