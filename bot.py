import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, ConversationHandler
from telegram.ext.filters import Text, COMMAND
from datetime import datetime, timedelta, date
import logging
from dotenv import load_dotenv
import os
import calendar
import uuid
import asyncio

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_IDS = os.getenv('ADMIN_IDS', '').split(',')  # Comma-separated admin IDs from .env


# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Conversation states
SELECT_DOCTOR, PATIENT_NAME, PATIENT_DOB, CAREGIVER_LINK, CANCEL_BOOKING, ADMIN_ADD, ADMIN_REMOVE, USER_EDIT, BROADCAST, ADMIN_ADD_SLOT, ADMIN_ADD_DOCTOR, SUPPORT_REQUEST = range(12)

# Booking tuple indices
BOOKING_FIELDS = {
    'id': 0,
    'user_id': 1,
    'patient_name': 2,
    'patient_dob': 3,
    'time_slot': 4,
    'booking_date': 5,
    'doctor_id': 6,
    'status': 7
}

# Initialize database
def init_db():
    try:
        conn = sqlite3.connect('doctomed.db', timeout=10)
        conn.execute('PRAGMA journal_mode=WAL')  # Enable Write-Ahead Logging
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS bookings 
                     (id INTEGER PRIMARY KEY, user_id INTEGER, patient_name TEXT, 
                      patient_dob TEXT, time_slot TEXT, booking_date TEXT, doctor_id INTEGER, 
                      status TEXT, confirmed INTEGER)''')
        c.execute('''CREATE TABLE IF NOT EXISTS users 
                     (user_id INTEGER PRIMARY KEY, is_caregiver INTEGER, linked_patient TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS admins 
                     (user_id INTEGER PRIMARY KEY)''')
        c.execute('''CREATE TABLE IF NOT EXISTS doctor_slots 
                     (id INTEGER PRIMARY KEY, booking_date TEXT, time_slot TEXT, doctor_id INTEGER, is_available INTEGER)''')
        c.execute('''CREATE TABLE IF NOT EXISTS doctors 
                     (user_id INTEGER PRIMARY KEY, name TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS support_requests 
                     (id INTEGER PRIMARY KEY, user_id INTEGER, message TEXT, timestamp TEXT, status TEXT)''')
        # Populate admins from ADMIN_IDS
        for admin_id in ADMIN_IDS:
            try:
                admin_id = int(admin_id.strip())
                c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (admin_id,))
            except ValueError:
                logger.warning(f"Invalid admin ID in ADMIN_IDS: {admin_id}")
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Database initialization error: {e}")
    finally:
        conn.close()

# Available time slots
TIME_SLOTS = ["09:00", "10:00", "11:00", "14:00", "15:00", "16:00"]

# Check if user is admin
def is_admin(user_id):
    conn = sqlite3.connect('doctomed.db', timeout=10)
    conn.execute('PRAGMA journal_mode=WAL')
    try:
        c = conn.cursor()
        c.execute('SELECT user_id FROM admins WHERE user_id = ?', (user_id,))
        result = c.fetchone()
        return result is not None
    except sqlite3.Error as e:
        logger.error(f"Error checking admin status for user {user_id}: {e}")
        return False
    finally:
        conn.close()

# Get available doctor slots for a specific doctor
def get_available_slots(doctor_id):
    conn = sqlite3.connect('doctomed.db', timeout=10)
    conn.execute('PRAGMA journal_mode=WAL')
    try:
        c = conn.cursor()
        today = date.today()
        end_date = today + timedelta(days=7)
        c.execute('''SELECT ds.booking_date, ds.time_slot, d.name 
                     FROM doctor_slots ds 
                     JOIN doctors d ON ds.doctor_id = d.user_id
                     WHERE ds.is_available = 1 AND ds.doctor_id = ?
                     AND ds.booking_date >= ? AND ds.booking_date <= ?
                     AND (ds.booking_date, ds.time_slot) NOT IN (
                         SELECT booking_date, time_slot FROM bookings WHERE confirmed = 1 AND doctor_id = ?
                     )
                     ORDER BY ds.booking_date, ds.time_slot''', 
                     (doctor_id, today.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'), doctor_id))
        slots = c.fetchall()
        return slots
    except sqlite3.Error as e:
        logger.error(f"Error fetching slots for doctor {doctor_id}: {e}")
        return []
    finally:
        conn.close()

# Get all doctors
def get_all_doctors():
    conn = sqlite3.connect('doctomed.db', timeout=10)
    conn.execute('PRAGMA journal_mode=WAL')
    try:
        c = conn.cursor()
        c.execute('SELECT user_id, name FROM doctors')
        doctors = c.fetchall()
        return doctors
    except sqlite3.Error as e:
        logger.error(f"Error fetching doctors: {e}")
        return []
    finally:
        conn.close()

# Get doctor by ID
def get_doctor_by_id(doctor_id):
    conn = sqlite3.connect('doctomed.db', timeout=10)
    conn.execute('PRAGMA journal_mode=WAL')
    try:
        c = conn.cursor()
        c.execute('SELECT user_id, name FROM doctors WHERE user_id = ?', (doctor_id,))
        doctor = c.fetchone()
        return doctor
    except sqlite3.Error as e:
        logger.error(f"Error fetching doctor {doctor_id}: {e}")
        return None
    finally:
        conn.close()

# Get user bookings
def get_user_bookings(user_id):
    conn = sqlite3.connect('doctomed.db', timeout=10)
    conn.execute('PRAGMA journal_mode=WAL')
    try:
        c = conn.cursor()
        c.execute('SELECT id, user_id, patient_name, patient_dob, time_slot, booking_date, doctor_id, status FROM bookings WHERE user_id = ? AND confirmed = 1', (user_id,))
        bookings = c.fetchall()
        return bookings
    except sqlite3.Error as e:
        logger.error(f"Error fetching bookings for user {user_id}: {e}")
        return []
    finally:
        conn.close()

# Get all bookings
def get_all_bookings():
    conn = sqlite3.connect('doctomed.db', timeout=10)
    conn.execute('PRAGMA journal_mode=WAL')
    try:
        c = conn.cursor()
        c.execute('SELECT id, user_id, patient_name, patient_dob, time_slot, booking_date, doctor_id, status FROM bookings WHERE confirmed = 1')
        bookings = c.fetchall()
        return bookings
    except sqlite3.Error as e:
        logger.error(f"Error fetching all bookings: {e}")
        return []
    finally:
        conn.close()

# Get booking by ID
def get_booking_by_id(booking_id):
    conn = sqlite3.connect('doctomed.db', timeout=10)
    conn.execute('PRAGMA journal_mode=WAL')
    try:
        c = conn.cursor()
        c.execute('SELECT id, user_id, patient_name, patient_dob, time_slot, booking_date, doctor_id, status FROM bookings WHERE id = ?', (booking_id,))
        booking = c.fetchone()
        return booking
    except sqlite3.Error as e:
        logger.error(f"Error fetching booking {booking_id}: {e}")
        return None
    finally:
        conn.close()

# Get all users
def get_all_users():
    conn = sqlite3.connect('doctomed.db', timeout=10)
    conn.execute('PRAGMA journal_mode=WAL')
    try:
        c = conn.cursor()
        c.execute('SELECT user_id, is_caregiver, linked_patient FROM users')
        users = c.fetchall()
        return users
    except sqlite3.Error as e:
        logger.error(f"Error fetching users: {e}")
        return []
    finally:
        conn.close()

# Get user by ID
def get_user_by_id(user_id):
    conn = sqlite3.connect('doctomed.db', timeout=10)
    conn.execute('PRAGMA journal_mode=WAL')
    try:
        c = conn.cursor()
        c.execute('SELECT user_id, is_caregiver, linked_patient FROM users WHERE user_id = ?', (user_id,))
        user = c.fetchone()
        return user
    except sqlite3.Error as e:
        logger.error(f"Error fetching user {user_id}: {e}")
        return None
    finally:
        conn.close()

# Get available slots for all doctors
def get_available_slots_for_all_doctors():
    conn = sqlite3.connect('doctomed.db', timeout=10)
    conn.execute('PRAGMA journal_mode=WAL')
    try:
        c = conn.cursor()
        today = date.today()
        end_date = today + timedelta(days=7)
        c.execute('''SELECT ds.booking_date, ds.time_slot, d.name 
                     FROM doctor_slots ds 
                     JOIN doctors d ON ds.doctor_id = d.user_id
                     WHERE ds.is_available = 1 
                     AND ds.booking_date >= ? AND ds.booking_date <= ?
                     ORDER BY ds.booking_date, ds.time_slot''', 
                     (today.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')))
        slots = c.fetchall()
        return slots
    except sqlite3.Error as e:
        logger.error(f"Error fetching all doctor slots: {e}")
        return []
    finally:
        conn.close()

# Delete user
def delete_user(user_id):
    conn = sqlite3.connect('doctomed.db', timeout=10)
    conn.execute('PRAGMA journal_mode=WAL')
    try:
        c = conn.cursor()
        c.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
        c.execute('UPDATE bookings SET confirmed = 0 WHERE user_id = ?', (user_id,))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Error deleting user {user_id}: {e}")
    finally:
        conn.close()

# Get all admins
def get_all_admins():
    conn = sqlite3.connect('doctomed.db', timeout=10)
    conn.execute('PRAGMA journal_mode=WAL')
    try:
        c = conn.cursor()
        c.execute('SELECT user_id FROM admins')
        admins = c.fetchall()
        return admins
    except sqlite3.Error as e:
        logger.error(f"Error fetching admins: {e}")
        return []
    finally:
        conn.close()

# Add admin
def add_admin(admin_id):
    conn = sqlite3.connect('doctomed.db', timeout=10)
    conn.execute('PRAGMA journal_mode=WAL')
    try:
        c = conn.cursor()
        c.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (admin_id,))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Error adding admin {admin_id}: {e}")
    finally:
        conn.close()

# Remove admin
def remove_admin(admin_id):
    conn = sqlite3.connect('doctomed.db', timeout=10)
    conn.execute('PRAGMA journal_mode=WAL')
    try:
        c = conn.cursor()
        c.execute('DELETE FROM admins WHERE user_id = ?', (admin_id,))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Error removing admin {admin_id}: {e}")
    finally:
        conn.close()

# Cancel booking
def cancel_booking(booking_id):
    conn = sqlite3.connect('doctomed.db', timeout=10)
    conn.execute('PRAGMA journal_mode=WAL')
    try:
        c = conn.cursor()
        c.execute('SELECT booking_date, time_slot, doctor_id, status, confirmed, patient_name, user_id FROM bookings WHERE id = ?', (booking_id,))
        booking = c.fetchone()
        if not booking:
            logger.error(f"Booking ID {booking_id} not found")
            return False, "Booking not found."
        if booking[4] == 0 or booking[3] == 'cancelled':
            logger.warning(f"Booking ID {booking_id} is already cancelled")
            return False, "Booking is already cancelled."
        
        c.execute('UPDATE bookings SET confirmed = 0, status = ? WHERE id = ?', ('cancelled', booking_id))
        c.execute('UPDATE doctor_slots SET is_available = 1 WHERE booking_date = ? AND time_slot = ? AND doctor_id = ?',
                  (booking[0], booking[1], booking[2]))
        conn.commit()
        return True, booking
    except sqlite3.Error as e:
        logger.error(f"Error cancelling booking {booking_id}: {e}")
        return False, str(e)
    finally:
        conn.close()

# Log support request
def log_support_request(user_id, message):
    conn = sqlite3.connect('doctomed.db', timeout=10)
    conn.execute('PRAGMA journal_mode=WAL')
    try:
        c = conn.cursor()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        c.execute('INSERT INTO support_requests (user_id, message, timestamp, status) VALUES (?, ?, ?, ?)',
                  (user_id, message, timestamp, 'open'))
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"Error logging support request for user {user_id}: {e}")
        return False
    finally:
        conn.close()

# Get system stats
def get_system_stats():
    conn = sqlite3.connect('doctomed.db', timeout=10)
    conn.execute('PRAGMA journal_mode=WAL')
    try:
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM bookings WHERE confirmed = 1')
        total_bookings = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM users')
        active_users = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM admins')
        total_admins = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM doctors')
        total_doctors = c.fetchone()[0]
        return {
            'total_bookings': total_bookings,
            'active_users': active_users,
            'total_admins': total_admins,
            'total_doctors': total_doctors
        }
    except sqlite3.Error as e:
        logger.error(f"Error fetching system stats: {e}")
        return {'total_bookings': 0, 'active_users': 0, 'total_admins': 0, 'total_doctors': 0}
    finally:
        conn.close()

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"User {user_id} started the bot")
    context.user_data.clear()  # Reset state on /start
    try:
        if is_admin(user_id):
            keyboard = [
                [InlineKeyboardButton("Admin Panel", callback_data='admin_panel')],
                [InlineKeyboardButton("Access User Features", callback_data='user_mode')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            welcome_message = (
                "👋 Welcome, Admin! Access the Admin Panel to manage the Doctomed Call Service.\n"
                "You can also switch to user features if needed."
            )
        else:
            keyboard = [
                [InlineKeyboardButton("Book Now", callback_data='book')],
                [InlineKeyboardButton("Cancel Booking", callback_data='cancel_booking')],
                [InlineKeyboardButton("Service Info", callback_data='info')],
                [InlineKeyboardButton("Contact Support", callback_data='support')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            welcome_message = (
                "👋 Welcome to Doctomed Call Service – professional care over the phone.\n"
                "📞 This service uses a Swiss premium number: 0900 0900 90\n"
                "Would you like to book a call?"
            )
        await update.message.reply_text(welcome_message, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error sending start message to user {user_id}: {e}", exc_info=True)
        await update.message.reply_text("⚠️ An error occurred. Please try again or contact support.")

# Cancel command
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"User {user_id} issued /cancel command")
    context.user_data.clear()  # Reset conversation state
    try:
        await update.message.reply_text("✅ Conversation reset. Use /start to begin again.")
    except Exception as e:
        logger.error(f"Error sending cancel response to user {user_id}: {e}")
    return ConversationHandler.END

# Health check command
async def health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        try:
            await update.message.reply_text("⚠️ Unauthorized access.")
        except Exception as e:
            logger.error(f"Error sending unauthorized message to user {user_id}: {e}")
        return
    try:
        stats = get_system_stats()
        conn = sqlite3.connect('doctomed.db', timeout=10)
        conn.close()
        health_status = "✅ Database: Connected\n"
        health_status += f"📊 Total Bookings: {stats['total_bookings']}\n"
        health_status += f"👥 Active Users: {stats['active_users']}\n"
        health_status += f"👨‍⚕️ Doctors: {stats['total_doctors']}\n"
        await update.message.reply_text(health_status)
    except Exception as e:
        logger.error(f"Health check failed for user {user_id}: {e}", exc_info=True)
        try:
            await update.message.reply_text(f"⚠️ Health check failed: {e}")
        except Exception as reply_error:
            logger.error(f"Failed to send health check error to user {user_id}: {reply_error}")

# Select doctor
async def select_doctor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        doctors = get_all_doctors()
        if not doctors:
            logger.warning("No doctors available in the database")
            await update.callback_query.message.reply_text("⚠️ No doctors available. Please contact support.")
            return ConversationHandler.END
        
        keyboard = [[InlineKeyboardButton(f"{doctor[1]}", callback_data=f'doctor_{doctor[0]}')] for doctor in doctors]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.message.reply_text(
            "👨‍⚕️ Please select a doctor to view their schedule:",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Error sending doctor selection to user {update.effective_user.id}: {e}", exc_info=True)
        try:
            await update.callback_query.message.reply_text("⚠️ An error occurred. Please try again or use /start to reset.")
        except Exception as reply_error:
            logger.error(f"Failed to send error message to user {update.effective_user.id}: {reply_error}")
        context.user_data.clear()
        return ConversationHandler.END
    return SELECT_DOCTOR

# Show calendar
async def show_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE, doctor_id):
    try:
        doctor = get_doctor_by_id(doctor_id)
        if not doctor:
            logger.warning(f"Doctor {doctor_id} not found")
            await update.callback_query.message.reply_text("⚠️ Doctor not found.")
            return ConversationHandler.END
        
        available_slots = get_available_slots(doctor_id)
        if not available_slots:
            logger.info(f"No available slots for doctor {doctor_id}")
            await update.callback_query.message.reply_text(
                f"⚠️ No available slots for {doctor[1]}. Please try another doctor or contact support."
            )
            return ConversationHandler.END
        
        slots_by_date = {}
        for slot in available_slots:
            booking_date = slot[0]
            if booking_date not in slots_by_date:
                slots_by_date[booking_date] = []
            slots_by_date[booking_date].append(slot[1])
        
        message = f"📅 {doctor[1]}'s Schedule (Next 7 Days)\n\n"
        for booking_date in sorted(slots_by_date.keys()):
            booking_date_dt = datetime.strptime(booking_date, '%Y-%m-%d')
            day_name = calendar.day_name[booking_date_dt.weekday()]
            message += f"🗓️ {booking_date} ({day_name})\n"
            for time_slot in sorted(slots_by_date[booking_date]):
                message += f"- {time_slot} ✅\n"
            message += "\n"
        
        keyboard = []
        for booking_date in sorted(slots_by_date.keys()):
            for time_slot in sorted(slots_by_date[booking_date]):
                callback_data = f"slot_{time_slot}_{booking_date}_{doctor_id}"
                keyboard.append([InlineKeyboardButton(time_slot, callback_data=callback_data)])
        keyboard.append([InlineKeyboardButton("Back to Doctors", callback_data='select_doctor')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.message.reply_text(
            message + "Select a slot to book:",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Error sending calendar for doctor {doctor_id} to user {update.effective_user.id}: {e}", exc_info=True)
        try:
            await update.callback_query.message.reply_text("⚠️ An error occurred. Please try again or use /start to reset.")
        except Exception as reply_error:
            logger.error(f"Failed to send error message to user {update.effective_user.id}: {reply_error}")
        context.user_data.clear()
        return ConversationHandler.END
    return SELECT_DOCTOR

# Button callback
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    logger.info(f"User {user_id} triggered callback: {query.data}")
    
    try:
        is_user_admin = is_admin(user_id)
        if query.data == 'user_mode' and is_user_admin:
            keyboard = [
                [InlineKeyboardButton("Book Now", callback_data='book')],
                [InlineKeyboardButton("Cancel Booking", callback_data='cancel_booking')],
                [InlineKeyboardButton("Service Info", callback_data='info')],
                [InlineKeyboardButton("Contact Support", callback_data='support')],
                [InlineKeyboardButton("Back to Admin Panel", callback_data='admin_panel')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(
                "Switched to user mode. Select an action:",
                reply_markup=reply_markup
            )
            return
        elif query.data == 'book' and not (is_user_admin and 'admin_panel' in query.data):
            await select_doctor(update, context)
            return SELECT_DOCTOR
        elif query.data == 'select_doctor' and not (is_user_admin and 'admin_panel' in query.data):
            await select_doctor(update, context)
            return SELECT_DOCTOR
        elif query.data.startswith('doctor_') and not (is_user_admin and 'admin_panel' in query.data):
            doctor_id = int(query.data.split('_')[1])
            await show_calendar(update, context, doctor_id)
            return SELECT_DOCTOR
        elif query.data == 'cancel_booking' and not (is_user_admin and 'admin_panel' in query.data):
            bookings = get_user_bookings(user_id)
            if not bookings:
                await query.message.reply_text("You have no active bookings to cancel.")
                return
            keyboard = []
            for b in bookings:
                patient_name = b[BOOKING_FIELDS['patient_name']]
                time_slot = b[BOOKING_FIELDS['time_slot']]
                booking_date = b[BOOKING_FIELDS['booking_date']]
                booking_id = b[BOOKING_FIELDS['id']]
                button_text = f"{patient_name} at {time_slot} on {booking_date}"
                callback_data = f'cancel_{booking_id}'
                keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text("Select a booking to cancel:", reply_markup=reply_markup)
        elif query.data.startswith('cancel_') and not (is_user_admin and 'admin_panel' in query.data):
            booking_id = int(query.data.split('_')[1])
            success, result = cancel_booking(booking_id)
            if success:
                booking = result
                await query.message.reply_text(
                    f"✅ Booking for {booking[5]} on {booking[0]} at {booking[1]} cancelled successfully."
                )
                try:
                    doctor = get_doctor_by_id(booking[2])
                    doctor_name = doctor[1] if doctor else "Doctor"
                    await context.bot.send_message(
                        chat_id=booking[2],
                        text=(
                            f"🔔 Booking cancelled:\n"
                            f"Patient: {booking[5]}\n"
                            f"Date: {booking[0]}\n"
                            f"Time: {booking[1]}"
                        )
                    )
                except Exception as e:
                    logger.error(f"Failed to notify doctor ID {booking[2]} about cancellation: {e}")
                    await query.message.reply_text("⚠️ Booking cancelled, but failed to notify the doctor.")
            else:
                await query.message.reply_text(f"⚠️ Failed to cancel booking: {result}")
        elif query.data == 'info' and not (is_user_admin and 'admin_panel' in query.data):
            doctors = get_all_doctors()
            doctor_list = "\n".join([f"- {doctor[1]}" for doctor in doctors]) if doctors else "No doctors available at the moment."
            await query.message.reply_text(
                "ℹ️ *Doctomed Call Service*\n\n"
                "We provide professional medical consultations via phone using a Swiss premium number: *0900 0900 90*.\n\n"
                "🕒 *Availability*: Monday to Friday, 9:00–17:00\n"
                "👨‍⚕️ *Our Doctors*:\n" + doctor_list + "\n\n"
                "🌐 Visit our website: https://doctomed.ch\n"
                "All our doctors are Swiss-certified, ensuring high-quality care."
            )
        elif query.data == 'support' and not (is_user_admin and 'admin_panel' in query.data):
            context.user_data['state'] = SUPPORT_REQUEST
            await query.message.reply_text(
                "📧 Please describe your issue or question, and our support team will get back to you.\n"
                "You can also contact us at support@doctomed.ch or call +41 44 123 45 67."
            )
            return SUPPORT_REQUEST
        elif query.data == 'admin_panel' and is_user_admin:
            keyboard = [
                [
                    InlineKeyboardButton("View Bookings", callback_data='admin_bookings'),
                    InlineKeyboardButton("Manage Users", callback_data='admin_users'),
                    InlineKeyboardButton("Add Admin", callback_data='admin_add')
                ],
                [
                    InlineKeyboardButton("Remove Admin", callback_data='admin_remove'),
                    InlineKeyboardButton("Manage Slots", callback_data='admin_slots'),
                    InlineKeyboardButton("Manage Doctors", callback_data='admin_doctors')
                ],
                [
                    InlineKeyboardButton("System Stats", callback_data='admin_stats'),
                    InlineKeyboardButton("Broadcast", callback_data='admin_broadcast'),
                    InlineKeyboardButton("Back", callback_data='back_to_start')
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text("Admin Panel:", reply_markup=reply_markup)
        elif query.data == 'back_to_start' and is_user_admin:
            await start(update, context)
        elif query.data == 'admin_bookings' and is_user_admin:
            bookings = get_all_bookings()
            if not bookings:
                await query.message.reply_text("No bookings found.")
                return
            keyboard = []
            for b in bookings:
                booking_id = b[BOOKING_FIELDS['id']]
                patient_name = b[BOOKING_FIELDS['patient_name']]
                booking_date = b[BOOKING_FIELDS['booking_date']]
                time_slot = b[BOOKING_FIELDS['time_slot']]
                button_text = f"ID: {booking_id} - {patient_name} ({booking_date} {time_slot})"
                callback_data = f'admin_booking_{booking_id}'
                keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text("Select a booking to manage:", reply_markup=reply_markup)
        elif query.data.startswith('admin_booking_') and is_user_admin:
            booking_id = int(query.data.split('_')[2])
            booking = get_booking_by_id(booking_id)
            if booking:
                keyboard = [
                    [InlineKeyboardButton("Cancel Booking", callback_data=f'admin_cancel_{booking_id}')],
                    [InlineKeyboardButton("Back to Bookings", callback_data='admin_bookings')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.message.reply_text(
                    f"Booking ID: {booking[BOOKING_FIELDS['id']]}\n"
                    f"User ID: {booking[BOOKING_FIELDS['user_id']]}\n"
                    f"Patient: {booking[BOOKING_FIELDS['patient_name']]}\n"
                    f"DOB: {booking[BOOKING_FIELDS['patient_dob']]}\n"
                    f"Slot: {booking[BOOKING_FIELDS['time_slot']]} on {booking[BOOKING_FIELDS['booking_date']]}\n"
                    f"Doctor ID: {booking[BOOKING_FIELDS['doctor_id']]}\n"
                    f"Status: {booking[BOOKING_FIELDS['status']]}",
                    reply_markup=reply_markup
                )
        elif query.data.startswith('admin_cancel_') and is_user_admin:
            booking_id = int(query.data.split('_')[2])
            success, result = cancel_booking(booking_id)
            if success:
                await query.message.reply_text(f"✅ Booking ID {booking_id} cancelled.")
            else:
                await query.message.reply_text(f"⚠️ Failed to cancel booking: {result}")
        elif query.data == 'admin_users' and is_user_admin:
            users = get_all_users()
            if not users:
                await query.message.reply_text("No users found.")
                return
            keyboard = [[InlineKeyboardButton(f"User ID: {u[0]}", callback_data=f'admin_user_{u[0]}')] for u in users]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text("Select a user to manage:", reply_markup=reply_markup)
        elif query.data.startswith('admin_user_') and is_user_admin:
            user_id = int(query.data.split('_')[2])
            user = get_user_by_id(user_id)
            if user:
                keyboard = [
                    [InlineKeyboardButton("Edit User", callback_data=f'admin_edit_user_{user_id}')],
                    [InlineKeyboardButton("Delete User", callback_data=f'admin_delete_user_{user_id}')],
                    [InlineKeyboardButton("Back to Users", callback_data='admin_users')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.message.reply_text(
                    f"User ID: {user[0]}\nCaregiver: {'Yes' if user[1] else 'No'}\nLinked Patient: {user[2] or 'None'}",
                    reply_markup=reply_markup
                )
        elif query.data.startswith('admin_edit_user_') and is_user_admin:
            context.user_data['edit_user_id'] = int(query.data.split('_')[3])
            await query.message.reply_text(
                "Enter new TFSUser details (format: is_caregiver,linked_patient)\n"
                "Example: 1,John Doe"
            )
            return USER_EDIT
        elif query.data.startswith('admin_delete_user_') and is_user_admin:
            user_id = int(query.data.split('_')[3])
            delete_user(user_id)
            await query.message.reply_text(f"✅ User ID {user_id} deleted.")
        elif query.data == 'admin_add' and is_user_admin:
            await query.message.reply_text("Enter the Telegram User ID of the new admin:")
            return ADMIN_ADD
        elif query.data == 'admin_remove' and is_user_admin:
            admins = get_all_admins()
            if not admins:
                await query.message.reply_text("No admins to remove.")
                return
            keyboard = [[InlineKeyboardButton(f"Admin ID: {a[0]}", callback_data=f'admin_remove_id_{a[0]}')] for a in admins]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text("Select an admin to remove:", reply_markup=reply_markup)
        elif query.data.startswith('admin_remove_id_') and is_user_admin:
            admin_id = int(query.data.split('_')[3])
            remove_admin(admin_id)
            await query.message.reply_text(f"✅ Admin ID {admin_id} removed.")
        elif query.data == 'admin_slots' and is_user_admin:
            keyboard = [
                [InlineKeyboardButton("Add Doctor Slot", callback_data='admin_add_slot')],
                [InlineKeyboardButton("View Doctor Slots", callback_data='admin_view_slots')],
                [InlineKeyboardButton("Back to Admin Panel", callback_data='admin_panel')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text("Manage Doctor Slots:", reply_markup=reply_markup)
        elif query.data == 'admin_doctors' and is_user_admin:
            keyboard = [
                [InlineKeyboardButton("Add Doctor", callback_data='admin_add_doctor')],
                [InlineKeyboardButton("View Doctors", callback_data='admin_view_doctors')],
                [InlineKeyboardButton("Back to Admin Panel", callback_data='admin_panel')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text("Manage Doctors:", reply_markup=reply_markup)
        elif query.data == 'admin_add_slot' and is_user_admin:
            context.user_data['state'] = ADMIN_ADD_SLOT
            await query.message.reply_text(
                "Enter the new doctor slot details (format: date,time_slot,doctor_id)\n"
                "Example: 2025-04-23,09:00,987654321"
            )
            return ADMIN_ADD_SLOT
        elif query.data == 'admin_add_doctor' and is_user_admin:
            context.user_data['state'] = ADMIN_ADD_DOCTOR
            await query.message.reply_text(
                "Enter the new doctor details (format: user_id,name)\n"
                "Example: 987654321,Dr. Martin"
            )
            return ADMIN_ADD_DOCTOR
        elif query.data == 'admin_view_slots' and is_user_admin:
            slots = get_available_slots_for_all_doctors()
            if not slots:
                await query.message.reply_text("No available doctor slots found.")
                return
            message = "Available Doctor Slots:\n"
            for slot in slots:
                booking_date = datetime.strptime(slot[0], '%Y-%m-%d')
                day_name = calendar.day_name[booking_date.weekday()]
                message += f"{slot[0]} ({day_name}), {slot[1]} with {slot[2]}\n"
            await query.message.reply_text(message)
        elif query.data == 'admin_view_doctors' and is_user_admin:
            doctors = get_all_doctors()
            if not doctors:
                await query.message.reply_text("No doctors found.")
                return
            message = "Registered Doctors:\n"
            for doctor in doctors:
                message += f"ID: {doctor[0]}, Name: {doctor[1]}\n"
            await query.message.reply_text(message)
        elif query.data == 'admin_stats' and is_user_admin:
            stats = get_system_stats()
            await query.message.reply_text(
                f"📊 System Statistics:\n"
                f"Total Bookings: {stats['total_bookings']}\n"
                f"Active Users: {stats['active_users']}\n"
                f"Admins: {stats['total_admins']}\n"
                f"Doctors: {stats['total_doctors']}"
            )
        elif query.data == 'admin_broadcast' and is_user_admin:
            await query.message.reply_text("Enter the broadcast message to send to all users:")
            return BROADCAST
        elif query.data.startswith('slot_') and not (is_user_admin and 'admin_panel' in query.data):
            parts = query.data.split('_')
            slot = parts[1]
            booking_date = parts[2]
            doctor_id = parts[3]
            context.user_data['selected_slot'] = slot
            context.user_data['selected_date'] = booking_date
            context.user_data['selected_doctor_id'] = int(doctor_id)
            context.user_data['state'] = PATIENT_NAME
            logger.info(f"User {user_id} selected slot {slot} on {booking_date} for doctor {doctor_id}")
            await query.message.reply_text(
                "📝 Please provide the patient's full name for the booking."
            )
            return PATIENT_NAME
        elif query.data == 'book_self' and not (is_user_admin and 'admin_panel' in query.data):
            conn = sqlite3.connect('doctomed.db', timeout=10)
            conn.execute('PRAGMA journal_mode=WAL')
            try:
                c = conn.cursor()
                c.execute('INSERT OR REPLACE INTO users (user_id, is_caregiver, linked_patient) VALUES (?, ?, ?)',
                          (user_id, 0, None))
                conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Error registering user {user_id} as self: {e}")
                await query.message.reply_text("⚠️ Error registering user. Please try again.")
                return
            finally:
                conn.close()
            await select_doctor(update, context)
            return SELECT_DOCTOR
        elif query.data == 'book_caregiver' and not (is_user_admin and 'admin_panel' in query.data):
            context.user_data['state'] = CAREGIVER_LINK
            await query.message.reply_text(
                "Please provide the name of the patient you are managing for."
            )
            return CAREGIVER_LINK
        elif query.data.startswith('approve_booking_'):
            booking_id = int(query.data.split('_')[2])
            booking = get_booking_by_id(booking_id)
            if not booking:
                await query.message.reply_text("⚠️ Booking not found.")
                return
            conn = sqlite3.connect('doctomed.db', timeout=10)
            conn.execute('PRAGMA journal_mode=WAL')
            try:
                c = conn.cursor()
                c.execute('UPDATE bookings SET status = ?, confirmed = 1 WHERE id = ?', ('approved', booking_id))
                c.execute('UPDATE doctor_slots SET is_available = 0 WHERE booking_date = ? AND time_slot = ? AND doctor_id = ?',
                          (booking[BOOKING_FIELDS['booking_date']], booking[BOOKING_FIELDS['time_slot']], booking[BOOKING_FIELDS['doctor_id']]))
                conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Error approving booking {booking_id}: {e}")
                await query.message.reply_text("⚠️ Error approving booking. Please try again.")
                return
            finally:
                conn.close()
            doctor = get_doctor_by_id(booking[BOOKING_FIELDS['doctor_id']])
            doctor_name = doctor[1] if doctor else "Doctor"
            booking_date = str(booking[BOOKING_FIELDS['booking_date']])
            try:
                booking_date_dt = datetime.strptime(booking_date, '%Y-%m-%d')
            except ValueError as e:
                logger.error(f"Date parsing error for booking {booking_id} in approve_booking: {e}, booking data: {booking}")
                await query.message.reply_text("⚠️ Invalid booking date in database. Please contact support.")
                return
            day_name = calendar.day_name[booking_date_dt.weekday()]
            current_date = date.today().strftime('%Y-%m-%d')
            date_display = "today" if booking[BOOKING_FIELDS['booking_date']] == current_date else f"on {booking[BOOKING_FIELDS['booking_date']]} ({day_name})"
            try:
                await context.bot.send_message(
                    chat_id=booking[BOOKING_FIELDS['user_id']],
                    text=(
                        f"✅ Your call with {doctor_name} is scheduled {date_display} at {booking[BOOKING_FIELDS['time_slot']]}. "
                        "Please call 0900 0900 90 at that time."
                    )
                )
            except Exception as e:
                logger.error(f"Failed to notify user {booking[BOOKING_FIELDS['user_id']]} about approval: {e}")
            try:
                await context.bot.send_message(
                    chat_id=booking[BOOKING_FIELDS['doctor_id']],
                    text=(
                        f"✅ Booking confirmed for {booking[BOOKING_FIELDS['patient_name']]} on {booking[BOOKING_FIELDS['booking_date']]} ({day_name}) at {booking[BOOKING_FIELDS['time_slot']]}. "
                        f"Patient: {booking[BOOKING_FIELDS['patient_name']]}\nDOB: {booking[BOOKING_FIELDS['patient_dob']]}\nUser ID: {booking[BOOKING_FIELDS['user_id']]}"
                    )
                )
            except Exception as e:
                logger.error(f"Failed to notify doctor {booking[BOOKING_FIELDS['doctor_id']]} about approval: {e}")
            await query.message.reply_text(f"✅ Booking ID {booking_id} approved. User and doctor notified.")
        elif query.data.startswith('reject_booking_'):
            booking_id = int(query.data.split('_')[2])
            booking = get_booking_by_id(booking_id)
            if not booking:
                await query.message.reply_text("⚠️ Booking not found.")
                return
            conn = sqlite3.connect('doctomed.db', timeout=10)
            conn.execute('PRAGMA journal_mode=WAL')
            try:
                c = conn.cursor()
                c.execute('UPDATE bookings SET status = ?, confirmed = 0 WHERE id = ?', ('rejected', booking_id))
                conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Error rejecting booking {booking_id}: {e}")
                await query.message.reply_text("⚠️ Error rejecting booking. Please try again.")
                return
            finally:
                conn.close()
            try:
                await context.bot.send_message(
                    chat_id=booking[BOOKING_FIELDS['user_id']],
                    text=f"❌ Your booking for {booking[BOOKING_FIELDS['patient_name']]} on {booking[BOOKING_FIELDS['booking_date']]} at {booking[BOOKING_FIELDS['time_slot']]} was rejected by the doctor. Please select another slot."
                )
            except Exception as e:
                logger.error(f"Failed to notify user {booking[BOOKING_FIELDS['user_id']]} about rejection: {e}")
            await query.message.reply_text(f"✅ Booking ID {booking_id} rejected. User notified.")
        else:
            await query.message.reply_text("⚠️ Invalid action. Please use the provided buttons.")
    except Exception as e:
        if "429" in str(e):
            logger.warning(f"Rate limit exceeded for user {user_id}: {e}")
            try:
                await query.message.reply_text("⚠️ Bot is temporarily rate-limited. Please try again in a moment.")
            except Exception as reply_error:
                logger.error(f"Failed to send rate limit message to user {user_id}: {reply_error}")
            return
        logger.error(f"Error in button_callback for user {user_id}, callback {query.data}: {e}", exc_info=True)
        try:
            await query.message.reply_text("⚠️ An error occurred. Please try again or use /start to reset.")
        except Exception as reply_error:
            logger.error(f"Failed to send error message to user {user_id}: {reply_error}")
        context.user_data.clear()
        return

# Handle booking start
async def handle_booking_start(query, context):
    user_id = query.from_user.id
    conn = sqlite3.connect('doctomed.db', timeout=10)
    conn.execute('PRAGMA journal_mode=WAL')
    try:
        c = conn.cursor()
        c.execute('SELECT is_caregiver FROM users WHERE user_id = ?', (user_id,))
        user = c.fetchone()
        if not user:
            keyboard = [
                [InlineKeyboardButton("For myself", callback_data='book_self')],
                [InlineKeyboardButton("For a loved one", callback_data='book_caregiver')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(
                "Are you booking for yourself or managing for someone else?",
                reply_markup=reply_markup
            )
            return
        await select_doctor(query, context)
        return SELECT_DOCTOR
    except Exception as e:
        logger.error(f"Error in handle_booking_start for user {user_id}: {e}", exc_info=True)
        try:
            await query.message.reply_text("⚠️ An error occurred. Please try again or use /start to reset.")
        except Exception as reply_error:
            logger.error(f"Failed to send error message to user {user_id}: {reply_error}")
        context.user_data.clear()
        return
    finally:
        conn.close()

# Get doctor ID by name
def get_doctor_id_by_name(name):
    conn = sqlite3.connect('doctomed.db', timeout=10)
    conn.execute('PRAGMA journal_mode=WAL')
    try:
        c = conn.cursor()
        c.execute('SELECT user_id FROM doctors WHERE name = ?', (name,))
        doctor = c.fetchone()
        return doctor[0] if doctor else None
    except sqlite3.Error as e:
        logger.error(f"Error fetching doctor by name {name}: {e}")
        return None
    finally:
        conn.close()

# Handle message
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    text = update.message.text
    logger.info(f"User {user_id} sent message: {text}, state: {context.user_data.get('state')}")
    
    try:
        is_user_admin = is_admin(user_id)
        if context.user_data.get('state') == CAREGIVER_LINK and not is_user_admin:
            conn = sqlite3.connect('doctomed.db', timeout=10)
            conn.execute('PRAGMA journal_mode=WAL')
            try:
                c = conn.cursor()
                c.execute('INSERT OR REPLACE INTO users (user_id, is_caregiver, linked_patient) VALUES (?, ?, ?)',
                          (user_id, 1, text))
                conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Error registering caregiver for user {user_id}: {e}")
                await update.message.reply_text("⚠️ Error registering caregiver. Please try again.")
                return ConversationHandler.END
            finally:
                conn.close()
            context.user_data.pop('state', None)
            await update.message.reply_text(
                f"✅ Registered as caregiver for {text}. You can now book calls on their behalf."
            )
            await select_doctor(update, context)
            return SELECT_DOCTOR
        elif context.user_data.get('state') == PATIENT_NAME and not is_user_admin:
            context.user_data['patient_name'] = text
            context.user_data['state'] = PATIENT_DOB
            await update.message.reply_text(
                "📅 Please provide the patient's date of birth (format: YYYY-MM-DD, e.g., 1980-01-01)."
            )
            return PATIENT_DOB
        elif context.user_data.get('state') == PATIENT_DOB and not is_user_admin:
            try:
                patient_dob = datetime.strptime(text, '%Y-%m-%d').strftime('%Y-%m-%d')
                patient_name = context.user_data['patient_name']
                time_slot = context.user_data['selected_slot']
                booking_date = context.user_data['selected_date']
                doctor_id = context.user_data['selected_doctor_id']
                
                try:
                    datetime.strptime(booking_date, '%Y-%m-%d')
                except ValueError:
                    logger.error(f"Invalid booking_date: {booking_date}")
                    await update.message.reply_text("⚠️ Invalid booking date. Please try again.")
                    context.user_data.clear()
                    return ConversationHandler.END
                
                conn = sqlite3.connect('doctomed.db', timeout=10)
                conn.execute('PRAGMA journal_mode=WAL')
                try:
                    c = conn.cursor()
                    c.execute('SELECT is_available FROM doctor_slots WHERE booking_date = ? AND time_slot = ? AND doctor_id = ?', 
                              (booking_date, time_slot, doctor_id))
                    slot = c.fetchone()
                    if not slot or slot[0] == 0:
                        await update.message.reply_text("⚠️ This slot is no longer available. Please select another slot.")
                        context.user_data.clear()
                        return ConversationHandler.END
                    
                    c.execute('INSERT INTO bookings (user_id, patient_name, patient_dob, time_slot, booking_date, doctor_id, status, confirmed) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                              (user_id, patient_name, patient_dob, time_slot, booking_date, doctor_id, 'pending', 0))
                    booking_id = c.lastrowid
                    conn.commit()
                except sqlite3.Error as e:
                    logger.error(f"Error inserting booking for user {user_id}: {e}")
                    await update.message.reply_text("⚠️ Error creating booking. Please try again.")
                    context.user_data.clear()
                    return ConversationHandler.END
                finally:
                    conn.close()
                
                username = update.message.from_user.username or "N/A"
                booking_date_dt = datetime.strptime(booking_date, '%Y-%m-%d')
                day_name = calendar.day_name[booking_date_dt.weekday()]
                try:
                    await context.bot.send_message(
                        chat_id=doctor_id,
                        text=(
                            f"🔔 New booking request:\n"
                            f"Patient: {patient_name}\n"
                            f"DOB: {patient_dob}\n"
                            f"Date: {booking_date} ({day_name})\n"
                            f"Time: {time_slot}\n"
                            f"User ID: {user_id}\n"
                            f"Username: {username}\n"
                            f"Please approve or reject the booking."
                        ),
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("Approve", callback_data=f'approve_booking_{booking_id}'),
                             InlineKeyboardButton("Reject", callback_data=f'reject_booking_{booking_id}')]
                        ])
                    )
                except Exception as e:
                    error_message = f"Failed to notify doctor ID {doctor_id}: {e}"
                    logger.error(error_message)
                    user_message = "⚠️ Error notifying doctor. Please try again or contact support."
                    if "chat not found" in str(e).lower():
                        user_message = "⚠️ Doctor's Telegram account not found. Please ensure the doctor has started the bot."
                    elif "blocked" in str(e).lower():
                        user_message = "⚠️ Bot is blocked by the doctor. Please contact the doctor to unblock the bot."
                    await update.message.reply_text(user_message)
                    for admin_id in ADMIN_IDS:
                        try:
                            await context.bot.send_message(
                                chat_id=int(admin_id),
                                text=f"⚠️ Notification error for booking ID {booking_id}: {error_message}"
                            )
                            await asyncio.sleep(0.1)  # Rate limit delay
                        except Exception as admin_error:
                            logger.error(f"Failed to notify admin {admin_id}: {admin_error}")
                    context.user_data.clear()
                    return ConversationHandler.END
                
                await update.message.reply_text(
                    f"📝 Booking request for {patient_name} (DOB: {patient_dob}) on {booking_date} at {time_slot} submitted.\n"
                    "You will be notified once the doctor approves."
                )
                
                context.user_data.clear()
                return ConversationHandler.END
            except ValueError:
                await update.message.reply_text("Invalid date format. Please use YYYY-MM-DD (e.g., 1980-01-01).")
                return PATIENT_DOB
        elif context.user_data.get('state') == ADMIN_ADD and is_user_admin:
            try:
                new_admin_id = int(text)
                add_admin(new_admin_id)
                await update.message.reply_text(f"✅ Admin ID {new_admin_id} added.")
            except ValueError:
                await update.message.reply_text("Please enter a valid Telegram User ID.")
            context.user_data.pop('state', None)
            return ConversationHandler.END
        elif context.user_data.get('state') == USER_EDIT and is_user_admin:
            try:
                edit_user_id = context.user_data['edit_user_id']
                is_caregiver, linked_patient = text.split(',')
                is_caregiver = int(is_caregiver.strip())
                linked_patient = linked_patient.strip() or None
                conn = sqlite3.connect('doctomed.db', timeout=10)
                conn.execute('PRAGMA journal_mode=WAL')
                try:
                    c = conn.cursor()
                    c.execute('UPDATE users SET is_caregiver = ?, linked_patient = ? WHERE user_id = ?',
                              (is_caregiver, linked_patient, edit_user_id))
                    conn.commit()
                except sqlite3.Error as e:
                    logger.error(f"Error updating user {edit_user_id}: {e}")
                    await update.message.reply_text("⚠️ Error updating user. Please try again.")
                    return ConversationHandler.END
                finally:
                    conn.close()
                await update.message.reply_text(f"✅ User ID {edit_user_id} updated.")
            except ValueError:
                await update.message.reply_text("Invalid format. Use: is_caregiver,linked_patient (e.g., 1,John Doe)")
            context.user_data.pop('state', None)
            context.user_data.pop('edit_user_id', None)
            return ConversationHandler.END
        elif context.user_data.get('state') == BROADCAST and is_user_admin:
            users = get_all_users()
            success_count = 0
            failure_count = 0
            for user in users:
                try:
                    await context.bot.send_message(chat_id=user[0], text=f"📢 Announcement: {text}")
                    success_count += 1
                    await asyncio.sleep(0.1)  # Rate limit delay
                except Exception as e:
                    logger.error(f"Failed to send broadcast to User ID {user[0]}: {e}")
                    failure_count += 1
            await update.message.reply_text(
                f"✅ Broadcast sent to {success_count} users.\n"
                f"❌ Failed to send to {failure_count} users."
            )
            context.user_data.pop('state', None)
            return ConversationHandler.END
        elif context.user_data.get('state') == ADMIN_ADD_SLOT and is_user_admin:
            try:
                booking_date, time_slot, doctor_id = text.split(',')
                booking_date = booking_date.strip()
                time_slot = time_slot.strip()
                doctor_id = int(doctor_id.strip())
                datetime.strptime(booking_date, '%Y-%m-%d')
                if time_slot not in TIME_SLOTS:
                    raise ValueError
                conn = sqlite3.connect('doctomed.db', timeout=10)
                conn.execute('PRAGMA journal_mode=WAL')
                try:
                    c = conn.cursor()
                    c.execute('SELECT user_id FROM doctors WHERE user_id = ?', (doctor_id,))
                    if not c.fetchone():
                        raise ValueError
                    c.execute('INSERT OR IGNORE INTO doctor_slots (booking_date, time_slot, doctor_id, is_available) VALUES (?, ?, ?, ?)',
                              (booking_date, time_slot, doctor_id, 1))
                    conn.commit()
                except ValueError:
                    await update.message.reply_text("Invalid doctor ID or format. Please check and try again.")
                    return ADMIN_ADD_SLOT
                except sqlite3.Error as e:
                    logger.error(f"Error adding doctor slot: {e}")
                    await update.message.reply_text("⚠️ Error adding slot. Please try again.")
                    return ConversationHandler.END
                finally:
                    conn.close()
                await update.message.reply_text(f"✅ Doctor slot added: {booking_date}, {time_slot} for Doctor ID {doctor_id}")
            except ValueError:
                await update.message.reply_text("Invalid format. Use: date,time_slot,doctor_id (e.g., 2025-04-23,09:00,987654321)")
                return ADMIN_ADD_SLOT
            context.user_data.pop('state', None)
            return ConversationHandler.END
        elif context.user_data.get('state') == ADMIN_ADD_DOCTOR and is_user_admin:
            try:
                user_id, name = text.split(',')
                user_id = int(user_id.strip())
                name = name.strip()
                conn = sqlite3.connect('doctomed.db', timeout=10)
                conn.execute('PRAGMA journal_mode=WAL')
                try:
                    c = conn.cursor()
                    c.execute('INSERT OR IGNORE INTO doctors (user_id, name) VALUES (?, ?)', (user_id, name))
                    conn.commit()
                except sqlite3.Error as e:
                    logger.error(f"Error adding doctor: {e}")
                    await update.message.reply_text("⚠️ Error adding doctor. Please try again.")
                    return ConversationHandler.END
                finally:
                    conn.close()
                await update.message.reply_text(f"✅ Doctor added: {name} (ID: {user_id})")
            except ValueError:
                await update.message.reply_text("Invalid format. Use: user_id,name (e.g., 987654321,Dr. Martin)")
                return ADMIN_ADD_DOCTOR
            context.user_data.pop('state', None)
            return ConversationHandler.END
        elif context.user_data.get('state') == SUPPORT_REQUEST and not is_user_admin:
            if log_support_request(user_id, text):
                for admin_id in ADMIN_IDS:
                    try:
                        username = update.message.from_user.username or "N/A"
                        await context.bot.send_message(
                            chat_id=int(admin_id),
                            text=(
                                f"🔔 New support request from User ID {user_id} (Username: {username}):\n"
                                f"Message: {text}"
                            )
                        )
                        await asyncio.sleep(0.1)  # Rate limit delay
                    except Exception as e:
                        logger.error(f"Failed to notify admin ID {admin_id} about support request: {e}")
                await update.message.reply_text(
                    "✅ Your support request has been submitted. Our team will contact you soon."
                )
            else:
                await update.message.reply_text(
                    "⚠️ Failed to submit your support request. Please try again or contact support@doctomed.ch."
                )
            context.user_data.pop('state', None)
            return ConversationHandler.END
        else:
            await update.message.reply_text("⚠️ Please use the provided buttons or commands.")
            return ConversationHandler.END
    except Exception as e:
        if "429" in str(e):
            logger.warning(f"Rate limit exceeded for user {user_id}: {e}")
            try:
                await update.message.reply_text("⚠️ Bot is temporarily rate-limited. Please try again in a moment.")
            except Exception as reply_error:
                logger.error(f"Failed to send rate limit message to user {user_id}: {reply_error}")
            return ConversationHandler.END
        logger.error(f"Error in handle_message for user {user_id}, text: {text}: {e}", exc_info=True)
        try:
            await update.message.reply_text("⚠️ An error occurred. Please try again or use /start to reset.")
        except Exception as reply_error:
            logger.error(f"Failed to send error message to user {user_id}: {reply_error}")
        context.user_data.clear()
        return ConversationHandler.END

# Main function
def main():
    init_db()
    
    if not BOT_TOKEN:
        logger.error("No TELEGRAM_BOT_TOKEN found in .env file")
        return
    
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        
        conv_handler = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(button_callback),
                MessageHandler(Text() & ~COMMAND, handle_message),
            ],
            states={
                SELECT_DOCTOR: [CallbackQueryHandler(button_callback, pattern='^(doctor_|slot_|select_doctor)')],
                PATIENT_NAME: [MessageHandler(Text() & ~COMMAND, handle_message)],
                PATIENT_DOB: [MessageHandler(Text() & ~COMMAND, handle_message)],
                CAREGIVER_LINK: [MessageHandler(Text() & ~COMMAND, handle_message)],
                CANCEL_BOOKING: [CallbackQueryHandler(button_callback, pattern='^cancel_')],
                ADMIN_ADD: [MessageHandler(Text() & ~COMMAND, handle_message)],
                USER_EDIT: [MessageHandler(Text() & ~COMMAND, handle_message)],
                BROADCAST: [MessageHandler(Text() & ~COMMAND, handle_message)],
                ADMIN_ADD_SLOT: [MessageHandler(Text() & ~COMMAND, handle_message)],
                ADMIN_ADD_DOCTOR: [MessageHandler(Text() & ~COMMAND, handle_message)],
                SUPPORT_REQUEST: [MessageHandler(Text() & ~COMMAND, handle_message)],
            },
            fallbacks=[
                CommandHandler('start', start),
                CommandHandler('cancel', cancel)
            ]
        )
        
        application.add_handler(CommandHandler('start', start))
        application.add_handler(CommandHandler('cancel', cancel))
        application.add_handler(CommandHandler('health', health))
        application.add_handler(conv_handler)
        
        logger.info("Starting bot polling")
        application.run_polling(poll_interval=1.0, timeout=10)
    except Exception as e:
        logger.error(f"Error starting bot: {e}", exc_info=True)

if __name__ == '__main__':
    main()
