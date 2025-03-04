import os
import json
import asyncio
import httpx

BOT_TOKEN = os.getenv("BOT_TOKEN")
ARCHIVE_CHANNEL_ID = os.getenv("ARCHIVE_CHANNEL_ID")
INLINE_CHANNEL_ID = os.getenv("INLINE_CHANNEL_ID")
DATABASE_FILE = "inline_songs.json"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
TIMEOUT = 20

def load_inline_database():
    if os.path.exists(DATABASE_FILE):
        with open(DATABASE_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    return []

def save_inline_database():
    with open(DATABASE_FILE, "w", encoding="utf-8") as file:
        json.dump(inline_song_database, file, indent=4, ensure_ascii=False)

inline_song_database = load_inline_database()

async def send_message(chat_id, text):
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        await client.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": text
        })

async def send_inline_database(chat_id):
    if os.path.exists(DATABASE_FILE):
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            with open(DATABASE_FILE, "rb") as file:
                await client.post(f"{BASE_URL}/sendDocument", params={"chat_id": chat_id}, files={"document": file})
    else:
        await send_message(chat_id, "دیتابیس خالی است!")

async def forward_to_inline_channel(file_id, title, performer):
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post(f"{BASE_URL}/sendAudio", json={
            "chat_id": INLINE_CHANNEL_ID,
            "audio": file_id,
            "caption": f"{title} - {performer}"
        })

        if response.json().get("ok"):
            inline_song_database.append({
                "file_id": file_id,
                "title": title,
                "performer": performer
            })
            save_inline_database()
            print(f"آهنگ به کانال اینلاین فوروارد و ذخیره شد: {title} - {performer}")
        else:
            print(f"خطا در فوروارد: {response.json()}")

async def check_new_messages():
    last_update_id = None
    while True:
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.get(f"{BASE_URL}/getUpdates", params={"offset": last_update_id})
                data = response.json()

                if data.get("ok"):
                    for update in data["result"]:
                        last_update_id = update["update_id"] + 1
                        message = update.get("message", {})
                        chat_id = message.get("chat", {}).get("id")
                        text = message.get("text", "").strip()

                        if text == "/list":
                            await send_inline_database(chat_id)

                        elif "audio" in message:
                            audio = message["audio"]
                            title = audio.get("title", "نامشخص")
                            performer = audio.get("performer", "نامشخص")
                            file_id = audio.get("file_id")

                            if str(chat_id) == INLINE_CHANNEL_ID:
                                inline_song_database.append({
                                    "file_id": file_id,
                                    "title": title,
                                    "performer": performer
                                })
                                save_inline_database()
                                print(f"آهنگ در دیتابیس اینلاین ذخیره شد: {title} - {performer}")

                            elif str(chat_id) == ARCHIVE_CHANNEL_ID:
                                await forward_to_inline_channel(file_id, title, performer)

        except Exception as e:
            print(f"⚠️ خطا: {e}")
            await asyncio.sleep(5)

        await asyncio.sleep(3)

async def main():
    print("ربات فعال شد!")
    await check_new_messages()

if __name__ == "__main__":
    asyncio.run(main())