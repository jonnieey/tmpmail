#!/usr/bin/env python
import asyncio
from typing import List, Dict, Any, Callable
from datetime import datetime
from .base import BaseEmailService, ServiceMessage
from ..logging_config import get_logger

# Get module logger
logger = get_logger(__name__)


class MailTMService(BaseEmailService):
    """MailTM service with polling-based monitoring"""

    SERVICE_NAME = "mailtm"

    def __init__(self):
        super().__init__()
        self.mailtm = None
        self._known_message_ids = set()
        logger.debug("MailTMService initialized")

    async def create_account(self, **kwargs) -> Dict[str, Any]:
        """Create new MailTM account"""
        logger.debug(f"create_account called with kwargs: {kwargs}")

        try:
            from mailtm import MailTM
            from mailtm.utils.misc import random_string

            if self.mailtm is None:
                self.mailtm = MailTM()

            random_password = random_string()
            logger.debug("Generating MailTM account")

            account = await self.mailtm.get_account(password=random_password)
            token = await self.mailtm.get_account_token(
                account.address, random_password
            )

            # Store account data
            account_data = {
                "service": self.SERVICE_NAME,
                "address": account.address,
                "token": token.token,
                "password": random_password,
                "created_at": datetime.now().isoformat(),
            }

            logger.info(f"MailTM account created: {account.address}")
            logger.debug("Account data stored")

            return account_data

        except ImportError:
            logger.error("MailTM library not installed")
            raise ImportError(
                "MailTM library not installed. Install with: pip install mailtm"
            )
        except Exception as e:
            logger.error(f"Error creating MailTM account: {e}", exc_info=True)
            raise

    async def restore_account(self, account_data: Dict[str, Any]) -> Dict[str, Any]:
        """Restore MailTM account from saved data"""
        logger.debug(
            f"restore_account called with account_data keys: {list(account_data.keys())}"
        )

        from mailtm import MailTM

        if self.mailtm is None:
            self.mailtm = MailTM()

        # Validate token
        token = account_data.get("token")
        if not token:
            logger.error("No token in account data")
            raise ValueError("No token in account data")

        try:
            logger.debug("Validating MailTM token")
            account = await self.mailtm.get_me(token)
            account_data["address"] = account.address

            logger.info(f"MailTM account restored: {account.address}")
            return account_data
        except Exception as e:
            logger.error(f"Failed to restore MailTM account: {e}", exc_info=True)
            raise Exception(f"Failed to restore MailTM account: {e}")

    async def get_messages(self, account_data: Dict[str, Any]) -> List[ServiceMessage]:
        """Get all MailTM messages"""
        logger.debug("get_messages called")

        if self.mailtm is None:
            await self.restore_account(account_data)

        token = account_data.get("token")
        if not token:
            logger.warning("No token available for MailTM")
            return []

        messages = []
        try:
            logger.debug("Fetching messages from MailTM API")
            raw_messages = await self.mailtm.get_messages(token, page=1)

            for raw_msg in raw_messages.hydra_member:
                # Parse timestamp if available
                timestamp = None
                if hasattr(raw_msg, "created_at") and raw_msg.created_at:
                    timestamp = raw_msg.created_at

                message = ServiceMessage(
                    id=raw_msg.id,
                    sender=raw_msg.from_.address
                    if hasattr(raw_msg, "from_") and raw_msg.from_
                    else "",
                    subject=raw_msg.subject or "No Subject",
                    text=raw_msg.intro or "",
                    html=raw_msg.html if hasattr(raw_msg, "html") else None,
                    timestamp=timestamp,
                    attachments=[],
                    raw=raw_msg,
                )
                messages.append(message)

            logger.info(f"Retrieved {len(messages)} messages from MailTM")

        except Exception as e:
            logger.error(f"Error getting MailTM messages: {e}", exc_info=True)

        return messages

    async def get_message_by_id(
        self, account_data: Dict[str, Any], message_id: str
    ) -> ServiceMessage:
        """Get specific MailTM message by ID"""
        logger.debug(f"get_message_by_id called for message_id: {message_id}")

        if self.mailtm is None:
            await self.restore_account(account_data)

        token = account_data.get("token")
        if not token:
            logger.error("No token available")
            raise ValueError("No token available")

        raw_msg = await self.mailtm.get_message_by_id(message_id, token)

        # Parse timestamp if available
        timestamp = None
        if hasattr(raw_msg, "created_at") and raw_msg.created_at:
            timestamp = raw_msg.created_at

        logger.debug(f"Retrieved message {message_id}")

        return ServiceMessage(
            id=raw_msg.id,
            sender=raw_msg.from_.address
            if hasattr(raw_msg, "from_") and raw_msg.from_
            else "",
            subject=raw_msg.subject or "No Subject",
            text=raw_msg.intro or "",
            html=raw_msg.html if hasattr(raw_msg, "html") else None,
            timestamp=timestamp,
            attachments=[],
            raw=raw_msg,
        )

    async def monitor_messages(
        self,
        account_data: Dict[str, Any],
        message_callback: Callable[[ServiceMessage], Any],
        interval: int = 5,
    ) -> None:
        """
        Monitor MailTM messages using polling.
        BLOCKS until cancelled or stopped.
        """
        logger.info(f"Starting MailTM message monitoring with interval: {interval}s")
        self._known_message_ids.clear()

        # Ensure the stop event is clear before starting
        self._stop_monitoring.clear()

        async def poll_for_messages():
            """Poll MailTM API for new messages"""
            poll_count = 0

            while not self._stop_monitoring.is_set():
                try:
                    poll_count += 1
                    logger.debug(f"MailTM poll #{poll_count}")

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
                    logger.debug("MailTM polling cancelled")
                    raise  # Allow cancellation to bubble up
                except Exception as e:
                    logger.error(f"MailTM polling error: {e}")
                    await asyncio.sleep(interval)

        # Create the task to allow cancellation
        self._monitor_task = asyncio.create_task(poll_for_messages())

        try:
            logger.info("MailTM monitoring active")
            await self._monitor_task
        except asyncio.CancelledError:
            logger.info("MailTM monitoring cancelled")
            # This happens when CLI calls task.cancel() or timeout occurs
            pass
        finally:
            logger.info("MailTM monitoring stopped")

    async def validate_account(self, account_data: Dict[str, Any]) -> bool:
        """Validate MailTM account token"""
        logger.debug("Validating MailTM account")

        if self.mailtm is None:
            await self.restore_account(account_data)

        token = account_data.get("token")
        if not token:
            logger.warning("No token for validation")
            return False

        try:
            account = await self.mailtm.get_me(token)
            is_valid = account is not None
            logger.debug(f"MailTM account validation result: {is_valid}")
            return is_valid
        except Exception as e:
            logger.error(f"MailTM account validation error: {e}")
            return False

    async def close(self):
        """Cleanup MailTM resources"""
        logger.info("Closing MailTM service")
        await super().close()

        if self.mailtm:
            try:
                logger.debug("Closing MailTM session")
                await self.mailtm.close_session()
                logger.debug("MailTM session closed")
            except Exception as e:
                logger.error(f"Error closing MailTM session: {e}")
            self.mailtm = None
        logger.info("MailTM service closed")
