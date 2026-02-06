from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from typing import Optional

INHERITANCE_MAX_RELATIVES = 20


def inheritance_currency_hint(raw: str) -> str:
    lowered = (raw or "").lower()
    if "₽" in raw or "руб" in lowered or "rur" in lowered or "rub" in lowered:
        return "₽"
    if "$" in raw or "usd" in lowered or "дол" in lowered:
        return "$"
    if "€" in raw or "eur" in lowered:
        return "€"
    if "﷼" in raw or "rial" in lowered or "риал" in lowered or "sar" in lowered:
        return "﷼"
    return ""


def parse_count(text: Optional[str], *, maximum: int = INHERITANCE_MAX_RELATIVES) -> Optional[int]:
    raw = (text or "").strip()
    if not raw:
        return None
    if not re.fullmatch(r"\d{1,2}", raw):
        return None
    value = int(raw)
    if value < 0 or value > maximum:
        return None
    return value


def parse_money(text: Optional[str]) -> Optional[Decimal]:
    raw = (text or "").strip()
    if not raw:
        return None
    cleaned = re.sub(r"[^\d,\.]", "", raw).replace(",", ".")
    if not cleaned:
        return None
    if cleaned.count(".") > 1:
        first, *rest = cleaned.split(".")
        cleaned = first + "." + "".join(rest)
    try:
        amount = Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None
    if amount <= 0:
        return None
    return amount


def parse_money_allow_zero(text: Optional[str]) -> Optional[Decimal]:
    raw = (text or "").strip()
    if not raw:
        return None
    cleaned = re.sub(r"[^\d,\.]", "", raw).replace(",", ".")
    if not cleaned:
        return None
    if cleaned.count(".") > 1:
        first, *rest = cleaned.split(".")
        cleaned = first + "." + "".join(rest)
    try:
        amount = Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None
    if amount < 0:
        return None
    return amount


def _format_fraction(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def format_money(amount: Decimal, *, currency: str = "") -> str:
    quantized = amount.quantize(Decimal("0.01"))
    if quantized == quantized.to_integral():
        number = f"{int(quantized):,}".replace(",", " ")
    else:
        number = f"{quantized:,.2f}".replace(",", " ").replace(".", ",")
    return f"{number} {currency}".rstrip()


@dataclass(frozen=True, slots=True)
class InheritanceInput:
    deceased_gender: str
    spouse: str
    sons: int
    daughters: int
    father_alive: bool
    mother_alive: bool
    brothers: int
    sisters: int


@dataclass(frozen=True, slots=True)
class InheritanceComputation:
    fixed_shares: dict[str, Fraction]
    children_asaba_share: Fraction
    siblings_asaba_share: Fraction
    children_parts: int
    siblings_parts: int
    awl_applied: bool
    radd_applied: bool
    leftover_unassigned: Fraction


def compute_inheritance(input_data: InheritanceInput) -> InheritanceComputation:
    has_children = (input_data.sons + input_data.daughters) > 0
    siblings_count = input_data.brothers + input_data.sisters
    spouse_share = Fraction(0, 1)
    if input_data.spouse == "husband":
        spouse_share = Fraction(1, 2) if not has_children else Fraction(1, 4)
    elif input_data.spouse == "wife":
        spouse_share = Fraction(1, 4) if not has_children else Fraction(1, 8)

    fixed: dict[str, Fraction] = {}
    if spouse_share:
        fixed["spouse"] = spouse_share

    if input_data.mother_alive:
        if has_children or siblings_count >= 2:
            mother_share = Fraction(1, 6)
        else:
            if input_data.father_alive and spouse_share and not has_children:
                mother_share = (Fraction(1, 1) - spouse_share) * Fraction(1, 3)
            else:
                mother_share = Fraction(1, 3)
        fixed["mother"] = mother_share

    if input_data.father_alive and has_children:
        fixed["father"] = Fraction(1, 6)
    elif input_data.father_alive and not has_children:
        fixed["father"] = Fraction(0, 1)

    if input_data.sons == 0 and input_data.daughters > 0:
        fixed["daughters"] = (
            Fraction(1, 2) if input_data.daughters == 1 else Fraction(2, 3)
        )

    if not has_children and not input_data.father_alive and input_data.brothers == 0 and input_data.sisters > 0:
        fixed["sisters"] = Fraction(1, 2) if input_data.sisters == 1 else Fraction(2, 3)

    total_fixed = sum(fixed.values(), Fraction(0, 1))
    awl_applied = False
    radd_applied = False
    if total_fixed > 1:
        awl_applied = True
        scale = Fraction(1, 1) / total_fixed
        fixed = {key: value * scale for key, value in fixed.items()}
        total_fixed = sum(fixed.values(), Fraction(0, 1))

    remainder = Fraction(1, 1) - total_fixed

    children_asaba_share = Fraction(0, 1)
    siblings_asaba_share = Fraction(0, 1)
    children_parts = 0
    siblings_parts = 0

    if remainder > 0:
        if input_data.sons > 0:
            children_asaba_share = remainder
            children_parts = 2 * input_data.sons + input_data.daughters
            remainder = Fraction(0, 1)
        elif input_data.father_alive:
            fixed["father"] = fixed.get("father", Fraction(0, 1)) + remainder
            remainder = Fraction(0, 1)
        elif (not has_children) and (not input_data.father_alive) and input_data.brothers > 0:
            siblings_asaba_share = remainder
            siblings_parts = (
                2 * input_data.brothers + input_data.sisters if input_data.sisters else input_data.brothers
            )
            remainder = Fraction(0, 1)

    if remainder > 0:
        radd_base = {key: value for key, value in fixed.items() if key != "spouse" and value > 0}
        base_sum = sum(radd_base.values(), Fraction(0, 1))
        if base_sum > 0:
            radd_applied = True
            for key, value in radd_base.items():
                fixed[key] = value + remainder * (value / base_sum)
            remainder = Fraction(0, 1)

    leftover_unassigned = remainder if remainder > 0 else Fraction(0, 1)

    return InheritanceComputation(
        fixed_shares=fixed,
        children_asaba_share=children_asaba_share,
        siblings_asaba_share=siblings_asaba_share,
        children_parts=children_parts,
        siblings_parts=siblings_parts,
        awl_applied=awl_applied,
        radd_applied=radd_applied,
        leftover_unassigned=leftover_unassigned,
    )


def render_inheritance_calculation(
    *,
    input_data: InheritanceInput,
    estate_amount: Decimal,
    currency: str,
    extra_lines: Optional[list[str]] = None,
) -> str:
    comp = compute_inheritance(input_data)

    lines: list[str] = [
        "📊 Расчёт долей по Шариату (Коран 4:11–12, 4:176)",
        "Порядок: похороны → долги → васият (до 1/3 и не наследникам) → распределение остатка.",
        "",
    ]
    if extra_lines:
        lines.extend([item for item in extra_lines if item])
        lines.append("")

    if comp.awl_applied:
        lines.append("ℹ️ Применён ‘awl (сумма обязательных долей > 100%).")
    if comp.radd_applied:
        lines.append("ℹ️ Применён radd (остаток возвращён наследникам, кроме супруга/супруги).")
    if comp.leftover_unassigned:
        lines.append("⚠️ Остаток не распределён автоматически — лучше уточнить у учёного.")
    if comp.awl_applied or comp.radd_applied or comp.leftover_unassigned:
        lines.append("")

    fixed = comp.fixed_shares
    spouse = input_data.spouse

    if spouse in {"wife", "husband"} and fixed.get("spouse"):
        label = "🧑‍🦱 Жена" if spouse == "wife" else "🧔 Муж"
        frac = fixed["spouse"]
        amount = estate_amount * Decimal(frac.numerator) / Decimal(frac.denominator)
        lines.append(f"{label}: {_format_fraction(frac)} → {format_money(amount, currency=currency)}")

    if input_data.mother_alive and fixed.get("mother"):
        frac = fixed["mother"]
        amount = estate_amount * Decimal(frac.numerator) / Decimal(frac.denominator)
        lines.append(f"👩 Мать: {_format_fraction(frac)} → {format_money(amount, currency=currency)}")

    if input_data.father_alive and fixed.get("father") is not None:
        frac = fixed.get("father", Fraction(0, 1))
        if frac > 0:
            amount = estate_amount * Decimal(frac.numerator) / Decimal(frac.denominator)
            lines.append(f"👨 Отец: {_format_fraction(frac)} → {format_money(amount, currency=currency)}")

    if input_data.sons == 0 and input_data.daughters > 0 and fixed.get("daughters"):
        frac = fixed["daughters"]
        amount = estate_amount * Decimal(frac.numerator) / Decimal(frac.denominator)
        label = "👧 Дочь" if input_data.daughters == 1 else f"👧 Дочери ({input_data.daughters})"
        lines.append(f"{label}: {_format_fraction(frac)} → {format_money(amount, currency=currency)}")

    if (input_data.sons + input_data.daughters) == 0 and (not input_data.father_alive) and fixed.get("sisters"):
        frac = fixed["sisters"]
        amount = estate_amount * Decimal(frac.numerator) / Decimal(frac.denominator)
        label = "👩‍🦱 Родная сестра" if input_data.sisters == 1 else f"👩‍🦱 Родные сёстры ({input_data.sisters})"
        lines.append(f"{label}: {_format_fraction(frac)} → {format_money(amount, currency=currency)}")

    if comp.children_asaba_share and comp.children_parts:
        group_amount = estate_amount * Decimal(comp.children_asaba_share.numerator) / Decimal(comp.children_asaba_share.denominator)
        part_value = group_amount / Decimal(comp.children_parts)
        lines.append("")
        lines.append("👶 Дети: остаток по правилу 2:1 (сын = 2 части, дочь = 1 часть)")
        lines.append(f"Итого частей: {comp.children_parts}")
        lines.append(f"Каждая часть: {format_money(part_value, currency=currency)}")

    if comp.siblings_asaba_share and comp.siblings_parts:
        group_amount = estate_amount * Decimal(comp.siblings_asaba_share.numerator) / Decimal(comp.siblings_asaba_share.denominator)
        part_value = group_amount / Decimal(comp.siblings_parts)
        lines.append("")
        lines.append("👥 Родные братья/сёстры: остаток по правилу 2:1 (брат = 2 части, сестра = 1 часть)")
        lines.append(f"Итого частей: {comp.siblings_parts}")
        lines.append(f"Каждая часть: {format_money(part_value, currency=currency)}")

    lines.extend(
        [
            "",
            "📌 Важно: если известны долги умершего, сначала их нужно погасить.",
            "📌 Важно: это общий автоматический расчёт, сложные случаи лучше уточнить у учёного.",
        ]
    )
    return "\n".join(lines).strip()

