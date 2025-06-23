from sqlalchemy import create_engine, Column, Integer, String, Date, Table, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()
engine = create_engine("sqlite:///rehearsal.db")
SessionLocal = sessionmaker(bind=engine)

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

def get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()