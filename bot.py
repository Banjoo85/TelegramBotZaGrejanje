import logging
import json
import os
import yagmail
import datetime
import html # Dodato za error_handler
import traceback # Dodato za error_handler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters
)
from telegram.constants import ParseMode
from dotenv import load_dotenv

# Učitavanje environment varijabli
load_dotenv()

# Inicijalni print da se potvrdi pokretanje fajla
print(f"Bot se pokreće sa najnovijim kodom! Vreme pokretanja: {datetime.datetime.now()}")

# Konfiguracija logginga
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Stanja za ConversationHandler ---
AWAITING_SKETCH = 1

# --- Podaci za Slanje Emaila i Kontakti ---
SENDER_EMAIL = os.environ.get('EMAIL_SENDER_EMAIL')
SENDER_PASSWORD = os.environ.get('EMAIL_APP_PASSWORD')
ADMIN_BCC_EMAIL = os.environ.get('ADMIN_BCC_EMAIL', "banjooo85@gmail.com")
# VAŠ TELEGRAM ID za obaveštenja o greškama (promenite ovo!)
DEVELOPER_CHAT_ID = os.environ.get('TELEGRAM_DEVELOPER_CHAT_ID') # Postavite ovo u .env ili Renderu


if not SENDER_EMAIL:
    logger.critical("EMAIL_SENDER_EMAIL environment variable not set. Bot cannot send emails.")
if not SENDER_PASSWORD:
    logger.critical("EMAIL_APP_PASSWORD environment variable not set. Bot cannot send emails.")
if not ADMIN_BCC_EMAIL:
    logger.warning("ADMIN_BCC_EMAIL environment variable not set, using default 'banjooo85@gmail.com'.")
if not DEVELOPER_CHAT_ID:
    logger.warning("TELEGRAM_DEVELOPER_CHAT_ID environment variable not set. Error notifications to developer will be skipped.")
else:
    try:
        DEVELOPER_CHAT_ID = int(DEVELOPER_CHAT_ID) # Osigurajte da je int
    except ValueError:
        logger.critical("TELEGRAM_DEVELOPER_CHAT_ID is not a valid integer. Error notifications to developer will be skipped.")
        DEVELOPER_CHAT_ID = None


CONTRACTOR_SRB_HEATING = {
    "name": "Igor Bošković",
    "phone": "+381 60 3932566",
    "email": "boskovicigor83@gmail.com",
    "telegram": "@IgorNS1983",
    "website": None 
}

CONTRACTOR_SRB_HP = {
    "firm": "Microma",
    "contact_person": "Borislav Dakić",
    "phone": "+381 63 582068",
    "email": "office@microma.rs",
    "website": "https://microma.rs"
}

CONTRACTOR_MNE_HP = {
    "firm": "Instal M",
    "contact_person": "Ivan Mujović",
    "phone": "+382 67 423 237",
    "email": "office@instalm.me",
    "website": None,
    "telegram": "@ivanmujovic"
}

HEAT_PUMP_TYPES_SR = {
    "water_to_water": "Voda-Voda Toplotna Pumpa",
    "air_to_water": "Vazduh-Voda Toplotna Pumpa"
}

HEAT_PUMP_TYPES_EN = {
    "water_to_water": "Water-to-Water Heat Pump",
    "air_to_water": "Air-to-Water Heat Pump"
}

HEAT_PUMP_TYPES_RU = {
    "water_to_water": "Тепловой насос Вода-Вода",
    "air_to_water": "Тепловой насос Воздух-Вода"
}

HEAT_PUMP_OFFERS = {
    "srbija": {
        "options": ["water_to_water", "air_to_water"],
        "contractor": CONTRACTOR_SRB_HP
    },
    "crna_gora": {
        "options": ["air_to_water"], 
        "contractor": CONTRACTOR_MNE_HP
    }
}

user_data = {}

def load_messages(lang_code: str):
    effective_lang_code = lang_code if lang_code else 'en'
    file_path = f'messages_{effective_lang_code}.json'
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            messages = json.load(f)
            logger.debug(f"Uspešno učitane poruke iz {file_path}")
            return messages
    except FileNotFoundError:
        logger.error(f"Message file for {effective_lang_code} not found at {file_path}. Defaulting to English.")
        with open(f'messages_en.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.critical(f"GREŠKA: JSON format error in {file_path}: {e}")
        logger.critical(f"Please check JSON syntax in {file_path} using a validator like jsonlint.com")
        with open(f'messages_en.json', 'r', encoding='utf-8') as f:
            return json.load(f)

async def send_email_with_sketch(recipient: str, subject: str, body: str, file_path: str, installation_type_info: str, telegram_username: str = "N/A") -> None:
    logger.info(f"Pokušavam da pošaljem email sa skicom. Primalac: {recipient}, Tema: {subject}, Fajl: {file_path}")
    try:
        if not SENDER_EMAIL or not SENDER_PASSWORD:
            logger.error("GREŠKA: EMAIL_SENDER_EMAIL ili EMAIL_APP_PASSWORD nisu postavljeni za slanje emaila sa skicom.")
            return

        logger.debug(f"Pokušavam da se povežem na SMTP server sa: {SENDER_EMAIL}")
        yag = yagmail.SMTP(user=SENDER_EMAIL, password=SENDER_PASSWORD, host='smtp.gmail.com', port=587, tls=True)
        logger.info("Uspesno kreiran yagmail SMTP objekat za slanje sa skicom.")
        
        full_body = (
            f"Primljen novi zahtev za ponudu za Grejnu Instalaciju:\n\n"
            f"Tip izabrane grejne instalacije: {installation_type_info}\n"
            f"Telegram ID korisnika: {telegram_username}\n\n"
            f"{body}"
        )

        contents = [full_body]
        if file_path and os.path.exists(file_path):
            contents.append(file_path)
            logger.info(f"Fajl '{file_path}' uspešno dodan kao prilog za email.")
        else:
            logger.warning(f"Fajl '{file_path}' ne postoji ili putanja nije validna. Email će biti poslat bez priloga.")

        yag.send(
            to=recipient,
            subject=subject,
            contents=contents,
            bcc=ADMIN_BCC_EMAIL
        )
        logger.info(f"Email sa skicom uspešno poslat na {recipient} sa BCC na {ADMIN_BCC_EMAIL}.")
    except yagmail.SMTPAuthenticationError as e:
        logger.critical(f"GREŠKA U AUTENTIFIKACIJI YAGMAIL-a (sa skicom): {e}")
        logger.critical("Proverite da li su EMAIL_SENDER_EMAIL i EMAIL_APP_PASSWORD ispravni (koristite 16-cifrenu app lozinku).")
    except Exception as e:
        logger.error(f"NEPREDVIĐENA GREŠKA prilikom slanja emaila sa skicom: {e}", exc_info=True)
    finally:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"Obrisan fajl: {file_path}")
            except OSError as e:
                logger.error(f"GREŠKA prilikom brisanja fajla {file_path}: {e}")

async def send_email_without_attachment(recipient: str, subject: str, body: str, telegram_username: str = "N/A") -> None:
    logger.info(f"Pokušavam da pošaljem email BEZ skice. Primalac: {recipient}, Tema: {subject}")
    try:
        if not SENDER_EMAIL or not SENDER_PASSWORD:
            logger.error("GREŠKA: EMAIL_SENDER_EMAIL ili EMAIL_APP_PASSWORD nisu postavljeni za slanje bez priloga.")
            return

        logger.debug(f"Pokušavam da se povežem na SMTP server (bez priloga) sa: {SENDER_EMAIL}")
        yag = yagmail.SMTP(user=SENDER_EMAIL, password=SENDER_PASSWORD, host='smtp.gmail.com', port=587, tls=True)
        logger.info("Uspesno kreiran yagmail SMTP objekat za slanje bez priloga.")

        full_body = (
            f"Primljen novi zahtev za ponudu:\n\n"
            f"Telegram ID korisnika: {telegram_username}\n"
            f"Ime: {telegram_username}" # Dodato ime korisnika u email
            f"\n\n{body}"
        )

        logger.info(f"Šaljem email (bez priloga) na: {recipient}, BCC: {ADMIN_BCC_EMAIL}")
        yag.send(
            to=recipient,
            subject=subject,
            contents=full_body,
            bcc=ADMIN_BCC_EMAIL
        )
        logger.info(f"Email (bez priloga) uspešno poslat na {recipient} sa BCC na {ADMIN_BCC_EMAIL}.")
    except yagmail.SMTPAuthenticationError as e:
        logger.critical(f"GREŠKA U AUTENTIFIKACIJI YAGMAIL-a (bez priloga): {e}")
        logger.critical("Proverite da li su EMAIL_SENDER_EMAIL i EMAIL_APP_PASSWORD ispravni (koristite 16-cifrenu app lozinku).")
    except Exception as e:
        logger.error(f"NEPREDVIĐENA GREŠKA prilikom slanja emaila (bez priloga): {e}", exc_info=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    # Inicijalizacija user_data za korisnika ako ne postoji
    if user_id not in user_data:
        user_data[user_id] = {'lang': 'en'} # Podrazumevani jezik dok korisnik ne izabere
        logger.debug(f"Inicijalizovan user_data za novog korisnika {user_id}: {user_data[user_id]}")
    
    messages = load_messages(user_data[user_id]['lang'])

    keyboard = [
        [InlineKeyboardButton("Srpski 🇷🇸", callback_data='lang_sr')],
        [InlineKeyboardButton("English 🇬🇧", callback_data='lang_en')],
        [InlineKeyboardButton("Русский 🇷🇺", callback_data='lang_ru')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(messages["start_message"], reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    callback_data = query.data
    logger.debug(f"Obradjuje se callback_data: {callback_data} za korisnika {user_id}")
    
    # --- KRITIČNA IZMENA: Proverite i inicijalizujte user_data ako nedostaje ---
    if user_id not in user_data:
        user_data[user_id] = {'lang': 'en'} # Podrazumevani jezik ako korisnik nije prošao kroz /start
        logger.warning(f"user_data[{user_id}] nije pronađen. Inicijalizovan sa podrazumevanim jezikom 'en'.")
        # Nakon inicijalizacije, preusmerite korisnika na start meni, jer mu nedostaje kontekst
        messages = load_messages(user_data[user_id]['lang']) # Učitajte poruke sa default jezikom
        await query.edit_message_text(text=messages["session_expired_restart_needed"], parse_mode=ParseMode.MARKDOWN_V2) # Obavestite korisnika
        await start(update, context) # Pozovite start handler da mu prikažete početni meni
        return ConversationHandler.END # Završite ConversationHandler ako je u njemu, jer je sesija resetovana
    # --- KRAJ KRITIČNE IZMENE ---

    logger.debug(f"user_data[{user_id}] na početku callback-a: {user_data.get(user_id)}")

    if callback_data.startswith('lang_'):
        lang_code = callback_data.split('_')[1]
        user_data[user_id]['lang'] = lang_code
        messages = load_messages(lang_code)
        await query.edit_message_text(text=messages["language_selected"])
        logger.debug(f"Jezik postavljen na {lang_code}. user_data[{user_id}]: {user_data[user_id]}")
        
        await choose_country(update, context, user_id)

    elif callback_data.startswith('country_'):
        country_code = "_".join(callback_data.split('_')[1:]) 
        user_data[user_id]['country'] = country_code
        
        messages = load_messages(user_data[user_id]['lang'])
        country_name_key = f"{country_code}_name"
        country_display_name = messages.get(country_name_key, country_code.capitalize())
        
        await query.edit_message_text(text=messages["country_selected"].format(country_name=country_display_name))
        logger.debug(f"Zemlja postavljena na {country_code}. user_data[{user_id}]: {user_data[user_id]}")
        
        await show_main_menu(update, context, user_id)

    elif callback_data.startswith('menu_'):
        menu_option = callback_data.split('_')[1]
        messages = load_messages(user_data[user_id]['lang'])
        logger.debug(f"Izabrana opcija menija: {menu_option}. user_data[{user_id}]: {user_data[user_id]}")
        
        if menu_option == 'quote':
            await query.edit_message_text(text=messages["request_quote_button"] + "...")
            await choose_installation_type_menu(update, context, user_id)
        elif menu_option == 'services':
            await query.edit_message_text(text=messages["services_info_button"] + "...")
            await query.message.reply_text("Detalji o našim uslugama će biti dodati uskoro. Hvala na interesovanju!", parse_mode=ParseMode.MARKDOWN_V2)
            await show_main_menu(update, context, user_id)
        elif menu_option == 'faq':
            await query.edit_message_text(text=messages["faq_button"] + "...")
            await query.message.reply_text("Česta pitanja će biti dostupna uskoro. Radimo na tome!", parse_mode=ParseMode.MARKDOWN_V2)
            await show_main_menu(update, context, user_id)
        elif menu_option == 'contact':
            await query.edit_message_text(text=messages["contact_button"] + "...")
            contractor = CONTRACTOR_SRB_HEATING # Za opštu "Kontakt" opciju, koristimo glavnog izvođača za Srbiju
            
            website_info = f"\nWeb: `{contractor['website']}`" if contractor['website'] else ""
            telegram_info = f"\nTelegram: `{contractor.get('telegram')}`" if contractor.get('telegram') else ""

            contact_info_text = messages["contractor_info"].format(
                phone=contractor['phone'],
                email=f"`{contractor['email']}`", # Dodato ` `
                website_info=website_info,
                telegram_info=telegram_info
            )
            try:
                await query.message.reply_text(contact_info_text, parse_mode=ParseMode.MARKDOWN_V2)
                logger.debug(f"Prikazan kontakt info za opciju 'Kontakt': {contact_info_text}")
            except Exception as e:
                logger.error(f"GREŠKA prilikom slanja kontakt info teksta za opciju 'Kontakt': {e}", exc_info=True)
                await query.message.reply_text("Došlo je do greške prilikom prikazivanja kontakt podataka. Molimo pokušajte ponovo.", parse_mode=ParseMode.MARKDOWN_V2)

            await show_main_menu(update, context, user_id)
            return None 

    elif callback_data.startswith('type_'):
        installation_type = callback_data.split('_')[1]
        user_data[user_id]['installation_type'] = installation_type
        messages = load_messages(user_data[user_id]['lang'])
        current_country = user_data[user_id].get('country') 

        logger.debug(f"Tip instalacije odabran: {installation_type}. ")
        logger.debug(f"current_country u user_data: {current_country}. ")
        logger.debug(f"user_data[{user_id}]: {user_data[user_id]}")
        
        await query.edit_message_text(text=messages["heat_pump_button"] + " je odabrana." if installation_type == 'heatpump' else messages["heating_installation_button"] + " je odabrana.")

        if installation_type == 'heating':
            logger.info(f"Korisnik {user_id}: Odabrana Grejna Instalacija. Dalje na meni za grejanje.")
            await choose_heating_system_menu(update, context, user_id)
        elif installation_type == 'heatpump':
            logger.info(f"Korisnik {user_id}: Odabrana Toplotna Pumpa. Zemlja: {current_country}")
            
            hp_offers_crna_gora_entry = HEAT_PUMP_OFFERS.get('crna_gora', {})
            hp_options_crna_gora = hp_offers_crna_gora_entry.get('options', [])
            logger.debug(f"Korisnik {user_id}: Proveravam uslove za Crnu Goru:")
            logger.debug(f"   current_country == 'crna_gora': {current_country == 'crna_gora'} (current_country: '{current_country}')")
            logger.debug(f"   len(hp_options_crna_gora) == 1: {len(hp_options_crna_gora) == 1} (options: {hp_options_crna_gora}, dužina: {len(hp_options_crna_gora)})")
            
            if hp_options_crna_gora:
                logger.debug(f"   hp_options_crna_gora[0] == 'air_to_water': {hp_options_crna_gora[0] == 'air_to_water'}")
            else:
                logger.debug(f"   hp_options_crna_gora je prazna, ne može se proveriti hp_options_crna_gora[0]")

            if current_country == 'crna_gora' and \
               len(hp_options_crna_gora) == 1 and \
               hp_options_crna_gora[0] == 'air_to_water':
                
                logger.info(f"Korisnik {user_id}: Svi uslovi za Crnu Goru su ispunjeni. Preskače se izbor tipa TP.")

                contractor = CONTRACTOR_MNE_HP
                chosen_hp_name_dict = {}
                if user_data[user_id]['lang'] == 'sr':
                    chosen_hp_name_dict = HEAT_PUMP_TYPES_SR
                elif user_data[user_id]['lang'] == 'en':
                    chosen_hp_name_dict = HEAT_PUMP_TYPES_EN
                elif user_data[user_id]['lang'] == 'ru':
                    chosen_hp_name_dict = HEAT_PUMP_TYPES_RU

                chosen_hp_name = chosen_hp_name_dict.get('air_to_water', 'Vazduh-Voda Toplotna Pumpa')
                country_display_name = messages.get(f"{current_country}_name", current_country.capitalize())
                website_info = f"\nWeb: `{contractor['website']}`" if contractor['website'] else "" # Dodato ` `
                
                telegram_info = f"\nTelegram: `{contractor.get('telegram')}`" if contractor.get('telegram') else "" # Dodato ` `

                telegram_username = update.effective_user.username if update.effective_user.username else 'N/A'

                subject = f"Novi zahtev za ponudu: Toplotna Pumpa ({chosen_hp_name}) od korisnika {user_id}"
                body_email = (
                    f"Korisnik je izabrao toplotnu pumpu tipa: {chosen_hp_name} u zemlji: {country_display_name}.\n"
                    f"ID korisnika: {user_id}\n"
                    f"Ime: {update.effective_user.full_name}\n"
                    f"Username: @{telegram_username}"
                )
                await send_email_without_attachment(
                    recipient=contractor['email'],
                    subject=subject,
                    body=body_email,
                    telegram_username=telegram_username
                )
                
                logger.debug(f"Korisnik {user_id}: Priprema se poruka sa podacima Instal M.")
                try:
                    await query.message.reply_text(
                        text=messages["hp_offer_info"].format(
                            hp_type=chosen_hp_name, 
                            country_name=country_display_name,
                            phone=contractor['phone'],
                            email=f"`{contractor['email']}`", # Dodato ` `
                            website_info=website_info,
                            telegram_info=telegram_info
                        ),
                        parse_mode=ParseMode.MARKDOWN_V2
                    )
                    logger.info(f"Korisnik {user_id}: Poruka sa podacima Instal M uspešno poslata.")
                except Exception as e:
                    logger.error(f"Korisnik {user_id}: GREŠKA prilikom slanja podataka Instal M: {e}", exc_info=True)
                    await query.message.reply_text("Došlo je do greške prilikom prikazivanja podataka. Molimo pokušajte ponovo.", parse_mode=ParseMode.MARKDOWN_V2)

                logger.info(f"Korisnik {user_id}: Vraćanje na glavni meni.")
                await show_main_menu(update, context, user_id)
                return 

            else:
                logger.debug(f"Korisnik {user_id}: Nije Crna Gora ili više opcija. Prikazuje se izbor tipa TP.")
                await show_heat_pump_options(update, context, user_id)
            return

    elif callback_data.startswith('system_'):
        heating_system_type = callback_data.split('_')[1]
        user_data[user_id]['heating_system_type'] = heating_system_type
        messages = load_messages(user_data[user_id]['lang'])
        logger.debug(f"Tip grejnog sistema odabran: {heating_system_type}. user_data[{user_id}]: {user_data[user_id]}")

        response_text = ""
        if heating_system_type == 'radiators':
            response_text = messages["radiators_button"]
        elif heating_system_type == 'fan_coil':
            response_text = messages["fan_coil_button"]
        elif heating_system_type == 'underfloor':
            response_text = messages["underfloor_heating_button"]
        elif heating_system_type == 'underfloor_fan_coil':
            response_text = messages["underfloor_fan_coil_button"]
        elif heating_system_type == 'complete_hp':
            response_text = messages["complete_with_hp_button"]
            user_data[user_id]['installation_type'] = 'heatpump_and_heating'
            await query.edit_message_text(text=f"{response_text} je izabrana. ") 
            
            contractor = CONTRACTOR_SRB_HEATING
            contractor_email_target = contractor["email"]
            telegram_username = update.effective_user.username if update.effective_user.username else 'N/A'
            
            subject = f"Novi zahtev: {response_text} od korisnika {user_id}"
            body_email = (
                f"Korisnik je izabrao opciju: {response_text}.\n"
                f"ID korisnika: {user_id}\n"
                f"Ime: {update.effective_user.full_name}\n"
                f"Username: @{telegram_username}"
            )
            
            await send_email_without_attachment(
                recipient=contractor_email_target,
                subject=subject,
                body=body_email,
                telegram_username=telegram_username
            )

            website_info = f"\nWeb: `{contractor['website']}`" if contractor['website'] else "" # Dodato ` `
            telegram_info = f"\nTelegram: `{contractor.get('telegram')}`" if contractor.get('telegram') else "" # Dodato ` `
            
            contact_info_text = messages["contractor_info"].format(
                phone=contractor['phone'],
                email=f"`{contractor['email']}`", # Dodato ` `
                website_info=website_info,
                telegram_info=telegram_info
            )
            try:
                await query.message.reply_text(contact_info_text, parse_mode=ParseMode.MARKDOWN_V2)
                logger.debug(f"Prikazan kontakt info za 'Komplet sa toplotnom pumpom': {contact_info_text}")
            except Exception as e:
                logger.error(f"GREŠKA prilikom slanja kontakt info teksta za 'Komplet sa toplotnom pumpom': {e}", exc_info=True)
                await query.message.reply_text("Došlo je do greške prilikom prikazivanja kontakt podataka. Molimo pokušajte ponovo.", parse_mode=ParseMode.MARKDOWN_V2)

            await show_main_menu(update, context, user_id)
            return

        elif heating_system_type == 'existing_heating':
            await query.edit_message_text(text=messages["existing_installation_button"] + " je izabrana.")
            await query.message.reply_text(messages["redirect_to_hp"], parse_mode=ParseMode.MARKDOWN_V2)
            await show_main_menu(update, context, user_id)
            return

        await query.edit_message_text(text=f"{response_text} je izabrana.")

        # PROVERA DA LI SE OVDE UVEK PRIKAZUJU PODACI ZA GREJNE INSTALACIJE
        if user_data[user_id].get('installation_type') == 'heating': 
            contractor = CONTRACTOR_SRB_HEATING
            contractor_email_target = contractor["email"]
            telegram_username = update.effective_user.username if update.effective_user.username else 'N/A'
            
            subject = f"Novi zahtev: Grejna instalacija ({response_text}) od korisnika {user_id}"
            body_email = (
                f"Korisnik je izabrao tip grejne instalacije: {response_text}.\n"
                f"ID korisnika: {user_id}\n"
                f"Ime: {update.effective_user.full_name}\n"
                f"Username: @{telegram_username}"
            )
            
            await send_email_without_attachment(
                recipient=contractor_email_target,
                subject=subject,
                body=body_email,
                telegram_username=telegram_username
            )

            website_info = f"\nWeb: `{contractor['website']}`" if contractor['website'] else "" # Dodato ` `
            telegram_info = f"\nTelegram: `{contractor.get('telegram')}`" if contractor.get('telegram') else "" # Dodato ` `

            logger.debug(f"Preparing contractor_info_text with: phone={contractor['phone']}, email={contractor['email']}, website_info='{website_info}', telegram_info='{telegram_info}'")
            logger.debug(f"Raw message template (contractor_info): {messages['contractor_info']}")

            contact_info_text = messages["contractor_info"].format(
                phone=contractor['phone'],
                email=f"`{contractor['email']}`", # Dodato ` `
                website_info=website_info,
                telegram_info=telegram_info
            )
            logger.debug(f"Generated contact_info_text for heating installation: {contact_info_text}")

            try:
                await query.message.reply_text(contact_info_text, parse_mode=ParseMode.MARKDOWN_V2)
                logger.debug(f"Prikazan kontakt info za grejne instalacije: {contact_info_text}")
            except Exception as e:
                logger.error(f"GREŠKA prilikom slanja kontakt info teksta za grejne instalacije: {e}", exc_info=True)
                await query.message.reply_text("Došlo je do greške prilikom prikazivanja kontakt podataka za grejne instalacije. Molimo pokušajte ponovo.", parse_mode=ParseMode.MARKDOWN_V2)

        keyboard = [
            [InlineKeyboardButton(messages["send_sketch_button"], callback_data='send_sketch_now')],
            [InlineKeyboardButton(messages["no_sketch_button"], callback_data='no_sketch_needed')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(messages["request_sketch_optional"], reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2)
        
        return AWAITING_SKETCH

    elif callback_data == 'no_sketch_needed':
        user_id = query.from_user.id
        # Proverite da li user_data[user_id] postoji pre pristupa
        if user_id not in user_data:
            user_data[user_id] = {'lang': 'en'} # Fallback
            logger.warning(f"user_data[{user_id}] nije pronađen u 'no_sketch_needed'. Inicijalizovan.")
            messages = load_messages(user_data[user_id]['lang']) # Učitajte poruke
            await query.edit_message_text(text=messages["session_expired_restart_needed"], parse_mode=ParseMode.MARKDOWN_V2)
            await start(update, context)
            return ConversationHandler.END

        messages = load_messages(user_data[user_id]['lang'])
        logger.info(f"Korisnik {user_id}: Odabrano da ne želi da pošalje skicu.")
        await query.edit_message_text(messages["no_sketch_confirmation"], parse_mode=ParseMode.MARKDOWN_V2)
        await show_main_menu(update, context, user_id)
        return ConversationHandler.END

    elif callback_data.startswith('hp_type_'):
        hp_type_chosen = callback_data.split('_')[2] 
        user_id = query.from_user.id
        # Proverite da li user_data[user_id] i 'lang'/'country' postoje pre pristupa
        if user_id not in user_data or 'lang' not in user_data[user_id] or 'country' not in user_data[user_id]:
            user_data[user_id] = {'lang': 'en'} # Fallback
            logger.warning(f"user_data[{user_id}] nije potpuno inicijalizovan u 'hp_type_'. Inicijalizovan.")
            messages = load_messages(user_data[user_id]['lang']) # Učitajte poruke
            await query.edit_message_text(text=messages["session_expired_restart_needed"], parse_mode=ParseMode.MARKDOWN_V2)
            await start(update, context)
            return ConversationHandler.END

        current_lang = user_data[user_id]['lang']
        current_country = user_data[user_id]['country']
        messages = load_messages(current_lang)
        logger.debug(f"Tip toplotne pumpe odabran: {hp_type_chosen}. user_data[{user_id}]: {user_data[user_id]}")

        country_data = HEAT_PUMP_OFFERS.get(current_country)
        if not country_data:
            await query.edit_message_text(text="Greška: Podaci za izabranu zemlju nisu pronađeni.", parse_mode=ParseMode.MARKDOWN_V2)
            return ConversationHandler.END

        contractor = country_data.get("contractor")
        
        hp_names_dict = {}
        if current_lang == 'sr':
            hp_names_dict = HEAT_PUMP_TYPES_SR
        elif current_lang == 'en':
            hp_names_dict = HEAT_PUMP_TYPES_EN
        elif current_lang == 'ru':
            hp_names_dict = HEAT_PUMP_TYPES_RU
        
        chosen_hp_name = hp_names_dict.get(hp_type_chosen, hp_type_chosen)
        
        country_name_key = f"{current_country}_name"
        country_display_name = messages.get(country_name_key, current_country.capitalize())

        website_info = f"\nWeb: `{contractor['website']}`" if contractor['website'] else "" # Dodato ` `
        telegram_username = update.effective_user.username if update.effective_user.username else 'N/A'

        subject = f"Novi zahtev za ponudu: Toplotna Pumpa ({chosen_hp_name}) od korisnika {user_id}"
        body_email = (
            f"Korisnik je izabrao toplotnu pumpu tipa: {chosen_hp_name} u zemlji: {country_display_name}.\n"
            f"ID korisnika: {user_id}\n"
            f"Ime: {update.effective_user.full_name}\n"
            f"Username: @{telegram_username}"
        )
        await send_email_without_attachment(
            recipient=contractor['email'],
            subject=subject,
            body=body_email,
            telegram_username=telegram_username
        )
        
        telegram_info = f"\nTelegram: `{contractor.get('telegram')}`" if contractor.get('telegram') else "" # Dodato ` `

        logger.debug(f"Preparing hp_offer_info text for HP type: {chosen_hp_name}, country: {country_display_name}")
        logger.debug(f"Contractor details: phone={contractor['phone']}, email={contractor['email']}, website_info='{website_info}', telegram_info='{telegram_info}'")
        logger.debug(f"Raw message template (hp_offer_info): {messages['hp_offer_info']}")

        try:
            await query.edit_message_text(
                text=messages["hp_offer_info"].format(
                    hp_type=chosen_hp_name,
                    country_name=country_display_name,
                    phone=contractor['phone'],
                    email=f"`{contractor['email']}`", # Dodato ` `
                    website_info=website_info,
                    telegram_info=telegram_info
                ),
                parse_mode=ParseMode.MARKDOWN_V2
            )
            logger.debug(f"HP offer info sent. Message: {messages['hp_offer_info'].format(hp_type=chosen_hp_name, country_name=country_display_name, phone=contractor['phone'], email=contractor['email'], website_info=website_info, telegram_info=telegram_info)}")
        except Exception as e:
            logger.error(f"GREŠKA prilikom slanja HP ponude teksta: {e}", exc_info=True)
            await query.message.reply_text("Došlo je do greške prilikom prikazivanja podataka o toplotnoj pumpi. Molimo pokušajte ponovo.", parse_mode=ParseMode.MARKDOWN_V2)

        await show_main_menu(update, context, user_id)
        return ConversationHandler.END


async def choose_country(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    # Proverite da li user_data[user_id] postoji pre pristupa
    if user_id not in user_data:
        user_data[user_id] = {'lang': 'en'} # Fallback
        logger.warning(f"user_data[{user_id}] nije pronađen u 'choose_country'. Inicijalizovan.")
        messages = load_messages(user_data[user_id]['lang'])
        await context.bot.send_message(chat_id=user_id, text=messages["session_expired_restart_needed"], parse_mode=ParseMode.MARKDOWN_V2)
        return

    messages = load_messages(user_data[user_id]['lang'])
    logger.debug(f"Prikazivanje izbora zemlje za korisnika {user_id}. user_data[{user_id}]: {user_data[user_id]}")

    keyboard = [
        [InlineKeyboardButton(messages["srbija_button"], callback_data='country_srbija')],
        [InlineKeyboardButton(messages["crna_gora_button"], callback_data='country_crna_gora')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=user_id, text=messages["choose_country"], reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    # Proverite da li user_data[user_id] postoji pre pristupa
    if user_id not in user_data:
        user_data[user_id] = {'lang': 'en'} # Fallback
        logger.warning(f"user_data[{user_id}] nije pronađen u 'show_main_menu'. Inicijalizovan.")
        messages = load_messages(user_data[user_id]['lang'])
        await context.bot.send_message(chat_id=user_id, text=messages["session_expired_restart_needed"], parse_mode=ParseMode.MARKDOWN_V2)
        return

    messages = load_messages(user_data[user_id]['lang'])
    logger.debug(f"Prikazivanje glavnog menija za korisnika {user_id}. user_data[{user_id}]: {user_data[user_id]}")
    
    keyboard = [
        [InlineKeyboardButton(messages["request_quote_button"], callback_data='menu_quote')],
        [InlineKeyboardButton(messages["services_info_button"], callback_data='menu_services')],
        [InlineKeyboardButton(messages["faq_button"], callback_data='menu_faq')],
        [InlineKeyboardButton(messages["contact_button"], callback_data='menu_contact')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=user_id, text=messages["main_menu_greeting"], reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2)

async def choose_installation_type_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    # Proverite da li user_data[user_id] postoji pre pristupa
    if user_id not in user_data:
        user_data[user_id] = {'lang': 'en'} # Fallback
        logger.warning(f"user_data[{user_id}] nije pronađen u 'choose_installation_type_menu'. Inicijalizovan.")
        messages = load_messages(user_data[user_id]['lang'])
        await context.bot.send_message(chat_id=user_id, text=messages["session_expired_restart_needed"], parse_mode=ParseMode.MARKDOWN_V2)
        return

    messages = load_messages(user_data[user_id]['lang'])
    logger.debug(f"Prikazivanje izbora tipa instalacije za korisnika {user_id}. user_data[{user_id}]: {user_data[user_id]}")
    
    keyboard = [
        [InlineKeyboardButton(messages["heating_installation_button"], callback_data='type_heating')],
        [InlineKeyboardButton(messages["heat_pump_button"], callback_data='type_heatpump')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=user_id, text=messages["choose_installation_type"], reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2)

async def choose_heating_system_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    # Proverite da li user_data[user_id] postoji pre pristupa
    if user_id not in user_data:
        user_data[user_id] = {'lang': 'en'} # Fallback
        logger.warning(f"user_data[{user_id}] nije pronađen u 'choose_heating_system_menu'. Inicijalizovan.")
        messages = load_messages(user_data[user_id]['lang'])
        await context.bot.send_message(chat_id=user_id, text=messages["session_expired_restart_needed"], parse_mode=ParseMode.MARKDOWN_V2)
        return

    messages = load_messages(user_data[user_id]['lang'])
    logger.debug(f"Prikazivanje izbora grejnog sistema za korisnika {user_id}. user_data[{user_id}]: {user_data[user_id]}")

    keyboard = [
        [InlineKeyboardButton(messages["radiators_button"], callback_data='system_radiators')],
        [InlineKeyboardButton(messages["fan_coil_button"], callback_data='system_fan_coil')],
        [InlineKeyboardButton(messages["underfloor_heating_button"], callback_data='system_underfloor')],
        [InlineKeyboardButton(messages["underfloor_fan_coil_button"], callback_data='system_underfloor_fan_coil')],
        [InlineKeyboardButton(messages["complete_with_hp_button"], callback_data='system_complete_hp')],
        [InlineKeyboardButton(messages["existing_installation_button"], callback_data='system_existing_heating')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=user_id, text=messages["choose_heating_system"], reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2)


async def show_heat_pump_options(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    # Proverite da li user_data[user_id] i 'lang'/'country' postoje pre pristupa
    if user_id not in user_data or 'lang' not in user_data[user_id] or 'country' not in user_data[user_id]:
        user_data[user_id] = {'lang': 'en'} # Fallback
        logger.warning(f"user_data[{user_id}] nije potpuno inicijalizovan u 'show_heat_pump_options'. Inicijalizovan.")
        messages = load_messages(user_data[user_id]['lang'])
        await context.bot.send_message(chat_id=user_id, text=messages["session_expired_restart_needed"], parse_mode=ParseMode.MARKDOWN_V2)
        return

    current_lang = user_data[user_id]['lang']
    current_country = user_data[user_id]['country']
    messages = load_messages(current_lang)
    logger.debug(f"Prikazivanje opcija TP za korisnika {user_id}. Country: {current_country}. user_data[{user_id}]: {user_data[user_id]}")
    
    keyboard = []
    
    hp_options = HEAT_PUMP_OFFERS.get(current_country, {}).get("options", [])
    
    hp_names_dict = {}
    if current_lang == 'sr':
        hp_names_dict = HEAT_PUMP_TYPES_SR
    elif current_lang == 'en':
        hp_names_dict = HEAT_PUMP_TYPES_EN
    elif current_lang == 'ru':
        hp_names_dict = HEAT_PUMP_TYPES_RU

    for hp_type_key in hp_options:
        button_text = hp_names_dict.get(hp_type_key, hp_type_key) 
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f'hp_type_{hp_type_key}')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=user_id, text=messages["choose_heat_pump_type"], reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2)


async def request_sketch_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    # Proverite da li user_data[user_id] postoji pre pristupa
    if user_id not in user_data:
        user_data[user_id] = {'lang': 'en'} # Fallback
        logger.warning(f"user_data[{user_id}] nije pronađen u 'request_sketch_entry'. Inicijalizovan.")
        messages = load_messages(user_data[user_id]['lang'])
        await update.effective_chat.send_message(
                messages.get("error_occurred", "An unexpected error occurred. Please try again or type /start.")
                # Nema parse_mode parametra, jer ova poruka ne zahteva Markdown formatiranje
            )
        return ConversationHandler.END # Završava konverzaciju i vraća na početak

    messages = load_messages(user_data[user_id]['lang'])
    logger.debug(f"Pokrenut request_sketch_entry za korisnika {user_id}. user_data[{user_id}]: {user_data[user_id]}")

    if update.callback_query and update.callback_query.data == 'send_sketch_now':
        await update.callback_query.edit_message_text(text=messages["request_sketch"], parse_mode=ParseMode.MARKDOWN_V2)
    else:
        await update.message.reply_text(messages["request_sketch"], parse_mode=ParseMode.MARKDOWN_V2)
        
    return AWAITING_SKETCH

async def handle_sketch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    # Proverite da li user_data[user_id] postoji pre pristupa
    if user_id not in user_data:
        user_data[user_id] = {'lang': 'en'} # Fallback
        logger.warning(f"user_data[{user_id}] nije pronađen u 'handle_sketch'. Inicijalizovan.")
        messages = load_messages(user_data[user_id]['lang'])
        await update.message.reply_text(text=messages["session_expired_restart_needed"], parse_mode=ParseMode.MARKDOWN_V2)
        return ConversationHandler.END # Završava konverzaciju

    messages = load_messages(user_data[user_id]['lang'])
    logger.debug(f"Primljen fajl u handle_sketch za korisnika {user_id}. user_data[{user_id}]: {user_data[user_id]}")
    
    file_id = None
    file_name = None
    
    if update.message.document:
        file_id = update.message.document.file_id
        file_name = update.message.document.file_name
    elif update.message.photo:
        file_id = update.message.photo[-1].file_id 
        if update.message.photo[-1].file_unique_id:
             file_name = f"sketch_{update.message.photo[-1].file_unique_id}.jpg"
        else:
            file_name = f"sketch_user_{user_id}_{file_id}.jpg"
    else:
        await update.message.reply_text("Molim vas pošaljite mi skicu kao fotografiju ili dokument. Ako želite da prekinete, kucajte /cancel.", parse_mode=ParseMode.MARKDOWN_V2)
        return AWAITING_SKETCH

    file_telegram = await context.bot.get_file(file_id)
    download_path = os.path.join("/tmp", file_name) 

    os.makedirs("/tmp", exist_ok=True) 

    await file_telegram.download_to_drive(download_path)
    logger.info(f"Fajl preuzet: {download_path}")
    
    subject = f"Novi zahtev za ponudu - Grejna instalacija (Skica) od korisnika {user_id}"
    
    selected_heating_system = user_data[user_id].get('heating_system_type', 'N/A')
    messages_for_type = load_messages(user_data[user_id]['lang'])
    installation_type_info = messages_for_type.get(f"{selected_heating_system}_button", selected_heating_system) 
    
    body = f"Korisnik je poslao skicu za grejnu instalaciju." \
           f"\nID korisnika: {user_id}" \
           f"\nIme: {update.effective_user.full_name}" \
           f"\nUsername: @{update.effective_user.username if update.effective_user.username else 'N/A'}"
    
    telegram_username = update.effective_user.username if update.effective_user.username else 'N/A'

    await send_email_with_sketch(
        recipient=CONTRACTOR_SRB_HEATING["email"],
        subject=subject,
        body=body,
        file_path=download_path,
        installation_type_info=installation_type_info,
        telegram_username=telegram_username
    )

    await update.message.reply_text(messages["sketch_received"], parse_mode=ParseMode.MARKDOWN_V2)
    
    contractor = CONTRACTOR_SRB_HEATING
    
    website_info = f"\nWeb: `{contractor['website']}`" if contractor['website'] else "" # Dodato ` `
    telegram_info = f"\nTelegram: `{contractor.get('telegram')}`" if contractor.get('telegram') else "" # Dodato ` `

    contact_info_text = messages["contractor_info"].format(
        phone=contractor['phone'],
        email=f"`{contractor['email']}`", # Dodato ` `
        website_info=website_info,
        telegram_info=telegram_info
    )
    try:
        await update.message.reply_text(contact_info_text, parse_mode=ParseMode.MARKDOWN_V2)
        logger.debug(f"Prikazan kontakt info nakon slanja skice: {contact_info_text}")
    except Exception as e:
        logger.error(f"GREŠKA prilikom slanja kontakt info teksta nakon slanja skice: {e}", exc_info=True)
        await update.message.reply_text("Došlo je do greške prilikom prikazivanja kontakt podataka. Molimo pokušajte ponovo.", parse_mode=ParseMode.MARKDOWN_V2)

    await show_main_menu(update, context, user_id)
    
    return ConversationHandler.END

async def cancel_sketch_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    # Proverite da li user_data[user_id] postoji pre pristupa
    if user_id not in user_data:
        user_data[user_id] = {'lang': 'en'} # Fallback
        logger.warning(f"user_data[{user_id}] nije pronađen u 'cancel_sketch_request'. Inicijalizovan.")
        messages = load_messages(user_data[user_id]['lang']) # Učitajte poruke
        await update.message.reply_text(text=messages["session_expired_restart_needed"], parse_mode=ParseMode.MARKDOWN_V2)
        return ConversationHandler.END

    messages = load_messages(user_data[user_id]['lang'])
    logger.debug(f"Otkazivanje skice za korisnika {user_id}. user_data[{user_id}]: {user_data[user_id]}")
    await update.message.reply_text(messages["no_sketch_confirmation"], parse_mode=ParseMode.MARKDOWN_V2)
    await show_main_menu(update, context, user_id)
    return ConversationHandler.END

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    logger.error("Exception while handling an update:", exc_info=context.error)

    # Obavestite korisnika ako je moguće
    if update and update.effective_chat:
        try:
            # Učitajte poruke na osnovu jezika korisnika ako je dostupan, inače engleski
            user_id = update.effective_user.id if update.effective_user else None
            lang = user_data.get(user_id, {}).get('lang', 'en') if user_id else 'en'
            messages = load_messages(lang)
            
            await update.effective_chat.send_message(
                messages.get("error_occurred", "An unexpected error occurred. Please try again or type /start."),
                parse_mode=ParseMode.MARKDOWN_V2
            )
        except Exception as e:
            logger.error(f"Failed to send error message to user: {e}")

    # Opcionalno: Pošaljite grešku sebi (administratoru)
    if DEVELOPER_CHAT_ID:
        try:
            tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
            tb_string = "".join(tb_list)
            update_str = update.to_dict() if isinstance(update, Update) else str(update)
            message = (
                f"An exception was raised while handling an update\n"
                f"<pre>update = {html.escape(json.dumps(update_str, indent=2))}"
                f"</pre>\n<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n"
                f"<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n"
                f"<pre>{html.escape(tb_string)}</pre>"
            )
            # Skratite poruku ako je predugačka za Telegram (max 4096 karaktera)
            if len(message) > 4096:
                message = message[:4000] + "..."
            await context.bot.send_message(
                chat_id=DEVELOPER_CHAT_ID, text=message, parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Failed to send error message to developer: {e}")


def main() -> None:
    TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
    if not TOKEN:
        logger.critical("TELEGRAM_BOT_TOKEN environment variable not set. Bot cannot start.")
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set.")
    
    PORT = int(os.environ.get('PORT', 8080)) 
    WEBHOOK_URL = os.environ.get('WEBHOOK_URL') 

    application = Application.builder().token(TOKEN).build() 

    # --- Registracija error handlera ---
    application.add_error_handler(error_handler) 
    # -----------------------------------

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback)) 

    sketch_conversation_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(request_sketch_entry, pattern='^send_sketch_now$')],
        states={
            AWAITING_SKETCH: [
                MessageHandler(filters.PHOTO | filters.Document.ALL, handle_sketch),
                CommandHandler("cancel", cancel_sketch_request),
                CallbackQueryHandler(button_callback, pattern='^no_sketch_needed$')
            ]
        },
        fallbacks=[CommandHandler("start", start), CommandHandler("cancel", cancel_sketch_request)]
    )
    application.add_handler(sketch_conversation_handler) 

    if WEBHOOK_URL:
        logger.info(f"Pokrećem bot u webhook modu. URL: {WEBHOOK_URL}, Port: {PORT}")
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