import os
import sqlite3
from datetime import datetime
from io import BytesIO
import qrcode
import telebot
from telebot import types

TOKEN = "8946349098:AAFQKMlUCyl3pFcYC5EEnzDPxlYKKvHMe_8"
SUPER_ADMIN_ID = 5874144878

bot = telebot.TeleBot(TOKEN)
user_states = {}


def init_db():
  conn = sqlite3.connect("attendance.db")
  cursor = conn.cursor()
  cursor.execute(
      "CREATE TABLE IF NOT EXISTS students (telegram_id INTEGER PRIMARY KEY,"
      " full_name TEXT)"
  )
  cursor.execute(
      "CREATE TABLE IF NOT EXISTS admins (telegram_id INTEGER PRIMARY KEY)"
  )
  cursor.execute(
      "CREATE TABLE IF NOT EXISTS attendance (telegram_id INTEGER, date TEXT,"
      " time TEXT, PRIMARY KEY (telegram_id, date))"
  )
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
  if cursor.fetchone():
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
  total = cursor.fetchone()[0]
  cursor.execute("SELECT COUNT(*) FROM attendance WHERE date = ?", (today,))
  present = cursor.fetchone()[0]
  conn.close()
  return total, present


def get_admin_keyboard():
  markup = types.InlineKeyboardMarkup(row_width=2)
  markup.add(
      types.InlineKeyboardButton(
          "➕ Admin qo'shish", callback_data="add_admin"
      ),
      types.InlineKeyboardButton(
          "❌ Admin o'chirish", callback_data="del_admin"
      ),
  )
  markup.add(
      types.InlineKeyboardButton(
          "➕ Talaba qo'shish", callback_data="add_student"
      ),
      types.InlineKeyboardButton(
          "❌ Talaba o'chirish", callback_data="del_student"
      ),
  )
  markup.add(
      types.InlineKeyboardButton(
          "📷 Tayyor QR kodni olish", callback_data="get_qr"
      )
  )
  markup.add(types.InlineKeyboardButton("📊 Statistika", callback_data="stats"))
  return markup


def get_student_keyboard():
  markup = types.InlineKeyboardMarkup()
  markup.add(
      types.InlineKeyboardButton(
          "📷 QR Skaner qilish", callback_data="scan_qr"
      )
  )
  return markup


@bot.message_handler(commands=["start"])
def cmd_start(message):
  add_admin(SUPER_ADMIN_ID)
  user_id = message.from_user.id
  if is_admin(user_id):
    bot.send_message(
        user_id,
        "Assalomu alaykum, Admin! Xush kelibsiz.",
        reply_markup=get_admin_keyboard(),
    )
  elif is_student(user_id):
    bot.send_message(
        user_id,
        "Assalomu alaykum, yotoqxona talabasi!",
        reply_markup=get_student_keyboard(),
    )
  else:
    bot.send_message(
        user_id, "Siz bu botda ro'yxatdan o'tmagansiz yoki talaba emassiz."
    )


@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
  user_id = call.from_user.id

  if call.data == "stats":
    if not is_admin(user_id):
      return bot.answer_callback_query(call.id, "Siz admin emassiz!")
    total, present = get_statistics()
    absent = total - present
    text = (
        f"📊 **Yotoqxona davomat statistikasi:**\n\n👥 Jami talabalar: {total}\n✅"
        f" Bugun kelganlar: {present}\n❌ Hozircha yo'qlar: {absent}"
    )
    bot.send_message(user_id, text, parse_mode="Markdown")

  elif call.data == "get_qr":
    if not is_admin(user_id):
      return bot.answer_callback_query(call.id, "Siz admin emassiz!")
    img = qrcode.make("hostel_attendance_secure_qr_code")
    output = BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    bot.send_photo(
        user_id,
        output,
        caption=(
            "📌 **Tayyor QR kod.**\nTalabalar ushbu QR kodni skaner qilish orqali"
            " kunlik davomatni belgilaydilar."
        ),
        parse_mode="Markdown",
    )

  elif call.data == "add_admin":
    if user_id != SUPER_ADMIN_ID:
      return bot.answer_callback_query(
          call.id, "Faqat bosh admin qo'sha oladi!"
      )
    user_states[user_id] = "waiting_for_admin_id"
    bot.send_message(user_id, "Yangi adminning Telegram ID raqamini yuboring:")

  elif call.data == "del_admin":
    if user_id != SUPER_ADMIN_ID:
      return bot.answer_callback_query(call.id, "Ruxsat yo'q!")
    user_states[user_id] = "waiting_for_del_admin_id"
    bot.send_message(
        user_id, "O'chiriladigan adminning Telegram ID raqamini yuboring:"
    )

  elif call.data == "add_student":
    if not is_admin(user_id):
      return bot.answer_callback_query(call.id, "Ruxsat yo'q!")
    user_states[user_id] = "waiting_for_student_info"
    bot.send_message(
        user_id,
        "Talaba ma'lumotlarini yuboring (Format: `ID F.I.O`)\nMasalan:"
        " `123456789 Anvaraliyev Baxtiyor`",
        parse_mode="Markdown",
    )

  elif call.data == "del_student":
    if not is_admin(user_id):
      return bot.answer_callback_query(call.id, "Ruxsat yo'q!")
    user_states[user_id] = "waiting_for_del_student_id"
    bot.send_message(
        user_id, "O'chiriladigan talabaning Telegram ID raqamini yuboring:"
    )

  elif call.data == "scan_qr":
    if not is_student(user_id):
      return bot.answer_callback_query(
          call.id, "Siz talabalar ro'yxatida emassiz!", show_alert=True
      )
    if mark_attendance(user_id):
      bot.send_message(
          user_id,
          "✅ **Davomatingiz muvaffaqiyatli belgilandi!**",
          parse_mode="Markdown",
      )
    else:
      bot.send_message(
          user_id,
          "⚠️ **Diqqat:** Siz bugun allaqachon davomat qilgansiz!",
          parse_mode="Markdown",
      )

  bot.answer_callback_query(call.id)


@bot.message_handler(func=lambda message: message.from_user.id in user_states)
def handle_states(message):
  user_id = message.from_user.id
  state = user_states.get(user_id)

  if state == "waiting_for_admin_id":
    try:
      new_id = int(message.text)
      add_admin(new_id)
      bot.send_message(user_id, f"✅ Admin {new_id} qo'shildi!")
    except ValueError:
      bot.send_message(user_id, "❌ Faqat raqam yuboring!")
  elif state == "waiting_for_del_admin_id":
    try:
      del_id = int(message.text)
      if del_id == SUPER_ADMIN_ID:
        bot.send_message(user_id, "❌ Bosh adminni o'chirib bo'lmaydi!")
      else:
        remove_admin(del_id)
        bot.send_message(user_id, f"🗑 Admin {del_id} o'chirildi.")
    except ValueError:
      bot.send_message(user_id, "❌ Noto'g'ri format.")
  elif state == "waiting_for_student_info":
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
      bot.send_message(user_id, "❌ Xato format! `ID F.I.O` ko'rinishida yuboring.")
      return
    try:
      s_id = int(parts[0])
      s_name = parts[1]
      add_student(s_id, s_name)
      bot.send_message(
          user_id, f"✅ Talaba qo'shildi:\nID: {s_id}\nIsm: {s_name}"
      )
    except ValueError:
      bot.send_message(user_id, "❌ ID raqam bo'lishi shart!")
  elif state == "waiting_for_del_student_id":
    try:
      s_id = int(message.text)
      remove_student(s_id)
      bot.send_message(user_id, f"🗑 Talaba (ID: {s_id}) o'chirildi.")
    except ValueError:
      bot.send_message(user_id, "❌ Xato format.")

  user_states.pop(user_id, None)


if __name__ == "__main__":
  init_db()
  print("Bot ishga tushdi...")
  bot.infinity_polling()
