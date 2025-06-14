import os
import logging
import json
import yagmail
import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes
)
from telegram.error import TelegramError
from telegram.constants import ParseMode

# Inicijalni print da se potvrdi pokretanje fajla
print(f"Bot se pokreće sa najnovijim kodom! Vreme pokretanja: {datetime.datetime.now()}")

# Konfiguracija logginga
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Stanja za ConversationHandler (za prikupljanje skice) ---
AWAITING_SKETCH = 1

# Globalni rečnik za čuvanje korisničkih podataka
user_data = {}

# --- Environment varijable ---
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SENDER_EMAIL = os.getenv("EMAIL_SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")
ADMIN_BCC_EMAIL = os.getenv("ADMIN_BCC_EMAIL")

# Provera da li su varijable učitane
if not BOT_TOKEN:
    logger.critical("TELEGRAM_BOT_TOKEN environment variable not set. Bot cannot start.")
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set.")
if not SENDER_EMAIL:
    logger.error("EMAIL_SENDER_EMAIL environment variable not set.")
    raise ValueError("EMAIL_SENDER_EMAIL environment variable not set.")
if not SENDER_PASSWORD:
    logger.error("EMAIL_APP_PASSWORD environment variable not set.")
    raise ValueError("EMAIL_APP_PASSWORD environment variable not set.")
if not ADMIN_BCC_EMAIL:
    print("WARNING: ADMIN_BCC_EMAIL environment variable not set, using default 'banjooo85@gmail.com'.")
    logger.warning("ADMIN_BCC_EMAIL environment variable not set, using default 'banjooo85@gmail.com'.")
    ADMIN_BCC_EMAIL = 'banjooo85@gmail.com' # Možete staviti vaš default email ovde

# --- Podaci za Izvođače ---
CONTRACTOR_SRB_HEATING = {
    'name': 'Instalacije Srbija d.o.o.',
    'phone': '+381 60 123 4567',
    'email': 'srbija@primer.com',
    'website': 'https://srbijagrejanje.rs',
    'telegram': None
}

CONTRACTOR_MNE_HP = {
    'name': 'Instal Mont d.o.o. Podgorica',
    'phone': '+382 68 123 456',
    'email': 'mont@primer.com',
    'website': 'https://instalmont.me',
    'telegram': 'instalmont_telegram'
}

# Ponuda toplotnih pumpi po zemlji
HEAT_PUMP_OFFERS = {
    'srbija': {
        'options': ['air_to_water', 'water_to_water', 'ground_source'],
        'contractor': CONTRACTOR_SRB_HEATING
    },
    'crna_gora': {
        'options': ['air_to_water'],
        'contractor': CONTRACTOR_MNE_HP # ISPRAVLJENO: bilo je CONTRACT0R_MNE_HP
    }
}

# --- Funkcija za učitavanje poruka (PREVODI) ---
def load_messages(lang_code: str):
    script_dir = os.path.dirname(__file__)
    file_path = os.path.join(script_dir, f'messages_{lang_code}.json')

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"GREŠKA: Message file for {lang_code} not found at {file_path}. Pokušavam da učitam engleski.")
        english_file_path = os.path.join(script_dir, 'messages_en.json')
        try:
            with open(english_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.critical(f"GREŠKA: Ni messages_en.json nije pronađen na {english_file_path}. Bot ne može učitati prevode.")
            return {"error_message": "Greška: Prevodni fajlovi nedostaju. Kontaktirajte podršku."}
    except json.JSONDecodeError as e:
        logger.critical(f"GREŠKA: Neispravan JSON format u {file_path} ili messages_en.json: {e}")
        return {"error_message": "Greška: Prevodni fajlovi su neispravni. Kontaktirajte podršku."}
    except Exception as e:
        logger.critical(f"Neočekivana greška prilikom učitavanja prevoda: {e}")
        return {"error_message": "Greška: Nešto neočekivano se desilo sa prevodima. Kontaktirajte podršku."}

# --- Funkcije za slanje emaila ---
async def send_email_with_sketch(to_email: str, subject: str, body: str, attachment_path: str = None) -> bool:
    try:
        yag = yagmail.SMTP(user=SENDER_EMAIL, password=SENDER_PASSWORD)
        contents = [body]
        
        if attachment_path and os.path.exists(attachment_path):
            contents.append(attachment_path)
            logger.info(f"Prilaganje fajla: {attachment_path}")
        else:
            if attachment_path:
                logger.warning(f"Putanja do priloga ne postoji ili je nevažeća: {attachment_path}")

        recipients = [to_email]
        if ADMIN_BCC_EMAIL:
            recipients.append({'bcc': ADMIN_BCC_EMAIL})

        yag.send(
            to=recipients,
            subject=subject,
            contents=contents
        )
        logger.info(f"Email poslat na {to_email} sa subject: {subject}")
        return True
    except Exception as e:
        logger.error(f"GREŠKA pri slanju emaila: {e}")
        return False
    finally:
        if attachment_path and os.path.exists(attachment_path):
            try:
                os.remove(attachment_path)
                logger.info(f"Obrisan privremeni fajl: {attachment_path}")
            except OSError as e:
                logger.error(f"GREŠKA prilikom brisanja fajla {attachment_path}: {e}")

# --- Funkcije za prikaz menija ---

async def choose_language(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    messages = load_messages('sr') # Uvek učitaj default srpski za izbor jezika
    keyboard = [
        [InlineKeyboardButton("Srpski (Serbian)", callback_data='lang_sr')],
        [InlineKeyboardButton("English", callback_data='lang_en')],
        [InlineKeyboardButton("Русский (Russian)", callback_data='lang_ru')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=user_id, text="Molimo odaberite jezik / Please select a language:", reply_markup=reply_markup)

async def choose_country(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    messages = load_messages(user_data[user_id]['lang'])
    print(f"DEBUG: Prikazivanje izbora zemlje za korisnika {user_id}. user_data[{user_id}]: {user_data[user_id]}")
    logger.debug(f"Prikazivanje izbora zemlje za korisnika {user_id}. user_data[{user_id}]: {user_data[user_id]}")
    keyboard = [
        [InlineKeyboardButton(messages["srbija_button"], callback_data='country_srbija')],
        [InlineKeyboardButton(messages["crna_gora_button"], callback_data='country_crna_gora')],
        [InlineKeyboardButton(messages["back_to_main_menu_button"], callback_data='menu_main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=user_id, text=messages["choose_country_message"], reply_markup=reply_markup)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    current_lang = user_data[user_id].get('lang', 'sr')
    messages = load_messages(current_lang)
    print(f"DEBUG: Prikazivanje glavnog menija za korisnika {user_id}. user_data[{user_id}]: {user_data[user_id]}")
    logger.debug(f"Prikazivanje glavnog menija za korisnika {user_id}. user_data[{user_id}]: {user_data[user_id]}")
    
    keyboard = [
        [InlineKeyboardButton(messages["request_quote_button"], callback_data='menu_quote')],
        [InlineKeyboardButton(messages["faq_button"], callback_data='menu_faq')],
        [InlineKeyboardButton(messages["contact_button"], callback_data='menu_contact')],
        [InlineKeyboardButton(messages["language_button"], callback_data='menu_language')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(text=messages["welcome_message"], reply_markup=reply_markup)
    else:
        await context.bot.send_message(chat_id=user_id, text=messages["welcome_message"], reply_markup=reply_markup)

async def show_quote_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    current_lang = user_data[user_id].get('lang', 'sr')
    messages = load_messages(current_lang)
    keyboard = [
        [InlineKeyboardButton(messages["heating_installation_button"], callback_data='quote_heating')],
        [InlineKeyboardButton(messages["heat_pump_button"], callback_data='quote_hp')],
        [InlineKeyboardButton(messages["back_to_main_menu_button"], callback_data='menu_main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(text=messages["request_quote_button"], reply_markup=reply_markup)

async def show_heating_type_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    current_lang = user_data[user_id].get('lang', 'sr')
    messages = load_messages(current_lang)
    user_data[user_id]['installation_type'] = 'heating' # Save type
    keyboard = [
        [InlineKeyboardButton(messages["radiators_button"], callback_data='heating_radiators')],
        [InlineKeyboardButton(messages["fan_coil_button"], callback_data='heating_fan_coil')],
        [InlineKeyboardButton(messages["floor_heating_button"], callback_data='heating_floor_heating')],
        [InlineKeyboardButton(messages["floor_heating_fan_coil_button"], callback_data='heating_floor_heating_fan_coil')],
        [InlineKeyboardButton(messages["complete_offer_button"], callback_data='heating_complete_offer')],
        [InlineKeyboardButton(messages["existing_installation_button"], callback_data='heating_existing_installation')],
        [InlineKeyboardButton(messages["back_to_main_menu_button"], callback_data='menu_quote')] # Back to quote menu
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(text=messages["heating_system_message"], reply_markup=reply_markup)

async def show_hp_type_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    current_lang = user_data[user_id].get('lang', 'sr')
    messages = load_messages(current_lang)
    user_data[user_id]['installation_type'] = 'hp' # Save type

    country_code = user_data[user_id]['country']
    if not country_code or country_code not in HEAT_PUMP_OFFERS:
        # Poruka za slučaj da zemlja nije odabrana ili nije podržana
        await update.callback_query.edit_message_text(text="Molimo prvo odaberite zemlju! / Please choose country first!")
        await choose_country(update, context, user_id)
        return

    available_options = HEAT_PUMP_OFFERS[country_code]['options']
    keyboard = []
    if 'air_to_water' in available_options:
        keyboard.append([InlineKeyboardButton(messages["air_to_water_hp_button"], callback_data='hp_air_to_water')])
    if 'water_to_water' in available_options:
        keyboard.append([InlineKeyboardButton(messages["water_to_water_hp_button"], callback_data='hp_water_to_water')])
    if 'ground_source' in available_options:
        keyboard.append([InlineKeyboardButton(messages["ground_source_hp_button"], callback_data='hp_ground_source')])
    
    keyboard.append([InlineKeyboardButton(messages["back_to_main_menu_button"], callback_data='menu_quote')]) # Back to quote menu

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(text=messages["hp_type_message"], reply_markup=reply_markup)

async def show_faq_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    current_lang = user_data[user_id].get('lang', 'sr')
    messages = load_messages(current_lang)
    faq_text = messages["faq_content"] # Pretpostavka da imate 'faq_content' u JSON-u
    keyboard = [
        [InlineKeyboardButton(messages["back_to_main_menu_button"], callback_data='menu_main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(text=faq_text, reply_markup=reply_markup)

async def show_contact_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    current_lang = user_data[user_id].get('lang', 'sr')
    messages = load_messages(current_lang)
    keyboard = [
        [InlineKeyboardButton(messages["back_to_main_menu_button"], callback_data='menu_main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    contact_text = messages["contact_info"].format(admin_email=ADMIN_BCC_EMAIL) # Pretpostavka da imate 'contact_info' u JSON-u
    await update.callback_query.edit_message_text(text=contact_text, reply_markup=reply_markup)


# --- Osnovne komande i handleri (postavljene ovde da budu pre main) ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Šalje poruku dobrodošlice i omogućava izbor jezika."""
    user_id = update.effective_user.id
    if user_id not in user_data:
        user_data[user_id] = {'lang': 'sr', 'country': None} # Default jezik na srpski
    
    current_lang = user_data[user_id]['lang']
    messages = load_messages(current_lang)

    logger.info(f"Komanda /start primljena od korisnika {user_id}. Inicijalizujem korisničke podatke.")
    
    await choose_language(update, context, user_id)


# --- Handleri za ConversationHandler (za skicu) ---
async def request_sketch_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ulazna tačka za ConversationHandler za traženje skice."""
    user_id = update.effective_user.id
    current_lang = user_data.get(user_id, {}).get('lang', 'sr')
    messages = load_messages(current_lang)
    
    # Ovo dugme je trebalo da dovede ovde, ali je ipak korisno za vraćanje na glavni meni
    keyboard = [
        [InlineKeyboardButton(messages["no_sketch_button"], callback_data='cancel_sketch')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=user_id,
        text=messages["request_sketch"],
        reply_markup=reply_markup
    )
    return AWAITING_SKETCH

async def handle_sketch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prima skicu (fotografiju ili dokument) i šalje email."""
    user_id = update.effective_user.id
    current_lang = user_data.get(user_id, {}).get('lang', 'sr')
    messages = load_messages(current_lang)

    logger.debug(f"Primljen fajl u handle_sketch za korisnika {user_id}. user_data[{user_id}]: {user_data.get(user_id)}")

    file_id = None
    file_name = None
    mime_type = None

    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        file_name = f"sketch_photo_{user_id}_{timestamp}.jpg"
        mime_type = "image/jpeg"
    elif update.message.document:
        document = update.message.document
        if document.mime_type not in ['application/pdf', 'image/jpeg', 'image/png']:
            await update.message.reply_text(messages["error_file_type"])
            return AWAITING_SKETCH

        file_id = document.file_id
        file_name = document.file_name
        mime_type = document.mime_type
    else:
        await update.message.reply_text(messages["error_file_type"])
        return AWAITING_SKETCH

    if not file_id:
        await update.message.reply_text(messages["error_file_type"])
        return AWAITING_SKETCH

    file_telegram = await context.bot.get_file(file_id)
    download_path = os.path.join("/tmp", file_name)
    os.makedirs("/tmp", exist_ok=True)

    try:
        await file_telegram.download_to_drive(download_path)
        logger.info(f"Fajl preuzet: {download_path}")

        subject = f"Novi zahtev za ponudu - Skica od korisnika {user_id}"
        
        user_info = user_data.get(user_id, {})
        user_country = user_info.get('country', 'N/A')
        user_installation_type = user_info.get('installation_type', 'N/A')
        user_heating_system_type = user_info.get('heating_system_type', 'N/A')
        user_hp_type_chosen = user_info.get('hp_type_chosen', 'N/A')
        user_object_type = user_info.get('object_type', 'N/A')
        user_area_and_floor = user_info.get('area_and_floor', 'N/A')

        email_body = (
            f"Korisnik {update.effective_user.full_name} ({user_id}) je poslao skicu.\n\n"
            f"Jezik: {current_lang}\n"
            f"Zemlja: {user_country}\n"
            f"Tip instalacije: {user_installation_type}\n"
            f"Tip grejnog sistema: {user_heating_system_type}\n"
            f"Tip toplotne pumpe: {user_hp_type_chosen}\n"
            f"Tip objekta: {user_object_type}\n"
            f"Kvadratura i spratnost: {user_area_and_floor}\n\n"
            f"Molimo vas da pregledate priloženu skicu."
        )

        recipient_email = None
        if user_country == 'srbija':
            recipient_email = CONTRACTOR_SRB_HEATING['email']
        elif user_country == 'crna_gora':
            recipient_email = CONTRACTOR_MNE_HP['email']
        
        if recipient_email:
            success = await send_email_with_sketch(recipient_email, subject, email_body, download_path)
            if success:
                await update.message.reply_text(messages["email_sent_success"])
            else:
                await update.message.reply_text(messages["email_sent_error"])
        else:
            await update.message.reply_text(messages["email_config_error"])
            logger.error(f"Nije pronađen email za izvođača u zemlji: {user_country}")

    except Exception as e:
        logger.error(f"GREŠKA prilikom obrade skice ili slanja emaila: {e}")
        await update.message.reply_text(messages["email_sent_error"])
    finally:
        pass # Fajl se briše u send_email_with_sketch finally bloku

    await show_main_menu(update, context, user_id)
    return ConversationHandler.END

async def cancel_sketch_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Otkazuje zahtev za skicu."""
    user_id = update.effective_user.id
    current_lang = user_data.get(user_id, {}).get('lang', 'sr')
    messages = load_messages(current_lang)
    
    print(f"DEBUG: Otkazivanje skice za korisnika {user_id}. user_data[{user_id}]: {user_data[user_id]}")
    logger.debug(f"Otkazivanje skice za korisnika {user_id}. user_data[{user_id}]: {user_data[user_id]}")

    if update.callback_query:
        await update.callback_query.edit_message_text(messages["no_sketch_received"])
    else:
        await update.message.reply_text(messages["no_sketch_received"])
        
    await show_main_menu(update, context, user_id)
    return ConversationHandler.END

# --- Generički handler za poruke (tekst, za hvatanje unosa korisnika) ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    current_lang = user_data.get(user_id, {}).get('lang', 'sr')
    messages = load_messages(current_lang)
    text = update.message.text
    logger.info(f"Primljena tekstualna poruka od korisnika {user_id}: {text}")

    # Logika za prikupljanje "object_type" i "area_and_floor"
    if 'awaiting_object_type' in user_data.get(user_id, {}) and user_data[user_id]['awaiting_object_type']:
        user_data[user_id]['object_type'] = text
        user_data[user_id]['awaiting_object_type'] = False # Reset flag
        # Nastavi na sledeće pitanje
        await update.message.reply_text(messages["area_and_floor_message"])
        user_data[user_id]['awaiting_area_and_floor'] = True # Set flag for next input
    elif 'awaiting_area_and_floor' in user_data.get(user_id, {}) and user_data[user_id]['awaiting_area_and_floor']:
        user_data[user_id]['area_and_floor'] = text
        user_data[user_id]['awaiting_area_and_floor'] = False # Reset flag
        # Sada ponudi da pošalje skicu
        keyboard = [
            [InlineKeyboardButton(messages["send_sketch_now_button"], callback_data='send_sketch_now')],
            [InlineKeyboardButton(messages["no_sketch_button"], callback_data='no_sketch_quote_confirm')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(messages["sketch_question"], reply_markup=reply_markup)
    else:
        await update.message.reply_text(messages["unknown_command"])


# --- Handler za dokumente (mogu biti i slike ako nisu uhvaćene kao photo) ---
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    current_lang = user_data.get(user_id, {}).get('lang', 'sr')
    messages = load_messages(current_lang)
    logger.info(f"Primljen dokument od korisnika {user_id}.")
    
    # Ovaj handler će biti pozvan samo ako dokument nije uhvaćen od strane handle_sketch
    # ili ako ne postoji aktivna konverzacija za skicu.
    # U tom slučaju, verovatno je korisnik poslao nešto neočekivano.
    await update.message.reply_text(messages["error_file_type"]) # Ili neka opštija poruka


# --- Handler za callback upite sa inline tastatura ---
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer() # Potvrdi callback upit odmah

    user_id = query.from_user.id
    callback_data = query.data
    logger.info(f"Primljen callback query od korisnika {user_id}: {callback_data}")

    if user_id not in user_data:
        user_data[user_id] = {'lang': 'sr', 'country': None}
    
    current_lang = user_data[user_id].get('lang', 'sr')
    messages = load_messages(current_lang)

    # --- Izbor jezika ---
    if callback_data.startswith('lang_'):
        lang_code = callback_data.split('_')[1]
        user_data[user_id]['lang'] = lang_code
        messages = load_messages(lang_code) # Reload messages with new language
        await query.edit_message_text(text=messages["language_selected"])
        await choose_country(update, context, user_id) # Nastavi na izbor zemlje
        return

    # --- Izbor zemlje ---
    elif callback_data.startswith('country_'):
        country_code = "_".join(callback_data.split('_')[1:]) # handles 'srbija' and 'crna_gora'
        user_data[user_id]['country'] = country_code
        country_name = messages.get(f"{country_code}_button", country_code) # Get localized name
        await query.edit_message_text(text=messages["country_selected"].format(country_name=country_name))
        await show_main_menu(update, context, user_id)
        return

    # --- Navigacija menija ---
    elif callback_data == 'menu_main_menu':
        await show_main_menu(update, context, user_id)
        return
    elif callback_data == 'menu_quote':
        await show_quote_menu(update, context, user_id)
        return
    elif callback_data == 'menu_faq':
        await show_faq_menu(update, context, user_id)
        return
    elif callback_data == 'menu_contact':
        await show_contact_menu(update, context, user_id)
        return
    elif callback_data == 'menu_language':
        await choose_language(update, context, user_id)
        return

    # --- Quote flow ---
    elif callback_data == 'quote_heating':
        user_data[user_id]['flow'] = 'heating'
        await show_heating_type_menu(update, context, user_id)
        return
    elif callback_data == 'quote_hp':
        user_data[user_id]['flow'] = 'hp'
        await show_hp_type_menu(update, context, user_id)
        return
    
    # --- Heating system type selection ---
    elif callback_data.startswith('heating_'):
        system_type = callback_data.split('_')[1]
        user_data[user_id]['heating_system_type'] = system_type
        
        if system_type == 'existing_installation':
            await query.edit_message_text(messages["redirect_to_hp"])
            await show_hp_type_menu(update, context, user_id)
        else:
            await query.edit_message_text(messages["object_type_message"])
            user_data[user_id]['awaiting_object_type'] = True # Postavi flag da očekuje unos tipa objekta
        return

    # --- Heat Pump type selection ---
    elif callback_data.startswith('hp_'):
        hp_type = callback_data.split('_')[1]
        user_data[user_id]['hp_type_chosen'] = hp_type
        
        country_code = user_data[user_id]['country']
        hp_offer_data = HEAT_PUMP_OFFERS.get(country_code, {}).get('contractor')

        if hp_offer_data:
            contractor_name = hp_offer_data['name']
            phone = hp_offer_data['phone']
            email = hp_offer_data['email']
            website_info = f"\nWebsite: {hp_offer_data['website']}" if hp_offer_data.get('website') else ""
            telegram_info = f"\nTelegram: @{hp_offer_data['telegram']}" if hp_offer_data.get('telegram') else ""

            hp_type_name = messages.get(f"{hp_type}_hp_button", hp_type)
            country_name = messages.get(f"{country_code}_button", country_code)

            info_text = messages["hp_offer_info"].format(
                hp_type_name=hp_type_name,
                country_name=country_name,
                contractor_name=contractor_name,
                phone=phone,
                email=email,
                website_info=website_info,
                telegram_info=telegram_info
            )
            await query.edit_message_text(text=info_text)
            await show_main_menu(update, context, user_id)
        else:
            await query.edit_message_text(messages["sending_quote_error"]) # Generic error for now
            logger.error(f"Nema podataka o izvođaču za zemlju: {country_code}")
            await show_main_menu(update, context, user_id)
        return

    # --- Potvrda upita (za one koji preskoče skicu) ---
    elif callback_data == 'no_sketch_quote_confirm':
        await query.edit_message_text(messages["request_quote_confirm"])
        keyboard = [
            [InlineKeyboardButton(messages["confirm_yes_button"], callback_data='confirm_quote_send')],
            [InlineKeyboardButton(messages["confirm_no_button"], callback_data='quote_send_cancel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_reply_markup(reply_markup=reply_markup)
        return

    elif callback_data == 'confirm_quote_send':
        # Slanje upita izvođaču bez skice
        user_info = user_data.get(user_id, {})
        user_country = user_info.get('country', 'N/A')
        user_installation_type = user_info.get('installation_type', 'N/A')
        user_heating_system_type = user_info.get('heating_system_type', 'N/A')
        user_hp_type_chosen = user_info.get('hp_type_chosen', 'N/A')
        user_object_type = user_info.get('object_type', 'N/A')
        user_area_and_floor = user_info.get('area_and_floor', 'N/A')

        subject = f"Novi upit za ponudu od korisnika {user_id}"
        email_body = (
            f"Korisnik {query.from_user.full_name} ({user_id}) je poslao upit.\n\n"
            f"Jezik: {current_lang}\n"
            f"Zemlja: {user_country}\n"
            f"Tip instalacije: {user_installation_type}\n"
            f"Tip grejnog sistema: {user_heating_system_type}\n"
            f"Tip toplotne pumpe: {user_hp_type_chosen}\n"
            f"Tip objekta: {user_object_type}\n"
            f"Kvadratura i spratnost: {user_area_and_floor}\n\n"
            f"Korisnik nije priložio skicu."
        )

        recipient_email = None
        if user_country == 'srbija':
            recipient_email = CONTRACTOR_SRB_HEATING['email']
        elif user_country == 'crna_gora':
            recipient_email = CONTRACTOR_MNE_HP['email']
        
        if recipient_email:
            success = await send_email_with_sketch(recipient_email, subject, email_body) # Bez attachmenta
            if success:
                await query.edit_message_text(messages["sending_quote_success"])
            else:
                await query.edit_message_text(messages["sending_quote_error"])
        else:
            await query.edit_message_text(messages["email_config_error"])
            logger.error(f"Nije pronađen email za izvođača u zemlji: {user_country}")

        await show_main_menu(update, context, user_id)
        return
    
    elif callback_data == 'quote_send_cancel':
        await query.edit_message_text(messages["quote_send_cancelled"])
        await show_main_menu(update, context, user_id)
        return

    # Ako dođe do ovde, callback_data je nepoznat
    logger.warning(f"Nepoznat callback_data: {callback_data} od korisnika {user_id}")
    await query.edit_message_text(messages["unknown_command"])


def main() -> None:
    """Pokreni bota."""
    TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    if not TOKEN:
        logger.critical("TELEGRAM_BOT_TOKEN environment variable not set. Bot cannot start.")
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set.")

    PORT = int(os.getenv('PORT', 8080))
    WEBHOOK_URL = os.getenv('WEBHOOK_URL')

    application = Application.builder().token(TOKEN).build()

    # Dodajte sve handlere
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_document))

    # ConversationHandler za skicu
    sketch_conversation_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(request_sketch_entry, pattern='^send_sketch_now$')],
        states={
            AWAITING_SKETCH: [
                MessageHandler(filters.PHOTO | filters.Document.ALL, handle_sketch),
                CallbackQueryHandler(cancel_sketch_request, pattern='^cancel_sketch$'),
                MessageHandler(filters.Regex('^(Ne|Cancel|Otkaži)$'), cancel_sketch_request)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_sketch_request)]
    )
    application.add_handler(sketch_conversation_handler)

    # --- KRITIČNO: Uslovno pokretanje Webhook ili Polling moda ---
    if WEBHOOK_URL:
        logger.info(f"Bot pokrenut u webhook modu. URL: {WEBHOOK_URL}/{TOKEN}, Port: {PORT}")
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{TOKEN}"
        )
    else:
        logger.info("WEBHOOK_URL nije postavljen. Pokrećem bot u polling modu (za lokalni razvoj).")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()