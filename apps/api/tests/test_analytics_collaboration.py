from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.analytics.collaboration_schemas import CommentCreate


def test_comment_requires_content() -> None:
    with pytest.raises(ValidationError):
        CommentCreate(body="")


def test_comment_rejects_duplicate_mentions() -> None:
    user_id = uuid4()
    with pytest.raises(ValidationError):
        CommentCreate(body="Revisar este indicador.", mentioned_user_ids=[user_id, user_id])
