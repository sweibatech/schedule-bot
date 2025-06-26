from sqlalchemy import Column, Integer, String, Date, Table, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

from config.settings import DEFAULT_ROLES
from db.db_client import db_connect, engine

Base = declarative_base()

# Association table for event roles
event_roles = Table(
    "event_roles", Base.metadata,
    Column("event_id", Integer, ForeignKey("events.id")),
    Column("role_id", Integer, ForeignKey("roles.id")),
)


class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    slot = Column(String, nullable=False)  # "morning" or "evening"
    name = Column(String, nullable=False)
    time = Column(String, nullable=False)
    roles = relationship("Role", secondary=event_roles, back_populates="events")
    participations = relationship("Participation", back_populates="event", cascade="all, delete")


class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    events = relationship("Event", secondary=event_roles, back_populates="roles")
    participations = relationship("Participation", back_populates="role")


class Participation(Base):
    __tablename__ = "participations"
    id = Column(Integer, primary_key=True)
    username = Column(String, nullable=False)
    event_id = Column(Integer, ForeignKey("events.id"))
    role_id = Column(Integer, ForeignKey("roles.id"))
    event = relationship("Event", back_populates="participations")
    role = relationship("Role", back_populates="participations")


def init_db():
    Base.metadata.create_all(engine)
    with db_connect() as db:
        for role_name in DEFAULT_ROLES:
            role = db.query(Role).filter_by(name=role_name).first()
            if not role:
                role = Role(name=role_name)
                db.add(role)
