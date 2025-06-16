import logging
import smtplib
import os
import yagmail
from datetime import datetime, timedelta

from dotenv import load_dotenv

# --- DODATO: IMPORTI ZA PYTHON-TELEGRAM-BOT BIBLIOTEKU ---
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# Učitavanje .env fajla za sigurne podatke
load_dotenv()

# --- POSTAVLJANJE LOGGINGA ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- TELEGRAM TOKEN I WEBHOOK URL ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# --- PODACI ZA EMAIL ---
YAGMAIL_USER = os.getenv("YAGMAIL_USER")
YAGMAIL_APP_PASSWORD = os.getenv("YAGMAIL_APP_PASSWORD")

# Telegram ID-ovi admina koji će primati obaveštenja
ADMIN_IDS = []
admin_id_str = os.getenv("TELEGRAM_ADMIN_ID")
if admin_id_str:
    try:
        ADMIN_IDS.append(int(admin_id_str))
        logger.info(f"Admin ID loaded: {ADMIN_IDS}")
    except ValueError:
        logger.error(f"TELEGRAM_ADMIN_ID is not a valid integer: {admin_id_str}")
else:
    logger.warning("TELEGRAM_ADMIN_ID is not set in environment variables.")

# --- DEFINICIJE STANJA ZA CONVERSATIONHANDLER ---
# Ovo mora biti definisano pre main() funkcije
(
    SELECTING_COUNTRY,
    SELECTING_INSTALLATION_TYPE,
    SELECTING_HEATING_SYSTEM,
    SELECTING_HEAT_PUMP_SUBTYPE,
    SELECTING_OBJECT_TYPE,
    ASKING_FOR_AREA,
    ASKING_FOR_FLOORS,
    ASKING_FOR_SKETCH,
    ASKING_FOR_FULL_NAME,
    ASKING_FOR_PHONE,
    ASKING_FOR_EMAIL,
    FINISH,
) = range(12) # Imaš 12 stanja, pa je 12 ispravno

# --- FUNKCIJE ZA SLANJE MAILA ---
def send_email_notification(data):
    """
    Šalje email obaveštenje sa prikupljenim podacima.
    """
    send_to = os.getenv("EMAIL_RECIPIENT", "igor.boskovic@example.com")
    bcc_recipients = [os.getenv("EMAIL_BCC", "banjooo85@gmail.com")]
    
    subject = "Novi upit sa Telegram bota: Toplotna Pumpa/Grejanje"
    
    body_html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ width: 80%; margin: 20px auto; padding: 20px; border: 1px solid #ddd; border-radius: 8px; background-color: #f9f9f9; }}
            h2 {{ color: #0056b3; }}
            ul {{ list-style: none; padding: 0; }}
            li {{ margin-bottom: 10px; }}
            strong {{ color: #0056b3; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Novi upit sa Telegram bota:</h2>
            <ul>
                <li><strong>Zemlja:</strong> {data.get('country', 'Nije uneto')}</li>
                <li><strong>Tip instalacije:</strong> {data.get('installation_type', 'Nije uneto')}</li>
                <li><strong>Sistem grejanja:</strong> {data.get('heating_system', 'Nije uneto')}</li>
                <li><strong>Podtip TP:</strong> {data.get('heat_pump_subtype', 'Nije uneto')}</li>
                <li><strong>Tip objekta:</strong> {data.get('object_type', 'Nije uneto')}</li>
                <li><strong>Površina:</strong> {data.get('area', 'Nije uneto')}</li>
                <li><strong>Spratnost:</strong> {data.get('floors', 'Nije uneto')}</li>
                <li><strong>Skica priložena:</strong> {data.get('sketch_attached', 'Nije uneto')}</li>
                <li><strong>Ime i prezime:</strong> {data.get('full_name', 'Nije uneto')}</li>
                <li><strong>Telefon:</strong> {data.get('phone_number', 'Nije uneto')}</li>
                <li><strong>Email korisnika:</strong> {data.get('user_email', 'Nije uneto')}</li>
            </ul>
            <p>Korisnik ID: {data.get('user_id', 'Nije poznat')}</p>
        </div>
    </body>
    </html>
    """
    
    if not YAGMAIL_USER or not YAGMAIL_APP_PASSWORD:
        logger.error("YAGMAIL_USER or YAGMAIL_APP_PASSWORD environment variables are not set. Email cannot be sent.")
        return False

    try:
        logger.info(f"Pokušavam da pošaljem email sa: {YAGMAIL_USER} na: {send_to}, BCC: {bcc_recipients}")
        yag = yagmail.SMTP(user=YAGMAIL_USER, password=YAGMAIL_APP_PASSWORD)
        yag.send(to=send_to, subject=subject, contents=body_html, bcc=bcc_recipients)
        logger.info(f"Email sa upitom uspešno poslat na {send_to} i BCC: {bcc_recipients}.")
        return True
    except Exception as e:
        logger.error(f"Greška pri slanju emaila: {e}")
        if isinstance(e, smtplib.SMTPAuthenticationError):
            logger.error("SMTP Authentication Error: Check YAGMAIL_USER and YAGMAIL_APP_PASSWORD (or general password) and ensure App Password is used for Gmail.")
        elif isinstance(e, smtplib.SMTPServerDisconnected):
            logger.error("SMTP Server Disconnected: Problem connecting to mail server. Check host/port or network.")
        return False

# --- DEFINICIJE HANDLER FUNKCIJA (MORAJU BITI DEFINISANE PRE main()) ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Počinje konverzaciju i traži zemlju."""
    user = update.effective_user
    await update.message.reply_html(
        f"Zdravo {user.mention_html()}! Dobrodošli. Ja sam bot za upite vezane za grejanje i toplotne pumpe.\n"
        "Za početak upita, molim vas unesite zemlju (npr. Srbija):"
    )
    return SELECTING_COUNTRY

async def handle_country(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Obrađuje unos zemlje i traži tip instalacije."""
    country = update.message.text
    context.user_data['country'] = country
    await update.message.reply_text(f"Odlično, zemlja je {country}. Sada, koji tip instalacije vas zanima (npr. 'grejanje', 'hlađenje', 'PTVA')?")
    return SELECTING_INSTALLATION_TYPE

# --- DODAJ OVDE OSTALE HANDLER FUNKCIJE KAO ŠTO SU:
# async def handle_installation_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
#     # Logika za obradu tipa instalacije i prelazak na sledeće stanje
#     pass
# async def handle_heating_system(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
#     # Logika za obradu sistema grejanja
#     pass
# ... i tako dalje za svaki STATE ...

async def handle_email_and_finish(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Obrađuje email korisnika i završava upit, šalje email notifikaciju."""
    user_email = update.message.text
    context.user_data['user_email'] = user_email
    
    user_data_for_email = context.user_data
    user_data_for_email['user_id'] = update.effective_user.id

    if send_email_notification(user_data_for_email):
        await update.message.reply_text(
            "Hvala vam na popunjenom upitu! Naš tim će vas kontaktirati uskoro."
        )
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(chat_id=admin_id, text=f"Primljen novi upit od korisnika ID: {user_data_for_email['user_id']}.\nDetalji su poslati emailom.")
            except Exception as e:
                logger.error(f"Could not notify admin {admin_id}: {e}")
    else:
        await update.message.reply_text(
            "Došlo je do greške prilikom slanja vašeg upita. Molimo pokušajte ponovo kasnije."
        )
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(chat_id=admin_id, text=f"PAŽNJA: Greška pri slanju email upita od korisnika ID: {user_data_for_email.get('user_id', 'N/A')}. Proverite logove na Renderu.")
            except Exception as e:
                logger.error(f"Could not notify admin {admin_id} about email error: {e}")

    context.user_data.clear()
    return ConversationHandler.END

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Otkaži konverzaciju."""
    await update.message.reply_text("Upit je otkazan. Možete početi ponovo sa /start.")
    context.user_data.clear()
    return ConversationHandler.END

async def start_non_conv(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ovo je primer start komande koja nije deo ConversationHandler-a."""
    await update.message.reply_text("Dobrodošli! Za početak upita koristite /start.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Prikazuje pomoć."""
    await update.message.reply_text("Ja sam bot za upite o grejanju. Unesite /start da započnete upit.")

# --- ISPRAVLJENO MESTO: DEFINICIJA unknown_command FUNKCIJE ---
async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Odgovara na nepoznate komande."""
    await update.message.reply_text("Izvinjavam se, ne razumem tu komandu. Koristite /start za početak upita.")

# Glavni deo aplikacije - main funkcija za pokretanje bota
def main() -> None:
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Konverzacija za upit (ovo je placeholder, zameni sa svojim stvarnim states)
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)], # Ovo pokreće konverzaciju
        states={
            SELECTING_COUNTRY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_country)],
            
            # --- PLAĆENA MESTA ZA TVOJE FUNKCIJE ---
            SELECTING_INSTALLATION_TYPE: [
                # OVDE DODAJ MessageHandler sa tvojom handle_installation_type funkcijom
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: (logger.info("Installation type received: %s", u.message.text), SELECTING_HEATING_SYSTEM)[1]), # Placeholder, zameni
            ],
            SELECTING_HEATING_SYSTEM: [
                # OVDE DODAJ MessageHandler sa tvojom handle_heating_system funkcijom
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: (logger.info("Heating system received: %s", u.message.text), SELECTING_HEAT_PUMP_SUBTYPE)[1]), # Placeholder, zameni
            ],
            SELECTING_HEAT_PUMP_SUBTYPE: [
                # OVDE DODAJ MessageHandler sa tvojom handle_heat_pump_subtype funkcijom
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: (logger.info("Heat pump subtype received: %s", u.message.text), SELECTING_OBJECT_TYPE)[1]), # Placeholder, zameni
            ],
            SELECTING_OBJECT_TYPE: [
                # OVDE DODAJ MessageHandler sa tvojom handle_object_type funkcijom
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: (logger.info("Object type received: %s", u.message.text), ASKING_FOR_AREA)[1]), # Placeholder, zameni
            ],
            ASKING_FOR_AREA: [
                # OVDE DODAJ MessageHandler sa tvojom handle_area funkcijom
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: (logger.info("Area received: %s", u.message.text), ASKING_FOR_FLOORS)[1]), # Placeholder, zameni
            ],
            ASKING_FOR_FLOORS: [
                # OVDE DODAJ MessageHandler sa tvojom handle_floors funkcijom
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: (logger.info("Floors received: %s", u.message.text), ASKING_FOR_SKETCH)[1]), # Placeholder, zameni
            ],
            ASKING_FOR_SKETCH: [
                # OVDE DODAJ MessageHandler sa tvojom handle_sketch funkcijom
                # Možda treba filters.PHOTO za sliku, ili filters.TEXT ako tražiš samo potvrdu
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: (logger.info("Sketch received: %s", u.message.text), ASKING_FOR_FULL_NAME)[1]), # Placeholder, zameni
            ],
            ASKING_FOR_FULL_NAME: [
                # OVDE DODAJ MessageHandler sa tvojom handle_full_name funkcijom
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: (logger.info("Full name received: %s", u.message.text), ASKING_FOR_PHONE)[1]), # Placeholder, zameni
            ],
            ASKING_FOR_PHONE: [
                # OVDE DODAJ MessageHandler sa tvojom handle_phone funkcijom
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: (logger.info("Phone received: %s", u.message.text), ASKING_FOR_EMAIL)[1]), # Placeholder, zameni
            ],
            ASKING_FOR_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_email_and_finish)],
            # FINISH: [MessageHandler(filters.ALL, ConversationHandler.END)], # Nema potrebe za posebnim handlerom ako handle_email_and_finish vraća ConversationHandler.END
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
        # per_chat=True, per_user=True (ili None za podrazumevano)
    )

    application.add_handler(conv_handler)
    
    # Dodavanje ostalih handlera
    # Ova linija application.add_handler(CommandHandler("start", start_non_conv))
    # Može biti redundantna ili izazvati konflikte ako ConversationHandler već koristi /start.
    # Ako želiš da /start komanda uvek pokreće konverzaciju, ukloni start_non_conv.
    # Ako želiš da imaš i opštu /start i konverzacijsku /start, ovo je naprednije i zahteva preciznije rukovanje.
    application.add_handler(CommandHandler("start", start_non_conv)) 
    application.add_handler(CommandHandler("help", help_command)) 
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command)) 

    # Provera da li su potrebne environment varijable postavljene
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set in environment variables. Bot cannot start.")
        return
    if not WEBHOOK_URL:
        logger.warning("WEBHOOK_URL is not set. Bot will try to run with polling instead of webhooks.")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        logger.info("Bot started with polling.")
    else:
        # Podesi webhook
        application.run_webhook(
            listen="0.0.0.0",
            port=int(os.environ.get("PORT", 8080)),
            url_path=TELEGRAM_BOT_TOKEN,
            webhook_url=WEBHOOK_URL + TELEGRAM_BOT_TOKEN
        )
        logger.info(f"Bot started with webhook on {WEBHOOK_URL + TELEGRAM_BOT_TOKEN}")
        
    logger.info("Application started")


# Ako pokrećeš bot.py direktno
if __name__ == "__main__":
    main()