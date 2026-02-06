from aiogram.fsm.state import State, StatesGroup


class UnbanAppealSG(StatesGroup):
    waiting_for_reason = State()


__all__ = ["UnbanAppealSG"]
