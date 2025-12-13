# SPDX-FileCopyrightText: 2025-present jonnieey <johnjahi55@gmail.com>
#
# SPDX-License-Identifier: MIT
#!/usr/bin/env python
"""
Universal Temporary Email Client

Supports multiple services with consistent interface:
- XTempMail (tempmail.plus) - event-driven
- MailTM - polling-based
- 10MinuteMail - hybrid
- Add your own service!

Usage:
    tmpmail <service> -n      # Create new account
    tmpmail -e <index>        # Use existing account
    tmpmail -l               # List recent accounts
"""

from .cli import main
from .config import ServiceRegistry
from .base import BaseEmailService
from .services.base import ServiceMessage
from .storage import AccountStorage
from .logging_config import setup_logging, get_logger

__version__ = "2.0.0"
__all__ = [
    "main",
    "ServiceRegistry",
    "BaseEmailService",
    "ServiceMessage",
    "AccountStorage",
    "setup_logging",
    "get_logger",
]
