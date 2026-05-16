from telethon import TelegramClient, events, types, utils
from telethon.sessions import StringSession
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.phone import DiscardCallRequest
from telethon.tl.types import PhoneCallDiscardReasonBusy, InputPhoneCall
import asyncio
import time
import os
import google.generativeai as genai
from gtts import gTTS
import PIL.Image
import yt_dlp
from flask import Flask
from threading import Thread

# --- RENDER UCHUN FLASK SERVER ---
app = Flask('')
@app.route('/')
def home(): return "Jarvis is Running 24/7!"
def run_flask(): app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- SOZLAMALAR ---
api_id = 32894755
api_hash = '67f6c4bfe4148ee90c1f54376a4da248'
# DIQQAT: Xavfsizlik uchun API KEY endi faqat Environment Variables orqali olinadi
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
SESSION_STRING = os.environ.get("SESSION_STRING")

if not GEMINI_API_KEY:
    print("❌ XATO: GEMINI_API_KEY topilmadi! Renderda Environment Variable o'rnating.")
else:
    genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel('gemini-3.1-flash-lite')

if SESSION_STRING:
    client = TelegramClient(StringSession(SESSION_STRING), api_id, api_hash)
else:
    client = TelegramClient('jarvis_session', api_id, api_hash)

# Global holatlar
IS_AFK = False
AFK_REASON = "Hozir bandman."
AI_ENABLED = True
GROUPS_ENABLED = False
VOICE_REPLY = False
ORIGINAL_BIO = ""
msg_cache = {}
user_locks = {}

# --- YORDAMCHI FUNKSIYALAR ---
async def send_as_voice(chat_id, text):
    try:
        filename = f"voice_{int(time.time())}.mp3"
        tts = gTTS(text=text, lang='tr')
        tts.save(filename)
        await client.send_file(chat_id, filename, voice_note=True)
        if os.path.exists(filename): os.remove(filename)
    except Exception as e: print(f"❌ Ovoz xatosi: {e}")

# --- BUYRUQLAR ---
@client.on(events.NewMessage(pattern=r'\.groups (on|off)', outgoing=True))
async def groups_toggle(event):
    global GROUPS_ENABLED
    GROUPS_ENABLED = (event.pattern_match.group(1) == "on")
    await event.edit(f"**Guruhlarda AI javob berish:** `{'Yoqildi' if GROUPS_ENABLED else 'O\'chirildi'}`")

@client.on(events.NewMessage(pattern=r'\.dl (.*)', outgoing=True))
async def download_handler(event):
    url = event.pattern_match.group(1)
    await event.edit("`PRO: Yuklanmoqda...` 📥")
    unique_name = f"dl_{int(time.time())}"
    ydl_opts = {'format': 'best', 'outtmpl': f'{unique_name}.%(ext)s', 'max_filesize': 50*1024*1024, 'quiet': True, 'noplaylist': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            await client.send_file(event.chat_id, filename, caption=f"🎬 **Downloader**\n🔗 {url}")
            if os.path.exists(filename): os.remove(filename)
            await event.delete()
    except Exception as e: await event.edit(f"❌ Xato: {e}")

@client.on(events.NewMessage(pattern=r'\.ocr', outgoing=True))
async def ocr_handler(event):
    if not event.is_reply: return await event.edit("`Rasmga reply qiling!`")
    reply = await event.get_reply_message()
    if not reply.photo: return await event.edit("`Bu rasm emas!`")
    await event.edit("`O'qilmoqda...` 🔍")
    path = await reply.download_media()
    try:
        with PIL.Image.open(path) as img:
            img.load()
            response = model.generate_content(["Rasmdagi matnlarni ko'chirib ber.", img])
            await event.edit(f"📝 **Matn:**\n\n{response.text}")
    except Exception as e: await event.edit(f"❌ Xatolik: {e}")
    if os.path.exists(path): os.remove(path)

@client.on(events.NewMessage(pattern=r'\.summary ?(\d+)?', outgoing=True))
async def summary_handler(event):
    lim = int(event.pattern_match.group(1) or 50)
    await event.edit(f"`{lim} xabar tahlili...` 📑")
    msgs = []
    async for m in client.iter_messages(event.chat_id, limit=lim):
        if m.text:
            s = await m.get_sender()
            name = utils.get_display_name(s) if s else "Noma'lum"
            msgs.append(f"{name}: {m.text}")
    if not msgs: return await event.edit("`Xabarlar yo'q.`")
    res = model.generate_content(f"Xulosa qil:\n\n" + "\n".join(msgs[::-1]))
    await event.edit(f"📑 **PRO Xulosa:**\n\n{res.text}")

@client.on(events.Raw(types.UpdatePhoneCall))
async def call_handler(event):
    global IS_AFK
    if isinstance(event.phone_call, types.PhoneCallRequested) and IS_AFK:
        try:
            await client(DiscardCallRequest(peer=InputPhoneCall(id=event.phone_call.id, access_hash=event.phone_call.access_hash), reason=PhoneCallDiscardReasonBusy(), duration=0))
            await client.send_message(event.phone_call.participant_id, "🚫 **Bandman.**")
        except: pass

@client.on(events.MessageDeleted)
async def anti_delete_handler(event):
    for mid in event.deleted_ids:
        if mid in msg_cache:
            m = msg_cache[mid]
            await client.send_message("me", f"🗑 **O'chirilgan:**\n👤 **Kimdan:** {m['sender']}\n💬 **Xabar:** {m['text'] or '[Media]'}")
            if m['media']: await client.send_file("me", m['media'])
            await asyncio.sleep(0.5)

@client.on(events.NewMessage(pattern=r'\.afk ?(.*)', outgoing=True))
async def afk_handler(event):
    global IS_AFK, ORIGINAL_BIO
    if IS_AFK: return await event.edit("`Siz allaqachon AFK holatidasiz.`")
    try:
        full = await client(GetFullUserRequest('me'))
        ORIGINAL_BIO = full.full_user.about or ""
        await client(UpdateProfileRequest(about="💤 AFK | Jarvis Pro Mode"))
    except Exception as e: print(f"Bio xatosi: {e}")
    IS_AFK = True
    await event.edit(f"**AFK PRO Yoqildi!** 💤")

@client.on(events.NewMessage(pattern=r'\.unafk', outgoing=True))
async def unafk_handler(event):
    global IS_AFK
    if not IS_AFK: return await event.edit("`Siz AFK emassiz.`")
    IS_AFK = False
    try: await client(UpdateProfileRequest(about=ORIGINAL_BIO))
    except: pass
    await event.edit("**AFK rejimi o'chirildi!** ✅")

@client.on(events.NewMessage(pattern=r'\.status', outgoing=True))
async def status_handler(event):
    status = f"🤖 **Jarvis Status:**\n\n"
    status += f"💤 **AFK:** `{'Yoqilgan' if IS_AFK else 'O\'chirilgan'}`\n"
    status += f"🧠 **AI:** `{'Yoqilgan' if AI_ENABLED else 'O\'chirilgan'}`\n"
    status += f"👥 **Guruhlar:** `{'Yoqilgan' if GROUPS_ENABLED else 'O\'chirilgan'}`"
    await event.edit(status)

@client.on(events.NewMessage(outgoing=True))
async def back_handler(event):
    global IS_AFK
    if IS_AFK and event.text and not event.text.startswith('.'):
        IS_AFK = False
        try: await client(UpdateProfileRequest(about=ORIGINAL_BIO))
        except: pass
        await event.respond("**Men qaytdim!** AFK rejimi avtomatik o'chirildi.")

@client.on(events.NewMessage(incoming=True))
async def auto_respond(event):
    global AI_ENABLED, GROUPS_ENABLED, user_locks
    if not event.is_private and not GROUPS_ENABLED: return
    s = await event.get_sender()
    if not s or (hasattr(s, 'bot') and s.bot): return
    name = utils.get_display_name(s); uid = event.sender_id
    msg_cache[event.id] = {'sender': name, 'text': event.text, 'media': event.media}
    if len(msg_cache) > 1000: msg_cache.pop(next(iter(msg_cache)))
    try:
        try: await event.mark_read()
        except: pass
        if IS_AFK and event.is_private:
            await event.reply("Egam hozir bandlar.")
            return
        if AI_ENABLED and GEMINI_API_KEY:
            if uid not in user_locks: user_locks[uid] = asyncio.Lock()
            async with user_locks[uid]:
                print(f"📩 Muloqot: {name}dan")
                prompt = f"Sen akkaunt egasi nomidan gapiryapsan. Senga {name} yozdi: '{event.text or '[Media]'}'. Juda qisqa, insoniy va erkak kishidek javob ber. O'zbek tilida."
                content = [prompt]
                if event.photo:
                    p = await event.download_media(); img = PIL.Image.open(p); img.load(); content.append(img); res = model.generate_content(content); os.remove(p)
                elif event.voice:
                    p = await event.download_media(); up = genai.upload_file(path=p); content.append(up); res = model.generate_content(content); os.remove(p)
                else: res = model.generate_content(content)
                answer = res.text if res.candidates else "..."
                async with client.action(event.chat_id, 'typing'):
                    await asyncio.sleep(1.5); await event.reply(answer)
    except Exception as e: print(f"⚠️ Xato: {e}")

# --- ISHGA TUSHIRISH ---
if __name__ == '__main__':
    Thread(target=run_flask).start()
    print("Jarvis Render Edition ishga tushishga tayyor...")
    client.start()
    client.run_until_disconnected()
