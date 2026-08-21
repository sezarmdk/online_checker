import asyncio, os, json
from aiohttp import web
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.functions.stories import GetPeerStoriesRequest, ReadStoriesRequest, SendReactionRequest
from telethon.tl.types import UpdateUserStatus, UserStatusOnline, UserStatusOffline, ReactionEmoji
from telethon.utils import get_display_name

# Config
API_ID = int(os.environ.get("API_ID", 32261789))
API_HASH = os.environ.get("API_HASH", "06254a37741c127fd669909f57e67168")
SESSION_STRING = os.environ.get("SESSION_STRING")
PORT = int(os.environ.get("PORT", 8080))

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# Web server Render uchun
async def web_handler(request):
    return web.Response(text="Bot is running and port is open!")

async def run_web_server():
    app = web.Application()
    app.router.add_get('/', web_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    print(f"Web server started on port {PORT}")

# Asosiy bot qismi
async def main():
    await client.start()
    print("Userbot started")
    # Web serverni fon rejimida ishga tushiramiz
    asyncio.create_task(run_web_server())
    # Userbot ishlashda davom etadi
    await client.run_until_disconnected()

client.loop.run_until_complete(main())
