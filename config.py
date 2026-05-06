# Copyright (C) @EliteSid
# Channel: https://t.me/VivaanUpdates

from dotenv import load_dotenv
import os
import re

# Load environment variables from .env file
load_dotenv()


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        value = int(raw_value)
    except ValueError:
        return default

    return max(value, minimum)


def _env_int_set(*names: str):
    values = set()
    for name in names:
        raw_value = os.getenv(name, "")
        for part in raw_value.replace(" ", "").split(","):
            if not part:
                continue
            try:
                values.add(int(part))
            except ValueError:
                continue
    return values

# ============================================
# API CREDENTIALS (Load from .env file)
# ============================================
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
OWNER_IDS = _env_int_set("OWNER_ID", "OWNER_IDS")

# Validate that all required environment variables are set
if not all([API_ID, API_HASH, BOT_TOKEN, MONGO_URI]):
    raise ValueError(
        "❌ CRITICAL: Missing required environment variables!\n"
        "Please create a .env file in your project root with:\n"
        "  API_ID=your_api_id\n"
        "  API_HASH=your_api_hash\n"
        "  BOT_TOKEN=your_bot_token\n"
        "  MONGO_URI=your_mongodb_uri\n\n"
        "Get your credentials from:\n"
        "  - API_ID & API_HASH: https://my.telegram.org/\n"
        "  - BOT_TOKEN: @BotFather on Telegram\n"
        "  - MONGO_URI: MongoDB Atlas (https://www.mongodb.com/cloud/atlas)"
    )

# ============================================
# WARNING & PUNISHMENT CONFIG
# ============================================
DEFAULT_WARNING_LIMIT = 5  # Number of warnings before punishment
DEFAULT_PUNISHMENT = "mute"  # Options: "mute" or "ban"

# Default configuration tuple (mode, limit, penalty)
DEFAULT_CONFIG = ('warn', DEFAULT_WARNING_LIMIT, DEFAULT_PUNISHMENT)

# ============================================
# PERFORMANCE & STABILITY TUNING
# ============================================
BOT_WORKERS = _env_int("BOT_WORKERS", 32, 1)
BOT_SLEEP_THRESHOLD = _env_int("BOT_SLEEP_THRESHOLD", 30, 0)
MAX_MESSAGE_CACHE_SIZE = _env_int("MAX_MESSAGE_CACHE_SIZE", 10000, 1000)
BIO_CACHE_TTL = _env_int("BIO_CACHE_TTL", 60, 0)
CLEAN_BIO_CACHE_TTL = _env_int("CLEAN_BIO_CACHE_TTL", min(BIO_CACHE_TTL, 10), 0)
LINK_BIO_CACHE_TTL = _env_int("LINK_BIO_CACHE_TTL", min(BIO_CACHE_TTL, 20), 0)
PROFILE_FETCH_CONCURRENCY = _env_int("PROFILE_FETCH_CONCURRENCY", 8, 1)
MAX_FLOOD_WAIT = _env_int("MAX_FLOOD_WAIT", 60, 0)
LOCAL_CACHE_MAX_SIZE = _env_int("LOCAL_CACHE_MAX_SIZE", 50000, 1000)
TELEGRAM_WRITE_CONCURRENCY = _env_int("TELEGRAM_WRITE_CONCURRENCY", 16, 1)
PENALTY_CACHE_TTL = _env_int("PENALTY_CACHE_TTL", 600, 30)
WARNING_NOTICE_COOLDOWN = _env_int("WARNING_NOTICE_COOLDOWN", 3, 0)
BROADCAST_CONCURRENCY = _env_int("BROADCAST_CONCURRENCY", 3, 1)
BROADCAST_DELAY_MS = _env_int("BROADCAST_DELAY_MS", 150, 0)
CHAT_REGISTER_CACHE_TTL = _env_int("CHAT_REGISTER_CACHE_TTL", 300, 1)

# ============================================
# URL DETECTION PATTERN
# ============================================
# Regex pattern to detect URLs in user bios
# Detects: @mentions, telegram links, URLs, social media, domains, shorteners
URL_PATTERN = re.compile(
    r'(?i)(?:'
        r'@[a-zA-Z0-9_][a-zA-Z0-9_]{3,31}|'  # @username mentions
        r't\.me/[a-zA-Z0-9_./\-]+|'  # t.me/username
        r'telegram\.me/[a-zA-Z0-9_./\-]+|'  # telegram.me/username
        r'tg\.me/[a-zA-Z0-9_./\-]+|'  # tg.me/username
        r'https?://[^\s]+|'  # http:// or https://
        r'www\.[a-zA-Z0-9.\-]+(?:[/?#][^\s]*)?|'  # www.example.com
        r'(?:bit\.ly|ow\.ly|tinyurl\.com|short\.link|goo\.gl|is\.gd)/[a-zA-Z0-9.\-_]+|'  # URL shorteners
        r'(?:instagram|tiktok|twitter|facebook|youtube|linkedin)\.com/[a-zA-Z0-9.\-_~:/?#@!$&\'()*+,;=%]+|'  # Social media
        r'(?:[a-zA-Z0-9](?:[a-zA-Z0-9\\\\-]{0,61}[a-zA-Z0-9])?\.)+(?:com|org|net|io|co|uk|app|dev|shop)(?:[/?#][^\s]*)?'  # Domain names
    r')'
)
