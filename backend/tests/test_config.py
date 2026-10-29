"""Unit tests for app.config."""
import os
from unittest.mock import patch

from app.config import get_gemini_api_key, has_gemini_api_key


def test_gemini_api_key_configured():
    with patch.dict(os.environ, {"GEMINI_API_KEY": "AIzaSyTestKey123"}, clear=False):
        assert get_gemini_api_key() == "AIzaSyTestKey123"
        assert has_gemini_api_key() is True


def test_gemini_api_key_empty():
    with patch.dict(os.environ, {"GEMINI_API_KEY": ""}, clear=False):
        assert get_gemini_api_key() == ""
        assert has_gemini_api_key() is False


def test_gemini_api_key_whitespace():
    with patch.dict(os.environ, {"GEMINI_API_KEY": "   \n\t "}, clear=False):
        assert get_gemini_api_key() == ""
        assert has_gemini_api_key() is False


def test_gemini_api_key_missing():
    env = os.environ.copy()
    env.pop("GEMINI_API_KEY", None)
    with patch.dict(os.environ, env, clear=True):
        assert get_gemini_api_key() == ""
        assert has_gemini_api_key() is False
