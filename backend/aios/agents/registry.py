"""
Agent Registry — loads AgentDefinitions from the database.
Used by the scheduler to verify that a requested agent type exists.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from aios.models import AgentDefinition


def get_definition(name: str, session: Session) -> AgentDefinition | None:
    return session.get(AgentDefinition, name)


def list_active(session: Session) -> list[AgentDefinition]:
    return list(
        session.scalars(select(AgentDefinition).where(AgentDefinition.is_active == True))  # noqa: E712
    )


def exists(name: str, session: Session) -> bool:
    return session.get(AgentDefinition, name) is not None
