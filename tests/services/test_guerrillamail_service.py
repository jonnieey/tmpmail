"""Tests for the GuerrillaMailService."""
import pytest
from unittest.mock import AsyncMock, patch
from tmpmail.services.guerrillamail_service import GuerrillaMailService
from tmpmail.services.base import ServiceMessage


@pytest.fixture
def mock_aiohttp_session():
    """Mock aiohttp.ClientSession."""
    with patch("aiohttp.ClientSession") as mock_session_class:
        mock_session_instance = mock_session_class.return_value
        # The return value of get() should be an async context manager
        mock_get_response = AsyncMock()
        mock_session_instance.get.return_value = mock_get_response
        yield mock_get_response


@pytest.mark.asyncio
async def test_create_account(mock_aiohttp_session):
    """Test creating a guerrillamail account."""
    mock_response = mock_aiohttp_session.__aenter__.return_value
    mock_response.status = 200
    mock_response.json = AsyncMock(
        return_value={
            "email_addr": "test@guerrillamail.com",
            "sid_token": "test_sid",
            "email_timestamp": 123456,
        }
    )

    service = GuerrillaMailService()
    account_data = await service.create_account()

    assert account_data["service"] == "guerrillamail"
    assert account_data["address"] == "test@guerrillamail.com"
    assert account_data["session_id"] == "test_sid"


@pytest.mark.asyncio
async def test_get_messages(mock_aiohttp_session):
    """Test getting messages from guerrillamail."""
    # This test requires careful sequencing of mocks
    # First call is to create_account, second is to get_messages
    mock_aiohttp_session.__aenter__.side_effect = [
        # First async context for create_account
        AsyncMock(
            status=200,
            json=AsyncMock(
                return_value={
                    "email_addr": "test@guerrillamail.com",
                    "sid_token": "test_sid",
                    "email_timestamp": 123456,
                }
            ),
        ),
        # Second async context for get_messages
        AsyncMock(
            status=200,
            json=AsyncMock(
                return_value={
                    "list": [
                        {
                            "mail_id": "msg1",
                            "mail_from": "s@d.com",
                            "mail_subject": "T",
                            "mail_body": "H",
                        }
                    ]
                }
            ),
        ),
    ]

    service = GuerrillaMailService()
    account_data = await service.create_account()
    messages = await service.get_messages(account_data)

    assert len(messages) == 1
    msg = messages[0]
    assert isinstance(msg, ServiceMessage)
    assert msg.id == "msg1"
