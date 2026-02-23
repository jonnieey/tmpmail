"""Tests for the logging_config module."""
import logging
import pytest
from tmpmail.logging_config import setup_logging, get_logger


@pytest.fixture
def clean_logging():
    """Clean up logging handlers after each test."""
    yield
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.WARNING)  # Reset to default


def test_setup_logging_level(clean_logging):
    """Test setting the logging level."""
    setup_logging(level="DEBUG")
    root_logger = logging.getLogger()
    assert root_logger.level == logging.DEBUG


def test_setup_logging_console(clean_logging, capsys):
    """Test logging to the console."""
    setup_logging(level="INFO", console=True)
    logger = get_logger(__name__)
    logger.info("test message")
    captured = capsys.readouterr()
    assert "test message" in captured.out
    assert "INFO" in captured.out


def test_setup_logging_file(clean_logging, tmp_path):
    """Test logging to a file."""
    log_file = tmp_path / "test.log"
    setup_logging(level="INFO", log_file=str(log_file))
    logger = get_logger(__name__)
    logger.info("test message")

    log_content = log_file.read_text()
    assert "test message" in log_content
    assert "INFO" in log_content


def test_get_logger(clean_logging):
    """Test getting a logger instance."""
    logger = get_logger("my_test_logger")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "my_test_logger"


def test_setup_logging_no_handlers(clean_logging):
    """Test that a NullHandler is added if no other handlers are configured."""
    setup_logging(level="INFO", console=False, log_file=None)
    root_logger = logging.getLogger()
    assert len(root_logger.handlers) == 1
    assert isinstance(root_logger.handlers[0], logging.NullHandler)
