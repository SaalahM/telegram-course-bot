import os
import sqlite3
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
import pandas as pd
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.request import HTTPXRequest
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# --- KEEP-ALIVE WEB SERVER FOR RENDER ---
def run_dummy_server():
    port = int(os.getenv("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()

# Start dummy server in a separate background thread
threading.Thread(target=run_dummy_server, daemon=True).start()

# --- BOT CONFIGURATION ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = os.getenv("DB_PATH", "course_registrations.db")
ADMIN_IDS = [1075393475]

NAME, DEPARTMENT, CLASS_YEAR, PHONE = range(4)

# --- DATABASE INITIALIZATION ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS participants (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT,
            department TEXT,
            class_year TEXT,
            phone TEXT,
            restart_count INTEGER DEFAULT 0
        )
    """)
    cursor.execute("PRAGMA table_info(participants)")
    columns = [column[1] for column in cursor.fetchall()]
    if "restart_count" not in columns:
        cursor.execute("ALTER TABLE participants ADD COLUMN restart_count INTEGER DEFAULT 0")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            session_code TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES participants (user_id),
            UNIQUE(user_id, session_code)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.commit()
    conn.close()

def is_already_registered(user_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM participants WHERE user_id = ? AND full_name IS NOT NULL", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

# --- HANDLERS & FLOWS ---
async def course_overview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    overview_text = (
        "&nbsp;&nbsp;&nbsp;&nbsp;📚 <b>COURSE OVERVIEW & INFORMATION</b>\n\n"
        "Welcome to the training course! Below are the essential details regarding the program structure, schedule, and attendance tracking:\n\n"
        "⏳ <b>Course Duration:</b> 4 Weeks\n"
        "📅 <b>Sessions:</b> 3 Days per week (12 total sessions)\n"
        "🏢 <b>Venue:</b> Tijara-tara Masjid\n"
        "🗣️ <b>Lectures:</b> Delivered by multiple experienced instructors with interactive Q&A sessions.\n\n"
        "🗂️ <b><u>MAJOR TOPICS COVERED</u></b>\n"
        "This program is designed to address the concept of FAMILY RAISING AND SOCIETY BUILDING under topics of:\n"
        "1️⃣ <b>The basics for Society Building</b>\n"
        "2️⃣ <b>Islamic concept of success</b>\n"
        "3️⃣ <b>Islamic World History</b>\n"
        "4️⃣ <b>The Model parents</b>\n\n\n"
        "📌 <b><u>Key Rules & Guidance</u></b>\n"
        "• <b>Registration:</b> Complete /register once to join the database.\n"
        "• <b>Attendance:</b> Use /attend during active class sessions to check in.\n"
        "• <b>Track Progress:</b> Check your record anytime using /mystatus.\n"
        "• <b>Fix Errors:</b> Made a mistake? Use /restart (1-time limit, before first attendance).\n\n"
        "💡 <b>Available Commands:</b>\n"
        "⚡ /overview — View course details and rules\n"
        "⚡ /register — Register as a participant\n"
        "⚡ /restart — Reset registration (1-time use)\n"
        "⚡ /attend — Mark session attendance\n"
        "⚡ /mystatus — Check your attendance record\n"
        "⚡ /cancel — Cancel active registration setup\n\n\n"
        "<blockquote>🔰 PREPARED BY <b>2016BATCH OF PHARMACY MUSLIM STUDENTS</b></blockquote>\n\n"
        "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; FI AMANILLAH 🍃"
    )
    await update.message.reply_text(overview_text, parse_mode="HTML")

async def start_reg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if is_already_registered(user_id):
        await update.message.reply_text("⚠️ *You are already registered!*", parse_mode="Markdown")
        return ConversationHandler.END
    await update.message.reply_text(
        " *الســـــــــــلام عليكم ورحمة اللــــــه👋*\n\n"
        "📝 *Welcome to Course Registration!*\n\n"
        "👉 *Question 1 of 3:* Please enter your *Full Name*:",
        parse_mode="Markdown",
    )
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["full_name"] = update.message.text
    keyboard = [
        [InlineKeyboardButton("🏥 Pharmacy", callback_data="Pharmacy"), InlineKeyboardButton("🩺 Medicine", callback_data="Medicine"), InlineKeyboardButton("🌐 Public Health", callback_data="Public Health")],
        [InlineKeyboardButton("🔬 Medical Lab", callback_data="Medical Lab"), InlineKeyboardButton("💉 Nursing", callback_data="Nursing"), InlineKeyboardButton("🧸 Pediatric", callback_data="Pediatric")],
        [InlineKeyboardButton("🌿 Environmental", callback_data="Environmental"), InlineKeyboardButton("🚑 Emergency Nursing", callback_data="Emergency Nursing"), InlineKeyboardButton("🧠 Psychiatric", callback_data="Psychiatric"), InlineKeyboardButton("⚙️ Other", callback_data="Other")],
    ]
    await update.message.reply_text(f"Thanks *{update.message.text}*!\n\n👉 *Question 2 of 3:* Select your *Department*:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return DEPARTMENT

async def get_department(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["department"] = query.data
    keyboard = [
        [InlineKeyboardButton("1️⃣ 1st Year", callback_data="1st Year"), InlineKeyboardButton("2️⃣ 2nd Year", callback_data="2nd Year")],
        [InlineKeyboardButton("3️⃣ 3rd Year", callback_data="3rd Year"), InlineKeyboardButton("4️⃣ 4th Year", callback_data="4th Year"), InlineKeyboardButton("🎓 5th Year+", callback_data="5th Year+")],
    ]
    await query.edit_message_text(text=f"🏢 Department: *{query.data}*\n\n👉 *Question 3 of 3:* Select *Class / Year*:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return CLASS_YEAR

async def get_class_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["class_year"] = query.data
    await query.edit_message_text(text=f"🎓 Class: *{query.data}*\n\n👉 *Final Step:* Type your *📞Phone Number*:", parse_mode="Markdown")
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    phone = update.message.text
    full_name, department, class_year = context.user_data.get("full_name", ""), context.user_data.get("department", ""), context.user_data.get("class_year", "")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT restart_count FROM participants WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    current_restarts = row[0] if row else 0

    cursor.execute(
        "INSERT OR REPLACE INTO participants (user_id, full_name, department, class_year, phone, restart_count) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, full_name, department, class_year, phone, current_restarts),
    )
    conn.commit()
    conn.close()

    await update.message.reply_text(f"✨ *REGISTRATION SUCCESSFUL!* ✨\n\n👤 *Name:* {full_name}\n🏢 *Department:* {department}\n🎓 *Class:* {class_year}\n📞 *Phone:* {phone}", parse_mode="Markdown")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ *Registration Canceled.*", parse_mode="Markdown")
    return ConversationHandler.END

async def restart_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not is_already_registered(user_id):
        await update.message.reply_text("⚠️ *Not Registered Yet!*", parse_mode="Markdown")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM attendance WHERE user_id = ?", (user_id,))
    if cursor.fetchone()[0] > 0:
        await update.message.reply_text("🔒 *Restart Locked!* You have already marked attendance.", parse_mode="Markdown")
        conn.close()
        return

    cursor.execute("SELECT restart_count FROM participants WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    restart_count = row[0] if row and row[0] is not None else 0

    if restart_count >= 1:
        await update.message.reply_text("🚫 *Limit Reached!* You have already used your 1-time reset.", parse_mode="Markdown")
        conn.close()
        return

    cursor.execute("DELETE FROM participants WHERE user_id = ?", (user_id,))
    cursor.execute("INSERT INTO participants (user_id, restart_count) VALUES (?, ?)", (user_id, restart_count + 1))
    conn.commit()
    conn.close()
    await update.message.reply_text("🔄 *Registration Reset Successful!* Send /register to start over.", parse_mode="Markdown")

async def attend_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_already_registered(update.message.from_user.id):
        await update.message.reply_text("⚠️ *Registration Required!* Use /register first.", parse_mode="Markdown")
        return
    keyboard = [
        [InlineKeyboardButton("📅 Week 1", callback_data="att_w1"), InlineKeyboardButton("📅 Week 2", callback_data="att_w2")],
        [InlineKeyboardButton("📅 Week 3", callback_data="att_w3"), InlineKeyboardButton("📅 Week 4", callback_data="att_w4")],
    ]
    await update.message.reply_text("📋 *ATTENDANCE CHECK-IN*\n\nSelect Week:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def handle_attendance_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data, user_id = query.data, query.from_user.id

    if data.startswith("att_w"):
        w = data.replace("att_w", "")
        keyboard = [[InlineKeyboardButton(f"{d}️⃣ Day {d}", callback_data=f"mark_week{w}_day{d}") for d in range(1, 4)]]
        await query.edit_message_text(f"📅 *Week {w}:* Select Day:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    if data.startswith("mark_"):
        req_session = data.replace("mark_", "")
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM system_config WHERE key = 'active_session'")
        row = cursor.fetchone()
        active = row[0] if row else None

        if not active or active != req_session:
            await query.edit_message_text("🔒 *Attendance Closed or Session Mismatch!*", parse_mode="Markdown")
            conn.close()
            return

        try:
            cursor.execute("INSERT INTO attendance (user_id, session_code) VALUES (?, ?)", (user_id, req_session))
            conn.commit()
            await query.edit_message_text(f"✅ *Attendance Recorded!* ({req_session.upper()})", parse_mode="Markdown")
        except sqlite3.IntegrityError:
            await query.edit_message_text("⚠️ *Already Recorded!*", parse_mode="Markdown")
        finally:
            conn.close()

async def my_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT full_name, department, class_year, phone, restart_count FROM participants WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()

    if not user or user[0] is None:
        await update.message.reply_text("⚠️ *Not Registered!*", parse_mode="Markdown")
        conn.close()
        return

    full_name, department, class_year, phone, restart_count = user
    cursor.execute("SELECT session_code FROM attendance WHERE user_id = ?", (user_id,))
    attended = [r[0].upper() for r in cursor.fetchall()]
    conn.close()

    msg = (
        f"📋 *YOUR PROFILE*\n\n👤 *Name:* {full_name}\n🏢 *Dept:* {department}\n"
        f"🎓 *Class:* {class_year}\n📞 *Phone:* {phone}\n\n"
        f"📊 *Attended:* {len(attended)}/12 sessions\n✅ *Sessions:* {', '.join(attended) if attended else 'None'}"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def open_attendance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id not in ADMIN_IDS or not context.args:
        return
    session_code = context.args[0].lower()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO system_config (key, value) VALUES ('active_session', ?)", (session_code,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"🟢 *ATTENDANCE OPENED:* {session_code}", parse_mode="Markdown")

async def close_attendance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id not in ADMIN_IDS:
        return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM system_config WHERE key = 'active_session'")
    conn.commit()
    conn.close()
    await update.message.reply_text("🔴 *ATTENDANCE CLOSED*", parse_mode="Markdown")

async def export_excel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id not in ADMIN_IDS:
        return
    excel_path = "attendance_matrix.xlsx"
    try:
        conn = sqlite3.connect(DB_PATH)
        df_students = pd.read_sql_query("SELECT user_id, full_name, department, class_year, phone FROM participants WHERE full_name IS NOT NULL", conn)
        df_attendance = pd.read_sql_query("SELECT user_id, session_code FROM attendance", conn)
        conn.close()

        all_sessions = [f"week{w}_day{d}" for w in range(1, 5) for d in range(1, 4)]
        for session in all_sessions:
            attended_users = df_attendance[df_attendance["session_code"] == session]["user_id"].tolist() if not df_attendance.empty else []
            df_students[session.upper()] = df_students["user_id"].apply(lambda uid: "Present" if uid in attended_users else "Absent")

        df_students["TOTAL_ATTENDED"] = (df_students[[s.upper() for s in all_sessions]] == "Present").sum(axis=1)
        df_export = df_students.drop(columns=["user_id"]).rename(columns={
            "full_name": "Full Name", "department": "Department", "class_year": "Class / Year",
            "phone": "Phone Number", "TOTAL_ATTENDED": "Total Sessions Attended (out of 12)"
        })
        df_export.to_excel(excel_path, index=False, engine="openpyxl")

        with open(excel_path, "rb") as f:
            await context.bot.send_document(chat_id=update.effective_chat.id, document=f, filename="Attendance_Matrix.xlsx")
    finally:
        if os.path.exists(excel_path):
            os.remove(excel_path)

# --- STARTUP ---
if __name__ == "__main__":
    init_db()
    req = HTTPXRequest(connection_pool_size=20, connect_timeout=15.0, read_timeout=15.0)
    app = ApplicationBuilder().token(BOT_TOKEN).request(req).concurrent_updates(True).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler(["register", "start"], start_reg)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            DEPARTMENT: [CallbackQueryHandler(get_department)],
            CLASS_YEAR: [CallbackQueryHandler(get_class_year)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("overview", course_overview))
    app.add_handler(CommandHandler("restart", restart_registration))
    app.add_handler(CommandHandler("attend", attend_menu))
    app.add_handler(CommandHandler("mystatus", my_status))
    app.add_handler(CallbackQueryHandler(handle_attendance_click, pattern="^(att_w|mark_week)"))
    app.add_handler(CommandHandler("open_attendance", open_attendance))
    app.add_handler(CommandHandler("close_attendance", close_attendance))
    app.add_handler(CommandHandler("export", export_excel))

    print("Bot is live...")
    app.run_polling()