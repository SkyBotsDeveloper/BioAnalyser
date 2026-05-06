<h1 align="center">🛡️ Bio Analyser Telegram Bot</h1>

<p align="center">
  <a href="https://github.com/SkyBotsDeveloper/BioAnalyser/stargazers"><img src="https://img.shields.io/github/stars/SkyBotsDeveloper/BioAnalyser?color=blue&style=flat" alt="GitHub Repo stars"></a>
  <a href="https://github.com/SkyBotsDeveloper/BioAnalyser/issues"><img src="https://img.shields.io/github/issues/SkyBotsDeveloper/BioAnalyser" alt="GitHub issues"></a>
  <a href="https://github.com/SkyBotsDeveloper/BioAnalyser/pulls"><img src="https://img.shields.io/github/issues-pr/SkyBotsDeveloper/BioAnalyser" alt="GitHub pull requests"></a>
  <a href="https://github.com/SkyBotsDeveloper/BioAnalyser/graphs/contributors"><img src="https://img.shields.io/github/contributors/SkyBotsDeveloper/BioAnalyser?style=flat" alt="GitHub contributors"></a>
  <a href="https://github.com/SkyBotsDeveloper/BioAnalyser/network/members"><img src="https://img.shields.io/github/forks/SkyBotsDeveloper/BioAnalyser?style=flat" alt="GitHub forks"></a>
</p>

<p align="center">
  <em>Bio Analyser is a production-ready Telegram bot that automatically monitors user bios in group chats for links. If a link is found in a user's bio, the bot can warn the user, mute them, or ban them based on configurable settings. This bot helps maintain a clean and safe environment in your Telegram group chats.</em>
</p>

<p align="center">
  <strong>⭐ If you find this useful, please star the repo! ⭐</strong>
</p>

<hr>

## ✨ Features

- ✅ Automatically checks user bios for links when they send messages in groups
- ✅ Configurable **warnings**, **mutes**, and **bans** for users with links in their bios
- ✅ **Whitelist & Unwhitelist** trusted members  
- ✅ **Cancel Warning** - reset a user's warnings instantly
- ✅ **Admin-only controls** with interactive inline keyboards
- ✅ **Production-ready** with secure credential management
- ✅ **Error handling** for robust operation

## 🎮 Demo Bot

Try it live: [@BioAnalyserBot](https://t.me/BioAnalyserBot)

## 📋 Requirements

Before you begin, ensure you have met the following requirements:

- **Python 3.8 or higher**
- **MongoDB Atlas account** (free tier available at [mongodb.com/cloud/atlas](https://www.mongodb.com/cloud/atlas))
- **Telegram Bot Token** from [@BotFather](https://t.me/BotFather)
- **Telegram API credentials** from [my.telegram.org](https://my.telegram.org)

## 📦 Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/SkyBotsDeveloper/BioAnalyser
cd BioAnalyser
```

### Step 2: Create Virtual Environment (Recommended)

```bash
# Linux/Mac
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Setup Environment Variables

Create a `.env` file in the project root directory:

```bash
# Linux/Mac
nano .env

# Windows
notepad .env
```

Add the following content (with your actual values):

```
API_ID=your_api_id_here
API_HASH=your_api_hash_here
BOT_TOKEN=your_bot_token_here
MONGO_URI=your_mongodb_connection_string_here
OWNER_ID=your_telegram_user_id
```

**How to get these values:**
- **API_ID & API_HASH**: Visit [my.telegram.org](https://my.telegram.org) → API Development Tools
- **BOT_TOKEN**: Chat with [@BotFather](https://t.me/BotFather) on Telegram → `/start` → Create Bot
- **MONGO_URI**: Create account at [MongoDB Atlas](https://www.mongodb.com/cloud/atlas) → Create Cluster → Copy connection string
- **OWNER_ID**: Your numeric Telegram user ID. For multiple owners, use `OWNER_IDS=111,222,333`

### ⚠️ Important: Keep `.env` Secure

- ❌ **NEVER** commit `.env` to GitHub
- ❌ **NEVER** share your credentials
- ✅ Use `.env` file for local development only
- ✅ For server deployments, set environment variables directly

## 🚀 Running the Bot

```bash
python bio.py
```

If successful, you should see:
```
Bot is running... ✅
```

## VPS Permanent Start

After cloning on Ubuntu/Debian VPS:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -U pip && pip install -r requirements.txt
sudo apt update && sudo apt install tmux -y
tmux
bash start
```

`bash start` installs a `systemd` service named `bioanalyser-bot`, starts the bot now, restarts it if it crashes, and starts it again automatically after VPS reboot.

Useful commands:

```bash
sudo journalctl -u bioanalyser-bot -f
sudo systemctl status bioanalyser-bot
sudo systemctl restart bioanalyser-bot
sudo systemctl stop bioanalyser-bot
```

You can still use `tmux` if you want a terminal session, but `systemd` is what keeps the bot permanent after reboot.

## 🎮 Usage

### Step 1: Add Bot to Group

1. Open your Telegram group
2. Click on group name → "Add members"
3. Search for [@BioAnalyserBot](https://t.me/BioAnalyserBot)
4. Add the bot to your group

### Step 2: Grant Admin Permissions

1. Right-click on the bot in the group
2. Click "Promote to admin"
3. Enable permissions: ✅ Delete messages, ✅ Restrict members

### Step 3: Configure the Bot

**For Group Admins Only:**

- `/config` - Configure warning limit (5, 10, or 15) and punishment (Mute or Ban)
- `/free [reply|id|@username]` - Whitelist a user
- `/unfree [reply|id|@username]` - Remove user from whitelist
- `/freelist` - View all whitelisted users
- `/help` - Show help message

**Owner Only:**

- `/broadcast your message` - Send a text broadcast to every known active DM/group/channel
- Reply to any message with `/broadcast` - Copy that message to every known active DM/group/channel
- `/stats` - Show active groups/channels, known private users, and users who started the bot

The bot records chats after it receives updates from them. If a group/channel/DM has never interacted with this bot version, it will not be in the broadcast list yet.
When Telegram sends a bot removal update, the removed chat is deleted from MongoDB so `/stats` stays current.

### Step 4: How It Works

**When a non-whitelisted user posts in the group:**

1. 🔍 Bot checks their bio for links
2. ⚠️ If link found → Warning issued (count increases)
3. 🔇 If warnings reach limit → User is muted or banned (based on config)
4. ✅ User can be whitelisted to skip checks

**Detected Link Types:**
- @mentions and @usernames
- Telegram links (t.me/*, telegram.me/*, tg.me/*)
- HTTP/HTTPS URLs
- Social media profiles (Instagram, TikTok, Twitter, Facebook, YouTube, LinkedIn)
- URL shorteners (bit.ly, ow.ly, tinyurl.com, goo.gl, etc.)
- Domain names (.com, .org, .net, .io, .shop, etc.)

## ⚙️ Configuration Examples

### Example 1: Strict Mode (Ban on 3 Warnings)

```
/config → Ban → 5 warnings
```

### Example 2: Moderate Mode (Mute on 5 Warnings)

```
/config → Mute → 5 warnings
```

### Example 3: Whitelist Important Users

```
/free @admin_user
/free @support_bot
/free @official_channel_account
```

### Example 4: View Whitelist

```
/freelist
```

## 📂 Project Structure

```
BioAnalyser/
├── bio.py                 # Main bot file
├── config.py              # Configuration with environment variables
├── requirements.txt       # Python dependencies
├── .env.example          # Environment template
├── .gitignore            # Git ignore file
├── helper/
│   └── utils.py          # Helper functions
└── README.md             # This file
```

## 🔐 Security Features

- ✅ **Secure Credentials**: Uses environment variables (`.env` file)
- ✅ **Error Handling**: Graceful handling of invalid user IDs
- ✅ **Admin Verification**: Only admins can configure the bot
- ✅ **Permission Checks**: Validates bot admin rights before actions
- ✅ **Production Ready**: Tested and optimized for stability

## 🐛 Troubleshooting

### Issue: "ModuleNotFoundError: dotenv"

**Solution:**
```bash
pip install python-dotenv
```

### Issue: "Missing environment variables"

**Solution:**
- Ensure `.env` file exists in project root
- Check that all required variables are present (API_ID, API_HASH, BOT_TOKEN, MONGO_URI)
- Verify there are no typos in variable names

### Issue: Bot won't start or stops immediately

**Solution:**
```bash
# Check your .env file
cat .env

# Or verify credentials are correct
# Test MongoDB connection
python -c "from motor.motor_asyncio import AsyncIOMotorClient; print('MongoDB OK')"
```

### Issue: "I don't have permission to restrict users"

**Solution:**
- Make sure bot has admin rights in the group
- Check permissions: Delete messages ✅, Restrict members ✅

### Issue: Bot not detecting links in bios

**Solution:**
- Make sure the bot has access to user profiles
- Check that the user being checked is not an admin
- Verify the user's bio contains an actual link

## 📊 Requirements.txt

Your `requirements.txt` should contain:

```
pyrogram==1.4.16
py-tgcalls==0.9.7
yt-dlp==2023.11.16
httpx==0.25.0
motor==3.3.1
pillow==10.0.1
python-dotenv==1.0.0
```

Install with:
```bash
pip install -r requirements.txt
```

## 🌐 Deployment

### Option 1: Local Machine
```bash
python bio.py
```

### Option 2: VPS/Server
```bash
# Using nohup (runs in background)
nohup python bio.py > bot.log 2>&1 &

# Using screen
screen -S biobot
python bio.py
# Press Ctrl+A then D to detach
```

### Option 3: Docker

Create `Dockerfile`:
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "bio.py"]
```

Build and run:
```bash
docker build -t bioanalyser .
docker run -d --env-file .env bioanalyser
```

## 📝 License

This project is provided as-is for educational and personal use.

## 👤 Author

- **Name:** Elite Sid
- **Telegram:** [@EliteSid](https://t.me/EliteSid)
- **Channel:** [@VivaanUpdates](https://t.me/VivaanUpdates)
- **Support:** [@VivaanSupport](https://t.me/VivaanSupport)

Feel free to reach out if you have any questions, feedback, or suggestions!

## 🙏 Support

If you find this bot helpful:

- ⭐ **Star** this repository
- 📢 **Share** with others (with credit)
- 🐛 **Report bugs** via GitHub Issues
- 💡 **Suggest features** via GitHub Issues
- 👥 **Contribute** via Pull Requests

## 🔄 Recent Updates (v2.0)

- ✅ Fixed critical bug: undefined variable `user_name`
- ✅ Added error handling for invalid user IDs
- ✅ Implemented secure credential management with `.env` file
- ✅ Simplified and improved warning logic
- ✅ Added comprehensive error messages
- ✅ Production-ready code with full documentation
- ✅ Added `.gitignore` to prevent credential exposure

## 📚 Documentation

- **Setup Guide:** See `setup_guide.md`
- **Bug Fixes:** See `bioanalyser_bug_fixes.md`
- **Security:** See `config_security_report.md`

---

<p align="center">
  <strong>Made with ❤️ by <a href="https://t.me/EliteSid">Elite Sid</a></strong>
</p>

<p align="center">
  <strong>⭐ Don't forget to star the repository! ⭐</strong>
</p>
