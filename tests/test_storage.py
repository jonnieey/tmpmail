"""Tests for the AccountStorage class."""
from datetime import datetime
import pytest
from freezegun import freeze_time

from tmpmail.storage import AccountStorage
from tmpmail.base import EmailAccount


@pytest.fixture
def mock_xdg_data_home(monkeypatch, tmp_path):
    """Mock XDG_DATA_HOME to use a temporary directory."""
    data_dir = tmp_path / "tmpmail"
    monkeypatch.setattr("tmpmail.storage.XDG_DATA_HOME", tmp_path)
    return data_dir


@pytest.fixture
def storage(mock_xdg_data_home):
    """Return an AccountStorage instance using the mocked data directory."""
    return AccountStorage(data_dir=mock_xdg_data_home)


@pytest.fixture
def sample_account():
    """Return a sample EmailAccount."""
    return EmailAccount(
        service="test_service",
        address="test@example.com",
        data={"token": "test_token"},
    )


def test_init_creates_directory_and_file(storage, mock_xdg_data_home):
    """Test that AccountStorage.__init__ creates the data directory and accounts file."""
    assert mock_xdg_data_home.exists()
    accounts_file = mock_xdg_data_home / "accounts.json"
    assert accounts_file.exists()
    assert accounts_file.read_text() == "[]"


@freeze_time("2023-01-01 12:00:00")
def test_save_account(storage, sample_account):
    """Test saving an account."""
    storage.save_account(sample_account)
    accounts = storage.load_all_accounts_raw()
    assert len(accounts) == 1
    acc = accounts[0]
    assert acc["service"] == "test_service"
    assert acc["address"] == "test@example.com"
    assert acc["data"] == {"token": "test_token"}
    assert acc["created_at"] == datetime.now().isoformat()
    assert acc["last_used"] == datetime.now().isoformat()


def test_save_duplicate_account(storage, sample_account):
    """Test that saving an account with the same address replaces the old one."""
    storage.save_account(sample_account)
    storage.save_account(sample_account)  # Save again
    accounts = storage.load_all_accounts_raw()
    assert len(accounts) == 1


def test_load_all_accounts_raw_empty(storage):
    """Test loading accounts when the file is empty."""
    accounts = storage.load_all_accounts_raw()
    assert accounts == []


def test_load_all_accounts_raw_invalid_json(storage):
    """Test loading accounts from a file with invalid JSON."""
    storage.accounts_file.write_text("this is not json")
    accounts = storage.load_all_accounts_raw()
    assert accounts == []


def test_get_account_by_index(storage, sample_account):
    """Test getting an account by its 1-based index."""
    storage.save_account(sample_account)
    acc_dict = storage.get_account_by_index(1)
    assert acc_dict is not None
    assert acc_dict["address"] == sample_account.address


def test_get_account_by_index_not_found(storage):
    """Test getting an account by an index that doesn't exist."""
    acc_dict = storage.get_account_by_index(1)
    assert acc_dict is None


def test_get_recent_accounts(storage):
    """Test getting a number of recent accounts."""
    for i in range(15):
        acc = EmailAccount(f"service{i}", f"test{i}@example.com", data={})
        storage.save_account(acc)

    accounts = storage.get_recent_accounts(count=10)
    assert len(accounts) == 10
    assert accounts[0]["address"] == "test5@example.com"
    assert accounts[-1]["address"] == "test14@example.com"


def test_get_accounts_by_service(storage):
    """Test filtering accounts by service."""
    acc1 = EmailAccount("service1", "test1@example.com", data={})
    acc2 = EmailAccount("service2", "test2@example.com", data={})
    storage.save_account(acc1)
    storage.save_account(acc2)

    service1_accounts = storage.get_accounts_by_service("service1")
    assert len(service1_accounts) == 1
    assert service1_accounts[0]["address"] == "test1@example.com"


@freeze_time("2023-01-01 12:00:00")
def test_update_account_usage(storage, sample_account):
    """Test updating the last_used timestamp of an account."""
    storage.save_account(sample_account)

    with freeze_time("2023-01-01 13:00:00"):
        storage.update_account_usage(sample_account.address)

    accounts = storage.load_all_accounts_raw()
    assert accounts[0]["last_used"] == datetime(2023, 1, 1, 13, 0, 0).isoformat()
