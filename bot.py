import logging
import os
import datetime
import json
import yagmail
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, ContextTypes
from telegram.constants import ParseMode

# Učitavanje .env fajla
load_dotenv()

# --- Postavljanje logginga ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Stanja za ConversationHandler ---
# Pažnja: Broj u range() mora odgovarati broju promenljivih (stanja) koje su ovde navedene.
# Trenutno ih ima 19, pa je range(19).
SELECT_LANGUAGE, MAIN_MENU, SELECT_COUNTRY, QUOTE_MENU, HEATING_CHOICE, \
HEAT_PUMP_TYPE, WATER_HEATING_TYPE, RADIATOR_TYPE, FLOOR_HEATING_TYPE, \
HEAT_PUMP_LOCATION_CHOICE, OBJECT_TYPE, AREA_INPUT, HAS_SKETCH_CHOICE, \
UPLOAD_SKETCH, CONFIRM_QUOTE_SEND, ASK_FOR_EMAIL, RECEIVE_EMAIL, \
CONTACT_MENU, SELECT_CONTACT_TYPE = range(19)

# --- PODACI ZA KONTAKT I ADMINI ---
# Podaci za kontakt
contact_info = {
    'srbija': {
        # Podaci za IZVOĐAČA RADOVA u Srbiji
        'contractor': {
            'name': 'Igor Bošković', # Dodato 'name' polje - PROVERITE DA LI JE OVO ISPRAVNO!
            'phone': '+381603932566',
            'email': 'boskovicigor83@gmail.com',
            'website': ':', # Koristite : ako ne postoji
            'telegram': '@IgorNS1983' # Koristite : ako ne postoji
        },
        # Podaci za PROIZVOĐAČA u Srbiji
        'manufacturer': {
            'name': 'Microma',
            'phone': '+38163582068',
            'email': 'office@microma.rs',
            'website': 'https://microma.rs',
            'telegram': ':'
        }
    },
    'crna_gora': {
        # Podaci za IZVOĐAČA RADOVA u Crnoj Gori
        'contractor': {
            'name': 'Instal M',
            'phone': '+38267423237',
            'email': 'office@instalm.me',
            'website': ':',
            'telegram': '@ivanmujovic'
        }
    }
}

# Telegram ID-ovi admina koji će primati obaveštenja (PROMENITE OVO S VAŠIM ID-jem!)
ADMIN_IDS = [
    6869162490, # ZAMENI OVO SA SVOJIM TELEGRAM ID-jem!
]

# Email podešavanja
EMAIL_SENDER_EMAIL = os.getenv('EMAIL_SENDER_EMAIL')
EMAIL_APP_PASSWORD = os.getenv('EMAIL_APP_PASSWORD') # App Password za Gmail, ne obična lozinka
ADMIN_BCC_EMAIL = os.getenv('ADMIN_BCC_EMAIL', 'testadmin@example.com') # Fallback vrednost

# Globalne varijable za bot
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')

# Učitavanje poruka iz JSON fajlova
def load_messages():
    messages = {}
    for lang in ['en', 'sr', 'de']: # Dodajte jezike po potrebi
        try:
            with open(f'messages_{lang}.json', 'r', encoding='utf-8') as f:
                messages[lang] = json.load(f)
        except FileNotFoundError:
            logger.error(f"messages_{lang}.json not found.")
            messages[lang] = {} # Prazan rečnik ako fajl ne postoji
    return messages

ALL_MESSAGES = load_messages()

def get_messages_for_user(user_id):
    # Koristimo .get() da bismo izbegli KeyError ako user_id nije u user_data ili 'language' nije postavljeno
    lang = user_data.get(user_id, {}).get('language', 'sr') # Default na 'sr' ako nema jezika
    return ALL_MESSAGES.get(lang, ALL_MESSAGES['sr']) # Fallback na 'sr' ako jezik ne postoji u ALL_MESSAGES

# Funkcija za slanje emaila
async def send_email(subject, body, to_email, attachments=None):
    if not EMAIL_SENDER_EMAIL or not EMAIL_APP_PASSWORD:
        logger.critical("Email credentials (EMAIL_SENDER_EMAIL or EMAIL_APP_PASSWORD) not set. Email cannot be sent.")
        return False

    try:
        yag = yagmail.SMTP(EMAIL_SENDER_EMAIL, EMAIL_APP_PASSWORD)
        yag.send(
            to=to_email,
            subject=subject,
            contents=body,
            bcc=ADMIN_BCC_EMAIL, # Slanje kopije adminu
            attachments=attachments
        )
        logger.info(f"Email successfully sent to {to_email} with subject: {subject}")
        return True
    except Exception as e:
        logger.error(f"GREŠKA pri slanju emaila: {e}")
        return False

# --- Pomoćne funkcije (za prikaz menija i upita) ---
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    messages = get_messages_for_user(user_id)
    keyboard = [
        [InlineKeyboardButton(messages["main_menu_quote_button"], callback_data='menu_quote')],
        [InlineKeyboardButton(messages["main_menu_contact_button"], callback_data='menu_contact')],
        [InlineKeyboardButton(messages["main_menu_language_button"], callback_data='menu_language')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(messages["main_menu_text"], reply_markup=reply_markup)
    else:
        await context.bot.send_message(chat_id=user_id, text=messages["main_menu_text"], reply_markup=reply_markup)
    return MAIN_MENU

async def choose_language(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    messages = get_messages_for_user(user_id) # Trenutni jezik (default sr)
    keyboard = [
        [InlineKeyboardButton("English 🇬🇧", callback_data='lang_en')],
        [InlineKeyboardButton("Srpski 🇷🇸", callback_data='lang_sr')],
        [InlineKeyboardButton("Deutsch 🇩🇪", callback_data='lang_de')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(messages["choose_language_text"], reply_markup=reply_markup)
    else:
        await context.bot.send_message(chat_id=user_id, text=messages["choose_language_text"], reply_markup=reply_markup)
    return SELECT_LANGUAGE

async def choose_country(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    messages = get_messages_for_user(user_id)
    keyboard = [
        [InlineKeyboardButton(messages["srbija_button"], callback_data='country_srbija')],
        [InlineKeyboardButton(messages["crna_gora_button"], callback_data='country_crna_gora')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(messages["choose_country_text"], reply_markup=reply_markup)
    return SELECT_COUNTRY

async def show_quote_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    messages = get_messages_for_user(user_id)
    keyboard = [
        [InlineKeyboardButton(messages["quote_heating_button"], callback_data='quote_heating')],
        [InlineKeyboardButton(messages["quote_water_heating_button"], callback_data='quote_water_heating')],
        [InlineKeyboardButton(messages["back_button"], callback_data='back_main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(messages["quote_menu_text"], reply_markup=reply_markup)
    return QUOTE_MENU

async def show_heating_choice(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    messages = get_messages_for_user(user_id)
    keyboard = [
        [InlineKeyboardButton(messages["heating_heat_pump_button"], callback_data='heating_heat_pump')],
        [InlineKeyboardButton(messages["heating_radiator_button"], callback_data='heating_radiator')],
        [InlineKeyboardButton(messages["heating_floor_button"], callback_data='heating_floor')],
        [InlineKeyboardButton(messages["heating_complete_offer_button"], callback_data='heating_complete_offer')],
        [InlineKeyboardButton(messages["back_button"], callback_data='back_quote_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(messages["heating_choice_text"], reply_markup=reply_markup)
    return HEATING_CHOICE

async def show_heat_pump_type_choice(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    messages = get_messages_for_user(user_id)
    keyboard = [
        [InlineKeyboardButton(messages["air_to_water_hp_button"], callback_data='hp_air_to_water')],
        [InlineKeyboardButton(messages["water_to_water_hp_button"], callback_data='hp_water_to_water')],
        [InlineKeyboardButton(messages["ground_source_hp_button"], callback_data='hp_ground_source')],
        [InlineKeyboardButton(messages["back_button"], callback_data='back_heating_choice')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(messages["heat_pump_type_text"], reply_markup=reply_markup)
    return HEAT_PUMP_TYPE

async def show_water_heating_type_choice(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    messages = get_messages_for_user(user_id)
    keyboard = [
        [InlineKeyboardButton(messages["solar_collector_button"], callback_data='wh_solar_collector')],
        [InlineKeyboardButton(messages["heat_pump_wh_button"], callback_data='wh_heat_pump')],
        [InlineKeyboardButton(messages["back_button"], callback_data='back_quote_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(messages["water_heating_type_text"], reply_markup=reply_markup)
    return WATER_HEATING_TYPE

async def show_radiator_type_choice(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    messages = get_messages_for_user(user_id)
    keyboard = [
        [InlineKeyboardButton(messages["radiator_classic_button"], callback_data='rad_classic')],
        [InlineKeyboardButton(messages["radiator_panel_button"], callback_data='rad_panel')],
        [InlineKeyboardButton(messages["radiator_designer_button"], callback_data='rad_designer')],
        [InlineKeyboardButton(messages["back_button"], callback_data='back_heating_choice')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(messages["radiator_type_text"], reply_markup=reply_markup)
    return RADIATOR_TYPE

async def show_floor_heating_type_choice(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    messages = get_messages_for_user(user_id)
    keyboard = [
        [InlineKeyboardButton(messages["floor_wet_button"], callback_data='floor_wet')],
        [InlineKeyboardButton(messages["floor_dry_button"], callback_data='floor_dry')],
        [InlineKeyboardButton(messages["back_button"], callback_data='back_heating_choice')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(messages["floor_heating_type_text"], reply_markup=reply_markup)
    return FLOOR_HEATING_TYPE

async def show_heat_pump_location_choice(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    messages = get_messages_for_user(user_id)
    keyboard = [
        [InlineKeyboardButton(messages["indoor_hp_button"], callback_data='location_indoor')],
        [InlineKeyboardButton(messages["outdoor_hp_button"], callback_data='location_outdoor')],
        [InlineKeyboardButton(messages["back_button"], callback_data='back_hp_type')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(messages["heat_pump_location_text"], reply_markup=reply_markup)
    return HEAT_PUMP_LOCATION_CHOICE

async def show_object_type_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    messages = get_messages_for_user(user_id)
    user_data[user_id]['last_message_id'] = (await update.callback_query.edit_message_text(messages["object_type_prompt"])).message_id
    return OBJECT_TYPE

async def show_area_input_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    messages = get_messages_for_user(user_id)
    # Koristimo update.message.reply_text jer se ova funkcija poziva nakon tekstualnog unosa
    user_data[user_id]['last_message_id'] = (await update.message.reply_text(messages["area_input_prompt"])).message_id
    return AREA_INPUT

async def show_has_sketch_choice(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    messages = get_messages_for_user(user_id)
    keyboard = [
        [InlineKeyboardButton(messages["yes_button"], callback_data='has_sketch_yes')],
        [InlineKeyboardButton(messages["no_button"], callback_data='has_sketch_no')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    # Koristimo update.message.reply_text jer se ova funkcija poziva nakon tekstualnog unosa
    user_data[user_id]['last_message_id'] = (await update.message.reply_text(messages["has_sketch_prompt"], reply_markup=reply_markup)).message_id
    return HAS_SKETCH_CHOICE

async def show_upload_sketch_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    messages = get_messages_for_user(user_id)
    await update.callback_query.edit_message_text(messages["upload_sketch_prompt"])
    return UPLOAD_SKETCH

async def show_confirm_quote_send(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, include_sketch_option=False):
    messages = get_messages_for_user(user_id)
    user_info = user_data[user_id]

    # Priprema teksta sa prikupljenim podacima
    quote_summary = messages["quote_summary_title"] + "\n\n"
    if user_info.get('heating_choice') == 'heating_complete_offer':
        quote_summary += messages["full_heating_offer_summary"].format(
            object_type=user_info.get('object_type', 'N/A'),
            area=user_info.get('area', 'N/A')
        )
    elif user_info.get('heating_choice') == 'heating_heat_pump':
        hp_type_name = messages.get(f"{user_info.get('hp_type_chosen', 'N/A')}_hp_button", user_info.get('hp_type_chosen', 'N/A'))
        hp_location_name = messages.get(f"{user_info.get('hp_location', 'N/A')}_hp_button", user_info.get('hp_location', 'N/A'))
        quote_summary += messages["heat_pump_offer_summary"].format(
            hp_type=hp_type_name,
            hp_location=hp_location_name,
            object_type=user_info.get('object_type', 'N/A'),
            area=user_info.get('area', 'N/A')
        )
    elif user_info.get('heating_choice') == 'heating_radiator':
        rad_type_name = messages.get(f"{user_info.get('radiator_type', 'N/A')}_button", user_info.get('radiator_type', 'N/A'))
        quote_summary += messages["radiator_offer_summary"].format(
            radiator_type=rad_type_name,
            object_type=user_info.get('object_type', 'N/A'),
            area=user_info.get('area', 'N/A')
        )
    elif user_info.get('heating_choice') == 'heating_floor':
        floor_type_name = messages.get(f"{user_info.get('floor_heating_type', 'N/A')}_button", user_info.get('floor_heating_type', 'N/A'))
        quote_summary += messages["floor_heating_offer_summary"].format(
            floor_heating_type=floor_type_name,
            object_type=user_info.get('object_type', 'N/A'),
            area=user_info.get('area', 'N/A')
        )
    elif user_info.get('quote_type') == 'water_heating':
        wh_type_name = messages.get(f"{user_info.get('water_heating_type', 'N/A')}_button", user_info.get('water_heating_type', 'N/A'))
        quote_summary += messages["water_heating_offer_summary"].format(
            water_heating_type=wh_type_name,
            object_type=user_info.get('object_type', 'N/A'),
            area=user_info.get('area', 'N/A')
        )
    # Dodajte ostale tipove grejanja po potrebi
    else:
        # Fallback za scenarije koji možda nisu eksplicitno pokriveni
        quote_summary += messages["generic_quote_summary"].format(
            object_type=user_info.get('object_type', 'N/A'),
            area=user_info.get('area', 'N/A')
        )

    if user_info.get('has_sketch'):
        quote_summary += f"\n\n{messages['sketch_attached_confirmation']}"

    quote_summary += f"\n\n{messages['email_for_quote_prompt']}"

    keyboard = [
        [InlineKeyboardButton(messages["confirm_send_button"], callback_data='confirm_quote_send')],
        [InlineKeyboardButton(messages["cancel_button"], callback_data='cancel_quote')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.edit_message_text(quote_summary, reply_markup=reply_markup)
    return CONFIRM_QUOTE_SEND

async def show_contact_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    messages = get_messages_for_user(user_id)
    country_code = user_data[user_id].get('country')

    if not country_code:
        await update.callback_query.edit_message_text(text=messages["choose_country_first"])
        await choose_country(update, context, user_id)
        return

    keyboard_buttons = []
    # Proverava da li zemlja ima izvođača u contact_info pre dodavanja dugmeta
    if country_code in contact_info and 'contractor' in contact_info[country_code]:
        keyboard_buttons.append([InlineKeyboardButton(messages["contact_contractor_button"], callback_data=f'contact_contractor_{country_code}')])
    
    # Proverava da li zemlja ima proizvođača u contact_info pre dodavanja dugmeta
    if country_code == 'srbija' and 'manufacturer' in contact_info[country_code]:
        keyboard_buttons.append([InlineKeyboardButton(messages["contact_manufacturer_button"], callback_data=f'contact_manufacturer_{country_code}')])

    keyboard_buttons.append([InlineKeyboardButton(messages["back_button"], callback_data='back_main_menu')])
    reply_markup = InlineKeyboardMarkup(keyboard_buttons)

    await update.callback_query.edit_message_text(messages["contact_menu_text"], reply_markup=reply_markup)
    return SELECT_CONTACT_TYPE

# --- Handleri za komande i callbacke ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    logger.info(f"Komanda /start primljena od korisnika {user_id}. Inicijalizujem korisničke podatke.")
    # Inicijalizacija user_data za novog korisnika. Čuva se jezik i zemlja ako postoje.
    if user_id not in user_data:
        user_data[user_id] = {'language': 'sr', 'country': 'srbija'} # Default vrednosti
    
    await choose_language(update, context, user_id)
    return SELECT_LANGUAGE

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_data = context.user_data
    messages = get_messages_for_user(user_id)

    callback_data = query.data

    logger.info(f"Primljen callback query od korisnika {user_id}: {callback_data}")

    # --- Language selection ---
    if callback_data.startswith('lang_'):
        lang = callback_data.split('_')[1]
        user_data[user_id]['language'] = lang
        # Ažuriraj poruke nakon promene jezika
        messages = get_messages_for_user(user_id)
        await choose_country(update, context, user_id)
        return SELECT_COUNTRY

    # --- Country selection ---
    elif callback_data.startswith('country_'):
        country = callback_data.split('_')[1]
        user_data[user_id]['country'] = country
        await show_main_menu(update, context, user_id)
        return MAIN_MENU

    # --- Main Menu navigation ---
    elif callback_data == 'menu_quote':
        await show_quote_menu(update, context, user_id)
        return QUOTE_MENU
    elif callback_data == 'menu_contact':
        await show_contact_menu(update, context, user_id)
        return SELECT_CONTACT_TYPE
    elif callback_data == 'menu_language':
        await choose_language(update, context, user_id)
        return SELECT_LANGUAGE

    # --- Quote Menu navigation ---
    elif callback_data == 'quote_heating':
        user_data[user_id]['quote_type'] = 'heating'
        await show_heating_choice(update, context, user_id)
        return HEATING_CHOICE
    elif callback_data == 'quote_water_heating':
        user_data[user_id]['quote_type'] = 'water_heating'
        await show_water_heating_type_choice(update, context, user_id)
        return WATER_HEATING_TYPE

    # --- Heating Choice navigation ---
    elif callback_data == 'heating_heat_pump':
        user_data[user_id]['heating_choice'] = 'heating_heat_pump'
        await show_heat_pump_type_choice(update, context, user_id)
        return HEAT_PUMP_TYPE
    elif callback_data == 'heating_radiator':
        user_data[user_id]['heating_choice'] = 'heating_radiator'
        await show_radiator_type_choice(update, context, user_id)
        return RADIATOR_TYPE
    elif callback_data == 'heating_floor':
        user_data[user_id]['heating_choice'] = 'heating_floor'
        await show_floor_heating_type_choice(update, context, user_id)
        return FLOOR_HEATING_TYPE
    elif callback_data == 'heating_complete_offer':
        user_data[user_id]['heating_choice'] = 'heating_complete_offer'
        await show_object_type_prompt(update, context, user_id)
        return OBJECT_TYPE

    # --- Heat Pump type selection ---
    elif callback_data.startswith('hp_'):
        hp_type = callback_data.split('_')[1]
        user_data[user_id]['hp_type_chosen'] = hp_type
        
        country_code = user_data[user_id].get('country')

        if not country_code or country_code not in contact_info:
            await query.edit_message_text(text=messages["choose_country_first"])
            await choose_country(update, context, user_id)
            return SELECT_COUNTRY # Vraćamo se na odabir zemlje

        # Preuzimanje podataka o IZVOĐAČU iz contact_info rečnika
        hp_contractor_data = contact_info.get(country_code, {}).get('contractor')

        if hp_contractor_data:
            contractor_name = hp_contractor_data.get('name', messages["no_name_available"])
            phone = hp_contractor_data.get('phone', messages["no_phone_available"])
            email = hp_contractor_data.get('email', messages["no_email_available"])
            
            # Provera i formatiranje za website i telegram, ignorisanje ':'
            website_info = ""
            if hp_contractor_data.get('website') and hp_contractor_data['website'] != ':':
                website_info = f"\nWebsite: {hp_contractor_data['website']}"
            
            telegram_info = ""
            if hp_contractor_data.get('telegram') and hp_contractor_data['telegram'] != ':':
                telegram_info = f"\nTelegram: {hp_contractor_data['telegram']}"

            # Prilagodite poruku za prikaz tipa toplotne pumpe i zemlje
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
            await query.edit_message_text(text=info_text, parse_mode=ParseMode.MARKDOWN) # Dodato parse_mode
            await show_main_menu(update, context, user_id) # Vraća se na glavni meni
            return ConversationHandler.END # Završava konverzaciju nakon prikaza informacija
        else:
            await query.edit_message_text(messages["sending_quote_error"]) # Generic error if no contractor data
            logger.error(f"Nema podataka o izvođaču toplotnih pumpi za zemlju: {country_code}")
            await show_main_menu(update, context, user_id)
            return ConversationHandler.END # Završava konverzaciju

    # --- Water Heating type selection ---
    elif callback_data.startswith('wh_'):
        user_data[user_id]['water_heating_type'] = callback_data.split('_')[1]
        await show_object_type_prompt(update, context, user_id)
        return OBJECT_TYPE

    # --- Radiator type selection ---
    elif callback_data.startswith('rad_'):
        user_data[user_id]['radiator_type'] = callback_data.split('_')[1]
        await show_object_type_prompt(update, context, user_id)
        return OBJECT_TYPE

    # --- Floor Heating type selection ---
    elif callback_data.startswith('floor_'):
        user_data[user_id]['floor_heating_type'] = callback_data.split('_')[1]
        await show_object_type_prompt(update, context, user_id)
        return OBJECT_TYPE

    # --- Heat Pump location choice ---
    elif callback_data.startswith('location_'):
        user_data[user_id]['hp_location'] = callback_data.split('_')[1]
        await show_object_type_prompt(update, context, user_id)
        return OBJECT_TYPE

    # --- Sketch related callbacks ---
    elif callback_data == 'has_sketch_yes':
        await show_upload_sketch_prompt(update, context, user_id)
        return UPLOAD_SKETCH
    elif callback_data == 'has_sketch_no':
        user_data[user_id]['has_sketch'] = False
        await show_confirm_quote_send(update, context, user_id, include_sketch_option=False)
        return CONFIRM_QUOTE_SEND

    # --- Confirm Quote Send ---
    elif callback_data == 'confirm_quote_send':
        await query.edit_message_text(messages["ask_for_email_prompt"])
        return ASK_FOR_EMAIL

    elif callback_data == 'cancel_quote':
        await query.edit_message_text(messages["quote_canceled"])
        await show_main_menu(update, context, user_id)
        return ConversationHandler.END # Završava konverzaciju

    # --- Contact Menu handlers ---
    elif callback_data.startswith('contact_'):
        parts = callback_data.split('_')
        contact_type = parts[1] # 'contractor' ili 'manufacturer'
        country = parts[2]     # 'srbija' ili 'crna_gora'

        contact_data = contact_info.get(country, {}).get(contact_type)

        if contact_data:
            name = contact_data.get('name', messages["no_name_available"])
            phone = contact_data.get('phone', messages["no_phone_available"])
            email = contact_data.get('email', messages["no_email_available"])
            
            website_info = ""
            if contact_data.get('website') and contact_data['website'] != ':':
                website_info = f"\nWebsite: {contact_data['website']}"
            
            telegram_info = ""
            if contact_data.get('telegram') and contact_data['telegram'] != ':':
                telegram_info = f"\nTelegram: {contact_data['telegram']}"

            info_text = messages["contact_info_template"].format(
                name=name,
                phone=phone,
                email=email,
                website_info=website_info,
                telegram_info=telegram_info
            )
            await query.edit_message_text(text=info_text, parse_mode=ParseMode.MARKDOWN)
            await show_main_menu(update, context, user_id)
            return ConversationHandler.END # Završava konverzaciju
        else:
            await query.edit_message_text(messages["contact_info_error"])
            await show_main_menu(update, context, user_id)
            return ConversationHandler.END

    # --- Back buttons ---
    elif callback_data == 'back_main_menu':
        await show_main_menu(update, context, user_id)
        return MAIN_MENU
    elif callback_data == 'back_quote_menu':
        await show_quote_menu(update, context, user_id)
        return QUOTE_MENU
    elif callback_data == 'back_heating_choice':
        await show_heating_choice(update, context, user_id)
        return HEATING_CHOICE
    elif callback_data == 'back_hp_type':
        await show_heat_pump_type_choice(update, context, user_id)
        return HEAT_PUMP_TYPE

    return ConversationHandler.END # Defaultno završava konverzaciju ako nema match-a

async def receive_object_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    messages = get_messages_for_user(user_id)

    # Obriši prethodnu poruku "Unesite tip objekta" (ako postoji)
    if 'last_message_id' in user_data[user_id]:
        try:
            await context.bot.delete_message(chat_id=user_id, message_id=user_data[user_id]['last_message_id'])
            del user_data[user_id]['last_message_id']
        except Exception as e:
            logger.warning(f"Could not delete message for user {user_id}: {e}")

    user_data[user_id]['object_type'] = update.message.text
    # Prosleđujemo 'update' objekat koji sadrži 'message' objekat
    await show_area_input_prompt(update, context, user_id)
    return AREA_INPUT

async def receive_area_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    messages = get_messages_for_user(user_id)

    # Obriši prethodnu poruku "Unesite kvadraturu" (ako postoji)
    if 'last_message_id' in user_data[user_id]:
        try:
            await context.bot.delete_message(chat_id=user_id, message_id=user_data[user_id]['last_message_id'])
            del user_data[user_id]['last_message_id']
        except Exception as e:
            logger.warning(f"Could not delete message for user {user_id}: {e}")

    area_text = update.message.text
    if area_text.isdigit() and int(area_text) > 0:
        user_data[user_id]['area'] = int(area_text)
        # Prosleđujemo 'update' objekat koji sadrži 'message' objekat
        await show_has_sketch_choice(update, context, user_id)
        return HAS_SKETCH_CHOICE
    else:
        await update.message.reply_text(messages["invalid_area_input"])
        return AREA_INPUT

async def receive_sketch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    messages = get_messages_for_user(user_id)

    # Obriši prethodnu poruku "Molimo pošaljite skicu" (ako postoji)
    if 'last_message_id' in user_data[user_id]:
        try:
            await context.bot.delete_message(chat_id=user_id, message_id=user_data[user_id]['last_message_id'])
            del user_data[user_id]['last_message_id']
        except Exception as e:
            logger.warning(f"Could not delete message for user {user_id}: {e}")

    photo_file = update.message.photo[-1].get_file()
    # Preuzmi fajl
    file_path = await photo_file.download_to_drive()
    user_data[user_id]['sketch_path'] = str(file_path) # Sačuvaj putanju do fajla
    user_data[user_id]['has_sketch'] = True

    # Prikaz sumarnog ekrana za potvrdu
    quote_summary = messages["quote_summary_title"] + "\n\n"
    quote_summary += messages["full_heating_offer_summary"].format(
        object_type=user_data[user_id].get('object_type', 'N/A'),
        area=user_data[user_id].get('area', 'N/A')
    )
    quote_summary += f"\n\n{messages['sketch_attached_confirmation']}" # Poruka da je skica priložena
    quote_summary += f"\n\n{messages['email_for_quote_prompt']}"

    keyboard = [
        [InlineKeyboardButton(messages["confirm_send_button"], callback_data='confirm_quote_send')],
        [InlineKeyboardButton(messages["cancel_button"], callback_data='cancel_quote')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(quote_summary, reply_markup=reply_markup)
    return CONFIRM_QUOTE_SEND

async def receive_email_for_quote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    messages = get_messages_for_user(user_id)
    user_email = update.message.text
    user_data[user_id]['user_email'] = user_email

    # Validacija emaila
    if "@" not in user_email or "." not in user_email:
        await update.message.reply_text(messages["invalid_email_format"])
        return ASK_FOR_EMAIL

    # Generisanje email sadržaja
    user_info = user_data[user_id]
    subject = messages["quote_email_subject"].format(user_id=user_id)

    body = messages["email_body_header"].format(
        user_id=user_id,
        first_name=update.effective_user.first_name,
        last_name=update.effective_user.last_name if update.effective_user.last_name else '',
        username=update.effective_user.username if update.effective_user.username else ''
    )

    body += messages["country_email_field"].format(country=messages.get(f"{user_info.get('country', 'N/A')}_button", user_info.get('country', 'N/A')))
    body += messages["object_type_email_field"].format(object_type=user_info.get('object_type', 'N/A'))
    body += messages["area_email_field"].format(area=user_info.get('area', 'N/A'))

    # Dodavanje detalja o izboru grejanja
    heating_choice_key = user_info.get('heating_choice')
    if heating_choice_key == 'heating_complete_offer':
        body += messages["heating_choice_email_field"].format(choice=messages["heating_complete_offer_button"])
    elif heating_choice_key == 'heating_heat_pump':
        hp_type_name = messages.get(f"{user_info.get('hp_type_chosen', 'N/A')}_hp_button", user_info.get('hp_type_chosen', 'N/A'))
        hp_location_name = messages.get(f"{user_info.get('hp_location', 'N/A')}_hp_button", user_info.get('hp_location', 'N/A'))
        body += messages["heating_choice_email_field"].format(choice=messages["heating_heat_pump_button"])
        body += messages["hp_type_email_field"].format(hp_type=hp_type_name)
        body += messages["hp_location_email_field"].format(hp_location=hp_location_name)
    elif heating_choice_key == 'heating_radiator':
        rad_type_name = messages.get(f"{user_info.get('radiator_type', 'N/A')}_button", user_info.get('radiator_type', 'N/A'))
        body += messages["heating_choice_email_field"].format(choice=messages["heating_radiator_button"])
        body += messages["radiator_type_email_field"].format(radiator_type=rad_type_name)
    elif heating_choice_key == 'heating_floor':
        floor_type_name = messages.get(f"{user_info.get('floor_heating_type', 'N/A')}_button", user_info.get('floor_heating_type', 'N/A'))
        body += messages["heating_choice_email_field"].format(choice=messages["heating_floor_button"])
        body += messages["floor_heating_type_email_field"].format(floor_type=floor_type_name)
    
    # Dodavanje detalja o izboru grejanja vode
    water_heating_choice_key = user_info.get('water_heating_type')
    if water_heating_choice_key == 'wh_solar_collector':
        body += messages["water_heating_choice_email_field"].format(choice=messages["solar_collector_button"])
    elif water_heating_choice_key == 'wh_heat_pump':
        body += messages["water_heating_choice_email_field"].format(choice=messages["heat_pump_wh_button"])


    attachments = []
    if user_data[user_id].get('has_sketch') and user_data[user_id].get('sketch_path'):
        body += messages["sketch_email_field"]
        attachments.append(user_data[user_id]['sketch_path'])

    # Slanje emaila
    email_sent = await send_email(subject, body, user_email, attachments)

    if email_sent:
        await update.message.reply_text(messages["quote_sent_success"])
    else:
        await update.message.reply_text(messages["quote_sent_error"])

    # Čišćenje korisničkih podataka i povratak na glavni meni
    if user_data[user_id].get('sketch_path') and os.path.exists(user_data[user_id]['sketch_path']):
        os.remove(user_data[user_id]['sketch_path']) # Brišemo fajl sa skicom
    
    # Resetuj podatke za ponovni unos, zadrži jezik i zemlju
    user_data[user_id] = {'language': user_data[user_id].get('language', 'sr'), 'country': user_data[user_id].get('country', 'srbija')} 
    await show_main_menu(update, context, user_id)
    return ConversationHandler.END # Završava konverzaciju


# Handler za nepoznate komande
async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    messages = get_messages_for_user(user_id)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=messages["unknown_command_text"])

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} prouzrokovao grešku {context.error}")
    # Opciono, pošaljite poruku korisniku da je došlo do greške
    if update.effective_user:
        messages = get_messages_for_user(update.effective_user.id)
        await context.bot.send_message(chat_id=update.effective_user.id, text=messages.get("general_error_message", "Došlo je do greške. Pokušajte ponovo."))


# Inicijalizacija user_data van funkcija da bi bila globalno dostupna
user_data = {}

def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.critical("TELEGRAM_BOT_TOKEN environment variable not set. Bot cannot start.")
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set.")

    # Uvek kreiramo Application objekat
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    logger.info(f"Bot se pokreće sa najnovijim kodom! Vreme pokretanja: {datetime.datetime.now()}")

    # Konverzacijski handler
    # Važno: entry_points može biti lista handlera.
    # Ako želite da /start započinje konverzaciju, stavite ga ovde.
    # Ako želite da dugmad pokreću konverzaciju, to radite kroz button_callback.
    sketch_conversation_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SELECT_LANGUAGE: [CallbackQueryHandler(button_callback, pattern='^lang_')],
            SELECT_COUNTRY: [CallbackQueryHandler(button_callback, pattern='^country_')],
            MAIN_MENU: [CallbackQueryHandler(button_callback, pattern='^menu_')],
            QUOTE_MENU: [CallbackQueryHandler(button_callback, pattern='^quote_')],
            HEATING_CHOICE: [CallbackQueryHandler(button_callback, pattern='^heating_')],
            HEAT_PUMP_TYPE: [CallbackQueryHandler(button_callback, pattern='^hp_')],
            WATER_HEATING_TYPE: [CallbackQueryHandler(button_callback, pattern='^wh_')],
            RADIATOR_TYPE: [CallbackQueryHandler(button_callback, pattern='^rad_')],
            FLOOR_HEATING_TYPE: [CallbackQueryHandler(button_callback, pattern='^floor_')],
            HEAT_PUMP_LOCATION_CHOICE: [CallbackQueryHandler(button_callback, pattern='^location_')],
            OBJECT_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_object_type)],
            AREA_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_area_input)],
            HAS_SKETCH_CHOICE: [CallbackQueryHandler(button_callback, pattern='^has_sketch_')],
            UPLOAD_SKETCH: [MessageHandler(filters.PHOTO, receive_sketch)],
            CONFIRM_QUOTE_SEND: [CallbackQueryHandler(button_callback, pattern='^(confirm_quote_send|cancel_quote)$')],
            ASK_FOR_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_email_for_quote)],
            SELECT_CONTACT_TYPE: [CallbackQueryHandler(button_callback, pattern='^contact_')],
        },
        fallbacks=[
            CallbackQueryHandler(button_callback, pattern='^back_'), # Generalni back button handler
            CommandHandler('start', start) # Resetuje konverzaciju ako se kuca /start
        ],
        allow_reentry=True # Dozvoljava ponovni ulazak u konverzaciju ako je već aktivna
    )

    application.add_handler(sketch_conversation_handler)
    application.add_handler(MessageHandler(filters.COMMAND, unknown)) # Unknown command handler
    application.add_error_handler(error_handler)

    if WEBHOOK_URL:
        # Pokreni bot u webhook modu
        PORT = int(os.environ.get('PORT', 8080)) # Render preporučuje da PORT bude 10000, proverite vaše podešavanje
        application.run_webhook(listen="0.0.0.0",
                                port=PORT,
                                url_path=TELEGRAM_BOT_TOKEN,
                                webhook_url=f"{WEBHOOK_URL}/{TELEGRAM_BOT_TOKEN}")
        logger.info(f"Bot pokrenut u webhook modu. URL: {WEBHOOK_URL}/{TELEGRAM_BOT_TOKEN}, Port: {PORT}")
    else:
        # Pokreni bot u polling modu (za lokalno testiranje)
        logger.info("Bot pokrenut u polling modu.")
        application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()