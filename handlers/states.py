from aiogram.fsm.state import State, StatesGroup


class PostForm(StatesGroup):
    title = State()
    description = State()
    price = State()
    photo = State()
    preview = State()


class EditPrice(StatesGroup):
    waiting_price = State()


class RejectReason(StatesGroup):
    waiting_reason = State()
