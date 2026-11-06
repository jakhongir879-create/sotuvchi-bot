"""Google Sheets bilan ishlash: do'konlarni saqlash, dublikat tekshiruv, holat yangilash."""
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import config

LEADS_SHEET = "Do'konlar"
LOG_SHEET = "Log"

HEADERS = [
    "username", "link", "shahar", "obunachi", "kontakt", "ball", "muammo",
    "xabar", "holat", "sana", "izoh",
    "yuborilgan_sana", "xabar_2", "eslatma",
]
LOG_HEADERS = ["vaqt", "username", "holat"]

_tz = ZoneInfo(config.TIMEZONE)


def now() -> datetime:
    return datetime.now(_tz)


def today() -> str:
    return now().strftime("%Y-%m-%d")


def normalize_username(raw: str) -> str:
    """'@Butik_UZ', 'https://instagram.com/butik_uz/?hl=uz' -> 'butik_uz'"""
    u = raw.strip().lower()
    u = re.sub(r"^https?://(www\.)?instagram\.com/", "", u)
    u = u.split("?")[0].strip("/").lstrip("@")
    return u.split("/")[0]


class Sheets:
    def __init__(self, leads_ws, log_ws):
        self.ws = leads_ws
        self.log = log_ws
        self._ensure_header(self.ws, HEADERS)
        self._ensure_header(self.log, LOG_HEADERS)

    @classmethod
    def connect(cls) -> "Sheets":
        import gspread  # bu yerda import qilamiz: testlar gspread'siz ham ishlasin

        client = gspread.service_account(filename=config.GOOGLE_CREDENTIALS_FILE)
        book = client.open_by_key(config.SPREADSHEET_ID)
        return cls(cls._get_or_create(book, LEADS_SHEET, len(HEADERS)),
                   cls._get_or_create(book, LOG_SHEET, len(LOG_HEADERS)))

    @staticmethod
    def _get_or_create(book, title: str, cols: int):
        import gspread

        try:
            return book.worksheet(title)
        except gspread.WorksheetNotFound:
            return book.add_worksheet(title=title, rows=1000, cols=cols)

    @staticmethod
    def _ensure_header(ws, headers: list[str]) -> None:
        values = ws.get_all_values()
        if not values:
            ws.append_row(headers)
        elif values[0] != headers:
            raise RuntimeError(
                f"'{ws.title}' varag'ining 1-qatori kutilgan sarlavhalarga mos emas. "
                "Varaqni bo'sh qoldiring, bot sarlavhani o'zi yozadi."
            )

    # ---------- o'qish ----------
    def _rows(self) -> list[dict]:
        """Barcha do'konlar; har birida '_row' (Sheets'dagi qator raqami) bor."""
        values = self.ws.get_all_values()
        out = []
        for i, row in enumerate(values[1:], start=2):
            row = row + [""] * (len(HEADERS) - len(row))
            d = dict(zip(HEADERS, row))
            d["_row"] = i
            out.append(d)
        return out

    def get(self, username: str) -> dict | None:
        u = normalize_username(username)
        return next((r for r in self._rows() if r["username"] == u), None)

    def exists(self, username: str) -> bool:
        return self.get(username) is not None

    def get_top_new(self, limit: int | None = None) -> list[dict]:
        """Holati 'yangi' bo'lgan do'konlar, eng yuqori ball birinchi."""
        limit = limit or config.DAILY_LIMIT
        new = [r for r in self._rows() if r["holat"] == "yangi"]
        new.sort(key=lambda r: _to_float(r["ball"]), reverse=True)
        return new[:limit]

    def followups_due(self, days: int = 2) -> list[dict]:
        """'yuborildi' holatida `days` kundan beri javobsiz, 2-xabar hali yozilmaganlar."""
        limit = (now() - timedelta(days=days)).strftime("%Y-%m-%d")
        return [
            r for r in self._rows()
            if r["holat"] == "yuborildi" and r["eslatma"] == ""
            and r["yuborilgan_sana"] and r["yuborilgan_sana"] <= limit
        ]

    # ---------- yozish ----------
    def add_leads(self, leads: list[dict]) -> tuple[int, int]:
        """Yangi do'konlarni qo'shadi. Dublikatlar (username bo'yicha) o'tkazib yuboriladi.
        Qaytaradi: (qo'shildi, o'tkazib yuborildi)."""
        seen = {r["username"] for r in self._rows()}
        rows, skipped = [], 0
        for lead in leads:
            u = normalize_username(lead.get("username", ""))
            if not u or u in seen:
                skipped += 1
                continue
            seen.add(u)
            data = {
                "link": f"https://instagram.com/{u}",
                "holat": "yangi",
                "sana": today(),
                **lead,
                "username": u,
            }
            rows.append([str(data.get(h, "")) for h in HEADERS])
        if rows:
            # RAW: matn "=" yoki "+" bilan boshlansa ham formula bo'lib ketmaydi
            self.ws.append_rows(rows, value_input_option="RAW")
        return len(rows), skipped

    def _set(self, row: int, column: str, value: str) -> None:
        self.ws.update_cell(row, HEADERS.index(column) + 1, value)

    def set_status(self, username: str, status: str, izoh: str | None = None) -> bool:
        """Holatni yangilaydi va Log'ga yozadi. Do'kon topilmasa False."""
        if status not in config.STATUSES:
            raise ValueError(f"Noma'lum holat: {status}")
        lead = self.get(username)
        if not lead:
            return False
        self._set(lead["_row"], "holat", status)
        if status == "yuborildi":
            self._set(lead["_row"], "yuborilgan_sana", today())
        if izoh:
            self._set(lead["_row"], "izoh", izoh)
        self.log.append_row([now().strftime("%Y-%m-%d %H:%M:%S"), lead["username"], status])
        return True

    def save_followup(self, username: str, text: str) -> bool:
        """2-xabar matnini saqlaydi va 'eslatma' belgisini qo'yadi (3-marta eslatilmaydi)."""
        lead = self.get(username)
        if not lead:
            return False
        self._set(lead["_row"], "xabar_2", text)
        self._set(lead["_row"], "eslatma", "ha")
        return True

    # ---------- hisobot ----------
    def stats(self, day: str | None = None) -> dict:
        """Kunlik va umumiy raqamlar (Log varag'idan)."""
        day = day or today()
        events = self.log.get_all_values()[1:]
        daily = {s: 0 for s in config.STATUSES}
        ever = {s: set() for s in config.STATUSES}
        for ts, username, status in events:
            if status not in daily:
                continue
            ever[status].add(username)
            if ts.startswith(day):
                daily[status] += 1
        total_sent = len(ever["yuborildi"])
        clients = len(ever["mijoz"])
        return {
            "day": day,
            "daily": daily,
            "total_sent": total_sent,
            "total_clients": clients,
            "conversion": round(clients / total_sent * 100, 1) if total_sent else 0.0,
        }


def _to_float(value: str) -> float:
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return 0.0


if __name__ == "__main__":
    # HAQIQIY Google Sheets bilan sinov. Test qatorini oxirida o'chiradi.
    print("Google Sheets'ga ulanmoqda...")
    sh = Sheets.connect()
    print("✅ Ulandi")

    test = {"username": "@test_dokon_123", "shahar": "Toshkent", "obunachi": 5000,
            "ball": 8, "xabar": "=Salom (sinov)"}
    print("1) Qo'shish        :", sh.add_leads([test]), "(kutilgan: (1, 0))")
    print("2) Dublikat        :", sh.add_leads([test]), "(kutilgan: (0, 1))")
    print("3) Holat o'zgartir :", sh.set_status("test_dokon_123", "yuborildi"), "(kutilgan: True)")
    print("4) Holat qiymati   :", sh.get("test_dokon_123")["holat"], "(kutilgan: yuborildi)")
    print("5) Statistika      :", sh.stats()["daily"]["yuborildi"], "(bugun kamida 1)")

    row = sh.get("test_dokon_123")["_row"]
    sh.ws.delete_rows(row)
    print("6) Test qatori o'chirildi. Hammasi ishlayapti ✅")
