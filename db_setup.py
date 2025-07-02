import os
from sqlalchemy import (
    create_engine, Column, Integer, String, Date, ForeignKey, Table
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
DB_NAME = os.getenv("DB_NAME", "music_schedule.db")
ADMIN_IDS = set(int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip())

Base = declarative_base()

# Association table for many-to-many Event <-> Role
event_roles = Table(
    "event_roles",
    Base.metadata,
    Column("event_id", Integer, ForeignKey("events.id"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id"), primary_key=True)
)

class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)

    participations = relationship("Participation", back_populates="role")
    events = relationship("Event", secondary=event_roles, back_populates="roles")

class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    slot = Column(String, nullable=False)  # "morning" or "evening"
    name = Column(String, nullable=False)
    time = Column(String, nullable=False)

    roles = relationship("Role", secondary=event_roles, back_populates="events")
    participations = relationship("Participation", back_populates="event")

class Participation(Base):
    __tablename__ = "participations"
    id = Column(Integer, primary_key=True)
    username = Column(String, nullable=False)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=True)

    event = relationship("Event", back_populates="participations")
    role = relationship("Role", back_populates="participations")

def get_engine():
    # Support both sqlite and other DBs via URL if desired
    if DB_NAME.startswith("sqlite:///") or DB_NAME.endswith(".db"):
        db_url = f"sqlite:///{DB_NAME}" if not DB_NAME.startswith("sqlite:///") else DB_NAME
    else:
        db_url = DB_NAME  # Assume full SQLAlchemy URL if not sqlite
    return create_engine(db_url, echo=False, future=True)

engine = get_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

def init_db():
    Base.metadata.create_all(bind=engine)