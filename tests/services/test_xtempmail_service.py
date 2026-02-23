"""Tests for the XTempMailService."""
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock
from tmpmail.services.xtempmail_service import XTempMailService
from tmpmail.services.base import ServiceMessage


@pytest.fixture
def mock_xtempmail_lib(monkeypatch):
    """Mock the xtempmail library."""
    mock_email_class = MagicMock()
    mock_email_instance = MagicMock()
    mock_email_instance.email = "test@mailto.plus"

    # Mock the on.message decorator chain
    decorator_mock = MagicMock(return_value=lambda f: f)
    mock_email_instance.on.message.return_value = decorator_mock

    mock_email_class.return_value = mock_email_instance

    monkeypatch.setattr("xtempmail.aiomail.Email", mock_email_class)
    monkeypatch.setattr("xtempmail.aiomail.EMAIL", MagicMock())
    # Return both the main instance and the mock for the decorator
    return mock_email_instance, decorator_mock


@pytest.mark.asyncio
async def test_create_account(mock_xtempmail_lib):
    """Test creating an xtempmail account."""
    mock_instance, _ = mock_xtempmail_lib
    service = XTempMailService()
    # Manually assign the mocked instance
    service.email_instance = mock_instance
    account_data = await service.create_account()

    assert account_data["service"] == "xtempmail"
    assert account_data["address"] == "test@mailto.plus"
    assert service.email_instance is not None


@pytest.mark.asyncio
async def test_get_messages(mock_xtempmail_lib):
    """Test getting messages from xtempmail."""
    mock_instance, _ = mock_xtempmail_lib
    raw_msg = MagicMock()
    raw_msg.id = "msg1"
    raw_msg.from_mail = "sender@domain.com"
    raw_msg.subject = "Test"
    raw_msg.text = "This is a test message."
    raw_msg.html = ""
    raw_msg.attachments = []
    raw_msg.timestamp = None

    mock_instance._messages = [raw_msg]

    service = XTempMailService()
    service.email_instance = mock_instance  # Manually assign the mocked instance
    messages = await service.get_messages({})

    assert len(messages) == 1
    msg = messages[0]
    assert isinstance(msg, ServiceMessage)
    assert msg.id == "msg1"
    assert msg.sender == "sender@domain.com"


@pytest.mark.asyncio
async def test_monitor_messages(mock_xtempmail_lib):
    """Test monitoring for new messages."""
    mock_instance, decorator_mock = mock_xtempmail_lib
    service = XTempMailService()
    account_data = {"address": "test@domain.com"}
    service.email_instance = mock_instance

    callback_mock = AsyncMock()
    stop_listener_event = asyncio.Event()

    async def mock_listen():
        """A mock listener that waits to be stopped."""
        await stop_listener_event.wait()

    mock_instance.listen = mock_listen

    async def message_producer():
        # Give the monitor a moment to register the handler
        await asyncio.sleep(0.1)

        # Ensure the decorator that registers the handler was called
        assert decorator_mock.called
        handler = decorator_mock.call_args[0][0]

        # Simulate a new message
        raw_msg = MagicMock(
            id="new_msg",
            from_mail="new@sender.com",
            subject="New",
            text="Hi",
            html="",
            attachments=[],
            timestamp=None,
        )
        await handler(raw_msg)

        # Stop the monitoring loop and the listener
        await service.stop_monitoring()
        stop_listener_event.set()

    monitor_task = asyncio.create_task(
        service.monitor_messages(account_data, callback_mock, interval=1)
    )
    producer_task = asyncio.create_task(message_producer())

    await asyncio.gather(monitor_task, producer_task)

    callback_mock.assert_called_once()
    called_message = callback_mock.call_args[0][0]
    assert called_message.id == "new_msg"
