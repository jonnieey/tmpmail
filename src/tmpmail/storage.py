#!/usr/bin/env python
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from xdg import XDG_DATA_HOME
from datetime import datetime

from .base import EmailAccount


class AccountStorage:
    """Universal storage for all email services"""

    def __init__(self, data_dir: Optional[Path] = None):
        if data_dir is None:
            data_dir = XDG_DATA_HOME / "tempmail"

        self.data_dir = data_dir
        self.accounts_file = data_dir / "accounts.json"

        self._ensure_data_dir()

    def _ensure_data_dir(self):
        """Ensure data directory exists"""
        if not self.data_dir.exists():
            self.data_dir.mkdir(parents=True, exist_ok=True)

        if not self.accounts_file.exists():
            self.accounts_file.write_text("[]")

    def save_account(self, account: EmailAccount):
        """Save any type of email account"""
        accounts = self.load_all_accounts_raw()

        # Remove duplicate by address
        accounts = [acc for acc in accounts if acc.get("address") != account.address]

        # Prepare account data
        account_data = {
            "service": account.service,
            "address": account.address,
            "data": account.data,
            "created_at": datetime.now().isoformat(),
            "last_used": datetime.now().isoformat(),
        }

        # Add to list
        accounts.append(account_data)

        # Keep only last 100 accounts
        if len(accounts) > 100:
            accounts = accounts[-100:]

        # Save to file
        self.accounts_file.write_text(json.dumps(accounts, indent=2))

    def load_all_accounts_raw(self) -> List[Dict[str, Any]]:
        """Load all accounts as raw dictionaries"""
        try:
            content = self.accounts_file.read_text()
            return json.loads(content)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def get_account_by_index(self, index: int) -> Optional[Dict[str, Any]]:
        """Get account by index (1-based, from most recent)"""
        accounts = self.load_all_accounts_raw()

        if index <= 0 or index > len(accounts):
            return None

        # Return from most recent
        return accounts[-index]

    def get_recent_accounts(self, count: int = 10) -> List[Dict[str, Any]]:
        """Get most recent accounts"""
        accounts = self.load_all_accounts_raw()
        return accounts[-count:] if accounts else []

    def get_accounts_by_service(self, service: str) -> List[Dict[str, Any]]:
        """Get all accounts for a specific service"""
        accounts = self.load_all_accounts_raw()
        return [acc for acc in accounts if acc.get("service") == service]

    def update_account_usage(self, address: str):
        """Update last_used timestamp for an account"""
        accounts = self.load_all_accounts_raw()

        for acc in accounts:
            if acc.get("address") == address:
                acc["last_used"] = datetime.now().isoformat()
                break

        self.accounts_file.write_text(json.dumps(accounts, indent=2))
