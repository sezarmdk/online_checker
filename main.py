import asyncio
import json
import os
from datetime import datetime, timezone, timedelta
from aiohttp import web
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import (
    UpdateUserStatus, UserStatusOnline, UserStatusOffline,
    ReactionEmoji
)
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.stories import (
    GetPeerStoriesRequest, ReadStoriesRequest, SendReactionRequest
)
from telethon.utils import get_display_name

API_ID = int(os.environ.get("API_ID", 32261789))
API_HASH = os.environ.get("API_HASH", "06254a37741c127fd669909f57e67168")
SESSION_STRING = os.environ.get("SESSION_STRING")
CHANNEL_ID = -1003669608470
PORT = int(os.environ.get("PORT", 8080))

UZ_TZ = timezone(timedelta(hours=5))

def get_uz_time():
    return datetime.now(UZ_TZ)

DB_FILE = 'tracker_clean.json'
START_TIME = get_uz_time()

def load_data():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "targets": {
            "8281020365": {"name": "Target 1", "status": "offline", "last_on": None, "last_off": None, "total_on": 0, "sessions": 0},
            "8750101205": {"name": "Target 2", "status": "offline", "last_on": None, "last_off": None, "total_on": 0, "sessions": 0}
        },
        "story_targets": [8281020365, 8750101205],
        "viewed_stories": {}
    }

def save_data(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

db = load_data()
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

def format_duration(seconds):
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    parts = []
    if hours > 0: parts.append(f"{hours} soat")
    if minutes > 0: parts.append(f"{minutes} daqiqa")
    if secs > 0 or not parts: parts.append(f"{secs} soniya")
    return " ".join(parts)

async def notify(text):
    try:
        await client.send_message(CHANNEL_ID, text)
    except Exception as e:
        print(f"[XATOLIK kanalga yuborishda]: {e}")

async def process_status(uid, status_obj):
    global db
    uid_str = str(uid)
    if uid_str not in db["targets"]:
        return

    now = get_uz_time()
    clock_str = now.strftime('%H:%M:%S')
    time_full = now.strftime('%Y-%m-%d %H:%M:%S')
    user = db["targets"][uid_str]
    name = user.get("name", uid_str)

    if isinstance(status_obj, UserStatusOnline):
        if user.get("status") == "online":
            return
        
        offline_dur_str = "Noma'lum"
        if user.get("last_off"):
            try:
                last_off_time = datetime.strptime(user["last_off"], '%Y-%m-%d %H:%M:%S').replace(tzinfo=UZ_TZ)
                diff = (now - last_off_time).total_seconds()
                offline_dur_str = format_duration(diff)
            except Exception:
                pass

        user["status"] = "online"
        user["last_on"] = time_full
        user["sessions"] = user.get("sessions", 0) + 1
        save_data(db)

        text = (
            f"🟢 **Online bo'ldi**\n\n"
            f"👤 **Foydalanuvchi:** {name}\n"
            f"🆔 **ID:** `{uid_str}`\n"
            f"⏰ **Vaqt:** `{clock_str}`\n"
            f"💤 **Offline turgan vaqti:** `{offline_dur_str}`"
        )
        await notify(text)

    elif isinstance(status_obj, UserStatusOffline):
        if user.get("status") == "offline":
            return
        
        online_dur_str = "Noma'lum"
        if user.get("last_on"):
            try:
                last_on_time = datetime.strptime(user["last_on"], '%Y-%m-%d %H:%M:%S').replace(tzinfo=UZ_TZ)
                diff = (now - last_on_time).total_seconds()
                user["total_on"] = user.get("total_on", 0) + diff
                online_dur_str = format_duration(diff)
            except Exception:
                pass

        user["status"] = "offline"
        user["last_off"] = time_full
        save_data(db)

        text = (
            f"🔴 **Offline bo'ldi**\n\n"
            f"👤 **Foydalanuvchi:** {name}\n"
            f"🆔 **ID:** `{uid_str}`\n"
            f"⏰ **Vaqt:** `{clock_str}`\n"
            f"⚡️ **Online bo'lgan vaqti:** `{online_dur_str}`"
        )
        await notify(text)

@client.on(events.Raw(UpdateUserStatus))
async def raw_handler(event):
    await process_status(event.user_id, event.status)

async def polling_checker():
    while True:
        for uid_str in list(db["targets"].keys()):
            try:
                uid = int(uid_str) if uid_str.isdigit() else uid_str
                res = await client(GetFullUserRequest(uid))
                user_obj = res.users[0] if res.users else None
                if user_obj:
                    db["targets"][uid_str]["name"] = get_display_name(user_obj)
                    if user_obj.status:
                        await process_status(user_obj.id, user_obj.status)
            except Exception:
                pass
            await asyncio.sleep(2)
        await asyncio.sleep(8)

async def check_stories():
    while True:
        try:
            story_targets = list(db.get("story_targets", []))
            viewed = db.setdefault("viewed_stories", {})

            for uid in story_targets:
                try:
                    uid_str = str(uid)
                    if uid_str not in viewed:
                        viewed[uid_str] = []

                    ent = await client.get_entity(uid)
                    res = await client(GetPeerStoriesRequest(peer=ent))
                    if hasattr(res, 'stories') and hasattr(res.stories, 'stories'):
                        for s in res.stories.stories:
                            if s.id not in viewed[uid_str]:
                                await client(ReadStoriesRequest(peer=ent, max_id=s.id))
                                try:
                                    await client(SendReactionRequest(peer=ent, story_id=s.id, reaction=ReactionEmoji(emoticon='❤️')))
                                except Exception:
                                    pass
                                viewed[uid_str].append(s.id)
                                save_data(db)
                                now_str = get_uz_time().strftime('%H:%M:%S')
                                await notify(f"💖 **Story ko'rildi va Like bosildi!**\n\n👤 **Foydalanuvchi:** {get_display_name(ent)}\n🆔 **ID:** `{uid}`\n📸 **Story ID:** `{s.id}`\n⏰ **Vaqt:** `{now_str}`")
                except Exception:
                    pass
                await asyncio.sleep(2)
        except Exception:
            pass
        await asyncio.sleep(15)

@client.on(events.NewMessage(from_users="me"))
async def commands(event):
    global db
    txt = event.raw_text.strip()
    parts = txt.split()
    cmd = parts[0] if parts else ""
    arg = parts[1] if len(parts) > 1 else ""

    if cmd == ".stat":
        uptime = format_duration((get_uz_time() - START_TIME).total_seconds())
        targets_txt = "\n".join([f"• {v.get('name', k)} (`{k}`): **{v.get('status', 'offline')}**" for k, v in db['targets'].items()])
        msg = (
            f"⚡️ **Status:** Faol 24/7 (UZ Time)\n"
            f"⏳ **Uptime:** `{uptime}`\n\n"
            f"👥 **Kuzatuvdagilar:**\n{targets_txt}"
        )
        await event.edit(msg)

    elif cmd == ".xisobot":
        msg = "📊 **Batafsil Hisobot:**\n\n"
        for k, v in db['targets'].items():
            name = v.get('name', k)
            st = v.get('status', 'offline').upper()
            l_on = v.get('last_on', 'Noma\'lum')
            l_off = v.get('last_off', 'Noma\'lum')
            msg += f"👤 **{name}** (`{k}`)\nHolat: **{st}**\nOxirgi online: `{l_on}`\nOxirgi offline: `{l_off}`\n\n"
        await event.edit(msg)

    elif cmd == ".kuzatish" and arg:
        try:
            target_id = int(arg) if arg.lstrip('-').isdigit() else arg
            ent = await client.get_entity(target_id)
            name = get_display_name(ent)
            db["targets"][str(ent.id)] = {"name": name, "status": "offline", "last_on": None, "last_off": None, "total_on": 0, "sessions": 0}
            save_data(db)
            await event.edit(f"✅ Kuzatuvga olindi: {name} (`{ent.id}`)")
        except Exception as e:
            await event.edit(f"❌ Xato: {e}")

    elif cmd == ".toxtatish" and arg:
        if arg in db["targets"]:
            name = db["targets"][arg].get("name", arg)
            del db["targets"][arg]
            save_data(db)
            await event.edit(f"🛑 Kuzatuv to'xtatildi: {name}")
        else:
            await event.edit("⚠️ Bunday ID topilmadi.")

    elif cmd == ".story" and arg:
        try:
            target_id = int(arg) if arg.lstrip('-').isdigit() else arg
            ent = await client.get_entity(target_id)
            if ent.id not in db.setdefault("story_targets", []):
                db["story_targets"].append(ent.id)
                save_data(db)
            await event.edit(f"📸 Story kuzatuviga olindi: {get_display_name(ent)}")
        except Exception as e:
            await event.edit(f"❌ Xato: {e}")

async def handle_ping(request):
    return web.Response(text="Bot is running")

async def run_web():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()

async def main():
    await client.start()
    asyncio.create_task(run_web())
    asyncio.create_task(polling_checker())
    asyncio.create_task(check_stories())

with client:
    client.loop.run_until_complete(main())
    client.run_until_disconnected()
