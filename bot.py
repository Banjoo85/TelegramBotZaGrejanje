import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes 
)
from telegram.error import BadRequest # Uvezite za rukovanje greskama
from telegram.constants import ParseMode # Za formatiranje teksta (npr. bold)
import logging
import json
import yagmail # Za slanje emailova

# Konfiguracija logovanja
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Učitavanje varijabli okruženja (za lokalni razvoj)
# Na Renderu, ove varijable su direktno dostupne iz okruženja
load_dotenv()

# Environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS") # Email za slanje
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD") # Aplikacijska lozinka za email
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL") # Vaš email za BCC kopije upita

# --- PODACI ZA KONTAKT I ADMINI ---
contact_info = {
    'srbija': {
        # Podaci za IZVOĐAČA RADOVA u Srbiji
        'contractor': {
            'name': 'Igor Bošković', # Dodato ime za lakše prepoznavanje
            'phone': '+381603932566',
            'email': 'boskovicigor83@gmail.com',
            'website': 'N/A', # Koristiti N/A ako nema, ili obrisati ključ
            'telegram': '@IgorNS1983'
        },
        # Podaci za PROIZVOĐAČA u Srbiji (za toplotne pumpe)
        'manufacturer': {
            'name': 'Microma',
            'phone': '+38163582068',
            'email': 'office@microma.rs',
            'website': 'https://microma.rs',
            'telegram': 'N/A'
        }
    },
    'crna_gora': {
        # Podaci za IZVOĐAČA RADOVA u Crnoj Gori (i za HP ovde)
        'contractor': {
            'name': 'Instal M',
            'phone': '+38267423237',
            'email': 'office@instalm.me',
            'website': 'N/A',
            'telegram': '@ivanmujovic'
        }
    }
}

# Telegram ID-ovi admina koji će primati obaveštenja (TVOJ ID TREBA DA BUDE OVDE)
ADMIN_IDS = [
    6869162490, # ZAMENI OVO SA SVOJIM TELEGRAM ID-jem
    # Dodajte još ID-jeva ako je potrebno
]
# --- KRAJ PODATAKA ZA KONTAKT I ADMINI ---


# Stanja za ConversationHandler
CHOOSE_LANGUAGE, CHOOSE_COUNTRY, CHOOSE_SERVICE, CHOOSE_HEATING_SYSTEM, \
INPUT_OBJECT_DETAILS, SEND_INQUIRY_CONFIRMATION, CHOOSE_HP_SYSTEM = range(7)

# Učitavanje poruka iz JSON fajlova
MESSAGES = {}
def load_messages():
    """Učitava poruke iz JSON fajlova za svaki jezik."""
    for lang in ['sr', 'en', 'ru']:
        try:
            with open(f'messages_{lang}.json', 'r', encoding='utf-8') as f:
                MESSAGES[lang] = json.load(f)
        except FileNotFoundError:
            logger.error(f"messages_{lang}.json not found. Please create it.")
            MESSAGES[lang] = {} # Prazan rečnik ako fajl ne postoji
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from messages_{lang}.json. Check for syntax errors.")
            MESSAGES[lang] = {}

# Pomoćna funkcija za dobijanje poruke na osnovu jezika i ključa
def get_message(lang_code, key):
    """Vraća poruku za dati ključ na određenom jeziku. Fallback na default poruku."""
    return MESSAGES.get(lang_code, {}).get(key, f"MISSING_MESSAGE: {key} for {lang_code}")

# --- Helper Functions for Keyboards ---

async def get_language_keyboard():
    """Generiše inline tastaturu za odabir jezika."""
    keyboard = [
        [InlineKeyboardButton("Srpski", callback_data="lang_sr")],
        [InlineKeyboardButton("English", callback_data="lang_en")],
        [InlineKeyboardButton("Русский", callback_data="lang_ru")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def get_country_keyboard(lang_code):
    """Generiše inline tastaturu za odabir države."""
    keyboard = [
        [InlineKeyboardButton(get_message(lang_code, "country_serbia"), callback_data="country_srb")],
        [InlineKeyboardButton(get_message(lang_code, "country_montenegro"), callback_data="country_mne")],
        [InlineKeyboardButton(get_message(lang_code, "back_button"), callback_data="back_to_language")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def get_service_keyboard(lang_code):
    """Generiše inline tastaturu za odabir usluge."""
    keyboard = [
        [InlineKeyboardButton(get_message(lang_code, "service_heating_installation"), callback_data="service_heating")],
        [InlineKeyboardButton(get_message(lang_code, "service_heat_pump"), callback_data="service_hp")],
        [InlineKeyboardButton(get_message(lang_code, "back_button"), callback_data="back_to_country")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def get_heating_system_keyboard(lang_code, country):
    """Generiše inline tastaturu za odabir grejnog sistema."""
    keyboard = [
        [InlineKeyboardButton(get_message(lang_code, "system_radiators"), callback_data="system_radiators")],
        [InlineKeyboardButton(get_message(lang_code, "system_fan_coils"), callback_data="system_fancoils")],
        [InlineKeyboardButton(get_message(lang_code, "system_floor_heating"), callback_data="system_floor_heating")],
        [InlineKeyboardButton(get_message(lang_code, "system_floor_fancoils"), callback_data="system_floor_fancoils")],
        [InlineKeyboardButton(get_message(lang_code, "system_complete_hp_offer"), callback_data="system_complete_hp_offer")]
    ]
    keyboard.append([InlineKeyboardButton(get_message(lang_code, "back_button"), callback_data="back_to_service")])
    return InlineKeyboardMarkup(keyboard)

async def get_hp_system_keyboard(lang_code, country):
    """Generiše inline tastaturu za odabir tipa toplotne pumpe."""
    keyboard = []
    if country == 'srb':
        keyboard.append([InlineKeyboardButton(get_message(lang_code, "hp_water_water"), callback_data="hp_water_water")])
        keyboard.append([InlineKeyboardButton(get_message(lang_code, "hp_air_water"), callback_data="hp_air_water")])
    elif country == 'mne':
        keyboard.append([InlineKeyboardButton(get_message(lang_code, "hp_air_water"), callback_data="hp_air_water")]) # Samo Vazduh-Voda za CG
    keyboard.append([InlineKeyboardButton(get_message(lang_code, "back_button"), callback_data="back_to_service")])
    return InlineKeyboardMarkup(keyboard)

async def get_send_inquiry_keyboard(lang_code):
    """Generiše inline tastaturu za potvrdu slanja upita."""
    keyboard = [
        [InlineKeyboardButton(get_message(lang_code, "send_inquiry_yes"), callback_data="send_inquiry_yes")],
        [InlineKeyboardButton(get_message(lang_code, "send_inquiry_no"), callback_data="send_inquiry_no")]
    ]
    keyboard.append([InlineKeyboardButton(get_message(lang_code, "back_button"), callback_data="back_to_object_details_keyboard")])
    return InlineKeyboardMarkup(keyboard)

# --- Email Sending Function ---
async def send_email(to_email, subject, body, attachment_paths=None):
    """Šalje email koristeći yagmail."""
    try:
        yag = yagmail.SMTP(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
        recipients = [to_email]
        if ADMIN_EMAIL and ADMIN_EMAIL not in recipients: # Dodajte ADMIN_EMAIL kao BCC, ako nije već glavni primalac
            recipients.append(ADMIN_EMAIL)

        logger.info(f"Attempting to send email to: {to_email}, with BCC to: {ADMIN_EMAIL}")

        yag.send(
            to=recipients,
            subject=subject,
            contents=body,
            attachments=attachment_paths
        )
        logger.info(f"Email sent successfully to {to_email} with BCC to {ADMIN_EMAIL}")
        return True
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        return False

# --- Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Pokreće konverzaciju, nudi odabir jezika."""
    load_messages() # Učitajte poruke pri svakom startu (za slučaj da se promene)
    
    welcome_message = get_message('sr', 'welcome_message') + "\n\n" + \
                      get_message('en', 'welcome_message') + "\n\n" + \
                      get_message('ru', 'welcome_message') + "\n\n" + \
                      get_message('sr', 'choose_language_prompt') + "\n" + \
                      get_message('en', 'choose_language_prompt') + "\n" + \
                      get_message('ru', 'choose_language_prompt')

    if update.message:
        await update.message.reply_text(welcome_message, reply_markup=await get_language_keyboard(), parse_mode=ParseMode.HTML)
    elif update.callback_query: # Ako se start pozove preko callbacka (npr. nakon cancela)
        query = update.callback_query
        await query.answer()
        try:
            await query.edit_message_text(welcome_message, reply_markup=await get_language_keyboard(), parse_mode=ParseMode.HTML)
        except BadRequest as e:
            logger.warning(f"Error editing message in start (callback): {e}. Sending new message.")
            await update.effective_chat.send_message(welcome_message, reply_markup=await get_language_keyboard(), parse_mode=ParseMode.HTML)

    context.user_data.clear() # Resetuj sve podatke pri novom startu
    return CHOOSE_LANGUAGE

async def choose_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Obrađuje odabir jezika."""
    query = update.callback_query
    await query.answer()
    lang_code = query.data.replace('lang_', '')
    context.user_data['lang'] = lang_code
    
    # Sakrijte eventualnu ReplyKeyboard (koja se koristi za Nazad)
    if update.effective_message.reply_markup and isinstance(update.effective_message.reply_markup, ReplyKeyboardMarkup):
        await update.effective_chat.send_message(get_message(lang_code, "choose_country"), reply_markup=InlineKeyboardMarkup([])) # Pošalji praznu inline tastaturu da se obriše reply tastatura


    try:
        await query.edit_message_text(
            text=get_message(lang_code, "choose_country"),
            reply_markup=await get_country_keyboard(lang_code)
        )
    except BadRequest as e:
        logger.warning(f"Error editing message in choose_language: {e}. Sending new message.")
        await update.effective_chat.send_message(
            text=get_message(lang_code, "choose_country"),
            reply_markup=await get_country_keyboard(lang_code)
        )
    return CHOOSE_COUNTRY

async def choose_country(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Obrađuje odabir države."""
    query = update.callback_query
    await query.answer()
    country_code = query.data.replace('country_', '')
    context.user_data['country'] = country_code
    lang_code = context.user_data['lang']

    country_name = get_message(lang_code, f"country_{country_code}") # Dohvati ime države
    message_text = get_message(lang_code, "country_selected").format(country_name=country_name)

    try:
        await query.edit_message_text(
            text=message_text + "\n\n" + get_message(lang_code, "choose_service"),
            reply_markup=await get_service_keyboard(lang_code),
            parse_mode=ParseMode.HTML # Omogući HTML formatiranje za bold
        )
    except BadRequest as e:
        logger.warning(f"Error editing message in choose_country: {e}. Sending new message.")
        await update.effective_chat.send_message(
            text=message_text + "\n\n" + get_message(lang_code, "choose_service"),
            reply_markup=await get_service_keyboard(lang_code),
            parse_mode=ParseMode.HTML
        )
    return CHOOSE_SERVICE

async def choose_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Obrađuje odabir usluge (grejna instalacija ili toplotna pumpa)."""
    query = update.callback_query
    await query.answer()
    service_type = query.data.replace('service_', '')
    context.user_data['service'] = service_type
    lang_code = context.user_data['lang']
    country_code = context.user_data['country']

    if service_type == 'heating':
        # Prikaz podataka o izvođaču za grejnu instalaciju
        if country_code == 'srb':
            contractor_data = contact_info['srbija']['contractor']
        elif country_code == 'mne':
            contractor_data = contact_info['crna_gora']['contractor']
        
        contractor_info_text = get_message(lang_code, "contractor_info").format(
            name=contractor_data.get('name', 'N/A'),
            phone=contractor_data.get('phone', 'N/A'),
            email=contractor_data.get('email', 'N/A'),
            website=contractor_data.get('website', 'N/A'),
            telegram=contractor_data.get('telegram', 'N/A')
        )
        
        try:
            await query.edit_message_text(
                text=contractor_info_text + "\n\n" + get_message(lang_code, "choose_heating_system"),
                reply_markup=await get_heating_system_keyboard(lang_code, country_code),
                parse_mode=ParseMode.HTML
            )
        except BadRequest as e:
            logger.warning(f"Error editing message in choose_service (heating): {e}. Sending new message.")
            await update.effective_chat.send_message(
                text=contractor_info_text + "\n\n" + get_message(lang_code, "choose_heating_system"),
                reply_markup=await get_heating_system_keyboard(lang_code, country_code),
                parse_mode=ParseMode.HTML
            )
        return CHOOSE_HEATING_SYSTEM
    elif service_type == 'hp':
        # Prikaz podataka o partneru/proizvođaču za toplotnu pumpu
        if country_code == 'srb':
            partner_data = contact_info['srbija']['manufacturer']
        elif country_code == 'mne':
            partner_data = contact_info['crna_gora']['contractor'] # Instal M za CG HP
        
        partner_info_text = get_message(lang_code, "partner_info").format(
            name=partner_data.get('name', 'N/A'),
            phone=partner_data.get('phone', 'N/A'),
            email=partner_data.get('email', 'N/A'),
            website=partner_data.get('website', 'N/A'),
            telegram=partner_data.get('telegram', 'N/A')
        )

        try:
            await query.edit_message_text(
                text=partner_info_text + "\n\n" + get_message(lang_code, "choose_hp_system"),
                reply_markup=await get_hp_system_keyboard(lang_code, country_code),
                parse_mode=ParseMode.HTML
            )
        except BadRequest as e:
            logger.warning(f"Error editing message in choose_service (hp): {e}. Sending new message.")
            await update.effective_chat.send_message(
                text=partner_info_text + "\n\n" + get_message(lang_code, "choose_hp_system"),
                reply_markup=await get_hp_system_keyboard(lang_code, country_code),
                parse_mode=ParseMode.HTML
            )
        return CHOOSE_HP_SYSTEM

async def choose_heating_system(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Obrađuje odabir specifičnog grejnog sistema."""
    query = update.callback_query
    await query.answer()
    system_type = query.data.replace('system_', '')
    context.user_data['heating_system'] = system_type
    lang_code = context.user_data['lang']

    system_name = get_message(lang_code, f"system_{system_type}")
    
    # Sakrijte prethodnu inline tastaturu slanjem nove prazne
    try:
        await query.edit_message_reply_markup(reply_markup=None) # Uklanja inline tastaturu
    except BadRequest as e:
        logger.warning(f"Could not remove inline keyboard: {e}")

    # Pošaljite novu poruku sa ReplyKeyboard za Nazad
    await update.effective_chat.send_message(
        text=get_message(lang_code, "selected_system").format(system_name=system_name) + "\n\n" + \
             get_message(lang_code, "input_object_details"),
        reply_markup=ReplyKeyboardMarkup([[get_message(lang_code, "back_button")]], one_time_keyboard=True, resize_keyboard=True),
        parse_mode=ParseMode.HTML
    )
    return INPUT_OBJECT_DETAILS

async def choose_hp_system(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Obrađuje odabir tipa toplotne pumpe i prikazuje informacije."""
    query = update.callback_query
    await query.answer()
    hp_type = query.data.replace('hp_', '')
    context.user_data['hp_system'] = hp_type
    lang_code = context.user_data['lang']
    country_code = context.user_data['country']

    hp_type_name = get_message(lang_code, f"hp_{hp_type}")
    
    # Prikaz podataka o partneru/proizvođaču za toplotnu pumpu (detaljnije informacije)
    if country_code == 'srb':
        partner_data = contact_info['srbija']['manufacturer']
    elif country_code == 'mne':
        partner_data = contact_info['crna_gora']['contractor'] # Instal M za CG HP
    
    partner_info_text_final = get_message(lang_code, "partner_info_final").format(
        name=partner_data.get('name', 'N/A'),
        phone=partner_data.get('phone', 'N/A'),
        email=partner_data.get('email', 'N/A'),
        website=partner_data.get('website', 'N/A'),
        telegram=partner_data.get('telegram', 'N/A')
    )

    # Nema daljeg toka za HP, samo ispis informacija i povratak na glavni meni
    try:
        await query.edit_message_text(
            text=get_message(lang_code, "selected_hp_type").format(hp_type_name=hp_type_name) + "\n\n" + \
                 partner_info_text_final + "\n\n" + get_message(lang_code, "main_menu_prompt"),
            reply_markup=await get_service_keyboard(lang_code), # Vraćanje na izbor usluge
            parse_mode=ParseMode.HTML
        )
    except BadRequest as e:
        logger.warning(f"Error editing message in choose_hp_system: {e}. Sending new message.")
        await update.effective_chat.send_message(
            text=get_message(lang_code, "selected_hp_type").format(hp_type_name=hp_type_name) + "\n\n" + \
                 partner_info_text_final + "\n\n" + get_message(lang_code, "main_menu_prompt"),
            reply_markup=await get_service_keyboard(lang_code),
            parse_mode=ParseMode.HTML
        )
    context.user_data.clear() # Resetuj sve podatke
    context.user_data['lang'] = lang_code # zadrži jezik
    return ConversationHandler.END # Završi konverzaciju

async def input_object_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prikuplja tekstualne detalje o objektu."""
    lang_code = context.user_data['lang']

    if update.message.text == get_message(lang_code, "back_button"):
        # Ako je korisnik kliknuo "Nazad" na ReplyKeyboard-u
        return await back_to_heating_system(update, context)

    # Sačuvaj unete detalje o objektu
    object_description = update.message.text
    context.user_data['object_details'] = {'description': object_description, 'attachments': []}

    # Ponudi opciju za slanje skice/PDF-a
    await update.message.reply_text(
        get_message(lang_code, "send_sketch_prompt"),
        reply_markup=ReplyKeyboardMarkup([[get_message(lang_code, "no_sketch_button"), get_message(lang_code, "back_button")]], one_time_keyboard=True, resize_keyboard=True),
        parse_mode=ParseMode.HTML
    )
    return SEND_INQUIRY_CONFIRMATION # Prelazimo na sledeće stanje gde čekamo skicu ili potvrdu

async def handle_document_or_no_sketch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Obrađuje primljeni dokument (skicu) ili odabir 'Ne' za skicu."""
    lang_code = context.user_data['lang']

    if 'object_details' not in context.user_data: # Ako se vratimo nazad pa opet ovde, osigurajmo da postoji
        context.user_data['object_details'] = {'description': 'N/A', 'attachments': []}

    if update.message.text == get_message(lang_code, "back_button"):
        # Ako je korisnik kliknuo "Nazad" na ReplyKeyboard-u
        return await back_to_object_details_input(update, context)

    if update.message.document:
        file_id = update.message.document.file_id
        file_name = update.message.document.file_name
        context.user_data['object_details']['attachments'].append({'file_id': file_id, 'file_name': file_name})
        await update.message.reply_text(get_message(lang_code, "sketch_received"))
    elif update.message.text == get_message(lang_code, "no_sketch_button"):
        await update.message.reply_text(get_message(lang_code, "no_sketch_chosen"))
    
    # Sakrij ReplyKeyboard
    await update.message.reply_text(get_message(lang_code, "confirm_send_inquiry"), reply_markup=InlineKeyboardMarkup([]))

    # Pitajte korisnika da li zeli da posalje upit
    await update.effective_chat.send_message(
        get_message(lang_code, "confirm_send_inquiry"),
        reply_markup=await get_send_inquiry_keyboard(lang_code),
        parse_mode=ParseMode.HTML
    )
    return SEND_INQUIRY_CONFIRMATION

async def send_inquiry_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Potvrđuje i šalje upit emailom."""
    query = update.callback_query
    await query.answer()
    lang_code = context.user_data['lang']

    if query.data == "send_inquiry_yes":
        country_code = context.user_data.get('country')
        heating_system_key = context.user_data.get('heating_system')
        object_details = context.user_data.get('object_details', {})
        user_info = update.effective_user # Informacije o korisniku

        # Odredite kome se šalje email i dobijte ime sistema za subject
        to_email = ""
        contractor_name = ""
        
        system_name_for_email = get_message(lang_code, f"system_{heating_system_key}") # Ime sistema za subject

        if country_code == 'srb':
            to_email = contact_info['srbija']['contractor']['email']
            contractor_name = contact_info['srbija']['contractor']['name']
        elif country_code == 'mne':
            to_email = contact_info['crna_gora']['contractor']['email']
            contractor_name = contact_info['crna_gora']['contractor']['name']
        
        subject = get_message(lang_code, "inquiry_subject").format(system=system_name_for_email)
        body = get_message(lang_code, "inquiry_body").format(
            user_name=user_info.full_name or user_info.username or "N/A",
            user_id=user_info.id,
            country=get_message(lang_code, f"country_{country_code}"),
            system=system_name_for_email,
            object_description=object_details.get('description', 'N/A')
        )

        attachments_paths = []
        if object_details.get('attachments'):
            for attachment_info in object_details['attachments']:
                file_id = attachment_info['file_id']
                file_name = attachment_info['file_name']
                
                temp_file_path = f"/tmp/{file_name}" # Render omogucava pisanje u /tmp
                try:
                    file = await context.bot.get_file(file_id)
                    await file.download_to_drive(temp_file_path)
                    attachments_paths.append(temp_file_path)
                except Exception as e:
                    logger.error(f"Failed to download file {file_name}: {e}")
                    await query.message.reply_text(get_message(lang_code, "attachment_download_failure").format(file_name=file_name), parse_mode=ParseMode.HTML)

        email_sent = await send_email(to_email, subject, body, attachments_paths)

        if email_sent:
            await query.edit_message_text(get_message(lang_code, "inquiry_sent_success").format(contractor=contractor_name), parse_mode=ParseMode.HTML)
        else:
            await query.edit_message_text(get_message(lang_code, "inquiry_sent_failure"), parse_mode=ParseMode.HTML)

        # Čišćenje privremenih fajlova
        for path in attachments_paths:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError as e:
                    logger.error(f"Error removing temporary file {path}: {e}")
        
        context.user_data.clear() # Resetuj sve podatke
        context.user_data['lang'] = lang_code # zadrzi jezik
        return ConversationHandler.END # Završi konverzaciju

    elif query.data == "send_inquiry_no":
        try:
            await query.edit_message_text(get_message(lang_code, "inquiry_cancelled"), parse_mode=ParseMode.HTML)
        except BadRequest as e:
            logger.warning(f"Error editing message in send_inquiry_no: {e}. Sending new message.")
            await update.effective_chat.send_message(get_message(lang_code, "inquiry_cancelled"), parse_mode=ParseMode.HTML)

        context.user_data.clear() # Resetuj sve podatke
        context.user_data['lang'] = lang_code # zadrzi jezik
        return ConversationHandler.END # Završi konverzaciju

# --- Back Handlers ---

async def back_to_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Vraća na izbor jezika."""
    query = update.callback_query
    await query.answer()
    
    await start(update, context) # Pozovi start handler direktno
    context.user_data.clear() # Resetuj sve podatke
    return CHOOSE_LANGUAGE

async def back_to_country(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Vraća na izbor države."""
    query = update.callback_query
    await query.answer()
    lang_code = context.user_data.get('lang', 'sr')
    context.user_data['country'] = None # Reset
    
    try:
        await query.edit_message_text(
            text=get_message(lang_code, "choose_country"),
            reply_markup=await get_country_keyboard(lang_code),
            parse_mode=ParseMode.HTML
        )
    except BadRequest as e:
        logger.warning(f"Error editing message in back_to_country: {e}. Sending new message.")
        await update.effective_chat.send_message(
            text=get_message(lang_code, "choose_country"),
            reply_markup=await get_country_keyboard(lang_code),
            parse_mode=ParseMode.HTML
        )
    return CHOOSE_COUNTRY

async def back_to_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Vraća na izbor usluge (grejna instalacija/toplotna pumpa)."""
    query = update.callback_query
    await query.answer()
    lang_code = context.user_data.get('lang', 'sr')
    context.user_data['service'] = None # Reset
    
    try:
        await query.edit_message_text(
            text=get_message(lang_code, "choose_service"),
            reply_markup=await get_service_keyboard(lang_code),
            parse_mode=ParseMode.HTML
        )
    except BadRequest as e:
        logger.warning(f"Error editing message in back_to_service: {e}. Sending new message.")
        await update.effective_chat.send_message(
            text=get_message(lang_code, "choose_service"),
            reply_markup=await get_service_keyboard(lang_code),
            parse_mode=ParseMode.HTML
        )
    return CHOOSE_SERVICE

async def back_to_heating_system(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Vraća na izbor grejnog sistema. Poziva se sa ReplyKeyboard 'Nazad'."""
    lang_code = context.user_data.get('lang', 'sr')
    country_code = context.user_data.get('country')
    context.user_data['heating_system'] = None # Reset
    
    # Prikaz podataka o izvođaču za grejnu instalaciju (ponovo)
    if country_code == 'srb':
        contractor_data = contact_info['srbija']['contractor']
    elif country_code == 'mne':
        contractor_data = contact_info['crna_gora']['contractor']
    
    contractor_info_text = get_message(lang_code, "contractor_info").format(
        name=contractor_data.get('name', 'N/A'),
        phone=contractor_data.get('phone', 'N/A'),
        email=contractor_data.get('email', 'N/A'),
        website=contractor_data.get('website', 'N/A'),
        telegram=contractor_data.get('telegram', 'N/A')
    )

    await update.message.reply_text( # Šaljemo novu poruku jer je ReplyKeyboard
        text=contractor_info_text + "\n\n" + get_message(lang_code, "choose_heating_system"),
        reply_markup=await get_heating_system_keyboard(lang_code, country_code),
        parse_mode=ParseMode.HTML
    )
    return CHOOSE_HEATING_SYSTEM

async def back_to_object_details_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Vraća na unos detalja o objektu. Poziva se sa ReplyKeyboard 'Nazad'."""
    lang_code = context.user_data.get('lang', 'sr')
    system_type = context.user_data.get('heating_system')
    system_name = get_message(lang_code, f"system_{system_type}")
    context.user_data['object_details'] = {} # Reset object details (ako se vraćamo, želimo da resetujemo unete detalje)

    await update.message.reply_text( # Šaljemo novu poruku jer je ReplyKeyboard
        text=get_message(lang_code, "selected_system").format(system_name=system_name) + "\n\n" + \
             get_message(lang_code, "input_object_details"),
        reply_markup=ReplyKeyboardMarkup([[get_message(lang_code, "back_button")]], one_time_keyboard=True, resize_keyboard=True),
        parse_mode=ParseMode.HTML
    )
    return INPUT_OBJECT_DETAILS

async def back_to_object_details_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Vraća sa ekrana za potvrdu slanja upita na unos detalja o objektu. Poziva se sa InlineKeyboard 'Nazad'."""
    query = update.callback_query
    await query.answer()
    lang_code = context.user_data.get('lang', 'sr')

    # Editujemo poruku koja je pitala za slanje skice i nudimo povratak na unos teksta/slanje skice
    try:
        await query.edit_message_text(
            text=get_message(lang_code, "send_sketch_prompt"),
            reply_markup=ReplyKeyboardMarkup([[get_message(lang_code, "no_sketch_button"), get_message(lang_code, "back_button")]], one_time_keyboard=True, resize_keyboard=True),
            parse_mode=ParseMode.HTML
        )
    except BadRequest as e:
        logger.warning(f"Error editing message in back_to_object_details_keyboard: {e}. Sending new message.")
        await update.effective_chat.send_message(
            text=get_message(lang_code, "send_sketch_prompt"),
            reply_markup=ReplyKeyboardMarkup([[get_message(lang_code, "no_sketch_button"), get_message(lang_code, "back_button")]], one_time_keyboard=True, resize_keyboard=True),
            parse_mode=ParseMode.HTML
        )
    return SEND_INQUIRY_CONFIRMATION # Vraćamo se na stanje gde se prikuplja skica/potvrda

# --- Fallback handler ---
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Otkazuje konverzaciju."""
    lang_code = context.user_data.get('lang', 'sr')
    if update.message:
        await update.message.reply_text(get_message(lang_code, "conversation_cancelled"), reply_markup=ReplyKeyboardMarkup([["/start"]], resize_keyboard=True), parse_mode=ParseMode.HTML)
    elif update.callback_query:
        query = update.callback_query
        await query.answer()
        try:
            await query.edit_message_text(get_message(lang_code, "conversation_cancelled"), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("/start", callback_data="start_again")]]), parse_mode=ParseMode.HTML)
        except BadRequest:
             await update.effective_chat.send_message(get_message(lang_code, "conversation_cancelled"), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("/start", callback_data="start_again")]]), parse_mode=ParseMode.HTML)

    context.user_data.clear() # Clear all user data
    return ConversationHandler.END


# --- Main function ---
def main():
    """Glavna funkcija za pokretanje bota."""
    load_messages() # Učitaj poruke jednom kada se aplikacija pokrene

    application = Application.builder().token(BOT_TOKEN).build()

    # Dohvati PORT koji Render dodeljuje i WEB_SERVICE_URL
    PORT = int(os.environ.get('PORT', 8080))
    WEB_SERVICE_URL = os.environ.get('WEB_SERVICE_URL')

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(start, pattern="^start_again$") # Omogućava restart sa inline dugmeta
        ],
        states={
            CHOOSE_LANGUAGE: [
                CallbackQueryHandler(choose_language, pattern="^lang_"),
            ],
            CHOOSE_COUNTRY: [
                CallbackQueryHandler(choose_country, pattern="^country_"),
                CallbackQueryHandler(back_to_language, pattern="^back_to_language$")
            ],
            CHOOSE_SERVICE: [
                CallbackQueryHandler(choose_service, pattern="^service_"),
                CallbackQueryHandler(back_to_country, pattern="^back_to_country$")
            ],
            CHOOSE_HEATING_SYSTEM: [
                CallbackQueryHandler(choose_heating_system, pattern="^system_"),
                CallbackQueryHandler(back_to_service, pattern="^back_to_service$")
            ],
            CHOOSE_HP_SYSTEM: [
                CallbackQueryHandler(choose_hp_system, pattern="^hp_"),
                CallbackQueryHandler(back_to_service, pattern="^back_to_service$")
            ],
            INPUT_OBJECT_DETAILS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_object_details),
                # Koristimo filters.Regex za back dugme sa ReplyKeyboard-a, mora da pokriva sve jezike
                MessageHandler(
                    filters.Regex(f"^{MESSAGES['sr'].get('back_button', 'MISSING_BUTTON')}$|^" + \
                                  f"{MESSAGES['en'].get('back_button', 'MISSING_BUTTON')}$|^" + \
                                  f"{MESSAGES['ru'].get('back_button', 'MISSING_BUTTON')}$"), back_to_heating_system
                )
            ],
            SEND_INQUIRY_CONFIRMATION: [
                MessageHandler(
                    filters.ATTACHMENT | filters.Regex(f"^{MESSAGES['sr'].get('no_sketch_button', 'MISSING_BUTTON')}$|^" + \
                                                       f"{MESSAGES['en'].get('no_sketch_button', 'MISSING_BUTTON')}$|^" + \
                                                       f"{MESSAGES['ru'].get('no_sketch_button', 'MISSING_BUTTON')}$"), handle_document_or_no_sketch
                ),
                CallbackQueryHandler(send_inquiry_confirmation, pattern="^send_inquiry_"),
                CallbackQueryHandler(back_to_object_details_keyboard, pattern="^back_to_object_details_keyboard$"),
                # Dodati MessageHandler za "Nazad" dugme na ReplyKeyboard (koje se koristi pri slanju skice)
                MessageHandler(
                    filters.Regex(f"^{MESSAGES['sr'].get('back_button', 'MISSING_BUTTON')}$|^" + \
                                  f"{MESSAGES['en'].get('back_button', 'MISSING_BUTTON')}$|^" + \
                                  f"{MESSAGES['ru'].get('back_button', 'MISSING_BUTTON')}$"), handle_document_or_no_sketch # Ovo ce uhvatiti "Nazad" sa ReplyKB
                )
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)

    # Pokretanje bota
    if WEB_SERVICE_URL:
        # Produkcijski mod (Render)
        webhook_url = f"{WEB_SERVICE_URL}/{BOT_TOKEN}"
        logger.info(f"Pokušavam da postavim webhook na: {webhook_url}")
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=BOT_TOKEN, # Vaš TOKEN kao putanja za endpoint
            webhook_url=webhook_url
        )
        logger.info("Bot pokrenut u produkcijskom modu (webhooks).")
    else:
        # Lokalni mod (polling)
        logger.info("Bot pokrenut u lokalnom modu (polling)...")
        application.run_polling(poll_interval=1.0) # Dodat poll_interval za PTB 20.x

if __name__ == "__main__":
    main()