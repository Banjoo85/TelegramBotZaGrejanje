import os
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler,
)
import yagmail

# Učitavanje .env fajla za lokalni razvoj (na Renderu neće biti potrebno, ali ne smeta)
load_dotenv()

# Konfiguracija logovanja
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Environment varijable (obavezno ih postavite na Render.com) ---
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_TELEGRAM_ID = os.getenv("TELEGRAM_ADMIN_ID") # Vaš Telegram ID za admin notifikacije (opciono, ali preporučeno)

# Email kredencijali za slanje upita
# Preporučuje se kreiranje posebnog email naloga za bota sa generisanom lozinkom za aplikaciju (App Password)
EMAIL_SENDER_ADDRESS = os.getenv("EMAIL_SENDER_ADDRESS")
EMAIL_SENDER_PASSWORD = os.getenv("EMAIL_SENDER_PASSWORD") # Koristite App Password ako je u pitanju Gmail

# Vaš email za BCC kopije
BCC_EMAIL = "banjooo85@gmail.com"

# --- Podaci o izvođačima i firmama ---
# Definisanje ovih podataka kao Python rečnika čini ih lakšim za održavanje
CONTRACTORS = {
    "srbija": {
        "name": "Igor Bošković",
        "email": "boskovicigor83@gmail.com",
        "phone": "+381 60 3932566",
        "telegram": "@IgorNS1983"
    },
    "crnagora": {
        "name": "Instal M (Ivan Mujović)",
        "email": "office@instalm.me",
        "phone": "+382 67 423 237",
        "telegram": "@ivanmujovic"
    }
}

MICROMA = {
    "name": "Microma",
    "contact": "Borislav Dakić",
    "email": "office@microma.rs",
    "phone": "+381 63 582068",
    "website": "https://microma.rs"
}

# --- Stanja konverzacije ---
(
    SELECT_LANGUAGE,
    SELECT_COUNTRY,
    SELECT_SERVICE,
    SELECT_HEATING_TYPE,
    ENTER_SURFACE,
    ENTER_FLOORS,
    SELECT_OBJECT_TYPE,
    ASK_FOR_SKETCH,
    RECEIVE_SKETCH,
    ENTER_CONTACT_INFO,
    SELECT_HP_TYPE,
    FINAL_CONFIRMATION
) = range(12)

# --- Tekstovi poruka na različitim jezicima ---
# --- Tekstovi poruka na različitim jezicima ---
MESSAGES = {
    "sr": { # Promenjeno iz "srpski" u "sr"
        "welcome": "Dobrodošli! Molimo izaberite jezik:\nWelcome! Please choose a language:\nДобро пожаловать! Пожалуйста, выберите язык:",
        "choose_language": "Molimo izaberite jezik:",
        "choose_country": "Molimo izaberite zemlju:",
        "country_srbija": "Srbija",
        "country_crnagora": "Crna Gora",
        "select_service": "Šta vas zanima?",
        "service_heating": "Grejna instalacija",
        "service_hp": "Toplotna pumpa",
        "srbija_contractor_info_heating": (
            f"Za grejne instalacije u Srbiji, vaš izvođač radova je {CONTRACTORS['srbija']['name']}.\n"
            f"Kontakt: Email: {CONTRACTORS['srbija']['email']}, Telefon: {CONTRACTORS['srbija']['phone']}"
            f" (Telegram: {CONTRACTORS['srbija']['telegram']})."
        ),
        "crnagora_contractor_info_heating": (
            f"Za grejne instalacije u Crnoj Gori, vaš izvođač radova je {CONTRACTORS['crnagora']['name']}.\n"
            f"Kontakt: Email: {CONTRACTORS['crnagora']['email']}, Telefon: {CONTRACTORS['crnagora']['phone']}"
            f" (Telegram: {CONTRACTORS['crnagora']['telegram']})."
        ),
        "srbija_microma_info_hp": (
            f"Za toplotne pumpe u Srbiji, partner je firma {MICROMA['name']}.\n"
            f"Kontakt osoba: {MICROMA['contact']}, Email: {MICROMA['email']}, Telefon: {MICROMA['phone']}.\n"
            f"Više informacija možete pronaći na: {MICROMA['website']}."
        ),
        "crnagora_instalm_info_hp": (
            f"Za toplotne pumpe u Crnoj Gori, partner je firma {CONTRACTORS['crnagora']['name']}.\n"
            f"Kontakt: Email: {CONTRACTORS['crnagora']['email']}, Telefon: {CONTRACTORS['crnagora']['phone']}"
            f" (Telegram: {CONTRACTORS['crnagora']['telegram']})."
        ),
        "select_heating_type": "Molimo izaberite tip grejne instalacije:",
        "heating_radiators": "Radijatori",
        "heating_fancoil": "Fancoil-i",
        "heating_underfloor": "Podno grejanje",
        "heating_underfloor_fancoil": "Podno grejanje + Fancoil-i",
        "heating_complete_hp": "Komplet ponuda sa toplotnom pumpom",
        "enter_surface": "Molimo unesite površinu objekta u kvadratnim metrima (samo broj, npr. 120):",
        "surface_invalid": "Neispravan unos. Molimo unesite samo broj za površinu objekta u kvadratnim metrima.",
        "enter_floors": "Molimo unesite broj spratova objekta (samo broj, npr. 2):",
        "floors_invalid": "Neispravan unos. Molimo unesite samo broj za broj spratova.",
        "select_object_type": "Koja je vrsta objekta?",
        "object_house": "Kuća",
        "object_apartment": "Stan",
        "object_commercial": "Poslovni prostor",
        "object_other": "Drugo",
        "ask_for_sketch": "Da li želite da priložite skicu objekta?",
        "yes": "Da",
        "no": "Ne",
        "upload_sketch": "Molimo priložite skicu (sliku ili dokument).",
        "skip_sketch": "Preskačem prilaganje skice.",
        "enter_contact_info": (
            "Molimo unesite vaš kontakt telefon i/ili email adresu, kako bismo vas lakše kontaktirali.\n"
            "(Npr: +3816x xxx xxxx, mejl@primer.com)"
        ),
        "select_hp_type_srbija": "Molimo izaberite tip toplotne pumpe:",
        "hp_water_water": "Voda-Voda",
        "hp_air_water": "Vazduh-Voda",
        "select_hp_type_crnagora": "Molimo izaberite tip toplotne pumpe:",
        "thank_you_heating": (
            "Hvala! Vaš upit za grejnu instalaciju je poslat."
            " Očekujte da vas izvođač radova kontaktira uskoro."
        ),
        "thank_you_hp": (
            "Hvala! Vaš upit za toplotnu pumpu je poslat."
            " Očekujte da vas kontaktiraju predstavnici firme."
        ),
        "error_sending_email": "Došlo je do greške prilikom slanja upita. Molimo pokušajte ponovo kasnije.",
        "something_went_wrong": "Došlo je do greške. Molimo pokušajte ponovo sa /start.",
        "choose_option": "Molimo izaberite jednu od ponuđenih opcija.",
        "start_over": "Započnite ponovo sa /start.",
    },
    "en": { # Promenjeno iz "english" u "en"
        "welcome": "Dobrodošli! Molimo izaberite jezik:\nWelcome! Please choose a language:\nДобро пожаловать! Пожалуйста, выберите язык:",
        "choose_language": "Please choose a language:",
        "choose_country": "Please choose a country:",
        "country_srbija": "Serbia",
        "country_crnagora": "Montenegro",
        "select_service": "What are you interested in?",
        "service_heating": "Heating Installation",
        "service_hp": "Heat Pump",
        "srbija_contractor_info_heating": (
            f"For heating installations in Serbia, your contractor is {CONTRACTORS['srbija']['name']}.\n"
            f"Contact: Email: {CONTRACTORS['srbija']['email']}, Phone: {CONTRACTORS['srbija']['phone']}"
            f" (Telegram: {CONTRACTORS['srbija']['telegram']})."
        ),
        "crnagora_contractor_info_heating": (
            f"For heating installations in Montenegro, your contractor is {CONTRACTORS['crnagora']['name']}.\n"
            f"Contact: Email: {CONTRACTORS['crnagora']['email']}, Phone: {CONTRACTORS['crnagora']['phone']}"
            f" (Telegram: {CONTRACTORS['crnagora']['telegram']})."
        ),
        "srbija_microma_info_hp": (
            f"For heat pumps in Serbia, our partner is {MICROMA['name']}.\n"
            f"Contact person: {MICROMA['contact']}, Email: {MICROMA['email']}, Phone: {MICROMA['phone']}.\n"
            f"More info: {MICROMA['website']}."
        ),
        "crnagora_instalm_info_hp": (
            f"For heat pumps in Montenegro, our partner is {CONTRACTORS['crnagora']['name']}.\n"
            f"Contact: Email: {CONTRACTORS['crnagora']['email']}, Phone: {CONTRACTORS['crnagora']['phone']}"
            f" (Telegram: {CONTRACTORS['crnagora']['telegram']})."
        ),
        "select_heating_type": "Please select the type of heating installation:",
        "heating_radiators": "Radiators",
        "heating_fancoil": "Fancoils",
        "heating_underfloor": "Underfloor Heating",
        "heating_underfloor_fancoil": "Underfloor Heating + Fancoils",
        "heating_complete_hp": "Complete offer with Heat Pump",
        "enter_surface": "Please enter the object's surface area in square meters (number only, e.g., 120):",
        "surface_invalid": "Invalid input. Please enter a number for the object's surface area in square meters.",
        "enter_floors": "Please enter the number of floors of the object (number only, e.g., 2):",
        "floors_invalid": "Invalid input. Please enter a number for the number of floors.",
        "select_object_type": "What is the type of the object?",
        "object_house": "House",
        "object_apartment": "Apartment",
        "object_commercial": "Commercial Space",
        "object_other": "Other",
        "ask_for_sketch": "Would you like to attach a sketch of the object?",
        "yes": "Yes",
        "no": "No",
        "upload_sketch": "Please attach the sketch (image or document).",
        "skip_sketch": "Skip attaching sketch.",
        "enter_contact_info": (
            "Please enter your contact phone number and/or email address, so we can contact you easily.\n"
            "(E.g.: +3816x xxx xxxx, email@example.com)"
        ),
        "select_hp_type_srbija": "Please select the heat pump type:",
        "hp_water_water": "Water-Water",
        "hp_air_water": "Air-Water",
        "select_hp_type_crnagora": "Please select the heat pump type:",
        "thank_you_heating": (
            "Thank you! Your heating installation inquiry has been sent."
            " The contractor will contact you soon."
        ),
        "thank_you_hp": (
            "Thank you! Your heat pump inquiry has been sent."
            " Company representatives will contact you soon."
        ),
        "error_sending_email": "An error occurred while sending the inquiry. Please try again later.",
        "something_went_wrong": "Something went wrong. Please try again with /start.",
        "choose_option": "Please choose one of the provided options.",
        "start_over": "Start over with /start.",
    },
    "ru": { # Promenjeno iz "russian" u "ru"
        "welcome": "Dobrodošli! Molimo izaberite jezik:\nWelcome! Please choose a language:\nДобро пожаловать! Пожалуйста, выберите язык:",
        "choose_language": "Пожалуйста, выберите язык:",
        "choose_country": "Пожалуйста, выберите страну:",
        "country_srbija": "Сербия",
        "country_crnagora": "Черногория",
        "select_service": "Что вас интересует?",
        "service_heating": "Система отопления",
        "service_hp": "Тепловой насос",
        "srbija_contractor_info_heating": (
            f"Для систем отопления в Сербии, ваш подрядчик - {CONTRACTORS['srbija']['name']}.\n"
            f"Контакты: Email: {CONTRACTORS['srbija']['email']}, Телефон: {CONTRACTORS['srbija']['phone']}"
            f" (Telegram: {CONTRACTORS['srbija']['telegram']})."
        ),
        "crnagora_contractor_info_heating": (
            f"Для систем отопления в Черногории, ваш подрядчик - {CONTRACTORS['crnagora']['name']}.\n"
            f"Контакты: Email: {CONTRACTORS['crnagora']['email']}, Телефон: {CONTRACTORS['crnagora']['phone']}"
            f" (Telegram: {CONTRACTORS['crnagora']['telegram']})."
        ),
        "srbija_microma_info_hp": (
            f"Для тепловых насосов в Сербии, наш партнер - компания {MICROMA['name']}.\n"
            f"Контактное лицо: {MICROMA['contact']}, Email: {MICROMA['email']}, Телефон: {MICROMA['phone']}.\n"
            f"Больше информации: {MICROMA['website']}."
        ),
        "crnagora_instalm_info_hp": (
            f"Для тепловых насосов в Черногории, наш партнер - компания {CONTRACTORS['crnagora']['name']}.\n"
            f"Контакты: Email: {CONTRACTORS['crnagora']['email']}, Телефон: {CONTRACTORS['crnagora']['phone']}"
            f" (Telegram: {CONTRACTORS['crnagora']['telegram']})."
        ),
        "select_heating_type": "Пожалуйста, выберите тип системы отопления:",
        "heating_radiators": "Радиаторы",
        "heating_fancoil": "Фанкойлы",
        "heating_underfloor": "Подогрев пола",
        "heating_underfloor_fancoil": "Подогрев пола + Фанкойлы",
        "heating_complete_hp": "Полное предложение с тепловым насосом",
        "enter_surface": "Пожалуйста, введите площадь объекта в квадратных метрах (только число, например, 120):",
        "surface_invalid": "Неверный ввод. Пожалуйста, введите только число для площади объекта в квадратных метрах.",
        "enter_floors": "Пожалуйста, введите количество этажей объекта (только число, например, 2):",
        "floors_invalid": "Неверный ввод. Пожалуйста, введите только число для количества этажей.",
        "select_object_type": "Какой тип объекта?",
        "object_house": "Дом",
        "object_apartment": "Квартира",
        "object_commercial": "Коммерческое помещение",
        "object_other": "Другое",
        "ask_for_sketch": "Вы хотите прикрепить эскиз объекта?",
        "yes": "Да",
        "no": "Нет",
        "upload_sketch": "Пожалуйста, прикрепите эскиз (изображение или документ).",
        "skip_sketch": "Пропустить прикрепление эскиза.",
        "enter_contact_info": (
            "Пожалуйста, введите ваш контактный телефон и/или адрес электронной почты, чтобы мы могли легко с вами связаться.\n"
            "(Например: +3816x xxx xxxx, email@example.com)"
        ),
        "select_hp_type_srbija": "Пожалуйста, выберите тип теплового насоса:",
        "hp_water_water": "Вода-Вода",
        "hp_air_water": "Воздух-Вода",
        "select_hp_type_crnagora": "Пожалуйста, выберите тип теплового насоса:",
        "thank_you_heating": (
            "Спасибо! Ваш запрос на систему отопления был отправлен."
            " Подрядчик свяжется с вами в ближайшее время."
        ),
        "thank_you_hp": (
            "Спасибо! Ваш запрос на тепловой насос был отправлен."
            " Представители компании свяжутся с вами в ближайшее время."
        ),
        "error_sending_email": "Произошла ошибка при отправке запроса. Пожалуйста, попробуйте еще раз позже.",
        "something_went_wrong": "Что-то пошло не так. Пожалуйста, попробуйте снова с /start.",
        "choose_option": "Пожалуйста, выберите один из предложенных вариантов.",
        "start_over": "Начать заново с /start.",
    }
}

# --- Komandni hendleri ---
async def start(update: Update, context):
    """Šalje pozdravnu poruku i traži izbor jezika."""
    keyboard = [
        [InlineKeyboardButton("Srpski", callback_data="lang_sr")],
        [InlineKeyboardButton("English", callback_data="lang_en")],
        [InlineKeyboardButton("Русский", callback_data="lang_ru")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(MESSAGES["srpski"]["welcome"], reply_markup=reply_markup)
    return SELECT_LANGUAGE

async def select_language(update: Update, context):
    """Hvata izbor jezika i traži izbor zemlje."""
    query = update.callback_query
    await query.answer()
    lang_code = query.data.split('_')[1] # 'sr', 'en', 'ru'
    
    # Sačuvajte izabrani jezik u korisničkom kontekstu
    context.user_data['language'] = lang_code
    
    keyboard = [
        [InlineKeyboardButton(MESSAGES[lang_code]["country_srbija"], callback_data="country_srbija")],
        [InlineKeyboardButton(MESSAGES[lang_code]["country_crnagora"], callback_data="country_crnagora")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=MESSAGES[lang_code]["choose_country"], reply_markup=reply_markup)
    return SELECT_COUNTRY

async def select_country(update: Update, context):
    """Hvata izbor zemlje i nudi izbor usluge (grejanje/toplotna pumpa)."""
    query = update.callback_query
    await query.answer()
    lang_code = context.user_data.get('language', 'srpski') # Podrazumevano srpski
    
    country = query.data.split('_')[1] # 'srbija', 'crnagora'
    context.user_data['country'] = country

    keyboard = [
        [InlineKeyboardButton(MESSAGES[lang_code]["service_heating"], callback_data="service_heating")],
        [InlineKeyboardButton(MESSAGES[lang_code]["service_hp"], callback_data="service_hp")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=MESSAGES[lang_code]["select_service"], reply_markup=reply_markup)
    return SELECT_SERVICE

async def select_service(update: Update, context):
    """Hvata izbor usluge i preusmerava."""
    query = update.callback_query
    await query.answer()
    lang_code = context.user_data.get('language', 'srpski')
    service = query.data.split('_')[1] # 'heating', 'hp'
    context.user_data['service'] = service

    if service == "heating":
        country = context.user_data['country']
        if country == "srbija":
            await query.edit_message_text(text=MESSAGES[lang_code]["srbija_contractor_info_heating"])
            contractor_data = CONTRACTORS['srbija']
        else: # crnagora
            await query.edit_message_text(text=MESSAGES[lang_code]["crnagora_contractor_info_heating"])
            contractor_data = CONTRACTORS['crnagora']
        
        context.user_data['recipient_email'] = contractor_data['email'] # Postavljanje emaila primaoca
        context.user_data['recipient_name'] = contractor_data['name']

        keyboard = [
            [InlineKeyboardButton(MESSAGES[lang_code]["heating_radiators"], callback_data="type_radiators")],
            [InlineKeyboardButton(MESSAGES[lang_code]["heating_fancoil"], callback_data="type_fancoil")],
            [InlineKeyboardButton(MESSAGES[lang_code]["heating_underfloor"], callback_data="type_underfloor")],
            [InlineKeyboardButton(MESSAGES[lang_code]["heating_underfloor_fancoil"], callback_data="type_underfloor_fancoil")],
            [InlineKeyboardButton(MESSAGES[lang_code]["heating_complete_hp"], callback_data="type_complete_hp")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id=query.message.chat_id, text=MESSAGES[lang_code]["select_heating_type"], reply_markup=reply_markup)
        return SELECT_HEATING_TYPE
    
    elif service == "hp":
        country = context.user_data['country']
        if country == "srbija":
            await query.edit_message_text(text=MESSAGES[lang_code]["srbija_microma_info_hp"])
            context.user_data['recipient_email'] = MICROMA['email']
            context.user_data['recipient_name'] = MICROMA['name']
            
            keyboard = [
                [InlineKeyboardButton(MESSAGES[lang_code]["hp_water_water"], callback_data="hp_water_water")],
                [InlineKeyboardButton(MESSAGES[lang_code]["hp_air_water"], callback_data="hp_air_water")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(chat_id=query.message.chat_id, text=MESSAGES[lang_code]["select_hp_type_srbija"], reply_markup=reply_markup)
            return SELECT_HP_TYPE
        else: # crnagora
            await query.edit_message_text(text=MESSAGES[lang_code]["crnagora_instalm_info_hp"])
            context.user_data['recipient_email'] = CONTRACTORS['crnagora']['email']
            context.user_data['recipient_name'] = CONTRACTORS['crnagora']['name']

            keyboard = [
                [InlineKeyboardButton(MESSAGES[lang_code]["hp_air_water"], callback_data="hp_air_water")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(chat_id=query.message.chat_id, text=MESSAGES[lang_code]["select_hp_type_crnagora"], reply_markup=reply_markup)
            return SELECT_HP_TYPE

async def select_heating_type(update: Update, context):
    """Hvata tip grejne instalacije i traži površinu objekta."""
    query = update.callback_query
    await query.answer()
    lang_code = context.user_data.get('language', 'srpski')
    heating_type = query.data.split('_')[1]
    context.user_data['heating_type'] = MESSAGES[lang_code][f"heating_{heating_type}"] # Sačuvaj tekstualni opis

    await query.edit_message_text(text=MESSAGES[lang_code]["enter_surface"])
    return ENTER_SURFACE

async def select_hp_type(update: Update, context):
    """Hvata tip toplotne pumpe i, ako je toplotna pumpa za CG, ide na unos kontakt podataka, inače ide na unos površine."""
    query = update.callback_query
    await query.answer()
    lang_code = context.user_data.get('language', 'srpski')
    hp_type = query.data.split('_')[1]
    context.user_data['hp_type'] = MESSAGES[lang_code][f"hp_{hp_type}"] # Sačuvaj tekstualni opis

    # Ako je Crna Gora, odmah idemo na kontakt, jer nema dodatnih pitanja o objektu za HP
    if context.user_data['country'] == "crnagora":
        await query.edit_message_text(text=MESSAGES[lang_code]["enter_contact_info"])
        return ENTER_CONTACT_INFO
    else: # Srbija - idemo na pitanja o objektu za HP
        await query.edit_message_text(text=MESSAGES[lang_code]["enter_surface"])
        return ENTER_SURFACE

async def enter_surface(update: Update, context):
    """Prima površinu objekta i traži broj spratova."""
    lang_code = context.user_data.get('language', 'srpski')
    try:
        surface = int(update.message.text)
        context.user_data['surface'] = surface
        await update.message.reply_text(MESSAGES[lang_code]["enter_floors"])
        return ENTER_FLOORS
    except ValueError:
        await update.message.reply_text(MESSAGES[lang_code]["surface_invalid"])
        return ENTER_SURFACE # Ostaje u istom stanju dok ne unese ispravno

async def enter_floors(update: Update, context):
    """Prima broj spratova i traži vrstu objekta."""
    lang_code = context.user_data.get('language', 'srpski')
    try:
        floors = int(update.message.text)
        context.user_data['floors'] = floors
        
        keyboard = [
            [InlineKeyboardButton(MESSAGES[lang_code]["object_house"], callback_data="object_house")],
            [InlineKeyboardButton(MESSAGES[lang_code]["object_apartment"], callback_data="object_apartment")],
            [InlineKeyboardButton(MESSAGES[lang_code]["object_commercial"], callback_data="object_commercial")],
            [InlineKeyboardButton(MESSAGES[lang_code]["object_other"], callback_data="object_other")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(MESSAGES[lang_code]["select_object_type"], reply_markup=reply_markup)
        return SELECT_OBJECT_TYPE
    except ValueError:
        await update.message.reply_text(MESSAGES[lang_code]["floors_invalid"])
        return ENTER_FLOORS # Ostaje u istom stanju dok ne unese ispravno

async def select_object_type(update: Update, context):
    """Hvata vrstu objekta i pita za skicu."""
    query = update.callback_query
    await query.answer()
    lang_code = context.user_data.get('language', 'srpski')
    object_type = query.data.split('_')[1]
    context.user_data['object_type'] = MESSAGES[lang_code][f"object_{object_type}"] # Sačuvaj tekstualni opis

    keyboard = [
        [InlineKeyboardButton(MESSAGES[lang_code]["yes"], callback_data="ask_sketch_yes")],
        [InlineKeyboardButton(MESSAGES[lang_code]["no"], callback_data="ask_sketch_no")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=MESSAGES[lang_code]["ask_for_sketch"], reply_markup=reply_markup)
    return ASK_FOR_SKETCH

async def ask_for_sketch(update: Update, context):
    """Rukuje odgovorom na pitanje o skici."""
    query = update.callback_query
    await query.answer()
    lang_code = context.user_data.get('language', 'srpski')
    
    if query.data == "ask_sketch_yes":
        await query.edit_message_text(text=MESSAGES[lang_code]["upload_sketch"])
        return RECEIVE_SKETCH
    else: # ask_sketch_no
        context.user_data['sketch_info'] = MESSAGES[lang_code]["skip_sketch"]
        await query.edit_message_text(text=MESSAGES[lang_code]["enter_contact_info"])
        return ENTER_CONTACT_INFO

async def receive_sketch(update: Update, context):
    """Prima skicu i traži kontakt podatke."""
    lang_code = context.user_data.get('language', 'srpski')
    
    if update.message.document:
        file_id = update.message.document.file_id
        file_name = update.message.document.file_name
        context.user_data['sketch_info'] = f"Korisnik je priložio dokument: {file_name} (File ID: {file_id})"
        context.user_data['sketch_file_id'] = file_id # Sačuvaj ID da možeš kasnije da preuzmeš
    elif update.message.photo:
        # Uzmi najveću rezoluciju slike
        file_id = update.message.photo[-1].file_id
        context.user_data['sketch_info'] = f"Korisnik je priložio sliku (File ID: {file_id})"
        context.user_data['sketch_file_id'] = file_id
    else:
        await update.message.reply_text(MESSAGES[lang_code]["upload_sketch"]) # Ponovi, ako nije ni slika ni dok
        return RECEIVE_SKETCH
    
    await update.message.reply_text(MESSAGES[lang_code]["enter_contact_info"])
    return ENTER_CONTACT_INFO

async def enter_contact_info(update: Update, context):
    """Prima kontakt podatke i šalje upit."""
    lang_code = context.user_data.get('language', 'srpski')
    context.user_data['contact_info'] = update.message.text
    user = update.message.from_user

    # Priprema sadržaja emaila
    subject = f"Novi upit od Telegram bota - {context.user_data.get('service').upper()} - {context.user_data.get('country').upper()}"
    body = [
        f"Korisničko ime Telegrama: @{user.username or 'N/A'} (ID: {user.id})",
        f"Izabrani jezik: {context.user_data.get('language', 'N/A')}",
        f"Izabrana zemlja: {context.user_data.get('country', 'N/A').capitalize()}",
        f"Tip upita: {MESSAGES[lang_code][f'service_{context.user_data.get('service', 'N/A')}']}"
    ]

    if context.user_data.get('service') == "heating":
        body.append(f"Tip grejne instalacije: {context.user_data.get('heating_type', 'N/A')}")
        body.append(f"Površina objekta: {context.user_data.get('surface', 'N/A')} m²")
        body.append(f"Broj spratova: {context.user_data.get('floors', 'N/A')}")
        body.append(f"Vrsta objekta: {context.user_data.get('object_type', 'N/A')}")
        body.append(f"Skica objekta: {context.user_data.get('sketch_info', 'Nije priložena')}")
    elif context.user_data.get('service') == "hp":
        body.append(f"Tip toplotne pumpe: {context.user_data.get('hp_type', 'N/A')}")
        # Za HP u CG nema pitanja o objektu, za Srbiju ima
        if context.user_data['country'] == "srbija":
            body.append(f"Površina objekta: {context.user_data.get('surface', 'N/A')} m²")
            body.append(f"Broj spratova: {context.user_data.get('floors', 'N/A')}")
            body.append(f"Vrsta objekta: {context.user_data.get('object_type', 'N/A')}")
            body.append(f"Skica objekta: {context.user_data.get('sketch_info', 'Nije priložena')}")

    body.append(f"Kontakt podaci korisnika: {context.user_data.get('contact_info', 'N/A')}")
    
    # Slanje emaila
    try:
        yag = yagmail.SMTP(EMAIL_SENDER_ADDRESS, EMAIL_SENDER_PASSWORD)
        
        recipients = [context.user_data['recipient_email']]
        
        # Prilaganje skice ako postoji
        attachments = []
        if 'sketch_file_id' in context.user_data:
            try:
                file_id = context.user_data['sketch_file_id']
                # Preuzimanje fajla
                telegram_file = await context.bot.get_file(file_id)
                # Kreiranje privremene putanje za čuvanje fajla
                # Bolje je koristiti BytesIO ili tempfile da se ne čuvaju fajlovi na serveru
                file_extension = ""
                if update.message.document:
                    file_extension = os.path.splitext(update.message.document.file_name)[1]
                elif update.message.photo:
                    file_extension = ".jpg" # Pretpostavka za slike
                
                temp_file_path = f"/tmp/sketch_{file_id}{file_extension}"
                await telegram_file.download_to_drive(custom_path=temp_file_path)
                attachments.append(temp_file_path)
            except Exception as e:
                logger.error(f"Greška pri preuzimanju/prilaganju skice: {e}")
                body.append("\nNAPOMENA: Došlo je do greške prilikom preuzimanja priložene skice.")

        yag.send(
            to=recipients,
            bcc=BCC_EMAIL,
            subject=subject,
            contents=body,
            attachments=attachments
        )
        # Očistiti privremene fajlove ako su kreirani
        for attach_path in attachments:
            if os.path.exists(attach_path):
                os.remove(attach_path)

        logger.info(f"Upit uspešno poslat na {context.user_data['recipient_email']} sa BCC na {BCC_EMAIL}.")
        
        if context.user_data['service'] == "heating":
            await update.message.reply_text(MESSAGES[lang_code]["thank_you_heating"])
        else:
            await update.message.reply_text(MESSAGES[lang_code]["thank_you_hp"])
        
        # Obavestite admina ako je TELEGRAM_ADMIN_ID postavljen
        if ADMIN_TELEGRAM_ID:
            try:
                await context.bot.send_message(chat_id=ADMIN_TELEGRAM_ID, text=f"Novi upit poslat:\n\n{'\n'.join(body)}")
                if attachments:
                    await context.bot.send_message(chat_id=ADMIN_TELEGRAM_ID, text="Skica je priložena (pogledajte originalni mejl).")
            except Exception as e:
                logger.warning(f"Nije moguće poslati admin notifikaciju: {e}")


    except Exception as e:
        logger.error(f"Greška pri slanju emaila: {e}")
        await update.message.reply_text(MESSAGES[lang_code]["error_sending_email"])
        if ADMIN_TELEGRAM_ID:
            await context.bot.send_message(chat_id=ADMIN_TELEGRAM_ID, text=f"GREŠKA PRI SLANJU MAILA! Korisnik @{user.username} (ID: {user.id}) je pokušao da pošalje upit, ali je došlo do greške: {e}")

    # Resetovanje konverzacije
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context):
    """Omogućava korisniku da prekine konverzaciju."""
    lang_code = context.user_data.get('language', 'srpski')
    await update.message.reply_text(MESSAGES[lang_code]["start_over"])
    context.user_data.clear()
    return ConversationHandler.END

async def fallback(update: Update, context):
    """Hvata neprepoznate poruke."""
    lang_code = context.user_data.get('language', 'srpski')
    await update.message.reply_text(MESSAGES[lang_code]["choose_option"])


def main():
    """Pokreće bota."""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN nije postavljen. Molimo podesite environment varijablu BOT_TOKEN.")
        return

    application = Application.builder().token(BOT_TOKEN).build()

    # Conversation Handler za vođenje korisnika kroz tok
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECT_LANGUAGE: [CallbackQueryHandler(select_language, pattern="^lang_")],
            SELECT_COUNTRY: [CallbackQueryHandler(select_country, pattern="^country_")],
            SELECT_SERVICE: [CallbackQueryHandler(select_service, pattern="^service_")],
            SELECT_HEATING_TYPE: [CallbackQueryHandler(select_heating_type, pattern="^type_")],
            SELECT_HP_TYPE: [CallbackQueryHandler(select_hp_type, pattern="^hp_")],
            ENTER_SURFACE: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_surface)],
            ENTER_FLOORS: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_floors)],
            SELECT_OBJECT_TYPE: [CallbackQueryHandler(select_object_type, pattern="^object_")],
            ASK_FOR_SKETCH: [CallbackQueryHandler(ask_for_sketch, pattern="^ask_sketch_")],
            RECEIVE_SKETCH: [MessageHandler(filters.ALL & ~filters.COMMAND, receive_sketch)],
            ENTER_CONTACT_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_contact_info)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", start), # Omogućava restartovanje u bilo kom trenutku
            MessageHandler(filters.TEXT | filters.PHOTO | filters.Document.ALL, fallback) # Hvata nepoznate unose, ukljucujuci dokumente
        ],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("cancel", cancel)) # Globalni cancel

    # --- Render.com deployment konfiguracija ---
    # Render.com obezbeđuje PORT environment varijablu
    PORT = int(os.environ.get("PORT", 8080))
    # Render.com hostname je dostupan preko RENDER_EXTERNAL_HOSTNAME
    # ili ga možete podesiti ručno u Render dashboardu kao WEBHOOK_URL
    WEBHOOK_URL = os.getenv("WEBHOOK_URL") 
    
    if WEBHOOK_URL:
        logger.info(f"Pokušavam da postavim webhook na: {WEBHOOK_URL}")
        try:
            application.run_webhook(
                listen="0.0.0.0",
                port=PORT,
                url_path=BOT_TOKEN, # Vaš bot token kao putanja za webhook
                webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}"
            )
            logger.info("Webhook je uspešno postavljen.")
        except Exception as e:
            logger.error(f"Greška pri postavljanju webhooka: {e}")
            logger.warning("Pokušavam da pokrenem bota u polling modu zbog greške sa webhookom.")
            application.run_polling(allowed_updates=Update.ALL_TYPES)
    else:
        logger.warning("WEBHOOK_URL nije postavljen. Pokrećem bota u polling modu (nije za produkciju na Renderu).")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()