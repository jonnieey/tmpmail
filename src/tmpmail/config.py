#!/usr/bin/env python
from typing import Dict, Type
from .services.xtempmail_service import XTempMailService
from .services.mailtm_service import MailTMService
# from services.tenminmail import TenMinMailService


class ServiceRegistry:
    """Registry for all email services"""

    _services: Dict[str, Type] = {}

    @classmethod
    def register(cls, name: str, service_class: Type):
        """Register a service with one or more names"""
        cls._services[name.lower()] = service_class

        # Also register by service class name if different
        service_name = getattr(service_class, "SERVICE_NAME", "").lower()
        if service_name and service_name != name.lower():
            cls._services[service_name] = service_class

    @classmethod
    def get_service(cls, name: str):
        """Get service class by name"""
        name_lower = name.lower()
        return cls._services.get(name_lower)

    @classmethod
    def create_service(cls, name: str):
        """Create service instance by name"""
        service_class = cls.get_service(name)
        if not service_class:
            raise ValueError(f"Unknown service: {name}")
        return service_class()

    @classmethod
    def list_services(cls) -> Dict[str, str]:
        """List all registered services with descriptions"""
        services = {}
        for name, service_class in cls._services.items():
            # Get unique service names
            service_name = getattr(service_class, "SERVICE_NAME", name)
            if service_name not in services:
                services[service_name] = service_class.__doc__ or "Email service"
        return services


# Register all services
ServiceRegistry.register("xtempmail", XTempMailService)
# ServiceRegistry.register("tempmail.plus", XTempMailService)  # Alias
ServiceRegistry.register("mailtm", MailTMService)
# ServiceRegistry.register("10minmail", TenMinMailService)
# ServiceRegistry.register("tenminmail", TenMinMailService)  # Alias
# ServiceRegistry.register("temp-mail", TenMinMailService)  # Another alias
