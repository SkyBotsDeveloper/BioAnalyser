<h1 align="center">Bio Analyser Telegram Bot</h1>

<p align="center">
  <a href="https://github.com/SkyBotsDeveloper/BioAnalyser/stargazers"><img src="https://img.shields.io/github/stars/SkyBotsDeveloper/BioAnalyser?color=blue&style=flat" alt="GitHub Repo stars"></a>
  <a href="https://github.com/SkyBotsDeveloper/BioAnalyser/issues"><img src="https://img.shields.io/github/issues/SkyBotsDeveloper/BioAnalyser" alt="GitHub issues"></a>
  <a href="https://github.com/SkyBotsDeveloper/BioAnalyser/pulls"><img src="https://img.shields.io/github/issues-pr/SkyBotsDeveloper/BioAnalyser" alt="GitHub pull requests"></a>
  <a href="https://github.com/SkyBotsDeveloper/BioAnalyser/graphs/contributors"><img src="https://img.shields.io/github/contributors/SkyBotsDeveloper/BioAnalyser?style=flat" alt="GitHub contributors"></a>
  <a href="https://github.com/SkyBotsDeveloper/BioAnalyser/network/members"><img src="https://img.shields.io/github/forks/SkyBotsDeveloper/BioAnalyser?style=flat" alt="GitHub forks"></a>
</p>

<p align="center">
  <em>Bio Analyser is a Telegram bot Script that automatically monitors user bios in group chats for links. If a link is found in a user's bio, the bot can warn the user, mute them, or ban them based on configurable settings. This bot helps maintain a clean and safe environment in your Telegram group chats.
</em>
</p>
<hr>

## Features

- Automatically checks user bios for links when they send a message in the group.
- Configurable **warnings**, **mutes**, and **bans** for users with links in their bios.
- **Whitelist** & **Unwhitelist** trusted members  
- **Cancel Warning** reset a user’s warnings  
- **Admin-only controls** with interactive inline keyboards

## 🎮 Demo Bot

Try it live: [@BioAnalyserBot](https://t.me/BioAnalyserBot)

## Requirements

Before you begin, ensure you have met the following requirements:

- Python 3.8 or higher

## Installation

```bash
git clone https://github.com/SkyBotsDeveloper/BioAnalyser
cd BioAnalyser
pip install -r requirements.txt

```

## Configuration

1. Open the `config.py` file in your favorite text editor.  
2. Replace the placeholders for `API_ID`, `API_HASH`, `BOT_TOKEN`, and `MONGO_URI` with your actual values:  
   - **`API_ID`**: Your API ID from [my.telegram.org](https://my.telegram.org).  
   - **`API_HASH`**: Your API Hash from [my.telegram.org](https://my.telegram.org).  
   - **`BOT_TOKEN`**: The token you obtained from [@BotFather](https://t.me/BotFather).  
   - **`MONGO_URI`**: Your MongoDB connection string (e.g., from [MongoDB Atlas](https://www.mongodb.com/cloud/atlas)).  

## Deploy the Bot

```sh
python bio.py
```

## Usage

1. Add the bot to your group.  
2. Grant the bot **Admin** rights (delete & restrict).  
3. In-chat commands (admins only):  
   - `/config` → choose “Warn”, “Mute”, or “Ban” and set warn count  
   - `/free [reply|id]` → whitelist a user  
   - `/unfree [reply|id]` → remove from whitelist  
   - `/freelist` → view all whitelisted users  
4. **Auto-scan:** When a non-whitelisted user posts, their bio is checked—warn/mute/ban applies.  


✨ **Note**: Fork this repo, & Star ☀️ the repo if you liked it. and Share this repo with Proper Credit

## Author

- Name: Elite Sid
- Telegram: [@EliteSid](https://t.me/EliteSid)

Feel free to reach out if you have any questions or feedback.
