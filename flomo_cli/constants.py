"""Central constants for Flomo CLI."""

from pathlib import Path

# API
API_BASE = "https://flomoapp.com/api/v1"
API_KEY = "flomo_web"
APP_VERSION = "4.0"
PLATFORM = "web"
SIGN_SECRET = "dbbc3dd73364b4084c3a69346e0ce2b2"
TIMEZONE = "8:0"

# Config
CONFIG_DIR = Path.home() / ".flomo-cli"
TOKEN_FILE = "token.json"

# Defaults
DEFAULT_LIST_LIMIT = 20
MAX_PAGE_SIZE = 200
