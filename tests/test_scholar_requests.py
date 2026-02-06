from __future__ import annotations

from dataclasses import dataclass

from app.services.scholar_requests.service import (
    ScholarAttachment,
    ScholarRequestDraft,
    build_forward_text,
    build_request_payload,
    build_request_summary,
)


@dataclass(frozen=True, slots=True)
class FakeUser:
    id: int
    full_name: str
    username: str | None = None


def test_build_request_payload_contains_sizes_and_username() -> None:
    user = FakeUser(id=123, full_name="Test User", username="tester")
    draft = ScholarRequestDraft(
        request_type="text",
        data={"ask_text": "Question"},
        attachments=[
            ScholarAttachment(content=b"abc", filename="a.txt", content_type="text/plain"),
            ScholarAttachment(content=b"0123456789", filename="b.pdf", content_type="application/pdf"),
        ],
    )
    payload = build_request_payload(request_id=7, telegram_user=user, language="ru", draft=draft)
    assert payload["request_id"] == 7
    assert payload["user_id"] == 123
    assert payload["username"] == "@tester"
    assert payload["type"] == "text"
    assert payload["attachments"][0]["size"] == 3
    assert payload["attachments"][1]["size"] == 10


def test_build_request_summary_includes_attachments_count() -> None:
    draft = ScholarRequestDraft(
        request_type="docs",
        data={"ask_docs_description": "Details"},
        attachments=[ScholarAttachment(content=b"x", filename="a.pdf", content_type="application/pdf")],
    )
    summary = build_request_summary(draft)
    assert "Вложения:" in summary
    assert "1" in summary


def test_build_forward_text_contains_request_id_and_user() -> None:
    user = FakeUser(id=321, full_name="Another User", username=None)
    text = build_forward_text(request_id=42, telegram_user=user, summary="S")
    assert "#42" in text
    assert "id=321" in text

