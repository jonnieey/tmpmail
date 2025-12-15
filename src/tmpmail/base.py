#!/usr/bin/env python
import pyperclip
import subprocess
import shlex
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import re

BROWSER = os.getenv("PRIVATE_BROWSER", os.getenv("BROWSER", "qutebrowser -T"))


@dataclass
class EmailAccount:
    """Represents an email account"""

    service: str
    address: str
    token: Optional[str] = None
    password: Optional[str] = None
    data: Optional[Dict[str, Any]] = None  # Service-specific data


@dataclass
class EmailMessage:
    """Represents an email message"""

    id: str
    sender: str
    subject: str
    text: str
    html: Optional[str] = None
    timestamp: Optional[str] = None


class BaseEmailService(ABC):
    """Abstract base class for all email services"""

    def __init__(self, service_name: str):
        self.service_name = service_name

    @abstractmethod
    async def create_account(self) -> EmailAccount:
        """Create a new email account"""
        pass

    @abstractmethod
    async def get_messages(self, account: EmailAccount) -> List[EmailMessage]:
        """Get all messages for an account"""
        pass

    @abstractmethod
    async def get_message_by_id(
        self, account: EmailAccount, message_id: str
    ) -> EmailMessage:
        """Get a specific message by ID"""
        pass

    @abstractmethod
    async def validate_account(self, account: EmailAccount) -> bool:
        """Validate if account credentials are still valid"""
        pass

    async def close(self):
        """Cleanup resources"""
        pass


class MessageProcessor:
    """Processes email messages to extract and open links"""

    def __init__(self, regex_pattern: Optional[str] = None):
        self.regex_pattern = (
            regex_pattern or r"https://www\.temi\.com/editor/t/[^\s\"'<>]+"
        )

    def extract_links(self, message, pattern: Optional[str] = None) -> List[str]:
        """Extract only Temi links from message text"""

        if not pattern:
            pattern = self.regex_pattern

        text = message.text or message.html or ""
        if not text:
            return []

        # Find all Temi links
        matches = re.findall(pattern, text, re.IGNORECASE)

        # Clean and filter results
        temi_links = []
        for match in matches:
            if isinstance(match, tuple):
                for m in match:
                    if m and "temi.com/editor/t/" in m:
                        # Clean the link
                        cleaned = m.rstrip(".,;:!?)")
                        temi_links.append(cleaned)
            elif match and "temi.com/editor/t/" in match:
                # Clean the link
                cleaned = match.rstrip(".,;:!?)")
                temi_links.append(cleaned)

        # Also check HTML
        if message.html:
            html_pattern = r'href=[\'"]?(https://www\.temi\.com/editor/t/[^\'" >]+)'
            html_links = re.findall(html_pattern, message.html, re.IGNORECASE)
            temi_links.extend(html_links)

        # Return unique Temi links only
        return list(set(temi_links))

    def process_message(self, message: EmailMessage) -> bool:
        """Process a single message, extract ONLY links and open in browser"""
        links = self.extract_link(message)

        if links:
            print(f"Found {len(links)} Temi link(s)")
            for i, link in enumerate(links, 1):
                print(f"  {i}. {link}")

            # Open the first Temi link
            if links:
                self.open_link_in_browser(links[0])
                pyperclip.copy(links[0])
                print(f"📋 Copied to clipboard: {links[0]}")
                return True
        return False

    @staticmethod
    def open_link_in_browser(link: str):
        """Open link in configured browser"""
        try:
            subprocess.run(
                [*shlex.split(f"{BROWSER} {link}")],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError as e:
            print(f"Failed to open browser: {e}")
