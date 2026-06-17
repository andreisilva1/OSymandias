"""
send_message tool — publishes a message to the Message Bus.
"""
import uuid
from datetime import datetime, timezone
from typing import Any

import redis as _redis
import json
from loguru import logger
from sqlalchemy.orm import Session

from osymandias.runtime.config import settings
from osymandias.runtime.models import Message, MessageType, AgentInstance
from osymandias.runtime.tools.registry import register


@register("send_message")
def send_message(
    to: str,
    subject: str,
    message_type: str,
    content: dict[str, Any],
    session: Session,
    agent_instance_id: uuid.UUID,
) -> dict:
    """Send a message to another agent in the same job."""
    try:
        sender = session.get(AgentInstance, agent_instance_id)
        if not sender:
            return {"delivered": False, "error": "sender not found"}

        msg_type = MessageType(message_type)
        now = datetime.now(timezone.utc)

        # Resolve receiver instance id if routing by type
        from sqlalchemy import select
        receiver_instance_id = None
        if to != "*":
            receiver = session.scalars(
                select(AgentInstance).where(
                    AgentInstance.job_id == sender.job_id,
                    AgentInstance.agent_definition_name == to,
                    AgentInstance.status.in_(["CREATED", "READY", "RUNNING", "BLOCKED"]),
                )
            ).first()
            if receiver:
                receiver_instance_id = receiver.id

        msg = Message(
            job_id=sender.job_id,
            sender_agent_instance_id=sender.id,
            receiver_agent_instance_id=receiver_instance_id,
            receiver_agent_type=to if to != "*" else None,
            message_type=msg_type,
            subject=subject,
            content=content,
            is_read=False,
            sent_at=now,
        )
        session.add(msg)
        session.flush()

        # Notify via Redis pub/sub
        r = _redis.from_url(settings.redis_url, decode_responses=True)
        channel = f"mailbox:{to}:{sender.job_id}"
        r.publish(channel, json.dumps({
            "message_id": str(msg.id),
            "from": sender.agent_definition_name,
            "subject": subject,
        }))

        session.commit()
        logger.debug("send_message: {} → {} subject='{}'", sender.agent_definition_name, to, subject)
        return {"delivered": True, "message_id": str(msg.id)}

    except Exception as exc:
        logger.warning("send_message failed: {}", exc)
        return {"delivered": False, "error": str(exc)}
