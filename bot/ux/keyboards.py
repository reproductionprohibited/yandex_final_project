from typing import List

from aiogram.types import (
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from data.models import Journey


DEFAULT_KEYBOARD = ReplyKeyboardMarkup(
    resize_keyboard=True,
    keyboard=[
        # [KeyboardButton(text='/help')],
        [KeyboardButton(text='/cancel')],
    ],
)

EDIT_USER_PARAMS_KEYBOARD = ReplyKeyboardMarkup(
    resize_keyboard=True,
    keyboard=[
        [
            KeyboardButton(text='age'),
            KeyboardButton(text='location'),
            KeyboardButton(text='bio'),
        ],
    ],
    one_time_keyboard=True,
)


EDIT_JOURNEY_PARAMS_KEYBOARD = ReplyKeyboardMarkup(
    resize_keyboard=True,
    keyboard=[
        [KeyboardButton(text='Title')],
        [KeyboardButton(text='Description')],
        [KeyboardButton(text='Locations')],
    ],
    one_time_keyboard=True,
)

EDIT_LOCATION_PARAMS_KEYBOARD = ReplyKeyboardMarkup(
    resize_keyboard=True,
    keyboard=[
        [
            KeyboardButton(text='Place'),
            KeyboardButton(text='Date start'),
            KeyboardButton(text='Date end'),
        ],
    ],
    one_time_keyboard=True,
)

EDIT_NOTE_PARAMS_KEYBOARD = ReplyKeyboardMarkup(
    resize_keyboard=True,
    keyboard=[
        [
            KeyboardButton(text='Title'),
            KeyboardButton(text='Content'),
        ],
    ],
    one_time_keyboard=True,
)

JOURNEY_INFO_KEYBOARD = ReplyKeyboardMarkup(
    resize_keyboard=True,
    keyboard=[
        [KeyboardButton(text='Location List'), KeyboardButton(text='Weather')],
        [KeyboardButton(text='Sightseeing'), KeyboardButton(text='Hotels')],
        [KeyboardButton(text='Restaurants'), KeyboardButton(text='Map Route')],
    ],
    one_time_keyboard=True,
)


def journey_list_keyboard(journey_list: List[Journey]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        resize_keyboard=True,
        keyboard=[[KeyboardButton(text=journey.title)] for journey in journey_list],
        one_time_keyboard=True,
    )


def journey_location_list_keyboard(journey: Journey) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        resize_keyboard=True,
        keyboard=[
            [
                KeyboardButton(
                    text=f'{location.place}: {location.date_start} - {location.date_end}',
                )
            ]
            for location in journey.locations
        ],
        one_time_keyboard=True,
    )


def journey_note_list_keyboard(journey: Journey) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        resize_keyboard=True,
        keyboard=[[KeyboardButton(text=f'{note.title}')] for note in journey.notes],
        one_time_keyboard=True,
    )
