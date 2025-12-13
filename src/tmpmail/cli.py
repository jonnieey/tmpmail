#!/usr/bin/env python
import asyncio
import argparse
import sys
import os
import pyperclip
import logging
from typing import Optional, List

from .config import ServiceRegistry
from .storage import AccountStorage
from .base import BaseEmailService
from .services.base import ServiceMessage
from .logging_config import setup_logging, get_logger

# Get module logger
logger = get_logger(__name__)


class TempMailCLI:
    """Universal CLI for all email services"""

    def __init__(self):
        self.storage = AccountStorage()
        self.current_service = None
        self.link_pattern = os.getenv("TMPMAIL_LINK_PATTERN")

    async def run(self):
        """Main CLI entry point"""
        logger.debug("CLI run method started")

        parser = self._create_parser()
        args = parser.parse_args()

        # Configure logging based on arguments
        # Default behavior: quiet (no console output)
        # Enable console output only if log-level is explicitly set
        console_logging = False
        if args.log_level:
            console_logging = True

        # --quiet overrides everything to force quiet
        if args.quiet:
            console_logging = False

        setup_logging(
            level=args.log_level or "WARNING",
            log_file=args.log_file,
            console=console_logging,
        )

        if args.new:
            logger.info(f"Processing new account request for service: {args.service}")
            await self.handle_new_account(args)

        elif args.existing:
            logger.info(
                f"Processing existing account request with index: {args.existing}"
            )
            await self.handle_existing_account(args)

        elif args.list:
            logger.info(f"Listing accounts (count: {args.list})")
            await self.list_accounts(args)

        elif args.services:
            logger.info("Listing available services")
            await self.list_services(args)

        else:
            logger.debug("No command specified, defaulting to list accounts")
            await self.list_accounts(args)

    def _create_parser(self):
        """Create argument parser with subcommands"""
        parser = argparse.ArgumentParser(
            description="Universal Temporary Email Client - Link Extractor",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  tmpmail mailtm -n                    # Create new MailTM account
  tmpmail xtempmail -n --name custom   # Create XTempMail with custom name
  tmpmail -e 10                        # Use 10th most recent account
  tmpmail -l                           # List recent accounts
  tmpmail --services                   # List available services

            """,
        )

        parser.add_argument(
            "service",
            nargs="?",
            help="Email service to use (e.g., xtempmail, mailtm)",
        )

        # Universal flags
        parser.add_argument(
            "-n", "--new", action="store_true", help="Create new account"
        )
        parser.add_argument(
            "-e",
            "--existing",
            type=int,
            help="Use existing account by index (from --list)",
        )
        parser.add_argument(
            "-l",
            "--list",
            type=int,
            nargs="?",
            const=10,
            help="List recent accounts (optional: number to show)",
        )
        parser.add_argument(
            "-s", "--services", action="store_true", help="List available services"
        )
        parser.add_argument(
            "--pattern",
            default=r"https://www\.temi\.com/editor/t/[^\s\"'<>]+",
            help="Custom regex pattern for link extraction",
        )

        # Service-specific options
        parser.add_argument("--name", help="Custom name for email address (XTempMail)")
        parser.add_argument(
            "--domain",
            choices=[
                "mailto.plus",
                "fexpost.com",
                "fexbox.org",
                "mailbok.in.ua",
                "chitthi.in",
                "fextemp.com",
                "any.pink",
                "merepost.com",
            ],
            help="Domain for XTempMail",
        )

        # Monitor options
        parser.add_argument(
            "--timeout",
            type=int,
            default=300,
            help="Stop monitoring after N seconds (0 = forever, 300 = default)",
        )

        # Logging options
        parser.add_argument(
            "--log-level",
            choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            default=None,
            help="Set logging level",
        )
        parser.add_argument("--log-file", help="Log to specified file")
        parser.add_argument(
            "--quiet",
            action="store_true",
            help="Suppress console output (logs to file only if --log-file is set)",
        )

        return parser

    async def handle_new_account(self, args):
        """Handle creating new account"""
        if not args.service:
            logger.error("Service name required for new account")
            print("Error: Service name required for new account")
            print(f"Available: {', '.join(ServiceRegistry.list_services().keys())}")
            return

        try:
            # Create service instance
            self.current_service = ServiceRegistry.create_service(args.service)

            # Service-specific parameters
            kwargs = {}
            if args.name:
                kwargs["name"] = args.name
            if args.domain:
                kwargs["domain"] = args.domain

            # Create account
            logger.info(f"Creating {args.service} account...")
            account_data = await self.current_service.create_account(**kwargs)

            # Convert to storage format and save
            from .base import EmailAccount

            account = EmailAccount(
                service=args.service, address=account_data["address"], data=account_data
            )
            self.storage.save_account(account)

            logger.info(f"Account created successfully: {account.address}")
            print(f"\n✅ Account created successfully!")
            print(f"📧 Email: {account.address}")
            pyperclip.copy(account.address)
            print(f"📋 Email copied to clipboard")

            # Start monitoring
            await self.start_monitoring(account, args)

        except Exception as e:
            logger.error(f"Error creating account: {e}", exc_info=True)
        finally:
            if self.current_service:
                await self.current_service.close()

    async def handle_existing_account(self, args):
        """Handle using existing account"""
        logger.debug(f"Looking up account with index: {args.existing}")
        account_dict = self.storage.get_account_by_index(args.existing)
        if not account_dict:
            logger.warning(f"No account found at index {args.existing}")
            print(f"No account found at index {args.existing}")
            return

        # Determine service from stored account
        service_name = account_dict.get("service")
        if not service_name:
            logger.error("Account has no service specified")
            print("Error: Account has no service specified")
            return

        try:
            # Create appropriate service
            self.current_service = ServiceRegistry.create_service(service_name)

            # Restore account
            account_data = account_dict.get("data", {})
            if hasattr(self.current_service, "restore_account"):
                account_data = await self.current_service.restore_account(account_data)

            from .base import EmailAccount

            account = EmailAccount(
                service=service_name,
                address=account_data.get("address", account_dict.get("address")),
                data=account_data,
            )

            logger.info(f"Using existing account: {account.address}")
            print(f"✅ Using account: {account.address}")
            await self.start_monitoring(account, args)

        except Exception as e:
            logger.error(f"Error using existing account: {e}", exc_info=True)
        finally:
            if self.current_service:
                await self.current_service.close()

    async def start_monitoring(self, account, args):
        """Start monitoring for messages, extract links"""
        logger.info("Starting message monitoring")

        print(f"\n⏰ Timeout after {args.timeout} seconds")

        print(f"\n🔍 Monitoring for for links...")

        print(f"📝 Press Ctrl+C to stop\n")

        # Track processed messages to avoid duplicates
        processed_ids = set()

        async def handle_message(message: ServiceMessage):
            """Callback for new messages"""
            if message.id in processed_ids:
                logger.debug(f"Skipping already processed message: {message.id}")
                return

            processed_ids.add(message.id)

            logger.info(
                f"New message received - ID: {message.id}, From: {message.sender}"
            )
            # print(f"\n📨 New message from: {message.sender}")
            # print(f"📝 Subject: {message.subject}")

            # Extract links using service's method with pattern
            pattern = args.pattern or self.link_pattern
            links = self.current_service.extract_links(message, pattern)

            # if links:
            #     logger.info(f"Found {len(links)} link(s) in message {message.id}")
            #     print(f"🎯 Found {len(links)} link(s):")
            #     for i, link in enumerate(links, 1):
            #         print(f"  {i}. {link}")
            #
            #     # Process first link
            if links:
                await self._process_link(links[0])
            else:
                logger.debug(f"No links found in message {message.id}")
                # Show a preview of the message but don't extract other links
                text_preview = (
                    message.text[:100] + "..."
                    if message.text and len(message.text) > 100
                    else message.text or "(no text)"
                )
                # print(f"📄 No links found. Preview: {text_preview}")

        # Start monitoring (each service uses its own implementation)
        try:
            if args.timeout > 0:
                logger.info(f"Monitoring with timeout: {args.timeout} seconds")
                # Run with timeout
                await asyncio.wait_for(
                    self.current_service.monitor_messages(
                        account.data, handle_message, interval=3
                    ),
                    timeout=args.timeout,
                )
                logger.info(f"Monitoring timeout reached after {args.timeout} seconds")
                print(f"\n⏰ Timeout after {args.timeout} seconds")
            else:
                logger.info("Monitoring indefinitely (until Ctrl+C)")
                # Run forever
                await self.current_service.monitor_messages(
                    account.data, handle_message, interval=3
                )

        except asyncio.TimeoutError:
            logger.info(f"Monitoring timeout reached after {args.timeout} seconds")
            print(f"\n⏰ Timeout after {args.timeout} seconds")
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user (KeyboardInterrupt)")
            print("\n⏹️ Stopped by user")
        except Exception as e:
            logger.error(f"Monitoring error: {e}", exc_info=True)
        finally:
            logger.info("Stopping monitoring service")
            await self.current_service.stop_monitoring()

    async def _process_link(self, link: str):
        """Process a link (copy to clipboard and open in browser)"""
        try:
            # Clean the link
            clean_link = link.strip()
            if not clean_link.startswith("http"):
                clean_link = "https://" + clean_link

            # Copy to clipboard
            pyperclip.copy(clean_link)
            logger.info(f"Link copied to clipboard: {clean_link}")
            print(f"📋 Link copied to clipboard")

            # Open in browser
            await self._open_in_browser(clean_link)

        except Exception as e:
            logger.error(f"Error processing Link: {e}", exc_info=True)

    async def _open_in_browser(self, url: str):
        """Open URL in browser asynchronously"""
        import subprocess
        import shlex

        browser = os.getenv("PRIVATE_BROWSER", os.getenv("BROWSER", "xdg-open"))

        # Run browser in background
        process = await asyncio.create_subprocess_exec(
            *shlex.split(browser),
            url,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )

        # Don't wait for browser to close
        logger.info(f"Opening URL in browser: {url}")
        print(f"🌐 Opening link in browser...")

        # Check if browser opened successfully
        await asyncio.sleep(0.5)  # Give it a moment
        if process.returncode is not None and process.returncode != 0:
            logger.warning(
                f"Browser may have failed to open (return code: {process.returncode})"
            )

    async def list_accounts(self, args):
        """List recent accounts"""
        count = args.list if hasattr(args, "list") and args.list else 10

        accounts = self.storage.get_recent_accounts(count)

        if not accounts:
            logger.info("No accounts found in storage")
            print("No accounts found")
            return

        logger.info(f"Listing {len(accounts)} recent accounts")
        print(f"\n📋 Recent accounts (newest first):")
        for i, acc in enumerate(reversed(accounts), 1):
            address = acc.get("address", "Unknown")
            service = acc.get("service", "Unknown")
            print(f"{i:3}. {address:<40} ({service})")

    async def list_services(self, args):
        """List available services"""
        services = ServiceRegistry.list_services()

        logger.info("Listing available services")
        print("\n🛠️  Available services:")
        for name, description in services.items():
            print(f"  {name:<15} - {description}")

        print(f"\nUsage: tmpmail <service> -n")


def main():
    """Entry point"""
    cli = TempMailCLI()

    # Parse args to get logging configuration first
    import argparse

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--log-level", default=None)
    parser.add_argument("--log-file")
    parser.add_argument("-q", "--quiet", action="store_true")
    args, _ = parser.parse_known_args()

    from .logging_config import setup_logging

    # Configure logging based on arguments
    # Default behavior: quiet (no console output)
    # Enable console output only if log-level is explicitly set
    console_logging = False
    if args.log_level:
        console_logging = True

    # --quiet overrides everything to force quiet
    if args.quiet:
        console_logging = False

    setup_logging(
        level=args.log_level or "WARNING",
        log_file=args.log_file,
        console=console_logging,
    )

    logger = get_logger(__name__)
    logger.info("Starting TempMail CLI")

    try:
        asyncio.run(cli.run())
    except KeyboardInterrupt:
        logger.info("Application terminated by user")
        print("\n👋 Exiting...")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Application error: {e}", exc_info=True)
        print(f"💥 Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
