import logging
import smtplib
import os
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from io import BytesIO # Za rad sa binarnim podacima slika

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ConversationHandler,
)
from telegram.constants import ParseMode # Dodato za ParseMode

# --- Učitavanje .env fajla za sigurne podatke ---
load_dotenv()

# --- PODACI ZA KONTAKT I ADMINI ---
contact_info = {
    'srbija': {
        # Podaci za IZVOĐAČA RADOVA u Srbiji
        'contractor': {
            'name': 'Igor Bošković',
            'phone': '+381603932566',
            'email': 'boskovicigor83@gmail.com',
            'website': ':',
            'telegram': '@IgorNS1983'
        },
        # Podaci za PROIZVOĐAČA u Srbiji (Microma)
        'manufacturer': {
            'name': 'Microma',
            'phone': '+38163582068',
            'email': 'office@microma.rs',
            'website': 'https://microma.rs',
            'telegram': ':'
        }
    },
    'crna_gora': {
        # Podaci za IZVOĐAČA RADOVA u Crnoj Gori (Instal M)
        'contractor': {
            'name': 'Instal M',
            'phone': '+38267423237',
            'email': 'office@instalm.me',
            'website': ':',
            'telegram': '@ivanmujovic'
        }
    }
}

# Telegram ID-ovi admina koji će primati obaveštenja
# ZAMENI OVO SA SVOJIM STVARNIM TELEGRAM ID-jem!
# Pronađi svoj ID koristeći @userinfobot na Telegramu.
ADMIN_IDS = []
admin_id_str = os.getenv("TELEGRAM_ADMIN_ID")
if admin_id_str:
    try:
        ADMIN_IDS.append(int(admin_id_str))
    except ValueError:
        logger.error(f"TELEGRAM_ADMIN_ID is not a valid integer: {admin_id_str}")

# Možeš i direktno, ali sa proverom (ako znaš da će uvek biti jedan admin):
# admin_id_raw = os.getenv("TELEGRAM_ADMIN_ID")
# ADMIN_IDS = [int(admin_id_raw)] if admin_id_raw else []

# Ako imaš više admina, i želiš ih iz jedne varijable razdvojene zarezom (napredno, samo primer):
# admin_ids_str = os.getenv("TELEGRAM_ADMIN_IDS", "") # Plural, ako zelis vise ID-jeva
# ADMIN_IDS = [int(x.strip()) for x in admin_ids_str.split(',') if x.strip().isdigit()]

# Definišemo stanja (states) za ConversationHandler
SELECTING_LANGUAGE, SELECTING_COUNTRY, SELECTING_HEATING_TYPE, SELECTING_INSTALLATION_OPTION, \
    ENTERING_OBJECT_DETAILS, SELECTING_HP_TYPE, CONFIRM_SEND_INQUIRY = range(7)

# --- Tekstovi na različitim jezicima ---
TEXTS = {
    "sr": {
        "welcome": "Dobrodošli! Molimo izaberite jezik:",
        "choose_language": "Izaberite jezik:",
        "Srbija": "Srbija 🇷🇸",
        "Crna Gora": "Crna Gora 🇲🇪",
        "choose_country": "Izaberite zemlju:",
        "grejna instalacija": "Grejna instalacija",
        "toplotna pumpa": "Toplotna pumpa",
        "heating_options": "Molimo izaberite opciju:",
        "contractor_info": "Izvođač radova: *{name}*\n📞: {phone}\n✉️: {email}\n🌐: {website}\n👤: {telegram}",
        "installation_options": "Izaberite tip instalacije:",
        "radijatori": "Radijatori",
        "fancoil-i": "Fancoil-i",
        "podno grejanje": "Podno grejanje",
        "podno grejanje+fancoil-i": "Podno grejanje + Fancoil-i",
        "komplet ponuda sa toplotnom pumpom": "Komplet ponuda sa toplotnom pumpom",
        "enter_object_details": "Molimo unesite podatke o objektu (površina, spratnost, vrsta objekta). Možete priložiti i skicu.",
        "inquiry_confirmation": "Da li želite da pošaljete upit izvođaču?",
        "Da": "Da",
        "Ne": "Ne",
        "inquiry_sent": "Vaš upit je uspešno poslat! Uskoro će Vas kontaktirati izvođač radova.",
        "inquiry_cancelled": "Upit otkazan.",
        "hp_options_srb": "Izaberite tip toplotne pumpe:",
        "hp_options_mne": "Izaberite tip toplotne pumpe:",
        "voda-voda": "Voda-Voda",
        "vazduh-voda": "Vazduh-Voda",
        "microma_info": "Podaci o proizvođaču toplotnih pumpi *Microma*:\n📞: {phone}\n✉️: {email}\n🌐: {website}",
        "instal_m_info": "Podaci o izvođaču toplotnih pumpi *Instal M*:\n📞: {phone}\n✉️: {email}\n🌐: {website}\n👤: {telegram}",
        "unknown_command": "Nepoznata komanda. Molimo koristite tastere.",
        "cancel_command": "Operacija otkazana. Možete početi ponovo sa /start.",
        "admin_inquiry_subject": "Novi upit od korisnika!",
        "admin_inquiry_body": "Korisnik: *{user_name}* (ID: `{user_id}`)\nZemlja: *{country_name}*\nIzbor: *{choice_type}*\nOpcija: *{option_selected}*\n\n*Detalji objekta:*\n{object_details}",
        "N/A": "N/A" # Dodato za N/A tekst
    },
    "en": {
        "welcome": "Welcome! Please choose your language:",
        "choose_language": "Choose language:",
        "Srbija": "Serbia 🇷🇸",
        "Crna Gora": "Montenegro 🇲🇪",
        "choose_country": "Choose country:",
        "grejna instalacija": "Heating Installation",
        "toplotna pumpa": "Heat Pump",
        "heating_options": "Please select an option:",
        "contractor_info": "Contractor: *{name}*\n📞: {phone}\n✉️: {email}\n🌐: {website}\n👤: {telegram}",
        "installation_options": "Select installation type:",
        "radijatori": "Radiators",
        "fancoil-i": "Fancoils",
        "podno grejanje": "Underfloor Heating",
        "podno grejanje+fancoil-i": "Underfloor Heating + Fancoils",
        "komplet ponuda sa toplotnom pumpom": "Complete offer with Heat Pump",
        "enter_object_details": "Please enter object details (area, number of floors, object type). You can also attach a sketch.",
        "inquiry_confirmation": "Do you want to send the inquiry to the contractor?",
        "Da": "Yes",
        "Ne": "No",
        "inquiry_sent": "Your inquiry has been sent successfully! The contractor will contact you soon.",
        "inquiry_cancelled": "Inquiry cancelled.",
        "hp_options_srb": "Select heat pump type:",
        "hp_options_mne": "Select heat pump type:",
        "voda-voda": "Water-to-Water",
        "vazduh-voda": "Air-to-Water",
        "microma_info": "Information about Microma heat pump manufacturer:\n📞: {phone}\n✉️: {email}\n🌐: {website}",
        "instal_m_info": "Information about Instal M (Montenegro) heat pump contractor:\n📞: {phone}\n✉️: {email}\n🌐: {website}\n👤: {telegram}",
        "unknown_command": "Unknown command. Please use the buttons.",
        "cancel_command": "Operation cancelled. You can start again with /start.",
        "admin_inquiry_subject": "New user inquiry!",
        "admin_inquiry_body": "User: *{user_name}* (ID: `{user_id}`)\nCountry: *{country_name}*\nChoice: *{choice_type}*\nOption: *{option_selected}*\n\n*Object details:*\n{object_details}",
        "N/A": "N/A" # Dodato za N/A tekst
    },
    "ru": {
        "welcome": "Добро пожаловать! Пожалуйста, выберите язык:",
        "choose_language": "Выберите язык:",
        "Srbija": "Сербия 🇷🇸",
        "Crna Gora": "Черногория 🇲🇪",
        "choose_country": "Выберите страну:",
        "grejna instalacija": "Отопительная установка",
        "toplotna pumpa": "Тепловой насос",
        "heating_options": "Пожалуйста, выберите вариант:",
        "contractor_info": "Подрядчик: *{name}*\n📞: {phone}\n✉️: {email}\n🌐: {website}\n👤: {telegram}",
        "installation_options": "Выберите тип установки:",
        "radijatori": "Радиаторы",
        "fancoil-i": "Фанкойлы",
        "podno grejanje": "Теплый пол",
        "podno grejanje+fancoil-i": "Теплый пол + Фанкойлы",
        "komplet ponuda sa toplotной pumpom": "Полное предложение с тепловым насосом",
        "enter_object_details": "Пожалуйста, введите данные об объекте (площадь, этажность, тип объекта). Вы также можете прикрепить эскиз.",
        "inquiry_confirmation": "Хотите отправить запрос подрядчику?",
        "Da": "Да",
        "Ne": "Нет",
        "inquiry_sent": "Ваш запрос успешно отправлен! Подрядчик свяжется с вами в ближайшее время.",
        "inquiry_cancelled": "Запрос отменен.",
        "hp_options_srb": "Выберите тип теплового насоса:",
        "hp_options_mne": "Выберите тип теплового насоса:",
        "voda-voda": "Вода-вода",
        "vazduh-voda": "Воздух-вода",
        "microma_info": "Информация о производителе тепловых насосов *Microma*:\n📞: {phone}\n✉️: {email}\n🌐: {website}",
        "instal_m_info": "Информация о подрядчике тепловых насосов *Instal M* (Черногория):\n📞: {phone}\n✉️: {email}\n🌐: {website}\n👤: {telegram}",
        "unknown_command": "Неизвестная команда. Пожалуйста, используйте кнопки.",
        "cancel_command": "Операция отменена. Вы можете начать снова с /start.",
        "admin_inquiry_subject": "Новый запрос пользователя!",
        "admin_inquiry_body": "Пользователь: *{user_name}* (ID: `{user_id}`)\nСтрана: *{country_name}*\nВыбор: *{choice_type}*\nОпция: *{option_selected}*\n\n*Детали объекта:*\n{object_details}",
        "N/A": "Н/Д" # Dodato za N/A tekst
    }
}


# --- Funkcija za slanje emaila ---
async def send_inquiry_email(
    to_email: str,
    bcc_email: str,
    subject: str,
    body: str,
    attachment_file_id: str = None,
    bot_instance: Bot = None, # Prihvatamo bot_instance za preuzimanje fajlova
    file_name: str = "sketch.jpg" # Default ime fajla
):
    sender_email = os.getenv("EMAIL_ADDRESS")
    sender_password = os.getenv("EMAIL_APP_PASSWORD") # Aplikaciona lozinka
    
    # Provera da li su potrebne varijable postavljene
    if not sender_email or not sender_password:
        logger.error("EMAIL_ADDRESS or EMAIL_APP_PASSWORD not set in .env")
        return False

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg['Bcc'] = bcc_email

    msg.attach(MIMEText(body, 'plain'))

    # Preuzimanje i prilaganje fajla ako postoji
    if attachment_file_id and bot_instance:
        try:
            logger.info(f"Pokušavam da preuzmem fajl sa ID-jem: {attachment_file_id}")
            # get_file je blokirajuća operacija, ali Python-Telegram-Bot rukuje sa ovim asinhrono
            file_obj = await bot_instance.get_file(attachment_file_id)
            
            # Downloadujemo fajl u memoriju kao BytesIO objekat
            downloaded_bytes = BytesIO()
            await file_obj.download_to_memory(out=downloaded_bytes)
            downloaded_bytes.seek(0) # Vrati kursor na početak BytesIO objekta

            part = MIMEBase("application", "octet-stream")
            part.set_payload(downloaded_bytes.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename= {file_name}")
            msg.attach(part)
            logger.info(f"Fajl {file_name} uspešno preuzet i priložen.")

        except Exception as e:
            logger.error(f"Greška prilikom preuzimanja ili prilaganja fajla {attachment_file_id}: {e}")
            # Nastavi bez priloga ako dođe do greške
            pass

    try:
        # Koristimo Gmail SMTP server; promenite ako koristite drugi
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server: # SMTPS za port 465
        # Alternativno za STARTTLS (port 587):
        # with smtplib.SMTP("smtp.gmail.com", 587) as server:
        #     server.starttls()
            server.login(sender_email, sender_password)
            text = msg.as_string()
            server.sendmail(sender_email, [to_email, bcc_email], text) # BCC ide ovde u sendmail
        logger.info(f"Email poslat na {to_email} sa BCC kopijom na {bcc_email}")
        return True
    except Exception as e:
        logger.error(f"Greška prilikom slanja emaila: {e}")
        return False

# --- Start funkcija (nepromenjena) ---
async def start(update: Update, context: object) -> int:
    """Počinje konverzaciju i traži izbor jezika."""
    keyboard = [
        [
            InlineKeyboardButton("Srpski 🇷🇸", callback_data="lang_sr"),
            InlineKeyboardButton("English 🇬🇧", callback_data="lang_en"),
            InlineKeyboardButton("Русский 🇷🇺", callback_data="lang_ru"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(TEXTS["sr"]["welcome"], reply_markup=reply_markup)
    return SELECTING_LANGUAGE

# --- Izbor jezika (nepromenjena) ---
async def select_language(update: Update, context: object) -> int:
    """Korisnik je izabrao jezik, prelazi se na izbor zemlje."""
    query = update.callback_query
    await query.answer()
    
    context.user_data['language'] = query.data.replace("lang_", "")
    lang = context.user_data['language']

    keyboard = [
        [
            InlineKeyboardButton(TEXTS[lang]["Srbija"], callback_data="country_srbija"),
            InlineKeyboardButton(TEXTS[lang]["Crna Gora"], callback_data="country_crna_gora"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(TEXTS[lang]["choose_country"], reply_markup=reply_markup)
    return SELECTING_COUNTRY

# --- Izbor zemlje ---
async def select_country(update: Update, context: object) -> int:
    """Korisnik je izabrao zemlju, prelazi se na izbor tipa instalacije/pumpe."""
    query = update.callback_query
    await query.answer()

    context.user_data['country_key'] = query.data.replace("country_", "") # Koristimo country_key za pristup podacima
    context.user_data['country_name'] = TEXTS[context.user_data['language']][context.user_data['country_key'].capitalize()] # Prikazno ime zemlje
    lang = context.user_data['language']

    keyboard = [
        [InlineKeyboardButton(TEXTS[lang]["grejna instalacija"], callback_data="type_heating")],
        [InlineKeyboardButton(TEXTS[lang]["toplotna pumpa"], callback_data="type_hp")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(TEXTS[lang]["heating_options"], reply_markup=reply_markup)
    return SELECTING_HEATING_TYPE

# --- Izbor tipa (Grejna instalacija / Toplotna pumpa) (ažurirana za dinamičke kontakt podatke) ---
async def select_heating_or_hp(update: Update, context: object) -> int:
    """Korisnik je izabao grejnu instalaciju ili toplotnu pumpu."""
    query = update.callback_query
    await query.answer()

    choice_type = query.data.replace("type_", "")
    context.user_data['choice_type'] = choice_type
    lang = context.user_data['language']
    country_key = context.user_data['country_key'] # 'srbija' ili 'crna_gora'

    if choice_type == "heating":
        contractor_data = contact_info[country_key]['contractor']
        contractor_text = TEXTS[lang]["contractor_info"].format(
            name=contractor_data['name'],
            phone=contractor_data['phone'],
            email=contractor_data['email'],
            website=contractor_data['website'] if contractor_data['website'] != ':' else TEXTS[lang]["N/A"],
            telegram=contractor_data['telegram'] if contractor_data['telegram'] != ':' else TEXTS[lang]["N/A"]
        )
        
        keyboard = [
            [InlineKeyboardButton(TEXTS[lang]["radijatori"], callback_data="inst_radijatori")],
            [InlineKeyboardButton(TEXTS[lang]["fancoil-i"], callback_data="inst_fancoil-i")],
            [InlineKeyboardButton(TEXTS[lang]["podno grejanje"], callback_data="inst_podno_grejanje")],
            [InlineKeyboardButton(TEXTS[lang]["podno grejanje+fancoil-i"], callback_data="inst_podno_grejanje_fancoil-i")],
            [InlineKeyboardButton(TEXTS[lang]["komplet ponuda sa toplotnom pumpom"], callback_data="inst_komplet_ponuda_sa_toplotnom_pumpom")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"{contractor_text}\n\n{TEXTS[lang]['installation_options']}", reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        return SELECTING_INSTALLATION_OPTION
    
    elif choice_type == "hp":
        if country_key == "srbija":
            keyboard = [
                [InlineKeyboardButton(TEXTS[lang]["voda-voda"], callback_data="hp_voda-voda")],
                [InlineKeyboardButton(TEXTS[lang]["vazduh-voda"], callback_data="hp_vazduh-voda")],
            ]
        else: # crna_gora
            keyboard = [
                [InlineKeyboardButton(TEXTS[lang]["vazduh-voda"], callback_data="hp_vazduh-voda")],
            ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(TEXTS[lang]["hp_options_srb"] if country_key == "srbija" else TEXTS[lang]["hp_options_mne"], reply_markup=reply_markup)
        return SELECTING_HP_TYPE

# --- Izbor opcije grejne instalacije (nepromenjena) ---
async def select_installation_option(update: Update, context: object) -> int:
    """Korisnik je izabrao specifičnu opciju grejne instalacije."""
    query = update.callback_query
    await query.answer()

    context.user_data['option_selected_key'] = query.data.replace("inst_", "")
    context.user_data['option_selected_name'] = TEXTS[context.user_data['language']].get(context.user_data['option_selected_key'], context.user_data['option_selected_key'])
    lang = context.user_data['language']

    await query.edit_message_text(TEXTS[lang]["enter_object_details"])
    return ENTERING_OBJECT_DETAILS

# --- Unos podataka o objektu (ažurirana za čuvanje podataka o slici) ---
async def enter_object_details(update: Update, context: object) -> int:
    """Korisnik unosi podatke o objektu."""
    context.user_data['object_details'] = update.message.text
    
    if update.message.photo:
        context.user_data['object_sketch_file_id'] = update.message.photo[-1].file_id # Uzima najveću rezoluciju fotke
    else:
        context.user_data['object_sketch_file_id'] = None

    lang = context.user_data['language']

    keyboard = [
        [
            InlineKeyboardButton(TEXTS[lang]["Da"], callback_data="confirm_yes"),
            InlineKeyboardButton(TEXTS[lang]["Ne"], callback_data="confirm_no"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(TEXTS[lang]["inquiry_confirmation"], reply_markup=reply_markup)
    return CONFIRM_SEND_INQUIRY

# --- Potvrda slanja upita (Ažurirana za slanje emaila i obaveštenja adminima) ---
async def confirm_send_inquiry(update: Update, context: object) -> int:
    """Potvrda slanja upita izvođaču."""
    query = update.callback_query
    await query.answer()

    lang = context.user_data['language']
    
    if query.data == "confirm_yes":
        country_key = context.user_data.get('country_key')
        contractor_data = contact_info[country_key]['contractor']
        
        user_id = update.effective_user.id
        user_name = update.effective_user.full_name
        object_details = context.user_data.get('object_details', TEXTS[lang]["N/A"])
        
        choice_type_display = TEXTS[lang]["grejna instalacija"] if context.user_data.get('choice_type') == "heating" else TEXTS[lang]["toplotna pumpa"]
        option_selected_display = context.user_data.get('option_selected_name', TEXTS[lang]["N/A"])
        
        object_sketch_file_id = context.user_data.get('object_sketch_file_id')

        # --- SLANJE EMAILA IZVOĐAČU ---
        contractor_email = contractor_data['email']
        admin_email_bcc = os.getenv("ADMIN_EMAIL") # BCC kopija na tvoj email
        
        email_subject = TEXTS[lang]["admin_inquiry_subject"]
        email_body = TEXTS[lang]["admin_inquiry_body"].format(
            user_name=user_name,
            user_id=user_id,
            country_name=context.user_data.get('country_name', TEXTS[lang]["N/A"]),
            choice_type=choice_type_display,
            option_selected=option_selected_display,
            object_details=object_details
        )
        
        email_sent_success = await send_inquiry_email(
            to_email=contractor_email,
            bcc_email=admin_email_bcc,
            subject=email_subject,
            body=email_body,
            attachment_file_id=object_sketch_file_id,
            bot_instance=context.bot # Prosleđujemo bot instancu za download fajla
        )
        
        if email_sent_success:
            logger.info(f"Email upit uspešno poslat izvođaču {contractor_email} i adminu {admin_email_bcc}.")
        else:
            logger.error(f"Neuspešno slanje email upita izvođaču {contractor_email} i adminu {admin_email_bcc}.")

        # --- SLANJE OBAVEŠTENJA ADMINIMA (putem Telegrama) ---
        admin_message_telegram = TEXTS[lang]["admin_inquiry_body"].format(
            user_name=user_name,
            user_id=user_id,
            country_name=context.user_data.get('country_name', TEXTS[lang]["N/A"]),
            choice_type=choice_type_display,
            option_selected=option_selected_display,
            object_details=object_details
        )

        bot_instance = context.bot # Pristupi bot objektu iz context-a

        for admin_id in ADMIN_IDS:
            try:
                await bot_instance.send_message(
                    chat_id=admin_id,
                    text=f"*{TEXTS[lang]['admin_inquiry_subject']}*\n\n{admin_message_telegram}",
                    parse_mode=ParseMode.MARKDOWN
                )
                if object_sketch_file_id:
                    await bot_instance.send_photo(
                        chat_id=admin_id,
                        photo=object_sketch_file_id,
                        caption=f"Skica od {user_name}"
                    )
                logger.info(f"Obaveštenje poslato adminu {admin_id} putem Telegrama.")
            except Exception as e:
                logger.error(f"Nije moguce poslati obavestenje adminu {admin_id} putem Telegrama: {e}")

        await query.edit_message_text(TEXTS[lang]["inquiry_sent"])
        
        context.user_data.clear() 
        return ConversationHandler.END 
    else:
        await query.edit_message_text(TEXTS[lang]["inquiry_cancelled"])
        context.user_data.clear() 
        return ConversationHandler.END 

# --- Izbor opcije toplotne pumpe (Ažurirana za dinamičke kontakt podatke i ParseMode) ---
async def select_hp_option(update: Update, context: object) -> int:
    """Korisnik je izabrao specifičnu opciju toplotne pumpe."""
    query = update.callback_query
    await query.answer()

    context.user_data['option_selected_key'] = query.data.replace("hp_", "")
    context.user_data['option_selected_name'] = TEXTS[context.user_data['language']].get(context.user_data['option_selected_key'], context.user_data['option_selected_key'])
    lang = context.user_data['language']
    country_key = context.user_data['country_key']

    if country_key == "srbija":
        manufacturer_data = contact_info[country_key]['manufacturer']
        info_text = TEXTS[lang]["microma_info"].format(
            phone=manufacturer_data['phone'],
            email=manufacturer_data['email'],
            website=manufacturer_data['website'] if manufacturer_data['website'] != ':' else TEXTS[lang]["N/A"]
        )
    else: # crna_gora
        contractor_data = contact_info[country_key]['contractor'] # U Crnoj Gori je to izvođač
        info_text = TEXTS[lang]["instal_m_info"].format(
            phone=contractor_data['phone'],
            email=contractor_data['email'],
            website=contractor_data['website'] if contractor_data['website'] != ':' else TEXTS[lang]["N/A"],
            telegram=contractor_data['telegram'] if contractor_data['telegram'] != ':' else TEXTS[lang]["N/A"]
        )
    
    await query.edit_message_text(info_text, parse_mode=ParseMode.MARKDOWN) # Koristi Markdown za boldovanje
    
    context.user_data.clear()
    return ConversationHandler.END

# --- Cancel komanda (nepromenjena) ---
async def cancel(update: Update, context: object) -> int:
    """Omogućava korisniku da prekine konverzaciju u bilo kom trenutku."""
    lang = context.user_data.get('language', 'sr') # Default na srpski ako nije izabran
    await update.message.reply_text(TEXTS[lang]["cancel_command"])
    context.user_data.clear()
    return ConversationHandler.END

# --- Fallback za nepoznate poruke unutar konverzacije (nepromenjena) ---
async def fallback(update: Update, context: object) -> int:
    """Hvata nepoznate poruke unutar konverzacije i obaveštava korisnika."""
    lang = context.user_data.get('language', 'sr')
    await update.message.reply_text(TEXTS[lang]["unknown_command"])
    return ConversationHandler.END

# --- Glavna funkcija za pokretanje bota ---
def main() -> None:
    # Učitaj token i URL iz .env fajla
    TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN")
    WEB_SERVICE_URL = os.getenv("WEB_SERVICE_URL")
    PORT = int(os.environ.get("PORT", "8080")) # Render obično koristi PORT varijablu okruženja

    if not TELEGRAM_BOT_TOKEN:
        logger.error("BOT_TOKEN env variable not set!")
        exit(1)
    if not WEB_SERVICE_URL:
        logger.error("WEB_SERVICE_URL env variable not set! This is required for webhook.")
        exit(1)

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECTING_LANGUAGE: [CallbackQueryHandler(select_language, pattern="^lang_")],
            SELECTING_COUNTRY: [CallbackQueryHandler(select_country, pattern="^country_")],
            SELECTING_HEATING_TYPE: [CallbackQueryHandler(select_heating_or_hp, pattern="^type_")],
            SELECTING_INSTALLATION_OPTION: [CallbackQueryHandler(select_installation_option, pattern="^inst_")],
            ENTERING_OBJECT_DETAILS: [
                MessageHandler(filters.TEXT | filters.PHOTO, enter_object_details),
                CommandHandler("cancel", cancel)
            ],
            CONFIRM_SEND_INQUIRY: [CallbackQueryHandler(confirm_send_inquiry, pattern="^confirm_")],
            SELECTING_HP_TYPE: [CallbackQueryHandler(select_hp_option, pattern="^hp_")],
        },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(filters.ALL, fallback)],
    )

    application.add_handler(conv_handler)
    
    # --- Postavljanje Webhooka za Render ---
    # Za Render, Telegram šalje update-ove na WEB_SERVICE_URL
    # Aplikacija sluša na PORT-u koji je definisan u okruženju (Render dodeljuje dinamički)
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TELEGRAM_BOT_TOKEN, # URL putanja bi trebalo da bude vaš token radi sigurnosti
        webhook_url=f"{WEB_SERVICE_URL}/{TELEGRAM_BOT_TOKEN}",
        allowed_updates=Update.ALL_TYPES # Omogućava sve tipove ažuriranja
    )
    logger.info(f"Bot pokrenut u Webhook modu na portu {PORT}. Webhook URL: {WEB_SERVICE_URL}/{TELEGRAM_BOT_TOKEN}")

if __name__ == '__main__':
    # Samo za lokalno testiranje, ako želite polling umesto webhooka:
    # If os.getenv("ON_RENDER") != "true":
    #    main_polling() # Kreirajte funkciju main_polling koja koristi application.run_polling()
    # else:
    main()