import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from osymandias.runtime.api.deps import get_db, get_or_404
from osymandias.runtime.api.schemas.webhook import WebhookCreate, WebhookResponse
from osymandias.runtime.models import WebhookSubscription

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


@router.post("", response_model=WebhookResponse, status_code=status.HTTP_201_CREATED)
async def create_webhook(body: WebhookCreate, db: AsyncSession = Depends(get_db)):
    hook = WebhookSubscription(url=body.url, events=body.events)
    db.add(hook)
    await db.commit()
    await db.refresh(hook)
    return hook


@router.get("", response_model=list[WebhookResponse])
async def list_webhooks(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(WebhookSubscription).order_by(WebhookSubscription.created_at.desc())
    )
    return result.scalars().all()


@router.delete("/{webhook_id}", status_code=204)
async def delete_webhook(webhook_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    hook = await get_or_404(db, WebhookSubscription, webhook_id, "Webhook")
    await db.delete(hook)
    await db.commit()
