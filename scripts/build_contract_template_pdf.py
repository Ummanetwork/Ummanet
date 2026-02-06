# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
import math
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

ROOT_DIR = Path(__file__).resolve().parents[1]
TEMPLATES_DIR = ROOT_DIR / "docs" / "шаблоны"

PRIMARY = colors.HexColor("#0b4f4f")
ACCENT = colors.HexColor("#c9a227")
ACCENT_HEX = "#c9a227"


def _register_fonts() -> None:
    fonts_dir = Path("C:/Windows/Fonts")
    pdfmetrics.registerFont(TTFont("TimesNewRoman", fonts_dir / "times.ttf"))
    pdfmetrics.registerFont(TTFont("TimesNewRoman-Bold", fonts_dir / "timesbd.ttf"))
    pdfmetrics.registerFont(TTFont("TimesNewRoman-Italic", fonts_dir / "timesi.ttf"))
    segui_symbol = fonts_dir / "seguisym.ttf"
    if segui_symbol.exists():
        pdfmetrics.registerFont(TTFont("SegoeUISymbol", segui_symbol))


def _draw_frame(c: canvas.Canvas, _doc: SimpleDocTemplate) -> None:
    width, height = A4
    margin = 36
    inner = margin + 6

    c.saveState()
    c.setStrokeColor(PRIMARY)
    c.setLineWidth(1.6)
    c.rect(margin, margin, width - 2 * margin, height - 2 * margin)

    c.setStrokeColor(ACCENT)
    c.setLineWidth(0.8)
    c.rect(inner, inner, width - 2 * inner, height - 2 * inner)

    c.setFillColor(ACCENT)
    for x, y in [
        (margin, margin),
        (width - margin, margin),
        (margin, height - margin),
        (width - margin, height - margin),
    ]:
        c.circle(x, y, 2.2, stroke=0, fill=1)

    c.setStrokeColor(colors.Color(0.85, 0.82, 0.75))
    c.setLineWidth(0.6)
    cx, cy = width / 2, height / 2
    r_outer, r_inner = 70, 30
    points = []
    for i in range(16):
        angle = i * math.pi / 8
        r = r_outer if i % 2 == 0 else r_inner
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    for i in range(len(points)):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % len(points)]
        c.line(x1, y1, x2, y2)

    c.setStrokeColor(colors.Color(0.75, 0.75, 0.75))
    c.setLineWidth(0.5)
    c.line(margin + 40, margin + 18, width - margin - 40, margin + 18)
    c.restoreState()


PLACEHOLDER_RE = re.compile(r"\{\{\s*[^}]+\s*\}\}")


def _highlight_placeholders(text: str) -> str:
    def repl(match: re.Match) -> str:
        token = match.group(0)
        return f"<font color='{ACCENT_HEX}'><b>{token}</b></font>"

    return PLACEHOLDER_RE.sub(repl, text)


def _build_styles() -> dict[str, ParagraphStyle]:
    return {
        "title": ParagraphStyle(
            "title",
            fontName="TimesNewRoman-Bold",
            fontSize=16,
            leading=20,
            alignment=TA_CENTER,
            textColor=PRIMARY,
            spaceAfter=10,
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            fontName="TimesNewRoman-Italic",
            fontSize=11.5,
            leading=14,
            alignment=TA_CENTER,
            textColor=colors.black,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "body",
            fontName="TimesNewRoman",
            fontSize=11,
            leading=15,
            alignment=TA_LEFT,
            textColor=colors.black,
            spaceAfter=6,
        ),
        "section": ParagraphStyle(
            "section",
            fontName="TimesNewRoman-Bold",
            fontSize=12.2,
            leading=16,
            alignment=TA_LEFT,
            textColor=PRIMARY,
            spaceBefore=8,
            spaceAfter=4,
        ),
        "note": ParagraphStyle(
            "note",
            fontName="TimesNewRoman-Italic",
            fontSize=10.5,
            leading=13,
            alignment=TA_LEFT,
            textColor=colors.HexColor("#444444"),
            spaceAfter=6,
        ),
    }


def _prophet_symbol() -> str:
    return "<font face='SegoeUISymbol'>ﷺ</font>"


def _build_story(content: list[tuple[str, str]], styles: dict[str, ParagraphStyle]) -> list:
    story = []
    for style_name, text in content:
        styled_text = _highlight_placeholders(text)
        story.append(Paragraph(styled_text, styles[style_name]))
        if style_name in {"title", "subtitle"}:
            story.append(Spacer(1, 4))
    return story


def _write_pdf(path: Path, title: str, content: list[tuple[str, str]]) -> None:
    styles = _build_styles()
    story = _build_story(content, styles)
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        topMargin=72,
        bottomMargin=54,
        leftMargin=54,
        rightMargin=54,
        title=title,
    )
    doc.build(story, onFirstPage=_draw_frame, onLaterPages=_draw_frame)


def build_pdfs() -> None:
    _register_fonts()
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

    sulh_content = [
        ("title", "ДОГОВОР МИРНОГО СОГЛАШЕНИЯ (СУЛЬХ) ПО ШАРИАТУ"),
        ("subtitle", "Во имя Аллаха, Милостивого, Милосердного."),
        (
            "subtitle",
            "Хвала Аллаху, Господу миров, и да будут благословение и мир Пророку "
            f"Мухаммаду {_prophet_symbol()}, его семье и сподвижникам.",
        ),
        ("section", "1. СТОРОНЫ ДОГОВОРА"),
        (
            "body",
            "1.1. Сторона 1:<br/>"
            "ФИО / Наименование: {{party_one_name}}<br/>"
            "Документ / регистрация: {{party_one_document}}<br/>"
            "Адрес: {{party_one_address}}<br/>"
            "Контактные данные: {{party_one_contact}}",
        ),
        (
            "body",
            "1.2. Сторона 2:<br/>"
            "ФИО / Наименование: {{party_two_name}}<br/>"
            "Документ / регистрация: {{party_two_document}}<br/>"
            "Адрес: {{party_two_address}}<br/>"
            "Контактные данные: {{party_two_contact}}",
        ),
        ("section", "2. ПРЕДМЕТ ДОГОВОРА"),
        (
            "body",
            "2.1. Настоящий договор является договором мирного соглашения (Сульх), "
            "заключаемым с целью мирного урегулирования спора или конфликта между сторонами "
            "на основе принципов Шариата.",
        ),
        (
            "body",
            "2.2. Суть спора/конфликта: {{dispute_subject}}",
        ),
        (
            "body",
            "2.3. Стороны соглашаются разрешить возникший конфликт с миром, без применения насилия, "
            "с соблюдением принципов справедливости и равенства.",
        ),
        ("section", "3. УСЛОВИЯ МИРНОГО СОГЛАШЕНИЯ"),
        (
            "body",
            "3.1. Предлагаемое решение и порядок примирения: {{proposed_resolution}}",
        ),
        (
            "body",
            "3.2. Стороны обязуются отказаться от любых претензий и исков, которые не были согласованы "
            "в данном договоре.",
        ),
        (
            "body",
            "3.3. Стороны отказываются от взаимных претензий по данному спору: {{claims_waived}}.",
        ),
        ("section", "4. ПРАВА СТОРОН"),
        (
            "body",
            "4.1. Каждая сторона имеет право обратиться за помощью к учёным для консультации по спорным вопросам "
            "и, при необходимости, передать вопрос шариатскому судье.",
        ),
        ("section", "5. РАСТОРЖЕНИЕ ДОГОВОРА"),
        (
            "body",
            "5.1. Договор может быть расторгнут по взаимному согласию сторон в любое время. "
            "5.2. В случае невыполнения условий мирного соглашения, одна из сторон может расторгнуть договор.",
        ),
        ("section", "6. РАЗРЕШЕНИЕ СПОРОВ"),
        (
            "body",
            "6.1. Все споры, возникающие в процессе выполнения договора, решаются мирным путём с использованием "
            "Шариата. 6.2. При невозможности разрешить спор мирным путём, вопрос передаётся шариатскому судье "
            "(кади) или учёному.",
        ),
        ("section", "7. ФОРС-МАЖОР (КАДАР)"),
        (
            "body",
            "Стороны освобождаются от ответственности за обстоятельства, произошедшие по воле Аллаха "
            "и не зависящие от них.",
        ),
        ("section", "8. ХРАНЕНИЕ И ДОСТУП К ДОГОВОРУ"),
        (
            "body",
            "8.1. Договор зафиксирован в шариатском боте. 8.2. Оригинал договора хранится в базе данных "
            "системы и доступен обеим сторонам через их личные аккаунты. 8.3. Электронная форма договора "
            "имеет полную юридическую и шариатскую силу.",
        ),
        ("section", "9. ЗАКЛЮЧИТЕЛЬНЫЕ ПОЛОЖЕНИЯ"),
        (
            "body",
            "9.1. Договор вступает в силу с момента иджаб и кабуль. 9.2. Стороны подтверждают добровольность "
            "и соответствие договора нормам Шариата.",
        ),
        ("section", "10. ПОДПИСИ СТОРОН"),
        (
            "body",
            "Сторона 1: {{party_one_name}}  Подпись: __________________  Дата: ____________",
        ),
        (
            "body",
            "Сторона 2: {{party_two_name}}  Подпись: __________________  Дата: ____________",
        ),
        ("note", "Аллах - Свидетель этого мирного соглашения."),
    ]

    qard_content = [
        ("title", "ДОГОВОР ЗАЙМА QARD AL-HASAN (ҚАРД АЛ-ХАСАН) ПО ШАРИАТУ"),
        ("subtitle", "Во имя Аллаха, Милостивого, Милосердного."),
        (
            "subtitle",
            "Хвала Аллаху, Господу миров, и да будут благословение и мир Пророку "
            f"Мухаммаду {_prophet_symbol()}, его семье и сподвижникам.",
        ),
        ("section", "1. СТОРОНЫ ДОГОВОРА"),
        (
            "body",
            "1.1. Займодавец (Сторона 1):<br/>"
            "ФИО / Наименование: {{lender_name}}<br/>"
            "Документ, удостоверяющий личность / регистрация: {{lender_document}}<br/>"
            "Адрес: {{lender_address}}<br/>"
            "Контактные данные: {{lender_contact}}",
        ),
        (
            "body",
            "1.2. Займополучатель (Сторона 2):<br/>"
            "ФИО / Наименование: {{borrower_name}}<br/>"
            "Документ, удостоверяющий личность / регистрация: {{borrower_document}}<br/>"
            "Адрес: {{borrower_address}}<br/>"
            "Контактные данные: {{borrower_contact}}",
        ),
        ("section", "2. ПРЕДМЕТ ДОГОВОРА"),
        (
            "body",
            "2.1. Займодавец передает Займополучателю денежные средства в размере: {{amount}}.",
        ),
        (
            "body",
            "2.2. Данный займ является Qard al-Hasan (Қард аль-Хасан) - благим, без процентов и "
            "без какой-либо выгоды для займодавца, полностью разрешенным по Шариату.",
        ),
        (
            "body",
            "2.3. Цель займа: {{purpose}}.",
        ),
        ("section", "3. СРОК И ПОРЯДОК ВОЗВРАТА"),
        (
            "body",
            "3.1. Срок возврата займа: {{due_date}}.",
        ),
        (
            "body",
            "3.2. Форма возврата: {{repayment_method}}.",
        ),
        (
            "body",
            "3.3. Займополучатель обязуется вернуть только сумму займа, без процентов, наценок, "
            "штрафов или дополнительных условий.",
        ),
        (
            "body",
            "3.4. Возможна досрочная выплата по желанию Займополучателя.",
        ),
        ("section", "4. ПРАВА И ОБЯЗАННОСТИ СТОРОН"),
        (
            "body",
            "4.1. Займодавец: передает точную сумму займа; не требует процентов или иных дополнительных выплат; "
            "предоставляет расписку или документ о передаче средств.",
        ),
        (
            "body",
            "4.2. Займополучатель: использует средства по назначению (по согласованию); "
            "возвращает полную сумму займа в срок; сообщает о любых обстоятельствах, влияющих на возврат.",
        ),
        ("section", "5. РАЗРЕШЕНИЕ СПОРОВ"),
        (
            "body",
            "5.1. Все споры решаются путем переговоров или через шариатского судью (кади) / учёного. "
            "5.2. Любые условия, противоречащие Шариату, считаются недействительными.",
        ),
        ("section", "6. ФОРС-МАЖОР (КАДАР)"),
        (
            "body",
            "Стороны освобождаются от ответственности за обстоятельства, не зависящие от них, по воле Аллаха.",
        ),
        ("section", "7. ХРАНЕНИЕ И ДОСТУП"),
        (
            "body",
            "7.1. Договор хранится в оригинале в базе данных шариатского бота и доступен обеим сторонам "
            "через их аккаунты.",
        ),
        (
            "body",
            "7.2. Все экземпляры договора считаются юридически равнозначными, и их хранение в системе "
            "шариатского бота подтверждает подлинность сделки.",
        ),
        ("section", "8. ЗАКЛЮЧИТЕЛЬНЫЕ ПОЛОЖЕНИЯ"),
        (
            "body",
            "8.1. Договор вступает в силу с момента иджаб и кабуль (предложения и принятия). "
            "8.2. Стороны подтверждают, что договор заключен добровольно, в соответствии с нормами Шариата.",
        ),
        ("section", "9. ПОДПИСИ СТОРОН"),
        (
            "body",
            "Займодавец: {{lender_name}}  Подпись: __________________  Дата: ____________",
        ),
        (
            "body",
            "Займополучатель: {{borrower_name}}  Подпись: __________________  Дата: ____________",
        ),
        ("note", "Аллах - Свидетель этой сделки."),
    ]

    _write_pdf(
        TEMPLATES_DIR / "contract_template_sulh_style.pdf",
        "Договор Сульх (шаблон)",
        sulh_content,
    )
    _write_pdf(
        TEMPLATES_DIR / "contract_template_qard_al_hasan_style.pdf",
        "Договор Qard al-Hasan (шаблон)",
        qard_content,
    )


if __name__ == "__main__":
    build_pdfs()
