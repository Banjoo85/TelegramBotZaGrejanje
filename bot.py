import os
import json
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    PicklePersistence
)
from telegram.constants import ParseMode

# Konfiguracija logovanja
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# Stanja za ConversationHandler
CHOOSE_INSTALLATION_TYPE, CHOOSE_HEATING_SYSTEM, UPLOAD_SKETCH, CHOOSE_HEAT_PUMP_TYPE = range(4)

# --- PODACI ZA KONTAKT I ADMINI ---
# Podaci za kontakt
contact_info = {
    'srbija': {
        # Podaci za IZVOĐAČA RADOVA u Srbiji
        'contractor': {
            'phone': '+381603932566',        # Telefon izvođača za Srbiju
            'email': 'boskovicigor83@gmail.com', # Email izvođača za Srbiju
            'website': ':',   # Website izvođača za Srbiju (ako postoji)
            'telegram': '@IgorNS1983' # Telegram izvođača za Srbiju (ako postoji)
        },
        # Podaci za PROIZVOĐAČA u Srbiji
        'manufacturer': {
            'name': 'Microma',           # Naziv proizvođača
            'phone': '+38163582068',        # Telefon proizvođača (RAZLIČIT)
            'email': 'office@microma.rs', # Email proizvođača (RAZLIČIT)
            'website': 'https://microma.rs', # Website proizvođača (RAZLIČIT)
            'telegram': ':'  # Telegram proizvođača (ako postoji)
        }
    },
    'crna_gora': {
        # Podaci za IZVOĐAČA RADOVA u Crnoj Gori (nema posebnog proizvođača ovde, samo izvođač)
        'contractor': {
            'name': 'Instal M',
            'phone': '+38267423237',
            'email': 'office@instalm.me',
            'website': ':',
            'telegram': '@ivanmujovic'
        }
    }
}

# Telegram ID-ovi admina koji će primati obaveštenja (TVOJ ID TREBA DA BUDE OVDE)
ADMIN_IDS = [
6869162490, # ZAMENI OVO SA SVOJIM TELEGRAM ID-jem (ADMIN ID 1)
]
# --- KRAJ SEKCIJE PODATAKA ---

# Učitavanje tokena i webhook URL-a
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
IS_LOCAL = os.getenv("IS_LOCAL", "True").lower() == "true"
PORT = int(os.environ.get("PORT", 8443))

# Funkcija za učitavanje poruka
def load_messages(lang: str) -> dict:
    try:
        with open(f'messages_{lang}.json', 'r', encoding='utf-8') as f:
            messages = json.load(f)
        logger.debug(f"Uspešno učitane poruke iz messages_{lang}.json")
        return messages
    except FileNotFoundError:
        logger.error(f"Fajl messages_{lang}.json nije pronađen. Vraćam podrazumevane engleske poruke.")
        with open('messages_en.json', 'r', encoding='utf-8') as f:
            messages = json.load(f)
        return messages
    except json.JSONDecodeError as e:
        logger.error(f"Greška prilikom parsiranja JSON fajla messages_{lang}.json: {e}. Vraćam podrazumevane engleske poruke.")
        with open('messages_en.json', 'r', encoding='utf-8') as f:
            messages = json.load(f)
        return messages

# Pomoćna funkcija za dobijanje poruke na osnovu korisničkog jezika
def get_message(user_id: int, key: str, user_data: dict) -> str:
    lang = user_data.get(user_id, {}).get('lang', 'en')
    messages = user_data.get(user_id, {}).get('messages', load_messages('en'))
    return messages.get(key, f"_{key}_ missing in messages. Defaulting to English.")

# Funkcija za slanje obaveštenja adminima
async def notify_admins(context: ContextTypes.DEFAULT_TYPE, message: str) -> None:
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=message, parse_mode=ParseMode.MARKDOWN_V2)
            logger.info(f"Obaveštenje poslato adminu {admin_id}")
        except Exception as e:
            logger.error(f"Greška prilikom slanja obaveštenja adminu {admin_id}: {e}")

# Funkcija za pružanje kontakt informacija (DEFINICIJA OVE FUNKCIJE JE SADA IZNAD SVIH POZIVA)
async def offer_contact_info(update: Update, context: ContextTypes.DEFAULT_TYPE, context_type: str) -> int:
    user_id = update.effective_user.id
    messages = context.user_data[user_id]['messages']
    
    country = context.user_data[user_id].get('country', 'srbija') # Default na Srbiju
    
    # Uzimanje podataka za IZVOĐAČA na osnovu zemlje
    # Ovo će biti "contractor" rečnik unutar 'srbija' ili 'crna_gora'
    contractor_contacts = contact_info.get(country, {}).get('contractor')
    if not contractor_contacts: # Fallback ako podaci za contractor nisu pronađeni (ne bi trebalo)
        contractor_contacts = contact_info['srbija']['contractor']
        logger.warning(f"Nisu pronađeni podaci za izvođača za zemlju {country}, korišćeni podaci za Srbiju.")
    
    phone_contractor = contractor_contacts['phone']
    email_contractor = contractor_contacts['email']
    website_contractor_info = f"\\n🌐 \\*Website\\:* {contractor_contacts['website']}" if contractor_contacts.get('website') else ""
    telegram_contractor_info = f"\\n💬 \\*Telegram Podrška\\:* {contractor_contacts['telegram']}" if contractor_contacts.get('telegram') else ""

    response_text = ""

    # Ako je zemlja Srbija, dodajemo i podatke o PROIZVOĐAČU
    manufacturer_details_text = ""
    if country == 'srbija' and 'manufacturer' in contact_info['srbija']:
        manufacturer_data = contact_info['srbija']['manufacturer']
        manufacturer_name = manufacturer_data['name']
        manufacturer_phone = manufacturer_data.get('phone', 'N/A')
        manufacturer_email = manufacturer_data.get('email', 'N/A')
        manufacturer_website_info = f"\\n🌐 \\*Website\\:* {manufacturer_data['website']}" if manufacturer_data.get('website') else ""
        manufacturer_telegram_info = f"\\n💬 \\*Telegram Podrška\\:* {manufacturer_data['telegram']}" if manufacturer_data.get('telegram') else ""

        manufacturer_details_text = (
            f"\\n\\n---\\n\\n\\*Kontakt za Proizvođača \\({manufacturer_name}\\)\\*:" # Dupla kosa crta za - i (
            f"\\n📞 \\*Telefon\\:* `{manufacturer_phone}`"
            f"\\n✉️ \\*Email\\:* {manufacturer_email}"
            f"{manufacturer_website_info}"
            f"{manufacturer_telegram_info}"
        )

    # Generisanje poruke za izvođača
    contractor_message_part = messages["contractor_info"].format(
        phone=phone_contractor,
        email=email_contractor,
        website_info=website_contractor_info,
        telegram_info=telegram_contractor_info
    )

    if context_type == "hp_quote":
        hp_type_chosen = context.user_data[user_id].get('hp_type', 'neodređeni tip').replace("_", " ").title()
        country_name = messages["srbija_button"].replace(" 🇷🇸", "") if country == 'srbija' else messages["crna_gora_button"].replace(" 🇲🇪", "")
        
        # Prikazujemo informacije o izvođaču za TP ponudu
        response_text = messages["hp_offer_info"].format(
            hp_type=hp_type_chosen,
            country_name=country_name
        )
        # Ako je Srbija, dodajemo i podatke o proizvođaču
        if country == 'srbija':
            response_text += manufacturer_details_text
            # VAŽNO: Dodajemo i kontakt podatke izvođača ovde, jer je hp_offer_info poruka sada opštija
            response_text += f"\\n\\n{contractor_message_part}" # Dodaj izvođača nakon proizvođača
            
    elif context_type == "hp_redirect":
        response_text = contractor_message_part
        if country == 'srbija':
            response_text += manufacturer_details_text

    else: # general_contact
        response_text = contractor_message_part
        if country == 'srbija':
            response_text += manufacturer_details_text

    await context.bot.send_message(chat_id=user_id, text=response_text, parse_mode=ParseMode.MARKDOWN_V2)
    return ConversationHandler.END


# Glavna start funkcija
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    logger.debug(f"start funkcija pozvana za korisnika {user_id}")

    if user_id not in context.user_data:
        context.user_data[user_id] = {'lang': 'en', 'session_active': True}
        logger.debug(f"Inicijalizovan user_data za novog korisnika {user_id}: {context.user_data[user_id]}")
    else:
        context.user_data[user_id]['session_active'] = True
        if 'messages' not in context.user_data[user_id]:
            context.user_data[user_id]['messages'] = load_messages(context.user_data[user_id].get('lang', 'en'))
        logger.debug(f"Postojeći user_data za korisnika {user_id}: {context.user_data[user_id]}")

    messages = context.user_data[user_id]['messages']

    keyboard = [
        [InlineKeyboardButton("Srpski 🇷🇸", callback_data='lang_sr')],
        [InlineKeyboardButton("English 🇬🇧", callback_data='lang_en')],
        [InlineKeyboardButton("Русский 🇷🇺", callback_data='lang_ru')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(messages["start_message"], reply_markup=reply_markup)
    logger.info(f"Korisnik {user_id} je dobio start poruku.")
    
    return CHOOSE_INSTALLATION_TYPE

# Funkcija za obradu odabira jezika
async def language_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    selected_lang = query.data.split('_')[1]

    context.user_data[user_id]['lang'] = selected_lang
    context.user_data[user_id]['messages'] = load_messages(selected_lang)
    messages = context.user_data[user_id]['messages']

    await query.edit_message_reply_markup(reply_markup=None)

    keyboard = [
        [
            InlineKeyboardButton(messages["srbija_button"], callback_data='country_srbija'),
            InlineKeyboardButton(messages["crna_gora_button"], callback_data='country_crna_gora')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    # Line 315 refers to this message:
    await context.bot.send_message(chat_id=user_id, text=messages["language_selected"], reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2)
    return CHOOSE_INSTALLATION_TYPE

# Funkcija za obradu odabira države
async def country_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    selected_country = query.data.split('_')[1]

    context.user_data[user_id]['country'] = selected_country
    messages = context.user_data[user_id]['messages']
    
    country_name = ""
    if selected_country == 'srbija':
        country_name = messages["srbija_button"].replace(" 🇷🇸", "")
    elif selected_country == 'crna_gora':
        country_name = messages["crna_gora_button"].replace(" 🇲🇪", "")

    await query.edit_message_reply_markup(reply_markup=None)

    keyboard = [
        [InlineKeyboardButton(messages["request_quote_button"], callback_data='request_quote')],
        [InlineKeyboardButton(messages["services_info_button"], callback_data='services_info')],
        [InlineKeyboardButton(messages["faq_button"], callback_data='faq')],
        [InlineKeyboardButton(messages["contact_button"], callback_data='contact')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=user_id,
        text=messages["country_selected"].format(country_name=country_name) + "\\n\\n" + messages["main_menu_greeting"], # \\n\\n za novi red
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN_V2
    )
    return CHOOSE_INSTALLATION_TYPE

# Funkcija za obradu opcija glavnog menija
async def main_menu_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    messages = context.user_data[user_id]['messages']
    selected_option = query.data

    await query.edit_message_reply_markup(reply_markup=None)

    if selected_option == 'request_quote':
        await context.bot.send_message(chat_id=user_id, text=messages["quote_request_acknowledgement"])
        return await request_quote_process(update, context)
    elif selected_option == 'services_info':
        await context.bot.send_message(chat_id=user_id, text="Usluge koje nudimo uključuju projektovanje, montažu i održavanje sistema grejanja i hlađenja, kao i rešenja sa toplotnim pumpama\\.", parse_mode=ParseMode.MARKDOWN_V2)
    elif selected_option == 'faq':
        await context.bot.send_message(chat_id=user_id, text="Česta pitanja: Kako odabrati pravu toplotnu pumpu\\? Koja je razlika između split i monoblok sistema\\? Za sve nedoumice, kontaktirajte nas!", parse_mode=ParseMode.MARKDOWN_V2)
    elif selected_option == 'contact':
        # Line 337 refers to this call:
        return await offer_contact_info(update, context, "general_contact")
    
    return CHOOSE_INSTALLATION_TYPE


# Funkcija za pokretanje procesa zahteva za ponudu
async def request_quote_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    messages = context.user_data[user_id]['messages']

    keyboard = [
        [InlineKeyboardButton(messages["heating_installation_button"], callback_data='inst_heating')],
        [InlineKeyboardButton(messages["heat_pump_button"], callback_data='inst_hp')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(messages["choose_installation_type"], reply_markup=reply_markup)
    else:
        await context.bot.send_message(chat_id=user_id, text=messages["choose_installation_type"], reply_markup=reply_markup)
    
    return CHOOSE_INSTALLATION_TYPE

# Funkcija za obradu odabira tipa instalacije
async def installation_type_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    selected_type = query.data.split('_')[1]
    messages = context.user_data[user_id]['messages']

    context.user_data[user_id]['installation_type'] = selected_type

    await query.edit_message_reply_markup(reply_markup=None)

    if selected_type == 'heating':
        keyboard = [
            [InlineKeyboardButton(messages["radiators_button"], callback_data='heating_radiators')],
            [InlineKeyboardButton(messages["fan_coil_button"], callback_data='heating_fancoil')],
            [InlineKeyboardButton(messages["underfloor_heating_button"], callback_data='heating_underfloor')],
            [InlineKeyboardButton(messages["underfloor_fan_coil_button"], callback_data='heating_underfloor_fancoil')],
            [InlineKeyboardButton(messages["complete_with_hp_button"], callback_data='heating_complete_hp')],
            [InlineKeyboardButton(messages["existing_installation_button"], callback_data='heating_existing')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id=user_id, text=messages["choose_heating_system"], reply_markup=reply_markup)
        return CHOOSE_HEATING_SYSTEM
    elif selected_type == 'hp': # Ako je korisnik odabrao "Toplotne pumpe"
        country = context.user_data[user_id].get('country', 'srbija') # Proveri koja je država odabrana
        if country == 'crna_gora': # AKO JE CRNA GORA!
            # Direktno vodi na kontakt info za Crnu Goru (TP ponuda)
            # Podaci su iz contractor dela za Crnu Goru
            cg_contractor = contact_info['crna_gora']['contractor']
            
            # Poruka koju prikazujemo (HP tip je fiksiran kao "Vazduh-Voda" za CG)
            hp_type_cg = "Toplotna pumpa Vazduh\\-Voda" # Escapovano za MarkdownV2
            country_name_cg = messages["crna_gora_button"].replace(" 🇲🇪", "") # Ime države

            # Formiranje početka poruke koristeći hp_offer_info iz JSON-a
            response_text_cg = messages["hp_offer_info"].format(
                hp_type=hp_type_cg,
                country_name=country_name_cg
            )
            # Dodaj kontakt podatke izvođača za CG
            response_text_cg += messages["contractor_info"].format(
                phone=cg_contractor['phone'],
                email=cg_contractor['email'],
                website_info=f"\\n🌐 \\*Website\\:* {cg_contractor['website']}" if cg_contractor.get('website') else "",
                telegram_info=f"\\n💬 \\*Telegram Podrška\\:* {cg_contractor['telegram']}" if cg_contractor.get('telegram') else ""
            )
            
            await context.bot.send_message(chat_id=user_id, text=response_text_cg, parse_mode=ParseMode.MARKDOWN_V2)
            return ConversationHandler.END # ZAVRŠAVA konverzaciju ovde
        else: # Za Srbiju (ili druge zemlje, ako ih bude), nudimo opcije za tip TP
            return await choose_heat_pump_type(update, context)


# Funkcija za odabir tipa toplotne pumpe
async def choose_heat_pump_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    messages = context.user_data[user_id]['messages']

    keyboard = [
        [InlineKeyboardButton("Split sistem", callback_data='hp_split')],
        [InlineKeyboardButton("Monoblok sistem", callback_data='hp_monoblock')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(messages["choose_heat_pump_type"], reply_markup=reply_markup)
    else:
        await context.bot.send_message(chat_id=user_id, text=messages["choose_heat_pump_type"], reply_markup=reply_markup)
    
    return CHOOSE_HEAT_PUMP_TYPE

# Funkcija za obradu odabira grejnog sistema
async def heating_system_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    selected_system = query.data.split('_')[1]
    messages = context.user_data[user_id]['messages']

    context.user_data[user_id]['heating_system'] = selected_system

    await query.edit_message_reply_markup(reply_markup=None)

    if selected_system == 'complete_hp' or selected_system == 'existing':
        await context.bot.send_message(chat_id=user_id, text=messages["redirect_to_hp"], parse_mode=ParseMode.MARKDOWN_V2)
        # Line 210 refers to this call:
        return await offer_contact_info(update, context, "hp_redirect")
    else:
        keyboard = [
            [InlineKeyboardButton(messages["send_sketch_button"], callback_data='sketch_yes')],
            [InlineKeyboardButton(messages["no_sketch_button"], callback_data='sketch_no')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(chat_id=user_id, text=messages["request_sketch_optional"], reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2)
        return UPLOAD_SKETCH

# Funkcija za obradu odabira tipa toplotne pumpe (nakon odabira)
async def heat_pump_type_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    selected_hp_type = query.data.split('_')[1]
    messages = context.user_data[user_id]['messages']

    context.user_data[user_id]['hp_type'] = selected_hp_type

    await query.edit_message_reply_markup(reply_markup=None)
    
    return await offer_contact_info(update, context, "hp_quote")

# Funkcija za obradu opcija skice
async def sketch_option(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    messages = context.user_data[user_id]['messages']
    choice = query.data.split('_')[1]

    await query.edit_message_reply_markup(reply_markup=None)

    if choice == 'yes':
        await context.bot.send_message(chat_id=user_id, text=messages["request_sketch"], parse_mode=ParseMode.MARKDOWN_V2)
        return UPLOAD_SKETCH
    else:
        await context.bot.send_message(chat_id=user_id, text=messages["no_sketch_confirmation"], parse_mode=ParseMode.MARKDOWN_V2)
        return ConversationHandler.END

# Funkcija za obradu primljene skice
async def handle_sketch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    messages = context.user_data[user_id]['messages']

    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        file_type = "sliku"
    elif update.message.document:
        file_id = update.message.document.file_id
        file_type = "dokument"
    else:
        await context.bot.send_message(chat_id=user_id, text=messages.get("invalid_file_type", "Molimo pošaljite fotografiju ili dokument\\."), parse_mode=ParseMode.MARKDOWN_V2)
        return UPLOAD_SKETCH

    logger.info(f"Skica (ID: {file_id}) primljena od korisnika {user_id}")

    await context.bot.send_message(chat_id=user_id, text=messages["sketch_received"], parse_mode=ParseMode.MARKDOWN_V2)

    # Obaveštenje adminima o primljenoj skici
    user_info = update.effective_user.mention_markdown_v2()
    notification_message = (
        f"Nova skica primljena od korisnika {user_info} (ID: `{user_id}`)\\.\\n" # Dupla kosa crta pre tačke
        f"Tip fajla: \\*{file_type}\\*\\n" # Dupla kosa crta pre *
        f"ID fajla: `{file_id}`"
    )
    await notify_admins(context, notification_message)

    return ConversationHandler.END

# Funkcija za obradu grešaka
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Update {update} prouzrokovao grešku {context.error}")
    user_id = update.effective_user.id if update.effective_user else None
    
    messages = {}
    if user_id and user_id in context.user_data and 'messages' in context.user_data[user_id]:
        messages = context.user_data[user_id]['messages']
    else:
        messages = load_messages('en')

    error_message_key = "error_occurred"
    # Proverava specifičnu grešku za "Can't parse entities"
    if isinstance(context.error, Exception) and "Can't parse entities" in str(context.error):
        error_message_key = "session_expired_restart_needed" 
        logger.error(f"Greška prilikom obaveštavanja korisnika o isteku sesije: {context.error}")
        # Pokušaj da pošalješ poruku bez MarkdownV2 parsiranja kao fallback
        try:
            await context.bot.send_message(chat_id=user_id, text=messages[error_message_key].replace("\\", ""), parse_mode=None)
        except Exception as e:
            logger.error(f"Sekundarna greška prilikom slanja fallback poruke: {e}")
            await context.bot.send_message(chat_id=user_id, text="Došlo je do greške u sesiji\\. Molimo kucajte /start da biste počeli ispočetka\\.", parse_mode=ParseMode.MARKDOWN_V2)
    else:
        await context.bot.send_message(chat_id=user_id, text=messages[error_message_key], parse_mode=ParseMode.MARKDOWN_V2)

# Glavna funkcija za pokretanje bota
def main() -> None:
    persistence = PicklePersistence(filepath="my_bot_data.pkl")

    application = ApplicationBuilder.builder() \
        .token(TELEGRAM_BOT_TOKEN) \
        .persistence(persistence) \
        .build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CallbackQueryHandler(language_selection, pattern='^lang_'),
        ],
        states={
            CHOOSE_INSTALLATION_TYPE: [
                CallbackQueryHandler(language_selection, pattern='^lang_'),
                CallbackQueryHandler(country_selection, pattern='^country_'),
                CallbackQueryHandler(installation_type_selection, pattern='^inst_'),
                CallbackQueryHandler(main_menu_options, pattern='^(request_quote|services_info|faq|contact)$')
            ],
            CHOOSE_HEATING_SYSTEM: [
                CallbackQueryHandler(heating_system_selection, pattern='^heating_')
            ],
            UPLOAD_SKETCH: [
                CallbackQueryHandler(sketch_option, pattern='^sketch_'),
                MessageHandler(filters.PHOTO | filters.Document.ALL, handle_sketch),
                CommandHandler('cancel', end_conversation)
            ],
            CHOOSE_HEAT_PUMP_TYPE: [
                CallbackQueryHandler(heat_pump_type_selected, pattern='^hp_')
            ]
        },
        fallbacks=[
            CommandHandler('start', start),
            CallbackQueryHandler(handle_session_expired),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_invalid_input)
        ],
        persistent=True,
        name="main_conversation"
    )

    application.add_handler(conv_handler)
    application.add_error_handler(error_handler)

    if not IS_LOCAL:
        logger.info(f"Pokrećem webhook na portu {PORT}")
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TELEGRAM_BOT_TOKEN,
            webhook_url=WEBHOOK_URL + TELEGRAM_BOT_TOKEN
        )
    else:
        logger.info("Pokrećem polling (lokalno)")
        application.run_polling(poll_interval=3)

async def end_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    messages = context.user_data.get(user_id, {}).get('messages', load_messages('en'))
    await update.message.reply_text(messages.get("conversation_ended", "Konverzacija je završena\\. Kucajte /start za ponovni početak\\."), parse_mode=ParseMode.MARKDOWN_V2)
    return ConversationHandler.END

async def handle_invalid_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    messages = context.user_data.get(user_id, {}).get('messages', load_messages('en'))
    
    current_state = await context.bot.get_state(user_id, 'main_conversation')

    if current_state == UPLOAD_SKETCH:
        await update.message.reply_text(messages["request_sketch"], parse_mode=ParseMode.MARKDOWN_V2)
        return UPLOAD_SKETCH
    else:
        await update.message.reply_text(messages["error_displaying_menu"], parse_mode=ParseMode.MARKDOWN_V2)
        return ConversationHandler.END

async def handle_session_expired(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    
    if user_id not in context.user_data or not context.user_data[user_id].get('session_active'):
        logger.warning(f"Sesija istekla za korisnika {user_id} tokom callback upita. Pokušavam da oporavim.")
        context.user_data[user_id] = {'lang': 'en', 'session_active': True}
        context.user_data[user_id]['messages'] = load_messages('en')
        messages = context.user_data[user_id]['messages']
        
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_reply_markup(reply_markup=None)
            await context.bot.send_message(chat_id=user_id, text=messages["session_expired_restart_needed"], parse_mode=ParseMode.MARKDOWN_V2)
        else:
            await context.bot.send_message(chat_id=user_id, text=messages["session_expired_restart_needed"], parse_mode=ParseMode.MARKDOWN_V2)
            
        await start(update, context)
        return ConversationHandler.END
    
    messages = context.user_data[user_id]['messages']
    await context.bot.send_message(chat_id=user_id, text=messages["error_displaying_menu"], parse_mode=ParseMode.MARKDOWN_V2)
    return ConversationHandler.END

if __name__ == "__main__":
    main()