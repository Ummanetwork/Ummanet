import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BOT_ROOT = os.path.join(ROOT, "bot")
if BOT_ROOT not in sys.path:
    sys.path.insert(0, BOT_ROOT)

import importlib.util

INVITE_FLOW_PATH = os.path.join(BOT_ROOT, "app", "bot", "services", "invite_flow.py")
spec = importlib.util.spec_from_file_location("invite_flow", INVITE_FLOW_PATH)
invite_flow = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(invite_flow)

normalize_invite_payload = invite_flow.normalize_invite_payload
try_attach_invite_case = invite_flow.try_attach_invite_case


class _FakeBot:
    def __init__(self) -> None:
        self.sent = []

    async def send_message(self, chat_id: int, text: str, reply_markup=None) -> None:  # noqa: ANN001
        self.sent.append((chat_id, text))


class _FakeCourtCases:
    def __init__(self) -> None:
        self.attach_called = False

    async def get_case_by_invite_code(self, invite_code: str) -> dict:
        return {"id": 1, "invite_code": invite_code, "plaintiff_id": 10, "user_id": 10}

    async def attach_defendant(self, case_id: int, defendant_id: int) -> dict:
        self.attach_called = True
        return {"id": case_id, "case_number": "2026-000001", "plaintiff_id": 10, "user_id": 10}


class _FakeDb:
    def __init__(self) -> None:
        self.court_cases = _FakeCourtCases()


@pytest.mark.asyncio
async def test_normalize_invite_payload() -> None:
    assert normalize_invite_payload(" ua3f43 ") == "UA3F43"


@pytest.mark.asyncio
async def test_try_attach_invite_case_attaches_defendant() -> None:
    bot = _FakeBot()
    db = _FakeDb()
    await try_attach_invite_case(
        bot=bot,
        db=db,
        user_id=42,
        invite_code="UA3F43",
        lang_code="ru",
    )
    assert db.court_cases.attach_called is True
    assert bot.sent
