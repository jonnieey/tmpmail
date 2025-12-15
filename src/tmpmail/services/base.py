#!/usr/bin/env python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Callable
import asyncio
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class ServiceMessage:
    """Standardized message format for all services"""

    id: str
    sender: str
    subject: str
    text: str
    html: Optional[str] = None
    timestamp: Optional[datetime] = None
    attachments: List[Dict] = None
    raw: Any = None  # Service-specific raw message

    def to_dict(self):
        """Convert to dictionary for storage"""
        data = asdict(self)
        if self.timestamp:
            data["timestamp"] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict):
        """Create from dictionary"""
        if "timestamp" in data and data["timestamp"]:
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


class BaseEmailService(ABC):
    """Universal interface for all email services"""

    SERVICE_NAME = "abstract"

    def __init__(self):
        self.service_name = self.SERVICE_NAME
        self._monitor_task = None
        self._stop_monitoring = asyncio.Event()

    @abstractmethod
    async def create_account(self, **kwargs) -> Dict[str, Any]:
        """Create a new email account - REQUIRED"""
        pass

    @abstractmethod
    async def get_messages(self, account_data: Dict[str, Any]) -> List[ServiceMessage]:
        """Get all messages for an account - REQUIRED"""
        pass

    @abstractmethod
    async def get_message_by_id(
        self, account_data: Dict[str, Any], message_id: str
    ) -> ServiceMessage:
        """Get a specific message by ID - REQUIRED"""
        pass

    @abstractmethod
    async def monitor_messages(
        self,
        account_data: Dict[str, Any],
        message_callback: Callable[[ServiceMessage], Any],
        interval: int = 5,
    ) -> None:
        """
        Monitor for new messages - REQUIRED

        Each service implements this in its own way:
        - XTempMail: Uses event-driven on_message decorator
        - MailTM: Uses polling with get_messages
        - Others: Their own implementation
        """
        pass

    @abstractmethod
    async def validate_account(self, account_data: Dict[str, Any]) -> bool:
        """Validate if account is still valid - REQUIRED"""
        pass

    async def stop_monitoring(self):
        """Stop message monitoring"""
        self._stop_monitoring.set()
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

    def extract_links(
        self, message: ServiceMessage, pattern: Optional[str] = None
    ) -> List[str]:
        """Extract links from message text - OPTIONAL (has default implementation)"""
        import re

        if not pattern:
            # Match https://www.temi.com/editor/t/ followed by any non-whitespace characters
            pattern = r"https://www\.temi\.com/editor/t/[^\s\"'<>]+"

        text = message.text or message.html or ""
        if not text:
            return []

        # Find all matches
        matches = re.findall(pattern, text, re.IGNORECASE)

        # Flatten and clean results
        links = []
        for match in matches:
            if isinstance(match, tuple):
                links.extend([m for m in match if m])
            elif match:
                # Clean the link
                cleaned_link = match.rstrip(".,;:!?)")
                if cleaned_link.startswith("https://www.temi.com/editor/t/"):
                    links.append(cleaned_link)

        # Also check HTML for links with href attributes
        if message.html:
            html_pattern = r'href=[\'"]?(https://www\.temi\.com/editor/t/[^\'" >]+)'
            html_links = re.findall(html_pattern, message.html, re.IGNORECASE)
            links.extend(html_links)

        # Return unique links only
        return list(set(links))

    async def close(self):
        """Cleanup resources - OPTIONAL (has default implementation)"""
        await self.stop_monitoring()

    # Optional methods (services can implement if supported)
    async def send_message(
        self,
        account_data: Dict[str, Any],
        to_email: str,
        subject: str,
        text: str,
        attachments: List[tuple] = None,
    ):
        """Send a message - OPTIONAL"""
        raise NotImplementedError(
            f"{self.service_name} does not support sending messages"
        )

    async def delete_message(self, account_data: Dict[str, Any], message_id: str):
        """Delete a message - OPTIONAL"""
        raise NotImplementedError(
            f"{self.service_name} does not support deleting messages"
        )

    async def get_account_info(self, account_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get account information - OPTIONAL"""
        return {
            "service": self.service_name,
            "address": account_data.get("address", ""),
            "created": account_data.get("created_at"),
            "valid": await self.validate_account(account_data),
        }
