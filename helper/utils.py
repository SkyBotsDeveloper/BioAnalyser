import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Hashable, List, Tuple

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, ReturnDocument
from pymongo.errors import PyMongoError
from pyrogram import Client, enums, errors

from config import (
    MONGO_URI,
    CHAT_REGISTER_CACHE_TTL,
    DEFAULT_CONFIG,
    DEFAULT_PUNISHMENT,
    DEFAULT_WARNING_LIMIT,
    LOCAL_CACHE_MAX_SIZE
)

logger = logging.getLogger(__name__)

mongo_client = AsyncIOMotorClient(
    MONGO_URI,
    maxPoolSize=100,
    minPoolSize=1,
    serverSelectionTimeoutMS=5000,
    connectTimeoutMS=10000,
    socketTimeoutMS=20000,
)
db = mongo_client["telegram_bot_db"]
warnings_collection = db["warnings"]
punishments_collection = db["punishments"]
whitelists_collection = db["whitelists"]
chats_collection = db["chats"]

ADMIN_CACHE_TTL = 120
CONFIG_CACHE_TTL = 300
WHITELIST_CACHE_TTL = 300
WHITELIST_LIST_CACHE_TTL = 60
WARNING_EMPTY_CACHE_TTL = 900
MAX_ADMIN_FLOOD_SLEEP = 30

CacheValue = Tuple[float, Any]

_admin_cache: Dict[Tuple[int, int], CacheValue] = {}
_config_cache: Dict[int, CacheValue] = {}
_whitelist_cache: Dict[Tuple[int, int], CacheValue] = {}
_whitelist_list_cache: Dict[int, CacheValue] = {}
_warning_state_cache: Dict[Tuple[int, int], CacheValue] = {}
_warning_fallback_cache: Dict[Tuple[int, int], CacheValue] = {}
_chat_register_cache: Dict[int, CacheValue] = {}

_database_ready = False
_database_ready_lock = asyncio.Lock()


def _flood_wait_seconds(exc: errors.FloodWait) -> int:
    return int(getattr(exc, "value", getattr(exc, "x", 0)) or 0)


def _cache_get(cache: Dict[Hashable, CacheValue], key: Hashable):
    item = cache.get(key)
    if item is None:
        return None

    expires_at, value = item
    if expires_at <= time.monotonic():
        cache.pop(key, None)
        return None
    return value


def _cache_set(cache: Dict[Hashable, CacheValue], key: Hashable, value, ttl: int) -> None:
    if ttl <= 0:
        return

    if len(cache) >= LOCAL_CACHE_MAX_SIZE:
        now = time.monotonic()
        for cached_key, (expires_at, _) in list(cache.items()):
            if expires_at <= now:
                cache.pop(cached_key, None)

        if len(cache) >= LOCAL_CACHE_MAX_SIZE:
            trim_count = max(1, LOCAL_CACHE_MAX_SIZE // 10)
            for cached_key in list(cache)[:trim_count]:
                cache.pop(cached_key, None)

    cache[key] = (time.monotonic() + ttl, value)


def _cache_delete(cache: Dict[Hashable, CacheValue], key: Hashable) -> None:
    cache.pop(key, None)


async def ensure_database_ready() -> None:
    global _database_ready

    if _database_ready:
        return

    async with _database_ready_lock:
        if _database_ready:
            return

        try:
            await asyncio.gather(
                warnings_collection.create_index(
                    [("chat_id", ASCENDING), ("user_id", ASCENDING)],
                    unique=True,
                    background=True,
                ),
                whitelists_collection.create_index(
                    [("chat_id", ASCENDING), ("user_id", ASCENDING)],
                    unique=True,
                    background=True,
                ),
                punishments_collection.create_index(
                    [("chat_id", ASCENDING)],
                    unique=True,
                    background=True,
                ),
                chats_collection.create_index(
                    [("chat_id", ASCENDING)],
                    unique=True,
                    background=True,
                ),
                chats_collection.create_index(
                    [("active", ASCENDING), ("type", ASCENDING)],
                    background=True,
                ),
            )
        except PyMongoError:
            logger.exception("Unable to create MongoDB indexes; continuing without startup indexes")
        finally:
            _database_ready = True


def _chat_type_value(chat) -> str:
    chat_type = getattr(chat, "type", None)
    return str(getattr(chat_type, "value", chat_type or "unknown"))


def _chat_title(chat) -> str:
    title = getattr(chat, "title", None)
    if title:
        return title

    first_name = getattr(chat, "first_name", None)
    last_name = getattr(chat, "last_name", None)
    if first_name:
        return f"{first_name}{(' ' + last_name) if last_name else ''}"

    username = getattr(chat, "username", None)
    if username:
        return username

    return str(getattr(chat, "id", "unknown"))


async def register_chat(chat) -> None:
    chat_id = getattr(chat, "id", None)
    if chat_id is None:
        return

    if _cache_get(_chat_register_cache, chat_id):
        return

    await ensure_database_ready()
    now = datetime.now(timezone.utc)
    username = getattr(chat, "username", None)

    try:
        await chats_collection.update_one(
            {"chat_id": chat_id},
            {
                "$set": {
                    "chat_id": chat_id,
                    "type": _chat_type_value(chat),
                    "title": _chat_title(chat),
                    "username": username,
                    "active": True,
                    "last_seen": now,
                    "inactive_reason": None,
                },
                "$setOnInsert": {"first_seen": now},
            },
            upsert=True,
        )
    except PyMongoError:
        logger.exception("MongoDB error while registering chat %s", chat_id)
        return

    _cache_set(_chat_register_cache, chat_id, True, CHAT_REGISTER_CACHE_TTL)


async def mark_user_started(chat) -> None:
    chat_id = getattr(chat, "id", None)
    if chat_id is None:
        return

    await ensure_database_ready()
    now = datetime.now(timezone.utc)
    username = getattr(chat, "username", None)

    try:
        await chats_collection.update_one(
            {"chat_id": chat_id},
            {
                "$set": {
                    "chat_id": chat_id,
                    "type": _chat_type_value(chat),
                    "title": _chat_title(chat),
                    "username": username,
                    "active": True,
                    "started": True,
                    "last_seen": now,
                    "last_start": now,
                    "inactive_reason": None,
                },
                "$setOnInsert": {"first_seen": now, "first_start": now},
            },
            upsert=True,
        )
    except PyMongoError:
        logger.exception("MongoDB error while recording started user %s", chat_id)
        return

    _cache_set(_chat_register_cache, chat_id, True, CHAT_REGISTER_CACHE_TTL)


async def get_broadcast_chats() -> List[dict]:
    await ensure_database_ready()

    try:
        cursor = chats_collection.find(
            {"active": True},
            {"_id": 0, "chat_id": 1, "type": 1, "title": 1, "username": 1},
        ).sort("last_seen", ASCENDING)
        return await cursor.to_list(length=None)
    except PyMongoError:
        logger.exception("MongoDB error while loading broadcast chats")
        return []


async def mark_chat_inactive(chat_id: int, reason: str) -> None:
    await ensure_database_ready()

    try:
        await chats_collection.delete_one({"chat_id": chat_id})
    except PyMongoError:
        logger.exception("MongoDB error while marking chat %s inactive", chat_id)
        return

    _cache_delete(_chat_register_cache, chat_id)
    logger.info("Removed chat %s from registry: %s", chat_id, reason)


async def get_bot_stats() -> dict:
    await ensure_database_ready()

    try:
        docs = await chats_collection.aggregate([
            {"$match": {"active": True}},
            {"$group": {"_id": "$type", "count": {"$sum": 1}}},
        ]).to_list(length=None)
        started_users = await chats_collection.count_documents({
            "active": True,
            "type": "private",
            "started": True,
        })
    except PyMongoError:
        logger.exception("MongoDB error while loading bot stats")
        return {
            "total": 0,
            "groups": 0,
            "channels": 0,
            "private_users": 0,
            "started_users": 0,
            "by_type": {},
        }

    by_type = {doc["_id"]: doc["count"] for doc in docs}
    groups = sum(by_type.get(chat_type, 0) for chat_type in ("group", "supergroup", "forum"))
    channels = by_type.get("channel", 0)
    private_users = by_type.get("private", 0)

    return {
        "total": sum(by_type.values()),
        "groups": groups,
        "channels": channels,
        "private_users": private_users,
        "started_users": started_users,
        "by_type": by_type,
    }


async def is_admin(
    client: Client,
    chat_id: int,
    user_id: int,
    default_on_error: bool = False,
) -> bool:
    if not user_id:
        return default_on_error

    key = (chat_id, user_id)
    cached = _cache_get(_admin_cache, key)
    if cached is not None:
        return bool(cached)

    for attempt in range(2):
        try:
            member = await client.get_chat_member(chat_id, user_id)
            is_chat_admin = member.status in {
                enums.ChatMemberStatus.OWNER,
                enums.ChatMemberStatus.ADMINISTRATOR,
            }
            break
        except errors.FloodWait as exc:
            wait_for = _flood_wait_seconds(exc)
            if wait_for <= MAX_ADMIN_FLOOD_SLEEP and attempt == 0:
                logger.warning("FloodWait while checking admin status: sleeping %ss", wait_for)
                await asyncio.sleep(wait_for + 1)
                continue

            logger.warning("Skipping admin check after FloodWait: %ss", wait_for)
            return default_on_error
        except errors.UserNotParticipant:
            is_chat_admin = False
            break
        except errors.RPCError:
            logger.exception("Telegram error while checking admin status for %s in %s", user_id, chat_id)
            return default_on_error
    else:
        return default_on_error

    _cache_set(_admin_cache, key, is_chat_admin, ADMIN_CACHE_TTL)
    return is_chat_admin


async def get_config(chat_id: int):
    cached = _cache_get(_config_cache, chat_id)
    if cached is not None:
        return cached

    await ensure_database_ready()

    try:
        doc = await punishments_collection.find_one({"chat_id": chat_id})
    except PyMongoError:
        logger.exception("MongoDB error while loading config for chat %s", chat_id)
        return DEFAULT_CONFIG

    if doc:
        config = (
            doc.get("mode", "warn"),
            doc.get("limit", DEFAULT_WARNING_LIMIT),
            doc.get("penalty", DEFAULT_PUNISHMENT),
        )
    else:
        config = DEFAULT_CONFIG

    _cache_set(_config_cache, chat_id, config, CONFIG_CACHE_TTL)
    return config


async def update_config(chat_id: int, mode=None, limit=None, penalty=None):
    update = {}
    if mode is not None:
        update["mode"] = mode
    if limit is not None:
        update["limit"] = limit
    if penalty is not None:
        update["penalty"] = penalty

    if not update:
        return

    await ensure_database_ready()

    try:
        await punishments_collection.update_one(
            {"chat_id": chat_id},
            {"$set": update},
            upsert=True,
        )
    except PyMongoError:
        logger.exception("MongoDB error while updating config for chat %s", chat_id)
        return

    current_mode, current_limit, current_penalty = _cache_get(_config_cache, chat_id) or DEFAULT_CONFIG
    _cache_set(
        _config_cache,
        chat_id,
        (
            update.get("mode", current_mode),
            update.get("limit", current_limit),
            update.get("penalty", current_penalty),
        ),
        CONFIG_CACHE_TTL,
    )


async def increment_warning(chat_id: int, user_id: int) -> int:
    await ensure_database_ready()

    key = (chat_id, user_id)
    try:
        doc = await warnings_collection.find_one_and_update(
            {"chat_id": chat_id, "user_id": user_id},
            {
                "$inc": {"count": 1},
                "$setOnInsert": {"chat_id": chat_id, "user_id": user_id},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
    except PyMongoError:
        logger.exception("MongoDB error while incrementing warning for %s in %s", user_id, chat_id)
        count = int(_cache_get(_warning_fallback_cache, key) or 0) + 1
        _cache_set(_warning_fallback_cache, key, count, WARNING_EMPTY_CACHE_TTL)
        return count

    count = int(doc.get("count", 1)) if doc else 1
    _cache_set(_warning_state_cache, key, count, WARNING_EMPTY_CACHE_TTL)
    _cache_delete(_warning_fallback_cache, key)
    return count


async def reset_warnings(chat_id: int, user_id: int):
    key = (chat_id, user_id)
    cached_warning_state = _cache_get(_warning_state_cache, key)
    if cached_warning_state is False:
        return

    await ensure_database_ready()

    try:
        await warnings_collection.delete_one({"chat_id": chat_id, "user_id": user_id})
    except PyMongoError:
        logger.exception("MongoDB error while resetting warnings for %s in %s", user_id, chat_id)
        _cache_delete(_warning_fallback_cache, key)
        return

    _cache_set(_warning_state_cache, key, False, WARNING_EMPTY_CACHE_TTL)
    _cache_delete(_warning_fallback_cache, key)


async def is_whitelisted(chat_id: int, user_id: int) -> bool:
    key = (chat_id, user_id)
    cached = _cache_get(_whitelist_cache, key)
    if cached is not None:
        return bool(cached)

    await ensure_database_ready()

    try:
        doc = await whitelists_collection.find_one(
            {"chat_id": chat_id, "user_id": user_id},
            {"_id": 1},
        )
    except PyMongoError:
        logger.exception("MongoDB error while checking whitelist for %s in %s", user_id, chat_id)
        return False

    result = bool(doc)
    _cache_set(_whitelist_cache, key, result, WHITELIST_CACHE_TTL)
    return result


async def add_whitelist(chat_id: int, user_id: int):
    await ensure_database_ready()

    try:
        await whitelists_collection.update_one(
            {"chat_id": chat_id, "user_id": user_id},
            {"$setOnInsert": {"chat_id": chat_id, "user_id": user_id}},
            upsert=True,
        )
    except PyMongoError:
        logger.exception("MongoDB error while adding whitelist for %s in %s", user_id, chat_id)
        return

    _cache_set(_whitelist_cache, (chat_id, user_id), True, WHITELIST_CACHE_TTL)
    _cache_delete(_whitelist_list_cache, chat_id)


async def remove_whitelist(chat_id: int, user_id: int):
    await ensure_database_ready()

    try:
        await whitelists_collection.delete_one({"chat_id": chat_id, "user_id": user_id})
    except PyMongoError:
        logger.exception("MongoDB error while removing whitelist for %s in %s", user_id, chat_id)
        return

    _cache_set(_whitelist_cache, (chat_id, user_id), False, WHITELIST_CACHE_TTL)
    _cache_delete(_whitelist_list_cache, chat_id)


async def get_whitelist(chat_id: int) -> List[int]:
    cached = _cache_get(_whitelist_list_cache, chat_id)
    if cached is not None:
        return list(cached)

    await ensure_database_ready()

    try:
        cursor = whitelists_collection.find({"chat_id": chat_id}, {"user_id": 1})
        docs = await cursor.to_list(length=None)
    except PyMongoError:
        logger.exception("MongoDB error while loading whitelist for chat %s", chat_id)
        return []

    ids = [doc["user_id"] for doc in docs]
    _cache_set(_whitelist_list_cache, chat_id, ids, WHITELIST_LIST_CACHE_TTL)
    return ids
