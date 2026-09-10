import asyncio
import sqlite3
from datetime import datetime
from io import BytesIO
import qrcode

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# --- SOZLAMALAR ---
TOKEN = "8946349098:AAFQKMlUCyl3pFcYC5EEnzDPxlYKKvHMe_8"
SUPER_ADMIN_ID = 5874144878

bot = Bot(token=TOKEN)
dp = Dispatcher()


# --- BAZA BILAN ISHLASH ---
def init_db():
  conn = sqlite3.connect("attendance.db")
  cursor = conn.cursor()

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            telegram_id INTEGER PRIMARY KEY,
            full_name TEXT
        )
    """)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            telegram_id INTEGER PRIMARY KEY
        )
    """)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            telegram_id INTEGER,
            date TEXT,
            time TEXT,
            PRIMARY KEY (telegram_id, date)
        )
    """)

  conn.commit()
  conn.close()


def add_admin(telegram_id):
  conn = sqlite3.connect("attendance.db")
  cursor = conn.cursor()
  try:
    cursor.execute(
        "INSERT OR IGNORE INTO admins (telegram_id) VALUES (?)", (telegram_id,)
    )
    conn.commit()
    return True
  except:
    return False
  finally:
    conn.close()


def remove_admin(telegram_id):
  conn = sqlite3.connect("attendance.db")
  cursor = conn.cursor()
  cursor.execute("DELETE FROM admins WHERE telegram_id = ?", (telegram_id,))
  conn.commit()
  conn.close()


def is_admin(telegram_id):
  conn = sqlite3.connect("attendance.db")
  cursor = conn.cursor()
  cursor.execute(
      "SELECT telegram_id FROM admins WHERE telegram_id = ?", (telegram_id,)
  )
  res = cursor.fetchone()
  conn.close()
  return res is not None


def add_student(telegram_id, full_name):
  conn = sqlite3.connect("attendance.db")
  cursor = conn.cursor()
  try:
    cursor.execute(
        "INSERT OR REPLACE INTO students (telegram_id, full_name) VALUES (?, ?)",
        (telegram_id, full_name),
    )
    conn.commit()
    return True
  except:
    return False
  finally:
    conn.close()


def remove_student(telegram_id):
  conn = sqlite3.connect("attendance.db")
  cursor = conn.cursor()
  cursor.execute("DELETE FROM students WHERE telegram_id = ?", (telegram_id,))
  cursor.execute("DELETE FROM attendance WHERE telegram_id = ?", (telegram_id,))
  conn.commit()
  conn.close()


def is_student(telegram_id):
  conn = sqlite3.connect("attendance.db")
  cursor = conn.cursor()
  cursor.execute(
      "SELECT telegram_id FROM students WHERE telegram_id = ?", (telegram_id,)
  )
  res = cursor.fetchone()
  conn.close()
  return res is not None


def mark_attendance(telegram_id):
  today = datetime.now().strftime("%Y-%m-%d")
  current_time = datetime.now().strftime("%H:%M:%S")

  conn = sqlite3.connect("attendance.db")
  cursor = conn.cursor()

  cursor.execute(
      "SELECT * FROM attendance WHERE telegram_id = ? AND date = ?",
      (telegram_id, today),
  )
  already = cursor.fetchone()

  if already:
    conn.close()
    return False

  cursor.execute(
      "INSERT INTO attendance (telegram_id, date, time) VALUES (?, ?, ?)",
      (telegram_id, today, current_time),
  )
  conn.commit()
  conn.close()
  return True


def get_statistics():
  conn = sqlite3.connect("attendance.db")
  cursor = conn.cursor()
  today = datetime.now().strftime("%Y-%m-%d")

  cursor.execute("SELECT COUNT(*) FROM students")
  total_students = cursor.fetchone()[0]

  cursor.execute("SELECT COUNT(*) FROM attendance WHERE date = ?", (today,))
  present_today = cursor.fetchone()[0]

  conn.close()
  return total_students, present_today


# --- FSM (STATE) HOLATLAR ---
class AdminStates(StatesGroup):
  waiting_for_admin_id = State()
  waiting_for_del_admin_id = State()
  waiting_for_student_info = State()
  waiting_for_del_student_id = State()


# --- KLAVIATURALAR ---
def get_admin_keyboard():
  return InlineKeyboardMarkup(
      inline_keyboard=[
          [
              InlineKeyboardButton(
                  text="➕ Admin qo'shish", callback_data="add_admin"
              ),
              InlineKeyboardButton(
                  text="❌ Admin o'chirish", callback_data="del_admin"
              ),
          ],
          [
              InlineKeyboardButton(
                  text="➕ Talaba qo'shish", callback_data="add_student"
              ),
              InlineKeyboardButton(
                  text="❌ Talaba o'chirish", callback_data="del_student"
              ),
          ],
          [
              InlineKeyboardButton(
                  text="📷 Tayyor QR kodni olish", callback_data="get_qr"
              )
          ],
          [InlineKeyboardButton(text="📊 Statistika", callback_data="stats")],
      ]
  )


def get_student_keyboard():
  return InlineKeyboardMarkup(
      inline_keyboard=[
          [
              InlineKeyboardButton(
                  text="📷 QR Skaner qilish", callback_data="scan_qr"
              )
          ]
      ]
  )


# --- START BUYRUG'I ---
@dp.message(Command("start"))
async def cmd_start(message: Message):
  user_id = message.from_user.id
  add_admin(SUPER_ADMIN_ID)

  if is_admin(user_id):
    await message.answer(
        "Assalomu alaykum, Admin! Xush kelibsiz.",
        reply_markup=get_admin_keyboard(),
    )
  elif is_student(user_id):
    await message.answer(
        "Assalomu alaykum, yotoqxona talabasi!",
        reply_markup=get_student_keyboard(),
    )
  else:
    await message.answer(
        "Siz bu botda ro'yxatdan o'tmagansiz yoki talaba emassiz."
    )


# --- STATISTIKA ---
@dp.callback_query(F.data == "stats")
async def show_stats(callback: CallbackQuery):
  if not is_admin(callback.from_user.id):
    return await callback.answer("Siz admin emassiz!", show_alert=True)

  total, present = get_statistics()
  absent = total - present

  text = (
      f"📊 **Yotoqxona davomat statistikasi:**\n\n"
      f"👥 Jami talabalar: {total}\n"
      f"✅ Bugun kelganlar: {present}\n"
      f"❌ Hozircha yo'qlar: {absent}"
  )
  await callback.message.answer(text, parse_mode="Markdown")
  await callback.answer()


# --- QR KOD YARATISH ---
@dp.callback_query(F.data == "get_qr")
async def get_qr_code(callback: CallbackQuery):
  if not is_admin(callback.from_user.id):
    return await callback.answer("Siz admin emassiz!", show_alert=True)

  qr_data = "hostel_attendance_secure_qr_code"
  img = qrcode.make(qr_data)
  output = BytesIO()
  img.save(output, format="PNG")
  output.seek(0)

  photo = BufferedInputFile(output.read(), filename="qr.png")
  await callback.message.answer_photo(
      photo=photo,
      caption=(
          "📌 **Tayyor QR kod.**\nTalabalar ushbu QR kodni skaner qilish orqali"
          " kunlik davomatni belgilaydilar (Kun davomida faqat 1 marta)."
      ),
      parse_mode="Markdown",
  )
  await callback.answer()


# --- ADMIN QO'SHISH / O'CHIRISH ---
@dp.callback_query(F.data == "add_admin")
async def start_add_admin(callback: CallbackQuery, state: FSMContext):
  if callback.from_user.id != SUPER_ADMIN_ID:
    return await callback.answer(
        "Faqat bosh admin yangi admin qo'sha oladi!", show_alert=True
    )

  await callback.message.answer("Yangi adminning Telegram ID raqamini yuboring:")
  await state.set_state(AdminStates.waiting_for_admin_id)
  await callback.answer()


@dp.message(AdminStates.waiting_for_admin_id)
async def process_add_admin(message: Message, state: FSMContext):
  try:
    new_admin_id = int(message.text)
    add_admin(new_admin_id)
    await message.answer(f"✅ {new_admin_id} muvaffaqiyatli admin qilindi!")
  except ValueError:
    await message.answer("❌ Xato! Faqat raqamlardan iborat ID yuboring.")
  await state.clear()


@dp.callback_query(F.data == "del_admin")
async def start_del_admin(callback: CallbackQuery, state: FSMContext):
  if callback.from_user.id != SUPER_ADMIN_ID:
    return await callback.answer("Faqat bosh admin huquqiga ega!", show_alert=True)

  await callback.message.answer(
      "O'chirilishi kerak bo'lgan adminning Telegram ID raqamini yuboring:"
  )
  await state.set_state(AdminStates.waiting_for_del_admin_id)
  await callback.answer()


@dp.message(AdminStates.waiting_for_del_admin_id)
async def process_del_admin(message: Message, state: FSMContext):
  try:
    admin_id = int(message.text)
    if admin_id == SUPER_ADMIN_ID:
      await message.answer("❌ Bosh adminni o'chirib bo'lmaydi!")
    else:
      remove_admin(admin_id)
      await message.answer(f"🗑 Admin {admin_id} o'chirildi.")
  except ValueError:
    await message.answer("❌ Noto'g'ri ID format.")
  await state.clear()


# --- TALABA QO'SHISH / O'CHIRISH ---
@dp.callback_query(F.data == "add_student")
async def start_add_student(callback: CallbackQuery, state: FSMContext):
  if not is_admin(callback.from_user.id):
    return await callback.answer("Ruxsat yo'q!", show_alert=True)

  await callback.message.answer(
      "Talaba ma'lumotlarini quyidagi tartibda yuboring:\n\n`Telegram_ID"
      " F.I.O`\nMasalan: `123456789 Anvaraliyev Baxtiyor`",
      parse_mode="Markdown",
  )
  await state.set_state(AdminStates.waiting_for_student_info)
  await callback.answer()


@dp.message(AdminStates.waiting_for_student_info)
async def process_add_student(message: Message, state: FSMContext):
  parts = message.text.split(maxsplit=1)
  if len(parts) < 2:
    await message.answer(
        "❌ Xato format! Qaytadan urinib ko'ring: `ID F.I.O`",
        parse_mode="Markdown",
    )
    return

  try:
    student_id = int(parts[0])
    full_name = parts[1]
    add_student(student_id, full_name)
    await message.answer(
        f"✅ Talaba qo'shildi:\nID: {student_id}\nIsm: {full_name}"
    )
  except ValueError:
    await message.answer("❌ Telegram ID raqam bo'lishi shart!")
  await state.clear()


@dp.callback_query(F.data == "del_student")
async def start_del_student(callback: CallbackQuery, state: FSMContext):
  if not is_admin(callback.from_user.id):
    return await callback.answer("Ruxsat yo'q!", show_alert=True)

  await callback.message.answer(
      "O'chirilishi kerak bo'lgan talabaning Telegram ID raqamini yuboring:"
  )
  await state.set_state(AdminStates.waiting_for_del_student_id)
  await callback.answer()


@dp.message(AdminStates.waiting_for_del_student_id)
async def process_del_student(message: Message, state: FSMContext):
  try:
    student_id = int(message.text)
    remove_student(student_id)
    await message.answer(f"🗑 Talaba (ID: {student_id}) bazadan o'chirildi.")
  except ValueError:
    await message.answer("❌ Noto'g'ri ID format.")
  await state.clear()


# --- TALABA: QR SKANER QILISH ---
@dp.callback_query(F.data == "scan_qr")
async def student_scan_qr(callback: CallbackQuery):
  user_id = callback.from_user.id
  if not is_student(user_id):
    return await callback.answer(
        "Siz talabalar ro'yxatida emassiz!", show_alert=True
    )

  success = mark_attendance(user_id)

  if success:
    await callback.message.answer(
        "✅ **Davomatingiz muvaffaqiyatli belgilandi!** Bugungi kun uchun yozib"
        " olindi.",
        parse_mode="Markdown",
    )
  else:
    await callback.message.answer(
        "⚠️ **Diqqat:** Siz bugun allaqachon davomat qilgansiz! Davomat kun"
        " davomida bir marta belgilanadi.",
        parse_mode="Markdown",
    )

  await callback.answer()


# --- ASOSIY FUNKSIYA ---
async def main():
  init_db()
  print("Bot ishga tushdi...")
  await dp.start_polling(bot)


if __name__ == "__main__":
  asyncio.run(main())
