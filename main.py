import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
# *** DODATO/IZMENJENO ***
from telegram.constants import ParseMode # Dodato: Za MARKDOWN_V2
from telegram.helpers import escape_markdown # Dodato: Za escape-ovanje teksta
# ***********************

# Učitavanje promenljivih okruženja iz .env fajla (ako postoji)
from dotenv import load_dotenv
load_dotenv()

# Postavke logovanja
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Učitavanje tokena iz environment varijable
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 8080)) # Default port 8080

# *** DODATO/IZMENJENO ***
# Učitavanje kontakta izvođača iz environment varijable (ili iz config.py ako ga koristite)
# Pretpostavljam da je ovo varijabla koja sadrži kontakt
IZVODJAC_KONTAKT_INFO = os.getenv("IZVODJAC_KONTAKT_INFO", "Kontakt nije dostupan.")
# ***********************

# Države za izbor
COUNTRIES = {
    "Srbija": "rs",
    "Hrvatska": "hr",
    "Bosna i Hercegovina": "ba",
    "Crna Gora": "me",
    "Slovenija": "si",
    "Makedonija": "mk",
}

# Tipovi instalacija
INSTALLATION_TYPES = {
    "Grejna instalacija": "heating",
    "Klimatizacija": "ac",
    "Ventilacija": "ventilation",
    "Solarni sistemi": "solar",
}

# Podtipovi grejnih instalacija
HEATING_TYPES = {
    "Podno grejanje": "underfloor",
    "Radijatorsko grejanje": "radiator",
    "TP komplet": "tp_complete", # Toplotna pumpa komplet
    "TP sanacija": "tp_rehab",   # Toplotna pumpa sanacija (postojeće instalacije)
    "Pelet": "pellet",
    "Gas": "gas",
    "Električno": "electric",
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Šalje poruku dobrodošlice i nudi izbor jezika."""
    keyboard = [
        [
            InlineKeyboardButton("Srpski", callback_data="lang_sr"),
            InlineKeyboardButton("English", callback_data="lang_en"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Dobrodošli! Molimo izaberite jezik:", reply_markup=reply_markup)
    context.user_data["current_state"] = "selecting_language"

async def select_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Rukuje izborom jezika."""
    query = update.callback_query
    await query.answer()
    lang = query.data.split("_")[1]
    context.user_data["language"] = lang
    await query.edit_message_text(f"Odabran jezik: {lang.upper()}")
    await choose_country(update, context)

async def choose_country(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Nudi izbor zemlje."""
    keyboard = []
    for country_name, country_code in COUNTRIES.items():
        keyboard.append([InlineKeyboardButton(country_name, callback_data=f"country_{country_code}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.reply_text("Molimo izaberite zemlju:", reply_markup=reply_markup)
    context.user_data["current_state"] = "selecting_country"

async def select_country(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Rukuje izborom zemlje."""
    query = update.callback_query
    await query.answer()
    country_code = query.data.split("_")[1]
    
    # Pronađi puno ime zemlje
    country_name = next((name for name, code in COUNTRIES.items() if code == country_code), "Nepoznato")

    context.user_data["country"] = country_name
    await query.edit_message_text(f"Odabrana zemlja: {country_name}")
    await choose_installation_type(update, context)

async def choose_installation_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Nudi izbor vrste instalacije."""
    keyboard = []
    for type_name, type_code in INSTALLATION_TYPES.items():
        keyboard.append([InlineKeyboardButton(type_name, callback_data=f"install_{type_code}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.reply_text("Sada možete izabrati vrstu instalacije:", reply_markup=reply_markup)
    context.user_data["current_state"] = "selecting_installation_type"

async def select_installation_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Rukuje izborom vrste instalacije."""
    query = update.callback_query
    await query.answer()
    installation_type_code = query.data.split("_")[1]
    
    # Pronađi puno ime vrste instalacije
    installation_type_name = next((name for name, code in INSTALLATION_TYPES.items() if code == installation_type_code), "Nepoznato")

    context.user_data["installation_type"] = installation_type_name
    await query.edit_message_text(f"Odabrali ste {installation_type_name}.")

    if installation_type_code == "heating":
        await choose_heating_type(update, context)
    else:
        # Trenutno, samo za grejanje nastavljamo, za ostale samo sumiramo
        await update.callback_query.message.reply_text(f"Trenutno su detalji dostupni samo za grejne instalacije. Hvala na razumevanju.")
        await summarize_and_confirm(update, context) # Sumiraj odmah za druge tipove

async def choose_heating_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Nudi izbor podtipa grejne instalacije."""
    keyboard = []
    for type_name, type_code in HEATING_TYPES.items():
        keyboard.append([InlineKeyboardButton(type_name, callback_data=f"heating_{type_code}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.reply_text("Molimo izaberite vrstu grejne instalacije:", reply_markup=reply_markup)
    context.user_data["current_state"] = "selecting_heating_type"

async def select_heating_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Rukuje izborom podtipa grejne instalacije."""
    query = update.callback_query
    await query.answer()
    heating_type_code = query.data.split("_")[1]
    
    # Pronađi puno ime vrste grejanja
    heating_type_name = next((name for name, code in HEATING_TYPES.items() if code == heating_type_code), "Nepoznato")

    context.user_data["heating_type"] = heating_type_name
    await query.edit_message_text(f"Odabrali ste: {heating_type_name}")
    await update.callback_query.message.reply_text("Molimo unesite površinu objekta u m²:")
    context.user_data["current_state"] = "awaiting_area"

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Rukuje tekstualnim unosom (npr. površina objekta)."""
    if context.user_data.get("current_state") == "awaiting_area":
        try:
            area = float(update.message.text)
            context.user_data["area"] = area
            await summarize_and_confirm(update, context) # Idemo na sumiranje i potvrdu
        except ValueError:
            await update.message.reply_text("Molimo unesite validan broj za površinu.")
    else:
        # Default handler za tekstualni unos koji nije očekivan u trenutnom stanju
        await update.message.reply_text("Nisam razumeo vaš unos. Molimo koristite tastere za navigaciju ili pokrenite /start.")

async def summarize_and_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sumira prikupljene podatke i traži potvrdu."""
    user_data = context.user_data
    
    # *** DODATO/IZMENJENO ***
    # Escape-ujemo sve delove stringa koji mogu sadržati specijalne karaktere
    # iz korisničkih unosa ili konstanti koje nisu striktno formatirane.
    # Posebno važno za IZVODJAC_KONTAKT_INFO.
    
    lang = escape_markdown(user_data.get('language', 'N/A').upper(), version=2)
    country = escape_markdown(user_data.get('country', 'N/A'), version=2)
    install_type = escape_markdown(user_data.get('installation_type', 'N/A'), version=2)
    heating_type = escape_markdown(user_data.get('heating_type', 'N/A'), version=2)
    
    # Ako je area broj, pretvaramo ga u string pre escape-ovanja
    area_str = escape_markdown(str(user_data.get('area', 'N/A')), version=2)

    # Učitavamo kontakt izvođača i escape-ujemo ga
    # IZVODJAC_KONTAKT_INFO je već učitan globalno
    escaped_izvodjac_kontakt = escape_markdown(IZVODJAC_KONTAKT_INFO, version=2)
    # ***********************

    summary = (
        f"\\*\\*\\*Pregled vaših unosa:\\*\\*\\*\n\n" # Dodate \\ za escape-ovanje zvezdica
        f"Jezik: `{lang}`\n"
        f"Zemlja: `{country}`\n"
        f"Tip instalacije: `{install_type}`\n"
        f"Grejna instalacija: `{heating_type}`\n"
        f"Površina objekta: `{area_str}` m²\n\n"
        f"Molimo potvrdite podatke\\.\n\n" # Escape-ovana tačka
        f"\\*\\*\\*Kontakt izvođača:\\*\\*\\*\n`{escaped_izvodjac_kontakt}`" # Escape-ovana tačka
    )
    
    keyboard = [
        [
            InlineKeyboardButton("Potvrdi", callback_data="confirm_yes"),
            InlineKeyboardButton("Ponovi", callback_data="confirm_no"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # *** IZMENJENO ***
    # Koristimo ParseMode.MARKDOWN_V2
    await update.message.reply_text(summary, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2)
    # ******************

    context.user_data["current_state"] = "awaiting_confirmation"

async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Rukuje potvrdom podataka."""
    query = update.callback_query
    await query.answer()

    if query.data == "confirm_yes":
        final_summary = (
            f"Hvala na potvrdi\\! Vaši podaci su uspešno zabeleženi\\.\n\n"
            f"Uskoro ćete biti kontaktirani od strane izvođača\\.\n\n"
            f"\\*\\*\\*Podaci izvođača:\\*\\*\\*\n`{escape_markdown(IZVODJAC_KONTAKT_INFO, version=2)}`"
        )
        await query.edit_message_text(final_summary, parse_mode=ParseMode.MARKDOWN_V2)
        # Opcionalno: ovde možete dodati logiku za slanje podataka na email/bazu podataka
        context.user_data.clear() # Resetuj korisničke podatke nakon završetka
    else:
        await query.edit_message_text("U redu, molimo ponovite unos od početka sa /start.")
        context.user_data.clear() # Resetuj korisničke podatke

def main() -> None:
    """Pokreće bota."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set.")
        exit(1)
    if not WEBHOOK_URL:
        logger.error("WEBHOOK_URL environment variable not set.")
        exit(1)

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Handleri
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(select_language, pattern="^lang_"))
    application.add_handler(CallbackQueryHandler(select_country, pattern="^country_"))
    application.add_handler(CallbackQueryHandler(select_installation_type, pattern="^install_"))
    application.add_handler(CallbackQueryHandler(select_heating_type, pattern="^heating_"))
    application.add_handler(CallbackQueryHandler(handle_confirmation, pattern="^confirm_"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))

    # Pokretanje bota sa webhookom
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="webhook",
        webhook_url=WEBHOOK_URL + "/webhook",
    )
    logger.info(f"Starting bot with webhook at {WEBHOOK_URL}/webhook on port {PORT}...")

if __name__ == "__main__":
    main()