import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai.models import AIOperationModel
from users.models import UserModel


class AIRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_operation_by_id(
        self, operation_id: uuid.UUID, user: UserModel
    ) -> AIOperationModel | None:
        query = select(AIOperationModel).where(
            AIOperationModel.id == operation_id,
            AIOperationModel.user_id == user.id,
        )
        result = await self.db.execute(query)
        operation = result.scalar_one_or_none()
        return operation
