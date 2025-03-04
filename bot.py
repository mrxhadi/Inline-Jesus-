import os
import json
import asyncio
import httpx
import traceback

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
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            await client.get(f"{BASE_URL}/sendMessage", params={"chat_id": chat_id, "text": text})
    except httpx.HTTPError as e:
        print(f"❌ خطا در ارسال پیام: {e}")
        traceback.print_exc()

async def forward_audio(message_id):
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            await client.get(f"{BASE_URL}/copyMessage", params={
                "chat_id": INLINE_ARCHIVE_CHANNEL_ID,
                "from_chat_id": MAIN_ARCHIVE_CHANNEL_ID,
                "message_id": message_id
            })
    except httpx.HTTPError as e:
        print(f"❌ خطا در فوروارد آهنگ: {e}")
        traceback.print_exc()

async def save_audio(message):
    try:
        audio = message.get("audio")
        if not audio:
            print("⚠️ پیام فاقد فایل صوتی است.")
            return

        inline_song_database.append({
            "file_id": audio["file_id"],
            "title": audio.get("title", "نامشخص"),
            "performer": audio.get("performer", "نامشخص"),
            "chat_id": INLINE_ARCHIVE_CHANNEL_ID
        })
        save_database(inline_song_database)
        print(f"✅ آهنگ ذخیره شد: {audio.get('title', 'نامشخص')} - {audio.get('performer', 'نامشخص')}")
    except Exception as e:
        print(f"❌ خطا در ذخیره‌سازی آهنگ: {e}")
        traceback.print_exc()

async def handle_inline_query(query_id, query):
    results = [
        {
            "type": "audio",
            "id": str(idx),
            "audio_file_id": song["file_id"],
            "title": song["title"],
            "performer": song["performer"]
        }
        for idx, song in enumerate(inline_song_database)
        if query.lower() in song.get("title", "").lower()
    ]

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            await client.post(f"{BASE_URL}/answerInlineQuery", json={
                "inline_query_id": query_id,
                "results": results,
                "cache_time": 0
            })
    except httpx.HTTPError as e:
        print(f"❌ خطا در پاسخ به اینلاین کوئری: {e}")
        traceback.print_exc()

async def send_database(chat_id):
    if not os.path.exists(DATABASE_FILE):
        await send_message(chat_id, "❌ دیتابیس یافت نشد.")
        return

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            with open(DATABASE_FILE, "rb") as file:
                await client.post(
                    f"{BASE_URL}/sendDocument",
                    params={"chat_id": chat_id},
                    files={"document": (DATABASE_FILE, file, "application/json")}
                )
    except httpx.HTTPError as e:
        print(f"❌ خطا در ارسال دیتابیس: {e}")
        traceback.print_exc()

async def update_database(document):
    if document["file_name"] != DATABASE_FILE:
        return "❌ لطفاً فایل inline_songs.json را ارسال کنید."

    file_id = document["file_id"]
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            file_info = await client.get(f"{BASE_URL}/getFile", params={"file_id": file_id})
            file_path = file_info.json()["result"]["file_path"]
            file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
            response = await client.get(file_url)

        with open(DATABASE_FILE, "wb") as file:
            file.write(response.content)

        inline_song_database[:] = load_database()
        return f"✅ دیتابیس بروزرسانی شد. تعداد آهنگ‌ها: {len(inline_song_database)}"

    except httpx.HTTPError as e:
        print(f"❌ خطا در بروزرسانی دیتابیس: {e}")
        traceback.print_exc()
        return "❌ خطا در بروزرسانی دیتابیس رخ داد."

async def check_updates():
    last_update_id = None
    while True:
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.get(
                    f"{BASE_URL}/getUpdates",
                    params={"offset": last_update_id, "timeout": 30}
                )
                data = response.json()
                updates = data.get("result", [])

            for update in updates:
                last_update_id = update["update_id"] + 1

                if "message" in update:
                    message = update["message"]
                    chat_id = message["chat"]["id"]

                    if chat_id == MAIN_ARCHIVE_CHANNEL_ID and "audio" in message:
                        await forward_audio(message["message_id"])

                    if chat_id == INLINE_ARCHIVE_CHANNEL_ID and "audio" in message:
                        await save_audio(message)

                    if "document" in message:
                        result = await update_database(message["document"])
                        await send_message(chat_id, result)

                    if "text" in message and message["text"] == "/list":
                        await send_database(chat_id)

                elif "inline_query" in update:
                    inline_query = update["inline_query"]
                    await handle_inline_query(inline_query["id"], inline_query["query"])

            await asyncio.sleep(1)

        except httpx.HTTPError as e:
            print(f"❌ خطای HTTP: {e}")
            traceback.print_exc()
            await asyncio.sleep(5)
        except Exception as e:
            print(f"❌ خطای ناشناخته: {e}")
            traceback.print_exc()
            await asyncio.sleep(5)

async def main():
    print("ربات آماده است.")
    await check_updates()

if __name__ == "__main__":
    asyncio.run(main())