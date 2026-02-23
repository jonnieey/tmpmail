"""Tests for the MailTMService."""
import pytest
from unittest.mock import MagicMock, AsyncMock
from tmpmail.services.mailtm_service import MailTMService
from tmpmail.services.base import ServiceMessage


@pytest.fixture
def mock_mailtm_lib(monkeypatch):
    """Mock the mailtm library."""
    mock_mailtm_class = MagicMock()
    mock_mailtm_instance = MagicMock()

    # Mock account creation
    mock_account = MagicMock()
    mock_account.address = "test@mail.tm"
    mock_mailtm_instance.get_account = AsyncMock(return_value=mock_account)
    mock_token = MagicMock(token="test_token")
    mock_mailtm_instance.get_account_token = AsyncMock(return_value=mock_token)

    # Mock message fetching
    raw_msg = MagicMock()
    raw_msg.id = "msg1"
    raw_msg.from_.address = "sender@domain.com"
    raw_msg.subject = "Test"
    raw_msg.created_at = None
    mock_messages = MagicMock()
    mock_messages.hydra_member = [raw_msg]
    mock_mailtm_instance.get_messages = AsyncMock(return_value=mock_messages)

    one_msg_details = MagicMock(text="Details", html=None, created_at=None)
    mock_mailtm_instance.get_message_by_id = AsyncMock(return_value=one_msg_details)

    mock_mailtm_class.return_value = mock_mailtm_instance
    monkeypatch.setattr("mailtm.MailTM", mock_mailtm_class)
    return mock_mailtm_instance


@pytest.mark.asyncio
async def test_create_account(mock_mailtm_lib):
    """Test creating a mailtm account."""
    service = MailTMService()
    account_data = await service.create_account()

    assert account_data["service"] == "mailtm"
    assert account_data["address"] == "test@mail.tm"
    assert account_data["token"] == "test_token"


@pytest.mark.asyncio
async def test_get_messages(mock_mailtm_lib):
    """Test getting messages from mailtm."""
    service = MailTMService()
    await service.create_account()
    messages = await service.get_messages({"token": "test_token"})

    assert len(messages) == 1
    msg = messages[0]
    assert isinstance(msg, ServiceMessage)
    assert msg.id == "msg1"
    assert msg.sender == "sender@domain.com"
    assert msg.text == "Details"
