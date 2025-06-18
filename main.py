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
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown
import yagmail

# Učitavanje promenljivih okruženja iz .env fajla (ako postoji)
# Ovo je prvenstveno za lokalno testiranje. Render automatski učitava environment variables.
from dotenv import load_dotenv
load_dotenv()

# Postavke logovanja
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- GLOBALNE VARIJABLE I KONSTANTE ---

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 8080))

# Environment varijable za slanje emaila (OVO MORA BITI NA RENDERU!)
SMTP_EMAIL_USER = os.getenv("SMTP_EMAIL_USER") # E-mail adresa sa koje saljete
SMTP_EMAIL_PASSWORD = os.getenv("SMTP_EMAIL_PASSWORD") # Lozinka ili app-specific password za taj e-mail (App Password za Gmail!)
MY_BCC_EMAIL = os.getenv("MY_BCC_EMAIL", "banjooo85@gmail.com") # Vas email

# Rečnik za višejezične poruke
MESSAGES = {
    "welcome_initial": { # Poruka pre izbora jezika
        "sr": "Dobrodošli! Molimo izaberite jezik:",
        "en": "Welcome! Please choose your language:",
        "ru": "Добро пожаловать! Пожалуйста, выберите язык:",
    },
    "language_selected": {
        "sr": "Odabran jezik: Srpski",
        "en": "Language selected: English",
        "ru": "Выбран язык: Русский",
    },
    "choose_country": {
        "sr": "Molimo izaberite zemlju:",
        "en": "Please choose a country:",
        "ru": "Пожалуйста, выберите страну:",
    },
    "country_selected": {
        "sr": "Odabrana zemlja: ",
        "en": "Selected country: ",
        "ru": "Выбрана страна: ",
    },
    "choose_main_installation_type": {
        "sr": "Sada izaberite vrstu instalacije:",
        "en": "Now choose the type of installation:",
        "ru": "Теперь выберите тип установки:",
    },
    "contractor_info": {
        "sr": "*Izvođač radova:*",
        "en": "*Contractor:*",
        "ru": "*Подрядчик:*",
    },
    "choose_heating_type": {
        "sr": "Molimo izaberite vrstu grejne instalacije:",
        "en": "Please choose the type of heating installation:",
        "ru": "Пожалуйста, выберите тип отопительной установки:",
    },
    "choose_hp_type": {
        "sr": "Molimo izaberite vrstu toplotne pumpe:",
        "en": "Please choose the type of heat pump:",
        "ru": "Пожалуйста, выберите тип теплового насоса:",
    },
    "enter_area": {
        "sr": "Molimo unesite površinu objekta u m²:",
        "en": "Please enter the object's area in m²:",
        "ru": "Пожалуйста, введите площадь объекта в м²:",
    },
    "invalid_area": {
        "sr": "Molimo unesite validan broj za površinu.",
        "en": "Please enter a valid number for the area.",
        "ru": "Пожалуйста, введите корректное число для площади.",
    },
    "enter_floors": {
        "sr": "Molimo unesite spratnost objekta (npr. P+1, P+2+Pk):",
        "en": "Please enter the number of floors (e.g., G+1, G+2+Attic):",
        "ru": "Пожалуйста, введите количество этажей объекта (например, 1+1, 1+2+чердак):",
    },
    "enter_object_type": {
        "sr": "Molimo unesite vrstu objekta (npr. kuća, stan, poslovni prostor):",
        "en": "Please enter the object type (e.g., house, apartment, commercial space):",
        "ru": "Пожалуйста, введите тип объекта (например, дом, квартира, коммерческое помещение):",
    },
    "send_sketch_question": {
        "sr": "Da li želite da pošaljete skicu?",
        "en": "Do you want to send a sketch?",
        "ru": "Хотите отправить эскиз?",
    },
    "send_sketch_yes": {
        "sr": "Molimo pošaljite skicu kao fotografiju.",
        "en": "Please send the sketch as a photo.",
        "ru": "Пожалуйста, отправьте эскиз в виде фотографии.",
    },
    "send_sketch_no": {
        "sr": "U redu, nećete slati skicu.",
        "en": "Okay, you won't be sending a sketch.",
        "ru": "Хорошо, вы не будете отправлять эскиз.",
    },
    "sketch_received": {
        "sr": "Hvala, skica je primljena.",
        "en": "Thank you, the sketch has been received.",
        "ru": "Спасибо, эскиз получен.",
    },
    "unexpected_photo": {
        "sr": "Trenutno ne očekujem fotografije.",
        "en": "I'm not expecting photos at the moment.",
        "ru": "В данный момент я не ожидаю фотографий.",
    },
    "summary_title": {
        "sr": "*Pregled vašeg upita:*",
        "en": "*Overview of your inquiry:*",
        "ru": "*Обзор вашего запроса:*",
    },
    "confirm_inquiry": {
        "sr": "Molimo potvrdite podatke pre slanja upita.",
        "en": "Please confirm the data before submitting the inquiry.",
        "ru": "Пожалуйста, подтвердите данные перед отправкой запроса.",
    },
    "send_inquiry_button": {
        "sr": "Pošalji upit",
        "en": "Send Inquiry",
        "ru": "Отправить запрос",
    },
    "try_again_button": {
        "sr": "Ponovi",
        "en": "Try Again",
        "ru": "Повторить",
    },
    "inquiry_sent_success": {
        "sr": "Hvala! Vaš upit je uspešno poslat {izvodjac_ime}\\. Uskoro ćete biti kontaktirani\\.",
        "en": "Thank you! Your inquiry has been successfully sent to {izvodjac_ime}\\. You will be contacted soon\\.",
        "ru": "Спасибо! Ваш запрос успешно отправлен {izvodjac_ime}\\. С вами свяжутся в ближайшее время\\.",
    },
    "inquiry_sent_error": {
        "sr": "Došlo je do greške prilikom slanja upita: `{error_message}` Molimo pokušajte ponovo kasnije\\.",
        "en": "An error occurred while sending the inquiry: `{error_message}` Please try again later\\.",
        "ru": "Произошла ошибка при отправке запроса: `{error_message}` Пожалуйста, попробуйте еще раз позже\\.",
    },
    "restart_message": {
        "sr": "U redu, molimo ponovite unos od početka sa /start.",
        "en": "Okay, please restart the input from the beginning with /start.",
        "ru": "Хорошо, пожалуйста, начните ввод сначала с /start.",
    },
    "error_contractor_data": {
        "sr": "Došlo je do greške pri pronalaženju podataka za izvođača.",
        "en": "An error occurred while retrieving contractor data.",
        "ru": "Произошла ошибка при получении данных подрядчика.",
    },
    "partner_info_title": {
        "sr": "*Informacije o partneru za toplotne pumpe:*",
        "en": "*Heat pump partner information:*",
        "ru": "*Информация о партнере по тепловым насосам:*",
    },
    "partner_info_unavailable": {
        "sr": "*Informacije o partneru za toplotne pumpe nisu dostupne*",
        "en": "*Heat pump partner information is not available*",
        "ru": "*Информация о партнере по тепловым насосам недоступна*",
    },
}


# Globalni podaci o izvođačima i Microma/Instal M (FIKSIRANO U KODU)
IZVODJACI = {
    "rs": {
        "ime": "Igor Bošković",
        "kontakt_email": "boskovicigor83@gmail.com",
        "kontakt_info_display": "Email: boskovicigor83@gmail.com, Telefon: +381 60 3932566, Telegram: @IgorNS1983",
        "options_heating": { # Grejna instalacija opcije za Srbiju
            "Radijatori": "radijatori",
            "Fancoil-i": "fancoils",
            "Podno grejanje": "underfloor",
            "Podno grejanje + Fancoil-i": "underfloor_fancoils",
            "Komplet ponuda sa toplotnom pumpom": "complete_tp",
        },
        "options_hp": { # Toplotna pumpa opcije za Srbiju
            "Voda-voda": "water_water",
            "Vazduh-voda": "air_water",
        },
        "hp_partner_info": { # Podaci za Microma
            "Firma": "Microma",
            "Kontakt osoba": "Borislav Dakić",
            "Email": "office@microma.rs",
            "Telefon": "+381 63 582068",
            "Web sajt": "https://microma.rs",
        },
    },
    "me": {
        "ime": "Instal M",
        "kontakt_email": "office@instalm.me",
        "kontakt_info_display": "Email: office@instalm.me, Telefon: +382 67 423 237, Telegram: @ivanmujovic",
        "options_heating": { # Grejna instalacija opcije za Crnu Goru
            "Radijatori": "radijatori",
            "Fancoil-i": "fancoils",
            "Podno grejanje": "underfloor",
            "Podno grejanje + Fancoil-i": "underfloor_fancoils",
            "Komplet ponuda sa toplotnom pumpom": "complete_tp",
        },
        "options_hp": { # Toplotna pumpa opcije za Crnu Goru
            "Vazduh-voda": "air_water", # Samo vazduh-voda za CG
        },
        "hp_partner_info": { # Podaci za Instal M
            "Firma": "Instal M",
            "Kontakt osoba": "Ivan Mujović",
            "Email": "office@instalm.me",
            "Telefon": "+382 67 423 237",
            "Telegram": "@ivanmujovic",
        },
    },
}

# Države za izbor (Samo Srbija i Crna Gora)
COUNTRIES = {
    "Srbija": "rs",
    "Crna Gora": "me",
}

# Tipovi instalacija za glavni meni
INSTALLATION_OPTIONS_MENU = {
    "Grejna instalacija": "heating",
    "Toplotna pumpa": "heat_pump",
}

# --- FUNKCIJE RUKOVAOCA ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Šalje poruku dobrodošlice i nudi izbor jezika."""
    keyboard = [
        [
            InlineKeyboardButton("Srpski", callback_data="lang_sr"),
            InlineKeyboardButton("English", callback_data="lang_en"),
            InlineKeyboardButton("Русский", callback_data="lang_ru"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    # Prikaz svih poruka za dobrodošlicu, pošto jezik jos nije izabran
    await update.message.reply_text(
        f"{MESSAGES['welcome_initial']['sr']}\n"
        f"{MESSAGES['welcome_initial']['en']}\n"
        f"{MESSAGES['welcome_initial']['ru']}",
        reply_markup=reply_markup
    )
    context.user_data["current_state"] = "selecting_language"

async def select_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    lang = query.data.split("_")[1]
    context.user_data["language"] = lang

    await query.edit_message_text(MESSAGES["language_selected"].get(lang, MESSAGES["language_selected"]["sr"]))
    await choose_country(update, context)

async def choose_country(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Nudi izbor zemlje."""
    current_lang = context.user_data.get('language', 'sr') # Default na srpski
    keyboard = []
    for country_name_sr, country_code in COUNTRIES.items():
        # Trenutno su nazivi zemalja na srpskom, što je OK
        keyboard.append([InlineKeyboardButton(country_name_sr, callback_data=f"country_{country_code}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.reply_text(MESSAGES["choose_country"].get(current_lang, MESSAGES["choose_country"]["sr"]), reply_markup=reply_markup)
    context.user_data["current_state"] = "selecting_country"

async def select_country(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    country_code = query.data.split("_")[1]
    
    country_name = next((name for name, code in COUNTRIES.items() if code == country_code), "Nepoznato")

    context.user_data["country"] = country_name
    context.user_data["country_code"] = country_code # Dodajemo country_code za lakše reference
    
    current_lang = context.user_data.get('language', 'sr')
    await query.edit_message_text(f"{MESSAGES['country_selected'].get(current_lang, MESSAGES['country_selected']['sr'])} {country_name}.")

    # Sada nudimo izbor za "Grejna instalacija" i "Toplotna pumpa"
    keyboard = []
    for type_name, type_code in INSTALLATION_OPTIONS_MENU.items():
        # Opcije menija su trenutno na srpskom
        keyboard.append([InlineKeyboardButton(type_name, callback_data=f"main_install_{type_code}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.reply_text(MESSAGES["choose_main_installation_type"].get(current_lang, MESSAGES["choose_main_installation_type"]["sr"]), reply_markup=reply_markup)
    context.user_data["current_state"] = "selecting_main_installation_type"

async def select_main_installation_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    main_type_code = query.data.split("_")[2] # main_install_<type_code>
    
    context.user_data["main_installation_type"] = main_type_code
    
    country_code = context.user_data.get("country_code")
    izvodjac_data = IZVODJACI.get(country_code)

    if not izvodjac_data:
        current_lang = context.user_data.get('language', 'sr')
        await query.edit_message_text(MESSAGES["error_contractor_data"].get(current_lang, MESSAGES["error_contractor_data"]["sr"]))
        context.user_data.clear()
        return

    # Prikaz podataka o izvođaču radova
    current_lang = context.user_data.get('language', 'sr')
    izvodjac_ime = escape_markdown(izvodjac_data["ime"], version=2)
    izvodjac_kontakt = escape_markdown(izvodjac_data["kontakt_info_display"], version=2)
    
    message_text = (
        f"{MESSAGES['contractor_info'].get(current_lang, MESSAGES['contractor_info']['sr'])}\n"
        f"Ime: `{izvodjac_ime}`\n"
        f"Kontakt: `{izvodjac_kontakt}`\n\n"
    )
    
    # Koristimo reply_text jer smo već editovali prethodnu poruku
    await query.message.reply_text(message_text, parse_mode=ParseMode.MARKDOWN_V2)

    if main_type_code == "heating":
        heating_options = izvodjac_data["options_heating"]
        keyboard = []
        for name, code in heating_options.items():
            keyboard.append([InlineKeyboardButton(name, callback_data=f"heating_option_{code}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(MESSAGES["choose_heating_type"].get(current_lang, MESSAGES["choose_heating_type"]["sr"]), reply_markup=reply_markup)
        context.user_data["current_state"] = "selecting_heating_option"

    elif main_type_code == "heat_pump":
        hp_options = izvodjac_data["options_hp"]
        keyboard = []
        for name, code in hp_options.items():
            keyboard.append([InlineKeyboardButton(name, callback_data=f"hp_option_{code}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(MESSAGES["choose_hp_type"].get(current_lang, MESSAGES["choose_hp_type"]["sr"]), reply_markup=reply_markup)
        context.user_data["current_state"] = "selecting_hp_option"


async def handle_heating_option_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    selected_option_code = query.data.split("_")[2] # heating_option_<code_value>
    
    context.user_data["selected_heating_option"] = selected_option_code
    
    # Prikaz potvrde izbora, možete prevesti
    await query.edit_message_text(f"Odabrali ste: {selected_option_code.replace('_', ' ').title()}.")

    # Početak prikupljanja podataka o objektu
    current_lang = context.user_data.get('language', 'sr')
    await query.message.reply_text(MESSAGES["enter_area"].get(current_lang, MESSAGES["enter_area"]["sr"]))
    context.user_data["current_state"] = "awaiting_area"

async def handle_hp_option_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    selected_hp_option_code = query.data.split("_")[2] # hp_option_<code_value>
    
    context.user_data["selected_hp_option"] = selected_hp_option_code
    
    # Prikaz potvrde izbora, možete prevesti
    await query.edit_message_text(f"Odabrali ste: {selected_hp_option_code.replace('_', ' ').title()}.")

    # Za toplotne pumpe, prelazimo odmah na sumiranje i slanje upita
    # Ako su potrebni dodatni podaci o objektu, tok treba da se proširi slično kao za grejanje.
    await summarize_and_send_inquiry(update, context)


async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    current_state = context.user_data.get("current_state")
    user_input = update.message.text
    current_lang = context.user_data.get('language', 'sr')

    if current_state == "awaiting_area":
        try:
            area = float(user_input)
            context.user_data["area"] = area
            await update.message.reply_text(MESSAGES["enter_floors"].get(current_lang, MESSAGES["enter_floors"]["sr"]))
            context.user_data["current_state"] = "awaiting_floors"
        except ValueError:
            await update.message.reply_text(MESSAGES["invalid_area"].get(current_lang, MESSAGES["invalid_area"]["sr"]))
    elif current_state == "awaiting_floors":
        context.user_data["floors"] = user_input
        await update.message.reply_text(MESSAGES["enter_object_type"].get(current_lang, MESSAGES["enter_object_type"]["sr"]))
        context.user_data["current_state"] = "awaiting_object_type"
    elif current_state == "awaiting_object_type":
        context.user_data["object_type"] = user_input
        keyboard = [
            [
                InlineKeyboardButton("Da", callback_data="send_sketch_yes"), # Prevesti
                InlineKeyboardButton("Ne", callback_data="send_sketch_no"), # Prevesti
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(MESSAGES["send_sketch_question"].get(current_lang, MESSAGES["send_sketch_question"]["sr"]), reply_markup=reply_markup)
        context.user_data["current_state"] = "awaiting_sketch_choice"
    else:
        # Generic fallback for unhandled text input
        await update.message.reply_text("Nisam razumeo vaš unos. Molimo koristite tastere za navigaciju ili pokrenite /start.")

async def handle_sketch_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    choice = query.data.split("_")[2] # send_sketch_<choice>
    current_lang = context.user_data.get('language', 'sr')

    if choice == "yes":
        await query.edit_message_text(MESSAGES["send_sketch_yes"].get(current_lang, MESSAGES["send_sketch_yes"]["sr"]))
        context.user_data["current_state"] = "awaiting_sketch_upload"
    else:
        context.user_data["sketch_uploaded"] = False # Nije poslao skicu
        await query.edit_message_text(MESSAGES["send_sketch_no"].get(current_lang, MESSAGES["send_sketch_no"]["sr"]))
        await summarize_and_send_inquiry(update, context) # Idemo na sumiranje i slanje upita

async def handle_photo_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    current_lang = context.user_data.get('language', 'sr')
    if context.user_data.get("current_state") == "awaiting_sketch_upload":
        photo_file = update.message.photo[-1].file_id # Uzmite najveću rezoluciju
        context.user_data["sketch_file_id"] = photo_file
        context.user_data["sketch_uploaded"] = True
        await update.message.reply_text(MESSAGES["sketch_received"].get(current_lang, MESSAGES["sketch_received"]["sr"]))
        await summarize_and_send_inquiry(update, context) # Idemo na sumiranje i slanje upita
    else:
        await update.message.reply_text(MESSAGES["unexpected_photo"].get(current_lang, MESSAGES["unexpected_photo"]["sr"]))

async def summarize_and_send_inquiry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_data = context.user_data
    
    current_lang = user_data.get('language', 'sr')
    country_code = user_data.get("country_code")
    izvodjac_data = IZVODJACI.get(country_code)

    summary_text_parts = [
        f"{MESSAGES['summary_title'].get(current_lang, MESSAGES['summary_title']['sr'])}\n",
        f"Jezik: `{escape_markdown(user_data.get('language', 'N/A').upper(), version=2)}`",
        f"Zemlja: `{escape_markdown(user_data.get('country', 'N/A'), version=2)}`",
        f"Glavni tip instalacije: `{escape_markdown(user_data.get('main_installation_type', 'N/A'), version=2)}`",
    ]

    if user_data.get('main_installation_type') == 'heating':
        summary_text_parts.append(f"Tip grejne instalacije: `{escape_markdown(user_data.get('selected_heating_option', 'N/A'), version=2)}`")
        summary_text_parts.append(f"Površina objekta: `{escape_markdown(str(user_data.get('area', 'N/A')), version=2)}` m²")
        summary_text_parts.append(f"Spratnost objekta: `{escape_markdown(user_data.get('floors', 'N/A'), version=2)}`")
        summary_text_parts.append(f"Vrsta objekta: `{escape_markdown(user_data.get('object_type', 'N/A'), version=2)}`")
        if user_data.get("sketch_uploaded"):
            summary_text_parts.append(f"Skica: Da (biće priložena)") # Prevesti
        else:
            summary_text_parts.append(f"Skica: Ne") # Prevesti

    elif user_data.get('main_installation_type') == 'heat_pump':
        summary_text_parts.append(f"Tip toplotne pumpe: `{escape_markdown(user_data.get('selected_hp_option', 'N/A'), version=2)}`")

        hp_partner_info = izvodjac_data.get("hp_partner_info", {})
        if hp_partner_info:
            summary_text_parts.append(f"\n{MESSAGES['partner_info_title'].get(current_lang, MESSAGES['partner_info_title']['sr'])}")
            for key, value in hp_partner_info.items():
                summary_text_parts.append(f"{key}: `{escape_markdown(str(value), version=2)}`")
        else:
            summary_text_parts.append(f"\n{MESSAGES['partner_info_unavailable'].get(current_lang, MESSAGES['partner_info_unavailable']['sr'])}")

    summary_text_parts.append(f"\n{MESSAGES['confirm_inquiry'].get(current_lang, MESSAGES['confirm_inquiry']['sr'])}")
    
    summary_text = "\n".join(summary_text_parts)

    keyboard = [
        [
            InlineKeyboardButton(MESSAGES["send_inquiry_button"].get(current_lang, MESSAGES["send_inquiry_button"]["sr"]), callback_data="final_send_inquiry"),
            InlineKeyboardButton(MESSAGES["try_again_button"].get(current_lang, MESSAGES["try_again_button"]["sr"]), callback_data="confirm_no"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Koristite edit_message_text ako je ovo odgovor na taster, inace reply_text
    if update.callback_query:
        await update.callback_query.message.reply_text(summary_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2)
    else: # Ako dolazi od handle_photo_input
        await update.message.reply_text(summary_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2)
    
    context.user_data["current_state"] = "awaiting_final_confirmation"


async def handle_final_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    current_lang = context.user_data.get('language', 'sr')

    if query.data == "final_send_inquiry":
        user_data = context.user_data
        country_code = user_data.get("country_code")
        izvodjac_data = IZVODJACI.get(country_code)
        
        recipient_email = izvodjac_data["kontakt_email"]
        
        email_subject = f"Novi upit za instalacije - {user_data.get('country', 'N/A')} ({user_data.get('language', 'N/A').upper()})"
        email_body = (
            f"Primljen je novi upit putem Telegram bota:\n\n"
            f"Jezik: {user_data.get('language', 'N/A').upper()}\n"
            f"Zemlja: {user_data.get('country', 'N/A')}\n"
            f"Glavni tip instalacije: {user_data.get('main_installation_type', 'N/A')}\n"
        )
        if user_data.get('main_installation_type') == 'heating':
            email_body += f"Tip grejne instalacije: {user_data.get('selected_heating_option', 'N/A')}\n"
            email_body += f"Površina objekta: {user_data.get('area', 'N/A')} m²\n"
            email_body += f"Spratnost objekta: {user_data.get('floors', 'N/A')}\n"
            email_body += f"Vrsta objekta: {user_data.get('object_type', 'N/A')}\n"
        elif user_data.get('main_installation_type') == 'heat_pump':
            email_body += f"Tip toplotne pumpe: {user_data.get('selected_hp_option', 'N/A')}\n"
            hp_partner_info = izvodjac_data.get("hp_partner_info", {})
            if hp_partner_info:
                email_body += "\nInformacije o partneru za toplotne pumpe:\n"
                for key, value in hp_partner_info.items():
                    email_body += f"{key}: {value}\n"

        attachments = []
        # Preuzmi skicu samo ako je poslana i ako je relevantno (za heating)
        if user_data.get('main_installation_type') == 'heating' and user_data.get("sketch_uploaded") and user_data.get("sketch_file_id"):
            file_id = user_data["sketch_file_id"]
            file = await context.bot.get_file(file_id)
            file_path = f"/tmp/skica_{file_id}.jpg" # Koristite /tmp za privremene fajlove na Renderu
            try:
                await file.download_to_drive(file_path)
                attachments.append(file_path)
                email_body += f"Priložena skica: Da\n"
            except Exception as e:
                logger.error(f"Failed to download sketch: {e}")
                email_body += f"Priložena skica: Greška pri preuzimanju ({e})\n"
        else:
            email_body += f"Priložena skica: Ne\n"
        
        # Provera da li su potrebne email varijable postavljene
        if not SMTP_EMAIL_USER or not SMTP_EMAIL_PASSWORD:
            error_msg = "Greška: E-mail korisničko ime ili lozinka (SMTP_EMAIL_USER/PASSWORD) nisu postavljeni na Renderu."
            logger.error(error_msg)
            await query.edit_message_text(escape_markdown(error_msg, version=2), parse_mode=ParseMode.MARKDOWN_V2)
            context.user_data.clear()
            return

        try:
            yg = yagmail.SMTP(user=SMTP_EMAIL_USER, password=SMTP_EMAIL_PASSWORD)
            yg.send(
                to=recipient_email,
                subject=email_subject,
                contents=email_body,
                attachments=attachments,
                bcc=[MY_BCC_EMAIL]
            )
            final_message = MESSAGES["inquiry_sent_success"].get(current_lang, MESSAGES["inquiry_sent_success"]["sr"]).format(izvodjac_ime=izvodjac_data['ime'])
            await query.edit_message_text(final_message, parse_mode=ParseMode.MARKDOWN_V2)
            logger.info(f"Email sent to {recipient_email} with BCC to {MY_BCC_EMAIL}")
        except Exception as e:
            error_message = str(e)
            final_message = MESSAGES["inquiry_sent_error"].get(current_lang, MESSAGES["inquiry_sent_error"]["sr"]).format(error_message=escape_markdown(error_message, version=2))
            await query.edit_message_text(final_message, parse_mode=ParseMode.MARKDOWN_V2)
            logger.error(f"Failed to send email: {e}")
        
        # Obrišite privremene fajlove ako postoje
        for att in attachments:
            if os.path.exists(att):
                os.remove(att)
        
        context.user_data.clear() # Resetuj korisničke podatke

    else: # Confirm No / Ponovi
        await query.edit_message_text(MESSAGES["restart_message"].get(current_lang, MESSAGES["restart_message"]["sr"]))
        context.user_data.clear()

# --- GLAVNA FUNKCIJA (main) ---

def main() -> None:
    """Pokreće bota."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set.")
        exit(1)
    if not WEBHOOK_URL:
        logger.error("WEBHOOK_URL environment variable not set.")
        exit(1)
    # Provera za email credentials
    if not SMTP_EMAIL_USER:
        logger.warning("SMTP_EMAIL_USER environment variable not set. Email sending may fail.")
    if not SMTP_EMAIL_PASSWORD:
        logger.warning("SMTP_EMAIL_PASSWORD environment variable not set. Email sending may fail.")

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Handleri
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(select_language, pattern="^lang_"))
    application.add_handler(CallbackQueryHandler(select_country, pattern="^country_"))
    application.add_handler(CallbackQueryHandler(select_main_installation_type, pattern="^main_install_"))
    application.add_handler(CallbackQueryHandler(handle_heating_option_selection, pattern="^heating_option_"))
    application.add_handler(CallbackQueryHandler(handle_hp_option_selection, pattern="^hp_option_"))
    application.add_handler(CallbackQueryHandler(handle_sketch_choice, pattern="^send_sketch_"))
    application.add_handler(CallbackQueryHandler(handle_final_confirmation, pattern="^final_send_inquiry|confirm_no"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo_input))

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