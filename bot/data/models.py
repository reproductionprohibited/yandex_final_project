from flask_login import UserMixin

from sqlalchemy import Column, ForeignKey, Integer, String, Date, Float
from sqlalchemy.orm import relationship

from .db_session import SqlAlchemyBase


class Admin(UserMixin, SqlAlchemyBase):
    __tablename__ = 'admins'

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True)
    password_hash = Column(String)

    def __repr__(self) -> str:
        return f'<Admin> {self.username}'


class User(SqlAlchemyBase):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_userid = Column(Integer, nullable=False)
    username = Column(String(32), unique=True, nullable=False)
    age = Column(Integer, nullable=False)
    living_location = Column(String, nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    bio = Column(String(200), nullable=False)

    def __repr__(self) -> str:
        return f'<User> {self.username}'


class Journey(SqlAlchemyBase):
    __tablename__ = 'journey'

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(Integer, nullable=False)
    title = Column(String(50), unique=True, nullable=False)
    description = Column(String(100), nullable=False)

    locations = relationship(
        'Location', back_populates='journey', cascade='all, delete-orphan'
    )
    notes = relationship('Note', back_populates='journey', cascade='all, delete-orphan')


class Location(SqlAlchemyBase):
    __tablename__ = 'location'

    id = Column(Integer, primary_key=True, autoincrement=True)
    place = Column(String, nullable=False)
    date_start = Column(Date, nullable=False)
    date_end = Column(Date, nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)

    journey_id = Column(Integer, ForeignKey('journey.id'))

    journey = relationship('Journey', back_populates='locations')


class Note(SqlAlchemyBase):
    __tablename__ = 'note'

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(50), nullable=False)
    content = Column(String(500), nullable=False)
    journey_id = Column(Integer, ForeignKey('journey.id'))

    journey = relationship('Journey', back_populates='notes')
