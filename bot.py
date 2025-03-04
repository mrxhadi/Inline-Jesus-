import os
import json
import asyncio
import httpx

BOT_TOKEN = os.getenv("BOT_TOKEN")
MAIN_ARCHIVE_CHANNEL_ID = int(os.getenv("MAIN_ARCHIVE_CHANNEL_ID"))
INLINE_ARCHIVE_CHANNEL_ID = int(os.getenv("INLINE_ARCHIVE_CHANNEL_ID"))
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

inline_song_database = load_database()

async def send_message(chat_id, text):
    async with httpx.AsyncClient() as client:
        await client.get(f"{BASE_URL}/sendMessage", params={"chat_id": chat_id, "text": text})

async def handle_document(document, chat_id):
    if document["file_name"] != DATABASE_FILE:
        await send_message(chat_id, "لطفاً فایل inline_songs.json را ارسال کنید.")
        return

    file_id = document["file_id"]
    async with httpx.AsyncClient() as client:
        file_info = await client.get(f"{BASE_URL}/getFile", params={"file_id": file_id})
        file_path = file_info.json()["result"]["file_path"]
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        response = await client.get(file_url)

    with open(DATABASE_FILE, "wb") as file:
        file.write(response.content)

    inline_song_database[:] = load_database()
    await send_message(chat_id, f"✅ دیتابیس بروزرسانی شد. تعداد آهنگ‌ها: {len(inline_song_database)}")

async def send_file_to_user(chat_id):
    if os.path.exists(DATABASE_FILE):
        async with httpx.AsyncClient() as client:
            with open(DATABASE_FILE, "rb") as file:
                await client.post(f"{BASE_URL}/sendDocument", params={"chat_id": chat_id}, files={"document": file})
    else:
        await send_message(chat_id, "❌ دیتابیس یافت نشد.")

async def handle_archive_channel(message):
    if "audio" in message:
        audio = message["audio"]
        file_id = audio["file_id"]
        title = audio.get("title", "نامشخص")
        performer = audio.get("performer", "نامشخص")

        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/copyMessage", params={
                "chat_id": INLINE_ARCHIVE_CHANNEL_ID,
                "from_chat_id": MAIN_ARCHIVE_CHANNEL_ID,
                "message_id": message["message_id"]
            })
            result = response.json()
            if result.get("ok"):
                inline_song_database.append({
                    "file_id": file_id,
                    "title": title,
                    "performer": performer,
                    "chat_id": INLINE_ARCHIVE_CHANNEL_ID
                })
                save_database(inline_song_database)
                print(f"آهنگ جدید از آرشیو اصلی ذخیره شد: {title} - {performer}")

async def handle_inline_archive_channel(message):
    if "audio" in message:
        audio = message["audio"]
        file_id = audio["file_id"]
        title = audio.get("title", "نامشخص")
        performer = audio.get("performer", "نامشخص")

        inline_song_database.append({
            "file_id": file_id,
            "title": title,
            "performer": performer,
            "chat_id": INLINE_ARCHIVE_CHANNEL_ID
        })
        save_database(inline_song_database)
        print(f"آهنگ جدید از آرشیو اینلاین ذخیره شد: {title} - {performer}")

async def handle_inline_query(query_id, query):
    results = []
    for idx, song in enumerate(inline_song_database):
        if query.lower() in song.get("title", "").lower():
            results.append({
                "type": "audio",
                "id": str(idx),
                "audio_file_id": song["file_id"],
                "title": song["title"],
                "performer": song["performer"]
            })

    async with httpx.AsyncClient() as client:
        await client.post(f"{BASE_URL}/answerInlineQuery", json={
            "inline_query_id": query_id,
            "results": results,
            "cache_time": 0
        })

async def check_updates():
    last_update_id = None
    while True:
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.get(f"{BASE_URL}/getUpdates", params={"offset": last_update_id, "timeout": 30})
                updates = response.json().get("result", [])

            for update in updates:
                last_update_id = update["update_id"] + 1
                message = update.get("message")
                inline_query = update.get("inline_query")

                if message:
                    chat_id = message["chat"]["id"]

                    if "document" in message:
                        await handle_document(message["document"], chat_id)
                    elif chat_id == INLINE_ARCHIVE_CHANNEL_ID:
                        await handle_inline_archive_channel(message)
                    elif chat_id == MAIN_ARCHIVE_CHANNEL_ID:
                        await handle_archive_channel(message)
                    elif "text" in message and message["text"] == "/list":
                        await send_file_to_user(chat_id)

                elif inline_query:
                    await handle_inline_query(inline_query["id"], inline_query["query"])

        except Exception as e:
            print(f"⚠️ خطا: {e}")
            await asyncio.sleep(5)

async def main():
    print("ربات آماده است.")
    await check_updates()

if __name__ == "__main__":
    asyncio.run(main())