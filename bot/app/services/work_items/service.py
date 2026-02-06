from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from app.infrastructure.database.db import DB

logger = logging.getLogger(__name__)


async def create_work_item(
    db: DB,
    *,
    topic: str,
    kind: str,
    target_user_id: int,
    created_by_user_id: Optional[int] = None,
    priority: str = "normal",
    payload: Optional[dict[str, Any]] = None,
) -> None:
    """
    Creates an admin work item in backend tables.
    This runs in bot process and uses shared Postgres.
    """
    normalized_topic = (topic or "").strip().lower()
    normalized_kind = (kind or "").strip().lower()
    normalized_priority = (priority or "").strip().lower() or "normal"
    if not normalized_topic or not normalized_kind or not target_user_id:
        return

    now = datetime.now(timezone.utc)
    payload_json = None
    if payload is not None:
        try:
            payload_json = json.dumps(payload, ensure_ascii=False)
        except Exception:
            payload_json = json.dumps({"raw": str(payload)}, ensure_ascii=False)

    try:
        await db.documents.connection.execute(
            sql=(
                """
                INSERT INTO work_items(
                    topic,
                    kind,
                    status,
                    priority,
                    created_by_user_id,
                    target_user_id,
                    assignee_admin_id,
                    payload,
                    created_at,
                    updated_at
                )
                VALUES (%s,%s,%s,%s,%s,%s,NULL,%s,%s,%s)
                """
            ),
            params=(
                normalized_topic,
                normalized_kind,
                "new",
                normalized_priority,
                int(created_by_user_id) if created_by_user_id else None,
                int(target_user_id),
                payload_json,
                now,
                now,
            ),
        )
    except Exception:
        logger.exception("Failed to create work item topic=%s kind=%s target_user_id=%s", topic, kind, target_user_id)

