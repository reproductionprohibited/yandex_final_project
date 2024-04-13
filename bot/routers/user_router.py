from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from data.crud import (
    create_user,
    update_user,
    get_user_by_telegram_userid,
)
from data.validators import validate_location
from ux.keyboards import (
    DEFAULT_KEYBOARD,
    EDIT_USER_PARAMS_KEYBOARD,
)
from ux.typical_answers import generate_profile_text
from settings import session

user_router = Router()


class UserForm(StatesGroup):
    age = State()
    location = State()
    bio = State()


class EditUserForm(StatesGroup):
    to_edit = State()
    edit_age = State()
    edit_location = State()
    edit_bio = State()


''' Create User Func Group '''
@user_router.message(UserForm.age)
async def add_user_age(message: Message, state: FSMContext) -> None:
    try:
        age = int(message.text)
        if not (0 <= age <= 122):
            raise ValueError('Invalid age')
    except ValueError:
        await message.answer(
            '⚠️ Please enter a valid age',
        )
        return

    await state.update_data(age=message.text)
    await state.set_state(UserForm.location)
    await message.answer(
        f'✍️ Ok, so you are {message.text} y.o. Where do you live?',
    )


@user_router.message(UserForm.location)
async def add_user_location(message: Message, state: FSMContext) -> None:
    location = message.text
    try:
        is_valid, _, placename, lat, lon = await validate_location(city=location)
        if is_valid:
            await state.update_data(location=placename, lat=lat, lon=lon)
            await state.set_state(UserForm.bio)
            await message.answer(
                '🧬 Good! One final detail: what do you want other people to know about you?',
            )
        else:
            raise Exception('Invalid location')
    except Exception:
        await message.answer(
            '⚠️ Something went wrong\n'
            'Are you sure you entered an existing location? Try again',
        )


@user_router.message(UserForm.bio)
async def add_user_bio(message: Message, state: FSMContext) -> None:
    bio = message.text
    if len(bio) > 200:
        await message.answer(
            '⚠️ You bio is too long. Try to fit it in 200 characters',
            reply_markup=DEFAULT_KEYBOARD,
        )
        return
    else:
        data = await state.update_data(bio=bio)
        await create_user(
            db_session=session,
            username=message.from_user.username,
            telegram_id=message.from_user.id,
            age=data['age'],
            lat=data['lat'],
            lon=data['lon'],
            living_location=data['location'],
            bio=data['bio'],
        )
        await end_user_signup(message=message, state=state)


async def end_user_signup(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        '✅ You are signed up! Now you can plan your trips!\n'
        'To see all available commands, see "Menu" (blue button in the left corner)',
        reply_markup=DEFAULT_KEYBOARD,
    )


''' Edit User Func Group '''
@user_router.message(Command(commands=['edit_profile']))
async def start_edit_user(message: Message, state: FSMContext) -> None:
    await state.set_state(EditUserForm.to_edit)

    await message.answer(
        '🧐 What exactly do you want to change in your profile?',
        reply_markup=EDIT_USER_PARAMS_KEYBOARD,
    )


@user_router.message(EditUserForm.to_edit)
async def edit_user_info(message: Message, state: FSMContext) -> None:
    if message.text == 'age':
        await state.set_state(EditUserForm.edit_age)
        await message.answer('🧐 How old are you?', reply_markup=DEFAULT_KEYBOARD)
    elif message.text == 'location':
        await state.set_state(EditUserForm.edit_location)
        await message.answer(f'🧐 Where do you live?', reply_markup=DEFAULT_KEYBOARD)
    elif message.text == 'bio':
        await state.set_state(EditUserForm.edit_bio)
        await message.answer('✍️ Type in your new bio', reply_markup=DEFAULT_KEYBOARD)
    else:
        await message.answer(
            '⚠️ Please provide one of the 3 options below',
            reply_markup=EDIT_USER_PARAMS_KEYBOARD,
        )


@user_router.message(EditUserForm.edit_age)
async def edit_user_age(message: Message, state: FSMContext) -> None:
    try:
        age = int(message.text)
        if not (0 <= age <= 122):
            raise ValueError('Invalid age')
    except ValueError:
        await message.answer(
            '⚠️ Please enter a valid age', reply_markup=DEFAULT_KEYBOARD
        )
        return

    user = await get_user_by_telegram_userid(db_session=session, telegram_id=message.from_user.id)
    await update_user(
        db_session=session,
        id=user.id,
        new_age=age,
    )
    await state.clear()
    await message.answer(
        '✅ Age changed successfully',
        reply_markup=DEFAULT_KEYBOARD,
    )


@user_router.message(EditUserForm.edit_location)
async def edit_user_location(message: Message, state: FSMContext) -> None:
    location = message.text
    try:
        is_valid, _, placename, lat, lon = await validate_location(city=location)
        if is_valid:
            await state.clear()
            user = await get_user_by_telegram_userid(db_session=session, telegram_id=message.from_user.id)
            await update_user(
                db_session=session,
                id=user.id,
                new_living_location=placename,
                new_lat=lat,
                new_lon=lon,
            )

            await message.answer(
                '✅ Location changed successfully',
                reply_markup=DEFAULT_KEYBOARD,
            )
        else:
            raise Exception('Invalid location')
    except Exception:
        await message.answer(
            '⚠️ Something went wrong\n' \
            'Are you sure you entered an existing location?',
            reply_markup=DEFAULT_KEYBOARD,
        )


@user_router.message(EditUserForm.edit_bio)
async def edit_user_bio(message: Message, state: FSMContext) -> None:
    bio = message.text
    if len(bio) > 200:
        await message.answer(
            '⚠️ You bio is too long. Try to fit it in 200 characters',
            reply_markup=DEFAULT_KEYBOARD,
        )
    else:
        user = await get_user_by_telegram_userid(db_session=session, telegram_id=message.from_user.id)
        await state.clear()
        await update_user(
            db_session=session,
            id=user.id,
            new_bio=bio,
        )
        await message.answer(
            '✅ Bio changed successfully',
            reply_markup=DEFAULT_KEYBOARD,
        )


''' See User Profile Func '''
@user_router.message(Command(commands=['profile']))
async def see_user_profile(message: Message) -> None:
    user = await get_user_by_telegram_userid(db_session=session, telegram_id=message.from_user.id)

    await message.answer(
        generate_profile_text(user=user),
        reply_markup=DEFAULT_KEYBOARD,
    )
