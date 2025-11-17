# Copyright (C) @EliteSid
# Channel: https://t.me/VivaanUpdates

import re

API_ID = "25387587" # Your Telegram API ID
API_HASH = "7b8e2e5bb84c617a474656ad7439ea6a" # Your Telegram API Hash
BOT_TOKEN = "7895494603:AAHU9fxmyH3ofnNto_AP6qAxekcNvGOorOA" # Your Bot Token

# MongoDB connection URI
MONGO_URI = "mongodb+srv://blood:blood@blood.nzlxlfq.mongodb.net/?retryWrites=true&w=majority&appName=blood"

DEFAULT_WARNING_LIMIT = 5
DEFAULT_PUNISHMENT = "mute" # Options: "mute", "ban"
DEFAULT_CONFIG = ("warn", DEFAULT_WARNING_LIMIT, DEFAULT_PUNISHMENT)

# Regex pattern to detect URLs in user bios
URL_PATTERN = re.compile(
    r'(?i)(?:'
        r'@[a-zA-Z0-9_][a-zA-Z0-9_]{3,31}|'
        r't\.me/[a-zA-Z0-9_./\-]+|'
        r'telegram\.me/[a-zA-Z0-9_./\-]+|'
        r'tg\.me/[a-zA-Z0-9_./\-]+|'
        r'https?://[^\s]+|'
        r'www\.[a-zA-Z0-9.\-]+(?:[/?#][^\s]*)?|'
        r'(?:bit\.ly|ow\.ly|tinyurl\.com|short\.link|goo\.gl|is\.gd)/[a-zA-Z0-9.\-_]+|'
        r'(?:instagram|tiktok|twitter|facebook|youtube|linkedin)\.com/[a-zA-Z0-9.\-_~:/?#@!$&\'()*+,;=%]+|'
        r'(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+(?:com|org|net|io|co|uk|app|dev|shop)(?:[/?#][^\s]*)?'
    r')'
)

