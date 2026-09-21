"""Called by command handlers, inside the SAME transaction as the data change.

This is what makes the write atomic without 2PC or a message broker: the
outbox row and the domain-table change either both commit or both roll back.
"""

import uuid

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.outbox.models import OutboxEvent


async def write_event(
    session: AsyncSession,
    *,
    aggregate_type: str,
    aggregate_id: uuid.UUID,
    event: BaseModel,
) -> OutboxEvent:
    outbox_event = OutboxEvent(
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        event_type=event.event_type,
        payload=event.model_dump(mode="json"),
    )
    session.add(outbox_event)
    # No commit here — caller's transaction (same session) commits both
    # the aggregate change and this outbox row together.
    return outbox_event
