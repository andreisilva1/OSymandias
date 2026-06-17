from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from osymandias.runtime.api.deps import get_db
from osymandias.runtime.models.memory_entry import MemoryEntry

router = APIRouter(prefix="/api/v1/memory", tags=["memory"])


@router.get("")
async def list_memory(
    scope: str | None = None,
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
):
    q = select(MemoryEntry).order_by(desc(MemoryEntry.created_at)).limit(limit)
    if scope:
        q = q.where(MemoryEntry.scope == scope.upper())
    result = await db.execute(q)
    entries = result.scalars().all()
    return [
        {
            "id": str(e.id),
            "scope": e.scope,
            "scope_id": str(e.scope_id) if e.scope_id else None,
            "key": e.key,
            "value": e.value,
            "access_count": e.access_count,
            "created_at": e.created_at.isoformat(),
            "last_accessed_at": e.last_accessed_at.isoformat() if e.last_accessed_at else None,
            "expires_at": e.expires_at.isoformat() if e.expires_at else None,
        }
        for e in entries
    ]


@router.delete("/{entry_id}", status_code=204)
async def delete_memory_entry(entry_id: str, db: AsyncSession = Depends(get_db)):
    entry = await db.get(MemoryEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Memory entry not found")
    await db.delete(entry)
    await db.commit()
