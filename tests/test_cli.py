"""Tests for the TempMailCLI."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from tmpmail.cli import TempMailCLI


@pytest.fixture
def cli():
    """Returns an instance of TempMailCLI."""
    cli_instance = TempMailCLI()
    # Mock storage to prevent file system operations
    cli_instance.storage = MagicMock()
    return cli_instance


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "argv, method_to_check",
    [
        (["new", "xtempmail"], "new_account"),
        (["list"], "list_accounts"),
        (["use", "1"], "use_account"),
        (["services"], "list_services"),
    ],
)
async def test_cli_commands(argv, method_to_check, cli):
    """Test that CLI commands dispatch to the correct methods."""
    with patch.object(
        TempMailCLI, method_to_check, new_callable=AsyncMock
    ) as mock_method:
        with patch("sys.argv", ["tmpmail"] + argv):
            # To prevent argparse from exiting on --help or errors
            with patch("argparse.ArgumentParser.exit"):
                await cli.run()
                mock_method.assert_called_once()


@pytest.mark.asyncio
async def test_new_account_command(cli):
    """Test the 'new' command logic."""
    with patch("sys.argv", ["tmpmail", "new", "xtempmail", "--name", "testuser"]):
        mock_service = MagicMock()
        mock_service.create_account = AsyncMock(
            return_value={"address": "testuser@domain.com", "data": {}}
        )
        mock_service.close = AsyncMock()

        with patch(
            "tmpmail.cli.ServiceRegistry.create_service", return_value=mock_service
        ):
            with patch.object(TempMailCLI, "start_monitoring", new_callable=AsyncMock):
                await cli.run()

                mock_service.create_account.assert_called_with(name="testuser")
                cli.storage.save_account.assert_called_once()


@pytest.mark.asyncio
async def test_use_account_command(cli):
    """Test the 'use' command logic."""
    with patch("sys.argv", ["tmpmail", "use", "1", "--service", "xtempmail"]):
        cli.storage.get_account_by_index.return_value = {
            "service": "xtempmail",
            "address": "old@domain.com",
            "data": {},
        }

        mock_service = MagicMock()
        mock_service.restore_account = AsyncMock(
            return_value={"address": "old@domain.com", "data": {}}
        )
        mock_service.close = AsyncMock()

        with patch(
            "tmpmail.cli.ServiceRegistry.create_service", return_value=mock_service
        ):
            with patch.object(TempMailCLI, "start_monitoring", new_callable=AsyncMock):
                await cli.run()

                cli.storage.get_account_by_index.assert_called_with(1, "xtempmail")
                mock_service.restore_account.assert_called_once()


@pytest.mark.asyncio
async def test_list_accounts_command(cli, capsys):
    """Test the 'list' command output."""
    with patch("sys.argv", ["tmpmail", "list"]):
        cli.storage.get_recent_accounts.return_value = [
            {
                "service": "xtempmail",
                "address": "test1@domain.com",
                "created_at": "2023-01-01",
            },
            {
                "service": "mailtm",
                "address": "test2@domain.com",
                "created_at": "2023-01-02",
            },
        ]

        await cli.run()

        captured = capsys.readouterr()
        assert "test1@domain.com" in captured.out
        assert "test2@domain.com" in captured.out
