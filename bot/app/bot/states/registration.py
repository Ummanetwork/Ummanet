from aiogram.fsm.state import State, StatesGroup


class RegistrationSG(StatesGroup):
    waiting_for_name = State()
    waiting_for_email = State()
    waiting_for_phone = State()
    waiting_for_phone_contact = State()


__all__ = ["RegistrationSG"]
