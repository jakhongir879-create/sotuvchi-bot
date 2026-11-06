"""sheets.py mantiqini internetsiz sinash (soxta Google varag'i bilan). Ishga tushirish: python test_sheets.py"""
import os
from datetime import timedelta

# .env bo'lmasa ham test ishlashi uchun soxta qiymatlar
for k, v in {"TELEGRAM_BOT_TOKEN": "x", "OWNER_TELEGRAM_ID": "1", "ANTHROPIC_API_KEY": "x",
             "APIFY_TOKEN": "x", "SPREADSHEET_ID": "x"}.items():
    os.environ.setdefault(k, v)

import sheets  # noqa: E402
from sheets import Sheets, normalize_username  # noqa: E402


class FakeWS:
    def __init__(self, title):
        self.title, self.data = title, []

    def get_all_values(self):
        return [r[:] for r in self.data]

    def append_row(self, row):
        self.data.append(list(row))

    def append_rows(self, rows, value_input_option=None):
        self.data.extend(list(r) for r in rows)

    def update_cell(self, row, col, value):
        r = self.data[row - 1]
        r.extend([""] * (col - len(r)))
        r[col - 1] = value


def check(name, cond):
    print(("✅" if cond else "❌"), name)
    if not cond:
        raise SystemExit(1)


sh = Sheets(FakeWS("Do'konlar"), FakeWS("Log"))

check("username tozalash", normalize_username("https://www.instagram.com/Butik_UZ/?hl=uz") == "butik_uz"
      and normalize_username("@Butik_UZ") == "butik_uz")

added, skipped = sh.add_leads([
    {"username": "@moda_a", "ball": 6, "xabar": "=SUM(1)"},
    {"username": "moda_b", "ball": "9"},
    {"username": "https://instagram.com/MODA_A/", "ball": 10},  # dublikat (boshqa yozilishda)
    {"username": "moda_c", "ball": 7.5},
    {"username": ""},
])
check("dublikat va bo'sh o'tkazib yuborildi", (added, skipped) == (3, 2))
check("qayta qo'shilsa hammasi dublikat", sh.add_leads([{"username": "moda_b"}]) == (0, 1))
check("holat va link avtomatik", sh.get("moda_b")["holat"] == "yangi"
      and sh.get("moda_b")["link"] == "https://instagram.com/moda_b")
check("ball bo'yicha tartib (9, 7.5, 6)", [r["username"] for r in sh.get_top_new()] == ["moda_b", "moda_c", "moda_a"])
check("limit ishlaydi", len(sh.get_top_new(2)) == 2)

check("holat yangilandi", sh.set_status("MODA_B", "yuborildi", izoh="DM"))
check("yuborilgan_sana yozildi", sh.get("moda_b")["yuborilgan_sana"] == sheets.today())
check("yuborilgan 'yangi' ro'yxatdan chiqdi", "moda_b" not in [r["username"] for r in sh.get_top_new()])
check("noma'lum do'kon -> False", sh.set_status("yoq_dokon", "mijoz") is False)
try:
    sh.set_status("moda_a", "notogri")
    check("noto'g'ri holat rad etildi", False)
except ValueError:
    check("noto'g'ri holat rad etildi", True)

check("bugun yuborilgan hali eslatmaga tushmaydi", sh.followups_due() == [])
old = (sheets.now() - timedelta(days=3)).strftime("%Y-%m-%d")
sh._set(sh.get("moda_b")["_row"], "yuborilgan_sana", old)
check("2 kundan oshgan eslatmaga tushdi", [r["username"] for r in sh.followups_due()] == ["moda_b"])
sh.save_followup("moda_b", "Salom, yana bir bor...")
check("2-xabardan keyin to'xtadi", sh.followups_due() == [])

sh.set_status("moda_c", "yuborildi")
sh.set_status("moda_c", "mijoz")
st = sh.stats()
check("statistika: yuborildi=2, mijoz=1, konversiya 50%",
      st["daily"]["yuborildi"] == 2 and st["daily"]["mijoz"] == 1 and st["conversion"] == 50.0)

print("\nHamma testlar o'tdi 🎉")
