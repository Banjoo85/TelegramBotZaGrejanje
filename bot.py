import os
import logging
import json
import yagmail
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler,
)
from telegram.constants import ParseMode

# Load environment variables from .env file
load_dotenv()

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# States for ConversationHandler
SELECTING_LANGUAGE, SELECTING_COUNTRY, MAIN_MENU, SELECTING_INSTALLATION_TYPE, \
    SELECTING_HEATING_SYSTEM, SELECTING_HEAT_PUMP_SUBTYPE, REQUESTING_OBJECT_TYPE, \
    REQUESTING_SURFACE_AREA, REQUESTING_NUM_FLOORS, REQUESTING_SKETCH, \
    REQUESTING_CONTACT_INFO, REQUESTING_EMAIL, CONFIRMING_DETAILS, SHOWING_CONTACT_INFO = range(14)

# Environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL") # Your email for BCC

# Directory for sketches
SKETCH_DIR = "sketches"
os.makedirs(SKETCH_DIR, exist_ok=True)

# Load messages from JSON files
MESSAGES = {}
for lang_code in ["sr", "en", "ru"]:
    with open(f"messages_{lang_code}.json", "r", encoding="utf-8") as f:
        MESSAGES[lang_code] = json.load(f)

def get_message(lang_code, key):
    return MESSAGES.get(lang_code, {}).get(key, MESSAGES["sr"].get(key, "Error: Message not found"))

# --- Helper functions for keyboards ---

def get_language_keyboard():
    keyboard = [
        [InlineKeyboardButton("Srpski 🇷🇸", callback_data="lang_sr")],
        [InlineKeyboardButton("English 🇬🇧", callback_data="lang_en")],
        [InlineKeyboardButton("Русский 🇷🇺", callback_data="lang_ru")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_country_keyboard(lang_code):
    keyboard = [
        [InlineKeyboardButton(get_message(lang_code, "srbija_button"), callback_data="country_srbija")],
        [InlineKeyboardButton(get_message(lang_code, "crna_gora_button"), callback_data="country_crnagora")],
    ]
    return InlineKeyboardMarkup(keyboard)

def main_menu_markup(lang_code):
    keyboard = [
        [InlineKeyboardButton(get_message(lang_code, "request_quote_button"), callback_data="main_request_quote")],
        [InlineKeyboardButton(get_message(lang_code, "faq_button"), callback_data="main_faq")],
        [InlineKeyboardButton(get_message(lang_code, "contact_button"), callback_data="main_contact")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_installation_type_keyboard(lang_code):
    keyboard = [
        [InlineKeyboardButton(get_message(lang_code, "heating_installation_button"), callback_data="inst_heating")],
        [InlineKeyboardButton(get_message(lang_code, "heat_pump_button"), callback_data="inst_heat_pump")],
        [InlineKeyboardButton(get_message(lang_code, "back_button"), callback_data="back_to_main_menu")], # Back button
    ]
    return InlineKeyboardMarkup(keyboard)

def get_heating_system_keyboard(lang_code, country_code):
    keyboard = [
        [InlineKeyboardButton(get_message(lang_code, "radiators_button"), callback_data="hs_radiators")],
        [InlineKeyboardButton(get_message(lang_code, "fan_coils_button"), callback_data="hs_fan_coils")],
        [InlineKeyboardButton(get_message(lang_code, "underfloor_heating_button"), callback_data="hs_underfloor")],
        [InlineKeyboardButton(get_message(lang_code, "underfloor_plus_fan_coils_button"), callback_data="hs_underfloor_plus_fan_coils")],
    ]
    if country_code == "srbija":
        keyboard.append([InlineKeyboardButton(get_message(lang_code, "complete_heat_pump_offer_button"), callback_data="hs_complete_hp")])

    keyboard.append([InlineKeyboardButton(get_message(lang_code, "back_button"), callback_data="back_to_installation_type_selection")]) # Back button
    return InlineKeyboardMarkup(keyboard)

def get_heat_pump_subtype_keyboard(lang_code, country_code):
    keyboard = []
    if country_code == "srbija":
        keyboard.append([InlineKeyboardButton(get_message(lang_code, "water_water_hp_button"), callback_data="hps_water_water")])
        keyboard.append([InlineKeyboardButton(get_message(lang_code, "air_water_hp_button"), callback_data="hps_air_water")])
    elif country_code == "crnagora":
        keyboard.append([InlineKeyboardButton(get_message(lang_code, "air_water_hp_button"), callback_data="hps_air_water")])

    keyboard.append([InlineKeyboardButton(get_message(lang_code, "back_button"), callback_data="back_to_installation_type_selection")]) # Back button
    return InlineKeyboardMarkup(keyboard)

def get_confirm_cancel_keyboard(lang_code):
    keyboard = [
        [InlineKeyboardButton(get_message(lang_code, "confirm_button"), callback_data="confirm_yes")],
        [InlineKeyboardButton(get_message(lang_code, "cancel_button"), callback_data="confirm_no")],
    ]
    return InlineKeyboardMarkup(keyboard)

# --- Command Handlers ---

async def start(update: Update, context):
    context.user_data.clear() # Clear user data on start
    await update.message.reply_text(
        get_message("sr", "start_message"), # Default to Serbian for initial choice
        reply_markup=get_language_keyboard()
    )
    return SELECTING_LANGUAGE

# --- Callback Handlers ---

async def select_language(update: Update, context):
    query = update.callback_query
    await query.answer()
    lang_code = query.data.split('_')[1]
    context.user_data['lang'] = lang_code
    await query.edit_message_text(
        text=get_message(lang_code, "language_selected"),
        reply_markup=get_country_keyboard(lang_code)
    )
    return SELECTING_COUNTRY

async def select_country(update: Update, context):
    query = update.callback_query
    await query.answer()
    lang_code = context.user_data['lang']
    country_code = query.data.split('_')[1]
    context.user_data['country'] = country_code

    # Store display name for country
    if country_code == "srbija":
        context.user_data['country_display'] = get_message(lang_code, "srbija_button").replace(" 🇷🇸", "")
    elif country_code == "crnagora":
        context.user_data['country_display'] = get_message(lang_code, "crna_gora_button").replace(" 🇲🇪", "")

    await query.edit_message_text(
        text=get_message(lang_code, "country_selected").format(country_name=context.user_data['country_display']),
        reply_markup=main_menu_markup(lang_code)
    )
    return MAIN_MENU

async def main_menu_action(update: Update, context):
    query = update.callback_query
    await query.answer()
    lang_code = context.user_data['lang']

    action = query.data.split('_')[1]

    if action == "request_quote":
        await query.edit_message_text(
            text=get_message(lang_code, "choose_installation_type"),
            reply_markup=get_installation_type_keyboard(lang_code)
        )
        return SELECTING_INSTALLATION_TYPE
    # "services_info" je uklonjen
    elif action == "faq":
        await query.edit_message_text(
            text=get_message(lang_code, "faq_message"), # Dodaj faq_message u JSON
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_message(lang_code, "back_button"), callback_data="back_to_main_menu")]])
        )
        return MAIN_MENU # Ostavljamo u MAIN_MENU state da se lakse vrati
    elif action == "contact":
        return await show_contact_info_step(update, context)


async def select_installation_type(update: Update, context):
    query = update.callback_query
    await query.answer()
    lang_code = context.user_data['lang']
    country_code = context.user_data['country']
    installation_type_code = query.data.split('_')[1]
    context.user_data['installation_type'] = installation_type_code

    installation_type_display = ""
    if installation_type_code == "heating":
        installation_type_display = get_message(lang_code, "installation_type_heating_text")
        context.user_data['installation_type_display'] = installation_type_display

        # Show contractor info based on country
        if country_code == "srbija":
            text = get_message(lang_code, "srbija_heating_intro") + "\n\n" + \
                   get_message(lang_code, "contact_srbija_contractor_display").format(
                       phone=get_message(lang_code, "contact_info_srbija_contractor_phone"),
                       email=get_message(lang_code, "contact_info_srbija_contractor_email"),
                       website=get_message(lang_code, "contact_info_srbija_contractor_website"),
                       telegram=get_message(lang_code, "contact_info_srbija_contractor_telegram")
                   )
            reply_markup = get_heating_system_keyboard(lang_code, country_code)
            next_state = SELECTING_HEATING_SYSTEM
        elif country_code == "crnagora":
            text = get_message(lang_code, "crna_gora_heating_intro") + "\n\n" + \
                   get_message(lang_code, "contact_crna_gora_contractor_display").format(
                       name=get_message(lang_code, "contact_info_crna_gora_contractor_name"),
                       phone=get_message(lang_code, "contact_info_crna_gora_contractor_phone"),
                       email=get_message(lang_code, "contact_info_crna_gora_contractor_email"),
                       website=get_message(lang_code, "contact_info_crna_gora_contractor_website"),
                       telegram=get_message(lang_code, "contact_info_crna_gora_contractor_telegram")
                   )
            reply_markup = get_heating_system_keyboard(lang_code, country_code)
            next_state = SELECTING_HEATING_SYSTEM
        else:
            text = get_message(lang_code, "contact_info_not_available")
            reply_markup = get_installation_type_keyboard(lang_code)
            next_state = SELECTING_INSTALLATION_TYPE # Stay in current state

        await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        return next_state


    elif installation_type_code == "heat_pump":
        installation_type_display = get_message(lang_code, "installation_type_heatpump_text")
        context.user_data['installation_type_display'] = installation_type_display
        context.user_data['heating_system_type'] = None # Reset heating system type for HP

        # Show manufacturer info based on country
        if country_code == "srbija":
            text = get_message(lang_code, "srbija_heat_pump_intro") + "\n\n" + \
                   get_message(lang_code, "contact_srbija_manufacturer_display").format(
                       name=get_message(lang_code, "contact_info_srbija_manufacturer_name"),
                       phone=get_message(lang_code, "contact_info_srbija_manufacturer_phone"),
                       email=get_message(lang_code, "contact_info_srbija_manufacturer_email"),
                       website=get_message(lang_code, "contact_info_srbija_manufacturer_website"),
                       telegram=get_message(lang_code, "contact_info_srbija_manufacturer_telegram")
                   )
            reply_markup = get_heat_pump_subtype_keyboard(lang_code, country_code)
            next_state = SELECTING_HEAT_PUMP_SUBTYPE
        elif country_code == "crnagora":
            text = get_message(lang_code, "crna_gora_heat_pump_intro") + "\n\n" + \
                   get_message(lang_code, "contact_crna_gora_contractor_display").format(
                       name=get_message(lang_code, "contact_info_crna_gora_contractor_name"),
                       phone=get_message(lang_code, "contact_info_crna_gora_contractor_phone"),
                       email=get_message(lang_code, "contact_info_crna_gora_contractor_email"),
                       website=get_message(lang_code, "contact_info_crna_gora_contractor_website"),
                       telegram=get_message(lang_code, "contact_info_crna_gora_contractor_telegram")
                   )
            reply_markup = get_heat_pump_subtype_keyboard(lang_code, country_code)
            next_state = SELECTING_HEAT_PUMP_SUBTYPE
        else:
            text = get_message(lang_code, "contact_info_not_available")
            reply_markup = get_installation_type_keyboard(lang_code)
            next_state = SELECTING_INSTALLATION_TYPE

        await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        return next_state


async def select_heating_system(update: Update, context):
    query = update.callback_query
    await query.answer()
    lang_code = context.user_data['lang']
    heating_system_code = query.data.split('_')[1]
    context.user_data['heating_system_type'] = heating_system_code
    context.user_data['heat_pump_subtype'] = None # Reset HP subtype for heating systems

    # Map codes to display text
    heating_system_display = get_message(lang_code, f"heating_system_type_{heating_system_code}_text")
    context.user_data['heating_system_type_display'] = heating_system_display

    await query.edit_message_text(
        text=f"{heating_system_display} {get_message(lang_code, 'selected_text')}\n\n" +
             get_message(lang_code, "request_object_details")
    )
    return REQUESTING_OBJECT_TYPE

async def select_heat_pump_subtype(update: Update, context):
    query = update.callback_query
    await query.answer()
    lang_code = context.user_data['lang']
    heat_pump_subtype_code = query.data.split('_')[1]
    context.user_data['heat_pump_subtype'] = heat_pump_subtype_code
    context.user_data['heating_system_type'] = None # Reset heating system type for HP

    # Map codes to display text
    heat_pump_subtype_display = get_message(lang_code, f"heat_pump_subtype_{heat_pump_subtype_code}_text")
    context.user_data['heat_pump_subtype_display'] = heat_pump_subtype_display

    await query.edit_message_text(
        text=f"{heat_pump_subtype_display} {get_message(lang_code, 'selected_text')}\n\n" +
             get_message(lang_code, "request_object_details")
    )
    return REQUESTING_OBJECT_TYPE

async def request_object_type(update: Update, context):
    lang_code = context.user_data['lang']
    context.user_data['object_type'] = update.message.text
    await update.message.reply_text(get_message(lang_code, "request_surface_area"))
    return REQUESTING_SURFACE_AREA

async def request_surface_area(update: Update, context):
    lang_code = context.user_data['lang']
    try:
        surface_area = int(update.message.text)
        if surface_area <= 0:
            raise ValueError
        context.user_data['surface_area'] = surface_area
        await update.message.reply_text(get_message(lang_code, "request_number_of_floors"))
        return REQUESTING_NUM_FLOORS
    except ValueError:
        await update.message.reply_text(get_message(lang_code, "invalid_surface_area"))
        return REQUESTING_SURFACE_AREA

async def request_num_floors(update: Update, context):
    lang_code = context.user_data['lang']
    try:
        num_floors = int(update.message.text)
        if num_floors <= 0:
            raise ValueError
        context.user_data['num_floors'] = num_floors
        await update.message.reply_text(get_message(lang_code, "request_sketch"))
        return REQUESTING_SKETCH
    except ValueError:
        await update.message.reply_text(get_message(lang_code, "invalid_floor_number"))
        return REQUESTING_NUM_FLOORS

async def request_sketch(update: Update, context):
    lang_code = context.user_data['lang']
    if update.message.document:
        file_id = update.message.document.file_id
        file_name = update.message.document.file_name
        file_path = os.path.join(SKETCH_DIR, file_name)
        new_file = await context.bot.get_file(file_id)
        await new_file.download_to_drive(file_path)
        context.user_data['sketch_path'] = file_path
        context.user_data['sketch_attached'] = get_message(lang_code, "yes_text")
        await update.message.reply_text(get_message(lang_code, "request_contact_info"))
        return REQUESTING_CONTACT_INFO
    elif update.message.photo:
        photo_file = await update.message.photo[-1].get_file()
        file_name = f"sketch_{update.message.from_user.id}_{photo_file.file_id}.jpg"
        file_path = os.path.join(SKETCH_DIR, file_name)
        await photo_file.download_to_drive(file_path)
        context.user_data['sketch_path'] = file_path
        context.user_data['sketch_attached'] = get_message(lang_code, "yes_text")
        await update.message.reply_text(get_message(lang_code, "request_contact_info"))
        return REQUESTING_CONTACT_INFO
    elif update.message.text and update.message.text.lower() == get_message(lang_code, "no_sketch_text").lower():
        context.user_data['sketch_path'] = None
        context.user_data['sketch_attached'] = get_message(lang_code, "no_sketch_provided")
        await update.message.reply_text(get_message(lang_code, "request_contact_info"))
        return REQUESTING_CONTACT_INFO
    else:
        await update.message.reply_text(get_message(lang_code, "invalid_sketch_input"))
        return REQUESTING_SKETCH

async def request_contact_info(update: Update, context):
    lang_code = context.user_data['lang']
    contact_info = update.message.text
    if "," in contact_info:
        parts = contact_info.split(",", 1)
        context.user_data['contact_name'] = parts[0].strip()
        context.user_data['contact_phone'] = parts[1].strip()
        await update.message.reply_text(get_message(lang_code, "request_email"))
        return REQUESTING_EMAIL
    else:
        await update.message.reply_text(get_message(lang_code, "invalid_contact_info_format"))
        return REQUESTING_CONTACT_INFO

async def request_email(update: Update, context):
    lang_code = context.user_data['lang']
    email = update.message.text
    if "@" in email and "." in email: # Basic email validation
        context.user_data['contact_email'] = email
        return await confirm_details(update, context)
    else:
        await update.message.reply_text(get_message(lang_code, "invalid_email_format"))
        return REQUESTING_EMAIL

async def confirm_details(update: Update, context):
    lang_code = context.user_data['lang']
    user_data = context.user_data

    # Prepare display names, handling cases where they might not be set
    country_display = user_data.get('country_display', get_message(lang_code, 'contact_info_not_available'))
    installation_type_display = user_data.get('installation_type_display', get_message(lang_code, 'contact_info_not_available'))
    heating_system_type_display = user_data.get('heating_system_type_display', get_message(lang_code, 'contact_info_not_available'))
    heat_pump_subtype_display = user_data.get('heat_pump_subtype_display', get_message(lang_code, 'contact_info_not_available'))

    # If heating system was chosen, set heat_pump_subtype_display to N/A
    if user_data.get('heating_system_type'):
        heat_pump_subtype_display = get_message(lang_code, 'no_sketch_provided') # Koristimo ovu poruku za "N/A"
    # If heat pump was chosen, set heating_system_type_display to N/A
    elif user_data.get('heat_pump_subtype'):
        heating_system_type_display = get_message(lang_code, 'no_sketch_provided') # Koristimo ovu poruku za "N/A"
    else:
        # Default to N/A if neither was explicitly chosen yet (shouldn't happen in proper flow)
        heating_system_type_display = get_message(lang_code, 'no_sketch_provided')
        heat_pump_subtype_display = get_message(lang_code, 'no_sketch_provided')

    confirmation_text = get_message(lang_code, "confirm_details").format(
        country=country_display,
        installation_type=installation_type_display,
        heating_system_type=heating_system_type_display,
        heat_pump_subtype=heat_pump_subtype_display,
        object_type=user_data.get('object_type', 'N/A'),
        surface_area=user_data.get('surface_area', 'N/A'),
        num_floors=user_data.get('num_floors', 'N/A'),
        sketch_attached=user_data.get('sketch_attached', get_message(lang_code, 'no_sketch_provided')),
        contact_name=user_data.get('contact_name', 'N/A'),
        contact_phone=user_data.get('contact_phone', 'N/A'),
        contact_email=user_data.get('contact_email', 'N/A')
    )

    if update.callback_query: # From back button to confirmation
        await update.callback_query.edit_message_text(
            text=confirmation_text,
            reply_markup=get_confirm_cancel_keyboard(lang_code)
        )
    else: # First time entering confirmation
        await update.message.reply_text(
            text=confirmation_text,
            reply_markup=get_confirm_cancel_keyboard(lang_code)
        )
    return CONFIRMING_DETAILS

async def final_confirm(update: Update, context):
    query = update.callback_query
    await query.answer()
    lang_code = context.user_data['lang']
    if query.data == "confirm_yes":
        await send_inquiry_email(context)
        await query.edit_message_text(get_message(lang_code, "inquiry_sent_success"))
        context.user_data.clear() # Clear data after successful sending
        return ConversationHandler.END
    else: # confirm_no or cancel
        await query.edit_message_text(get_message(lang_code, "inquiry_canceled"))
        context.user_data.clear()
        return ConversationHandler.END

async def send_inquiry_email(context):
    user_data = context.user_data
    lang_code = user_data['lang']

    country_display = user_data.get('country_display', 'N/A')
    installation_type_display = user_data.get('installation_type_display', 'N/A')
    heating_system_type_display = user_data.get('heating_system_type_display', 'N/A')
    heat_pump_subtype_display = user_data.get('heat_pump_subtype_display', 'N/A')

    # Determine recipient email based on selected country and installation type
    recipient_email = None
    if user_data.get('country') == 'srbija':
        if user_data.get('installation_type') == 'heating':
            recipient_email = get_message('sr', 'contact_info_srbija_contractor_email') # Igor Bošković
        elif user_data.get('installation_type') == 'heat_pump':
            recipient_email = get_message('sr', 'contact_info_srbija_manufacturer_email') # Microma
    elif user_data.get('country') == 'crnagora':
        recipient_email = get_message('sr', 'contact_info_crna_gora_contractor_email') # Instal M (for both heating and HP)

    if not recipient_email:
        logger.error("No recipient email found for the selected options.")
        return # Do not attempt to send if no recipient

    # Construct email subject
    email_subject = get_message(lang_code, "email_subject").format(
        country_display=country_display,
        installation_type_display=installation_type_display
    )

    # Construct email body
    body = get_message(lang_code, "confirm_details").format(
        country=country_display,
        installation_type=installation_type_display,
        heating_system_type=heating_system_type_display if user_data.get('heating_system_type') else 'N/A',
        heat_pump_subtype=heat_pump_subtype_display if user_data.get('heat_pump_subtype') else 'N/A',
        object_type=user_data.get('object_type', 'N/A'),
        surface_area=user_data.get('surface_area', 'N/A'),
        num_floors=user_data.get('num_floors', 'N/A'),
        sketch_attached=user_data.get('sketch_attached', get_message(lang_code, 'no_sketch_provided')),
        contact_name=user_data.get('contact_name', 'N/A'),
        contact_phone=user_data.get('contact_phone', 'N/A'),
        contact_email=user_data.get('contact_email', 'N/A')
    )

    attachments = []
    if user_data.get('sketch_path'):
        attachments.append(user_data['sketch_path'])

    try:
        yag = yagmail.SMTP(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
        yag.send(
            to=recipient_email,
            bcc=ADMIN_EMAIL, # Send BCC copy to admin
            subject=email_subject,
            contents=body,
            attachments=attachments
        )
        logger.info(f"Email sent successfully to {recipient_email} with BCC to {ADMIN_EMAIL}")

        # Clean up sketch file after sending email
        if user_data.get('sketch_path') and os.path.exists(user_data['sketch_path']):
            os.remove(user_data['sketch_path'])
            logger.info(f"Deleted sketch file: {user_data['sketch_path']}")

    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        # Optionally, inform the user about the error

async def show_contact_info_step(update: Update, context):
    query = update.callback_query
    lang_code = context.user_data['lang']
    country_code = context.user_data.get('country') # Get current country

    contact_message = get_message(lang_code, "contact_info_not_available")
    if country_code == "srbija":
        contact_message = get_message(lang_code, "contact_srbija_contractor_display").format(
            phone=get_message(lang_code, "contact_info_srbija_contractor_phone"),
            email=get_message(lang_code, "contact_info_srbija_contractor_email"),
            website=get_message(lang_code, "contact_info_srbija_contractor_website"),
            telegram=get_message(lang_code, "contact_info_srbija_contractor_telegram")
        ) + "\n\n" + get_message(lang_code, "contact_srbija_manufacturer_display").format(
            name=get_message(lang_code, "contact_info_srbija_manufacturer_name"),
            phone=get_message(lang_code, "contact_info_srbija_manufacturer_phone"),
            email=get_message(lang_code, "contact_info_srbija_manufacturer_email"),
            website=get_message(lang_code, "contact_info_srbija_manufacturer_website"),
            telegram=get_message(lang_code, "contact_info_srbija_manufacturer_telegram")
        )
    elif country_code == "crnagora":
        contact_message = get_message(lang_code, "contact_crna_gora_contractor_display").format(
            name=get_message(lang_code, "contact_info_crna_gora_contractor_name"),
            phone=get_message(lang_code, "contact_info_crna_gora_contractor_phone"),
            email=get_message(lang_code, "contact_info_crna_gora_contractor_email"),
            website=get_message(lang_code, "contact_info_crna_gora_contractor_website"),
            telegram=get_message(lang_code, "contact_info_crna_gora_contractor_telegram")
        )

    await query.edit_message_text(
        text=contact_message,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(get_message(lang_code, "back_button"), callback_data="back_to_main_menu")]])
    )
    return MAIN_MENU # Stay in MAIN_MENU state to allow easy return

# --- Back Button Handlers ---

async def back_to_main_menu(update: Update, context):
    query = update.callback_query
    await query.answer()
    lang_code = context.user_data['lang']
    await query.edit_message_text(
        text=get_message(lang_code, "back_to_main_menu") + "\n" + get_message(lang_code, "main_menu_greeting"),
        reply_markup=main_menu_markup(lang_code)
    )
    return MAIN_MENU

async def back_to_country_selection(update: Update, context):
    query = update.callback_query
    await query.answer()
    lang_code = context.user_data['lang']
    await query.edit_message_text(
        text=get_message(lang_code, "back_to_country_selection") + "\n" + get_message(lang_code, "choose_country"),
        reply_markup=get_country_keyboard(lang_code)
    )
    return SELECTING_COUNTRY

async def back_to_installation_type_selection(update: Update, context):
    query = update.callback_query
    await query.answer()
    lang_code = context.user_data['lang']
    await query.edit_message_text(
        text=get_message(lang_code, "back_to_installation_type_selection") + "\n" + get_message(lang_code, "choose_installation_type"),
        reply_markup=get_installation_type_keyboard(lang_code)
    )
    return SELECTING_INSTALLATION_TYPE

async def back_to_heating_system_selection(update: Update, context):
    query = update.callback_query
    await query.answer()
    lang_code = context.user_data['lang']
    country_code = context.user_data['country'] # Need country to correctly display heating systems
    await query.edit_message_text(
        text=get_message(lang_code, "back_to_heating_system_selection") + "\n\n" + get_message(lang_code, "choose_heating_system"),
        reply_markup=get_heating_system_keyboard(lang_code, country_code)
    )
    return SELECTING_HEATING_SYSTEM

async def back_to_heat_pump_subtype_selection(update: Update, context):
    query = update.callback_query
    await query.answer()
    lang_code = context.user_data['lang']
    country_code = context.user_data['country'] # Need country to correctly display HP subtypes
    await query.edit_message_text(
        text=get_message(lang_code, "back_to_heat_pump_subtype_selection") + "\n\n" + get_message(lang_code, "select_heat_pump_subtype"),
        reply_markup=get_heat_pump_subtype_keyboard(lang_code, country_code)
    )
    return SELECTING_HEAT_PUMP_SUBTYPE

# --- Main function ---

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECTING_LANGUAGE: [
                CallbackQueryHandler(select_language, pattern="^lang_"),
            ],
            SELECTING_COUNTRY: [
                CallbackQueryHandler(select_country, pattern="^country_"),
                CallbackQueryHandler(back_to_main_menu, pattern="^back_to_main_menu$") # Add back button
            ],
            MAIN_MENU: [
                CallbackQueryHandler(main_menu_action, pattern="^main_"),
                CallbackQueryHandler(select_country, pattern="^country_"), # Keep for contact info
            ],
            SELECTING_INSTALLATION_TYPE: [
                CallbackQueryHandler(select_installation_type, pattern="^inst_"),
                CallbackQueryHandler(back_to_main_menu, pattern="^back_to_main_menu$") # Add back button
            ],
            SELECTING_HEATING_SYSTEM: [
                CallbackQueryHandler(select_heating_system, pattern="^hs_"),
                CallbackQueryHandler(back_to_installation_type_selection, pattern="^back_to_installation_type_selection$") # Add back button
            ],
            SELECTING_HEAT_PUMP_SUBTYPE: [
                CallbackQueryHandler(select_heat_pump_subtype, pattern="^hps_"),
                CallbackQueryHandler(back_to_installation_type_selection, pattern="^back_to_installation_type_selection$") # Add back button
            ],
            REQUESTING_OBJECT_TYPE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, request_object_type),
                CallbackQueryHandler(back_to_heating_system_selection, pattern="^back_to_heating_system_selection$"), # Back from object type to heating/hp choice
                CallbackQueryHandler(back_to_heat_pump_subtype_selection, pattern="^back_to_heat_pump_subtype_selection$") # Back from object type to heating/hp choice
            ],
            REQUESTING_SURFACE_AREA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, request_surface_area),
                CallbackQueryHandler(confirm_details, pattern="^back_to_confirm_details$") # Placeholder for going back
            ],
            REQUESTING_NUM_FLOORS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, request_num_floors),
                CallbackQueryHandler(confirm_details, pattern="^back_to_confirm_details$") # Placeholder for going back
            ],
            REQUESTING_SKETCH: [
                MessageHandler(filters.PHOTO | filters.Document.ALL & ~filters.COMMAND | filters.TEXT & ~filters.COMMAND, request_sketch),
                CallbackQueryHandler(confirm_details, pattern="^back_to_confirm_details$") # Placeholder for going back
            ],
            REQUESTING_CONTACT_INFO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, request_contact_info),
                CallbackQueryHandler(confirm_details, pattern="^back_to_confirm_details$") # Placeholder for going back
            ],
            REQUESTING_EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, request_email),
                CallbackQueryHandler(confirm_details, pattern="^back_to_confirm_details$") # Placeholder for going back
            ],
            CONFIRMING_DETAILS: [
                CallbackQueryHandler(final_confirm, pattern="^confirm_"),
                CallbackQueryHandler(request_object_type, pattern="^back_to_object_type$"), # Go back from confirmation to object type
            ],
            SHOWING_CONTACT_INFO: [
                CallbackQueryHandler(back_to_main_menu, pattern="^back_to_main_menu$")
            ]
        },
        fallbacks=[CommandHandler("start", start)],
    )

    application.add_handler(conv_handler)
    # This bot runs in polling mode
    logger.info("Pokrećem bota u lokalnom modu (polling)...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()