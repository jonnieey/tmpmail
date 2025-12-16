#!/usr/bin/env python
# guerrillamail_service.py
import asyncio
import json
from typing import List, Dict, Any, Callable
from datetime import datetime, timezone
from .base import BaseEmailService, ServiceMessage
from ..logging_config import get_logger

# Get module logger
logger = get_logger(__name__)


class GuerrillaMailService(BaseEmailService):
    """Guerrilla Mail service implementation"""

    SERVICE_NAME = "guerrillamail"

    def __init__(self):
        super().__init__()
        self.session = None
        self._known_message_ids = set()
        self._base_url = "http://api.guerrillamail.com"
        logger.debug("GuerrillaMailService initialized")

    async def create_account(self, **kwargs) -> Dict[str, Any]:
        """Create a new Guerrilla Mail account"""
        logger.debug(f"create_account called with kwargs: {kwargs}")

        try:
            import aiohttp

            self.session = aiohttp.ClientSession()

            # Get initial session and email address
            logger.debug("Getting initial session from Guerrilla Mail")
            async with self.session.get(
                f"{self._base_url}/ajax.php",
                params={"f": "get_email_address", "ip": "127.0.0.1"},
            ) as response:
                if response.status != 200:
                    raise Exception(f"Failed to get session: {response.status}")

                data = await response.json()

                if data.get("email_addr"):
                    email_address = data["email_addr"]
                    session_id = data.get("sid_token")
                    email_timestamp = data.get("email_timestamp", 0)
                else:
                    raise Exception("No email address received from API")

                logger.debug(
                    f"Got email address: {email_address}, session_id: {session_id}"
                )

            # Store account data
            account_data = {
                "service": self.SERVICE_NAME,
                "address": email_address,
                "session_id": session_id,
                "email_timestamp": email_timestamp,
                "created_at": datetime.now().isoformat(),
            }

            logger.info(f"Guerrilla Mail account created: {email_address}")
            logger.debug(f"Account data: {account_data}")

            return account_data

        except ImportError:
            logger.error("aiohttp not installed")
            raise ImportError(
                "aiohttp library not installed. Install with: pip install aiohttp"
            )
        except Exception as e:
            logger.error(f"Error creating Guerrilla Mail account: {e}", exc_info=True)
            raise

    async def restore_account(self, account_data: Dict[str, Any]) -> Dict[str, Any]:
        """Restore Guerrilla Mail account from saved data"""
        logger.debug(
            f"restore_account called with account_data keys: {list(account_data.keys())}"
        )

        try:
            import aiohttp

            if not self.session:
                self.session = aiohttp.ClientSession()

            session_id = account_data.get("session_id")
            email_address = account_data.get("address")
            email_timestamp = account_data.get("email_timestamp", 0)

            if not session_id or not email_address:
                logger.warning("Missing session data, creating new account")
                return await self.create_account()

            # Check if session is expired (1 hour timeout)
            current_time = int(datetime.now().timestamp())
            expiry_time = email_timestamp + 3600 - 5  # 1 hour - 5 seconds buffer

            if current_time >= expiry_time:
                logger.info("Session expired, renewing...")
                # Renew session by setting the same email address
                return await self._renew_session(account_data)

            # Test the session by getting email list
            async with self.session.get(
                f"{self._base_url}/ajax.php",
                params={
                    "f": "get_email_list",
                    "sid_token": session_id,
                    "ip": "127.0.0.1",
                    "offset": 0,
                },
            ) as response:
                if response.status != 200:
                    logger.warning("Session validation failed, creating new account")
                    return await self.create_account()

            logger.info(f"Account restored: {email_address}")
            return account_data

        except Exception as e:
            logger.error(
                f"Failed to restore Guerrilla Mail account: {e}", exc_info=True
            )
            # Fall back to creating a new account
            return await self.create_account()

    async def _renew_session(self, account_data: Dict[str, Any]) -> Dict[str, Any]:
        """Renew an expired session by setting the same email address"""
        try:
            email_address = account_data.get("address")
            if not email_address:
                return await self.create_account()

            # Extract local part from email address (before @)
            local_part = (
                email_address.split("@")[0] if "@" in email_address else email_address
            )

            # Set email address to renew session
            async with self.session.get(
                f"{self._base_url}/ajax.php",
                params={
                    "f": "set_email_user",
                    "email_user": local_part,
                    "ip": "127.0.0.1",
                },
            ) as response:
                if response.status != 200:
                    raise Exception("Failed to renew session")

                data = await response.json()

                if data.get("email_addr"):
                    account_data["address"] = data["email_addr"]
                    account_data["session_id"] = data.get("sid_token")
                    account_data["email_timestamp"] = data.get("email_timestamp", 0)
                    logger.info(f"Session renewed: {account_data['address']}")
                    return account_data
                else:
                    raise Exception("Failed to renew session")

        except Exception as e:
            logger.error(f"Failed to renew session: {e}")
            # Create new account if renewal fails
            return await self.create_account()

    async def get_messages(self, account_data: Dict[str, Any]) -> List[ServiceMessage]:
        """Get all messages for the account"""
        logger.debug("get_messages called")

        try:
            if not self.session:
                await self.restore_account(account_data)

            session_id = account_data.get("session_id")
            if not session_id:
                logger.warning("No session ID, cannot get messages")
                return []

            messages = []

            # Get messages from API
            async with self.session.get(
                f"{self._base_url}/ajax.php",
                params={
                    "f": "get_email_list",
                    "sid_token": session_id,
                    "ip": "127.0.0.1",
                    "offset": 0,
                },
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    email_list = data.get("list", [])

                    for email_data in email_list:
                        message = self._convert_to_servicemessage(email_data)
                        messages.append(message)

                    logger.info(
                        f"Retrieved {len(messages)} messages from Guerrilla Mail"
                    )
                else:
                    logger.warning(f"Failed to get messages: {response.status}")

            return messages

        except Exception as e:
            logger.error(f"Error getting messages: {e}", exc_info=True)
            return []

    async def get_message_by_id(
        self, account_data: Dict[str, Any], message_id: str
    ) -> ServiceMessage:
        """Get specific message by ID"""
        logger.debug(f"get_message_by_id called for message_id: {message_id}")

        try:
            if not self.session:
                await self.restore_account(account_data)

            session_id = account_data.get("session_id")
            if not session_id:
                raise ValueError("No session ID available")

            # Get message content
            async with self.session.get(
                f"{self._base_url}/ajax.php",
                params={
                    "f": "fetch_email",
                    "sid_token": session_id,
                    "ip": "127.0.0.1",
                    "email_id": message_id,
                },
            ) as response:
                if response.status == 200:
                    email_data = await response.json()
                    if not email_data:
                        raise ValueError(f"Message {message_id} not found")

                    message = self._convert_to_servicemessage(email_data)
                    logger.debug(f"Retrieved message {message_id}")
                    return message
                else:
                    logger.error(
                        f"Failed to get message {message_id}: {response.status}"
                    )
                    raise ValueError(f"Message {message_id} not found")

        except Exception as e:
            logger.error(f"Error getting message by ID: {e}", exc_info=True)
            raise

    async def monitor_messages(
        self,
        account_data: Dict[str, Any],
        message_callback: Callable[[ServiceMessage], Any],
        interval: int = 5,
    ) -> None:
        """
        Monitor for new messages using polling
        """
        logger.info(
            f"Starting Guerrilla Mail message monitoring with interval: {interval}s"
        )
        self._known_message_ids.clear()
        self._stop_monitoring.clear()

        async def poll_for_messages():
            """Poll Guerrilla Mail API for new messages"""
            poll_count = 0

            while not self._stop_monitoring.is_set():
                try:
                    poll_count += 1
                    logger.debug(f"Guerrilla Mail poll #{poll_count}")

                    # Get current messages
                    messages = await self.get_messages(account_data)

                    # Find new messages
                    current_ids = {msg.id for msg in messages}

                    # If this is the first poll, just mark all as known
                    if not self._known_message_ids:
                        logger.debug(
                            f"First poll, marking {len(current_ids)} messages as known"
                        )
                        self._known_message_ids.update(current_ids)
                        # Optionally process all existing messages on first poll
                        for msg in messages:
                            await message_callback(msg)
                    else:
                        new_ids = current_ids - self._known_message_ids

                        if new_ids:
                            logger.info(f"Found {len(new_ids)} new message(s)")
                            # Process new messages
                            for msg in messages:
                                if msg.id in new_ids:
                                    await message_callback(msg)
                        else:
                            logger.debug("No new messages found")

                        # Update known IDs
                        self._known_message_ids.update(new_ids)

                    # Wait before next poll
                    await asyncio.sleep(interval)

                except asyncio.CancelledError:
                    logger.debug("Guerrilla Mail polling cancelled")
                    raise
                except Exception as e:
                    logger.error(f"Guerrilla Mail polling error: {e}")
                    await asyncio.sleep(interval)

        # Create the task to allow cancellation
        self._monitor_task = asyncio.create_task(poll_for_messages())

        try:
            logger.info("Guerrilla Mail monitoring active")
            await self._monitor_task
        except asyncio.CancelledError:
            logger.info("Guerrilla Mail monitoring cancelled")
        finally:
            logger.info("Guerrilla Mail monitoring stopped")

    def _convert_to_servicemessage(self, email_data: Dict) -> ServiceMessage:
        """Convert Guerrilla Mail message data to ServiceMessage"""
        logger.debug("Converting Guerrilla Mail message to ServiceMessage")

        # Extract message ID
        message_id = str(email_data.get("mail_id", ""))
        if not message_id:
            # Generate ID from content hash
            import hashlib

            content = json.dumps(email_data, sort_keys=True)
            message_id = hashlib.md5(content.encode()).hexdigest()

        # Extract sender
        sender = email_data.get("mail_from", "")

        # Extract subject
        subject = email_data.get("mail_subject", "No Subject")

        # Extract text content
        text = email_data.get("mail_body", "") or email_data.get("mail_excerpt", "")

        # Extract HTML content if available
        html = None  # Guerrilla Mail API returns plain text

        # Extract timestamp
        timestamp = None
        mail_timestamp = email_data.get("mail_timestamp")
        if mail_timestamp:
            try:
                # Convert timestamp (usually Unix timestamp)
                if isinstance(mail_timestamp, str):
                    mail_timestamp = int(mail_timestamp)
                timestamp = datetime.fromtimestamp(mail_timestamp, tz=timezone.utc)
            except Exception as e:
                logger.debug(f"Could not parse timestamp: {e}")

        message = ServiceMessage(
            id=message_id,
            sender=sender,
            subject=subject,
            text=text,
            html=html,
            timestamp=timestamp,
            attachments=[],  # Guerrilla Mail might not support attachments
            raw=email_data,
        )

        logger.debug(
            f"Converted message: ID={message.id}, From={message.sender}, Subject={message.subject[:30]}..."
        )
        return message

    async def validate_account(self, account_data: Dict[str, Any]) -> bool:
        """Validate Guerrilla Mail account"""
        logger.debug("Validating Guerrilla Mail account")

        try:
            import aiohttp

            if not self.session:
                self.session = aiohttp.ClientSession()

            session_id = account_data.get("session_id")
            if not session_id:
                logger.warning("No session ID for validation")
                return False

            # Check if session is expired
            email_timestamp = account_data.get("email_timestamp", 0)
            current_time = int(datetime.now().timestamp())
            expiry_time = email_timestamp + 3600 - 5

            if current_time >= expiry_time:
                logger.debug("Session expired")
                return False

            # Test the session by getting email list
            async with self.session.get(
                f"{self._base_url}/ajax.php",
                params={
                    "f": "get_email_list",
                    "sid_token": session_id,
                    "ip": "127.0.0.1",
                    "offset": 0,
                },
            ) as response:
                is_valid = response.status == 200
                logger.debug(f"Account validation result: {is_valid}")
                return is_valid

        except Exception as e:
            logger.error(f"Account validation error: {e}", exc_info=True)
            return False

    async def set_email_address(
        self, account_data: Dict[str, Any], local_part: str
    ) -> Dict[str, Any]:
        """Set custom email address (local part) for Guerrilla Mail"""
        logger.debug(f"Setting email address to: {local_part}")

        try:
            import aiohttp

            if not self.session:
                self.session = aiohttp.ClientSession()

            # Set email address
            async with self.session.get(
                f"{self._base_url}/ajax.php",
                params={
                    "f": "set_email_user",
                    "email_user": local_part,
                    "ip": "127.0.0.1",
                },
            ) as response:
                if response.status != 200:
                    raise Exception("Failed to set email address")

                data = await response.json()

                if data.get("email_addr"):
                    account_data["address"] = data["email_addr"]
                    account_data["session_id"] = data.get("sid_token")
                    account_data["email_timestamp"] = data.get("email_timestamp", 0)
                    logger.info(f"Email address set to: {account_data['address']}")
                    return account_data
                else:
                    raise Exception("Failed to set email address")

        except Exception as e:
            logger.error(f"Error setting email address: {e}", exc_info=True)
            raise

    async def get_account_info(self, account_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get account information including session expiry"""
        info = await super().get_account_info(account_data)

        # Add session expiry information
        email_timestamp = account_data.get("email_timestamp", 0)
        if email_timestamp:
            try:
                current_time = int(datetime.now().timestamp())
                expiry_time = email_timestamp + 3600  # 1 hour
                seconds_left = max(0, expiry_time - current_time)
                minutes_left = seconds_left / 60
                info["session_expires_in_minutes"] = round(minutes_left, 1)
            except Exception:
                pass

        return info

    async def close(self):
        """Cleanup Guerrilla Mail resources"""
        logger.info("Closing Guerrilla Mail service")
        await super().close()

        if self.session:
            try:
                logger.debug("Closing aiohttp session")
                await self.session.close()
                logger.debug("aiohttp session closed")
            except Exception as e:
                logger.error(f"Error closing session: {e}")
            self.session = None

        logger.info("Guerrilla Mail service closed")
