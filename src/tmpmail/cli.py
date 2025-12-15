#!/usr/bin/env python
import asyncio
import argparse
import sys
import os
import pyperclip

from .config import ServiceRegistry
from .storage import AccountStorage
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
        console_logging = False
        if args.log_level:
            console_logging = True

        if args.quiet:
            console_logging = False

        setup_logging(
            level=args.log_level or "WARNING",
            log_file=args.log_file,
            console=console_logging,
        )

        # Execute the appropriate subcommand
        if hasattr(args, "func"):
            await args.func(args)
        else:
            # Default action: list accounts
            await self.list_accounts(args)

    def _create_parser(self):
        """Create argument parser with subcommands"""
        parser = argparse.ArgumentParser(
            description="Universal Temporary Email Client - Link Extractor",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  tmpmail new mailtm                     # Create new MailTM account
  tmpmail new xtempmail --name custom    # Create XTempMail with custom name
  tmpmail list mailtm                    # List MailTM accounts
  tmpmail use 1 --service mailtm         # Use 1st most recent MailTM account
  tmpmail services                       # List available services

            """,
        )

        # Global options
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

        # Create subparsers
        subparsers = parser.add_subparsers(dest="command", help="Commands")

        # 'new' command: Create new account
        new_parser = subparsers.add_parser("new", help="Create new email account")
        new_parser.add_argument(
            "service",
            help="Email service to use (e.g., xtempmail, mailtm)",
            choices=list(ServiceRegistry.list_services().keys()),
        )
        new_parser.add_argument(
            "--name",
            help="Custom name for email address (service-specific)",
        )
        new_parser.add_argument(
            "--pattern",
            default=r"https://www\.temi\.com/editor/t/[^\s\"'<>]+",
            help="Custom regex pattern for link extraction",
        )
        new_parser.add_argument(
            "--timeout",
            type=int,
            default=300,
            help="Stop monitoring after N seconds (0 = forever, 300 = default)",
        )
        new_parser.set_defaults(func=self.new_account)

        # 'list' command: List accounts
        list_parser = subparsers.add_parser("list", help="List existing accounts")
        list_parser.add_argument(
            "service",
            nargs="?",
            help="Filter by service (e.g., mailtm, xtempmail)",
            choices=list(ServiceRegistry.list_services().keys()) + [None],
        )
        list_parser.add_argument(
            "-c",
            "--count",
            type=int,
            default=10,
            help="Number of accounts to show (default: 10)",
        )
        list_parser.set_defaults(func=self.list_accounts)

        # 'use' command: Use existing account
        use_parser = subparsers.add_parser("use", help="Use existing account")
        use_parser.add_argument(
            "index",
            type=int,
            help="Account index (from list command)",
        )
        use_parser.add_argument(
            "--service",
            help="Filter by service when selecting index",
            choices=list(ServiceRegistry.list_services().keys()),
        )
        use_parser.add_argument(
            "--pattern",
            default=r"https://www\.temi\.com/editor/t/[^\s\"'<>]+",
            help="Custom regex pattern for link extraction",
        )
        use_parser.add_argument(
            "--timeout",
            type=int,
            default=300,
            help="Stop monitoring after N seconds (0 = forever, 300 = default)",
        )
        use_parser.set_defaults(func=self.use_account)

        # 'services' command: List available services
        services_parser = subparsers.add_parser(
            "services", help="List available email services"
        )
        services_parser.set_defaults(func=self.list_services)

        # Add service-specific options dynamically
        self._add_service_specific_options(new_parser)

        return parser

    def _add_service_specific_options(self, parser):
        """Add service-specific options to the new command"""
        # XTempMail-specific options
        xtempmail_group = parser.add_argument_group(
            "XTempMail options", "Options specific to XTempMail service"
        )
        xtempmail_group.add_argument(
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
            help="Domain for XTempMail (only valid with xtempmail service)",
        )

        # Add more service-specific groups here as needed
        # For example:
        # mailtm_group = parser.add_argument_group("MailTM options")

    async def new_account(self, args):
        """Handle creating new account"""
        logger.info(f"Creating new {args.service} account")

        # Validate service-specific options
        if args.domain and args.service != "xtempmail":
            logger.warning(
                f"--domain option is only valid for xtempmail service, ignoring for {args.service}"
            )
            print("Warning: --domain option is only valid for xtempmail service")
            args.domain = None

        try:
            # Create service instance
            self.current_service = ServiceRegistry.create_service(args.service)

            # Prepare service-specific parameters
            kwargs = {}
            if args.name:
                kwargs["name"] = args.name
            if args.service == "xtempmail" and args.domain:
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
            print("\n✅ Account created successfully!")
            print(f"📧 Email: {account.address}")
            pyperclip.copy(account.address)
            print("📋 Email copied to clipboard")

            # Start monitoring
            await self.start_monitoring(account, args)

        except Exception as e:
            logger.error(f"Error creating account: {e}", exc_info=True)
            print(f"Error: {e}")
        finally:
            if self.current_service:
                await self.current_service.close()

    async def use_account(self, args):
        """Handle using existing account"""
        logger.debug(
            f"Looking up account with index: {args.index}, service: {args.service}"
        )

        # Get account by index with optional service filter
        account_dict = self.storage.get_account_by_index(args.index, args.service)

        if not account_dict:
            service_msg = f" for service '{args.service}'" if args.service else ""
            logger.warning(f"No account found at index {args.index}{service_msg}")
            print(f"No account found at index {args.index}{service_msg}")
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
            print(f"Error: {e}")
        finally:
            if self.current_service:
                await self.current_service.close()

    async def list_accounts(self, args):
        """List recent accounts"""
        count = args.count if hasattr(args, "count") else 10
        service_filter = getattr(args, "service", None)

        accounts = self.storage.get_recent_accounts(count, service_filter)

        if not accounts:
            service_msg = f" for service '{service_filter}'" if service_filter else ""
            logger.info(f"No accounts found in storage{service_msg}")
            print(f"No accounts found{service_msg}")
            return

        service_msg = f" for service '{service_filter}'" if service_filter else ""
        logger.info(f"Listing {len(accounts)} recent accounts{service_msg}")
        print(f"\n📋 Recent accounts{service_msg} (newest first):")

        # Reverse to show newest first with index 1
        for i, acc in enumerate(reversed(accounts), 1):
            address = acc.get("address", "Unknown")
            service = acc.get("service", "Unknown")
            created_at = acc.get("created_at", "")
            if created_at:
                created_at = f" - {created_at}"
            print(f"{i:3}. {address:<40} ({service}){created_at}")

    async def list_services(self, args):
        """List available services"""
        services = ServiceRegistry.list_services()

        logger.info("Listing available services")
        print("\n🛠️  Available services:")
        for name, description in services.items():
            print(f"  {name:<15} - {description}")

        print("\nUsage examples:")
        print("  tmpmail new <service>          # Create new account")
        print("  tmpmail list [service]         # List accounts")
        print("  tmpmail use <index> [--service <service>]  # Use existing account")

    async def start_monitoring(self, account, args):
        """Start monitoring for messages, extract links"""
        logger.info("Starting message monitoring")

        print(f"\n⏰ Timeout after {args.timeout} seconds")
        print("\n🔍 Monitoring for links...")
        print("📝 Press Ctrl+C to stop\n")

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

            # Extract links using service's method with pattern
            pattern = args.pattern or self.link_pattern
            links = self.current_service.extract_links(message, pattern)

            if links:
                await self._process_link(links[0])
            else:
                logger.debug(f"No links found in message {message.id}")

        # Start monitoring
        try:
            if args.timeout > 0:
                logger.info(f"Monitoring with timeout: {args.timeout} seconds")
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
            print(f"Monitoring error: {e}")
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
            print("📋 Link copied to clipboard")

            # Open in browser
            await self._open_in_browser(clean_link)

        except Exception as e:
            logger.error(f"Error processing Link: {e}", exc_info=True)

    async def _open_in_browser(self, url: str):
        """Open URL in browser asynchronously"""
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
        print("🌐 Opening link in browser...")

        # Check if browser opened successfully
        await asyncio.sleep(0.5)
        if process.returncode is not None and process.returncode != 0:
            logger.warning(
                f"Browser may have failed to open (return code: {process.returncode})"
            )


def main():
    """Entry point"""
    cli = TempMailCLI()

    # Parse args to get logging configuration first
    import argparse

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("command", nargs="?")
    parser.add_argument("--log-level", default=None)
    parser.add_argument("--log-file")
    parser.add_argument("-q", "--quiet", action="store_true")
    args, _ = parser.parse_known_args()

    from .logging_config import setup_logging

    # Configure logging based on arguments
    console_logging = False
    if args.log_level:
        console_logging = True

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
