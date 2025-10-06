import asyncio
import pytest

pytest.importorskip("aiosqlite")

from bot_moderator.data.database import Database
from bot_moderator.services.join_request_service import JoinRequestService




def test_join_request_flow(tmp_path):
    async def run():
        db = Database(url="sqlite+aiosqlite:///:memory:", storage_dir=str(tmp_path))
        await db.connect()
        service = JoinRequestService(db)

        request = await service.upsert_request(chat_id=42, user_id=100, questions=["Q1", "Q2"], expires_at=None)
        assert request.status == "pending"
        assert request.questionnaire_answers["questions"] == ["Q1", "Q2"]

        pending = await service.list_pending(42)
        assert len(pending) == 1

        await service.store_answers(42, 100, ["A1", "A2"])
        stored = await service.get_request(42, 100)
        assert stored.questionnaire_answers["answers"] == ["A1", "A2"]

        await service.set_status(42, 100, "approved")
        updated = await service.get_request(42, 100)
        assert updated.status == "approved"

        await db.disconnect()

    asyncio.run(run())
