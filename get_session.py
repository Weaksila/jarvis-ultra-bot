from telethon.sync import TelegramClient
from telethon.sessions import StringSession

api_id = 32894755
api_hash = '67f6c4bfe4148ee90c1f54376a4da248'

with TelegramClient(StringSession(), api_id, api_hash) as client:
    print("\nSIZNING STRING SESSION KODINGIZ (NUSXALAB OLING):\n")
    print(client.session.save())
    print("\n-----------------------------------------------\n")
