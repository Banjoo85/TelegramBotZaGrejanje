import os
import logging
import json
import yagmail
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes # Uvezeno za rešavanje "ContextTypes is not defined" greške
)
from telegram.error import TelegramError # Uvezeno za rukovanje Telegram greškama

# Omogući logovanje
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING) # Smanji logovanje za httpx
logger = logging.getLogger(__name__)

# Učitaj varijable okruženja iz .env fajla (koristi se samo lokalno)
# Na Renderu se ove varijable setuju direktno u dashboardu
load_dotenv()

# Environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")

# Dodatne varijable za Render deployment
WEB_SERVICE_URL = os.getenv('WEB_SERVICE_URL')
PORT = int(os.environ.get('PORT', 8080)) # Render uvek dodeljuje port, obično 8080
# KLJUČNO: ON_RENDER proverava da li je varijabla okruženja "ON_RENDER" postavljena na "true" (mala slova)
ON_RENDER = os.getenv("ON_RENDER", "false").lower() == "true"

# Stanja za ConversationHandler
CHOOSE_LANGUAGE, START, SERVICES, ABOUT_US, CONTACT_US, SEND_EMAIL = range(6)
ENTER_MESSAGE, COLLECT_CONTACT_INFO, CONFIRM_SEND = range(6, 9)

# Dictionary za čuvanje korisničkih informacija tokom konverzacije
user_data = {}

# Učitavanje prevoda
def load_messages(lang_code):
    try:
        with open(f'messages_{lang_code}.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Translation file messages_{lang_code}.json not found.")
        return {} # Vrati prazan rečnik ako fajl ne postoji

messages = {
    'sr': load_messages('sr'),
    'en': load_messages('en'),
    'ru': load_messages('ru')
}

# --- Pomoćne funkcije ---
def get_message(lang_code, key):
    return messages.get(lang_code, {}).get(key, f"_{key}_ missing")

def get_current_language(update: Update):
    chat_id = update.effective_chat.id
    return user_data.get(chat_id, {}).get('language', 'sr') # Default na srpski

# --- Komande i Handleri ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    current_lang = get_current_language(update)
    user_data.setdefault(chat_id, {})['language'] = current_lang # Osiguraj da je jezik postavljen

    keyboard = [
        [InlineKeyboardButton(get_message(current_lang, "services_button"), callback_data='services')],
        [InlineKeyboardButton(get_message(current_lang, "about_us_button"), callback_data='about_us')],
        [InlineKeyboardButton(get_message(current_lang, "contact_us_button"), callback_data='contact_us')],
        [InlineKeyboardButton(get_message(current_lang, "language_button"), callback_data='language')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(get_message(current_lang, "welcome_message"), reply_markup=reply_markup)
    return START

async def choose_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("Srpski", callback_data='lang_sr')],
        [InlineKeyboardButton("English", callback_data='lang_en')],
        [InlineKeyboardButton("Русский", callback_data='lang_ru')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(get_message(get_current_language(update), "choose_language_message"), reply_markup=reply_markup)
    return CHOOSE_LANGUAGE

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    chat_id = update.effective_chat.id
    lang_code = query.data.replace('lang_', '')
    user_data.setdefault(chat_id, {})['language'] = lang_code # Postavi izabrani jezik

    current_lang = get_current_language(update)
    keyboard = [
        [InlineKeyboardButton(get_message(current_lang, "services_button"), callback_data='services')],
        [InlineKeyboardButton(get_message(current_lang, "about_us_button"), callback_data='about_us')],
        [InlineKeyboardButton(get_message(current_lang, "contact_us_button"), callback_data='contact_us')],
        [InlineKeyboardButton(get_message(current_lang, "language_button"), callback_data='language')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(get_message(current_lang, "language_set_message"), reply_markup=reply_markup)
    return START

async def show_services(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    current_lang = get_current_language(update)

    keyboard = [[InlineKeyboardButton(get_message(current_lang, "back_to_main_menu_button"), callback_data='main_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(get_message(current_lang, "services_message"), reply_markup=reply_markup)
    return SERVICES

async def show_about_us(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    current_lang = get_current_language(update)

    keyboard = [[InlineKeyboardButton(get_message(current_lang, "back_to_main_menu_button"), callback_data='main_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(get_message(current_lang, "about_us_message"), reply_markup=reply_markup)
    return ABOUT_US

async def show_contact_us(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    current_lang = get_current_language(update)

    keyboard = [[InlineKeyboardButton(get_message(current_lang, "send_email_button"), callback_data='send_email')],
                [InlineKeyboardButton(get_message(current_lang, "back_to_main_menu_button"), callback_data='main_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(get_message(current_lang, "contact_us_message"), reply_markup=reply_markup)
    return CONTACT_US

async def back_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    current_lang = get_current_language(update)

    keyboard = [
        [InlineKeyboardButton(get_message(current_lang, "services_button"), callback_data='services')],
        [InlineKeyboardButton(get_message(current_lang, "about_us_button"), callback_data='about_us')],
        [InlineKeyboardButton(get_message(current_lang, "contact_us_button"), callback_data='contact_us')],
        [InlineKeyboardButton(get_message(current_lang, "language_button"), callback_data='language')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(get_message(current_lang, "welcome_message"), reply_markup=reply_markup)
    return START

async def request_email_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    current_lang = get_current_language(update)

    await query.edit_message_text(get_message(current_lang, "enter_email_message"))
    return ENTER_MESSAGE

async def collect_email_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    current_lang = get_current_language(update)

    user_data[chat_id]['email_message'] = update.message.text
    await update.message.reply_text(get_message(current_lang, "enter_contact_info"))
    return COLLECT_CONTACT_INFO

async def collect_contact_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    current_lang = get_current_language(update)

    user_data[chat_id]['contact_info'] = update.message.text

    # Prikazivanje unetih podataka za potvrdu
    message_text = get_message(current_lang, "confirm_email_send")
    message_text += f"\n\n{get_message(current_lang, 'your_message')}: {user_data[chat_id]['email_message']}"
    message_text += f"\n{get_message(current_lang, 'your_contact_info')}: {user_data[chat_id]['contact_info']}"

    keyboard = [
        [InlineKeyboardButton(get_message(current_lang, "yes_send_button"), callback_data='confirm_send')],
        [InlineKeyboardButton(get_message(current_lang, "no_cancel_button"), callback_data='cancel_send')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(message_text, reply_markup=reply_markup)
    return CONFIRM_SEND

async def send_email_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    current_lang = get_current_language(update)

    if query.data == 'confirm_send':
        email_message = user_data[chat_id].get('email_message')
        contact_info = user_data[chat_id].get('contact_info')
        telegram_username = update.effective_user.username
        telegram_id = update.effective_user.id

        subject = f"Novi upit sa Telegram bota od @{telegram_username} ({telegram_id})"
        content = [
            f"Korisnička poruka:\n{email_message}\n\n",
            f"Kontakt informacije korisnika:\n{contact_info}\n\n",
            f"Telegram korisničko ime: @{telegram_username}\n",
            f"Telegram ID: {telegram_id}"
        ]

        try:
            # yagmail.SMTP se inicijalizuje sa akreditivima iz environment varijabli
            # NE pokušava da pročita ~/.yagmail fajl ako su user i password dati
            with yagmail.SMTP(user=EMAIL_ADDRESS, password=EMAIL_APP_PASSWORD) as yag:
                yag.send(
                    to=ADMIN_EMAIL,
                    bcc=ADMIN_EMAIL, # Šalje kopiju i adminu kao BCC
                    subject=subject,
                    contents=content
                )
            logger.info(f"Email successfully sent from {EMAIL_ADDRESS} to {ADMIN_EMAIL}")
            await query.edit_message_text(get_message(current_lang, "email_sent_success"))
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            await query.edit_message_text(get_message(current_lang, "email_sent_error"))

    else: # if query.data == 'cancel_send'
        await query.edit_message_text(get_message(current_lang, "email_send_cancelled"))

    # Resetovanje user_data za trenutnog korisnika
    if chat_id in user_data:
        del user_data[chat_id]['email_message']
        del user_data[chat_id]['contact_info']

    return await back_to_main_menu(update, context)


async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    current_lang = get_current_language(update)
    await update.message.reply_text(get_message(current_lang, "conversation_cancelled"))
    return ConversationHandler.END

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_lang = get_current_language(update)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=get_message(current_lang, "unknown_command"))

# Glavna funkcija za pokretanje bota
def main() -> None:
    # Kreiranje Application objekta
    application = Application.builder().token(BOT_TOKEN).build()

    # ConversationHandler za upravljanje stanjima
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start_command)],
        states={
            START: [
                CallbackQueryHandler(show_services, pattern='^services$'),
                CallbackQueryHandler(show_about_us, pattern='^about_us$'),
                CallbackQueryHandler(show_contact_us, pattern='^contact_us$'),
                CallbackQueryHandler(choose_language, pattern='^language$'),
            ],
            CHOOSE_LANGUAGE: [
                CallbackQueryHandler(set_language, pattern='^lang_'),
            ],
            SERVICES: [
                CallbackQueryHandler(back_to_main_menu, pattern='^main_menu$'),
            ],
            ABOUT_US: [
                CallbackQueryHandler(back_to_main_menu, pattern='^main_menu$'),
            ],
            CONTACT_US: [
                CallbackQueryHandler(request_email_message, pattern='^send_email$'),
                CallbackQueryHandler(back_to_main_menu, pattern='^main_menu$'),
            ],
            ENTER_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, collect_email_message),
            ],
            COLLECT_CONTACT_INFO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, collect_contact_info),
            ],
            CONFIRM_SEND: [
                CallbackQueryHandler(send_email_to_admin, pattern='^confirm_send$|^cancel_send$'),
                CallbackQueryHandler(back_to_main_menu, pattern='^main_menu$'), # Omogući povratak na glavni meni
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation), CommandHandler("start", start_command)],
    )

    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.COMMAND, unknown)) # Hvata nepoznate komande

    # Logika za pokretanje bota (Webhook vs. Polling)
    if ON_RENDER:
        # Podesite webhook URL
        webhook_url_full = f"{WEB_SERVICE_URL}/{BOT_TOKEN}"

        logging.info(f"Bot pokrenut u webhook modu na portu {PORT}, URL: {webhook_url_full}")
        # Briše prethodne webhookove i postavlja novi
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=BOT_TOKEN,
            webhook_url=webhook_url_full
        )
    else:
        logging.info("Bot pokrenut u lokalnom modu (polling)...")
        application.run_polling(poll_interval=1.0) # Možete podesiti interval po potrebi

# Pokreni bota
if __name__ == "__main__":
    main()