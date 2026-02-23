"""Tests for the base service classes."""
from datetime import datetime, timezone
from tmpmail.services.base import ServiceMessage, BaseEmailService


def test_service_message_to_dict():
    """Test converting a ServiceMessage to a dictionary."""
    now = datetime.now(timezone.utc)
    msg = ServiceMessage(
        id="123",
        sender="sender@example.com",
        subject="Test Subject",
        text="Hello",
        timestamp=now,
    )
    msg_dict = msg.to_dict()
    assert msg_dict["id"] == "123"
    assert msg_dict["timestamp"] == now.isoformat()


def test_service_message_from_dict():
    """Test creating a ServiceMessage from a dictionary."""
    now = datetime.now(timezone.utc)
    msg_dict = {
        "id": "123",
        "sender": "sender@example.com",
        "subject": "Test Subject",
        "text": "Hello",
        "timestamp": now.isoformat(),
        "html": None,
        "attachments": None,
        "raw": None,
    }
    msg = ServiceMessage.from_dict(msg_dict)
    assert msg.id == "123"
    assert msg.timestamp == now


def test_base_email_service_extract_links():
    """Test the default link extraction implementation."""

    class DummyService(BaseEmailService):
        async def create_account(self, **kwargs):
            pass

        async def get_messages(self, account_data):
            pass

        async def get_message_by_id(self, account_data, message_id):
            pass

        async def monitor_messages(self, account_data, message_callback, interval=5):
            pass

        async def validate_account(self, account_data):
            pass

    service = DummyService()
    message = ServiceMessage(
        id="1",
        sender="",
        subject="",
        text="Here is a link: https://example.com/page and another http://test.com",
    )
    pattern = r"https?://\S+"
    links = service.extract_links(message, pattern)
    assert len(links) == 2
    assert "https://example.com/page" in links
    assert "http://test.com" in links
