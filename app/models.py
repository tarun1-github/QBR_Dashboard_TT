from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    track: Mapped[str] = mapped_column(String(100), index=True)

class Ticket(Base):
    __tablename__ = "tickets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    parent_ticket: Mapped[str] = mapped_column(String(50), index=True)
    ticket_type: Mapped[str] = mapped_column(String(20), index=True)
    project: Mapped[str] = mapped_column(String(100), index=True)
    track: Mapped[str] = mapped_column(String(100), index=True)
    service: Mapped[str] = mapped_column(String(100))
    part: Mapped[str] = mapped_column(String(100))
    priority: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(50))
    created_date: Mapped[datetime] = mapped_column(DateTime, index=True)
    closed_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alert_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    alert_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    project: Mapped[str] = mapped_column(String(100), index=True)
    track: Mapped[str] = mapped_column(String(100), index=True)
    service: Mapped[str] = mapped_column(String(100))
    part: Mapped[str] = mapped_column(String(100))
    alert_type: Mapped[str] = mapped_column(String(100))
    severity: Mapped[str] = mapped_column(String(30))
    monitoring_tool: Mapped[str] = mapped_column(String(50))

class TicketAlert(Base):
    __tablename__ = "ticket_alert"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[str] = mapped_column(String(50), index=True)
    alert_id: Mapped[str] = mapped_column(String(50), index=True)
    relationship: Mapped[str] = mapped_column(String(100))

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30), index=True)
    active: Mapped[int] = mapped_column(Integer, default=1)

class UserTrackAccess(Base):
    __tablename__ = "user_track_access"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), index=True)
    track: Mapped[str] = mapped_column(String(100), index=True)
