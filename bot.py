import os
import json
import asyncio
import httpx

BOT_TOKEN = os.getenv("BOT_TOKEN")
MAIN_ARCHIVE_CHANNEL_ID = os.getenv("MAIN_ARCHIVE_CHANNEL_ID")
INLINE_ARCHIVE_CHANNEL_ID = os.getenv("INLINE_ARCHIVE_CHANNEL_ID")
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

async def send_file_to_user(chat_id):
    if os.path.exists(DATABASE_FILE):
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            with open(DATABASE_FILE, "rb") as file:
                await client.post(f"{BASE_URL}/sendDocument", data={"chat_id": chat_id}, files={"document": ("inline_songs.json", file)})
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
    print(f"✅ آهنگ ذخیره شد: {audio.get('title', 'نامشخص')}")

async def forward_and_store_from_main_channel(message):
    audio = message["audio"]
    # به‌روز رسانی دیتابیس اینلاین
    await update_inline_database(audio, str(INLINE_ARCHIVE_CHANNEL_ID))
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post(f"{BASE_URL}/sendAudio", json={
            "chat_id": INLINE_ARCHIVE_CHANNEL_ID,
            "audio": audio["file_id"],
            "caption": f"{audio.get('title', 'نامشخص')} - {audio.get('performer', 'نامشخص')}"
        })
        print("فوروارد از کانال اصلی:", response.json())

async def handle_inline_archive_channel(message):
    audio = message.get("audio")
    if not audio:
        print("پیام فاقد فایل صوتی است.")
        return

    title = audio.get("title", "Unknown Title")
    performer = audio.get("performer", "Unknown Performer")
    file_id = audio["file_id"]
    chat_id = message["chat"]["id"]

    song_data = {
        "file_id": file_id,
        "title": title,
        "performer": performer,
        "chat_id": chat_id
    }

    inline_songs_database.append(song_data)
    save_inline_database(inline_songs_database)
    print(f"آهنگ جدید در چنل اینلاین آرشیو ذخیره شد: {title} - {performer}")
                        # بررسی inline query (این بخش را می‌توانید بعداً اضافه کنید)
                        if "inline_query" in update:
                            # inline_query_handler(update["inline_query"])  # در صورت نیاز
                            pass
                        elif "message" in update:
                            message = update["message"]
                            chat_id = str(message.get("chat", {}).get("id", ""))
                            text = message.get("text", "").strip()

                            if text == "/list":
                                await send_file_to_user(chat_id)
                            elif "document" in message:
                                # اگر فایل دیتابیس ارسال شد
                                await handle_document(message["document"], chat_id)
                            elif "audio" in message:
                                if chat_id == MAIN_ARCHIVE_CHANNEL_ID:
                                    await forward_and_store_from_main_channel(message)
                                elif chat_id == INLINE_ARCHIVE_CHANNEL_ID:
                                    await handle_inline_archive_channel(message["audio"])
                                else:
                                    # پیام صوتی از سایر چت‌ها را نادیده می‌گیریم
                                    pass
        except Exception as e:
            print(f"⚠️ خطا: {e}")
            await asyncio.sleep(5)
        await asyncio.sleep(3)

async def main():
    print("ربات فعال است.")
    await send_message(MAIN_ARCHIVE_CHANNEL_ID, "ربات فعال است.")
    await check_updates()

if __name__ == "__main__":
    asyncio.run(main())