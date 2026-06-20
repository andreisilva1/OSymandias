from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from osymandias.runtime.api.deps import get_db, get_or_404
from osymandias.runtime.api.schemas.memory import MemoryEntryResponse
from osymandias.runtime.models.memory_entry import MemoryEntry

router = APIRouter(prefix="/api/v1/memory", tags=["memory"])


@router.get("", response_model=list[MemoryEntryResponse])
async def list_memory(
    scope: str | None = None,
    scope_id: str | None = None,
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
):
    q = select(MemoryEntry).order_by(desc(MemoryEntry.created_at)).limit(limit)
    if scope:
        q = q.where(MemoryEntry.scope == scope.upper())
    if scope_id:
        q = q.where(MemoryEntry.scope_id == scope_id)
    result = await db.execute(q)
    return result.scalars().all()


@router.delete("/{entry_id}", status_code=204)
async def delete_memory_entry(entry_id: str, db: AsyncSession = Depends(get_db)):
    entry = await get_or_404(db, MemoryEntry, entry_id, "Memory entry")
    await db.delete(entry)
    await db.commit()
