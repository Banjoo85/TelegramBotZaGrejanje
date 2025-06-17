# main.py
import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from config import (
    TELEGRAM_BOT_TOKEN,
    LANGUAGES,
    START_MESSAGES,
    CONTACTS,
    MY_BCC_EMAIL,
    WEBHOOK_URL,
    WEBHOOK_SECRET,
    SMTP_EMAIL_USER,
    SMTP_EMAIL_PASSWORD
)

# Konfiguracija logovanja (za praćenje šta se dešava sa botom)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Glavni Handleri ---

async def start(update: Update, context):
    """Šalje pozdravnu poruku i inline tastaturu za odabir jezika."""
    keyboard = []
    for lang_code, lang_name in LANGUAGES.items():
        keyboard.append([InlineKeyboardButton(lang_name, callback_data=f"select_lang:{lang_code}")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Dobrodošli! / Welcome! / Добро пожаловать!\n\nPlease choose your language / Molimo izaberite jezik / Пожалуйста, выберите язык:",
        reply_markup=reply_markup
    )

async def button(update: Update, context):
    """Obrađuje klikove na inline dugmad."""
    query = update.callback_query
    await query.answer()

    data = query.data
    
    if data.startswith("select_lang:"):
        lang_code = data.split(":")[1]
        context.user_data['language'] = lang_code
        await query.edit_message_text(text=f"{START_MESSAGES[lang_code]}")
        await send_country_selection(update, context)

    elif data.startswith("select_country:"):
        country = data.split(":")[1]
        context.user_data['country'] = country
        await query.edit_message_text(
            text=f"Odabrana zemlja: **{country}**\n\nSada možete izabrati vrstu instalacije:",
            parse_mode='Markdown'
        )
        await send_installation_type_selection(update, context)

    elif data == "select_grejanje":
        context.user_data['installation_type'] = 'grejanje'
        await query.edit_message_text(text="Odabrali ste grejnu instalaciju.")
        await send_heating_options(update, context)

    elif data == "select_toplotna_pumpa":
        context.user_data['installation_type'] = 'toplotna_pumpa'
        await query.edit_message_text(text="Odabrali ste toplotnu pumpu.")
        await send_heatpump_options(update, context)

    # --- Ovdje će ići novi handleri za tipove grejanja/TP-a i prikupljanje podataka ---
    elif data.startswith("heating_type:"):
        heating_type = data.split(":")[1]
        context.user_data['heating_type'] = heating_type
        await query.edit_message_text(f"Odabrali ste: {heating_type.replace('_', ' ').capitalize()}")
        await query.message.reply_text("Molimo unesite površinu objekta u m²:")
        context.user_data['state'] = 'awaiting_area' # Postavljanje stanja za ConversationHandler

    elif data.startswith("hp_type:"):
        hp_type = data.split(":")[1]
        context.user_data['hp_type'] = hp_type
        await query.edit_message_text(f"Odabrali ste: {hp_type.replace('_', ' ').capitalize()} toplotnu pumpu.")
        await query.message.reply_text("Molimo unesite površinu objekta u m²:")
        context.user_data['state'] = 'awaiting_area'

async def send_country_selection(update: Update, context):
    """Šalje inline tastaturu za odabir zemlje."""
    keyboard = [
        [InlineKeyboardButton("Srbija 🇷🇸", callback_data="select_country:Srbija")],
        [InlineKeyboardButton("Crna Gora 🇲🇪", callback_data="select_country:Crna Gora")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Molimo izaberite zemlju:",
        reply_markup=reply_markup
    )

async def send_installation_type_selection(update: Update, context):
    """Šalje inline tastaturu za odabir tipa instalacije."""
    keyboard = [
        [InlineKeyboardButton("Grejna instalacija", callback_data="select_grejanje")],
        [InlineKeyboardButton("Toplotna pumpa", callback_data="select_toplotna_pumpa")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Molimo izaberite vrstu instalacije:",
        reply_markup=reply_markup
    )

async def send_heating_options(update: Update, context):
    """Šalje opcije za grejnu instalaciju zavisno od zemlje."""
    country = context.user_data.get('country')
    if country == "Srbija":
        izvodjac = CONTACTS["Srbija"]["grejanje"]
        contact_info = f"**Izvođač radova za Srbiju:**\nIme: {izvodjac['ime']}\nEmail: {izvodjac['email']}\nTelefon: {izvodjac['telefon']}\nTelegram: {izvodjac['telegram']}\n\n"
        keyboard = [
            [InlineKeyboardButton("Radijatori", callback_data="heating_type:radijatori")],
            [InlineKeyboardButton("Fancoil-i", callback_data="heating_type:fancoili")],
            [InlineKeyboardButton("Podno grejanje", callback_data="heating_type:podno")],
            [InlineKeyboardButton("Podno grejanje + Fancoil-i", callback_data="heating_type:podno_fancoili")],
            [InlineKeyboardButton("Komplet ponuda sa toplotnom pumpom", callback_data="heating_type:tp_komplet")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"{contact_info}Molimo izaberite specifičnu opciju grejne instalacije:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    elif country == "Crna Gora":
        izvodjac = CONTACTS["Crna Gora"]["general"]
        contact_info = f"**Partner firma za Crnu Goru:**\nFirma: {izvodjac['firma']}\nKontakt osoba: {izvodjac['kontakt_osoba']}\nEmail: {izvodjac['email']}\nTelefon: {izvodjac['telefon']}\nTelegram: {izvodjac['telegram']}\n\n"
        keyboard = [
            [InlineKeyboardButton("Radijatori", callback_data="heating_type:radijatori_cg")],
            [InlineKeyboardButton("Fancoil-i", callback_data="heating_type:fancoili_cg")],
            [InlineKeyboardButton("Podno grejanje", callback_data="heating_type:podno_cg")],
            [InlineKeyboardButton("Podno grejanje + Fancoil-i", callback_data="heating_type:podno_fancoili_cg")],
            [InlineKeyboardButton("Komplet ponuda sa toplotnom pumpom", callback_data="heating_type:tp_komplet_cg")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"{contact_info}Molimo izaberite specifičnu opciju grejne instalacije:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

async def send_heatpump_options(update: Update, context):
    """Šalje opcije za toplotne pumpe zavisno od zemlje."""
    country = context.user_data.get('country')
    if country == "Srbija":
        proizvodjac = CONTACTS["Srbija"]["toplotna_pumpa"]
        contact_info = f"**Proizvođač toplotnih pumpi za Srbiju:**\nFirma: {proizvodjac['firma']}\nKontakt osoba: {proizvodjac['kontakt_osoba']}\nEmail: {proizvodjac['email']}\nTelefon: {proizvodjac['telefon']}\nWeb: {proizvodjac['web']}\n\n"
        keyboard = [
            [InlineKeyboardButton("Voda-voda", callback_data="hp_type:voda_voda")],
            [InlineKeyboardButton("Vazduh-voda", callback_data="hp_type:vazduh_voda")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"{contact_info}Molimo izaberite tip toplotne pumpe:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    elif country == "Crna Gora":
        partner = CONTACTS["Crna Gora"]["general"]
        contact_info = f"**Partner firma za Crnu Goru:**\nFirma: {partner['firma']}\nKontakt osoba: {partner['kontakt_osoba']}\nEmail: {partner['email']}\nTelefon: {partner['telefon']}\nTelegram: {partner['telegram']}\n\n"
        keyboard = [
            [InlineKeyboardButton("Vazduh-voda", callback_data="hp_type:vazduh_voda_cg")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"{contact_info}Molimo izaberite tip toplotne pumpe:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

async def handle_text_input(update: Update, context):
    """Obrađuje tekstualne unose na osnovu trenutnog stanja konverzacije."""
    user_message = update.message.text
    chat_id = update.effective_chat.id
    current_state = context.user_data.get('state')

    if current_state == 'awaiting_area':
        try:
            area = float(user_message)
            context.user_data['area'] = area
            await update.message.reply_text("Hvala! Molimo unesite spratnost objekta:")
            context.user_data['state'] = 'awaiting_floors'
        except ValueError:
            await update.message.reply_text("Molimo unesite validan broj za površinu (npr. 120.5):")
    
    elif current_state == 'awaiting_floors':
        try:
            floors = int(user_message)
            context.user_data['floors'] = floors
            await update.message.reply_text("Hvala! Molimo unesite vrstu objekta (npr. kuća, stan, poslovni prostor):")
            context.user_data['state'] = 'awaiting_object_type'
        except ValueError:
            await update.message.reply_text("Molimo unesite validan ceo broj za spratnost (npr. 2):")

    elif current_state == 'awaiting_object_type':
        context.user_data['object_type'] = user_message
        await update.message.reply_text("Hvala! Da li imate neku skicu ili dodatne napomene? Unesite tekst ili pošaljite sliku/PDF, ili kucajte 'Nema':")
        context.user_data['state'] = 'awaiting_sketch_or_notes'

    elif current_state == 'awaiting_sketch_or_notes':
        if user_message.lower() == 'nema':
            context.user_data['notes'] = "Korisnik nije priložio skicu niti dodatne napomene."
            await request_contact_info(update, context) # Idemo na sledeći korak
        else:
            context.user_data['notes'] = user_message # Ako je tekst, čuvamo kao belešku
            await update.message.reply_text("Hvala na napomenama.")
            await request_contact_info(update, context) # Idemo na sledeći korak
        # Ovdje ćemo kasnije dodati obradu za sliku/PDF
    
    elif current_state == 'awaiting_phone':
        phone = user_message.strip()
        # Osnovna validacija telefona (može se poboljšati)
        if phone.lower() == 'preskoči' or len(phone) >= 5: # Pretpostavimo minimum 5 cifara
            context.user_data['phone'] = phone if phone.lower() != 'preskoči' else 'Nije priložen'
            await update.message.reply_text("Hvala! Molimo unesite vašu e-mail adresu ili kucajte 'Preskoči':")
            context.user_data['state'] = 'awaiting_email'
        else:
            await update.message.reply_text("Molimo unesite validan broj telefona ili kucajte 'Preskoči':")

    elif current_state == 'awaiting_email':
        email = user_message.strip()
        # Osnovna validacija emaila
        if email.lower() == 'preskoči' or ('@' in email and '.' in email):
            context.user_data['email'] = email if email.lower() != 'preskoči' else 'Nije priložen'
            await summarize_and_confirm(update, context) # Idemo na sumiranje i potvrdu
        else:
            await update.message.reply_text("Molimo unesite validnu e-mail adresu ili kucajte 'Preskoči':")

async def request_contact_info(update: Update, context):
    """Traži od korisnika kontakt telefon."""
    await update.message.reply_text("Odlično! Sada su nam potrebni vaši kontakt podaci kako bi vas izvođač radova mogao kontaktirati u vezi ponude.\n\nMolimo vas, unesite vaš **kontakt telefon** (npr. +3816XXXXXXXX) ili kucajte 'Preskoči':")
    context.user_data['state'] = 'awaiting_phone'

async def summarize_and_confirm(update: Update, context):
    """Sumira prikupljene podatke i traži potvrdu za slanje."""
    user_data = context.user_data
    
    summary = (
        "Hvala! Evo sumarnih podataka za vaš upit:\n\n"
        "**Podaci o objektu:**\n"
        f"- Zemlja: {user_data.get('country', 'Nije navedeno')}\n"
        f"- Vrsta instalacije: {user_data.get('installation_type', 'Nije navedeno').replace('_', ' ').capitalize()}\n"
        f"- Tip grejanja/TP: {user_data.get('heating_type', user_data.get('hp_type', 'Nije navedeno')).replace('_', ' ').capitalize()}\n"
        f"- Površina: {user_data.get('area', 'Nije navedeno')} m²\n"
        f"- Spratnost: {user_data.get('floors', 'Nije navedeno')}\n"
        f"- Vrsta objekta: {user_data.get('object_type', 'Nije navedeno')}\n"
        f"- Skica/Napomene: {user_data.get('notes', 'Nema')}\n\n"
        "**Vaši kontakt podaci:**\n"
        f"- Telefon: {user_data.get('phone', 'Nije priložen')}\n"
        f"- E-mail: {user_data.get('email', 'Nije priložen')}\n"
        f"- Vaš Telegram ID: @{update.effective_user.username if update.effective_user.username else update.effective_user.id}\n\n"
        "Molimo vas, potvrdite da su podaci tačni pre slanja."
    )

    keyboard = [
        [InlineKeyboardButton("Pošalji upit", callback_data="confirm_send_query")],
        [InlineKeyboardButton("Izmeni podatke", callback_data="edit_data")], # Vraćanje na početak
        [InlineKeyboardButton("Odustani", callback_data="cancel_query")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(summary, reply_markup=reply_markup, parse_mode='Markdown')
    context.user_data['state'] = 'awaiting_confirmation'

async def confirm_send_query(update: Update, context):
    """Šalje upit odgovarajućem izvođaču."""
    query = update.callback_query
    await query.answer()

    user_data = context.user_data
    country = user_data.get('country')
    installation_type = user_data.get('installation_type')

    recipient_email = None
    if country == "Srbija":
        if installation_type == "grejanje":
            recipient_email = CONTACTS["Srbija"]["grejanje"]["email"]
        elif installation_type == "toplotna_pumpa":
            recipient_email = CONTACTS["Srbija"]["toplotna_pumpa"]["email"]
    elif country == "Crna Gora":
        recipient_email = CONTACTS["Crna Gora"]["general"]["email"]

    if recipient_email and SMTP_EMAIL_USER and SMTP_EMAIL_PASSWORD:
        try:
            import yagmail
            yag = yagmail.SMTP(user=SMTP_EMAIL_USER, password=SMTP_EMAIL_PASSWORD)

            subject = f"Novi upit za {installation_type.replace('_', ' ').capitalize()} ({country})"
            
            # Prikupite sve podatke za email telo
            email_body = (
                f"Novi upit od korisnika Telegram bota:\n\n"
                f"**Podaci o objektu:**\n"
                f"- Zemlja: {user_data.get('country', 'Nije navedeno')}\n"
                f"- Vrsta instalacije: {user_data.get('installation_type', 'Nije navedeno').replace('_', ' ').capitalize()}\n"
                f"- Tip grejanja/TP: {user_data.get('heating_type', user_data.get('hp_type', 'Nije navedeno')).replace('_', ' ').capitalize()}\n"
                f"- Površina: {user_data.get('area', 'Nije navedeno')} m²\n"
                f"- Spratnost: {user_data.get('floors', 'Nije navedeno')}\n"
                f"- Vrsta objekta: {user_data.get('object_type', 'Nije navedeno')}\n"
                f"- Skica/Napomene: {user_data.get('notes', 'Nema')}\n\n"
                f"**Kontakt podaci korisnika:**\n"
                f"- Telefon: {user_data.get('phone', 'Nije priložen')}\n"
                f"- E-mail: {user_data.get('email', 'Nije priložen')}\n"
                f"- Telegram ID: @{update.effective_user.username if update.effective_user.username else update.effective_user.id}\n"
            )

            yag.send(
                to=recipient_email,
                subject=subject,
                contents=email_body,
                bcc=MY_BCC_EMAIL # Vaš email kao BCC
            )
            await query.edit_message_text("Vaš upit je uspešno poslat! Izvođač će vas uskoro kontaktirati.")
            logger.info(f"Email sent to {recipient_email} from {SMTP_EMAIL_USER}")
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            await query.edit_message_text("Došlo je do greške prilikom slanja upita. Molimo pokušajte ponovo kasnije.")
    else:
        await query.edit_message_text("Nije moguće poslati upit, podaci o primaocu ili SMTP podaci nisu ispravno konfigurisani.")

    context.user_data.clear() # Resetuj stanje konverzacije nakon slanja/greške

async def edit_data(update: Update, context):
    """Vraća korisnika na početak unosa podataka (ili specifičan korak)."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("U redu, molim vas ponovo unesite podatke. Počnimo od površine objekta u m²:")
    context.user_data['state'] = 'awaiting_area' # Resetujemo na početak unosa podataka

async def cancel_query(update: Update, context):
    """Otkaže upit."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Upit je otkazan. Možete započeti novi upit komandom /start.")
    context.user_data.clear() # Resetuj stanje konverzacije

async def unknown(update: Update, context):
    """Odgovara na nepoznate komande i tekst ako bot nije u očekivanom stanju."""
    if 'state' in context.user_data and context.user_data['state'].startswith('awaiting_'):
        # Ovo znači da bot očekuje specifičan unos, a nije komanda.
        # Handle_text_input će se pozvati za ovo.
        pass # Ne radimo ništa ovde, MessageHandler(filters.TEXT) će to preuzeti
    else:
        await update.message.reply_text("Izvinite, ne razumem tu komandu. Molimo koristite dugmad ili unesite tražene informacije.")


# --- Glavna funkcija za pokretanje bota ---

def main():
    """Pokreće bota."""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button))

    # Handler za tekstualne unose na osnovu stanja
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))

    # Callback Handleri za potvrdu/izmenu/otkazivanje
    application.add_handler(CallbackQueryHandler(confirm_send_query, pattern='^confirm_send_query$'))
    application.add_handler(CallbackQueryHandler(edit_data, pattern='^edit_data$'))
    application.add_handler(CallbackQueryHandler(cancel_query, pattern='^cancel_query$'))


    application.add_handler(MessageHandler(filters.COMMAND, unknown)) # Za nepoznate komande

    # Za hostovanje na Renderu, MORATE koristiti Webhooks
    port = int(os.environ.get('PORT', '8080')) # Render obično koristi PORT env varijablu

    # Važno: WEBHOOK_URL je domen Rendera, a url_path je putanja unutar tog domena
    # setWebhook API pozivu treba puna putanja (webhook_url parametar)
    # dok run_webhook sluša na putanji unutar vaše aplikacije (url_path parametar)
    # Za Render je najjednostavnije da url_path bude prazan, a webhook_url kompletna putanja.
    
    if not WEBHOOK_URL:
        logger.error("RENDER_EXTERNAL_HOSTNAME (WEBHOOK_URL) environment variable is not set. Cannot start webhook.")
        # Fallback to polling for local development if webhook not set
        logger.info("Falling back to polling for local development. Set RENDER_EXTERNAL_HOSTNAME for webhook deployment.")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    else:
        logger.info(f"Starting bot with webhook at https://{WEBHOOK_URL}/webhook on port {port}...")
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path="webhook", # Telegram će pogoditi https://your-render-domain.onrender.com/webhook
            webhook_url=f"https://{WEBHOOK_URL}/webhook",
            secret_token=WEBHOOK_SECRET
        )
    logger.info("Bot started.")

if __name__ == '__main__':
    main()