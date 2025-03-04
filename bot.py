import os
import json
import asyncio
import httpx

BOT_TOKEN = os.getenv("BOT_TOKEN")
INLINE_ARCHIVE_CHANNEL_ID = os.getenv("INLINE_ARCHIVE_CHANNEL_ID")
MAIN_ARCHIVE_CHANNEL_ID = os.getenv("MAIN_ARCHIVE_CHANNEL_ID")
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
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        await client.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": text})


async def handle_document(document, chat_id):
    file_name = document["file_name"]
    if file_name != "inline_songs.json":
        await send_message(chat_id, "لطفاً فقط فایل inline_songs.json ارسال کنید.")
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
    await send_message(chat_id, "✅ دیتابیس اینلاین به‌روزرسانی شد.")


async def send_file_to_user(chat_id):
    if os.path.exists(DATABASE_FILE):
        async with httpx.AsyncClient() as client:
            with open(DATABASE_FILE, "rb") as file:
                await client.post(f"{BASE_URL}/sendDocument", data={"chat_id": chat_id}, files={"document": file})
    else:
        await send_message(chat_id, "دیتابیس خالی است.")


async def update_inline_database(audio, chat_id):
    inline_song_database.append({
        "file_id": audio["file_id"],
        "title": audio.get("title", "نامشخص"),
        "performer": audio.get("performer", "نامشخص"),
        "chat_id": chat_id
    })
    save_database(inline_song_database)


async def forward_and_store_from_main_channel(message):
    audio = message["audio"]
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{BASE_URL}/sendAudio", json={
            "chat_id": INLINE_ARCHIVE_CHANNEL_ID,
            "audio": audio["file_id"],
            "caption": ""
        })
        if response.json().get("ok"):
            await update_inline_database(audio, INLINE_ARCHIVE_CHANNEL_ID)


async def handle_inline_archive_channel(audio):
    await update_inline_database(audio, INLINE_ARCHIVE_CHANNEL_ID)


async def handle_inline_query(query_id, query_text):
    results = []
    for song in inline_song_database:
        if query_text.lower() in song["title"].lower():
            results.append({
                "type": "audio",
                "id": song["file_id"],
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
                response = await client.get(f"{BASE_URL}/getUpdates", params={"offset": last_update_id})
                data = response.json()
                if data.get("ok"):
                    for update in data["result"]:
                        last_update_id = update["update_id"] + 1
                        if "inline_query" in update:
                            inline_query = update["inline_query"]
                            await handle_inline_query(inline_query["id"], inline_query["query"])
                        elif "message" in update:
                            message = update["message"]
                            chat_id = str(message["chat"]["id"])
                            if chat_id == MAIN_ARCHIVE_CHANNEL_ID and "audio" in message:
                                await forward_and_store_from_main_channel(message)
                            elif chat_id == INLINE_ARCHIVE_CHANNEL_ID and "audio" in message:
                                await handle_inline_archive_channel(message["audio"])
                            elif "document" in message:
                                await handle_document(message["document"], chat_id)
                            elif "text" in message and message["text"] == "/list":
                                await send_file_to_user(chat_id)
        except Exception as e:
            print(f"⚠️ خطا: {e}")
            await asyncio.sleep(5)
        await asyncio.sleep(3)


async def main():
    await check_updates()


if __name__ == "__main__":
    asyncio.run(main())