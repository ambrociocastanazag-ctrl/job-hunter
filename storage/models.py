import json
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Boolean, Float, Text,
    DateTime, ForeignKey, JSON,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(50))
    source_url = Column(Text)
    url_hash = Column(String(40), unique=True, nullable=False, index=True)
    content_hash = Column(String(40), nullable=False, index=True)

    title = Column(String(300))
    company = Column(String(200))
    location = Column(String(200))
    is_remote = Column(Boolean, default=False)

    min_amount = Column(Float, nullable=True)
    max_amount = Column(Float, nullable=True)
    currency = Column(String(10), nullable=True)

    description = Column(Text)
    posted_at = Column(DateTime(timezone=True), nullable=True)
    scraped_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    score = Column(Integer, default=0)
    stack_detected = Column(JSON, default=list)
    is_new = Column(Boolean, default=True)
    is_favorite = Column(Boolean, default=False, nullable=False, server_default="0")

    applications = relationship("Application", back_populates="job")


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)

    status = Column(String(30), default="Pendiente")
    applied_at = Column(DateTime(timezone=True), nullable=True)
    cv_version = Column(String(100), nullable=True)
    cover_letter_path = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    next_action_at = Column(DateTime(timezone=True), nullable=True)
    response_at = Column(DateTime(timezone=True), nullable=True)

    job = relationship("Job", back_populates="applications")


class SearchRun(Base):
    __tablename__ = "search_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    finished_at = Column(DateTime(timezone=True), nullable=True)
    total_found = Column(Integer, default=0)
    new_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    params_json = Column(JSON, default=dict)

    mode = Column(String(20), default="daily")
    trigger = Column(String(20), default="cli")  # manual | schedule | cli
    status = Column(String(20), default="ok")    # running | ok | failed | cancelled
    log_path = Column(Text, nullable=True)
