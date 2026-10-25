"""Sozlamalar: hamma narsa .env faylidan o'qiladi."""
import os
import sys

from dotenv import load_dotenv

load_dotenv()


def _get(name: str, default: str | None = None, required: bool = True) -> str:
    value = os.getenv(name, default)
    if required and not value:
        sys.exit(f"❌ .env faylida {name} to'ldirilmagan. .env.example'ga qarang.")
    return value or ""


TELEGRAM_BOT_TOKEN = _get("TELEGRAM_BOT_TOKEN")
OWNER_TELEGRAM_ID = int(_get("OWNER_TELEGRAM_ID"))

GEMINI_API_KEY = _get("GEMINI_API_KEY")
GEMINI_MODEL = _get("GEMINI_MODEL", "gemini-2.5-flash", required=False)

APIFY_TOKEN = _get("APIFY_TOKEN")

GOOGLE_CREDENTIALS_FILE = _get("GOOGLE_CREDENTIALS_FILE", "credentials.json", required=False)
SPREADSHEET_ID = _get("SPREADSHEET_ID")

TIMEZONE = _get("TIMEZONE", "Asia/Tashkent", required=False)
DAILY_LIMIT = int(_get("DAILY_LIMIT", "30", required=False))

# Holatlar (Sheets'dagi "holat" ustuni uchun)
STATUSES = [
    "yangi", "yuborildi", "javob berdi", "namuna ko'rsatildi",
    "sinovda", "mijoz", "rad etdi",
]


if __name__ == "__main__":
    # Sinov: kalitlar o'qilganini tekshiradi (to'liq ko'rsatmaydi)
    def mask(s: str) -> str:
        return s[:4] + "..." if len(s) > 4 else "***"

    print("✅ .env muvaffaqiyatli o'qildi")
    print("Bot tokeni :", mask(TELEGRAM_BOT_TOKEN))
    print("Owner ID   :", OWNER_TELEGRAM_ID)
    print("Gemini     :", mask(GEMINI_API_KEY), GEMINI_MODEL)
    print("Apify      :", mask(APIFY_TOKEN))
    print("Sheet ID   :", mask(SPREADSHEET_ID))
    print("Kunlik limit:", DAILY_LIMIT, "| Vaqt zonasi:", TIMEZONE)
