import asyncio, os, json
from aiohttp import web
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# Environment variable'lardan o'qish (Render panelidan oladi)
API_ID = int(os.environ.get("API_ID", 32261789))
API_HASH = os.environ.get("API_HASH", "06254a37741c127fd669909f57e67168")
SESSION_STRING = os.environ.get("SESSION_STRING")
PORT = int(os.environ.get("PORT", 8080))

# Mijozni ishga tushirish
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# Render uchun "soxta" veb-server (Buni o'chirmang!)
async def handle_ping(request):
    return web.Response(text="Bot is active")

async def run_web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    print(f"Web server started on port {PORT}")

# .stat buyrug'i uchun handler
@client.on(events.NewMessage(from_users="me", pattern=r"\.stat"))
async def stat_handler(event):
    await event.edit("✅ **Bot ishlamoqda!**\n\n🟢 *Holat: 24/7 (Render)*")

async def main():
    # Veb-serverni ishga tushirish
    asyncio.create_task(run_web_server())
    
    # Botga ulanish
    await client.start()
    print("Userbot muvaffaqiyatli ulandi!")
    await client.run_until_disconnected()

if __name__ == "__main__":
    client.loop.run_until_complete(main())
