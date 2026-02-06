from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_handlers_routers_order_is_stable() -> None:
    src = _read("bot/app/bot/handlers/__init__.py")
    idx_commands = src.find("commands_router")
    idx_comitee = src.find("comitee_router")
    assert idx_commands != -1 and idx_comitee != -1
    assert idx_commands < idx_comitee


def test_bot_includes_routers_before_dialogs() -> None:
    src = _read("bot/app/bot/bot.py")
    idx_routers = src.find("dp.include_routers(*routers)")
    idx_dialogs = src.find("dp.include_routers(*dialogs)")
    assert idx_routers != -1 and idx_dialogs != -1
    assert idx_routers < idx_dialogs


def test_comitee_router_includes_subrouters_in_expected_order() -> None:
    src = _read("bot/app/bot/handlers/comitee.py")
    expected = [
        "router.include_router(menu_router)",
        "router.include_router(inheritance_router)",
        "router.include_router(nikah_router)",
        "router.include_router(spouse_search_router)",
        "router.include_router(contracts_router)",
        "router.include_router(courts_router)",
        "router.include_router(knowledge_router)",
        "router.include_router(blacklist_router)",
        "router.include_router(scholars_router)",
    ]
    positions = [src.find(item) for item in expected]
    assert all(pos != -1 for pos in positions)
    assert positions == sorted(positions)


def test_scholars_catchall_handler_exists() -> None:
    src = _read("bot/app/bot/handlers/comitee_scholars.py")
    assert "@router.message(~MenuKeyFilter(MAIN_MENU_KEYS))" in src
