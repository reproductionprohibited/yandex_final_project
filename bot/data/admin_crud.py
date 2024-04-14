from typing import List

from sqlalchemy.orm import Session

from .models import (
    Admin,
    Journey,
    Location,
    Note,
    User,
)

def get_admin_by_username(
    db_session: Session,
    username: str
) -> Admin | None:
    return db_session.query(Admin).filter_by(username=username).one_or_none()


def get_all_journeys(
    db_session: Session,
) -> List[Journey]:
    return db_session.query(Journey).all()


def get_journey_by_id(
    db_session: Session,
    journey_id: int,
) -> Journey | None:
    return db_session.query(Journey).filter_by(id = journey_id).first()

def get_all_journey_notes(
    db_session: Session,
    journey_id: int,
) -> List[Note]:
    journey = get_journey_by_id(db_session, journey_id=journey_id)
    if journey is None:
        return []
    
    return journey.notes


def get_all_users(
    db_session: Session,
) -> List[User]:
    return db_session.query(User).all()