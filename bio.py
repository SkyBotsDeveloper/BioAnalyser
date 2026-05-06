"""
Author: Elite Sid
User: https://t.me/EliteSid
Channel: https://t.me/VivaanUpdates
"""

import asyncio
import functools
import logging
import time

from pyrogram import Client, filters, errors, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions

from helper.utils import (
    is_admin,
    get_config, update_config,
    increment_warning, reset_warnings,
    is_whitelisted, add_whitelist, remove_whitelist, get_whitelist,
    get_bot_stats, get_broadcast_chats, mark_chat_inactive, mark_user_started, register_chat
)

from config import (
    API_ID,
    API_HASH,
    BOT_TOKEN,
    BOT_SLEEP_THRESHOLD,
    BOT_WORKERS,
    BROADCAST_CONCURRENCY,
    BROADCAST_DELAY_MS,
    BIO_CACHE_TTL,
    CLEAN_BIO_CACHE_TTL,
    LINK_BIO_CACHE_TTL,
    LOCAL_CACHE_MAX_SIZE,
    MAX_FLOOD_WAIT,
    MAX_MESSAGE_CACHE_SIZE,
    OWNER_IDS,
    PENALTY_CACHE_TTL,
    PROFILE_FETCH_CONCURRENCY,
    TELEGRAM_WRITE_CONCURRENCY,
    WARNING_NOTICE_COOLDOWN,
    URL_PATTERN
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

app = Client(
    "biolink_protector_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=BOT_WORKERS,
    sleep_threshold=BOT_SLEEP_THRESHOLD,
    max_message_cache_size=MAX_MESSAGE_CACHE_SIZE,
)

_profile_fetch_semaphore = asyncio.Semaphore(PROFILE_FETCH_CONCURRENCY)
_telegram_write_semaphore = asyncio.Semaphore(TELEGRAM_WRITE_CONCURRENCY)
_profile_cache = {}
_bio_decision_cache = {}
_notice_cache = {}
_penalty_cache = {}
_warning_notice_cache = {}
_profile_fetch_tasks = {}
_chat_user_locks = {}
_bot_id = None


def _flood_wait_seconds(exc: errors.FloodWait) -> int:
    return int(getattr(exc, "value", getattr(exc, "x", 0)) or 0)


def _cache_get(cache, key):
    item = cache.get(key)
    if item is None:
        return None

    expires_at, value = item
    if expires_at <= time.monotonic():
        cache.pop(key, None)
        return None
    return value


def _cache_set(cache, key, value, ttl: int) -> None:
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


def _cache_delete(cache, key) -> None:
    cache.pop(key, None)


def _get_lock(cache, key) -> asyncio.Lock:
    lock = cache.get(key)
    if lock is not None:
        return lock

    if len(cache) >= LOCAL_CACHE_MAX_SIZE:
        for cached_key, cached_lock in list(cache.items()):
            if not cached_lock.locked():
                cache.pop(cached_key, None)
            if len(cache) < LOCAL_CACHE_MAX_SIZE:
                break

    lock = asyncio.Lock()
    cache[key] = lock
    return lock


def _full_name(user) -> str:
    first_name = getattr(user, "first_name", None) or "User"
    last_name = getattr(user, "last_name", None)
    return f"{first_name}{(' ' + last_name) if last_name else ''}"


def _mention(user_id: int, full_name: str) -> str:
    return f"[{full_name}](tg://user?id={user_id})"


def is_owner(user_id: int) -> bool:
    return bool(user_id and user_id in OWNER_IDS)


def extract_command_payload(message) -> str:
    raw_text = message.text or message.caption or ""
    parts = raw_text.split(maxsplit=1)
    if len(parts) < 2:
        return ""
    return parts[1].strip()


async def get_bot_id(client: Client) -> int:
    global _bot_id
    if _bot_id is None:
        me = await client.get_me()
        _bot_id = me.id
    return _bot_id


def chat_member_user_id(member):
    user = getattr(member, "user", None)
    return getattr(user, "id", None)


def chat_member_is_active(member) -> bool:
    if member is None:
        return False

    inactive_statuses = {
        enums.ChatMemberStatus.LEFT,
        enums.ChatMemberStatus.BANNED,
    }
    if member.status in inactive_statuses:
        return False

    if member.status == enums.ChatMemberStatus.RESTRICTED and getattr(member, "is_member", True) is False:
        return False

    return True


def guarded_handler(name: str):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(client: Client, update):
            try:
                return await func(client, update)
            except errors.FloodWait as exc:
                wait_for = _flood_wait_seconds(exc)
                if wait_for <= MAX_FLOOD_WAIT:
                    logger.warning("%s hit FloodWait; sleeping %ss", name, wait_for)
                    await asyncio.sleep(wait_for + 1)
                else:
                    logger.warning("%s skipped after long FloodWait: %ss", name, wait_for)
            except Exception:
                logger.exception("Unhandled error in %s", name)

        return wrapper

    return decorator


async def telegram_call(action, *args, default=None, retries: int = 1, suppress=(), write: bool = False, **kwargs):
    for attempt in range(retries + 1):
        try:
            if write:
                async with _telegram_write_semaphore:
                    return await action(*args, **kwargs)

            return await action(*args, **kwargs)
        except errors.FloodWait as exc:
            wait_for = _flood_wait_seconds(exc)
            if wait_for <= MAX_FLOOD_WAIT and attempt < retries:
                logger.warning("FloodWait from Telegram; sleeping %ss", wait_for)
                await asyncio.sleep(wait_for + 1)
                continue

            logger.warning("Telegram call skipped after FloodWait: %ss", wait_for)
            return default
        except suppress as exc:
            logger.warning("Telegram RPC call failed: %s", exc)
            return default

    return default


async def fetch_user_profile(client: Client, user_id: int, force_refresh: bool = False):
    if not force_refresh:
        cached = _cache_get(_profile_cache, user_id)
        if cached is not None:
            return cached

    async with _profile_fetch_semaphore:
        if not force_refresh:
            cached = _cache_get(_profile_cache, user_id)
            if cached is not None:
                return cached

        user = await telegram_call(
            client.get_chat,
            user_id,
            default=None,
            retries=1,
            suppress=(errors.RPCError,),
        )
        if user is None:
            return None

        profile = (user.bio or "", _full_name(user))
        _cache_set(_profile_cache, user_id, profile, BIO_CACHE_TTL)
        return profile


async def get_user_profile(client: Client, user_id: int, force_refresh: bool = False):
    if not force_refresh:
        cached = _cache_get(_profile_cache, user_id)
        if cached is not None:
            return cached

    task_key = (user_id, force_refresh)
    existing_task = _profile_fetch_tasks.get(task_key)
    if existing_task is not None:
        return await asyncio.shield(existing_task)

    task = asyncio.create_task(fetch_user_profile(client, user_id, force_refresh=force_refresh))
    _profile_fetch_tasks[task_key] = task
    try:
        return await asyncio.shield(task)
    finally:
        if _profile_fetch_tasks.get(task_key) is task:
            _profile_fetch_tasks.pop(task_key, None)


async def get_bio_decision(client: Client, user_id: int):
    cached = _cache_get(_bio_decision_cache, user_id)
    if cached is not None:
        return cached

    profile = await get_user_profile(client, user_id, force_refresh=True)
    if profile is None:
        return None

    bio, full_name = profile
    has_link = bool(URL_PATTERN.search(bio))
    decision = (has_link, bio, full_name)
    _cache_set(_bio_decision_cache, user_id, decision, LINK_BIO_CACHE_TTL if has_link else CLEAN_BIO_CACHE_TTL)
    return decision


async def notify_missing_delete_permission(client: Client, chat_id: int) -> None:
    cache_key = ("delete_permission", chat_id)
    if _cache_get(_notice_cache, cache_key):
        return

    _cache_set(_notice_cache, cache_key, True, 300)
    await telegram_call(
        client.send_message,
        chat_id,
        "Please grant me delete permission.",
        retries=1,
        suppress=(errors.RPCError,),
        write=True,
    )


async def delete_group_message(client: Client, message) -> bool:
    try:
        async with _telegram_write_semaphore:
            await message.delete()
        return True
    except errors.FloodWait as exc:
        wait_for = _flood_wait_seconds(exc)
        if wait_for <= MAX_FLOOD_WAIT:
            logger.warning("Delete hit FloodWait; sleeping %ss", wait_for)
            await asyncio.sleep(wait_for + 1)
            try:
                async with _telegram_write_semaphore:
                    await message.delete()
                return True
            except (errors.RPCError, errors.FloodWait):
                logger.exception("Message delete failed after retry")
                return False

        logger.warning("Message delete skipped after long FloodWait: %ss", wait_for)
        return False
    except (errors.MessageDeleteForbidden, errors.ChatAdminRequired):
        await notify_missing_delete_permission(client, message.chat.id)
        return False
    except errors.RPCError:
        logger.exception("Message delete failed")
        return False


async def safe_edit(message, text: str, reply_markup=None) -> None:
    if message is None:
        return

    await telegram_call(
        message.edit_text,
        text,
        reply_markup=reply_markup,
        retries=1,
        suppress=(errors.RPCError,),
        write=True,
    )


async def apply_penalty(client: Client, chat_id: int, user_id: int, penalty: str) -> bool:
    for attempt in range(2):
        try:
            async with _telegram_write_semaphore:
                if penalty == "mute":
                    await client.restrict_chat_member(chat_id, user_id, ChatPermissions())
                else:
                    await client.ban_chat_member(chat_id, user_id)
            return True
        except errors.FloodWait as exc:
            wait_for = _flood_wait_seconds(exc)
            if wait_for <= MAX_FLOOD_WAIT and attempt == 0:
                logger.warning("%s hit FloodWait; sleeping %ss", penalty, wait_for)
                await asyncio.sleep(wait_for + 1)
                continue

            logger.warning("%s skipped after FloodWait: %ss", penalty, wait_for)
            return False
        except errors.ChatAdminRequired:
            raise
        except errors.RPCError:
            logger.exception("Unable to apply %s to %s in %s", penalty, user_id, chat_id)
            return False

    return False


def already_penalized(chat_id: int, user_id: int) -> bool:
    return bool(_cache_get(_penalty_cache, (chat_id, user_id)))


def mark_penalized(chat_id: int, user_id: int, penalty: str) -> None:
    _cache_set(_penalty_cache, (chat_id, user_id), penalty, PENALTY_CACHE_TTL)


def clear_penalty(chat_id: int, user_id: int) -> None:
    _cache_delete(_penalty_cache, (chat_id, user_id))


def should_send_warning_notice(chat_id: int, user_id: int) -> bool:
    if WARNING_NOTICE_COOLDOWN <= 0:
        return True

    key = (chat_id, user_id)
    if _cache_get(_warning_notice_cache, key):
        return False

    _cache_set(_warning_notice_cache, key, True, WARNING_NOTICE_COOLDOWN)
    return True


def is_inactive_broadcast_error(exc: errors.RPCError) -> bool:
    reason = exc.__class__.__name__.lower()
    inactive_markers = (
        "adminrequired",
        "banned",
        "blocked",
        "deactivated",
        "forbidden",
        "invalid",
        "kicked",
        "private",
        "writeforbidden",
    )
    return any(marker in reason for marker in inactive_markers)


async def send_broadcast_item(client: Client, chat_id: int, text: str, source_chat_id=None, source_message_id=None):
    for attempt in range(2):
        try:
            async with _telegram_write_semaphore:
                if source_chat_id is not None and source_message_id is not None:
                    await client.copy_message(chat_id, source_chat_id, source_message_id)
                else:
                    await client.send_message(chat_id, text)

            if BROADCAST_DELAY_MS > 0:
                await asyncio.sleep(BROADCAST_DELAY_MS / 1000)
            return "sent", None
        except errors.FloodWait as exc:
            wait_for = _flood_wait_seconds(exc)
            if wait_for <= MAX_FLOOD_WAIT and attempt == 0:
                logger.warning("Broadcast FloodWait for %s: sleeping %ss", chat_id, wait_for)
                await asyncio.sleep(wait_for + 1)
                continue
            return "failed", f"FloodWait {wait_for}s"
        except errors.RPCError as exc:
            reason = exc.__class__.__name__
            if is_inactive_broadcast_error(exc):
                await mark_chat_inactive(chat_id, reason)
                return "inactive", reason
            logger.warning("Broadcast failed for %s: %s", chat_id, exc)
            return "failed", reason

    return "failed", "retry_failed"


async def run_broadcast_job(client: Client, status_message, chats, text: str, source_chat_id=None, source_message_id=None):
    total = len(chats)
    stats = {"sent": 0, "failed": 0, "inactive": 0}
    queue = asyncio.Queue()
    last_update = 0.0

    for chat in chats:
        queue.put_nowait(chat)

    async def update_status(force: bool = False) -> None:
        nonlocal last_update
        now = time.monotonic()
        if not force and now - last_update < 5:
            return
        last_update = now
        done = stats["sent"] + stats["failed"] + stats["inactive"]
        await safe_edit(
            status_message,
            "**Broadcast running...**\n\n"
            f"Total: `{total}`\n"
            f"Done: `{done}`\n"
            f"Sent: `{stats['sent']}`\n"
            f"Failed: `{stats['failed']}`\n"
            f"Removed/no access: `{stats['inactive']}`",
        )

    async def worker() -> None:
        while True:
            try:
                chat = queue.get_nowait()
            except asyncio.QueueEmpty:
                return

            chat_id = chat["chat_id"]
            status, _reason = await send_broadcast_item(
                client,
                chat_id,
                text,
                source_chat_id=source_chat_id,
                source_message_id=source_message_id,
            )
            stats[status] += 1
            queue.task_done()
            await update_status()

    await update_status(force=True)
    workers = [
        asyncio.create_task(worker())
        for _ in range(min(BROADCAST_CONCURRENCY, max(total, 1)))
    ]

    try:
        await asyncio.gather(*workers)
    except Exception:
        logger.exception("Broadcast job crashed")
        await safe_edit(status_message, "**Broadcast stopped because of an internal error. Check logs.**")
        return

    await safe_edit(
        status_message,
        "**Broadcast finished.**\n\n"
        f"Total: `{total}`\n"
        f"Sent: `{stats['sent']}`\n"
        f"Failed: `{stats['failed']}`\n"
        f"Removed/no access: `{stats['inactive']}`",
    )


@app.on_message(filters.all, group=-100)
@guarded_handler("remember_chat")
async def remember_chat_handler(client: Client, message):
    if message.chat:
        await register_chat(message.chat)


@app.on_chat_member_updated(group=-100)
@guarded_handler("chat_member_update")
async def chat_member_update_handler(client: Client, update):
    bot_id = await get_bot_id(client)
    old_member = getattr(update, "old_chat_member", None)
    new_member = getattr(update, "new_chat_member", None)

    if bot_id not in {chat_member_user_id(old_member), chat_member_user_id(new_member)}:
        return

    chat = getattr(update, "chat", None)
    chat_id = getattr(chat, "id", None)
    if chat_id is None:
        return

    if chat_member_is_active(new_member):
        await register_chat(chat)
    else:
        await mark_chat_inactive(chat_id, "bot_removed")


@app.on_message(filters.command("stats"), group=-50)
@guarded_handler("stats")
async def stats_handler(client: Client, message):
    chat_id = message.chat.id
    if message.chat:
        await register_chat(message.chat)

    if not OWNER_IDS:
        return await telegram_call(
            client.send_message,
            chat_id,
            "OWNER_ID or OWNER_IDS is not configured in .env.",
            reply_to_message_id=message.id,
            retries=1,
            suppress=(errors.RPCError,),
            write=True,
        )

    if not message.from_user or not is_owner(message.from_user.id):
        return

    stats = await get_bot_stats()
    by_type = stats["by_type"]
    text = (
        "**Bot Stats**\n\n"
        f"Groups: `{stats['groups']}`\n"
        f"Channels: `{stats['channels']}`\n"
        f"Users started bot: `{stats['started_users']}`\n"
        f"Known private users: `{stats['private_users']}`\n"
        f"Total broadcast targets: `{stats['total']}`\n\n"
        "**Breakdown:**\n"
        f"Private: `{by_type.get('private', 0)}`\n"
        f"Group: `{by_type.get('group', 0)}`\n"
        f"Supergroup: `{by_type.get('supergroup', 0)}`\n"
        f"Forum: `{by_type.get('forum', 0)}`\n"
        f"Channel: `{by_type.get('channel', 0)}`"
    )
    await telegram_call(
        client.send_message,
        chat_id,
        text,
        reply_to_message_id=message.id,
        retries=1,
        suppress=(errors.RPCError,),
        write=True,
    )


@app.on_message(filters.command("broadcast"), group=-50)
@guarded_handler("broadcast")
async def broadcast_handler(client: Client, message):
    chat_id = message.chat.id
    if message.chat:
        await register_chat(message.chat)

    if not OWNER_IDS:
        return await telegram_call(
            client.send_message,
            chat_id,
            "OWNER_ID or OWNER_IDS is not configured in .env.",
            reply_to_message_id=message.id,
            retries=1,
            suppress=(errors.RPCError,),
            write=True,
        )

    if not message.from_user or not is_owner(message.from_user.id):
        return

    payload = extract_command_payload(message)
    source_message = None

    if not payload and message.reply_to_message:
        source_message = message.reply_to_message
    elif not payload:
        return await telegram_call(
            client.send_message,
            chat_id,
            "Usage: `/broadcast your message` or reply to any message with `/broadcast`.",
            reply_to_message_id=message.id,
            retries=1,
            suppress=(errors.RPCError,),
            write=True,
        )

    if payload and len(payload) > 4096:
        return await telegram_call(
            client.send_message,
            chat_id,
            "Broadcast text is too long. Telegram text messages must be 4096 characters or less.",
            reply_to_message_id=message.id,
            retries=1,
            suppress=(errors.RPCError,),
            write=True,
        )

    chats = await get_broadcast_chats()
    if not chats:
        return await telegram_call(
            client.send_message,
            chat_id,
            "No known chats found yet. The bot records DMs, groups, and channels after it receives updates from them.",
            reply_to_message_id=message.id,
            retries=1,
            suppress=(errors.RPCError,),
            write=True,
        )

    status_message = await telegram_call(
        client.send_message,
        chat_id,
        f"Starting broadcast to `{len(chats)}` known active chats...",
        reply_to_message_id=message.id,
        default=None,
        retries=1,
        suppress=(errors.RPCError,),
        write=True,
    )

    if status_message is None:
        return

    source_chat_id = source_message.chat.id if source_message else None
    source_message_id = source_message.id if source_message else None
    asyncio.create_task(
        run_broadcast_job(
            client,
            status_message,
            chats,
            payload,
            source_chat_id=source_chat_id,
            source_message_id=source_message_id,
        )
    )


@app.on_message(filters.command("start"))
@guarded_handler("start")
async def start_handler(client: Client, message):
    chat_id = message.chat.id
    if message.chat and message.chat.type == enums.ChatType.PRIVATE:
        await mark_user_started(message.chat)

    bot = await client.get_me()
    add_url = f"https://t.me/{bot.username}?startgroup=true"
    text = (
        "**âœ¨ Welcome to Bio Analyser Bot! âœ¨**\n\n"
        "ðŸ›¡ï¸ I help protect your groups from users with links in their bio.\n\n"
        "**ðŸ”¹ Key Features:**\n"
        "   â€¢ Automatic URL detection in user bios\n"
        "   â€¢ Customizable warning limit\n"
        "   â€¢ Auto-mute or ban when limit is reached\n"
        "   â€¢ Whitelist management for trusted users\n\n"
        "**Use /help to see all available commands.**"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("âž• Add Me to Your Group", url=add_url)],
        [
            InlineKeyboardButton("ðŸ› ï¸ Support", url="https://t.me/VivaanSupport"),
            InlineKeyboardButton("ðŸ—‘ï¸ Close", callback_data="close")
        ]
    ])
    await client.send_message(chat_id, text, reply_markup=kb)
    
@app.on_message(filters.command("help"))
@guarded_handler("help")
async def help_handler(client: Client, message):
    chat_id = message.chat.id
    help_text = (
        "**ðŸ› ï¸ Bot Commands & Usage**\n\n"
        "`/config` â€“ set warn-limit & punishment mode\n"
        "`/free` â€“ whitelist a user (reply or user/id)\n"
        "`/unfree` â€“ remove from whitelist\n"
        "`/freelist` â€“ list all whitelisted users\n\n"
        "**When someone with a URL in their bio posts, I'll:**\n"
        " 1. âš ï¸ Warn them\n"
        " 2. ðŸ”‡ Mute if they exceed limit\n"
        " 3. ðŸ”¨ Ban if set to ban\n\n"
        "**Use the inline buttons on warnings to cancel or whitelist**"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("ðŸ—‘ï¸ Close", callback_data="close")]
    ])
    await client.send_message(chat_id, help_text, reply_markup=kb)

@app.on_message(filters.group & filters.command("config"))
@guarded_handler("config")
async def configure(client: Client, message):
    chat_id = message.chat.id
    if not message.from_user:
        return
    user_id = message.from_user.id
    if not await is_admin(client, chat_id, user_id):
        return

    mode, limit, penalty = await get_config(chat_id)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Warn", callback_data="warn")],
        [
            InlineKeyboardButton("Mute âœ…" if penalty == "mute" else "Mute", callback_data="mute"),
            InlineKeyboardButton("Ban âœ…" if penalty == "ban" else "Ban", callback_data="ban")
        ],
        [InlineKeyboardButton("Close", callback_data="close")]
    ])
    await client.send_message(
        chat_id,
        "**Choose penalty for users with links in bio:**",
        reply_markup=keyboard
    )
    await message.delete()

@app.on_message(filters.group & filters.command("free"))
@guarded_handler("free")
async def command_free(client: Client, message):
    chat_id = message.chat.id
    if not message.from_user:
        return
    user_id = message.from_user.id
    if not await is_admin(client, chat_id, user_id):
        return

    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
    elif len(message.command) > 1:
        arg = message.command[1]
        try:
            target = await client.get_users(int(arg) if arg.isdigit() else arg)
        except Exception as e:
            return await client.send_message(chat_id, "âŒ **User not found or invalid ID.**")
    else:
        return await client.send_message(chat_id, "**Reply or use /free user or id to whitelist someone.**")

    await add_whitelist(chat_id, target.id)
    await reset_warnings(chat_id, target.id)

    text = f"**âœ… {target.mention} has been added to the whitelist**"
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("ðŸš« Unwhitelist", callback_data=f"unwhitelist_{target.id}"),
            InlineKeyboardButton("ðŸ—‘ï¸ Close", callback_data="close")
        ]
    ])
    await client.send_message(chat_id, text, reply_markup=keyboard)

@app.on_message(filters.group & filters.command("unfree"))
@guarded_handler("unfree")
async def command_unfree(client: Client, message):
    chat_id = message.chat.id
    if not message.from_user:
        return
    user_id = message.from_user.id
    if not await is_admin(client, chat_id, user_id):
        return

    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
    elif len(message.command) > 1:
        arg = message.command[1]
        try:
            target = await client.get_users(int(arg) if arg.isdigit() else arg)
        except Exception as e:
            return await client.send_message(chat_id, "âŒ **User not found or invalid ID.**")
    else:
        return await client.send_message(chat_id, "**Reply or use /unfree user or id to unwhitelist someone.**")

    if await is_whitelisted(chat_id, target.id):
        await remove_whitelist(chat_id, target.id)
        text = f"**ðŸš« {target.mention} has been removed from the whitelist**"
    else:
        text = f"**â„¹ï¸ {target.mention} is not whitelisted.**"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("âœ… Whitelist", callback_data=f"whitelist_{target.id}"),
            InlineKeyboardButton("ðŸ—‘ï¸ Close", callback_data="close")
        ]
    ])
    await client.send_message(chat_id, text, reply_markup=keyboard)

@app.on_message(filters.group & filters.command("freelist"))
@guarded_handler("freelist")
async def command_freelist(client: Client, message):
    chat_id = message.chat.id
    if not message.from_user:
        return
    user_id = message.from_user.id
    if not await is_admin(client, chat_id, user_id):
        return

    ids = await get_whitelist(chat_id)
    if not ids:
        await client.send_message(chat_id, "**âš ï¸ No users are whitelisted in this group.**")
        return

    text = "**ðŸ“‹ Whitelisted Users:**\n\n"
    for i, uid in enumerate(ids, start=1):
        try:
            user = await client.get_users(uid)
            name = f"{user.first_name}{(' ' + user.last_name) if user.last_name else ''}"
            text += f"{i}: {name} [`{uid}`]\n"
        except:
            text += f"{i}: [User not found] [`{uid}`]\n"

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("ðŸ—‘ï¸ Close", callback_data="close")]])
    await client.send_message(chat_id, text, reply_markup=keyboard)

@app.on_callback_query()
@guarded_handler("callback")
async def callback_handler(client: Client, callback_query):
    data = callback_query.data or ""
    if not data:
        return await callback_query.answer()

    if not callback_query.message:
        return await callback_query.answer("This action is no longer available.", show_alert=True)

    chat_id = callback_query.message.chat.id
    user_id = callback_query.from_user.id

    if data == "close" and callback_query.message.chat.type == enums.ChatType.PRIVATE:
        await callback_query.message.delete()
        return await callback_query.answer()

    if not await is_admin(client, chat_id, user_id):
        return await callback_query.answer("âŒ You are not administrator", show_alert=True)

    if data == "close":
        return await callback_query.message.delete()

    if data == "back":
        mode, limit, penalty = await get_config(chat_id)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Warn", callback_data="warn")],
            [
                InlineKeyboardButton("Mute âœ…" if penalty=="mute" else "Mute", callback_data="mute"),
                InlineKeyboardButton("Ban âœ…" if penalty=="ban" else "Ban", callback_data="ban")
            ],
            [InlineKeyboardButton("Close", callback_data="close")]
        ])
        await callback_query.message.edit_text("**Choose penalty for users with links in bio:**", reply_markup=kb)
        return await callback_query.answer()

    if data == "warn":
        _, selected_limit, _ = await get_config(chat_id)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"5 âœ…" if selected_limit==5 else "5", callback_data="warn_5"),
             InlineKeyboardButton(f"10 âœ…" if selected_limit==10 else "10", callback_data="warn_10"),
             InlineKeyboardButton(f"15 âœ…" if selected_limit==15 else "15", callback_data="warn_15")],
            [InlineKeyboardButton("Back", callback_data="back"), InlineKeyboardButton("Close", callback_data="close")]
        ])
        return await callback_query.message.edit_text("**Select number of warns before penalty:**", reply_markup=kb)

    if data in ["mute", "ban"]:
        await update_config(chat_id, penalty=data)
        mode, limit, penalty = await get_config(chat_id)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Warn", callback_data="warn")],
            [
                InlineKeyboardButton("Mute âœ…" if penalty=="mute" else "Mute", callback_data="mute"),
                InlineKeyboardButton("Ban âœ…" if penalty=="ban" else "Ban", callback_data="ban")
            ],
            [InlineKeyboardButton("Close", callback_data="close")]
        ])
        await callback_query.message.edit_text("**Punishment selected:**", reply_markup=kb)
        return await callback_query.answer()

    if data.startswith("warn_"):
        count = int(data.split("_")[1])
        await update_config(chat_id, limit=count)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"5 âœ…" if count==5 else "5", callback_data="warn_5"),
             InlineKeyboardButton(f"10 âœ…" if count==10 else "10", callback_data="warn_10"),
             InlineKeyboardButton(f"15 âœ…" if count==15 else "15", callback_data="warn_15")],
            [InlineKeyboardButton("Back", callback_data="back"), InlineKeyboardButton("Close", callback_data="close")]
        ])
        await callback_query.message.edit_text(f"**Warning limit set to {count}**", reply_markup=kb)
        return await callback_query.answer()

    if data.startswith(("unmute_", "unban_")):
        action, uid = data.split("_")
        target_id = int(uid)
        profile = await get_user_profile(client, target_id)
        name = profile[1] if profile else "User"
        try:
            if action == "unmute":
                async with _telegram_write_semaphore:
                    await client.restrict_chat_member(chat_id, target_id, ChatPermissions(can_send_messages=True))
            else:
                async with _telegram_write_semaphore:
                    await client.unban_chat_member(chat_id, target_id)
            await reset_warnings(chat_id, target_id)
            clear_penalty(chat_id, target_id)
            msg = f"**{name} (`{target_id}`) has been {'unmuted' if action=='unmute' else 'unbanned'}**."

            kb = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("Whitelist âœ…", callback_data=f"whitelist_{target_id}"),
                    InlineKeyboardButton("ðŸ—‘ï¸ Close", callback_data="close")
                ]
            ])
            await callback_query.message.edit_text(msg, reply_markup=kb)
        
        except errors.ChatAdminRequired:
            await callback_query.message.edit_text(f"I don't have permission to {action} users.")
        return await callback_query.answer()

    if data.startswith("cancel_warn_"):
        target_id = int(data.split("_")[-1])
        await reset_warnings(chat_id, target_id)
        clear_penalty(chat_id, target_id)
        profile = await get_user_profile(client, target_id)
        full_name = profile[1] if profile else "User"
        mention = _mention(target_id, full_name)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Whitelistâœ…", callback_data=f"whitelist_{target_id}"),
             InlineKeyboardButton("ðŸ—‘ï¸ Close", callback_data="close")]
        ])
        await callback_query.message.edit_text(f"**âœ… {mention} [`{target_id}`] has no more warnings!**", reply_markup=kb)
        return await callback_query.answer()

    if data.startswith("whitelist_"):
        target_id = int(data.split("_")[1])
        await add_whitelist(chat_id, target_id)
        await reset_warnings(chat_id, target_id)
        clear_penalty(chat_id, target_id)
        profile = await get_user_profile(client, target_id)
        full_name = profile[1] if profile else "User"
        mention = _mention(target_id, full_name)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("ðŸš« Unwhitelist", callback_data=f"unwhitelist_{target_id}"),
             InlineKeyboardButton("ðŸ—‘ï¸ Close", callback_data="close")]
        ])
        await callback_query.message.edit_text(f"**âœ… {mention} [`{target_id}`] has been whitelisted!**", reply_markup=kb)
        return await callback_query.answer()

    if data.startswith("unwhitelist_"):
        target_id = int(data.split("_")[1])
        await remove_whitelist(chat_id, target_id)
        profile = await get_user_profile(client, target_id)
        full_name = profile[1] if profile else "User"
        mention = _mention(target_id, full_name)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Whitelistâœ…", callback_data=f"whitelist_{target_id}"),
             InlineKeyboardButton("ðŸ—‘ï¸ Close", callback_data="close")]
        ])
        await callback_query.message.edit_text(f"**âŒ {mention} [`{target_id}`] has been removed from whitelist.**", reply_markup=kb)
        return await callback_query.answer()

@app.on_message(filters.group)
@guarded_handler("check_bio")
async def check_bio(client: Client, message):
    chat_id = message.chat.id
    if not message.from_user:
        return

    user_id = message.from_user.id
    if is_owner(user_id):
        return

    if await is_admin(client, chat_id, user_id, default_on_error=True) or await is_whitelisted(chat_id, user_id):
        return

    decision = await get_bio_decision(client, user_id)
    if decision is None:
        return

    has_link, _bio, full_name = decision
    mention = _mention(user_id, full_name)

    if has_link:
        if already_penalized(chat_id, user_id):
            await delete_group_message(client, message)
            return

        deleted = await delete_group_message(client, message)
        if not deleted:
            return

        flow_lock = _get_lock(_chat_user_locks, (chat_id, user_id))
        async with flow_lock:
            if already_penalized(chat_id, user_id):
                return

            _, limit, penalty = await get_config(chat_id)
            count = await increment_warning(chat_id, user_id)

            if count >= limit:
                try:
                    applied = await apply_penalty(client, chat_id, user_id, penalty)
                    if applied:
                        mark_penalized(chat_id, user_id, penalty)
                        if penalty == "mute":
                            kb = InlineKeyboardMarkup([[InlineKeyboardButton("Unmute", callback_data=f"unmute_{user_id}")]])
                            text = f"**{mention} has been muted for [Link In Bio].**"
                        else:
                            kb = InlineKeyboardMarkup([[InlineKeyboardButton("Unban", callback_data=f"unban_{user_id}")]])
                            text = f"**{mention} has been banned for [Link In Bio].**"

                        await telegram_call(
                            client.send_message,
                            chat_id,
                            text,
                            reply_markup=kb,
                            retries=1,
                            suppress=(errors.RPCError,),
                            write=True,
                        )
                except errors.ChatAdminRequired:
                    if should_send_warning_notice(chat_id, user_id):
                        await telegram_call(
                            client.send_message,
                            chat_id,
                            f"**I don't have permission to {penalty} users.**",
                            retries=1,
                            suppress=(errors.RPCError,),
                            write=True,
                        )
                return

            if not should_send_warning_notice(chat_id, user_id):
                return

            warning_text = (
                "**Warning Issued**\n\n"
                f"**User:** {mention} `[ {user_id} ]`\n"
                "**Reason:** URL found in bio\n"
                f"**Warning:** {count}/{limit}\n\n"
                "**Notice: Please remove any links from your bio (apne bio se link hatane ka kripa kare).**"
            )
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Cancel Warning", callback_data=f"cancel_warn_{user_id}"),
                 InlineKeyboardButton("Whitelist", callback_data=f"whitelist_{user_id}")],
                [InlineKeyboardButton("Close", callback_data="close")]
            ])
            await telegram_call(
                client.send_message,
                chat_id,
                warning_text,
                reply_markup=keyboard,
                default=None,
                retries=1,
                suppress=(errors.RPCError,),
                write=True,
            )
    else:
        await reset_warnings(chat_id, user_id)
        clear_penalty(chat_id, user_id)



if __name__ == "__main__":
    app.run()
