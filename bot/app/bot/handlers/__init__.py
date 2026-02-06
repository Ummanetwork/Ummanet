from .commands import commands_router
from .comitee import comitee_router

__all__ = ["routers"]

routers = [
    commands_router,
    comitee_router,
]
