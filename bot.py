import os
import json
import asyncio
import httpx

BOT_TOKEN = os.getenv("BOT_TOKEN")
ARCHIVE_CHANNEL_ID = os.getenv("ARCHIVE_CHANNEL_ID")  # کانال آرشیو اصلی
INLINE_CHANNEL_ID = os.getenv("INLINE_CHANNEL_ID")    # کانال آرشیو اینلاین
DATABASE_FILE = "inline_songs.json"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
TIMEOUT = 20

def load_database():
    if os.path.exists(DATABASE_FILE):
        with open(DATABASE_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    return []

def save_database(data):
    with open(DATABASE_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)

inline_database = load_database()

async def send_message(chat_id, text):
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        await client.post(f"{BASE_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": text
        })

async def forward_and_save_audio(message):
    audio = message.get("audio")
    if not audio:
        return

    file_id = audio["file_id"]
    title = audio.get("title", "نامشخص")
    performer = audio.get("performer", "نامشخص")

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post(f"{BASE_URL}/sendAudio", json={
            "chat_id": INLINE_CHANNEL_ID,
            "audio": file_id,
            "caption": f"{title} - {performer}"
        })
        if response.json().get("ok"):
            inline_database.append({
                "file_id": file_id,
                "title": title,
                "performer": performer
            })
            save_database(inline_database)

async def handle_document(document, chat_id):
    if document["file_name"] != "inline_songs.json":
        await send_message(chat_id, "فقط فایل inline_songs.json قابل قبول است.")
        return

    file_id = document["file_id"]
    async with httpx.AsyncClient() as client:
        file_info = await client.get(f"{BASE_URL}/getFile", params={"file_id": file_id})
        file_path = file_info.json()["result"]["file_path"]
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        response = await client.get(file_url)
        with open(DATABASE_FILE, "wb") as file:
            file.write(response.content)
    inline_database[:] = load_database()
    await send_message(chat_id, f"دیتابیس inline_songs.json با موفقیت آپدیت شد.")

async def send_database(chat_id):
    if not os.path.exists(DATABASE_FILE):
        await send_message(chat_id, "دیتابیس خالی است.")
        return

    async with httpx.AsyncClient() as client:
        with open(DATABASE_FILE, "rb") as file:
            await client.post(f"{BASE_URL}/sendDocument", params={"chat_id": chat_id}, files={"document": file})

async def check_updates():
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

                        if chat_id == int(ARCHIVE_CHANNEL_ID) and "audio" in message:
                            await forward_and_save_audio(message)

                        elif text == "/list":
                            await send_database(chat_id)

                        elif "document" in message:
                            await handle_document(message["document"], chat_id)

        except Exception as e:
            print(f"خطا: {e}")
            await asyncio.sleep(5)

        await asyncio.sleep(2)

async def main():
    await send_message(ARCHIVE_CHANNEL_ID, "ربات فعال شد و آماده است.")
    await check_updates()

if __name__ == "__main__":
    asyncio.run(main())