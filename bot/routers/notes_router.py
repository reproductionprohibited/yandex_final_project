from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from data.crud import (
    get_all_user_journeys,
    get_journey_by_title,
    get_user_by_telegram_userid,
    create_note,
    delete_note,
    get_note_by_title,
    update_note,
)
from ux.keyboards import (
    DEFAULT_KEYBOARD,
    EDIT_NOTE_PARAMS_KEYBOARD,
    journey_list_keyboard,
    journey_note_list_keyboard,
)
from ux.typical_answers import (
    generate_note_text,
)
from settings import session

notes_router = Router()


class NoteCreateForm(StatesGroup):
    journey = State()
    title = State()
    content = State()


class NoteEditForm(StatesGroup):
    set_journey = State()
    set_note = State()
    set_edit_field = State()
    input_edit = State()


class NoteGetForm(StatesGroup):
    note = State()


class NoteRemoveForm(StatesGroup):
    set_journey = State()
    set_note = State()


''' Create Note Func Group '''
@notes_router.message(Command(commands=['add_note']))
async def start_create_note(message: Message, state: FSMContext) -> None:
    await state.clear()

    user = await get_user_by_telegram_userid(db_session=session, telegram_id=message.from_user.id)
    journeys = await get_all_user_journeys(db_session=session, owner_id=user.id)

    if len(journeys) > 0:
        keyboard = journey_list_keyboard(journey_list=journeys)

        await state.update_data(journeys=journeys)

        await state.set_state(NoteCreateForm.journey)
        await message.answer(
            '🧐 To which journey do you want a new note?',
            reply_markup=keyboard,
        )
    else:
        await state.clear()
        await message.answer(
            '⚠️ First, you should create a journey. Use /create_journey',
            reply_markup=DEFAULT_KEYBOARD,
        )


@notes_router.message(NoteCreateForm.journey)
async def set_journey_note(message: Message, state: FSMContext) -> None:
    journey_title = message.text

    data = await state.get_data()
    journeys = data['journeys']

    if journey_title not in [journey.title for journey in journeys]:
        keyboard = journey_list_keyboard(journey_list=journeys)
        await message.answer('⚠️ Invalid journey. Use the buttons', reply_markup=keyboard)
    else:
        await state.set_state(NoteCreateForm.title)
        await state.update_data(journey=journey_title)
        await message.answer(
            f'✍️ A new note! What would you call it?',
            reply_markup=DEFAULT_KEYBOARD,
        )


@notes_router.message(NoteCreateForm.title)
async def set_title_note(message: Message, state: FSMContext) -> None:
    title = message.text
    data = await state.get_data()
    journey_title = data['journey']

    user = await get_user_by_telegram_userid(db_session=session, telegram_id=message.from_user.id)
    journey = await get_journey_by_title(
        db_session=session, owner_id=user.id, journey_title=journey_title
    )

    if title in [note.title for note in journey.notes]:
        await message.answer(
            '⚠️ You already have a note with this title associated with this journey. Please, choose another one',
            reply_markup=DEFAULT_KEYBOARD,
        )
        return

    if len(title) > 50:
        await message.answer(
            '⚠️ That is too long for a title. Could you try something shorter?',
            reply_markup=DEFAULT_KEYBOARD,
        )
    else:
        await state.set_state(NoteCreateForm.content)
        await state.update_data(title=title, journey=journey)
        await message.answer(
            '✍️ Type in your note itself',
            reply_markup=DEFAULT_KEYBOARD,
        )


@notes_router.message(NoteCreateForm.content)
async def set_content_note(message: Message, state: FSMContext) -> None:
    content = message.text
    if len(content) > 500:
        await message.answer(
            '⚠️ That is too long for a note. Could you try something shorter?',
            reply_markup=DEFAULT_KEYBOARD,
        )
    else:
        data = await state.update_data(content=content)
        journey = data['journey']

        await create_note(
            db_session=session,
            title=data['title'],
            content=data['content'],
            journey=journey,
        )

        await finish_create_note(message=message, state=state)


async def finish_create_note(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        '✅ Successfully created a new note.',
        reply_markup=DEFAULT_KEYBOARD,
    )


''' Watch Journey Notes Func Group '''
@notes_router.message(Command(commands=['see_notes']))
async def start_watch_journey_notes(message: Message, state: FSMContext) -> None:
    await state.clear()

    user = await get_user_by_telegram_userid(db_session=session, telegram_id=message.from_user.id)
    journeys = await get_all_user_journeys(db_session=session, owner_id=user.id)

    if len(journeys) > 0:
        keyboard = journey_list_keyboard(journey_list=journeys)

        await state.update_data(journeys=journeys)

        await state.set_state(NoteGetForm.note)
        await message.answer(
            '🧐 From which journey do you want to see your notes?',
            reply_markup=keyboard,
        )
    else:
        await state.clear()
        await message.answer(
            '⚠️ First, you should create a journey. Use /create_journey',
            reply_markup=DEFAULT_KEYBOARD,
        )


@notes_router.message(NoteGetForm.note)
async def display_all_journey_notes(message: Message, state: FSMContext) -> None:
    journey_title = message.text

    data = await state.get_data()
    if journey_title not in [journey.title for journey in data['journeys']]:
        await message.answer(
            '⚠️ You do not have such journey. Use the buttons',
            reply_markup=journey_list_keyboard(journey_list=data['journeys']),
        )
    else:
        user = await get_user_by_telegram_userid(db_session=session, telegram_id=message.from_user.id)
        journey = await get_journey_by_title(
            db_session=session, journey_title=journey_title, owner_id=user.id
        )
        notes = journey.notes
        await state.clear()

        if len(notes) == 0:
            await message.answer(
                '⚠️ You do not have any notes. Use /add_note',
                reply_markup=DEFAULT_KEYBOARD,
            )
        else:
            await message.answer(
                f'🗒️ {journey_title} notes',
                reply_markup=DEFAULT_KEYBOARD,
            )
            for note in notes:
                await message.answer(
                    generate_note_text(note=note), reply_markup=DEFAULT_KEYBOARD
                )


''' Edit Note Func Group '''
@notes_router.message(Command(commands=['edit_note']))
async def start_edit_journey_note(message: Message, state: FSMContext) -> None:
    await state.clear()

    user = await get_user_by_telegram_userid(db_session=session, telegram_id=message.from_user.id)
    journeys = await get_all_user_journeys(db_session=session, owner_id=user.id)

    if len(journeys) > 0:
        keyboard = journey_list_keyboard(journey_list=journeys)

        await state.update_data(journeys=journeys)

        await state.set_state(NoteEditForm.set_journey)
        await message.answer(
            '🧐 From which journey do you want to edit a note?',
            reply_markup=keyboard,
        )
    else:
        await state.clear()
        await message.answer(
            '⚠️ First, you should create a journey. Use /create_journey',
            reply_markup=DEFAULT_KEYBOARD,
        )


@notes_router.message(NoteEditForm.set_journey)
async def select_edit_journey_note(message: Message, state: FSMContext) -> None:
    journey_title = message.text

    data = await state.get_data()
    journeys = data['journeys']
    if journey_title not in [journey.title for journey in journeys]:
        keyboard = journey_list_keyboard(journey_list=journeys)

        await message.answer(
            '⚠️ Invalid journey title. Use the keyboard',
            reply_markup=keyboard,
        )
    else:
        user = await get_user_by_telegram_userid(db_session=session, telegram_id=message.from_user.id)
        journey = await get_journey_by_title(
            db_session=session, journey_title=journey_title, owner_id=user.id
        )

        if len(journey.notes) > 0:
            await state.update_data(journey=journey)
            await state.set_state(NoteEditForm.set_note)
            keyboard = journey_note_list_keyboard(journey=journey)
            await message.answer(
                '🧐 Which note do you want to edit?',
                reply_markup=keyboard,
            )

        else:
            await state.clear()
            await message.answer(
                '⚠️ There are no notes to this journey. Use /add_note',
                reply_markup=DEFAULT_KEYBOARD,
            )


@notes_router.message(NoteEditForm.set_note)
async def select_edit_note(message: Message, state: FSMContext) -> None:
    note_title = message.text

    data = await state.get_data()
    journey = data['journey']

    if note_title not in [note.title for note in journey.notes]:
        keyboard = journey_note_list_keyboard(journey=journey)
        await message.answer(
            '⚠️ Invalid note. Use the keyboard',
            reply_markup=keyboard,
        )
    else:
        note = await get_note_by_title(journey=journey, note_title=note_title)
        await state.update_data(note=note)
        await state.set_state(NoteEditForm.set_edit_field)
        await message.answer(
            '🧐 What do you want to change',
            reply_markup=EDIT_NOTE_PARAMS_KEYBOARD,
        )


@notes_router.message(NoteEditForm.set_edit_field)
async def set_edit_field_note(message: Message, state: FSMContext) -> None:
    param = message.text

    if param not in ['Title', 'Content']:
        await message.answer(
            '⚠️ There is no such parameter. Use the keyboard',
            reply_markup=EDIT_NOTE_PARAMS_KEYBOARD,
        )
    else:
        await state.update_data(edit_field=param)
        await state.set_state(NoteEditForm.input_edit)
        await message.answer(
            '✍️ Ok. What do you want to change it to?',
            reply_markup=DEFAULT_KEYBOARD,
        )


@notes_router.message(NoteEditForm.input_edit)
async def input_field_edit_note(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    note = data['note']

    if data['edit_field'] == 'Title':
        new_title = message.text
        if len(new_title) > 50:
            await message.answer(
                '⚠️ That is too long for a title. Maybe try something shorter?',
                reply_markup=DEFAULT_KEYBOARD,
            )
        else:
            await update_note(db_session=session, note=note, new_title=new_title)
            await finish_edit_note(message=message, state=state)
    elif data['edit_field'] == 'Content':
        new_content = message.text
        if len(new_content) > 500:
            await message.answer(
                '⚠️ That is too long for a note. Maybe try to shorten it?',
                reply_markup=DEFAULT_KEYBOARD,
            )
        else:
            await update_note(
                db_session=session,
                note=note,
                new_content=new_content,
            )
            await finish_edit_note(message=message, state=state)


async def finish_edit_note(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        '✅ Note successfully edited. Anything else?',
        reply_markup=DEFAULT_KEYBOARD,
    )


@notes_router.message(Command(commands=['remove_note']))
async def start_remove_journey_note(message: Message, state: FSMContext) -> None:
    await state.clear()

    user = await get_user_by_telegram_userid(db_session=session, telegram_id=message.from_user.id)
    journeys = await get_all_user_journeys(db_session=session, owner_id=user.id)

    if len(journeys) > 0:
        keyboard = journey_list_keyboard(journey_list=journeys)

        await state.update_data(journeys=journeys)

        await state.set_state(NoteRemoveForm.set_journey)
        await message.answer(
            '🧐 From which journey do you want to delete a note?',
            reply_markup=keyboard,
        )
    else:
        await state.clear()
        await message.answer(
            '⚠️ First, you should create a journey. Use /create_journey',
            reply_markup=DEFAULT_KEYBOARD,
        )


@notes_router.message(NoteRemoveForm.set_journey)
async def select_remove_journey_note(message: Message, state: FSMContext) -> None:
    journey_title = message.text

    data = await state.get_data()
    journeys = data['journeys']
    if journey_title not in [journey.title for journey in journeys]:
        keyboard = journey_list_keyboard(journey_list=journeys)

        await message.answer(
            '⚠️ There is no such journey. Use the keyboard',
            reply_markup=keyboard,
        )
    else:
        user = await get_user_by_telegram_userid(db_session=session, telegram_id=message.from_user.id)
        journey = await get_journey_by_title(
            db_session=session, journey_title=journey_title, owner_id=user.id
        )

        if len(journey.notes) > 0:
            await state.update_data(journey=journey)
            await state.set_state(NoteRemoveForm.set_note)
            keyboard = journey_note_list_keyboard(journey=journey)
            await message.answer(
                '🧐 Which note do you want to delete?',
                reply_markup=keyboard,
            )
        else:
            await state.clear()
            await message.answer(
                '⚠️ You do not have any notes for this journey. Use /add_note',
                reply_markup=DEFAULT_KEYBOARD,
            )


@notes_router.message(NoteRemoveForm.set_note)
async def select_remove_note(message: Message, state: FSMContext) -> None:
    note_title = message.text

    data = await state.get_data()
    journey = data['journey']
    if note_title not in [note.title for note in journey.notes]:
        keyboard = journey_note_list_keyboard(journey=journey)
        await message.answer(
            '⚠️ Invalid note. Use the keyboard',
            reply_markup=keyboard,
        )
    else:
        note = await get_note_by_title(journey=journey, note_title=note_title)
        await delete_note(
            db_session=session,
            note=note,
        )
        await finish_remove_note(message=message, state=state)


async def finish_remove_note(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        '✅ The note is successfully deleted. Anything else?',
        reply_markup=DEFAULT_KEYBOARD,
    )
