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
SELECT_DOCTOR, PATIENT_NAME, PATIENT_DOB, CAREGIVER_LINK, CANCEL_BOOKING, ADMIN_ADD, ADMIN_REMOVE, USER_EDIT, BROADCAST, ADMIN_ADD_SLOT, ADMIN_ADD_DOCTOR, SUPPORT_REQUEST, SELECT_LANGUAGE = range(13)

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

# Translations dictionary
translations = {
    'en': {
        'welcome_user': "👋 Welcome to Doctomed Call Service – professional care over the phone.\n📞 This service uses a Swiss premium number: 0900 0900 90\nWould you like to book a call?",
        'welcome_admin': "👋 Welcome, Admin! Access the Admin Panel to manage the Doctomed Call Service.\nYou can also switch to user features if needed.",
        'select_language': "🌐 Please select your preferred language:",
        'language_changed': "✅ Language changed to {language}.",
        'conversation_reset': "✅ Conversation reset. Use /start to begin again.",
        'unauthorized': "⚠️ Unauthorized access.",
        'no_doctors': "⚠️ No doctors available. Please contact support.",
        'error_occurred': "⚠️ An error occurred. Please try again or contact support.",
        'select_doctor': "👨‍⚕️ Please select a doctor to view their schedule:",
        'no_slots': "⚠️ No available slots for {doctor_name}. Please try another doctor or contact support.",
        'doctor_not_found': "⚠️ Doctor not found.",
        'schedule_header': "📅 {doctor_name}'s Schedule (Next 7 Days)\n\n",
        'select_slot': "Select a slot to book:",
        'back_to_doctors': "Back to Doctors",
        'no_bookings': "You have no active bookings to cancel.",
        'select_booking_to_cancel': "Select a booking to cancel:",
        'booking_cancelled': "✅ Booking for {patient_name} on {date} at {time} cancelled successfully.",
        'failed_to_notify_doctor': "⚠️ Booking cancelled, but failed to notify the doctor.",
        'failed_to_cancel': "⚠️ Failed to cancel booking: {reason}",
        'service_info': "ℹ️ *Doctomed Call Service*\n\nWe provide professional medical consultations via phone using a Swiss premium number: *0900 0900 90*.\n\n🕒 *Availability*: Monday to Friday, 9:00–17:00\n👨‍⚕️ *Our Doctors*:\n{doctor_list}\n\n🌐 Visit our website: https://doctomed.ch\nAll our doctors are Swiss-certified, ensuring high-quality care.",
        'no_doctors_available': "No doctors available at the moment.",
        'support_prompt': "📧 Please describe your issue or question, and our support team will get back to you.\nYou can also contact us at support@doctomed.ch or call +41 44 123 45 67.",
        'support_submitted': "✅ Your support request has been submitted. Our team will contact you soon.",
        'support_failed': "⚠️ Failed to submit your support request. Please try again or contact support@doctomed.ch.",
        'admin_panel': "Admin Panel:",
        'booking_for': "Are you booking for yourself or managing for someone else?",
        'book_self': "For myself",
        'book_caregiver': "For a loved one",
        'patient_name_prompt': "📝 Please provide the patient's full name for the booking.",
        'patient_dob_prompt': "📅 Please provide the patient's date of birth (format: YYYY-MM-DD, e.g., 1980-01-01).",
        'caregiver_patient_prompt': "Please provide the name of the patient you are managing for.",
        'caregiver_registered': "✅ Registered as caregiver for {patient_name}. You can now book calls on their behalf.",
        'invalid_date_format': "Invalid date format. Please use YYYY-MM-DD (e.g., 1980-01-01).",
        'slot_unavailable': "⚠️ This slot is no longer available. Please select another slot.",
        'booking_submitted': "📝 Booking request for {patient_name} (DOB: {dob}) on {date} at {time} submitted.\nYou will be notified once the doctor approves.",
        'booking_error': "⚠️ Error creating booking. Please try again.",
        'doctor_notification_error': "⚠️ Error notifying doctor: {reason}",
        'invalid_action': "⚠️ Please use the provided buttons or commands.",
        'rate_limit_exceeded': "⚠️ Bot is temporarily rate-limited. Please try again in a moment.",
        'health_status': "✅ Database: Connected\n📊 Total Bookings: {total_bookings}\n👥 Active Users: {active_users}\n👨‍⚕️ Doctors: {total_doctors}",
        'health_failed': "⚠️ Health check failed: {error}",
        'admin_bookings': "Select a booking to manage:",
        'no_bookings_admin': "No bookings found.",
        'booking_details': "Booking ID: {id}\nUser ID: {user_id}\nPatient: {patient_name}\nDOB: {dob}\nSlot: {time} on {date}\nDoctor ID: {doctor_id}\nStatus: {status}",
        'admin_cancel_booking': "Cancel Booking",
        'back_to_bookings': "Back to Bookings",
        'admin_booking_cancelled': "✅ Booking ID {id} cancelled.",
        'admin_users': "Select a user to manage:",
        'no_users': "No users found.",
        'user_details': "User ID: {id}\nCaregiver: {caregiver}\nLinked Patient: {linked_patient}",
        'edit_user': "Edit User",
        'delete_user': "Delete User",
        'back_to_users': "Back to Users",
        'admin_edit_user_prompt': "Enter new user details (format: is_caregiver,linked_patient)\nExample: 1,John Doe",
        'user_updated': "✅ User ID {id} updated.",
        'invalid_user_format': "Invalid format. Use: is_caregiver,linked_patient (e.g., 1,John Doe)",
        'user_deleted': "✅ User ID {id} deleted.",
        'admin_add_prompt': "Enter the Telegram User ID of the new admin:",
        'admin_added': "✅ Admin ID {id} added.",
        'invalid_admin_id': "Please enter a valid Telegram User ID.",
        'admin_remove': "Select an admin to remove:",
        'no_admins': "No admins to remove.",
        'admin_removed': "✅ Admin ID {id} removed.",
        'admin_slots': "Manage Doctor Slots:",
        'admin_doctors': "Manage Doctors:",
        'admin_add_slot': "Add Doctor Slot",
        'view_slots': "View Doctor Slots",
        'back_to_admin': "Back to Admin Panel",
        'admin_add_doctor': "Add Doctor",
        'view_doctors': "View Doctors",
        'admin_add_slot_prompt': "Enter the new doctor slot details (format: date,time_slot,doctor_id)\nExample: 2025-04-23,09:00,987654321",
        'admin_add_doctor_prompt': "Enter the new doctor details (format: user_id,name)\nExample: 987654321,Dr. Martin",
        'slot_added': "✅ Doctor slot added: {date}, {time} for Doctor ID {doctor_id}",
        'invalid_slot_format': "Invalid format. Use: date,time_slot,doctor_id (e.g., 2025-04-23,09:00,987654321)",
        'invalid_doctor_id': "Invalid doctor ID or format. Please check and try again.",
        'doctor_added': "✅ Doctor added: {name} (ID: {id})",
        'invalid_doctor_format': "Invalid format. Use: user_id,name (e.g., 987654321,Dr. Martin)",
        'no_slots_available': "No available doctor slots found.",
        'slots_list': "Available Doctor Slots:\n",
        'no_doctors_admin': "No doctors found.",
        'doctors_list': "Registered Doctors:\n",
        'system_stats': "📊 System Statistics:\nTotal Bookings: {total_bookings}\nActive Users: {active_users}\nAdmins: {total_admins}\nDoctors: {total_doctors}",
        'broadcast_prompt': "Enter the broadcast message to send to all users:",
        'broadcast_result': "✅ Broadcast sent to {success} users.\n❌ Failed to send to {failed} users.",
        'booking_approved': "✅ Your call with {doctor_name} is scheduled {date_display} at {time}. Please call 0900 0900 90 at that time.",
        'booking_rejected': "❌ Your booking for {patient_name} on {date} at {time} was rejected by the doctor. Please select another slot.",
        'booking_approved_admin': "✅ Booking ID {id} approved. User and doctor notified.",
        'booking_rejected_admin': "✅ Booking ID {id} rejected. User notified.",
        'booking_not_found': "⚠️ Booking not found.",
        'approve': "Approve",
        'reject': "Reject",
        'doctor_notification': "🔔 New booking request:\nPatient: {patient_name}\nDOB: {dob}\nDate: {date} ({day_name})\nTime: {time}\nUser ID: {user_id}\nUsername: {username}\nPlease approve or reject the booking.",
        'doctor_cancel_notification': "🔔 Booking cancelled:\nPatient: {patient_name}\nDate: {date}\nTime: {time}",
        'doctor_approve_notification': "✅ Booking confirmed for {patient_name} on {date} ({day_name}) at {time}.\nPatient: {patient_name}\nDOB: {dob}\nUser ID: {user_id}",
        'invalid_booking_date': "⚠️ Invalid booking date in database. Please contact support."
    },
    'de': {
        'welcome_user': "👋 Willkommen beim Doctomed Call Service – professionelle Beratung per Telefon.\n📞 Dieser Dienst nutzt eine Schweizer Premium-Nummer: 0900 0900 90\nMöchten Sie einen Anruf buchen?",
        'welcome_admin': "👋 Willkommen, Admin! Greifen Sie auf das Admin-Panel zu, um den Doctomed Call Service zu verwalten.\nSie können auch zu den Benutzerfunktionen wechseln.",
        'select_language': "🌐 Bitte wählen Sie Ihre bevorzugte Sprache:",
        'language_changed': "✅ Sprache auf {language} geändert.",
        'conversation_reset': "✅ Konversation zurückgesetzt. Verwenden Sie /start, um erneut zu beginnen.",
        'unauthorized': "⚠️ Unbefugter Zugriff.",
        'no_doctors': "⚠️ Keine Ärzte verfügbar. Bitte kontaktieren Sie den Support.",
        'error_occurred': "⚠️ Ein Fehler ist aufgetreten. Bitte versuchen Sie es erneut oder kontaktieren Sie den Support.",
        'select_doctor': "👨‍⚕️ Bitte wählen Sie einen Arzt, um dessen Zeitplan einzusehen:",
        'no_slots': "⚠️ Keine verfügbaren Termine für {doctor_name}. Bitte wählen Sie einen anderen Arzt oder kontaktieren Sie den Support.",
        'doctor_not_found': "⚠️ Arzt nicht gefunden.",
        'schedule_header': "📅 Zeitplan von {doctor_name} (nächste 7 Tage)\n\n",
        'select_slot': "Wählen Sie einen Termin zum Buchen:",
        'back_to_doctors': "Zurück zu den Ärzten",
        'no_bookings': "Sie haben keine aktiven Buchungen zum Stornieren.",
        'select_booking_to_cancel': "Wählen Sie eine Buchung zum Stornieren:",
        'booking_cancelled': "✅ Buchung für {patient_name} am {date} um {time} erfolgreich storniert.",
        'failed_to_notify_doctor': "⚠️ Buchung storniert, aber Benachrichtigung des Arztes fehlgeschlagen.",
        'failed_to_cancel': "⚠️ Buchung konnte nicht storniert werden: {reason}",
        'service_info': "ℹ️ *Doctomed Call Service*\n\nWir bieten professionelle medizinische Beratungen per Telefon über eine Schweizer Premium-Nummer: *0900 0900 90*.\n\n🕒 *Verfügbarkeit*: Montag bis Freitag, 9:00–17:00\n👨‍⚕️ *Unsere Ärzte*:\n{doctor_list}\n\n🌐 Besuchen Sie unsere Website: https://doctomed.ch\nAlle unsere Ärzte sind in der Schweiz zertifiziert und gewährleisten qualitativ hochwertige Betreuung.",
        'no_doctors_available': "Momentan keine Ärzte verfügbar.",
        'support_prompt': "📧 Bitte beschreiben Sie Ihr Problem oder Ihre Frage, unser Support-Team wird sich bei Ihnen melden.\nSie können uns auch unter support@doctomed.ch oder telefonisch unter +41 44 123 45 67 erreichen.",
        'support_submitted': "✅ Ihre Support-Anfrage wurde eingereicht. Unser Team wird sich bald bei Ihnen melden.",
        'support_failed': "⚠️ Ihre Support-Anfrage konnte nicht eingereicht werden. Bitte versuchen Sie es erneut oder kontaktieren Sie support@doctomed.ch.",
        'admin_panel': "Admin-Panel:",
        'booking_for': "Buchen Sie für sich selbst oder für eine andere Person?",
        'book_self': "Für mich selbst",
        'book_caregiver': "Für eine andere Person",
        'patient_name_prompt': "📝 Bitte geben Sie den vollständigen Namen des Patienten für die Buchung an.",
        'patient_dob_prompt': "📅 Bitte geben Sie das Geburtsdatum des Patienten an (Format: JJJJ-MM-TT, z.B. 1980-01-01).",
        'caregiver_patient_prompt': "Bitte geben Sie den Namen des Patienten ein, für den Sie die Buchung verwalten.",
        'caregiver_registered': "✅ Als Betreuer für {patient_name} registriert. Sie können nun Anrufe im Namen dieser Person buchen.",
        'invalid_date_format': "Ungültiges Datumsformat. Bitte verwenden Sie JJJJ-MM-TT (z.B. 1980-01-01).",
        'slot_unavailable': "⚠️ Dieser Termin ist nicht mehr verfügbar. Bitte wählen Sie einen anderen Termin.",
        'booking_submitted': "📝 Buchungsanfrage für {patient_name} (Geburtsdatum: {dob}) am {date} um {time} eingereicht.\nSie werden benachrichtigt, sobald der Arzt zustimmt.",
        'booking_error': "⚠️ Fehler beim Erstellen der Buchung. Bitte versuchen Sie es erneut.",
        'doctor_notification_error': "⚠️ Fehler bei der Benachrichtigung des Arztes: {reason}",
        'invalid_action': "⚠️ Bitte verwenden Sie die bereitgestellten Schaltflächen oder Befehle.",
        'rate_limit_exceeded': "⚠️ Bot ist vorübergehend eingeschränkt. Bitte versuchen Sie es in einem Moment erneut.",
        'health_status': "✅ Datenbank: Verbunden\n📊 Gesamtbuchungen: {total_bookings}\n👥 Aktive Benutzer: {active_users}\n👨‍⚕️ Ärzte: {total_doctors}",
        'health_failed': "⚠️ Gesundheitsprüfung fehlgeschlagen: {error}",
        'admin_bookings': "Wählen Sie eine Buchung zur Verwaltung:",
        'no_bookings_admin': "Keine Buchungen gefunden.",
        'booking_details': "Buchungs-ID: {id}\nBenutzer-ID: {user_id}\nPatient: {patient_name}\nGeburtsdatum: {dob}\nTermin: {time} am {date}\nArzt-ID: {doctor_id}\nStatus: {status}",
        'admin_cancel_booking': "Buchung stornieren",
        'back_to_bookings': "Zurück zu den Buchungen",
        'admin_booking_cancelled': "✅ Buchungs-ID {id} storniert.",
        'admin_users': "Wählen Sie einen Benutzer zur Verwaltung:",
        'no_users': "Keine Benutzer gefunden.",
        'user_details': "Benutzer-ID: {id}\nBetreuer: {caregiver}\nVerknüpfter Patient: {linked_patient}",
        'edit_user': "Benutzer bearbeiten",
        'delete_user': "Benutzer löschen",
        'back_to_users': "Zurück zu den Benutzern",
        'admin_edit_user_prompt': "Geben Sie neue Benutzerdetails ein (Format: is_caregiver,linked_patient)\nBeispiel: 1,John Doe",
        'user_updated': "✅ Benutzer-ID {id} aktualisiert.",
        'invalid_user_format': "Ungültiges Format. Verwenden Sie: is_caregiver,linked_patient (z.B. 1,John Doe)",
        'user_deleted': "✅ Benutzer-ID {id} gelöscht.",
        'admin_add_prompt': "Geben Sie die Telegram-Benutzer-ID des neuen Admins ein:",
        'admin_added': "✅ Admin-ID {id} hinzugefügt.",
        'invalid_admin_id': "Bitte geben Sie eine gültige Telegram-Benutzer-ID ein.",
        'admin_remove': "Wählen Sie einen Admin zum Entfernen:",
        'no_admins': "Keine Admins zum Entfernen.",
        'admin_removed': "✅ Admin-ID {id} entfernt.",
        'admin_slots': "Arzttermine verwalten:",
        'admin_doctors': "Ärzte verwalten:",
        'admin_add_slot': "Arzttermin hinzufügen",
        'view_slots': "Arzttermine anzeigen",
        'back_to_admin': "Zurück zum Admin-Panel",
        'admin_add_doctor': "Arzt hinzufügen",
        'view_doctors': "Ärzte anzeigen",
        'admin_add_slot_prompt': "Geben Sie die Details des neuen Arzttermins ein (Format: Datum,Zeit,Arzt-ID)\nBeispiel: 2025-04-23,09:00,987654321",
        'admin_add_doctor_prompt': "Geben Sie die Details des neuen Arztes ein (Format: Benutzer-ID,Name)\nBeispiel: 987654321,Dr. Martin",
        'slot_added': "✅ Arzttermin hinzugefügt: {date}, {time} für Arzt-ID {doctor_id}",
        'invalid_slot_format': "Ungültiges Format. Verwenden Sie: Datum,Zeit,Arzt-ID (z.B. 2025-04-23,09:00,987654321)",
        'invalid_doctor_id': "Ungültige Arzt-ID oder Format. Bitte überprüfen Sie und versuchen Sie es erneut.",
        'doctor_added': "✅ Arzt hinzugefügt: {name} (ID: {id})",
        'invalid_doctor_format': "Ungültiges Format. Verwenden Sie: Benutzer-ID,Name (z.B. 987654321,Dr. Martin)",
        'no_slots_available': "Keine verfügbaren Arzttermine gefunden.",
        'slots_list': "Verfügbare Arzttermine:\n",
        'no_doctors_admin': "Keine Ärzte gefunden.",
        'doctors_list': "Registrierte Ärzte:\n",
        'system_stats': "📊 Systemstatistiken:\nGesamtbuchungen: {total_bookings}\nAktive Benutzer: {active_users}\nAdmins: {total_admins}\nÄrzte: {total_doctors}",
        'broadcast_prompt': "Geben Sie die Broadcast-Nachricht ein, die an alle Benutzer gesendet werden soll:",
        'broadcast_result': "✅ Broadcast an {success} Benutzer gesendet.\n❌ Konnte an {failed} Benutzer nicht gesendet werden.",
        'booking_approved': "✅ Ihr Anruf mit {doctor_name} ist für {date_display} um {time} geplant. Bitte rufen Sie um diese Zeit 0900 0900 90 an.",
        'booking_rejected': "❌ Ihre Buchung für {patient_name} am {date} um {time} wurde vom Arzt abgelehnt. Bitte wählen Sie einen anderen Termin.",
        'booking_approved_admin': "✅ Buchungs-ID {id} genehmigt. Benutzer und Arzt benachrichtigt.",
        'booking_rejected_admin': "✅ Buchungs-ID {id} abgelehnt. Benutzer benachrichtigt.",
        'booking_not_found': "⚠️ Buchung nicht gefunden.",
        'approve': "Genehmigen",
        'reject': "Ablehnen",
        'doctor_notification': "🔔 Neue Buchungsanfrage:\nPatient: {patient_name}\nGeburtsdatum: {dob}\nDatum: {date} ({day_name})\nZeit: {time}\nBenutzer-ID: {user_id}\nBenutzername: {username}\nBitte genehmigen oder lehnen Sie die Buchung ab.",
        'doctor_cancel_notification': "🔔 Buchung storniert:\nPatient: {patient_name}\nDatum: {date}\nZeit: {time}",
        'doctor_approve_notification': "✅ Buchung bestätigt für {patient_name} am {date} ({day_name}) um {time}.\nPatient: {patient_name}\nGeburtsdatum: {dob}\nBenutzer-ID: {user_id}",
        'invalid_booking_date': "⚠️ Ungültiges Buchungsdatum in der Datenbank. Bitte kontaktieren Sie den Support."
    },
    'fr': {
        'welcome_user': "👋 Bienvenue chez Doctomed Call Service – soins professionnels par téléphone.\n📞 Ce service utilise un numéro premium suisse : 0900 0900 90\nSouhaitez-vous réserver un appel ?",
        'welcome_admin': "👋 Bienvenue, Admin ! Accédez au panneau d'administration pour gérer le service Doctomed Call.\nVous pouvez également passer aux fonctionnalités utilisateur si nécessaire.",
        'select_language': "🌐 Veuillez sélectionner votre langue préférée :",
        'language_changed': "✅ Langue changée en {language}.",
        'conversation_reset': "✅ Conversation réinitialisée. Utilisez /start pour recommencer.",
        'unauthorized': "⚠️ Accès non autorisé.",
        'no_doctors': "⚠️ Aucun médecin disponible. Veuillez contacter le support.",
        'error_occurred': "⚠️ Une erreur s'est produite. Veuillez réessayer ou contacter le support.",
        'select_doctor': "👨‍⚕️ Veuillez sélectionner un médecin pour voir son planning :",
        'no_slots': "⚠️ Aucun créneau disponible pour {doctor_name}. Veuillez choisir un autre médecin ou contacter le support.",
        'doctor_not_found': "⚠️ Médecin non trouvé.",
        'schedule_header': "📅 Planning de {doctor_name} (7 prochains jours)\n\n",
        'select_slot': "Sélectionnez un créneau pour réserver :",
        'back_to_doctors': "Retour aux médecins",
        'no_bookings': "Vous n'avez aucune réservation active à annuler.",
        'select_booking_to_cancel': "Sélectionnez une réservation à annuler :",
        'booking_cancelled': "✅ Réservation pour {patient_name} le {date} à {time} annulée avec succès.",
        'failed_to_notify_doctor': "⚠️ Réservation annulée, mais échec de la notification du médecin.",
        'failed_to_cancel': "⚠️ Échec de l'annulation de la réservation : {reason}",
        'service_info': "ℹ️ *Doctomed Call Service*\n\nNous proposons des consultations médicales professionnelles par téléphone via un numéro premium suisse : *0900 0900 90*.\n\n🕒 *Disponibilité* : Lundi au vendredi, 9h00–17h00\n👨‍⚕️ *Nos médecins* :\n{doctor_list}\n\n🌐 Visitez notre site : https://doctomed.ch\nTous nos médecins sont certifiés en Suisse, garantissant des soins de haute qualité.",
        'no_doctors_available': "Aucun médecin disponible pour le moment.",
        'support_prompt': "📧 Veuillez décrire votre problème ou votre question, et notre équipe de support vous répondra.\nVous pouvez également nous contacter à support@doctomed.ch ou appeler le +41 44 123 45 67.",
        'support_submitted': "✅ Votre demande de support a été soumise. Notre équipe vous contactera bientôt.",
        'support_failed': "⚠️ Échec de la soumission de votre demande de support. Veuillez réessayer ou contacter support@doctomed.ch.",
        'admin_panel': "Panneau d'administration :",
        'booking_for': "Réservez-vous pour vous-même ou pour une autre personne ?",
        'book_self': "Pour moi-même",
        'book_caregiver': "Pour un proche",
        'patient_name_prompt': "📝 Veuillez fournir le nom complet du patient pour la réservation.",
        'patient_dob_prompt': "📅 Veuillez fournir la date de naissance du patient (format : AAAA-MM-JJ, ex. 1980-01-01).",
        'caregiver_patient_prompt': "Veuillez fournir le nom du patient pour lequel vous effectuez la réservation.",
        'caregiver_registered': "✅ Enregistré en tant que soignant pour {patient_name}. Vous pouvez maintenant réserver des appels en son nom.",
        'invalid_date_format': "Format de date invalide. Veuillez utiliser AAAA-MM-JJ (ex. 1980-01-01).",
        'slot_unavailable': "⚠️ Ce créneau n'est plus disponible. Veuillez sélectionner un autre créneau.",
        'booking_submitted': "📝 Demande de réservation pour {patient_name} (Date de naissance : {dob}) le {date} à {time} soumise.\nVous serez notifié une fois que le médecin aura approuvé.",
        'booking_error': "⚠️ Erreur lors de la création de la réservation. Veuillez réessayer.",
        'doctor_notification_error': "⚠️ Erreur lors de la notification du médecin : {reason}",
        'invalid_action': "⚠️ Veuillez utiliser les boutons ou commandes fournis.",
        'rate_limit_exceeded': "⚠️ Le bot est temporairement limité. Veuillez réessayer dans un instant.",
        'health_status': "✅ Base de données : Connectée\n📊 Total des réservations : {total_bookings}\n👥 Utilisateurs actifs : {active_users}\n👨‍⚕️ Médecins : {total_doctors}",
        'health_failed': "⚠️ Échec de la vérification de santé : {error}",
        'admin_bookings': "Sélectionnez une réservation à gérer :",
        'no_bookings_admin': "Aucune réservation trouvée.",
        'booking_details': "ID de réservation : {id}\nID utilisateur : {user_id}\nPatient : {patient_name}\nDate de naissance : {dob}\nCréneau : {time} le {date}\nID médecin : {doctor_id}\nStatut : {status}",
        'admin_cancel_booking': "Annuler la réservation",
        'back_to_bookings': "Retour aux réservations",
        'admin_booking_cancelled': "✅ ID de réservation {id} annulée.",
        'admin_users': "Sélectionnez un utilisateur à gérer :",
        'no_users': "Aucun utilisateur trouvé.",
        'user_details': "ID utilisateur : {id}\nSoignant : {caregiver}\nPatient lié : {linked_patient}",
        'edit_user': "Modifier l'utilisateur",
        'delete_user': "Supprimer l'utilisateur",
        'back_to_users': "Retour aux utilisateurs",
        'admin_edit_user_prompt': "Entrez les nouveaux détails de l'utilisateur (format : is_caregiver,linked_patient)\nExemple : 1,John Doe",
        'user_updated': "✅ ID utilisateur {id} mis à jour.",
        'invalid_user_format': "Format invalide. Utilisez : is_caregiver,linked_patient (ex. 1,John Doe)",
        'user_deleted': "✅ ID utilisateur {id} supprimé.",
        'admin_add_prompt': "Entrez l'ID utilisateur Telegram du nouvel admin :",
        'admin_added': "✅ ID admin {id} ajouté.",
        'invalid_admin_id': "Veuillez entrer un ID utilisateur Telegram valide.",
        'admin_remove': "Sélectionnez un admin à supprimer :",
        'no_admins': "Aucun admin à supprimer.",
        'admin_removed': "✅ ID admin {id} supprimé.",
        'admin_slots': "Gérer les créneaux des médecins :",
        'admin_doctors': "Gérer les médecins :",
        'admin_add_slot': "Ajouter un créneau médecin",
        'view_slots': "Voir les créneaux des médecins",
        'back_to_admin': "Retour au panneau d'administration",
        'admin_add_doctor': "Ajouter un médecin",
        'view_doctors': "Voir les médecins",
        'admin_add_slot_prompt': "Entrez les détails du nouveau créneau médecin (format : date,heure,id_médecin)\nExemple : 2025-04-23,09:00,987654321",
        'admin_add_doctor_prompt': "Entrez les détails du nouveau médecin (format : id_utilisateur,nom)\nExemple : 987654321,Dr. Martin",
        'slot_added': "✅ Créneau médecin ajouté : {date}, {time} pour l'ID médecin {doctor_id}",
        'invalid_slot_format': "Format invalide. Utilisez : date,heure,id_médecin (ex. 2025-04-23,09:00,987654321)",
        'invalid_doctor_id': "ID médecin ou format invalide. Veuillez vérifier et réessayer.",
        'doctor_added': "✅ Médecin ajouté : {name} (ID : {id})",
        'invalid_doctor_format': "Format invalide. Utilisez : id_utilisateur,nom (ex. 987654321,Dr. Martin)",
        'no_slots_available': "Aucun créneau médecin disponible trouvé.",
        'slots_list': "Créneaux médecins disponibles :\n",
        'no_doctors_admin': "Aucun médecin trouvé.",
        'doctors_list': "Médecins enregistrés :\n",
        'system_stats': "📊 Statistiques du système :\nTotal des réservations : {total_bookings}\nUtilisateurs actifs : {active_users}\nAdmins : {total_admins}\nMédecins : {total_doctors}",
        'broadcast_prompt': "Entrez le message de diffusion à envoyer à tous les utilisateurs :",
        'broadcast_result': "✅ Diffusion envoyée à {success} utilisateurs.\n❌ Échec de l'envoi à {failed} utilisateurs.",
        'booking_approved': "✅ Votre appel avec {doctor_name} est prévu {date_display} à {time}. Veuillez appeler le 0900 0900 90 à ce moment.",
        'booking_rejected': "❌ Votre réservation pour {patient_name} le {date} à {time} a été rejetée par le médecin. Veuillez sélectionner un autre créneau.",
        'booking_approved_admin': "✅ ID de réservation {id} approuvée. Utilisateur et médecin notifiés.",
        'booking_rejected_admin': "✅ ID de réservation {id} rejetée. Utilisateur notifié.",
        'booking_not_found': "⚠️ Réservation non trouvée.",
        'approve': "Approuver",
        'reject': "Rejeter",
        'doctor_notification': "🔔 Nouvelle demande de réservation :\nPatient : {patient_name}\nDate de naissance : {dob}\nDate : {date} ({day_name})\nHeure : {time}\nID utilisateur : {user_id}\nNom d'utilisateur : {username}\nVeuillez approuver ou rejeter la réservation.",
        'doctor_cancel_notification': "🔔 Réservation annulée :\nPatient : {patient_name}\nDate : {date}\nHeure : {time}",
        'doctor_approve_notification': "✅ Réservation confirmée pour {patient_name} le {date} ({day_name}) à {time}.\nPatient : {patient_name}\nDate de naissance : {dob}\nID utilisateur : {user_id}",
        'invalid_booking_date': "⚠️ Date de réservation invalide dans la base de données. Veuillez contacter le support."
    },
    'it': {
        'welcome_user': "👋 Benvenuto al Doctomed Call Service – assistenza professionale tramite telefono.\n📞 Questo servizio utilizza un numero premium svizzero: 0900 0900 90\nDesideri prenotare una chiamata?",
        'welcome_admin': "👋 Benvenuto, Admin! Accedi al Pannello di Amministrazione per gestire il Doctomed Call Service.\nPuoi anche passare alle funzionalità utente se necessario.",
        'select_language': "🌐 Seleziona la tua lingua preferita:",
        'language_changed': "✅ Lingua cambiata in {language}.",
        'conversation_reset': "✅ Conversazione reimpostata. Usa /start per ricominciare.",
        'unauthorized': "⚠️ Accesso non autorizzato.",
        'no_doctors': "⚠️ Nessun medico disponibile. Contatta il supporto.",
        'error_occurred': "⚠️ Si è verificato un errore. Riprova o contatta il supporto.",
        'select_doctor': "👨‍⚕️ Seleziona un medico per visualizzare il suo programma:",
        'no_slots': "⚠️ Nessun appuntamento disponibile per {doctor_name}. Prova con un altro medico o contatta il supporto.",
        'doctor_not_found': "⚠️ Medico non trovato.",
        'schedule_header': "📅 Programma di {doctor_name} (prossimi 7 giorni)\n\n",
        'select_slot': "Seleziona un appuntamento per prenotare:",
        'back_to_doctors': "Torna ai medici",
        'no_bookings': "Non hai prenotazioni attive da annullare.",
        'select_booking_to_cancel': "Seleziona una prenotazione da annullare:",
        'booking_cancelled': "✅ Prenotazione per {patient_name} il {date} alle {time} annullata con successo.",
        'failed_to_notify_doctor': "⚠️ Prenotazione annullata, ma impossibile notificare il medico.",
        'failed_to_cancel': "⚠️ Impossibile annullare la prenotazione: {reason}",
        'service_info': "ℹ️ *Doctomed Call Service*\n\nOffriamo consulenze mediche professionali tramite telefono utilizzando un numero premium svizzero: *0900 0900 90*.\n\n🕒 *Disponibilità*: Lunedì al venerdì, 9:00–17:00\n👨‍⚕️ *I nostri medici*:\n{doctor_list}\n\n🌐 Visita il nostro sito: https://doctomed.ch\nTutti i nostri medici sono certificati in Svizzera, garantendo cure di alta qualità.",
        'no_doctors_available': "Nessun medico disponibile al momento.",
        'support_prompt': "📧 Descrivi il tuo problema o la tua domanda, il nostro team di supporto ti risponderà.\nPuoi anche contattarci a support@doctomed.ch o chiamare il +41 44 123 45 67.",
        'support_submitted': "✅ La tua richiesta di supporto è stata inviata. Il nostro team ti contatterà presto.",
        'support_failed': "⚠️ Impossibile inviare la tua richiesta di supporto. Riprova o contatta support@doctomed.ch.",
        'admin_panel': "Pannello di amministrazione:",
        'booking_for': "Stai prenotando per te stesso o per qualcun altro?",
        'book_self': "Per me stesso",
        'book_caregiver': "Per una persona cara",
        'patient_name_prompt': "📝 Fornisci il nome completo del paziente per la prenotazione.",
        'patient_dob_prompt': "📅 Fornisci la data di nascita del paziente (formato: AAAA-MM-GG, es. 1980-01-01).",
        'caregiver_patient_prompt': "Fornisci il nome del paziente per cui stai gestendo la prenotazione.",
        'caregiver_registered': "✅ Registrato come caregiver per {patient_name}. Ora puoi prenotare chiamate per suo conto.",
        'invalid_date_format': "Formato data non valido. Usa AAAA-MM-GG (es. 1980-01-01).",
        'slot_unavailable': "⚠️ Questo appuntamento non è più disponibile. Seleziona un altro appuntamento.",
        'booking_submitted': "📝 Richiesta di prenotazione per {patient_name} (Data di nascita: {dob}) il {date} alle {time} inviata.\nSarai notificato quando il medico approverà.",
        'booking_error': "⚠️ Errore nella creazione della prenotazione. Riprova.",
        'doctor_notification_error': "⚠️ Errore nella notifica del medico: {reason}",
        'invalid_action': "⚠️ Usa i pulsanti o i comandi forniti.",
        'rate_limit_exceeded': "⚠️ Il bot è temporaneamente limitato. Riprova tra un momento.",
        'health_status': "✅ Database: Connesso\n📊 Prenotazioni totali: {total_bookings}\n👥 Utenti attivi: {active_users}\n👨‍⚕️ Medici: {total_doctors}",
        'health_failed': "⚠️ Controllo salute fallito: {error}",
        'admin_bookings': "Seleziona una prenotazione da gestire:",
        'no_bookings_admin': "Nessuna prenotazione trovata.",
        'booking_details': "ID Prenotazione: {id}\nID Utente: {user_id}\nPaziente: {patient_name}\nData di nascita: {dob}\nAppuntamento: {time} il {date}\nID Medico: {doctor_id}\nStato: {status}",
        'admin_cancel_booking': "Annulla Prenotazione",
        'back_to_bookings': "Torna alle Prenotazioni",
        'admin_booking_cancelled': "✅ ID Prenotazione {id} annullata.",
        'admin_users': "Seleziona un utente da gestire:",
        'no_users': "Nessun utente trovato.",
        'user_details': "ID Utente: {id}\nCaregiver: {caregiver}\nPaziente collegato: {linked_patient}",
        'edit_user': "Modifica Utente",
        'delete_user': "Elimina Utente",
        'back_to_users': "Torna agli Utenti",
        'admin_edit_user_prompt': "Inserisci i nuovi dettagli dell'utente (formato: is_caregiver,linked_patient)\nEsempio: 1,John Doe",
        'user_updated': "✅ ID Utente {id} aggiornato.",
        'invalid_user_format': "Formato non valido. Usa: is_caregiver,linked_patient (es. 1,John Doe)",
        'user_deleted': "✅ ID Utente {id} eliminato.",
        'admin_add_prompt': "Inserisci l'ID utente Telegram del nuovo admin:",
        'admin_added': "✅ ID Admin {id} aggiunto.",
        'invalid_admin_id': "Inserisci un ID utente Telegram valido.",
        'admin_remove': "Seleziona un admin da rimuovere:",
        'no_admins': "Nessun admin da rimuovere.",
        'admin_removed': "✅ ID Admin {id} rimosso.",
        'admin_slots': "Gestisci gli Appuntamenti dei Medici:",
        'admin_doctors': "Gestisci i Medici:",
        'admin_add_slot': "Aggiungi Appuntamento Medico",
        'view_slots': "Visualizza Appuntamenti Medici",
        'back_to_admin': "Torna al Pannello di Amministrazione",
        'admin_add_doctor': "Aggiungi Medico",
        'view_doctors': "Visualizza Medici",
        'admin_add_slot_prompt': "Inserisci i dettagli del nuovo appuntamento medico (formato: data,ora,id_medico)\nEsempio: 2025-04-23,09:00,987654321",
        'admin_add_doctor_prompt': "Inserisci i dettagli del nuovo medico (formato: id_utente,nome)\nEsempio: 987654321,Dr. Martin",
        'slot_added': "✅ Appuntamento medico aggiunto: {date}, {time} per ID Medico {doctor_id}",
        'invalid_slot_format': "Formato non valido. Usa: data,ora,id_medico (es. 2025-04-23,09:00,987654321)",
        'invalid_doctor_id': "ID medico o formato non valido. Verifica e riprova.",
        'doctor_added': "✅ Medico aggiunto: {name} (ID: {id})",
        'invalid_doctor_format': "Formato non valido. Usa: id_utente,nome (es. 987654321,Dr. Martin)",
        'no_slots_available': "Nessun appuntamento medico disponibile trovato.",
        'slots_list': "Appuntamenti Medici Disponibili:\n",
        'no_doctors_admin': "Nessun medico trovato.",
        'doctors_list': "Medici Registrati:\n",
        'system_stats': "📊 Statistiche di Sistema:\nPrenotazioni Totali: {total_bookings}\nUtenti Attivi: {active_users}\nAdmin: {total_admins}\nMedici: {total_doctors}",
        'broadcast_prompt': "Inserisci il messaggio di trasmissione da inviare a tutti gli utenti:",
        'broadcast_result': "✅ Trasmissione inviata a {success} utenti.\n❌ Impossibile inviare a {failed} utenti.",
        'booking_approved': "✅ La tua chiamata con {doctor_name} è programmata {date_display} alle {time}. Chiama il 0900 0900 90 a quell'ora.",
        'booking_rejected': "❌ La tua prenotazione per {patient_name} il {date} alle {time} è stata rifiutata dal medico. Seleziona un altro appuntamento.",
        'booking_approved_admin': "✅ ID Prenotazione {id} approvata. Utente e medico notificati.",
        'booking_rejected_admin': "✅ ID Prenotazione {id} rifiutata. Utente notificato.",
        'booking_not_found': "⚠️ Prenotazione non trovata.",
        'approve': "Approva",
        'reject': "Rifiuta",
        'doctor_notification': "🔔 Nuova richiesta di prenotazione:\nPaziente: {patient_name}\nData di nascita: {dob}\nData: {date} ({day_name})\nOra: {time}\nID Utente: {user_id}\nNome utente: {username}\nApprova o rifiuta la prenotazione.",
        'doctor_cancel_notification': "🔔 Prenotazione annullata:\nPaziente: {patient_name}\nData: {date}\nOra: {time}",
        'doctor_approve_notification': "✅ Prenotazione confermata per {patient_name} il {date} ({day_name}) alle {time}.\nPaziente: {patient_name}\nData di nascita: {dob}\nID Utente: {user_id}",
        'invalid_booking_date': "⚠️ Data di prenotazione non valida nel database. Contatta il supporto."
    }
}

# Available languages
LANGUAGES = {
    'en': 'English',
    'de': 'Deutsch',
    'fr': 'Français',
    'it': 'Italiano'
}

# Helper function to get translated message
def get_message(key, lang='en', **kwargs):
    message = translations.get(lang, translations['en']).get(key, translations['en'].get(key, key))
    try:
        return message.format(**kwargs)
    except KeyError as e:
        logger.warning(f"Missing format key in translation for key {key}, lang {lang}: {e}")
        return message

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
                     (user_id INTEGER PRIMARY KEY, is_caregiver INTEGER, linked_patient TEXT, language TEXT)''')
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

# Get user's language preference
def get_user_language(user_id):
    conn = sqlite3.connect('doctomed.db', timeout=10)
    conn.execute('PRAGMA journal_mode=WAL')
    try:
        c = conn.cursor()
        c.execute('SELECT language FROM users WHERE user_id = ?', (user_id,))
        result = c.fetchone()
        return result[0] if result and result[0] in LANGUAGES else 'en'
    except sqlite3.Error as e:
        logger.error(f"Error fetching language for user {user_id}: {e}")
        return 'en'
    finally:
        conn.close()

# Set user's language preference
def set_user_language(user_id, language):
    conn = sqlite3.connect('doctomed.db', timeout=10)
    conn.execute('PRAGMA journal_mode=WAL')
    try:
        c = conn.cursor()
        c.execute('UPDATE users SET language = ? WHERE user_id = ?', (language, user_id))
        if c.rowcount == 0:
            c.execute('INSERT INTO users (user_id, language) VALUES (?, ?)', (user_id, language))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Error setting language for user {user_id}: {e}")
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
        c.execute('SELECT user_id, is_caregiver, linked_patient, language FROM users')
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
        c.execute('SELECT user_id, is_caregiver, linked_patient, language FROM users WHERE user_id = ?', (user_id,))
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

# Language selection command
async def language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"User {user_id} issued /language command")
    keyboard = [[InlineKeyboardButton(name, callback_data=f'lang_{code}')] for code, name in LANGUAGES.items()]
    reply_markup = InlineKeyboardMarkup(keyboard)
    lang = context.user_data.get('language', get_user_language(user_id))
    await update.message.reply_text(
        get_message('select_language', lang),
        reply_markup=reply_markup
    )
    return SELECT_LANGUAGE

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"User {user_id} started the bot")
    context.user_data.clear()  # Reset state on /start
    
    # Check if user exists and has a language preference
    user = get_user_by_id(user_id)
    if user and user[3]:  # user[3] is the language column
        context.user_data['language'] = user[3]
        await show_main_menu(update, context)
    else:
        # Prompt for language selection
        keyboard = [[InlineKeyboardButton(name, callback_data=f'lang_{code}')] for code, name in LANGUAGES.items()]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            get_message('select_language', 'en'),
            reply_markup=reply_markup
        )
        return SELECT_LANGUAGE

# Show main menu based on user/admin status
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = context.user_data.get('language', get_user_language(user_id))
    
    try:
        if is_admin(user_id):
            keyboard = [
                [InlineKeyboardButton("Admin Panel", callback_data='admin_panel')],
                [InlineKeyboardButton("Access User Features", callback_data='user_mode')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            welcome_message = get_message('welcome_admin', lang)
        else:
            keyboard = [
                [InlineKeyboardButton("Book Now", callback_data='book')],
                [InlineKeyboardButton("Cancel Booking", callback_data='cancel_booking')],
                [InlineKeyboardButton("Service Info", callback_data='info')],
                [InlineKeyboardButton("Contact Support", callback_data='support')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            welcome_message = get_message('welcome_user', lang)
        
        if update.callback_query:
            await update.callback_query.message.reply_text(welcome_message, reply_markup=reply_markup)
        else:
            await update.message.reply_text(welcome_message, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error sending main menu to user {user_id}: {e}", exc_info=True)
        await (update.callback_query.message if update.callback_query else update.message).reply_text(
            get_message('error_occurred', lang)
        )

# Cancel command
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = context.user_data.get('language', get_user_language(user_id))
    logger.info(f"User {user_id} issued /cancel command")
    context.user_data.clear()  # Reset conversation state
    try:
        await update.message.reply_text(get_message('conversation_reset', lang))
    except Exception as e:
        logger.error(f"Error sending cancel response to user {user_id}: {e}")
    return ConversationHandler.END

# Health check command
async def health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = context.user_data.get('language', get_user_language(user_id))
    if not is_admin(user_id):
        try:
            await update.message.reply_text(get_message('unauthorized', lang))
        except Exception as e:
            logger.error(f"Error sending unauthorized message to user {user_id}: {e}")
        return
    try:
        stats = get_system_stats()
        conn = sqlite3.connect('doctomed.db', timeout=10)
        conn.close()
        health_status = get_message('health_status', lang,
                                    total_bookings=stats['total_bookings'],
                                    active_users=stats['active_users'],
                                    total_doctors=stats['total_doctors'])
        await update.message.reply_text(health_status)
    except Exception as e:
        logger.error(f"Health check failed for user {user_id}: {e}", exc_info=True)
        try:
            await update.message.reply_text(get_message('health_failed', lang, error=str(e)))
        except Exception as reply_error:
            logger.error(f"Failed to send health check error to user {user_id}: {reply_error}")

# Select doctor
async def select_doctor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = context.user_data.get('language', get_user_language(user_id))
    try:
        doctors = get_all_doctors()
        if not doctors:
            logger.warning("No doctors available in the database")
            await update.callback_query.message.reply_text(get_message('no_doctors', lang))
            return ConversationHandler.END
        
        keyboard = [[InlineKeyboardButton(f"{doctor[1]}", callback_data=f'doctor_{doctor[0]}')] for doctor in doctors]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.message.reply_text(
            get_message('select_doctor', lang),
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Error sending doctor selection to user {user_id}: {e}", exc_info=True)
        try:
            await update.callback_query.message.reply_text(get_message('error_occurred', lang))
        except Exception as reply_error:
            logger.error(f"Failed to send error message to user {user_id}: {reply_error}")
        context.user_data.clear()
        return ConversationHandler.END
    return SELECT_DOCTOR

# Show calendar
async def show_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE, doctor_id):
    user_id = update.effective_user.id
    lang = context.user_data.get('language', get_user_language(user_id))
    try:
        doctor = get_doctor_by_id(doctor_id)
        if not doctor:
            logger.warning(f"Doctor {doctor_id} not found")
            await update.callback_query.message.reply_text(get_message('doctor_not_found', lang))
            return ConversationHandler.END
        
        available_slots = get_available_slots(doctor_id)
        if not available_slots:
            logger.info(f"No available slots for doctor {doctor_id}")
            await update.callback_query.message.reply_text(
                get_message('no_slots', lang, doctor_name=doctor[1])
            )
            return ConversationHandler.END
        
        slots_by_date = {}
        for slot in available_slots:
            booking_date = slot[0]
            if booking_date not in slots_by_date:
                slots_by_date[booking_date] = []
            slots_by_date[booking_date].append(slot[1])
        
        message = get_message('schedule_header', lang, doctor_name=doctor[1])
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
        keyboard.append([InlineKeyboardButton(get_message('back_to_doctors', lang), callback_data='select_doctor')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.message.reply_text(
            message + get_message('select_slot', lang),
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Error sending calendar for doctor {doctor_id} to user {user_id}: {e}", exc_info=True)
        try:
            await update.callback_query.message.reply_text(get_message('error_occurred', lang))
        except Exception as reply_error:
            logger.error(f"Failed to send error message to user {user_id}: {reply_error}")
        context.user_data.clear()
        return ConversationHandler.END
    return SELECT_DOCTOR

# Button callback
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    lang = context.user_data.get('language', get_user_language(user_id))
    logger.info(f"User {user_id} triggered callback: {query.data}")
    
    try:
        is_user_admin = is_admin(user_id)
        if query.data.startswith('lang_'):
            lang_code = query.data.split('_')[1]
            if lang_code in LANGUAGES:
                context.user_data['language'] = lang_code
                set_user_language(user_id, lang_code)
                await query.message.reply_text(
                    get_message('language_changed', lang_code, language=LANGUAGES[lang_code])
                )
                await show_main_menu(update, context)
                return ConversationHandler.END
            else:
                await query.message.reply_text(get_message('error_occurred', lang))
                return
        elif query.data == 'user_mode' and is_user_admin:
            keyboard = [
                [InlineKeyboardButton("Book Now", callback_data='book')],
                [InlineKeyboardButton("Cancel Booking", callback_data='cancel_booking')],
                [InlineKeyboardButton("Service Info", callback_data='info')],
                [InlineKeyboardButton("Contact Support", callback_data='support')],
                [InlineKeyboardButton("Back to Admin Panel", callback_data='admin_panel')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(
                get_message('welcome_user', lang),
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
                await query.message.reply_text(get_message('no_bookings', lang))
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
            await query.message.reply_text(get_message('select_booking_to_cancel', lang), reply_markup=reply_markup)
        elif query.data.startswith('cancel_') and not (is_user_admin and 'admin_panel' in query.data):
            booking_id = int(query.data.split('_')[1])
            success, result = cancel_booking(booking_id)
            if success:
                booking = result
                await query.message.reply_text(
                    get_message('booking_cancelled', lang,
                                patient_name=booking[5],
                                date=booking[0],
                                time=booking[1])
                )
                try:
                    doctor = get_doctor_by_id(booking[2])
                    doctor_lang = get_user_language(booking[2])
                    await context.bot.send_message(
                        chat_id=booking[2],
                        text=get_message('doctor_cancel_notification', doctor_lang,
                                         patient_name=booking[5],
                                         date=booking[0],
                                         time=booking[1])
                    )
                except Exception as e:
                    logger.error(f"Failed to notify doctor ID {booking[2]} about cancellation: {e}")
                    await query.message.reply_text(get_message('failed_to_notify_doctor', lang))
            else:
                await query.message.reply_text(get_message('failed_to_cancel', lang, reason=result))
        elif query.data == 'info' and not (is_user_admin and 'admin_panel' in query.data):
            doctors = get_all_doctors()
            doctor_list = "\n".join([f"- {doctor[1]}" for doctor in doctors]) if doctors else get_message('no_doctors_available', lang)
            await query.message.reply_text(
                get_message('service_info', lang, doctor_list=doctor_list)
            )
        elif query.data == 'support' and not (is_user_admin and 'admin_panel' in query.data):
            context.user_data['state'] = SUPPORT_REQUEST
            await query.message.reply_text(get_message('support_prompt', lang))
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
            await query.message.reply_text(get_message('admin_panel', lang), reply_markup=reply_markup)
        elif query.data == 'back_to_start' and is_user_admin:
            await start(update, context)
        elif query.data == 'admin_bookings' and is_user_admin:
            bookings = get_all_bookings()
            if not bookings:
                await query.message.reply_text(get_message('no_bookings_admin', lang))
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
            await query.message.reply_text(get_message('admin_bookings', lang), reply_markup=reply_markup)
        elif query.data.startswith('admin_booking_') and is_user_admin:
            booking_id = int(query.data.split('_')[2])
            booking = get_booking_by_id(booking_id)
            if booking:
                keyboard = [
                    [InlineKeyboardButton(get_message('admin_cancel_booking', lang), callback_data=f'admin_cancel_{booking_id}')],
                    [InlineKeyboardButton(get_message('back_to_bookings', lang), callback_data='admin_bookings')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.message.reply_text(
                    get_message('booking_details', lang,
                                id=booking[BOOKING_FIELDS['id']],
                                user_id=booking[BOOKING_FIELDS['user_id']],
                                patient_name=booking[BOOKING_FIELDS['patient_name']],
                                dob=booking[BOOKING_FIELDS['patient_dob']],
                                time=booking[BOOKING_FIELDS['time_slot']],
                                date=booking[BOOKING_FIELDS['booking_date']],
                                doctor_id=booking[BOOKING_FIELDS['doctor_id']],
                                status=booking[BOOKING_FIELDS['status']]),
                    reply_markup=reply_markup
                )
        elif query.data.startswith('admin_cancel_') and is_user_admin:
            booking_id = int(query.data.split('_')[2])
            success, result = cancel_booking(booking_id)
            if success:
                await query.message.reply_text(get_message('admin_booking_cancelled', lang, id=booking_id))
            else:
                await query.message.reply_text(get_message('failed_to_cancel', lang, reason=result))
        elif query.data == 'admin_users' and is_user_admin:
            users = get_all_users()
            if not users:
                await query.message.reply_text(get_message('no_users', lang))
                return
            keyboard = [[InlineKeyboardButton(f"User ID: {u[0]}", callback_data=f'admin_user_{u[0]}')] for u in users]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(get_message('admin_users', lang), reply_markup=reply_markup)
        elif query.data.startswith('admin_user_') and is_user_admin:
            user_id = int(query.data.split('_')[2])
            user = get_user_by_id(user_id)
            if user:
                keyboard = [
                    [InlineKeyboardButton(get_message('edit_user', lang), callback_data=f'admin_edit_user_{user_id}')],
                    [InlineKeyboardButton(get_message('delete_user', lang), callback_data=f'admin_delete_user_{user_id}')],
                    [InlineKeyboardButton(get_message('back_to_users', lang), callback_data='admin_users')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.message.reply_text(
                    get_message('user_details', lang,
                                id=user[0],
                                caregiver='Yes' if user[1] else 'No',
                                linked_patient=user[2] or 'None'),
                    reply_markup=reply_markup
                )
        elif query.data.startswith('admin_edit_user_') and is_user_admin:
            context.user_data['edit_user_id'] = int(query.data.split('_')[3])
            await query.message.reply_text(get_message('admin_edit_user_prompt', lang))
            return USER_EDIT
        elif query.data.startswith('admin_delete_user_') and is_user_admin:
            user_id = int(query.data.split('_')[3])
            delete_user(user_id)
            await query.message.reply_text(get_message('user_deleted', lang, id=user_id))
        elif query.data == 'admin_add' and is_user_admin:
            await query.message.reply_text(get_message('admin_add_prompt', lang))
            return ADMIN_ADD
        elif query.data == 'admin_remove' and is_user_admin:
            admins = get_all_admins()
            if not admins:
                await query.message.reply_text(get_message('no_admins', lang))
                return
            keyboard = [[InlineKeyboardButton(f"Admin ID: {a[0]}", callback_data=f'admin_remove_id_{a[0]}')] for a in admins]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(get_message('admin_remove', lang), reply_markup=reply_markup)
        elif query.data.startswith('admin_remove_id_') and is_user_admin:
            admin_id = int(query.data.split('_')[3])
            remove_admin(admin_id)
            await query.message.reply_text(get_message('admin_removed', lang, id=admin_id))
        elif query.data == 'admin_slots' and is_user_admin:
            keyboard = [
                [InlineKeyboardButton(get_message('admin_add_slot', lang), callback_data='admin_add_slot')],
                [InlineKeyboardButton(get_message('view_slots', lang), callback_data='admin_view_slots')],
                [InlineKeyboardButton(get_message('back_to_admin', lang), callback_data='admin_panel')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(get_message('admin_slots', lang), reply_markup=reply_markup)
        elif query.data == 'admin_doctors' and is_user_admin:
            keyboard = [
                [InlineKeyboardButton(get_message('admin_add_doctor', lang), callback_data='admin_add_doctor')],
                [InlineKeyboardButton(get_message('view_doctors', lang), callback_data='admin_view_doctors')],
                [InlineKeyboardButton(get_message('back_to_admin', lang), callback_data='admin_panel')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(get_message('admin_doctors', lang), reply_markup=reply_markup)
        elif query.data == 'admin_add_slot' and is_user_admin:
            context.user_data['state'] = ADMIN_ADD_SLOT
            await query.message.reply_text(get_message('admin_add_slot_prompt', lang))
            return ADMIN_ADD_SLOT
        elif query.data == 'admin_add_doctor' and is_user_admin:
            context.user_data['state'] = ADMIN_ADD_DOCTOR
            await query.message.reply_text(get_message('admin_add_doctor_prompt', lang))
            return ADMIN_ADD_DOCTOR
        elif query.data == 'admin_view_slots' and is_user_admin:
            slots = get_available_slots_for_all_doctors()
            if not slots:
                await query.message.reply_text(get_message('no_slots_available', lang))
                return
            message = get_message('slots_list', lang)
            for slot in slots:
                booking_date = datetime.strptime(slot[0], '%Y-%m-%d')
                day_name = calendar.day_name[booking_date.weekday()]
                message += f"{slot[0]} ({day_name}), {slot[1]} with {slot[2]}\n"
            await query.message.reply_text(message)
        elif query.data == 'admin_view_doctors' and is_user_admin:
            doctors = get_all_doctors()
            if not doctors:
                await query.message.reply_text(get_message('no_doctors_admin', lang))
                return
            message = get_message('doctors_list', lang)
            for doctor in doctors:
                message += f"ID: {doctor[0]}, Name: {doctor[1]}\n"
            await query.message.reply_text(message)
        elif query.data == 'admin_stats' and is_user_admin:
            stats = get_system_stats()
            await query.message.reply_text(
                get_message('system_stats', lang,
                            total_bookings=stats['total_bookings'],
                            active_users=stats['active_users'],
                            total_admins=stats['total_admins'],
                            total_doctors=stats['total_doctors'])
            )
        elif query.data == 'admin_broadcast' and is_user_admin:
            await query.message.reply_text(get_message('broadcast_prompt', lang))
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
            await query.message.reply_text(get_message('patient_name_prompt', lang))
            return PATIENT_NAME
        elif query.data == 'book_self' and not (is_user_admin and 'admin_panel' in query.data):
            conn = sqlite3.connect('doctomed.db', timeout=10)
            conn.execute('PRAGMA journal_mode=WAL')
            try:
                c = conn.cursor()
                c.execute('INSERT OR REPLACE INTO users (user_id, is_caregiver, linked_patient, language) VALUES (?, ?, ?, ?)',
                          (user_id, 0, None, lang))
                conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Error registering user {user_id} as self: {e}")
                await query.message.reply_text(get_message('error_occurred', lang))
                return
            finally:
                conn.close()
            await select_doctor(update, context)
            return SELECT_DOCTOR
        elif query.data == 'book_caregiver' and not (is_user_admin and 'admin_panel' in query.data):
            context.user_data['state'] = CAREGIVER_LINK
            await query.message.reply_text(get_message('caregiver_patient_prompt', lang))
            return CAREGIVER_LINK
        elif query.data.startswith('approve_booking_'):
            booking_id = int(query.data.split('_')[2])
            booking = get_booking_by_id(booking_id)
            if not booking:
                await query.message.reply_text(get_message('booking_not_found', lang))
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
                await query.message.reply_text(get_message('error_occurred', lang))
                return
            finally:
                conn.close()
            doctor = get_doctor_by_id(booking[BOOKING_FIELDS['doctor_id']])
            doctor_name = doctor[1] if doctor else "Doctor"
            user_lang = get_user_language(booking[BOOKING_FIELDS['user_id']])
            doctor_lang = get_user_language(booking[BOOKING_FIELDS['doctor_id']])
            booking_date = str(booking[BOOKING_FIELDS['booking_date']])
            try:
                booking_date_dt = datetime.strptime(booking_date, '%Y-%m-%d')
            except ValueError as e:
                logger.error(f"Date parsing error for booking {booking_id} in approve_booking: {e}, booking data: {booking}")
                await query.message.reply_text(get_message('invalid_booking_date', lang))
                return
            day_name = calendar.day_name[booking_date_dt.weekday()]
            current_date = date.today().strftime('%Y-%m-%d')
            date_display = "today" if booking[BOOKING_FIELDS['booking_date']] == current_date else f"on {booking[BOOKING_FIELDS['booking_date']]} ({day_name})"
            try:
                await context.bot.send_message(
                    chat_id=booking[BOOKING_FIELDS['user_id']],
                    text=get_message('booking_approved', user_lang,
                                     doctor_name=doctor_name,
                                     date_display=date_display,
                                     time=booking[BOOKING_FIELDS['time_slot']])
                )
            except Exception as e:
                logger.error(f"Failed to notify user {booking[BOOKING_FIELDS['user_id']]} about approval: {e}")
            try:
                await context.bot.send_message(
                    chat_id=booking[BOOKING_FIELDS['doctor_id']],
                    text=get_message('doctor_approve_notification', doctor_lang,
                                     patient_name=booking[BOOKING_FIELDS['patient_name']],
                                     date=booking[BOOKING_FIELDS['booking_date']],
                                     day_name=day_name,
                                     time=booking[BOOKING_FIELDS['time_slot']],
                                     dob=booking[BOOKING_FIELDS['patient_dob']],
                                     user_id=booking[BOOKING_FIELDS['user_id']])
                )
            except Exception as e:
                logger.error(f"Failed to notify doctor {booking[BOOKING_FIELDS['doctor_id']]} about approval: {e}")
            await query.message.reply_text(get_message('booking_approved_admin', lang, id=booking_id))
        elif query.data.startswith('reject_booking_'):
            booking_id = int(query.data.split('_')[2])
            booking = get_booking_by_id(booking_id)
            if not booking:
                await query.message.reply_text(get_message('booking_not_found', lang))
                return
            conn = sqlite3.connect('doctomed.db', timeout=10)
            conn.execute('PRAGMA journal_mode=WAL')
            try:
                c = conn.cursor()
                c.execute('UPDATE bookings SET status = ?, confirmed = 0 WHERE id = ?', ('rejected', booking_id))
                conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Error rejecting booking {booking_id}: {e}")
                await query.message.reply_text(get_message('error_occurred', lang))
                return
            finally:
                conn.close()
            user_lang = get_user_language(booking[BOOKING_FIELDS['user_id']])
            try:
                await context.bot.send_message(
                    chat_id=booking[BOOKING_FIELDS['user_id']],
                    text=get_message('booking_rejected', user_lang,
                                     patient_name=booking[BOOKING_FIELDS['patient_name']],
                                     date=booking[BOOKING_FIELDS['booking_date']],
                                     time=booking[BOOKING_FIELDS['time_slot']])
                )
            except Exception as e:
                logger.error(f"Failed to notify user {booking[BOOKING_FIELDS['user_id']]} about rejection: {e}")
            await query.message.reply_text(get_message('booking_rejected_admin', lang, id=booking_id))
        else:
            await query.message.reply_text(get_message('invalid_action', lang))
    except Exception as e:
        if "429" in str(e):
            logger.warning(f"Rate limit exceeded for user {user_id}: {e}")
            try:
                await query.message.reply_text(get_message('rate_limit_exceeded', lang))
            except Exception as reply_error:
                logger.error(f"Failed to send rate limit message to user {user_id}: {reply_error}")
            return
        logger.error(f"Error in button_callback for user {user_id}, callback {query.data}: {e}", exc_info=True)
        try:
            await query.message.reply_text(get_message('error_occurred', lang))
        except Exception as reply_error:
            logger.error(f"Failed to send error message to user {user_id}: {reply_error}")
        context.user_data.clear()
        return

# Handle booking start
async def handle_booking_start(query, context):
    user_id = query.from_user.id
    lang = context.user_data.get('language', get_user_language(user_id))
    conn = sqlite3.connect('doctomed.db', timeout=10)
    conn.execute('PRAGMA journal_mode=WAL')
    try:
        c = conn.cursor()
        c.execute('SELECT is_caregiver FROM users WHERE user_id = ?', (user_id,))
        user = c.fetchone()
        if not user:
            keyboard = [
                [InlineKeyboardButton(get_message('book_self', lang), callback_data='book_self')],
                [InlineKeyboardButton(get_message('book_caregiver', lang), callback_data='book_caregiver')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(
                get_message('booking_for', lang),
                reply_markup=reply_markup
            )
            return
        await select_doctor(query, context)
        return SELECT_DOCTOR
    except Exception as e:
        logger.error(f"Error in handle_booking_start for user {user_id}: {e}", exc_info=True)
        try:
            await query.message.reply_text(get_message('error_occurred', lang))
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
    lang = context.user_data.get('language', get_user_language(user_id))
    logger.info(f"User {user_id} sent message: {text}, state: {context.user_data.get('state')}")
    
    try:
        is_user_admin = is_admin(user_id)
        if context.user_data.get('state') == CAREGIVER_LINK and not is_user_admin:
            conn = sqlite3.connect('doctomed.db', timeout=10)
            conn.execute('PRAGMA journal_mode=WAL')
            try:
                c = conn.cursor()
                c.execute('INSERT OR REPLACE INTO users (user_id, is_caregiver, linked_patient, language) VALUES (?, ?, ?, ?)',
                          (user_id, 1, text, lang))
                conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Error registering caregiver for user {user_id}: {e}")
                await update.message.reply_text(get_message('error_occurred', lang))
                return ConversationHandler.END
            finally:
                conn.close()
            context.user_data.pop('state', None)
            await update.message.reply_text(
                get_message('caregiver_registered', lang, patient_name=text)
            )
            await select_doctor(update, context)
            return SELECT_DOCTOR
        elif context.user_data.get('state') == PATIENT_NAME and not is_user_admin:
            context.user_data['patient_name'] = text
            context.user_data['state'] = PATIENT_DOB
            await update.message.reply_text(get_message('patient_dob_prompt', lang))
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
                    await update.message.reply_text(get_message('error_occurred', lang))
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
                        await update.message.reply_text(get_message('slot_unavailable', lang))
                        context.user_data.clear()
                        return ConversationHandler.END
                    
                    c.execute('INSERT INTO bookings (user_id, patient_name, patient_dob, time_slot, booking_date, doctor_id, status, confirmed) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                              (user_id, patient_name, patient_dob, time_slot, booking_date, doctor_id, 'pending', 0))
                    booking_id = c.lastrowid
                    conn.commit()
                except sqlite3.Error as e:
                    logger.error(f"Error inserting booking for user {user_id}: {e}")
                    await update.message.reply_text(get_message('booking_error', lang))
                    context.user_data.clear()
                    return ConversationHandler.END
                finally:
                    conn.close()
                
                username = update.message.from_user.username or "N/A"
                booking_date_dt = datetime.strptime(booking_date, '%Y-%m-%d')
                day_name = calendar.day_name[booking_date_dt.weekday()]
                doctor_lang = get_user_language(doctor_id)
                try:
                    await context.bot.send_message(
                        chat_id=doctor_id,
                        text=get_message('doctor_notification', doctor_lang,
                                         patient_name=patient_name,
                                         dob=patient_dob,
                                         date=booking_date,
                                         day_name=day_name,
                                         time=time_slot,
                                         user_id=user_id,
                                         username=username),
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton(get_message('approve', doctor_lang), callback_data=f'approve_booking_{booking_id}'),
                             InlineKeyboardButton(get_message('reject', doctor_lang), callback_data=f'reject_booking_{booking_id}')]
                        ])
                    )
                except Exception as e:
                    error_message = f"Failed to notify doctor ID {doctor_id}: {e}"
                    logger.error(error_message)
                    user_message = get_message('doctor_notification_error', lang, reason=str(e))
                    if "chat not found" in str(e).lower():
                        user_message = get_message('doctor_notification_error', lang, reason="Doctor's Telegram account not found. Please ensure the doctor has started the bot.")
                    elif "blocked" in str(e).lower():
                        user_message = get_message('doctor_notification_error', lang, reason="Bot is blocked by the doctor. Please contact the doctor to unblock the bot.")
                    await update.message.reply_text(user_message)
                    for admin_id in ADMIN_IDS:
                        try:
                            admin_lang = get_user_language(int(admin_id))
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
                    get_message('booking_submitted', lang,
                                patient_name=patient_name,
                                dob=patient_dob,
                                date=booking_date,
                                time=time_slot)
                )
                
                context.user_data.clear()
                return ConversationHandler.END
            except ValueError:
                await update.message.reply_text(get_message('invalid_date_format', lang))
                return PATIENT_DOB
        elif context.user_data.get('state') == ADMIN_ADD and is_user_admin:
            try:
                new_admin_id = int(text)
                add_admin(new_admin_id)
                await update.message.reply_text(get_message('admin_added', lang, id=new_admin_id))
            except ValueError:
                await update.message.reply_text(get_message('invalid_admin_id', lang))
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
                    await update.message.reply_text(get_message('error_occurred', lang))
                    return ConversationHandler.END
                finally:
                    conn.close()
                await update.message.reply_text(get_message('user_updated', lang, id=edit_user_id))
            except ValueError:
                await update.message.reply_text(get_message('invalid_user_format', lang))
            context.user_data.pop('state', None)
            context.user_data.pop('edit_user_id', None)
            return ConversationHandler.END
        elif context.user_data.get('state') == BROADCAST and is_user_admin:
            users = get_all_users()
            success_count = 0
            failure_count = 0
            for user in users:
                user_lang = user[3] if user[3] in LANGUAGES else 'en'
                try:
                    await context.bot.send_message(chat_id=user[0], text=f"📢 {get_message('announcement', user_lang, default='Announcement')}: {text}")
                    success_count += 1
                    await asyncio.sleep(0.1)  # Rate limit delay
                except Exception as e:
                    logger.error(f"Failed to send broadcast to User ID {user[0]}: {e}")
                    failure_count += 1
            await update.message.reply_text(
                get_message('broadcast_result', lang, success=success_count, failed=failure_count)
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
                    await update.message.reply_text(get_message('invalid_doctor_id', lang))
                    return ADMIN_ADD_SLOT
                except sqlite3.Error as e:
                    logger.error(f"Error adding doctor slot: {e}")
                    await update.message.reply_text(get_message('error_occurred', lang))
                    return ConversationHandler.END
                finally:
                    conn.close()
                await update.message.reply_text(
                    get_message('slot_added', lang, date=booking_date, time=time_slot, doctor_id=doctor_id)
                )
            except ValueError:
                await update.message.reply_text(get_message('invalid_slot_format', lang))
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
                    await update.message.reply_text(get_message('error_occurred', lang))
                    return ConversationHandler.END
                finally:
                    conn.close()
                await update.message.reply_text(
                    get_message('doctor_added', lang, name=name, id=user_id)
                )
            except ValueError:
                await update.message.reply_text(get_message('invalid_doctor_format', lang))
                return ADMIN_ADD_DOCTOR
            context.user_data.pop('state', None)
            return ConversationHandler.END
        elif context.user_data.get('state') == SUPPORT_REQUEST and not is_user_admin:
            if log_support_request(user_id, text):
                for admin_id in ADMIN_IDS:
                    try:
                        admin_lang = get_user_language(int(admin_id))
                        username = update.message.from_user.username or "N/A"
                        await context.bot.send_message(
                            chat_id=int(admin_id),
                            text=(
                                f"🔔 {get_message('new_support_request', admin_lang, default='New support request')} "
                                f"from User ID {user_id} (Username: {username}):\n"
                                f"Message: {text}"
                            )
                        )
                        await asyncio.sleep(0.1)  # Rate limit delay
                    except Exception as e:
                        logger.error(f"Failed to notify admin ID {admin_id} about support request: {e}")
                await update.message.reply_text(get_message('support_submitted', lang))
            else:
                await update.message.reply_text(get_message('support_failed', lang))
            context.user_data.pop('state', None)
            return ConversationHandler.END
        else:
            await update.message.reply_text(get_message('invalid_action', lang))
            return ConversationHandler.END
    except Exception as e:
        if "429" in str(e):
            logger.warning(f"Rate limit exceeded for user {user_id}: {e}")
            try:
                await update.message.reply_text(get_message('rate_limit_exceeded', lang))
            except Exception as reply_error:
                logger.error(f"Failed to send rate limit message to user {user_id}: {reply_error}")
            return ConversationHandler.END
        logger.error(f"Error in handle_message for user {user_id}, text: {text}: {e}", exc_info=True)
        try:
            await update.message.reply_text(get_message('error_occurred', lang))
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
                SELECT_LANGUAGE: [CallbackQueryHandler(button_callback, pattern='^lang_')],
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
                CommandHandler('cancel', cancel),
                CommandHandler('language', language)
            ]
        )
        
        application.add_handler(CommandHandler('start', start))
        application.add_handler(CommandHandler('cancel', cancel))
        application.add_handler(CommandHandler('language', language))
        application.add_handler(CommandHandler('health', health))
        application.add_handler(conv_handler)
        
        logger.info("Starting bot polling")
        application.run_polling(poll_interval=1.0, timeout=10)
    except Exception as e:
        logger.error(f"Error starting bot: {e}", exc_info=True)

if __name__ == '__main__':
    main()
