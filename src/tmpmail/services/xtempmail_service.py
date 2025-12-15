#!/usr/bin/env python
import asyncio
from typing import List, Dict, Any, Callable
from datetime import datetime
from .base import BaseEmailService, ServiceMessage
from ..utils import random_string
from ..logging_config import get_logger
import random

# Get module logger
logger = get_logger(__name__)


class XTempMailService(BaseEmailService):
    """XTempMail service with comprehensive message monitoring"""

    SERVICE_NAME = "xtempmail"

    def __init__(self):
        super().__init__()
        self.email_instance = None
        self._message_queue = asyncio.Queue()
        self._is_listening = False
        self._processed_message_ids = set()
        logger.debug("XTempMailService initialized")

    async def create_account(self, **kwargs) -> Dict[str, Any]:
        """Create a new XTempMail account"""
        logger.debug(f"create_account called with kwargs: {kwargs}")

        try:
            from xtempmail.aiomail import Email, EMAIL

            domain_map = {
                "mailto.plus": EMAIL.MAILTO_PLUS,
                "fexpost.com": EMAIL.FEXPOST_COM,
                "fexbox.org": EMAIL.FEXBOX_ORG,
                "mailbok.in.ua": EMAIL.MAILBOX_IN_UA,
                "chitthi.in": EMAIL.CHITTHI_IN,
                "fextemp.com": EMAIL.FEXTEMP_COM,
                "any.pink": EMAIL.ANY_PINK,
                "merepost.com": EMAIL.MEREPOST_COM,
            }

            # choose a random domain

            name = kwargs.get("name", "") or random_string()
            domain = random.choice(list(domain_map.keys()))

            ext = domain_map.get(domain)

            logger.debug(f"Creating account with name: {name}, domain: {domain}")

            # Create email instance
            self.email_instance = Email(name=name, ext=ext)

            # Store account data
            account_data = {
                "service": self.SERVICE_NAME,
                "address": str(self.email_instance.email),
                "name": name,
                "domain": domain,
                "ext": ext.value if hasattr(ext, "value") else str(ext),
                "inbox_id": getattr(self.email_instance, "first_id", ""),
                "created_at": datetime.now().isoformat(),
            }

            logger.info(f"Account created: {account_data['address']}")
            logger.debug(f"Account data: {account_data}")

            return account_data

        except ImportError:
            logger.error("XTempMail library not installed")
            raise ImportError(
                "XTempMail library not installed. "
                "Install with: pip install git+https://github.com/krypton-byte/xtempmail"
            )
        except Exception as e:
            logger.error(f"Error creating XTempMail account: {e}", exc_info=True)
            raise

    async def restore_account(self, account_data: Dict[str, Any]) -> Dict[str, Any]:
        """Restore account from saved data"""
        logger.debug(
            f"restore_account called with account_data keys: {list(account_data.keys())}"
        )

        try:
            from xtempmail.aiomail import Email, EMAIL

            # Recreate email instance
            name = account_data.get("name", "")
            ext_value = account_data.get("ext", "")

            logger.debug(f"Restoring account - name: {name}, ext_value: {ext_value}")

            # Find matching EMAIL enum
            ext = None
            for email_ext in EMAIL:
                if str(email_ext.value) == ext_value or str(email_ext) == ext_value:
                    ext = email_ext
                    break

            if not ext:
                logger.warning(f"Extension {ext_value} not found, using default")
                ext = EMAIL.MAILTO_PLUS

            self.email_instance = Email(name=name, ext=ext)

            # Update account data
            account_data["address"] = str(self.email_instance.email)
            account_data["inbox_id"] = getattr(self.email_instance, "first_id", "")

            logger.info(f"Account restored: {account_data['address']}")
            logger.debug(f"Restored account data: {account_data}")

            return account_data

        except Exception as e:
            logger.error(f"Failed to restore XTempMail account: {e}", exc_info=True)
            raise Exception(f"Failed to restore XTempMail account: {e}")

    async def get_messages(self, account_data: Dict[str, Any]) -> List[ServiceMessage]:
        """Get all messages - both old and new"""
        logger.debug("get_messages called")

        messages = []

        if self.email_instance is None:
            logger.debug("Email instance not found, restoring account")
            await self.restore_account(account_data)

        # First, check if there's a way to get old messages
        # XTempMail might store messages in an internal cache
        if hasattr(self.email_instance, "_messages"):
            message_count = len(self.email_instance._messages)
            logger.debug(f"Found {message_count} messages in internal cache")

            for raw_msg in self.email_instance._messages:
                msg = self._convert_to_servicemessage(raw_msg)
                messages.append(msg)
        else:
            logger.debug("No internal message cache found")

        logger.info(f"Retrieved {len(messages)} messages")
        return messages

    async def get_message_by_id(
        self, account_data: Dict[str, Any], message_id: str
    ) -> ServiceMessage:
        """Get specific message by ID"""
        logger.debug(f"get_message_by_id called for message_id: {message_id}")

        messages = await self.get_messages(account_data)
        for msg in messages:
            if msg.id == message_id:
                logger.debug(f"Found message with ID: {message_id}")
                return msg

        logger.warning(f"Message {message_id} not found")
        raise ValueError(f"Message {message_id} not found")

    async def monitor_messages(
        self,
        account_data: Dict[str, Any],
        message_callback: Callable[[ServiceMessage], Any],
        interval: int = 5,
    ) -> None:
        """
        Comprehensive monitoring that processes ALL messages:
        1. First, process any existing/old messages
        2. Then, listen for new incoming messages
        3. Also periodically re-check for any missed messages
        """
        logger.info(f"Starting message monitoring with interval: {interval}s")

        if self.email_instance is None:
            logger.debug("Email instance not found, restoring account")
            await self.restore_account(account_data)

        # Clear stop flag
        self._stop_monitoring.clear()
        self._is_listening = True

        # Reset processed IDs for this session
        self._processed_message_ids.clear()
        logger.debug("Cleared processed message IDs, set monitoring flag")

        # STEP 1: Process any existing/old messages immediately
        logger.debug("Processing existing messages")
        await self._process_existing_messages(account_data, message_callback)

        # STEP 2: Set up event handler for NEW incoming messages
        async def handle_new_message(raw_msg):
            """Handle incoming XTempMail messages via event system"""
            try:
                logger.debug("Event received for new message")
                message = self._convert_to_servicemessage(raw_msg)

                # Check if we've already processed this message
                if message.id not in self._processed_message_ids:
                    logger.info(f"New unprocessed message: {message.id}")
                    self._processed_message_ids.add(message.id)
                    await message_callback(message)
                else:
                    logger.debug(f"Skipping already processed message: {message.id}")

            except Exception as e:
                logger.error(f"Error handling XTempMail message: {e}", exc_info=True)

        # Register the event handler
        logger.debug("Registering message event handler")
        self.email_instance.on.message()(handle_new_message)

        # STEP 3: Start the listening task
        logger.debug("Starting listener task")
        listen_task = asyncio.create_task(self._run_listener())

        # STEP 4: Start background periodic re-check for missed messages
        logger.debug("Starting periodic re-check task")
        recheck_task = asyncio.create_task(
            self._periodic_recheck(account_data, message_callback, interval)
        )

        try:
            logger.info("Message monitoring active")
            # Wait until we're told to stop
            while not self._stop_monitoring.is_set() and self._is_listening:
                await asyncio.sleep(0.5)  # Small sleep to prevent CPU spinning

                # Check if listener task died
                if listen_task.done():
                    try:
                        result = listen_task.result()
                        logger.warning(f"Listener task completed: {result}")
                        # Restart listener
                        logger.info("Restarting listener task")
                        listen_task = asyncio.create_task(self._run_listener())
                    except Exception as e:
                        logger.error(f"Listener task failed: {e}", exc_info=True)
                        # Try to restart
                        logger.info("Attempting to restart listener task after failure")
                        listen_task = asyncio.create_task(self._run_listener())

        except asyncio.CancelledError:
            logger.info("Monitoring cancelled")
        except Exception as e:
            logger.error(f"Monitoring loop error: {e}", exc_info=True)
        finally:
            # Cleanup
            logger.info("Cleaning up monitoring resources")
            self._is_listening = False

            # Cancel tasks
            tasks = [t for t in [listen_task, recheck_task] if t is not None]
            for task in tasks:
                if task and not task.done():
                    logger.debug(f"Cancelling task: {task}")
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        logger.debug(f"Task cancelled successfully: {task}")
                    except Exception as e:
                        logger.error(f"Error cancelling task: {e}")

    async def _process_existing_messages(
        self,
        account_data: Dict[str, Any],
        message_callback: Callable[[ServiceMessage], Any],
    ) -> None:
        """Process any messages that already exist in the inbox"""
        logger.debug("Processing existing messages")

        try:
            # Get existing messages
            existing_messages = await self.get_messages(account_data)

            if existing_messages:
                logger.info(f"Found {len(existing_messages)} existing message(s)")

                # Process each existing message
                processed_count = 0
                for message in existing_messages:
                    if message.id not in self._processed_message_ids:
                        self._processed_message_ids.add(message.id)
                        await message_callback(message)
                        processed_count += 1
                    else:
                        logger.debug(
                            f"Skipping already processed existing message: {message.id}"
                        )

                logger.info(f"Processed {processed_count} existing messages")
            else:
                logger.debug("No existing messages found")

        except Exception as e:
            logger.error(f"Error processing existing messages: {e}", exc_info=True)

    async def _run_listener(self) -> None:
        """Run XTempMail's listen method"""
        logger.debug("Starting XTempMail listener")

        try:
            if self.email_instance and hasattr(self.email_instance, "listen"):
                logger.info("Starting event listener")
                await self.email_instance.listen()
            else:
                logger.error("No email instance or listen method not available")

        except asyncio.CancelledError:
            logger.info("Listener cancelled")
            raise
        except Exception as e:
            logger.error(f"XTempMail listener error: {e}", exc_info=True)
            raise

    async def _periodic_recheck(
        self,
        account_data: Dict[str, Any],
        message_callback: Callable[[ServiceMessage], Any],
        interval: int,
    ) -> None:
        """Periodically re-check for any missed messages"""
        logger.debug(f"Starting periodic re-check with interval: {interval}s")

        check_count = 0

        while not self._stop_monitoring.is_set() and self._is_listening:
            try:
                # Wait for interval
                await asyncio.sleep(interval)
                check_count += 1

                if self._stop_monitoring.is_set():
                    logger.debug("Stop monitoring set, exiting re-check")
                    break

                logger.debug(f"Periodic re-check #{check_count}")

                # Get current messages
                current_messages = await self.get_messages(account_data)

                # Check for any unprocessed messages
                new_messages = []
                for message in current_messages:
                    if message.id not in self._processed_message_ids:
                        new_messages.append(message)

                if new_messages:
                    logger.info(
                        f"Found {len(new_messages)} missed message(s) in re-check"
                    )

                    # Process missed messages
                    for message in new_messages:
                        self._processed_message_ids.add(message.id)
                        await message_callback(message)
                else:
                    logger.debug("No missed messages found in re-check")

            except asyncio.CancelledError:
                logger.debug("Re-check cancelled")
                break
            except Exception as e:
                logger.error(f"XTempMail re-check error: {e}", exc_info=True)
                # Continue anyway
                await asyncio.sleep(interval)

    def _convert_to_servicemessage(self, raw_msg) -> ServiceMessage:
        """Convert XTempMail EmailMessage to ServiceMessage"""
        logger.debug("Converting raw message to ServiceMessage")

        # Try to get timestamp
        timestamp = None
        if hasattr(raw_msg, "created_at"):
            timestamp = raw_msg.created_at
        elif hasattr(raw_msg, "timestamp"):
            timestamp = raw_msg.timestamp

        # Get sender info
        sender = ""
        if hasattr(raw_msg, "from_mail"):
            sender = str(raw_msg.from_mail)
        elif hasattr(raw_msg, "sender"):
            sender = str(raw_msg.sender)

        # Get attachments
        attachments = []
        if hasattr(raw_msg, "attachments"):
            for att in raw_msg.attachments:
                attachments.append(
                    {
                        "name": getattr(att, "name", ""),
                        "size": getattr(att, "size", 0),
                        "url": getattr(att, "url", ""),
                    }
                )

        # Generate message ID if not present
        message_id = getattr(raw_msg, "id", None)
        if not message_id:
            # Create a deterministic ID based on content
            import hashlib

            content = f"{sender}-{getattr(raw_msg, 'subject', '')}-{getattr(raw_msg, 'text', '')}"
            message_id = hashlib.md5(content.encode()).hexdigest()
            logger.debug(f"Generated message ID: {message_id}")

        message = ServiceMessage(
            id=message_id,
            sender=sender,
            subject=getattr(raw_msg, "subject", "No Subject"),
            text=getattr(raw_msg, "text", ""),
            html=getattr(raw_msg, "html", ""),
            timestamp=timestamp,
            attachments=attachments,
            raw=raw_msg,
        )

        logger.debug(
            f"Converted message: ID={message.id}, From={message.sender}, Subject={message.subject[:30]}..."
        )
        return message

    async def validate_account(self, account_data: Dict[str, Any]) -> bool:
        """Validate XTempMail account by checking if we can get address"""
        logger.debug("Validating XTempMail account")

        try:
            if self.email_instance is None:
                await self.restore_account(account_data)

            email_str = str(self.email_instance.email)
            is_valid = bool(email_str and "@" in email_str)

            logger.debug(f"Account validation result: {is_valid}")
            return is_valid

        except Exception as e:
            logger.error(f"Account validation error: {e}", exc_info=True)
            return False

    async def send_message(
        self,
        account_data: Dict[str, Any],
        to_email: str,
        subject: str,
        text: str,
        attachments: List[tuple] = None,
    ):
        """Send message using XTempMail"""
        logger.info(f"Sending message to: {to_email}, subject: {subject}")

        if self.email_instance is None:
            await self.restore_account(account_data)

        if hasattr(self.email_instance.email, "send_message"):
            await self.email_instance.email.send_message(
                to_email, subject, text, multiply_file=attachments
            )
            logger.info("Message sent successfully")
        else:
            logger.warning("send_message method not available")

    async def delete_message(self, account_data: Dict[str, Any], message_id: str):
        """Delete message in XTempMail"""
        logger.info(f"Deleting message: {message_id}")

        # XTempMail messages have delete method
        messages = await self.get_messages(account_data)
        for msg in messages:
            if msg.id == message_id and hasattr(msg.raw, "delete"):
                await msg.raw.delete()
                logger.info(f"Message {message_id} deleted")
                return

        logger.warning(f"Message {message_id} not found or cannot be deleted")
        raise ValueError(f"Message {message_id} not found or cannot be deleted")

    async def stop_monitoring(self):
        """Stop XTempMail monitoring"""
        logger.info("Stopping XTempMail monitoring")
        self._stop_monitoring.set()
        self._is_listening = False

        # Cancel any running tasks
        if (
            hasattr(self, "_monitor_task")
            and self._monitor_task
            and not self._monitor_task.done()
        ):
            logger.debug("Cancelling monitor task")
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                logger.debug("Monitor task cancelled successfully")

    async def close(self):
        """Cleanup XTempMail resources"""
        logger.info("Closing XTempMail service")
        await self.stop_monitoring()

        # Destroy email instance
        if self.email_instance and hasattr(self.email_instance, "destroy"):
            try:
                logger.debug("Destroying email instance")
                await self.email_instance.destroy()
                logger.debug("Email instance destroyed")
            except Exception as e:
                logger.error(f"Error destroying email instance: {e}")
            self.email_instance = None
        logger.info("XTempMail service closed")
