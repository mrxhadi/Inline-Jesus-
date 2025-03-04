import os
import json
import asyncio
import httpx

BOT_TOKEN = os.getenv("BOT_TOKEN")
INLINE_CHANNEL_ID = os.getenv("INLINE_CHANNEL_ID")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
DATABASE_FILE = "inline_songs.json"
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
        await client.get(f"{BASE_URL}/sendMessage", params={"chat_id": chat_id, "text": text})

async def send_file_to_user(chat_id):
    if os.path.exists(DATABASE_FILE):
        async with httpx.AsyncClient() as client:
            with open(DATABASE_FILE, "rb") as file:
                await client.post(f"{BASE_URL}/sendDocument", params={"chat_id": chat_id}, files={"document": file})
    else:
        await send_message(chat_id, "⚠️ دیتابیس خالی است!")

async def forward_and_store(song):
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.get(f"{BASE_URL}/sendAudio", params={
            "chat_id": INLINE_CHANNEL_ID,
            "audio": song["file_id"],
            "caption": f"{song['title']} - {song['performer']}"
        })

        if response.json().get("ok"):
            inline_song_database.append(song)
            save_database(inline_song_database)

async def handle_new_audio(message):
    audio = message["audio"]
    file_id = audio["file_id"]
    title = audio.get("title", "نامشخص")
    performer = audio.get("performer", "نامشخص")
    chat_id = message["chat"]["id"]

    for song in inline_song_database:
        if song["file_id"] == file_id:
            return

    new_song = {
        "file_id": file_id,
        "title": title,
        "performer": performer
    }

    if str(chat_id) != INLINE_CHANNEL_ID:
        await forward_and_store(new_song)
    else:
        inline_song_database.append(new_song)
        save_database(inline_song_database)

async def handle_inline_query(inline_query):
    query = inline_query.get("query", "").lower()
    results = []

    for i, song in enumerate(inline_song_database):
        title = song.get("title", "نامشخص")
        performer = song.get("performer", "نامشخص")
        file_id = song["file_id"]

        if query in title.lower() or query in performer.lower():
            results.append({
                "type": "audio",
                "id": str(i),
                "audio_file_id": file_id,
                "title": title,
                "performer": performer
            })

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        await client.post(f"{BASE_URL}/answerInlineQuery", json={
            "inline_query_id": inline_query["id"],
            "results": results,
            "cache_time": 0
        })

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

                        if "inline_query" in update:
                            await handle_inline_query(update["inline_query"])
                            continue

                        message = update.get("message", {})
                        chat_id = message.get("chat", {}).get("id")
                        text = message.get("text", "").strip()

                        if text == "/start":
                            await send_message(chat_id, "ربات فعال است.")
                        elif text == "/list":
                            await send_file_to_user(chat_id)
                        elif "audio" in message:
                            await handle_new_audio(message)

        except Exception as e:
            print(f"⚠️ خطا: {e}")
            await asyncio.sleep(5)

        await asyncio.sleep(3)

async def main():
    print("ربات فعال شد.")
    await check_new_messages()

if __name__ == "__main__":
    asyncio.run(main())