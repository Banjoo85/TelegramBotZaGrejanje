import os
import logging
import tempfile
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

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_TELEGRAM_ID = os.getenv("TELEGRAM_ADMIN_ID")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

EMAIL_SENDER_ADDRESS = os.getenv("EMAIL_SENDER_ADDRESS")
EMAIL_SENDER_PASSWORD = os.getenv("EMAIL_SENDER_PASSWORD")
BCC_EMAIL = "banjooo85@gmail.com"

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

MESSAGES = {
    "sr": {
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
    "en": {
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
    "ru": {
        "welcome": "Добро пожаловать! Выберите язык:",
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

async def start(update: Update, context):
    """Šalje pozdravnu poruku i traži izbor jezika."""
    keyboard = [
        [InlineKeyboardButton("Srpski", callback_data="lang_sr")],
        [InlineKeyboardButton("English", callback_data="lang_en")],
        [InlineKeyboardButton("Русский", callback_data="lang_ru")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(MESSAGES["sr"]["welcome"], reply_markup=reply_markup)
    return SELECT_LANGUAGE

async def select_language(update: Update, context):
    """Hvata izbor jezika i traži izbor zemlje."""
    query = update.callback_query
    await query.answer()
    lang_code = query.data.split('_')[1]
    
    context.user_data['language'] = lang_code
    logger.info(f"User {update.effective_user.id} selected language: {lang_code}")
    
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
    lang_code = context.user_data.get('language', 'sr')
    
    country = query.data.split('_')[1]
    context.user_data['country'] = country
    logger.info(f"User {update.effective_user.id} selected country: {country}")

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
    lang_code = context.user_data.get('language', 'sr')
    service = query.data.split('_')[1]
    context.user_data['service'] = service
    logger.info(f"User {update.effective_user.id} selected service: {service}")

    if service == "heating":
        country = context.user_data['country']
        if country == "srbija":
            await query.edit_message_text(text=MESSAGES[lang_code]["srbija_contractor_info_heating"])
            contractor_data = CONTRACTORS['srbija']
        else: # crnagora
            await query.edit_message_text(text=MESSAGES[lang_code]["crnagora_contractor_info_heating"])
            contractor_data = CONTRACTORS['crnagora']
        
        context.user_data['recipient_email'] = contractor_data['email']
        context.user_data['recipient_name'] = contractor_data['name']

        keyboard = [
            [InlineKeyboardButton(MESSAGES[lang_code]["heating_radiators"], callback_data="heating_radiators")],
            [InlineKeyboardButton(MESSAGES[lang_code]["heating_fancoil"], callback_data="heating_fancoil")],
            [InlineKeyboardButton(MESSAGES[lang_code]["heating_underfloor"], callback_data="heating_underfloor")],
            [InlineKeyboardButton(MESSAGES[lang_code]["heating_underfloor_fancoil"], callback_data="heating_underfloor_fancoil")],
            [InlineKeyboardButton(MESSAGES[lang_code]["heating_complete_hp"], callback_data="heating_complete_hp")], # ISPRAVLJENO OVDJE
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
    lang_code = context.user_data.get('language', 'sr')
    heating_type_key = query.data # Uzmi ceo callback_data string
    
    if heating_type_key in MESSAGES[lang_code]:
        context.user_data['heating_type'] = MESSAGES[lang_code][heating_type_key]
    else:
        logger.warning(f"Nepoznat heating_type_key: {heating_type_key} za jezik: {lang_code}")
        context.user_data['heating_type'] = "N/A - Unknown Heating Type"

    logger.info(f"User {update.effective_user.id} selected heating type: {context.user_data['heating_type']}")
    await query.edit_message_text(text=MESSAGES[lang_code]["enter_surface"])
    return ENTER_SURFACE

async def select_hp_type(update: Update, context):
    """Hvata tip toplotne pumpe i, ako je toplotna pumpa za CG, ide na unos kontakt podataka, inače ide na unos površine."""
    query = update.callback_query
    await query.answer()
    lang_code = context.user_data.get('language', 'sr')
    
    hp_type_key = query.data # Uzmi ceo callback_data string, npr. "hp_water_water"
    
    if hp_type_key in MESSAGES[lang_code]:
        context.user_data['hp_type'] = MESSAGES[lang_code][hp_type_key]
    else:
        logger.warning(f"Nepoznat hp_type_key: {hp_type_key} za jezik: {lang_code}")
        context.user_data['hp_type'] = "N/A - Unknown HP Type"

    logger.info(f"User {update.effective_user.id} selected HP type: {context.user_data['hp_type']}")

    if context.user_data['country'] == "crnagora":
        await query.edit_message_text(text=MESSAGES[lang_code]["enter_contact_info"])
        return ENTER_CONTACT_INFO
    else:
        await query.edit_message_text(text=MESSAGES[lang_code]["enter_surface"])
        return ENTER_SURFACE

async def enter_surface(update: Update, context):
    """Prima površinu objekta i traži broj spratova."""
    lang_code = context.user_data.get('language', 'sr')
    user_input = update.message.text
    try:
        surface = int(user_input)
        context.user_data['surface'] = surface
        logger.info(f"User {update.effective_user.id} entered surface: {surface} m²")
        await update.message.reply_text(MESSAGES[lang_code]["enter_floors"])
        return ENTER_FLOORS
    except ValueError:
        logger.warning(f"User {update.effective_user.id} entered invalid surface: '{user_input}'")
        await update.message.reply_text(MESSAGES[lang_code]["surface_invalid"])
        return ENTER_SURFACE

async def enter_floors(update: Update, context):
    """Prima broj spratova i traži vrstu objekta."""
    lang_code = context.user_data.get('language', 'sr')
    user_input = update.message.text
    try:
        floors = int(user_input)
        context.user_data['floors'] = floors
        logger.info(f"User {update.effective_user.id} entered floors: {floors}")
        
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
        logger.warning(f"User {update.effective_user.id} entered invalid floors: '{user_input}'")
        await update.message.reply_text(MESSAGES[lang_code]["floors_invalid"])
        return ENTER_FLOORS

async def select_object_type(update: Update, context):
    """Hvata vrstu objekta i pita za skicu."""
    query = update.callback_query
    await query.answer()
    lang_code = context.user_data.get('language', 'sr')
    object_type_key = query.data # Uzmi ceo callback_data string
    
    if object_type_key in MESSAGES[lang_code]:
        context.user_data['object_type'] = MESSAGES[lang_code][object_type_key]
    else:
        logger.warning(f"Nepoznat object_type_key: {object_type_key} za jezik: {lang_code}")
        context.user_data['object_type'] = "N/A - Unknown Object Type"

    logger.info(f"User {update.effective_user.id} selected object type: {context.user_data['object_type']}")

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
    lang_code = context.user_data.get('language', 'sr')
    
    if query.data == "ask_sketch_yes":
        logger.info(f"User {update.effective_user.id} chose to attach sketch.")
        await query.edit_message_text(text=MESSAGES[lang_code]["upload_sketch"])
        return RECEIVE_SKETCH
    else: # ask_sketch_no
        context.user_data['sketch_info'] = MESSAGES[lang_code]["skip_sketch"]
        context.user_data['sketch_file_id'] = None
        logger.info(f"User {update.effective_user.id} chose NOT to attach sketch.")
        await query.edit_message_text(text=MESSAGES[lang_code]["enter_contact_info"])
        return ENTER_CONTACT_INFO

async def receive_sketch(update: Update, context):
    """Prima skicu i traži kontakt podatke."""
    lang_code = context.user_data.get('language', 'sr')
    
    file_id = None
    file_name = "N/A"
    if update.message.document:
        file_id = update.message.document.file_id
        file_name = update.message.document.file_name
        context.user_data['sketch_info'] = f"Korisnik je priložio dokument: {file_name} (File ID: {file_id})"
        logger.info(f"User {update.effective_user.id} uploaded document: {file_name} (ID: {file_id})")
    elif update.message.photo:
        file_id = update.message.photo[-1].file_id
        context.user_data['sketch_info'] = f"Korisnik je priložio sliku (File ID: {file_id})"
        file_name = f"photo_{file_id}.jpg"
        logger.info(f"User {update.effective_user.id} uploaded photo (ID: {file_id})")
    else:
        logger.warning(f"User {update.effective_user.id} sent message not a document or photo in RECEIVE_SKETCH: {update.message.text}")
        await update.message.reply_text(MESSAGES[lang_code]["upload_sketch"])
        return RECEIVE_SKETCH
    
    context.user_data['sketch_file_id'] = file_id
    
    await update.message.reply_text(MESSAGES[lang_code]["enter_contact_info"])
    return ENTER_CONTACT_INFO

async def enter_contact_info(update: Update, context):
    """Prima kontakt podatke i šalje upit."""
    lang_code = context.user_data.get('language', 'sr')
    context.user_data['contact_info'] = update.message.text
    user = update.message.from_user

    service_type = context.user_data.get('service', 'N/A')
    heating_type = context.user_data.get('heating_type', 'N/A')
    country = context.user_data.get('country', 'N/A')

    if service_type == "heating" and heating_type == MESSAGES[lang_code]["heating_complete_hp"]:
        subject = f"Novi upit od Telegram bota - KOMPLETNA PONUDA (Grejanje + TP) - {country.upper()}"
    else:
        subject = f"Novi upit od Telegram bota - {service_type.upper()} - {country.upper()}"

    body = [
        f"Korisnicko ime Telegrama: @{user.username or 'N/A'} (ID: {user.id})",
        f"Izabrani jezik: {lang_code}",
        f"Izabrana zemlja: {country.capitalize()}",
        f"Tip upita: {MESSAGES[lang_code][f'service_{service_type}']}"
    ]

    if service_type == "heating":
        body.append(f"Tip grejne instalacije: {heating_type}")
        body.append(f"Povrsina objekta: {context.user_data.get('surface', 'N/A')} m²")
        body.append(f"Broj spratova: {context.user_data.get('floors', 'N/A')}")
        body.append(f"Vrsta objekta: {context.user_data.get('object_type', 'N/A')}")
        body.append(f"Skica objekta: {context.user_data.get('sketch_info', 'Nije prilozena')}")
    elif service_type == "hp":
        body.append(f"Tip toplotne pumpe: {context.user_data.get('hp_type', 'N/A')}")
        if country == "srbija":
            body.append(f"Povrsina objekta: {context.user_data.get('surface', 'N/A')} m²")
            body.append(f"Broj spratova: {context.user_data.get('floors', 'N/A')}")
            body.append(f"Vrsta objekta: {context.user_data.get('object_type', 'N/A')}")
            body.append(f"Skica objekta: {context.user_data.get('sketch_info', 'Nije prilozena')}")

    body.append(f"Kontakt podaci korisnika: {context.user_data.get('contact_info', 'N/A')}")
    
    email_body_string = "\n".join(body) 

    logger.info(f"User {user.id} - Preparing email. Full context.user_data: {context.user_data}")
    logger.info(f"Email body content to be sent:\n{email_body_string}")

    try:
        yag = yagmail.SMTP(EMAIL_SENDER_ADDRESS, EMAIL_SENDER_PASSWORD)
        
        recipients = [context.user_data['recipient_email']]
        
        if service_type == "heating" and heating_type == MESSAGES[lang_code]["heating_complete_hp"]:
            if country == "srbija":
                recipients.append(MICROMA['email'])
                logger.info(f"Complete HP offer in Serbia: Adding {MICROMA['email']} to recipients.")
        
        attachments = []
        temp_file_path = None
        if context.user_data.get('sketch_file_id'): 
            try:
                file_id = context.user_data['sketch_file_id']
                telegram_file = await context.bot.get_file(file_id)
                
                file_extension = ""
                # Koristi update.message.document ili update.message.photo za odredjivanje ekstenzije
                if update.message.document:
                    file_extension = os.path.splitext(update.message.document.file_name)[1]
                elif update.message.photo:
                    file_extension = ".jpg" # Default for photos, Telegram doesn't provide original name
                    
                with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
                    temp_file_path = temp_file.name
                
                await telegram_file.download_to_drive(custom_path=temp_file_path)
                attachments.append(temp_file_path)
                logger.info(f"Sketch attached: {temp_file_path}")
            except Exception as e:
                logger.error(f"Greska pri preuzimanju/prilaganju skice za korisnika {user.id}: {e}")
                email_body_string += "\n\nNAPOMENA: Doslo je do greske prilikom preuzimanja prilozene skice."
                if 'temp_file_path' in locals() and temp_file_path and os.path.exists(temp_file_path):
                     os.remove(temp_file_path)
                attachments = []
        
        yag.send(
            to=recipients,
            bcc=BCC_EMAIL,
            subject=subject,
            contents=email_body_string,
            attachments=attachments
        )
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            logger.info(f"Temporary sketch file deleted: {temp_file_path}")


        logger.info(f"Upit uspesno poslat na {', '.join(recipients)} sa BCC na {BCC_EMAIL}.")
        
        if service_type == "heating":
            await update.message.reply_text(MESSAGES[lang_code]["thank_you_heating"])
        else:
            await update.message.reply_text(MESSAGES[lang_code]["thank_you_hp"])
        
        if ADMIN_TELEGRAM_ID:
            try:
                admin_message = f"**NOVI UPIT PRIMLJEN!**\n\n" \
                                f"Od: @{user.username or 'N/A'} (ID: {user.id})\n" \
                                f"Jezik: {lang_code}\n" \
                                f"Zemlja: {country.capitalize()}\n" \
                                f"Tip upita: {MESSAGES[lang_code][f'service_{service_type}']}\n"
                
                if service_type == "heating":
                    admin_message += f"Tip grejanja: {heating_type}\n"
                    admin_message += f"Povrsina: {context.user_data.get('surface', 'N/A')} m²\n"
                    admin_message += f"Spratovi: {context.user_data.get('floors', 'N/A')}\n"
                    admin_message += f"Vrsta objekta: {context.user_data.get('object_type', 'N/A')}\n"
                    admin_message += f"Skica: {'Prilozena' if context.user_data.get('sketch_file_id') else 'Nije prilozena'}\n"
                elif service_type == "hp":
                    admin_message += f"Tip toplotne pumpe: {context.user_data.get('hp_type', 'N/A')}\n"
                    if country == "srbija": # Only for Serbia HP has these additional details
                        admin_message += f"Povrsina: {context.user_data.get('surface', 'N/A')} m²\n"
                        admin_message += f"Spratovi: {context.user_data.get('floors', 'N/A')}\n"
                        admin_message += f"Vrsta objekta: {context.user_data.get('object_type', 'N/A')}\n"
                        admin_message += f"Skica: {'Prilozena' if context.user_data.get('sketch_file_id') else 'Nije prilozena'}\n"

                admin_message += f"Kontakt: {context.user_data.get('contact_info', 'N/A')}\n\n" \
                                 f"Email poslat na: {', '.join(recipients)}"
                
                await context.bot.send_message(chat_id=ADMIN_TELEGRAM_ID, text=admin_message, parse_mode='Markdown')
                if attachments:
                    await context.bot.send_message(chat_id=ADMIN_TELEGRAM_ID, text="Skica je prilozena (pogledajte originalni mejl).")
            except Exception as e:
                logger.warning(f"Nije moguce poslati admin notifikaciju: {e}")


    except Exception as e:
        logger.error(f"Greska pri slanju emaila za korisnika {user.id}: {e}", exc_info=True)
        await update.message.reply_text(MESSAGES[lang_code]["error_sending_email"])
        if ADMIN_TELEGRAM_ID:
            await context.bot.send_message(chat_id=ADMIN_TELEGRAM_ID, text=f"GREŠKA PRI SLANJU MAILA! Korisnik @{user.username} (ID: {user.id}) je pokusao da posalje upit, ali je doslo do greske: {e}")

    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context):
    """Omogućava korisniku da prekine konverzaciju."""
    lang_code = context.user_data.get('language', 'sr')
    logger.info(f"User {update.effective_user.id} cancelled conversation.")
    await update.message.reply_text(MESSAGES[lang_code]["start_over"])
    context.user_data.clear()
    return ConversationHandler.END

async def fallback(update: Update, context):
    """Hvata neprepoznate poruke."""
    lang_code = context.user_data.get('language', 'sr')
    logger.warning(f"User {update.effective_user.id} sent unknown message: {update.message.text}")
    await update.message.reply_text(MESSAGES[lang_code]["choose_option"])
    context.user_data.clear()
    return ConversationHandler.END

async def error_handler(update: Update, context):
    """Log the error and send a message to the user."""
    logger.error("Exception while handling an update:", exc_info=context.error)
    lang_code = context.user_data.get('language', 'sr')
    if update.effective_message:
        await update.effective_message.reply_text(MESSAGES[lang_code]["something_went_wrong"])
    context.user_data.clear()
    return ConversationHandler.END


def main():
    """Pokreće bota."""
    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECT_LANGUAGE: [CallbackQueryHandler(select_language, pattern="^lang_")],
            SELECT_COUNTRY: [CallbackQueryHandler(select_country, pattern="^country_")],
            SELECT_SERVICE: [CallbackQueryHandler(select_service, pattern="^service_")],
            SELECT_HEATING_TYPE: [CallbackQueryHandler(select_heating_type, pattern="^(heating_radiators|heating_fancoil|heating_underfloor|heating_underfloor_fancoil|heating_complete_hp)$")], # AŽURIRAN PATTERN
            SELECT_HP_TYPE: [CallbackQueryHandler(select_hp_type, pattern="^(hp_water_water|hp_air_water)$")], # AŽURIRAN PATTERN
            ENTER_SURFACE: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_surface)],
            ENTER_FLOORS: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_floors)],
            SELECT_OBJECT_TYPE: [CallbackQueryHandler(select_object_type, pattern="^object_")],
            ASK_FOR_SKETCH: [CallbackQueryHandler(ask_for_sketch, pattern="^ask_sketch_")],
            RECEIVE_SKETCH: [
                MessageHandler(filters.PHOTO | filters.Document.ALL & ~filters.COMMAND, receive_sketch),
                MessageHandler(filters.TEXT & ~filters.COMMAND, fallback)
            ],
            ENTER_CONTACT_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_contact_info)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.add_error_handler(error_handler)

    if WEBHOOK_URL:
        PORT = int(os.environ.get("PORT", "8443"))
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=BOT_TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}"
        )
        logger.info(f"Webhook enabled on port {PORT} with URL {WEBHOOK_URL}/{BOT_TOKEN}")
    else:
        logger.info("Polling enabled (WEBHOOK_URL not set).")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()