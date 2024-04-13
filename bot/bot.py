import asyncio
import logging
import sys

from aiogram import Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message


from data.crud import get_user_by_telegram_userid
from routers.user_router import user_router, UserForm
from routers.journey_router import journey_router
from routers.notes_router import notes_router
from ux.keyboards import DEFAULT_KEYBOARD
from ux.typical_answers import generate_welcoming_text
from settings import session
from setup import bot

dp = Dispatcher()
dp.include_router(user_router)
dp.include_router(journey_router)
dp.include_router(notes_router)


@dp.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext) -> None:
    user = await get_user_by_telegram_userid(db_session=session, telegram_id=message.from_user.id)
    if user is not None:
        await message.answer(
            f'👋 Hello, {message.from_user.username}! Long time no see',
            reply_markup=DEFAULT_KEYBOARD,
        )
        return

    await state.set_state(UserForm.age)
    await message.answer(
        generate_welcoming_text(username=message.from_user.username),
    )


@dp.message(Command(commands=['cancel']))
async def cancel_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        '❌ Action canceled',
        reply_markup=DEFAULT_KEYBOARD,
    )


async def main() -> None:
    await dp.start_polling(bot)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
