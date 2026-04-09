import uuid
from typing import List

from anyio import to_thread

from users.models import UserModel
from pins.repository.pin import PinRepository
from pins.repository.comment import CommentRepository
from pins.schemas import PinCommentResponse
from boards.models import PinCommentModel
from core.exception import NotFoundError, ForbiddenError, BadRequestError, ConflictError
from core.infra.comment_filter import CommentFilter


class CommentService:
    def __init__(
        self,
        pin_repo: PinRepository,
        comment_repo: CommentRepository,
        comment_filter: CommentFilter,
    ):
        self.pin_repo = pin_repo
        self.comment_repo = comment_repo
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

    async def get_comments(self, pin_id: uuid.UUID) -> List[PinCommentModel]:
        pin = await self.pin_repo.get_pin_by_id(pin_id)
        if not pin:
            raise NotFoundError("Pin not found")
        comments = await self.comment_repo.get_all_comments_flat(pin_id)
        return self._build_comment_tree(comments)

    async def get_comment_by_id(self, comment_id: uuid.UUID) -> PinCommentModel:
        comment = await self.comment_repo.get_comment_by_id(comment_id)
        if not comment:
            raise NotFoundError("Comment not found")

        comments = await self.comment_repo.get_all_comments_flat(comment.pin_id)
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
        pin = await self.pin_repo.get_pin_by_id(pin_id)
        if not pin:
            raise NotFoundError("Pin not found")
        if parent_id:
            comment = await self.comment_repo.get_comment_by_id(parent_id)
            if not comment:
                raise NotFoundError("Comment not found")
        if not await to_thread.run_sync(self.comment_filter.filter_comment_text, text):
            raise BadRequestError("Comment is toxic")
        new_comment = await self.comment_repo.add_comment(
            pin_id=pin_id, user_id=user_id, text=text, parent_id=parent_id
        )
        return new_comment

    async def update_comment(
        self, comment_id: uuid.UUID, user_id: uuid.UUID, text: str
    ) -> PinCommentModel:
        comment = await self.comment_repo.get_comment_by_id(comment_id)
        if not comment:
            raise NotFoundError("Comment not found")
        if comment.user_id != user_id:
            raise ForbiddenError("Not the comment owner")
        updated_comment = await self.comment_repo.update_comment(comment, text)
        return updated_comment

    async def delete_comment(
        self, pin_id: uuid.UUID, comment_id: uuid.UUID, current_user: UserModel
    ) -> None:
        pin = await self.pin_repo.get_pin_by_id(pin_id)
        if not pin:
            raise NotFoundError("Pin not found")
        comment = await self.comment_repo.get_comment_by_id(comment_id)
        if not comment:
            raise NotFoundError("Comment not found")
        if comment.user_id != current_user.id:
            raise ForbiddenError("Not the comment owner")
        if comment.pin_id != pin.id:
            raise NotFoundError("Comment not found")
        await self.comment_repo.delete_comment(comment)

    async def add_comment_like(
        self, pin_id: uuid.UUID, comment_id: uuid.UUID, user_id: uuid.UUID
    ) -> PinCommentModel:
        pin = await self.pin_repo.get_pin_by_id(pin_id)
        if not pin:
            raise NotFoundError("Pin not found")
        comment = await self.comment_repo.get_comment_by_id(comment_id)
        if not comment:
            raise NotFoundError("Comment not found")

        existing_like = await self.comment_repo.get_comment_like(comment_id, user_id)
        if existing_like:
            raise ConflictError("Comment already liked")

        updated_comment = await self.comment_repo.add_comment_like(comment, user_id)
        return updated_comment

    async def delete_comment_like(
        self, pin_id: uuid.UUID, comment_id: uuid.UUID, user_id: uuid.UUID
    ) -> PinCommentModel:
        pin = await self.pin_repo.get_pin_by_id(pin_id)
        if not pin:
            raise NotFoundError("Pin not found")
        comment = await self.comment_repo.get_comment_by_id(comment_id)
        if not comment:
            raise NotFoundError("Comment not found")

        like = await self.comment_repo.get_comment_like(comment_id, user_id)
        if not like:
            raise NotFoundError("Comment like not found")

        updated_comment = await self.comment_repo.delete_comment_like(comment, like)
        return updated_comment
