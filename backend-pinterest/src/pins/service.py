import uuid
import base64
import io
from typing import List

from PIL import Image, UnidentifiedImageError

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import logger
from src.core.infra.cache import CacheService
from src.core.infra.s3 import S3Service
from src.core.infra.comment_filter import CommentFilter
from src.core.exception import (
    ConflictError,
    NotFoundError,
    ForbiddenError,
    BadRequestError,
)

from src.boards.models import PinModel, PinCommentModel
from src.users.models import UserModel
from src.pins.schemas import (
    PinCommentResponse,
    PinCreate,
    PinUpdate,
    CreatedAt,
    Popularity,
    PinResponse,
    PinListResponse,
)
from src.tags.service import TagService
from src.pins.repository import PinRepository
from src.pins.task import index_image_task


class PinService:
    def __init__(
        self,
        db: AsyncSession,
        cache: CacheService,
        repo: PinRepository,
        tag_service: TagService,
        s3_service: S3Service,
        comment_filter: CommentFilter,
    ) -> None:
        self.db = db
        self.cache = cache
        self.repo = repo
        self.tag_service = tag_service
        self.s3_service = s3_service
        self.comment_filter = comment_filter

    def _build_comment_tree(self, comments: List[PinCommentModel]):
        id_to_resp = {
            c.id: PinCommentResponse(
                id=c.id,
                comment=c.comment,
                parent_id=c.parent_id,
                likes_count=c.likes_count,
                created_at=c.created_at,
                user=c.user,
                replies=[],
            )
            for c in comments
        }

        root_comments = []
        for c in comments:
            resp = id_to_resp[c.id]
            if c.parent_id is None:
                root_comments.append(resp)
            else:
                parent = id_to_resp.get(c.parent_id)
                if parent is not None:
                    parent.replies.append(resp)

        root_comments.sort(key=lambda x: x.created_at, reverse=True)
        return root_comments

    async def _get_from_cache(self, pin_id: uuid.UUID) -> List[PinListResponse] | None:
        try:
            data = await self.cache.get_pattern(f"related_pins:{pin_id}:*")
            if data:
                return [
                    PinListResponse.model_validate_json(item)
                    for item in data
                    if item is not None
                ]
        except Exception as e:
            logger.warning(f"Cache read error: {e}")
            return None

    async def _set_to_cache(self, pin_id: uuid.UUID, pins: list[PinModel]) -> None:
        try:
            for i, pin in enumerate(pins):
                pin_json = PinListResponse.model_validate(pin)
                await self.cache.set(
                    f"related_pins:{pin_id}:{i}", pin_json.model_dump_json(), 600
                )
        except Exception as e:
            logger.error(f"Cache write error: {e}")

    async def get_pin_by_id(self, pin_id: uuid.UUID) -> PinModel | None:
        result = await self.repo.get_pin_by_id(pin_id)
        if result is None:
            raise NotFoundError("Pin not found")
        return result

    async def get_pins(
        self,
        offset: int = 0,
        limit: int = 20,
        search: str | None = None,
        tags: list[str] = [],
        created_at: CreatedAt | None = None,
        popularity: Popularity | None = None,
    ) -> List[PinModel]:
        return await self.repo.get_pins(
            offset=offset,
            limit=limit,
            search=search,
            tags=tags,
            created_at=created_at,
            popularity=popularity,
        )

    async def get_pins_by_ids(self, pin_ids: list[str]) -> List[PinModel]:
        return await self.repo.get_pins_by_ids(pin_ids)

    async def create_pin(
        self,
        image: UploadFile,
        owner: UserModel,
        data: PinCreate,
    ) -> PinModel:
        allowed = {"image/jpeg", "image/png", "image/webp", "image/gif"}
        if image.content_type not in allowed:
            raise BadRequestError("Unsupported image type")

        try:
            with Image.open(image.file) as img:
                if img.size[0] > 1100 or img.size[1] > 2100:
                    raise BadRequestError("Image dimensions exceed 1100x2100 pixels")
        except UnidentifiedImageError:
            raise BadRequestError("Invalid or corrupted image file")

        await image.seek(0)
        original_content = await image.read()
        await image.seek(0)

        image_url = await self.s3_service.upload_image_to_s3(image)

        with Image.open(io.BytesIO(original_content)) as img:
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.thumbnail((500, 500))
            thumb_io = io.BytesIO()
            img.save(thumb_io, format="JPEG")
            base64_thumb = base64.b64encode(thumb_io.getvalue()).decode("utf-8")

        tags = await self.tag_service.get_or_create_tag(data.tags)
        pin = await self.repo.create_pin(owner, data, image_url, tags)
        index_image_task.delay(str(pin.id), base64_thumb)
        return pin

    async def update_pin(
        self, pin: PinModel, data: PinUpdate, current_user: UserModel
    ) -> PinModel:
        if pin.owner_id != current_user.id:
            raise ForbiddenError("Not the pin owner")
        update_data = data.model_dump(exclude_unset=True)
        if "tags" in update_data:
            pin.tags = await self.tag_service.get_or_create_tag(update_data["tags"])
            del update_data["tags"]
        return await self.repo.update_pin(pin, update_data)

    async def delete_pin(self, pin: PinModel, current_user: UserModel) -> None:
        if pin.owner_id != current_user.id:
            raise ForbiddenError("Not the pin owner")
        await self.repo.delete_pin(pin)

    async def get_related_pins(
        self, pin_id: uuid.UUID, limit: int = 20
    ) -> List[PinModel]:
        cached_pins = await self._get_from_cache(pin_id)
        if cached_pins:
            return cached_pins
        base_pin = await self.repo.get_pin_by_id(pin_id)
        if not base_pin or not base_pin.tags:
            return []

        tag_ids = [tag.id for tag in base_pin.tags]
        related_pins = await self.repo.get_related_by_tags(pin_id, tag_ids, limit)

        if related_pins:
            await self._set_to_cache(pin_id, related_pins)

        return related_pins

    async def like_pin(self, pin_id: uuid.UUID, user_id: uuid.UUID) -> PinModel:
        like = await self.repo.get_like(pin_id, user_id)
        pin = await self.repo.get_pin_by_id(pin_id)
        if like:
            raise ConflictError("Like already exists")
        await self.repo.add_like(pin_id, user_id)
        if hasattr(pin, "likes_count"):
            pin.likes_count += 1
            await self.db.flush()
        return pin

    async def unlike_pin(self, pin_id: uuid.UUID, user_id: uuid.UUID) -> PinModel:
        like = await self.repo.get_like(pin_id, user_id)
        pin = await self.repo.get_pin_by_id(pin_id)
        if not like:
            raise NotFoundError("Like not found")
        await self.repo.delete_like(like)
        if hasattr(pin, "likes_count") and pin.likes_count > 0:
            pin.likes_count -= 1
            await self.db.flush()
        return pin

    async def get_comments(self, pin_id: uuid.UUID) -> List[PinCommentModel]:
        pin = await self.repo.get_pin_by_id(pin_id)
        if not pin:
            raise NotFoundError("Pin not found")
        comments = await self.repo.get_all_comments_flat(pin_id)
        return self._build_comment_tree(comments)

    async def get_comment_by_id(self, comment_id: uuid.UUID) -> PinCommentModel:
        comment = await self.repo.get_comment_by_id(comment_id)
        if not comment:
            raise NotFoundError("Comment not found")

        comments = await self.repo.get_all_comments_flat(comment.pin_id)
        tree = self._build_comment_tree(comments)

        def find_in_tree(nodes):
            for node in nodes:
                if node.id == comment_id:
                    return node
                found = find_in_tree(node.replies)
                if found:
                    return found
            return None

        found_comment = find_in_tree(tree)
        return found_comment or comment

    async def add_comment(
        self,
        pin_id: uuid.UUID,
        parent_id: uuid.UUID | None,
        user_id: uuid.UUID,
        text: str,
    ) -> PinCommentModel:
        pin = await self.repo.get_pin_by_id(pin_id)
        if not pin:
            raise NotFoundError("Pin not found")
        if parent_id:
            comment = await self.repo.get_comment_by_id(parent_id)
            if not comment:
                raise NotFoundError("Comment not found")
        if not self.comment_filter.filter_comment_text(text):
            raise BadRequestError("Comment is toxic")
        new_comment = await self.repo.add_comment(
            pin_id=pin_id, user_id=user_id, text=text, parent_id=parent_id
        )
        return new_comment

    async def add_comment_like(
        self, pin_id: uuid.UUID, comment_id: uuid.UUID, user_id: uuid.UUID
    ) -> PinCommentModel:
        pin = await self.repo.get_pin_by_id(pin_id)
        if not pin:
            raise NotFoundError("Pin not found")
        comment = await self.repo.get_comment_by_id(comment_id)
        if not comment:
            raise NotFoundError("Comment not found")

        existing_like = await self.repo.get_comment_like(comment_id, user_id)
        if existing_like:
            raise ConflictError("Comment already liked")

        updated_comment = await self.repo.add_comment_like(comment, user_id)
        return updated_comment

    async def delete_comment_like(
        self, pin_id: uuid.UUID, comment_id: uuid.UUID, user_id: uuid.UUID
    ) -> PinCommentModel:
        pin = await self.repo.get_pin_by_id(pin_id)
        if not pin:
            raise NotFoundError("Pin not found")
        comment = await self.repo.get_comment_by_id(comment_id)
        if not comment:
            raise NotFoundError("Comment not found")

        like = await self.repo.get_comment_like(comment_id, user_id)
        if not like:
            raise NotFoundError("Comment like not found")

        updated_comment = await self.repo.delete_comment_like(comment, like)
        return updated_comment

    async def update_comment(
        self, comment_id: uuid.UUID, user_id: uuid.UUID, text: str
    ) -> PinCommentModel:
        comment = await self.repo.get_comment_by_id(comment_id)
        if not comment:
            raise NotFoundError("Comment not found")
        if comment.user_id != user_id:
            raise ForbiddenError("Not the comment owner")
        updated_comment = await self.repo.update_comment(comment, text)
        return updated_comment

    async def delete_comment(
        self, pin_id: uuid.UUID, comment_id: uuid.UUID, current_user: UserModel
    ) -> None:
        pin = await self.repo.get_pin_by_id(pin_id)
        if not pin:
            raise NotFoundError("Pin not found")
        await self.repo.get_all_comments_flat(pin_id)
        comment = await self.repo.get_comment_by_id(comment_id)
        if not comment:
            raise NotFoundError("Comment not found")
        if comment.user_id != current_user.id:
            raise ForbiddenError("Not the comment owner")
        if comment.pin_id != pin.id:
            raise NotFoundError("Comment not found")
        await self.repo.delete_comment(comment)

    async def get_pin_detail(self, pin_id: uuid.UUID) -> PinResponse:
        pin = await self.repo.get_pin_by_id(pin_id)
        if pin is None:
            raise NotFoundError("Pin not found")

        all_comments = await self.repo.get_all_comments_flat(pin_id)
        comment_tree = self._build_comment_tree(all_comments)

        pin_list = PinListResponse.model_validate(pin)
        return PinResponse(**pin_list.model_dump(), comments=comment_tree)
