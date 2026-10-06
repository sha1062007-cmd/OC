import os
import sys
import pathlib

# Ensure project root is always in sys.path across all operating systems
ROOT_DIR = str(pathlib.Path(__file__).resolve().parent.parent)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import pytest

# Ensure offline mock mode for instant deterministic testing
os.environ["MOCK_LLM"] = "true"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
