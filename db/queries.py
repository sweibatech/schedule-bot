from db_setup import Event, Role, Participation
from db.dto import EventDTO, RoleDTO, ParticipationDTO
from sqlalchemy.orm import joinedload
from typing import List
from datetime import date

def to_role_dto(role: Role) -> RoleDTO:
    return RoleDTO(id=role.id, name=role.name)

def to_participation_dto(part: Participation) -> ParticipationDTO:
    return ParticipationDTO(
        id=part.id,
        username=part.username,
        role=to_role_dto(part.role) if part.role else None,
    )

def to_event_dto(event: Event) -> EventDTO:
    return EventDTO(
        id=event.id,
        date=event.date.isoformat(),
        slot=event.slot,
        name=event.name,
        time=event.time,
        roles=[to_role_dto(role) for role in event.roles],
        participations=[to_participation_dto(part) for part in event.participations],
    )

def get_events_for_dates(session, dates: List[date]) -> List[EventDTO]:
    events = (
        session.query(Event)
        .options(
            joinedload(Event.roles),
            joinedload(Event.participations).joinedload(Participation.role),
        )
        .filter(Event.date.in_(dates))
        .order_by(Event.date, Event.slot)
        .all()
    )
    return [to_event_dto(e) for e in events]

def get_event_by_id(session, event_id: int) -> EventDTO:
    event = (
        session.query(Event)
        .options(
            joinedload(Event.roles),
            joinedload(Event.participations).joinedload(Participation.role),
        )
        .filter_by(id=event_id)
        .first()
    )
    return to_event_dto(event) if event else None

def get_or_create_role(session, role_name: str) -> Role:
    role = session.query(Role).filter_by(name=role_name).first()
    if not role:
        role = Role(name=role_name)
        session.add(role)
        session.commit()
    return role

def get_participations_for_username(session, username: str, after_date: date) -> List[ParticipationDTO]:
    parts = (
        session.query(Participation)
        .join(Event)
        .filter(
            Participation.username == username,
            Event.date >= today
        )
        .order_by(Event.date, Event.slot)
        .all()
    )
    return [to_participation_dto(p) for p in parts]