import asyncio
import json
import os
from datetime import datetime, timedelta
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import (
    UpdateUserStatus, UserStatusOnline, UserStatusOffline,
    ReactionEmoji
)
from telethon.tl.functions.stories import (
    GetPeerStoriesRequest, ReadStoriesRequest, SendReactionRequest
)
from telethon.utils import get_display_name

API_ID = int(os.environ.get("API_ID", 32261789))
API_HASH = os.environ.get("API_HASH", "06254a37741c127fd669909f57e67168")
SESSION_STRING = os.environ.get("SESSION_STRING")
CHANNEL_INVITE_LINK = os.environ.get("CHANNEL_LINK", "https://t.me/+vQr-UkBn9GdlNmQy")

DB_FILE = 'tracker_clean.json'
START_TIME = datetime.now()

def load_data():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "targets": {
            "8281020365": {"name": "User", "status": "offline", "last_on": None, "last_off": None, "total_on": 0, "sessions": 0},
            "8750101205": {"name": "User", "status": "offline", "last_on": None, "last_off": None, "total_on": 0, "sessions": 0}
        },
        "story_targets": [8281020365, 8750101205],
        "viewed_stories": {}
    }

def save_data(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

db = load_data()
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

channel_entity = None
target_entities = {}

def format_duration(seconds):
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    parts = []
    if hours > 0:
        parts.append(f"{hours} soat")
    if minutes > 0:
        parts.append(f"{minutes} daqiqa")
    if secs > 0 or not parts:
        parts.append(f"{secs} soniya")
    return " ".join(parts)

@client.on(events.Raw(UpdateUserStatus))
async def status_handler(event):
    global channel_entity, target_entities, db
    
    uid_str = str(event.user_id)
    if uid_str not in db["targets"]:
        return

    now = datetime.now()
    clock_str = now.strftime('%H:%M:%S')
    time_full = now.strftime('%Y-%m-%d %H:%M:%S')
    user = db["targets"][uid_str]
    target_ent = target_entities.get(event.user_id)
    name = get_display_name(target_ent) if target_ent else user.get("name", uid_str)
    user["name"] = name

    if isinstance(event.status, UserStatusOnline):
        if user.get("status") == "online":
            return
        
        offline_dur_str = "Noma'lum"
        if user.get("last_off"):
            try:
                last_off_time = datetime.strptime(user["last_off"], '%Y-%m-%d %H:%M:%S')
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
        if channel_entity:
            try:
                await client.send_message(channel_entity, text)
            except Exception as e:
                print(f"Xatolik: {e}")

    elif isinstance(event.status, UserStatusOffline):
        if user.get("status") == "offline":
            return
        
        online_dur_str = "Noma'lum"
        if user.get("last_on"):
            try:
                last_on_time = datetime.strptime(user["last_on"], '%Y-%m-%d %H:%M:%S')
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
        if channel_entity:
            try:
                await client.send_message(channel_entity, text)
            except Exception as e:
                print(f"Xatolik: {e}")

async def check_stories_loop():
    global db, channel_entity
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
                    result = await client(GetPeerStoriesRequest(peer=ent))
                    
                    if hasattr(result, 'stories') and hasattr(result.stories, 'stories'):
                        for story in result.stories.stories:
                            story_id = story.id
                            if story_id not in viewed[uid_str]:
                                await client(ReadStoriesRequest(peer=ent, max_id=story_id))
                                try:
                                    await client(SendReactionRequest(
                                        peer=ent,
                                        story_id=story_id,
                                        reaction=ReactionEmoji(emoticon='❤️')
                                    ))
                                except Exception:
                                    pass

                                viewed[uid_str].append(story_id)
                                save_data(db)

                                name = get_display_name(ent)
                                now_str = datetime.now().strftime('%H:%M:%S')
                                log_msg = (
                                    f"💖 **Yangi Story ko'rildi va Like bosildi!**\n\n"
                                    f"👤 **Foydalanuvchi:** {name}\n"
                                    f"🆔 **ID:** `{uid}`\n"
                                    f"📸 **Story ID:** `{story_id}`\n"
                                    f"⏰ **Vaqt:** `{now_str}`"
                                )
                                if channel_entity:
                                    await client.send_message(channel_entity, log_msg)
                except Exception:
                    pass
                await asyncio.sleep(2)
        except Exception as e:
            print(f"Story xatosi: {e}")
        await asyncio.sleep(20)

@client.on(events.NewMessage(from_users="me"))
async def commands(event):
    global channel_entity, target_entities, db
    raw = event.raw_text.strip()
    parts = raw.split()
    cmd = parts[0] if parts else ""
    arg = parts[1] if len(parts) > 1 else ""

    if cmd == ".stat":
        uptime = format_duration((datetime.now() - START_TIME).total_seconds())
        msg = (
            f"⚡️ **Render Tracker Status**\n\n"
            f"🟢 **Holat:** 24/7 Faol\n"
            f"⏳ **Uptime:** `{uptime}`\n"
            f"👥 **Online kuzatuv:** `{len(db['targets'])} ta`\n"
            f"📸 **Story kuzatuv:** `{len(db.get('story_targets', []))} ta`"
        )
        await event.edit(msg)

    elif cmd == ".kuzatish" and arg:
        try:
            target_id = int(arg) if arg.lstrip('-').isdigit() else arg
            ent = await client.get_entity(target_id)
            uid_str = str(ent.id)
            name = get_display_name(ent)
            target_entities[ent.id] = ent
            db["targets"][uid_str] = {
                "name": name,
                "status": "offline",
                "last_on": None,
                "last_off": None,
                "total_on": 0,
                "sessions": 0
            }
            save_data(db)
            await event.edit(f"✅ **Online kuzatuvga olindi:**\n👤 {name} (`{uid_str}`)")
        except Exception as e:
            await event.edit(f"❌ Xatolik: {e}")

    elif cmd == ".toxtatish" and arg:
        if arg in db["targets"]:
            name = db["targets"][arg].get("name", arg)
            del db["targets"][arg]
            if arg.isdigit() and int(arg) in target_entities:
                del target_entities[int(arg)]
            save_data(db)
            await event.edit(f"🛑 **Kuzatuv to'xtatildi:** {name}")
        else:
            await event.edit("⚠️ Bunday ID topilmadi.")

    elif cmd == ".story" and arg:
        try:
            target_id = int(arg) if arg.lstrip('-').isdigit() else arg
            ent = await client.get_entity(target_id)
            targets = db.setdefault("story_targets", [])
            if ent.id not in targets:
                targets.append(ent.id)
                save_data(db)
            name = get_display_name(ent)
            await event.edit(f"📸 **Story kuzatuviga qo'shildi:**\n👤 {name} (`{ent.id}`)")
        except Exception as e:
            await event.edit(f"❌ Xatolik: {e}")

async def send_daily_report():
    global channel_entity, db
    if not channel_entity or not db["targets"]:
        return

    today_str = datetime.now().strftime('%d.%m.%Y')
    report = f"📊 **KUNLIK HISOBOT ({today_str})**\n━━━━━━━━━━━━━━━━━━━━\n\n"

    for uid, data in db["targets"].items():
        name = data.get("name", uid)
        online_str = format_duration(data.get("total_on", 0))
        sessions = data.get("sessions", 0)

        report += (
            f"👤 **{name}** (`{uid}`):\n"
            f"⏱ **Tarmoqda bo'lgan vaqt:** `{online_str}`\n"
            f"🔄 **Kirib-chiqishlar:** `{sessions} marta`\n"
            f"────────────────────\n"
        )
        data["total_on"] = 0
        data["sessions"] = 0

    save_data(db)
    await client.send_message(channel_entity, report)

async def schedule_daily():
    while True:
        now = datetime.now()
        target = now.replace(hour=23, minute=59, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        wait_seconds = (target - now).total_seconds()
        await asyncio.sleep(wait_seconds)
        await send_daily_report()
        await asyncio.sleep(60)

async def main():
    global channel_entity, target_entities, db
    await client.start()
    print("Render: Akkauntga muvaffaqiyatli ulandi.")

    try:
        channel_entity = await client.get_entity(CHANNEL_INVITE_LINK)
    except Exception as e:
        print(f"Kanal yuklanmadi: {e}")

    for uid_str in list(db["targets"].keys()):
        try:
            uid = int(uid_str) if uid_str.isdigit() else uid_str
            ent = await client.get_entity(uid)
            target_entities[ent.id] = ent
            db["targets"][uid_str]["name"] = get_display_name(ent)
        except Exception as e:
            print(f"ID {uid_str} yuklanmadi: {e}")

    save_data(db)
    asyncio.create_task(schedule_daily())
    asyncio.create_task(check_stories_loop())

with client:
    client.loop.run_until_complete(main())
    client.run_until_disconnected()
