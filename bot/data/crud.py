from datetime import date
from typing import List

from sqlalchemy.orm import Session

from .models import (
    Admin,
    Journey,
    Location,
    Note,
    User,
)


async def create_user(
    db_session: Session,
    username: str,
    telegram_id: int,
    age: int,
    lat: float,
    lon: float,
    living_location: str,
    bio: str,
) -> User:
    user = User(
        username=username,
        telegram_userid=telegram_id,
        age=age,
        lat=lat,
        lon=lon,
        living_location=living_location,
        bio=bio,
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    return user


async def get_user_by_telegram_userid(
    db_session: Session,
    telegram_id: int,
) -> User | None:
    return db_session.query(User).filter_by(telegram_userid=telegram_id).one_or_none()


async def update_user(
    db_session: Session,
    id: int,
    new_age: int | None = None,
    new_living_location: str | None = None,
    new_lat: float | None = None,
    new_lon: float | None = None,
    new_bio: str | None = None,
):
    user: User = db_session.query(User).get(id)
    if new_age is not None:
        user.age = new_age
    if new_living_location is not None:
        user.living_location = new_living_location
    if new_lat is not None:
        user.lat = new_lat
    if new_lon is not None:
        user.lon = new_lon
    if new_bio is not None:
        user.bio = new_bio

    db_session.commit()


async def create_journey(
    db_session: Session,
    owner_id: int,
    title: str,
    description: str,
) -> Journey:
    journey = Journey(owner_id=owner_id, title=title, description=description)

    db_session.add(journey)
    db_session.commit()
    db_session.refresh(journey)

    return journey


async def get_all_journeys(
    db_session: Session,
) -> List[Journey]:
    return db_session.query(Journey).all()


async def get_all_user_journeys(
    db_session: Session,
    owner_id: int,
) -> List[Journey]:
    return db_session.query(Journey).filter_by(owner_id=owner_id).all()


async def get_journey_by_title(
    db_session: Session,
    owner_id: int,
    journey_title: str,
) -> Journey | None:
    return (
        db_session.query(Journey)
        .filter_by(title=journey_title, owner_id=owner_id)
        .one_or_none()
    )


async def get_journey_by_id(
    db_session: Session,
    journey_id: int,
) -> Journey | None:
    return db_session.query(Journey).get(journey_id)


async def update_journey(
    db_session: Session,
    journey: Journey,
    new_title: str | None = None,
    new_description: str | None = None,
) -> None:
    if new_title is not None:
        journey.title = new_title
    if new_description is not None:
        journey.description = new_description

    db_session.commit()


async def delete_journey(
    db_session: Session,
    journey: Journey,
) -> None:
    db_session.delete(journey)
    db_session.commit()


async def create_location(
    db_session: Session,
    place: str,
    date_start: date,
    date_end: date,
    lat: float,
    lon: float,
    journey: Journey,
) -> Location:
    location = Location(
        place=place,
        date_start=date_start,
        date_end=date_end,
        lat=lat,
        lon=lon,
    )

    journey.locations.append(location)

    db_session.add(location)
    db_session.commit()
    db_session.refresh(location)

    return location


async def get_location_by_journey_place_datestart_dateend(
    db_session: Session,
    journey: Journey,
    place: str,
    date_start: date,
    date_end: date,
) -> Location | None:
    return (
        db_session.query(Location)
        .filter_by(
            place=place, date_start=date_start, date_end=date_end, journey_id=journey.id
        )
        .one_or_none()
    )


async def update_location(
    db_session: Session,
    location: Location,
    new_place: str | None = None,
    new_date_start: date | None = None,
    new_date_end: date | None = None,
    new_lat: float | None = None,
    new_lon: float | None = None,
) -> None:
    if new_place is not None:
        location.place = new_place
    if new_date_start is not None:
        location.date_start = new_date_start
    if new_date_end is not None:
        location.date_end = new_date_end
    if new_lat is not None:
        location.lat = new_lat
    if new_lon is not None:
        location.lon = new_lon

    db_session.commit()


async def delete_location_from_journey(
    db_session: Session,
    journey: Journey,
    location: Location,
) -> None:
    journey.locations.remove(location)
    db_session.delete(location)
    db_session.commit()


async def create_note(
    db_session: Session, title: str, content: str, journey: Journey
) -> Note:
    note = Note(
        title=title,
        content=content,
    )

    journey.notes.append(note)

    db_session.add(note)
    db_session.commit()
    db_session.refresh(note)

    return note


async def update_note(
    db_session: Session,
    note: Note,
    new_title: str | None = None,
    new_content: str | None = None,
) -> None:
    if new_title is not None:
        note.title = new_title
    if new_content is not None:
        note.content = new_content

    db_session.commit()


async def delete_note(
    db_session: Session,
    note: Note,
) -> None:
    db_session.delete(note)
    db_session.commit()


async def get_note_by_title(
    journey: Journey,
    note_title: str,
) -> Note:
    return [note for note in journey.notes if note.title == note_title][0]