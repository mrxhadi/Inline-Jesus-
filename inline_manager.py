import json
import os
import httpx
import asyncio

BOT_TOKEN = os.getenv("BOT_TOKEN")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
INLINE_DATABASE_FILE = "inline_songs.json"
TIMEOUT = 20

def load_inline_database():
    if os.path.exists(INLINE_DATABASE_FILE):
        with open(INLINE_DATABASE_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    return []

inline_database = load_inline_database()

async def answer_inline_query(inline_query_id, results):
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        await client.post(f"{BASE_URL}/answerInlineQuery", json={
            "inline_query_id": inline_query_id,
            "results": results,
            "cache_time": 1
        })

async def handle_inline_query(inline_query):
    query = inline_query.get("query", "").lower()
    inline_query_id = inline_query["id"]

    matched_songs = []
    for song in inline_database:
        title = song.get("title", "")
        performer = song.get("performer", "")
        if query in title.lower() or query in performer.lower():
            matched_songs.append({
                "type": "audio",
                "id": song["file_id"],
                "audio_file_id": song["file_id"],
                "title": title,
                "performer": performer
            })

    await answer_inline_query(inline_query_id, matched_songs[:10])

async def update_inline_database(audio):
    song = {
        "file_id": audio["file_id"],
        "title": audio.get("title", "نامشخص"),
        "performer": audio.get("performer", "نامشخص")
    }
    inline_database.append(song)
    with open(INLINE_DATABASE_FILE, "w", encoding="utf-8") as file:
        json.dump(inline_database, file, indent=4, ensure_ascii=False)
