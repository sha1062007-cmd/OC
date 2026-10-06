"""Pytest global configuration and fixtures."""
import os
import pytest

# Ensure offline mock mode for instant deterministic testing
os.environ["MOCK_LLM"] = "true"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
