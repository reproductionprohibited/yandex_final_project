from data.models import Journey, Location, Note, User
from aiogram.utils.markdown import hbold, hitalic

DATE_CONFLICTS_WITH_ANOTHER_DATE = '''
This date conflicts with another date, associated with this location. Maybe you made a mistake?
'''

def generate_note_text(note: Note) -> str:
    lines = [f'✏️ {hitalic(note.title)}', note.content]
    return '\n'.join(lines)


def generate_location_text(location: Location) -> str:
    lines = [
        f'📍 {hbold(location.place)}',
        f'{location.date_start} - {location.date_end}',
    ]

    return '\n'.join(lines)


def generate_journey_text(journey: Journey) -> str:
    lines = [
        f'Journey {hbold(journey.title)}',
        f'Description: {hitalic(journey.description)}',
    ]

    for i, location in enumerate(journey.locations):
        lines.append(generate_location_text(location=location))
        if i != len(journey.locations) - 1:
            lines.append('---')

    return '\n'.join(lines)


def generate_welcoming_text(username: str) -> str:
    lines = [
        f'👋 Hello, {hitalic(username)}',
        'This is a travel agent bot! Let\'s first fill out a form...',
        'We need this data to improve your experience of using our bot :)',
        'How old are you?',
    ]

    return '\n'.join(lines)


def generate_profile_text(user: User) -> str:
    lines = [
        f'ℹ️ {hitalic(user.username)}\'s profile',
        f'😎 {hitalic(user.age)} y.o.',
        '',
        f'✏️ {hitalic(user.bio)}',
        '',
        f'📍 Lives in: {hitalic(user.living_location)}',
    ]

    return '\n'.join(lines)
