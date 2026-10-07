from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Status = Literal["OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"]
Priority = Literal["LOW", "MEDIUM", "HIGH", "URGENT"]
Category = Literal["GENERAL", "ACCESS", "HARDWARE", "NETWORK", "BILLING"]


class TicketCreate(BaseModel):
    subject: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=5000)
    requester: str = Field(min_length=1, max_length=120)
    category: Category = "GENERAL"
    priority: Priority = "MEDIUM"
    team: str | None = Field(default=None, max_length=80)


class TicketUpdate(BaseModel):
    subject: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    category: Category | None = None
    priority: Priority | None = None
    status: Status | None = None
    team: str | None = Field(default=None, max_length=80)


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subject: str
    description: str
    requester: str
    category: str
    priority: str
    status: str
    team: str
    created_at: datetime
    updated_at: datetime


class CommentCreate(BaseModel):
    author: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=5000)


class CommentOut(CommentCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int
    created_at: datetime


class StatsOut(BaseModel):
    total: int
    open: int
    in_progress: int
    resolved: int
    closed: int
    urgent_open: int
