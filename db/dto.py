from dataclasses import dataclass
from typing import List, Optional

@dataclass
class RoleDTO:
    id: int
    name: str

@dataclass
class EventDTO:
    id: int
    date: str
    slot: str
    name: str
    time: str
    roles: List['RoleDTO']
    participations: List['ParticipationDTO']

@dataclass
class ParticipationDTO:
    id: int
    username: str
    role: Optional['RoleDTO']