"""Tests for the random_string utility function."""
import string
from tmpmail.utils import random_string


def test_random_string_default_length():
    """Test random_string with default length."""
    s = random_string()
    assert isinstance(s, str)
    assert len(s) == 8


def test_random_string_custom_length():
    """Test random_string with a custom length."""
    s = random_string(length=16)
    assert isinstance(s, str)
    assert len(s) == 16


def test_random_string_zero_length():
    """Test random_string with zero length."""
    s = random_string(length=0)
    assert isinstance(s, str)
    assert len(s) == 0


def test_random_string_characters():
    """Test that random_string contains only allowed characters."""
    allowed_chars = string.ascii_letters + string.digits
    s = random_string(length=100)
    for char in s:
        assert char in allowed_chars


def test_random_string_uniqueness():
    """Test that multiple calls to random_string produce different results."""
    results = {random_string() for _ in range(100)}
    assert len(results) > 95  # High probability of being unique
