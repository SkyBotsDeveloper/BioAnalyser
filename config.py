# Copyright (C) @EliteSid
# Channel: https://t.me/VivaanUpdates

from dotenv import load_dotenv
import os
import re

# Load environment variables from .env file
load_dotenv()

# ============================================
# API CREDENTIALS (Load from .env file)
# ============================================
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

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
