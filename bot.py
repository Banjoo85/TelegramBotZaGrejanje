import logging
import json
import os
import re
import yagmail
from dotenv import load_dotenv

## VAŽNO: Učitavanje .env fajla mora biti na samom vrhu, odmah nakon importova
load_dotenv()

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import asyncio # Dodat import za asyncio

## VAŽNO: Postavljanje logginga, obično odmah nakon .env učitavanja
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Stanja za ConversationHandler
CHOOSE_OBJECT_TYPE, ENTER_SURFACE_AREA, ENTER_NUM_FLOORS, SEND_SKETCH, ENTER_CONTACT_INFO, ENTER_EMAIL, CONFIRM_DETAILS = range(7)

# Rečnik za čuvanje korisničkih preferencija i podataka za upit
user_data = {} # U produkciji bi ovo trebalo da bude baza podataka

# --- Pomoćne funkcije i handleri (POREDANI PO ZAVISNOSTI - od najniže ka najvišoj) ---

## VAŽNO: load_messages je često pozivana, pa ide na početak
def load_messages(lang_code):
    try:
        with open(f'messages_{lang_code}.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Message file for {lang_code} not found. Defaulting to English.")
        with open(f'messages_en.json', 'r', encoding='utf-8') as f:
            return json.load(f)

## VAŽNO: Krajnje funkcije u ConversationHandler-u, idu prve
async def send_inquiry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    messages = load_messages(user_data[user_id]['lang'])
    inquiry_data = context.user_data['inquiry']

    sender_email = os.getenv("EMAIL_SENDER_EMAIL")
    app_password = os.getenv("EMAIL_APP_PASSWORD")
    admin_bcc_email = os.getenv("ADMIN_BCC_EMAIL")

    recipient_email = ""
    if inquiry_data['country'] == 'srbija':
        recipient_email = "igor.boskovic@example.com" # Stvarni email Igora Boškovića
        if inquiry_data['installation_type'] == 'heatpump':
             recipient_email = "microma.doo@example.com" # Stvarni email Microme
    elif inquiry_data['country'] == 'crna_gora':
        recipient_email = "instal.m@example.com" # Stvarni email Instal M

    if not all([sender_email, app_password, recipient_email]):
        logger.error("Nedostaju email konfiguracije za slanje upita.")
        await query.edit_message_text("Došlo je do greške prilikom slanja upita. Molimo pokušajte ponovo kasnije.")
        return ConversationHandler.END

    email_body = f"Novi upit sa Telegram bota:\n\n" \
                 f"Zemlja: {inquiry_data.get('country')}\n" \
                 f"Tip instalacije: {inquiry_data.get('installation_type')}\n" \
                 f"Sistem grejanja: {inquiry_data.get('heating_system_type', 'N/A')}\n" \
                 f"Podtip TP: {inquiry_data.get('heat_pump_subtype', 'N/A')}\n" \
                 f"Tip objekta: {inquiry_data.get('object_type')}\n" \
                 f"Površina: {inquiry_data.get('surface_area')} m²\n" \
                 f"Spratnost: {inquiry_data.get('num_floors')}\n" \
                 f"Skica priložena: {'Da' if inquiry_data['sketch_attached'] else 'Ne'}\n" \
                 f"Ime i prezime: {inquiry_data.get('contact_name')}\n" \
                 f"Telefon: {inquiry_data.get('contact_phone')}\n" \
                 f"Email korisnika: {inquiry_data.get('contact_email')}\n\n" \
                 f"Korisnik ID: {user_id}"

    try:
        yag = yagmail.SMTP(user=sender_email, password=app_password)

        attachments = []
        if inquiry_data['sketch_attached'] and inquiry_data['sketch_file_id']:
            file_id = inquiry_data['sketch_file_id']
            telegram_file = await context.bot.get_file(file_id)
            file_path = f"{file_id}.{telegram_file.file_path.split('.')[-1]}"
            await telegram_file.download_to_drive(file_path)
            attachments.append(file_path)
            logger.info(f"Skica preuzeta i biće prikačena: {file_path}")

        yag.send(
            to=recipient_email,
            bcc=admin_bcc_email,
            subject=f"Novi upit za ponudu: {inquiry_data.get('country').upper()} - {inquiry_data.get('installation_type').capitalize()}",
            contents=email_body,
            attachments=attachments
        )
        await query.edit_message_text(text=messages["inquiry_sent_success"])
        logger.info(f"Upit uspešno poslat na {recipient_email} (BCC: {admin_bcc_email}) od korisnika {user_id}.")

        if attachments and os.path.exists(attachments[0]):
            os.remove(attachments[0])
            logger.info(f"Privremeni fajl skice obrisan: {attachments[0]}")

    except Exception as e:
        logger.error(f"Greška prilikom slanja emaila za upit {user_id}: {e}")
        await query.edit_message_text("Došlo je do greške prilikom slanja upita. Molimo pokušajte ponovo kasnije.")

    context.user_data.clear() # Očisti podatke nakon završenog upita
    return ConversationHandler.END

async def cancel_inquiry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    messages = load_messages(user_data[user_id]['lang'])
    await query.edit_message_text(text=messages["inquiry_canceled"])
    context.user_data.clear() # Očisti podatke
    return ConversationHandler.END

async def conversation_timeout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    messages = load_messages(user_data[user_id]['lang'])
    await context.bot.send_message(chat_id=user_id, text="Vreme za unos je isteklo. Molimo počnite ponovo sa /start.")
    context.user_data.clear()
    return ConversationHandler.END

## VAŽNO: Funkcije za prikupljanje podataka u ConversationHandler-u, idu sledeće
async def get_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    messages = load_messages(user_data[user_id]['lang'])
    email = update.message.text

    if re.match(r"[^@]+@[^@]+\.[^@]+", email): # Basic email validation
        context.user_data['inquiry']['contact_email'] = email
        inquiry_data = context.user_data['inquiry']

        confirm_text = messages["confirm_details"].format(
            object_type=inquiry_data['object_type'],
            surface_area=inquiry_data['surface_area'],
            num_floors=inquiry_data['num_floors'],
            sketch_attached=messages["confirm_button"] if inquiry_data['sketch_attached'] else messages["cancel_button"],
            contact_name=inquiry_data['contact_name'],
            contact_phone=inquiry_data['contact_phone'],
            contact_email=inquiry_data['contact_email']
        )

        keyboard = [
            [InlineKeyboardButton(messages["confirm_button"], callback_data='confirm_inquiry')],
            [InlineKeyboardButton(messages["cancel_button"], callback_data='cancel_inquiry')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(confirm_text, reply_markup=reply_markup)
        return CONFIRM_DETAILS
    else:
        await update.message.reply_text("Molimo unesite validnu email adresu.")
        return ENTER_EMAIL

async def get_contact_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    messages = load_messages(user_data[user_id]['lang'])

    contact_text = update.message.text
    match = re.match(r"([\w\sčćšđžČĆŠĐŽ.]+),\s*([\d\s\/\+\-]+)", contact_text)
    if match:
        context.user_data['inquiry']['contact_name'] = match.group(1).strip()
        context.user_data['inquiry']['contact_phone'] = match.group(2).strip()
        await update.message.reply_text(messages["request_email"])
        return ENTER_EMAIL
    else:
        await update.message.reply_text("Format je pogrešan. Molimo unesite Ime Prezime, Telefon (npr. Petar Petrović, 06x/xxx-xxxx).")
        return ENTER_CONTACT_INFO

async def get_sketch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    messages = load_messages(user_data[user_id]['lang'])

    if update.message.document:
        context.user_data['inquiry']['sketch_attached'] = True
        context.user_data['inquiry']['sketch_file_id'] = update.message.document.file_id
        await update.message.reply_text("Skica je primljena.")
    elif update.message.photo:
        context.user_data['inquiry']['sketch_attached'] = True
        context.user_data['inquiry']['sketch_file_id'] = update.message.photo[-1].file_id
        await update.message.reply_text("Skica (slika) je primljena.")
    ## VAŽNO: Proveravamo da li je tekst "Ne" ili ekvivalent iz json fajla
    elif update.message.text and update.message.text.lower() == messages["no_sketch_text"].lower():
        context.user_data['inquiry']['sketch_attached'] = False
        await update.message.reply_text("Nema skice.")
    else:
        await update.message.reply_text("Molimo pošaljite skicu kao sliku/PDF ili pošaljite 'Ne'.")
        return SEND_SKETCH

    await update.message.reply_text(messages["request_contact_info"])
    return ENTER_CONTACT_INFO

async def get_num_floors(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    messages = load_messages(user_data[user_id]['lang'])
    try:
        num_floors = int(update.message.text)
        context.user_data['inquiry']['num_floors'] = num_floors
        await update.message.reply_text(messages["request_sketch"])
        return SEND_SKETCH
    except ValueError:
        await update.message.reply_text("Molimo unesite validan broj za spratnost.")
        return ENTER_NUM_FLOORS

async def get_surface_area(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    messages = load_messages(user_data[user_id]['lang'])
    try:
        surface_area = int(update.message.text)
        context.user_data['inquiry']['surface_area'] = surface_area
        await update.message.reply_text(messages["request_number_of_floors"])
        return ENTER_NUM_FLOORS
    except ValueError:
        await update.message.reply_text("Molimo unesite validan broj za površinu.")
        return ENTER_SURFACE_AREA

async def get_object_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    messages = load_messages(user_data[user_id]['lang'])
    context.user_data['inquiry']['object_type'] = update.message.text
    await update.message.reply_text(messages["request_surface_area"])
    return ENTER_SURFACE_AREA

## VAŽNO: Conversation Handler entry point, poziva gornje funkcije
async def query_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    messages = load_messages(user_data[user_id]['lang'])
    # Inicijalizacija privremenih podataka za upit
    context.user_data['inquiry'] = {
        'country': user_data[user_id].get('country'),
        'installation_type': user_data[user_id].get('installation_type'),
        'heating_system_type': user_data[user_id].get('heating_system_type'),
        'heat_pump_subtype': user_data[user_id].get('heat_pump_subtype'),
        'object_type': None,
        'surface_area': None,
        'num_floors': None,
        'sketch_attached': False,
        'sketch_file_id': None,
        'contact_name': None,
        'contact_phone': None,
        'contact_email': None
    }
    await context.bot.send_message(chat_id=user_id, text=messages["request_object_details"])
    return CHOOSE_OBJECT_TYPE

## VAŽNO: Funkcije za specifične menije, pozivaju se iz button_callback-a
async def show_crna_gora_heat_pump_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    messages = load_messages(user_data[user_id]['lang'])
    await context.bot.send_message(chat_id=user_id, text=messages["crna_gora_heat_pump_intro"])
    await context.bot.send_message(chat_id=user_id, text=messages["instal_m_info"], parse_mode='Markdown')
    # Direktno započni konverzaciju
    await query_start(update, context)

async def show_crna_gora_heating_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    messages = load_messages(user_data[user_id]['lang'])
    await context.bot.send_message(chat_id=user_id, text=messages["crna_gora_heating_intro"])

    keyboard = [
        [InlineKeyboardButton(messages["radiators_button"], callback_data='system_cg_radiators')],
        [InlineKeyboardButton(messages["fan_coils_button"], callback_data='system_cg_fan_coils')],
        [InlineKeyboardButton(messages["underfloor_heating_button"], callback_data='system_cg_underfloor')],
        [InlineKeyboardButton(messages["underfloor_plus_fan_coils_button"], callback_data='system_cg_underfloor_plus_fan_coils')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=user_id, text=messages["choose_heating_system"], reply_markup=reply_markup)

async def show_srbija_heat_pump_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    messages = load_messages(user_data[user_id]['lang'])
    await context.bot.send_message(chat_id=user_id, text=messages["srbija_heat_pump_intro"])

    keyboard = [
        [InlineKeyboardButton(messages["water_water_hp_button"], callback_data='hp_srb_water_water')],
        [InlineKeyboardButton(messages["air_water_hp_button"], callback_data='hp_srb_air_water')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=user_id, text=messages["choose_installation_type"], reply_markup=reply_markup)

async def show_srbija_heating_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    messages = load_messages(user_data[user_id]['lang'])
    await context.bot.send_message(chat_id=user_id, text=messages["srbija_heating_intro"])

    keyboard = [
        [InlineKeyboardButton(messages["radiators_button"], callback_data='system_srb_radiators')],
        [InlineKeyboardButton(messages["fan_coils_button"], callback_data='system_srb_fan_coils')],
        [InlineKeyboardButton(messages["underfloor_heating_button"], callback_data='system_srb_underfloor')],
        [InlineKeyboardButton(messages["underfloor_plus_fan_coils_button"], callback_data='system_srb_underfloor_plus_fan_coils')],
        [InlineKeyboardButton(messages["complete_heat_pump_offer_button"], callback_data='system_srb_complete_hp')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=user_id, text=messages["choose_installation_type"], reply_markup=reply_markup)

async def choose_installation_type_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    messages = load_messages(user_data[user_id]['lang'])

    keyboard = [
        [InlineKeyboardButton(messages["heating_installation_button"], callback_data='type_heating')],
        [InlineKeyboardButton(messages["heat_pump_button"], callback_data='type_heatpump')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=user_id, text=messages["choose_installation_type"], reply_markup=reply_markup)

## VAŽNO: Glavne meni funkcije
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    messages = load_messages(user_data[user_id]['lang'])

    keyboard = [
        [InlineKeyboardButton(messages["request_quote_button"], callback_data='menu_quote')],
        [InlineKeyboardButton(messages["services_info_button"], callback_data='menu_services')],
        [InlineKeyboardButton(messages["faq_button"], callback_data='menu_faq')],
        [InlineKeyboardButton(messages["contact_button"], callback_data='menu_contact')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=user_id, text=messages["main_menu_greeting"], reply_markup=reply_markup)

async def choose_country(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    messages = load_messages(user_data[user_id]['lang'])

    keyboard = [
        [InlineKeyboardButton(messages["srbija_button"], callback_data='country_srbija')],
        [InlineKeyboardButton(messages["crna_gora_button"], callback_data='country_crna_gora')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(chat_id=user_id, text=messages["choose_country"], reply_markup=reply_markup)

## VAŽNO: Start funkcija
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_data[user_id] = {'lang': 'en'} # Podrazumevani jezik dok korisnik ne izabere

    messages = load_messages(user_data[user_id]['lang'])

    keyboard = [
        [InlineKeyboardButton("Srpski 🇷🇸", callback_data='lang_sr')],
        [InlineKeyboardButton("English 🇬🇧", callback_data='lang_en')],
        [InlineKeyboardButton("Русский 🇷🇺", callback_data='lang_ru')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(messages["start_message"], reply_markup=reply_markup)

## VAŽNO: Glavni handler za sve "inline" dugmiće, on poziva mnoge funkcije iznad
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    callback_data = query.data

    if user_id not in user_data:
        user_data[user_id] = {'lang': 'en'}

    messages = load_messages(user_data[user_id]['lang'])

    if callback_data.startswith('lang_'):
        lang_code = callback_data.split('_')[1]
        user_data[user_id]['lang'] = lang_code
        messages = load_messages(lang_code)
        await query.edit_message_text(text=messages["language_selected"])
        await choose_country(update, context, user_id)

    elif callback_data.startswith('country_'):
        country_code = callback_data.split('_')[1]
        user_data[user_id]['country'] = country_code

        country_name = messages["srbija_button"] if country_code == 'srbija' else messages["crna_gora_button"]
        await query.edit_message_text(text=f"{messages['country_selected'].replace('Srbija', country_name).replace('Serbia', country_name).replace('Сербию', country_name)}")

        await show_main_menu(update, context, user_id)

    elif callback_data.startswith('menu_'):
        menu_option = callback_data.split('_')[1]

        if menu_option == 'quote':
            await query.edit_message_text(text=messages["request_quote_button"])
            await choose_installation_type_menu(update, context, user_id)
        elif menu_option == 'services':
            await query.edit_message_text(text=messages["services_info_button"] + "...")
            # Dalja logika za prikaz usluga
        elif menu_option == 'faq':
            await query.edit_message_text(text=messages["faq_button"] + "...")
            # Dalja logika za FAQ
        elif menu_option == 'contact':
            await query.edit_message_text(text=messages["contact_button"] + "...")
            # Dalja logika za prikaz kontakta

    elif callback_data.startswith('type_'):
        installation_type = callback_data.split('_')[1]
        user_data[user_id]['installation_type'] = installation_type

        selected_country = user_data[user_id].get('country')

        await query.edit_message_text(text=f"{messages[f'{installation_type}_installation_button']} je odabrana.")

        if installation_type == 'heating':
            if selected_country == 'srbija':
                await show_srbija_heating_menu(update, context, user_id)
            elif selected_country == 'crna_gora':
                await show_crna_gora_heating_menu(update, context, user_id)
        elif installation_type == 'heatpump':
            if selected_country == 'srbija':
                await show_srbija_heat_pump_menu(update, context, user_id)
            elif selected_country == 'crna_gora':
                await show_crna_gora_heat_pump_menu(update, context, user_id)

    elif callback_data.startswith('system_'): # Obrađuje izbor grejnog sistema (Srbija i Crna Gora)
        system_type = callback_data.split('_')[2] # Npr. srb_radiators -> radiators
        user_data[user_id]['heating_system_type'] = system_type

        selected_country = user_data[user_id].get('country')
        if selected_country == 'srbija':
            await query.message.reply_text(messages["srbija_heating_intro"])
        elif selected_country == 'crna_gora':
            await query.message.reply_text(messages["crna_gora_heating_intro"])

        await query.edit_message_text(text=f"{messages[f'{system_type}_button']} je odabrano.")

        # Sada započinjemo konverzaciju za prikupljanje detalja o objektu
        await query_start(update, context)

    elif callback_data.startswith('hp_'): # Obrađuje izbor toplotne pumpe (Srbija)
        hp_type = callback_data.split('_')[2] # Npr. srb_water_water -> water_water
        user_data[user_id]['heat_pump_subtype'] = hp_type

        await query.edit_message_text(text=f"{messages[f'{hp_type}_hp_button']} je odabrana.")
        await query.message.reply_text(messages["microma_info"], parse_mode='Markdown') # Prikazuje info o Micromi

        # Sada započinjemo konverzaciju za prikupljanje detalja o objektu
        await query_start(update, context)

    elif callback_data == 'confirm_inquiry':
        # Ove callback-ove obrađuje ConversationHandler, pa nema potrebe za "return" ovde
        pass

    elif callback_data == 'cancel_inquiry':
        # Ove callback-ove obrađuje ConversationHandler, pa nema potrebe za "return" ovde
        pass

## VAŽNO: Glavna funkcija za pokretanje bota
def main() -> Application: # Promenjen return type da bi Pylance bio srećan
    """Konfiguriše i vraća Telegram Bot Application instancu."""
    ## VAŽNO: Koristi BOT_TOKEN koji si postavio na Renderu
    BOT_TOKEN = os.getenv("BOT_TOKEN")

    if not BOT_TOKEN:
        logger.critical("Greška: BOT_TOKEN environment varijabla NIJE podešena! Bot se neće pokrenuti.")
        raise ValueError("BOT_TOKEN environment varijabla nije pronađena.")

    application = Application.builder().token(BOT_TOKEN).build()

    # Conversation Handler za prikupljanje detalja o objektu
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(query_start, pattern='^(system_|hp_)'), # Započinje kada se izabere tip sistema/HP
        ],
        states={
            CHOOSE_OBJECT_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_object_type)],
            ENTER_SURFACE_AREA: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_surface_area)],
            ENTER_NUM_FLOORS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_num_floors)],
            SEND_SKETCH: [MessageHandler(filters.PHOTO | filters.DOCUMENT | (filters.TEXT & ~filters.COMMAND), get_sketch)],
            ENTER_CONTACT_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_contact_info)],
            ENTER_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_email)],
            CONFIRM_DETAILS: [CallbackQueryHandler(send_inquiry, pattern='confirm_inquiry'),
                              CallbackQueryHandler(cancel_inquiry, pattern='cancel_inquiry')],
        },
        fallbacks=[CommandHandler("cancel", cancel_inquiry)],
        # conversation_timeout_function=conversation_timeout, # Aktiviraj kada sve radi
        # timeout=600 # 10 minuta neaktivnosti
    )

    # Dodaj handlere
    application.add_handler(CommandHandler("start", start)) ## VAŽNO: Ovo registruje /start komandu
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(button_callback)) # Button callback treba da bude posle conv_handler da bi se obradili callback-ovi koji nisu deo conv_handler-a

    return application # Vraćamo konfigurisanu aplikaciju

## VAŽNO: Glavni blok za pokretanje, izvršava se kada se skripta pokrene direktno
if __name__ == "__main__":
    # Ova promenljiva govori da li smo u lokalnom razvojnom okruženju ili na Renderu
    IS_ON_RENDER = os.getenv("ON_RENDER", "false").lower() == "true"
    PORT = int(os.environ.get('PORT', '8080'))

    application = main() # Inicijalizacija aplikacije

    if IS_ON_RENDER:
        WEBHOOK_URL = os.getenv("WEBHOOK_URL")
        if not WEBHOOK_URL:
             logger.critical("Greška: WEBHOOK_URL environment varijabla NIJE podešena za Render deployment!")
             raise ValueError("WEBHOOK_URL environment varijabla nije pronađena.")

        logger.info("Pokrećem bota na Renderu (webhook)...")
        async def setup_webhook():
            # Uvek obriši prethodni webhook pre postavljanja novog
            await application.bot.delete_webhook()
            # Postavi webhook. Url_path je prazan, jer se ceo URL šalje u set_webhook
            await application.bot.set_webhook(url=WEBHOOK_URL)
            logger.info(f"Webhook uspešno postavljen na: {WEBHOOK_URL}")

        # Pokreni async funkciju za postavljanje webhooka
        asyncio.run(setup_webhook())

        # Sada pokrećemo webhook server
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path="", # url_path treba biti prazan ako je ceo WEBHOOK_URL poslat Telegramu
            webhook_url=WEBHOOK_URL # Pun URL za Telegram
        )
        logger.info("Webhook server je pokrenut i sluša zahteve.")

    else:
        logger.info("Pokrećem bota u lokalnom modu (polling)...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)