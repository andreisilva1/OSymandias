from collections.abc import AsyncGenerator
from typing import Any, TypeVar

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from osymandias.runtime.db.session import AsyncSessionLocal

T = TypeVar("T")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def get_or_404(db: AsyncSession, model: type[T], id_val: Any, entity: str) -> T:
    obj = await db.get(model, id_val)
    if not obj:
        raise HTTPException(status_code=404, detail=f"{entity} not found")
    return obj
