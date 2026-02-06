from __future__ import annotations

from aiogram import Router

from .comitee_blacklist import router as blacklist_router
from .comitee_contracts import router as contracts_router
from .comitee_courts import router as courts_router
from .comitee_inheritance import router as inheritance_router
from .comitee_nikah import router as nikah_router
from .comitee_spouse_search import router as spouse_search_router
from .comitee_knowledge import router as knowledge_router
from .comitee_menu import rebuild_menu_texts, router as menu_router, show_welcome_menu
from .comitee_meetings import router as meetings_router
from .comitee_scholars import router as scholars_router
from .comitee_good_deeds import router as good_deeds_router
from .comitee_sharia_control import router as sharia_control_router

router = Router(name="comitee")
comitee_router = router

router.include_router(menu_router)
router.include_router(inheritance_router)
router.include_router(nikah_router)
router.include_router(spouse_search_router)
router.include_router(contracts_router)
router.include_router(courts_router)
router.include_router(knowledge_router)
router.include_router(blacklist_router)
router.include_router(scholars_router)
router.include_router(meetings_router)
router.include_router(good_deeds_router)
router.include_router(sharia_control_router)

__all__ = [
    "comitee_router",
    "rebuild_menu_texts",
    "show_welcome_menu",
]
