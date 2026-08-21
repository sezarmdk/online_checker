import asyncio
import json
import os
from datetime import datetime, timezone, timedelta
from aiohttp import web
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import UpdateUserStatus, UserStatusOnline, UserStatusOffline, ReactionEmoji
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.stories import GetPeerStoriesRequest, ReadStoriesRequest, SendReactionRequest
from telethon.utils import get_display_name

API_ID = int(os.environ.get("API_ID", 32261789))
API_HASH = os.environ.get("API_HASH", "06254a37741c127fd669909f57e67168")
SESSION_STRING = os.environ.get("SESSION_STRING")
CHANNEL_ID = -1003669608470
PORT = int(os.environ.get("PORT", 8080))

UZ_TZ = timezone(timedelta(hours=5))
def get_uz_time(): return datetime.now(UZ_TZ)

DB_FILE = 'tracker_clean.json'
START_TIME = get_uz_time()

def load_data():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except: pass
    return {"targets": {}, "story_targets": [], "viewed_stories": {}}

def save_data(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4, ensure_ascii=False)

db = load_data()
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

def format_duration(seconds):
    seconds = int(seconds)
    hours, minutes = seconds // 3600, (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours}s {minutes}d {secs}s"

async def notify(text):
    try: await client.send_message(CHANNEL_ID, text)
    except Exception as e: print(f"Kanalga yuborishda xato: {e}")

async def process_status(uid, status_obj):
    global db
    uid_str = str(uid)
    if uid_str not in db["targets"]: return
    
    now = get_uz_time()
    user = db["targets"][uid_str]
    name = user.get("name", uid_str)

    if isinstance(status_obj, UserStatusOnline):
        if user.get("status") == "online": return
        dur = "Noma'lum"
        if user.get("last_off"):
            try:
                last_off = datetime.strptime(user["last_off"], '%Y-%m-%d %H:%M:%S').replace(tzinfo=UZ_TZ)
                dur = format_duration((now - last_off).total_seconds())
            except: pass
        user.update({"status": "online", "last_on": now.strftime('%Y-%m-%d %H:%M:%S')})
        save_data(db)
        await notify(f"🟢 **Online**\n👤 {name}\n⏰ {now.strftime('%H:%M:%S')}\n💤 Offline davri: {dur}")

    elif isinstance(status_obj, UserStatusOffline):
        if user.get("status") == "offline": return
        dur = "Noma'lum"
        if user.get("last_on"):
            try:
                last_on = datetime.strptime(user["last_on"], '%Y-%m-%d %H:%M:%S').replace(tzinfo=UZ_TZ)
                dur = format_duration((now - last_on).total_seconds())
            except: pass
        user.update({"status": "offline", "last_off": now.strftime('%Y-%m-%d %H:%M:%S')})
        save_data(db)
        await notify(f"🔴 **Offline**\n👤 {name}\n⏰ {now.strftime('%H:%M:%S')}\n⚡️ Online davri: {dur}")

@client.on(events.Raw(UpdateUserStatus))
async def raw_handler(event): await process_status(event.user_id, event.status)

async def polling_checker():
    while True:
        for uid_str in list(db["targets"].keys()):
            try:
                res = await client(GetFullUserRequest(int(uid_str)))
                if res.users and res.users[0].status:
                    await process_status(int(uid_str), res.users[0].status)
            except: pass
            await asyncio.sleep(2)
        await asyncio.sleep(20)

async def check_stories():
    while True:
        try:
            for uid in list(db.get("story_targets", [])):
                try:
                    ent = await client.get_entity(uid)
                    res = await client(GetPeerStoriesRequest(peer=ent))
                    if hasattr(res, 'stories'):
                        for s in res.stories.stories:
                            if s.id not in db.setdefault("viewed_stories", {}).setdefault(str(uid), []):
                                await client(ReadStoriesRequest(peer=ent, max_id=s.id))
                                try: await client(SendReactionRequest(peer=ent, story_id=s.id, reaction=ReactionEmoji(emoticon='❤️')))
                                except: pass
                                db["viewed_stories"][str(uid)].append(s.id)
                                save_data(db)
                                await notify(f"💖 **Story ko'rildi**\n👤 {get_display_name(ent)}\n⏰ {get_uz_time().strftime('%H:%M:%S')}")
                except: pass
                await asyncio.sleep(2)
        except: pass
        await asyncio.sleep(30)

@client.on(events.NewMessage(from_users="me"))
async def commands(event):
    global db
    txt = event.raw_text.split()
    cmd = txt[0] if txt else ""
    arg = txt[1] if len(txt) > 1 else ""

    if cmd == ".stat":
        uptime = format_duration((get_uz_time() - START_TIME).total_seconds())
        await event.edit(f"⚡️ **Status:** Faol\n⏳ **Uptime:** {uptime}\n👥 **Kuzatuv:** {len(db['targets'])} ta")
    
    elif cmd == ".xisobot":
        msg = "📊 **Batafsil Hisobot:**\n\n"
        for k, v in db['targets'].items():
            msg += f"👤 {v.get('name', k)}: **{v.get('status', 'offline').upper()}**\n"
        await event.edit(msg)

    elif cmd == ".kuzatish" and arg:
        try:
            ent = await client.get_entity(arg)
            db["targets"][str(ent.id)] = {"name": get_display_name(ent), "status": "offline"}
            save_data(db)
            await event.edit(f"✅ Kuzatuvga olindi: {get_display_name(ent)}")
        except Exception as e: await event.edit(f"❌ Xato: {e}")

    elif cmd == ".toxtatish" and arg:
        if arg in db["targets"]:
            del db["targets"][arg]
            save_data(db)
            await event.edit("🛑 Kuzatuv to'xtatildi.")

async def run_web():
    app = web.Application()
    app.router.add_get('/', lambda r: web.Response(text="Bot is running"))
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', PORT).start()

async def main():
    await client.start()
    asyncio.create_task(run_web())
    asyncio.create_task(polling_checker())
    asyncio.create_task(check_stories())
    await notify("🚀 **Userbot ishga tushdi!**")

with client:
    client.loop.run_until_complete(main())
    client.run_until_disconnected()
