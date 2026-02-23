"""Tests for the ServiceRegistry."""
import pytest
from tmpmail.config import ServiceRegistry
from tmpmail.services.base import BaseEmailService


class DummyService(BaseEmailService):
    """A dummy email service for testing purposes."""

    SERVICE_NAME = "dummy"

    async def create_account(self, **kwargs):
        """Dummy create_account."""
        pass

    async def get_messages(self, account_data):
        """Dummy get_messages."""
        pass

    async def get_message_by_id(self, account_data, message_id):
        """Dummy get_message_by_id."""
        pass

    async def monitor_messages(self, account_data, message_callback, interval=5):
        """Dummy monitor_messages."""
        pass

    async def validate_account(self, account_data):
        """Dummy validate_account."""
        pass


@pytest.fixture(autouse=True)
def clean_registry():
    """Clean up the registry before and after each test."""
    ServiceRegistry._services = {}
    yield
    ServiceRegistry._services = {}


def test_register_service():
    """Test registering a service."""
    ServiceRegistry.register("dummy", DummyService)
    assert "dummy" in ServiceRegistry._services
    assert ServiceRegistry._services["dummy"] == DummyService


def test_register_service_with_service_name():
    """Test registering a service also registers by its SERVICE_NAME."""
    ServiceRegistry.register("d", DummyService)
    assert "d" in ServiceRegistry._services
    assert "dummy" in ServiceRegistry._services
    assert ServiceRegistry._services["d"] == DummyService
    assert ServiceRegistry._services["dummy"] == DummyService


def test_get_service():
    """Test getting a service from the registry."""
    ServiceRegistry.register("dummy", DummyService)
    service_class = ServiceRegistry.get_service("dummy")
    assert service_class == DummyService
    service_class_upper = ServiceRegistry.get_service("DUMMY")
    assert service_class_upper == DummyService


def test_get_nonexistent_service():
    """Test getting a service that does not exist."""
    service_class = ServiceRegistry.get_service("nonexistent")
    assert service_class is None


def test_create_service():
    """Test creating a service instance."""
    ServiceRegistry.register("dummy", DummyService)
    service_instance = ServiceRegistry.create_service("dummy")
    assert isinstance(service_instance, DummyService)


def test_create_nonexistent_service():
    """Test creating a service that does not exist."""
    with pytest.raises(ValueError, match="Unknown service: nonexistent"):
        ServiceRegistry.create_service("nonexistent")


def test_list_services():
    """Test listing all registered services."""
    ServiceRegistry.register("dummy1", DummyService)

    class DummyService2(DummyService):
        SERVICE_NAME = "dummy2"

    ServiceRegistry.register("dummy2_alias", DummyService2)

    services = ServiceRegistry.list_services()
    assert "dummy" in services
    assert "dummy2" in services
    assert "dummy2_alias" not in services  # Should be listed by SERVICE_NAME
    assert services["dummy"] == "Email service"
