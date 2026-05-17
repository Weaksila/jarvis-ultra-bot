from telethon import TelegramClient, events, types, utils
from telethon.sessions import StringSession
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.phone import DiscardCallRequest
from telethon.tl.types import PhoneCallDiscardReasonBusy, InputPhoneCall
import asyncio
import time
import os
import datetime
from google import genai
from google.genai import types as gt
from gtts import gTTS
import PIL.Image
import yt_dlp
from flask import Flask
from threading import Thread
from telethon.tl.functions.messages import CheckChatInviteRequest, ImportChatInviteRequest

# --- RENDER UCHUN FLASK SERVER ---
app = Flask('')
@app.route('/')
def home(): return "Jarvis is Running 24/7!"
def run_flask(): app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- SOZLAMALAR ---
api_id = 32894755
api_hash = '67f6c4bfe4148ee90c1f54376a4da248'
SESSION_STRING = os.environ.get("SESSION_STRING")

# --- MULTI-API KEY ROTATION TIZIMI ---
# Renderda GEMINI_API_KEY_1, GEMINI_API_KEY_2, GEMINI_API_KEY_3 ... o'rnating
# Yoki oddiy GEMINI_API_KEY ham ishlaydi
API_KEYS = []
for i in range(1, 11):  # 10 tagacha kalit qo'llab-quvvatlaydi
    key = os.environ.get(f"GEMINI_API_KEY_{i}")
    if key: API_KEYS.append(key)
if not API_KEYS:  # Agar numbered kalitlar yo'q bo'lsa, oddiy kalitni oladi
    single_key = os.environ.get("GEMINI_API_KEY")
    if single_key: API_KEYS.append(single_key)

if not API_KEYS:
    print("❌ XATO: Hech qanday GEMINI_API_KEY topilmadi!")

current_key_index = 0
_genai_client = None

LOG_GROUP = "https://t.me/+q_mKpo69fTZkMzYy"
_log_peer = None

async def send_to_log(msg, file=None, parse_mode=None):
    """Barcha log xabarlarini maxsus guruhga yuboradi"""
    try:
        if file:
            await client.send_file(LOG_GROUP, file, caption=msg, parse_mode=parse_mode)
        else:
            await client.send_message(LOG_GROUP, msg, parse_mode=parse_mode)
    except Exception as e:
        print(f"Log guruhiga yuborishda xato: {e}", flush=True)
        try:
            if file: await client.send_file("me", file, caption=msg, parse_mode=parse_mode)
            else: await client.send_message("me", msg, parse_mode=parse_mode)
        except: pass

def get_client():
    """Joriy API kalit bilan genai client qaytaradi"""
    global current_key_index, _genai_client
    if not API_KEYS: return None
    _genai_client = genai.Client(api_key=API_KEYS[current_key_index])
    return _genai_client

def get_model():
    """Joriy API kalit bilan model qaytaradi (eski kod bilan moslik)"""
    return get_client()

async def generate_with_rotation(content):
    """429 xatolik bo'lsa, keyingi kalitga o'tib qayta urinadi"""
    global current_key_index, api_usage, api_last_reset, _genai_client
    # Kunlik reset tekshiruvi
    if time.time() - api_last_reset >= 86400:
        api_usage = {}
        api_last_reset = time.time()
        print("🔄 API kunlik limit resetlandi!", flush=True)
    
    err = "API kalit topilmadi yoki barcha urinishlar muvaffaqiyatsiz bo'ldi."
    tried_keys = set()
    while len(tried_keys) < len(API_KEYS):
        tried_keys.add(current_key_index)
        try:
            cl = get_client()
            if not cl: return "❌ API kalit topilmadi."
            # Kontentni formatlash
            if isinstance(content, list):
                text_parts = [p for p in content if isinstance(p, str)]
                media_parts = [p for p in content if not isinstance(p, str)]
                prompt_text = " ".join(text_parts)
                if media_parts:
                    res = await cl.aio.models.generate_content(
                        model='gemini-3.1-flash-lite',
                        contents=[prompt_text] + media_parts
                    )
                else:
                    res = await cl.aio.models.generate_content(
                        model='gemini-3.1-flash-lite',
                        contents=prompt_text
                    )
            else:
                res = await cl.aio.models.generate_content(
                    model='gemini-3.1-flash-lite',
                    contents=str(content)
                )
            # Muvaffaqiyatli so'rovni hisoblash
            api_usage[current_key_index] = api_usage.get(current_key_index, 0) + 1
            try:
                return res.text
            except ValueError:
                return "⚠️ Kechirasiz, ushbu xabarga xavfsizlik filtri sababli javob bera olmayman."

        except Exception as e:
            err = str(e)
            if '429' in err or 'quota' in err.lower() or 'limit' in err.lower() or 'resource_exhausted' in err.lower():
                old_index = current_key_index + 1
                current_key_index = (current_key_index + 1) % len(API_KEYS)
                print(f"⚠️ API limit! {old_index}-kalit tugadi, {current_key_index+1}-kalitga o'tildi. Xato: {err}", flush=True)
                await asyncio.sleep(1)
            else:
                # Kutilmagan API xatolarini ham logga chiqarish
                print(f"❌ Kutilmagan API xatosi: {err}", flush=True)
                raise e
    # Barcha kalitlar tugadi — Saved Messages'ga xabar yuborish
    msg = (
        "🚨 JARVIS OGOHLANTIRISH\n\n"
        f"⚠️ Barcha {len(API_KEYS)} ta Gemini API kalit ishlamayapti yoki limitga yetdi!\n\n"
        f"Oxirgi xatolik: {err}\n\n"
        "🔑 Yechim:\n"
        "1. Yangi Google accountdan aistudio.google.com kirib kalit oling.\n"
        "2. Renderda GEMINI_API_KEY_2 ga qo'shing\n"
    )
    try:
        await send_to_log(msg, parse_mode=None)
        print("🚨 Barcha API kalitlar tugadi! Maxsus guruhga xabar yuborildi.", flush=True)
    except Exception as send_err:
        print(f"🚨 Barcha API kalitlar tugadi! Xabar yuborishda xato: {send_err}", flush=True)
    return "⏳ Hozircha javob bera olmayapman. Egam tez orada hal qiladi!"


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
conversation_history = {}  # Har bir foydalanuvchi uchun suhbat tarixi
MAX_HISTORY = 20  # Har bir foydalanuvchi uchun max xabar soni

# API Usage Tracker
DAILY_LIMIT = 1500  # Gemini bepul limit (kuniga)
api_usage = {}  # {kalit_index: so'rovlar_soni}
api_last_reset = time.time()  # Oxirgi reset vaqti

def get_usage_report():
    """Barcha kalitlar uchun foizli hisobot"""
    lines = []
    total_used = 0
    total_limit = len(API_KEYS) * DAILY_LIMIT
    for i, key in enumerate(API_KEYS):
        used = api_usage.get(i, 0)
        total_used += used
        remaining = max(0, DAILY_LIMIT - used)
        pct_used = min(100, (used / DAILY_LIMIT) * 100)
        pct_left = 100 - pct_used
        # Progress bar
        filled = int(pct_left / 10)
        bar = '█' * filled + '░' * (10 - filled)
        status = '✅' if pct_left > 30 else ('⚠️' if pct_left > 0 else '❌')
        short_key = f"...{key[-6:]}"  # Xavfsizlik uchun faqat oxirgi 6 ta belgi
        lines.append(f"{status} **Kalit {i+1}** `{short_key}`\n   [{bar}] `{pct_left:.0f}%` qoldi ({remaining}/{DAILY_LIMIT})") 
    total_pct = max(0, 100 - (total_used / total_limit * 100)) if total_limit > 0 else 0
    total_bar_filled = int(total_pct / 10)
    total_bar = '█' * total_bar_filled + '░' * (10 - total_bar_filled)
    summary = f"\n📊 **Jami:** [{total_bar}] `{total_pct:.0f}%` qoldi"
    reset_time = datetime.datetime.utcfromtimestamp(api_last_reset + 86400).strftime('%H:%M UTC')
    return "\n".join(lines) + summary + f"\n⏰ **Reset vaqti:** {reset_time}"



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
@client.on(events.NewMessage(pattern=r'\.apistatus', outgoing=True))
async def api_status_handler(event):
    await event.edit("`API holati tekshirilmoqda...` 🔍")
    if not API_KEYS:
        return await event.edit("❌ API kalitlar topilmadi!")
    report = get_usage_report()
    msg = f"🔑 **GEMINI API HOLATI**\n\n{report}"
    await event.edit(msg)

@client.on(events.NewMessage(pattern=r'\.groups (on|off)', outgoing=True))
async def groups_toggle(event):
    global GROUPS_ENABLED
    GROUPS_ENABLED = (event.pattern_match.group(1) == "on")
    text = "Yoqildi" if GROUPS_ENABLED else "O'chirildi"
    await event.edit(f"**Guruhlarda AI javob berish:** `{text}`")

async def daily_api_report():
    """Har kuni soat 08:00 UTC da Saved Messages'ga hisobot yuboradi"""
    while True:
        now = datetime.datetime.utcnow()
        # Keyingi soat 08:00 UTC gacha kutish
        target = now.replace(hour=8, minute=0, second=0, microsecond=0)
        if now >= target:
            target += datetime.timedelta(days=1)
        wait_seconds = (target - now).total_seconds()
        await asyncio.sleep(wait_seconds)
        try:
            report = get_usage_report()
            msg = (
                "📊 **KUNLIK API HISOBOTI**\n\n"
                f"{report}\n\n"
                "💡 Ko'proq kalit qo'shish uchun Renderda\n"
                "`GEMINI_API_KEY_2`, `GEMINI_API_KEY_3` o'rnating."
            )
            await send_to_log(msg)
        except Exception as e:
            print(f"⚠️ Kunlik hisobot xatosi: {e}")


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
            await event.delete()
    except Exception as e: 
        await event.edit(f"❌ Xato: {e}")
    finally:
        # Har qanday holatda ham diskda fayl qolib ketmasligini kafolatlash
        try:
            if 'filename' in locals() and os.path.exists(filename):
                os.remove(filename)
            elif os.path.exists(unique_name + ".mp4"): os.remove(unique_name + ".mp4")
            elif os.path.exists(unique_name + ".webm"): os.remove(unique_name + ".webm")
        except: pass


@client.on(events.NewMessage(pattern=r'\.ocr', outgoing=True))
async def ocr_handler(event):
    if not event.is_reply: return await event.edit("`Rasmga reply qiling!`")
    reply = await event.get_reply_message()
    if not reply.photo: return await event.edit("`Bu rasm emas!`")
    await event.edit("`O'qilmoqda...` 🔍")
    path = await reply.download_media()
    try:
        cl = get_client()
        with PIL.Image.open(path) as img:
            img.load()
            import io
            buf = io.BytesIO()
            img.save(buf, format='JPEG')
            img_bytes = buf.getvalue()
            response = await cl.aio.models.generate_content(
                model='gemini-3.1-flash-lite',
                contents=[

                    gt.Part.from_bytes(data=img_bytes, mime_type='image/jpeg'),
                    "Rasmdagi barcha matnlarni aniq ko'chirib ber."
                ]
            )
            await event.edit(f"📝 **Matn:**\n\n{response.text}")
    except Exception as e: await event.edit(f"❌ Xatolik: {e}")
    if os.path.exists(path): os.remove(path)

@client.on(events.NewMessage(pattern=r'\.summary ?(\d+)?', outgoing=True))
async def summary_handler(event):
    lim = int(event.pattern_match.group(1) or 50)
    await event.edit(f"`{lim} xabar tahlili...` 📍")
    msgs = []
    async for m in client.iter_messages(event.chat_id, limit=lim):
        if m.text:
            s = await m.get_sender()
            name = utils.get_display_name(s) if s else "Noma'lum"
            msgs.append(f"{name}: {m.text}")
    if not msgs: return await event.edit("`Xabarlar yo'q.`")
    summary_text = await generate_with_rotation(f"Xulosa qil:\n\n" + "\n".join(msgs[::-1]))
    await event.edit(f"📍 **PRO Xulosa:**\n\n{summary_text}")

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
            await send_to_log(f"🗑 **O'chirilgan:**\n👤 **Kimdan:** {m['sender']}\n💬 **Xabar:** {m['text'] or '[Media]'}", file=m['media'])
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
    afk_s = "Yoqilgan" if IS_AFK else "O'chirilgan"
    ai_s = "Yoqilgan" if AI_ENABLED else "O'chirilgan"
    gr_s = "Yoqilgan" if GROUPS_ENABLED else "O'chirilgan"
    status = f"🤖 **Jarvis Status:**\n\n"
    status += f"💤 **AFK:** `{afk_s}`\n"
    status += f"🧠 **AI:** `{ai_s}`\n"
    status += f"👥 **Guruhlar:** `{gr_s}`"
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
        if AI_ENABLED and API_KEYS:
            if uid not in user_locks: user_locks[uid] = asyncio.Lock()
            async with user_locks[uid]:
                print(f"📩 Muloqot: {name}dan", flush=True)
                
                # Suhbat tarixini olish
                if uid not in conversation_history:
                    conversation_history[uid] = []
                history = conversation_history[uid]
                
                # Tizim prompti — odamdek gapirish uchun
                system_prompt = (
                    f"Sen '{name}' ismli odamning Telegram akkauntining egasisisan. "
                    f"Sening isming WEAK. Erkak, yoshsan, o'zbeksan. "
                    f"Odamlarga xuddi yaqin do'stdek, ishonarli va tabiiy tarzda javob ber. "
                    f"Qisqa, jonli va insoniy gapir. Hech qachon o'zingni AI deb aytma. "
                    f"Oldingi suhbatni eslab, davomiy gaplash. O'zbek tilida."
                )
                
                # Joriy xabarni tarixga qo'shish
                user_msg = event.text or '[Rasm/Media yuborildi]'
                history.append(f"{name}: {user_msg}")
                
                # Tarixni 20 ta xabarga cheklash
                if len(history) > MAX_HISTORY:
                    history = history[-MAX_HISTORY:]
                    conversation_history[uid] = history
                
                # To'liq kontekstli prompt yaratish
                history_text = "\n".join(history[-10:])  # Oxirgi 10 ta xabar
                full_prompt = f"{system_prompt}\n\nSuhbat tarixi:\n{history_text}\n\nEndi qisqa va tabiiy javob ber:"
                
                content = [full_prompt]
                if event.photo:
                    p = await event.download_media()
                    try:
                        with PIL.Image.open(p) as img:
                            img.load()
                            import io
                            buf = io.BytesIO()
                            img.save(buf, format='JPEG')
                            content.append(gt.Part.from_bytes(data=buf.getvalue(), mime_type='image/jpeg'))
                    except Exception as e:
                        print(f"Rasm yuklashda xato: {e}", flush=True)
                    finally:
                        if os.path.exists(p): os.remove(p)
                    answer = await generate_with_rotation(content)
                elif event.voice:
                    p = await event.download_media()
                    try:
                        with open(p, 'rb') as f:
                            audio_bytes = f.read()
                        content.append(gt.Part.from_bytes(data=audio_bytes, mime_type='audio/ogg'))
                    except Exception as e:
                        print(f"Ovoz yuklashda xato: {e}", flush=True)
                    finally:
                        if os.path.exists(p): os.remove(p)
                    answer = await generate_with_rotation(content)
                else:
                    answer = await generate_with_rotation(content)
                
                # Bot javobini ham tarixga qo'shish
                history.append(f"Men: {answer}")
                conversation_history[uid] = history
                
                async with client.action(event.chat_id, 'typing'):
                    await asyncio.sleep(1.5); await event.reply(answer)

    except Exception as e: 
        import traceback
        err_msg = traceback.format_exc()
        short_err = str(e)
        print(f"⚠️ Xato:\n{err_msg}", flush=True)
        try:
            # Markdown parse error oldini olish uchun parse_mode=None
            await send_to_log(f"⚠️ JARVIS XATOLIK!\nKim bilan: {name}\n\nXato sababi:\n{short_err}", parse_mode=None)
        except: pass


# --- ISHGA TUSHIRISH ---
async def startup_notification():
    try:
        msg = (
            "✅ JARVIS PRO ISHGA TUSHDI!\n\n"
            f"🔑 API Kalitlar: {len(API_KEYS)} ta\n"
            "🌐 Server: Render (24/7)\n"
            "🧠 Model: Gemini 3.1 Flash Lite\n\n"
            "Men ishlashga to'liq tayyorman! Xatolik bo'lsa darhol shu yerga yozaman."
        )
        await send_to_log(msg, parse_mode=None)
    except Exception as e:
        print(f"Startup xabarida xato: {e}")

if __name__ == '__main__':
    Thread(target=run_flask).start()
    print("Jarvis PRO Edition ishga tushishga tayyor...", flush=True)
    client.start()
    # Orqa fon vazifalarini ishga tushirish
    loop = client.loop
    loop.create_task(startup_notification())
    loop.create_task(daily_api_report())
    print(f"✅ {len(API_KEYS)} ta API kalit yuklandi. Kunlik hisobot 08:00 UTC da yuboriladi.", flush=True)
    client.run_until_disconnected()
