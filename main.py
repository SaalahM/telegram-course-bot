import os
import threading
from html import escape
from http.server import HTTPServer, SimpleHTTPRequestHandler
# --- KEEP-ALIVE WEB SERVER FOR RENDER ---
def run_dummy_server():
    port = int(os.getenv("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    server.serve_forever()

# Start dummy server in a separate background thread
threading.Thread(target=run_dummy_server, daemon=True).start()
import sqlite3
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

# ==========================================
# CONFIGURATION
# ==========================================
# Reads token from environment variables, falls back to hardcoded string locally
BOT_TOKEN = os.getenv("BOT_TOKEN", "8626983590:AAF-gWsg-QsYPAERGuMFzKlTTQEFuXiJtK0")

# Database path (Uses persistent directory on cloud host, or local file for development)
DB_PATH = os.getenv("DB_PATH", "course_registrations.db")

# List of authorized admin Telegram IDs
ADMIN_IDS = [1075393475]  # Add additional numeric Telegram IDs separated by commas

# Registration states
NAME, DEPARTMENT, CLASS_YEAR, PHONE = range(4)


# ==========================================
# DATABASE INITIALIZATION
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Table for registered participants
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS participants (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT,
            department TEXT,
            class_year TEXT,
            phone TEXT,
            restart_count INTEGER DEFAULT 0
        )
    """
    )

    # Ensure restart_count column exists if updating existing database
    cursor.execute("PRAGMA table_info(participants)")
    columns = [column[1] for column in cursor.fetchall()]
    if "restart_count" not in columns:
        cursor.execute(
            "ALTER TABLE participants ADD COLUMN restart_count INTEGER DEFAULT 0"
        )

    # Table for attendance check-ins
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            session_code TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES participants (user_id),
            UNIQUE(user_id, session_code)
        )
    """
    )

    # Table for tracking admin session toggle
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS system_config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """
    )

    conn.commit()
    conn.close()


def is_already_registered(user_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM participants WHERE user_id = ? AND full_name IS NOT NULL",
        (user_id,),
    )
    result = cursor.fetchone()
    conn.close()
    return result is not None


# ==========================================
# COURSE OVERVIEW COMMAND
# ==========================================
async def course_overview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    overview_text = (
        "        📚 <b>COURSE OVERVIEW & INFORMATION</b>\n\n"
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
        "                                      FI AMANILLAH 🍃"
    )
    await update.message.reply_text(overview_text, parse_mode="HTML")


# ==========================================
# REGISTRATION FLOW
# ==========================================
async def start_reg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if is_already_registered(user_id):
        await update.message.reply_text(
            "⚠️ <b>You are already registered!</b>\n\n"
            "If you made a mistake, you can use /restart to re-register "
            "(allowed once before taking attendance).",
            parse_mode="HTML",
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "<blockquote>👋 الســـــــــــلام عليكم ورحمة اللــــــه "
        "وبركــــــــــــــــــــــــــاته 👋</blockquote>\n\n"
        "📝 <b>Welcome to Course Registration!</b>\n\n"
        "👉 <b>Question 1 of 3:</b> Please enter your <b>Full Name</b>:",
        parse_mode="HTML",
    )
    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    full_name = update.message.text.strip()
    context.user_data["full_name"] = full_name

    keyboard = [
        [
            InlineKeyboardButton("🏥 Pharmacy", callback_data="Pharmacy"),
            InlineKeyboardButton("🩺 Medicine", callback_data="Medicine"),
            InlineKeyboardButton(
                "🌐 Public Health", callback_data="Public Health"
            ),
        ],
        [
            InlineKeyboardButton("🔬 Medical Lab", callback_data="Medical Lab"),
            InlineKeyboardButton("💉 Nursing", callback_data="Nursing"),
            InlineKeyboardButton("🧸 Pediatric", callback_data="Pediatric"),
        ],
        [
            InlineKeyboardButton(
                "🌿 Environmental", callback_data="Environmental"
            ),
            InlineKeyboardButton(
                "🚑 Emergency Nursing", callback_data="Emergency Nursing"
            ),
            InlineKeyboardButton(
                "🧠 Psychiatric", callback_data="Psychiatric"
            ),
            InlineKeyboardButton("⚙️ Other", callback_data="Other"),
        ],
    ]

    await update.message.reply_text(
        f"Thanks <b>{escape(full_name)}</b>!\n\n"
        "👉 <b>Question 2 of 3:</b> Please select your "
        "<b>Department</b> below:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )
    return DEPARTMENT


async def get_department(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    department = query.data
    context.user_data["department"] = department

    keyboard = [
        [
            InlineKeyboardButton("1️⃣ 1st Year", callback_data="1st Year"),
            InlineKeyboardButton("2️⃣ 2nd Year", callback_data="2nd Year"),
        ],
        [
            InlineKeyboardButton("3️⃣ 3rd Year", callback_data="3rd Year"),
            InlineKeyboardButton("4️⃣ 4th Year", callback_data="4th Year"),
            InlineKeyboardButton("🎓 5th Year+", callback_data="5th Year+"),
        ],
    ]

    await query.edit_message_text(
        text=(
            f"🏢 Department set to: <b>{escape(department)}</b>\n\n"
            "👉 <b>Question 3 of 3:</b> Select your current "
            "<b>Class / Year</b>:"
        ),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )
    return CLASS_YEAR


async def get_class_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    class_year = query.data
    context.user_data["class_year"] = class_year

    await query.edit_message_text(
        text=(
            f"🎓 Class set to: <b>{escape(class_year)}</b>\n\n"
            "👉 <b>Final Step:</b> Please type and send your "
            "<b>📞 Phone Number</b>:"
        ),
        parse_mode="HTML",
    )
    return PHONE


async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    phone = update.message.text.strip()
    full_name = context.user_data.get("full_name", "")
    department = context.user_data.get("department", "")
    class_year = context.user_data.get("class_year", "")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT restart_count FROM participants WHERE user_id = ?",
        (user_id,),
    )
    row = cursor.fetchone()
    current_restarts = row[0] if row else 0

    cursor.execute(
        """
        INSERT OR REPLACE INTO participants
        (user_id, full_name, department, class_year, phone, restart_count)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, full_name, department, class_year, phone, current_restarts),
    )
    conn.commit()
    conn.close()

    summary = (
        "✨ <b>REGISTRATION SUCCESSFUL!</b> ✨\n\n"
        f"👤 <b>Name:</b> {escape(full_name)}\n"
        f"🏢 <b>Department:</b> {escape(department)}\n"
        f"🎓 <b>Class:</b> {escape(class_year)}\n"
        f"📞 <b>Phone:</b> {escape(phone)}\n\n"
        "You can now mark attendance using /attend during active sessions.\n"
        "💡 <b>Want to know about the course?</b> "
        "Send /overview to get more information."
    )

    await update.message.reply_text(summary, parse_mode="HTML")
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❌ <b>Registration Canceled.</b>\n\n"
        "Send /register whenever you are ready to try again.",
        parse_mode="HTML",
    )
    return ConversationHandler.END


# ==========================================
# RESTART REGISTRATION COMMAND
# ==========================================
async def restart_registration(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    user_id = update.message.from_user.id

    if not is_already_registered(user_id):
        await update.message.reply_text(
            "⚠️ *Not Registered Yet!*\n\n"
            "You do not have an active registration to reset. Send /register to start.",
            parse_mode="Markdown",
        )
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT COUNT(*) FROM attendance WHERE user_id = ?", (user_id,)
    )
    attendance_count = cursor.fetchone()[0]

    if attendance_count > 0:
        await update.message.reply_text(
            "🔒 *Restart Locked!*\n\n"
            "You cannot reset your registration because you have already marked attendance for class sessions.",
            parse_mode="Markdown",
        )
        conn.close()
        return

    cursor.execute(
        "SELECT restart_count FROM participants WHERE user_id = ?", (user_id,)
    )
    row = cursor.fetchone()
    restart_count = row[0] if row and row[0] is not None else 0

    if restart_count >= 1:
        await update.message.reply_text(
            "🚫 *Limit Reached!*\n\n"
            "You have already used your 1-time registration reset.",
            parse_mode="Markdown",
        )
        conn.close()
        return

    new_restart_count = restart_count + 1
    cursor.execute("DELETE FROM participants WHERE user_id = ?", (user_id,))
    cursor.execute(
        "INSERT INTO participants (user_id, restart_count) VALUES (?, ?)",
        (user_id, new_restart_count),
    )
    conn.commit()
    conn.close()

    await update.message.reply_text(
        "🔄 *Registration Reset Successful!*\n\n"
        "Your details have been cleared. Send /register to enter your correct details.\n"
        "⚠️ *Note:* This was your single allowed reset.",
        parse_mode="Markdown",
    )


# ==========================================
# ATTENDANCE FLOW
# ==========================================
async def attend_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if not is_already_registered(user_id):
        await update.message.reply_text(
            "⚠️ *Registration Required!*\n\n"
            "You must register first using /register before marking attendance.",
            parse_mode="Markdown",
        )
        return

    keyboard = [
        [
            InlineKeyboardButton("📅 Week 1", callback_data="att_w1"),
            InlineKeyboardButton("📅 Week 2", callback_data="att_w2"),
        ],
        [
            InlineKeyboardButton("📅 Week 3", callback_data="att_w3"),
            InlineKeyboardButton("📅 Week 4", callback_data="att_w4"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "📋 *ATTENDANCE CHECK-IN*\n\nSelect the *Week* to mark your attendance:",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )


async def handle_attendance_click(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data.startswith("att_w"):
        week_num = data.replace("att_w", "")
        keyboard = [
            [
                InlineKeyboardButton(
                    "1️⃣ Day 1", callback_data=f"mark_week{week_num}_day1"
                ),
                InlineKeyboardButton(
                    "2️⃣ Day 2", callback_data=f"mark_week{week_num}_day2"
                ),
                InlineKeyboardButton(
                    "3️⃣ Day 3", callback_data=f"mark_week{week_num}_day3"
                ),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"📅 *Week {week_num}:* Select today's class session:",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )
        return

    if data.startswith("mark_"):
        requested_session = data.replace("mark_", "")

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT value FROM system_config WHERE key = 'active_session'"
        )
        active_row = cursor.fetchone()
        active_session = active_row[0] if active_row else None

        if not active_session:
            await query.edit_message_text(
                "🔒 *Attendance Closed!*\n\nAttendance is currently *CLOSED* by the instructor.",
                parse_mode="Markdown",
            )
            conn.close()
            return

        if active_session != requested_session:
            await query.edit_message_text(
                f"❌ *Session Mismatch!*\n\n"
                f"Attendance for *{requested_session}* is not active.\n"
                f"Currently open session: *{active_session}*",
                parse_mode="Markdown",
            )
            conn.close()
            return

        try:
            cursor.execute(
                "INSERT INTO attendance (user_id, session_code) VALUES (?, ?)",
                (user_id, requested_session),
            )
            conn.commit()
            await query.edit_message_text(
                f"✅ *Attendance Recorded!*\n\n"
                f"Session: *{requested_session.upper()}*",
                parse_mode="Markdown",
            )
        except sqlite3.IntegrityError:
            await query.edit_message_text(
                f"⚠️ *Duplicate Check-in!*\n\n"
                f"You have already recorded attendance for *{requested_session.upper()}*.",
                parse_mode="Markdown",
            )
        finally:
            conn.close()


# ==========================================
# USER STATUS COMMAND
# ==========================================
async def my_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT full_name, department, class_year, phone, restart_count FROM participants WHERE user_id = ?",
        (user_id,),
    )
    user = cursor.fetchone()

    if not user or user[0] is None:
        await update.message.reply_text(
            "⚠️ *Not Registered!*\n\nYou are not registered yet. Use /register to get started.",
            parse_mode="Markdown",
        )
        conn.close()
        return

    full_name, department, class_year, phone, restart_count = user

    cursor.execute(
        "SELECT session_code FROM attendance WHERE user_id = ?", (user_id,)
    )
    attended_rows = cursor.fetchall()
    conn.close()

    attended_sessions = [row[0].upper() for row in attended_rows]
    total_attended = len(attended_sessions)
    sessions_str = (
        ", ".join(attended_sessions) if attended_sessions else "None"
    )

    if total_attended > 0:
        restart_note = "🔒 *Registration Locked:* Attendance active."
    elif restart_count >= 1:
        restart_note = "🔒 *Registration Locked:* Reset limit (1/1) reached."
    else:
        restart_note = "💡 *Need to edit info?* Send /restart (allowed once before 1st attendance)."

    msg = (
        "📋 *YOUR PARTICIPANT PROFILE*\n\n"
        f"👤 *Name:* {full_name}\n"
        f"🏢 *Department:* {department}\n"
        f"🎓 *Class:* {class_year}\n"
        f"📞 *Phone:* {phone}\n\n"
        f"📊 *Total Attended:* {total_attended}/12 sessions\n"
        f"✅ *Sessions List:* {sessions_str}\n\n"
        f"{restart_note}"
    )

    await update.message.reply_text(msg, parse_mode="Markdown")


# ==========================================
# ADMIN COMMANDS
# ==========================================
async def open_attendance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id not in ADMIN_IDS:
        await update.message.reply_text(
            "⛔ *Unauthorized Command.*", parse_mode="Markdown"
        )
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ *Missing Session Code!*\n\nExample: /open_attendance week1_day1",
            parse_mode="Markdown",
        )
        return

    session_code = context.args[0].lower()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO system_config (key, value) VALUES ('active_session', ?)",
        (session_code,),
    )
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"🟢 *ATTENDANCE OPENED!*\n\nActive Session: *{session_code}*",
        parse_mode="Markdown",
    )


async def close_attendance(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    if update.message.from_user.id not in ADMIN_IDS:
        await update.message.reply_text(
            "⛔ *Unauthorized Command.*", parse_mode="Markdown"
        )
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM system_config WHERE key = 'active_session'")
    conn.commit()
    conn.close()

    await update.message.reply_text(
        "🔴 *ATTENDANCE CLOSED!*\n\nAttendance is now disabled for all sessions.",
        parse_mode="Markdown",
    )


async def export_excel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id not in ADMIN_IDS:
        await update.message.reply_text(
            "⛔ *Unauthorized Command.*", parse_mode="Markdown"
        )
        return

    excel_path = "attendance_matrix.xlsx"

    try:
        if not os.path.exists(DB_PATH):
            await update.message.reply_text(
                "⚠️ *No registration database found yet.*", parse_mode="Markdown"
            )
            return

        conn = sqlite3.connect(DB_PATH)
        df_students = pd.read_sql_query(
            "SELECT user_id, full_name, department, class_year, phone FROM participants WHERE full_name IS NOT NULL",
            conn,
        )

        if df_students.empty:
            await update.message.reply_text(
                "⚠️ *The database is currently empty or no registered participants found.*",
                parse_mode="Markdown",
            )
            conn.close()
            return

        df_attendance = pd.read_sql_query(
            "SELECT user_id, session_code FROM attendance", conn
        )
        conn.close()

        all_sessions = [
            f"week{w}_day{d}" for w in range(1, 5) for d in range(1, 4)
        ]

        for session in all_sessions:
            if not df_attendance.empty:
                attended_users = df_attendance[
                    df_attendance["session_code"] == session
                ]["user_id"].tolist()
                df_students[session.upper()] = df_students["user_id"].apply(
                    lambda uid: "Present" if uid in attended_users else "Absent"
                )
            else:
                df_students[session.upper()] = "Absent"

        session_cols = [s.upper() for s in all_sessions]
        df_students["TOTAL_ATTENDED"] = (
            df_students[session_cols] == "Present"
        ).sum(axis=1)

        df_export = df_students.drop(columns=["user_id"])
        df_export.rename(
            columns={
                "full_name": "Full Name",
                "department": "Department",
                "class_year": "Class / Year",
                "phone": "Phone Number",
                "TOTAL_ATTENDED": "Total Sessions Attended (out of 12)",
            },
            inplace=True,
        )

        df_export.to_excel(excel_path, index=False, engine="openpyxl")

        await update.message.reply_text(
            "📊 *Generating Attendance Matrix Spreadsheet...*",
            parse_mode="Markdown",
        )

        with open(excel_path, "rb") as file:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=file,
                filename="Course_Attendance_Matrix.xlsx",
                caption="Here is the full participant list with 4-week attendance matrix.",
            )

    except Exception as e:
        await update.message.reply_text(
            f"❌ *Error exporting Excel:* `{str(e)}`", parse_mode="Markdown"
        )
    finally:
        if os.path.exists(excel_path):
            try:
                os.remove(excel_path)
            except OSError:
                pass


# ==========================================
# MAIN APPLICATION STARTUP
# ==========================================
if __name__ == "__main__":
    init_db()

    # Connection pooling setup for high-concurrency environments
    request = HTTPXRequest(
        connection_pool_size=20,
        connect_timeout=15.0,
        read_timeout=15.0,
    )

    # Initialize Application with concurrent update execution
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .request(request)
        .concurrent_updates(True)
        .build()
    )

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler(["register", "start"], start_reg)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            DEPARTMENT: [CallbackQueryHandler(get_department)],
            CLASS_YEAR: [CallbackQueryHandler(get_class_year)],
            PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],allow_reentry=True,
    )

    # Command and Callback Register
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("overview", course_overview))
    app.add_handler(CommandHandler("restart", restart_registration))
    app.add_handler(CommandHandler("attend", attend_menu))
    app.add_handler(CommandHandler("mystatus", my_status))
    app.add_handler(
        CallbackQueryHandler(
            handle_attendance_click, pattern="^(att_w|mark_week)"
        )
    )
    app.add_handler(CommandHandler("open_attendance", open_attendance))
    app.add_handler(CommandHandler("close_attendance", close_attendance))
    app.add_handler(CommandHandler("export", export_excel))

    print("Registration & Attendance Bot is running smoothly...")
    app.run_polling()
