import os
import json
import asyncio
import httpx
from inline_manager import handle_inline_query, update_inline_database

BOT_TOKEN = os.getenv("BOT_TOKEN")
ARCHIVE_CHANNEL_ID = os.getenv("ARCHIVE_CHANNEL_ID")
INLINE_ARCHIVE_CHANNEL_ID = os.getenv("INLINE_ARCHIVE_CHANNEL_ID")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
INLINE_DATABASE_FILE = "inline_songs.json"
DATABASE_FILE = "songs.json"
TIMEOUT = 20

def load_database(file_name):
    if os.path.exists(file_name):
        with open(file_name, "r", encoding="utf-8") as file:
            return json.load(file)
    return []

song_database = load_database(DATABASE_FILE)

async def send_message(chat_id, text):
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        await client.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": text
        })

async def send_file(chat_id, file_path):
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        with open(file_path, "rb") as file:
            await client.post(f"{BASE_URL}/sendDocument", data={"chat_id": chat_id}, files={"document": file})

async def handle_updates():
    last_update_id = None
    while True:
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.get(f"{BASE_URL}/getUpdates", params={"offset": last_update_id})
                updates = response.json().get("result", [])

                for update in updates:
                    last_update_id = update["update_id"] + 1

                    if "inline_query" in update:
                        await handle_inline_query(update["inline_query"])
                    elif "message" in update:
                        await handle_message(update["message"])

        except Exception as e:
            print(f"Error: {e}")
            await asyncio.sleep(5)

async def handle_message(message):
    chat_id = message["chat"]["id"]

    if "audio" in message and str(chat_id) == INLINE_ARCHIVE_CHANNEL_ID:
        audio = message["audio"]
        await update_inline_database(audio)

    if "text" in message:
        text = message["text"]
        if text == "/list":
            await send_file(chat_id, DATABASE_FILE)
            await send_file(chat_id, INLINE_DATABASE_FILE)

async def main():
    await send_message(ARCHIVE_CHANNEL_ID, "ربات آماده است.")
    await handle_updates()

if __name__ == "__main__":
    asyncio.run(main())
