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
                await client.post(
                    f"{BASE_URL}/sendDocument",
                    params={"chat_id": chat_id},
                    files={"document": (DATABASE_FILE, file, "application/json")}
                )
    else:
        await send_message(chat_id, "❌ دیتابیس یافت نشد.")

async def handle_archive_channel(message):
    if "audio" in message:
        audio = message["audio"]
        file_id = audio["file_id"]
        title = audio.get("title", "نامشخص")
        performer = audio.get("performer", "نامشخص")

        async with httpx.AsyncClient() as client:
            await client.get(f"{BASE_URL}/copyMessage", params={
                "chat_id": INLINE_ARCHIVE_CHANNEL_ID,
                "from_chat_id": MAIN_ARCHIVE_CHANNEL_ID,
                "message_id": message["message_id"]
            })

async def save_song_from_inline_channel(message):
    try:
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
            print(f"✅ آهنگ جدید ذخیره شد: {title} - {performer}")
        else:
            print("⚠️ پیام دریافتی فاقد فایل صوتی است.")
    except Exception as e:
        print(f"❌ خطا در ذخیره‌سازی آهنگ از چنل اینلاین: {e}")
        traceback.print_exc()

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
                response = await client.get(
                    f"{BASE_URL}/getUpdates",
                    params={"offset": last_update_id, "timeout": 30}
                )
                data = response.json()
                print(f"داده دریافتی از getUpdates: {data}")

                if data.get("error_code") == 409:
                    print("❌ خطای 409: تداخل در اجرای ربات. متوقف می‌شود.")
                    break

                updates = data.get("result", [])

            for update in updates:
                print(f"بررسی آپدیت جدید: {update}")
                last_update_id = update["update_id"] + 1

                if "message" in update:
                    message = update["message"]
                    chat_id = message["chat"]["id"]
                    print(f"پیام جدید: {message}")

                    if "audio" in message:
                        if chat_id == MAIN_ARCHIVE_CHANNEL_ID:
                            await handle_archive_channel(message)
                        elif chat_id == INLINE_ARCHIVE_CHANNEL_ID:
                            await save_song_from_inline_channel(message)
                    elif "document" in message and chat_id not in [MAIN_ARCHIVE_CHANNEL_ID, INLINE_ARCHIVE_CHANNEL_ID]:
                        await handle_document(message["document"], chat_id)
                    elif "text" in message and message["text"] == "/list" and chat_id not in [MAIN_ARCHIVE_CHANNEL_ID, INLINE_ARCHIVE_CHANNEL_ID]:
                        await send_file_to_user(chat_id)
                    else:
                        print("⚠️ پیام نامرتبط دریافت شد. نادیده گرفته می‌شود.")

                elif "inline_query" in update:
                    inline_query = update["inline_query"]
                    print(f"کوئری اینلاین جدید: {inline_query}")
                    await handle_inline_query(inline_query["id"], inline_query["query"])

                else:
                    print("⚠️ آپدیت نامرتبط دریافت شد و نادیده گرفته می‌شود.")

            await asyncio.sleep(1)

        except Exception as e:
            print(f"❌ خطا در check_updates: {e}")
            traceback.print_exc()
            await asyncio.sleep(5)

async def main():
    print("ربات آماده است.")
    await check_updates()

if __name__ == "__main__":
    asyncio.run(main())