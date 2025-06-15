import logging
import os
import json
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

# Učitaj BOT_TOKEN iz okruženja
API_TOKEN = os.getenv("BOT_TOKEN")
if not API_TOKEN:
    raise ValueError("BOT_TOKEN nije postavljen u ENV!")

# Inicijalizacija bota i dispečera
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Postavke logovanja
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- PODACI ZA KONTAKT I ADMINI ---
contact_info = {
    'srbija': {
        'contractor': {
            'name': 'Igor Boskovic', # Dodao sam 'name' polje
            'phone': '+381603932566',
            'email': 'boskovicigor83@gmail.com',
            'website': '', # Prazan string umesto ':' ako nema sajta
            'telegram': '@IgorNS1983'
        },
        'manufacturer': {
            'name': 'Microma',
            'phone': '+38163582068',
            'email': 'office@microma.rs',
            'website': 'https://microma.rs',
            'telegram': '' # Prazan string umesto ':' ako nema Telegrama
        }
    },
    'crna_gora': {
        'contractor': {
            'name': 'Instal M',
            'phone': '+38267423237',
            'email': 'office@instalm.me',
            'website': '', # Prazan string
            'telegram': '@ivanmujovic'
        }
    }
}

ADMIN_IDS = [
    6869162490,  # Tvoj Telegram ID; BCC kopija upita ide ovde
]

# Globalna varijabla za poruke
ALL_MESSAGES = {}

def load_messages():
    messages = {}
    # Učitavamo sve podržane jezike
    for lang in ['en', 'sr', 'de', 'ru']:
        try:
            with open(f'messages_{lang}.json', 'r', encoding='utf-8') as f:
                messages[lang] = json.load(f)
        except FileNotFoundError:
            logger.error(f"messages_{lang}.json not found. Creating empty dict for {lang}.")
            messages[lang] = {} # Kreiraj prazan rječnik ako fajl ne postoji
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from messages_{lang}.json. Check file format.")
            messages[lang] = {} # Kreiraj prazan rječnik ako je format pogrešan
    return messages

# Učitavanje poruka na početku skripte
ALL_MESSAGES = load_messages()

# Funkcija za dobijanje poruka za određenog korisnika
async def get_messages_for_user(user_id: int, state: FSMContext):
    user_data = await state.get_data()
    # Pokušaj dohvatiti jezik iz FSMContext-a
    lang = user_data.get('language')

    # Ako jezik nije postavljen u FSMContext-u, pokušaj iz Telegram klijenta
    if not lang:
        try:
            # Aiogram način za dobijanje user objecta iz callback_query ili message
            # Ako je iz poruke: message.from_user.language_code
            # Ako je iz callbacka: callback_query.from_user.language_code
            # Treba nam robustniji način da dobijemo user_object bez preterane logike
            
            # Za start komandu, language_code je direktno dostupan
            # Za callback_query, takođe je direktno dostupan
            # Ne treba nam bot.get_chat_member ovde, jer su user podaci već u Message/CallbackQuery objektu.
            pass # Odlučili smo da ne radimo automatsku detekciju na početku
                 # već da uvek nudimo izbor jezika eksplicitno.
                 # Dakle, ova logika bi se koristila SAMO ako bismo imali fallback.
                 # Za sada, default je 'sr' ako nema izbora.
        except Exception as e:
            logger.warning(f"Greška pri pokušaju automatske detekcije jezika: {e}")
            lang = 'sr' # Fallback na srpski ako dođe do greške ili se ne detektuje

    # Ako i dalje nema jezika iz state-a, postaviti default
    if not lang:
        lang = 'sr'

    # Uverite se da je izabrani jezik validan i da postoje poruke za njega
    if lang not in ALL_MESSAGES or not ALL_MESSAGES[lang]:
        logger.warning(f"Jezik '{lang}' nije pronađen ili je prazan u ALL_MESSAGES. Vraćam na 'sr'.")
        lang = 'sr' # Fallback na srpski
        if lang not in ALL_MESSAGES or not ALL_MESSAGES[lang]:
            logger.error(f"Ni fallback jezik 'sr' nije pronađen ili je prazan. Vraćam prazan rječnik.")
            return {} # Kao poslednje rešenje, vratite prazan dict
    
    # Ažuriraj jezik u FSMContext-u ako je promenjen ili prvi put postavljen
    if user_data.get('language') != lang:
        await state.update_data(language=lang)
    
    return ALL_MESSAGES[lang]


# Definišemo FSM za unos podataka o objektu
class ObjectInfo(StatesGroup):
    awaiting_object_type = State()
    awaiting_area = State()
    awaiting_floors = State()
    awaiting_sketch = State()
    confirming = State()
    choosing_language = State() # Dodajemo stanje za izbor jezika
    choosing_country = State() # Dodajemo stanje za izbor zemlje

# /start handler – pozdravna poruka i izbor jezika
@dp.message_handler(commands=['start'], state="*") # Omogućava restart iz bilo kog stanja
async def send_welcome(message: types.Message, state: FSMContext):
    # Inicijalizujemo jezik korisnika na 'sr' ako nije postavljen (ili ako je resetovan FSM)
    # Ovaj poziv će se pobrinuti da 'language' bude setovan u state-u
    messages = await get_messages_for_user(message.from_user.id, state)

    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(messages.get('english_button_text', 'English 🇬🇧'), callback_data="lang_en"),
        InlineKeyboardButton(messages.get('serbian_button_text', 'Srpski 🇷🇸'), callback_data="lang_sr"),
        InlineKeyboardButton(messages.get('german_button_text', 'Deutsch 🇩🇪'), callback_data="lang_de"),
        InlineKeyboardButton(messages.get('russian_button_text', 'Русский 🇷🇺'), callback_data="lang_ru") # DODATO: Taster za ruski
    )
    # Koristimo edit_message_text ako je poruka već poslata (npr. na restart), inače send_message
    try:
        await message.answer(messages.get('choose_language_text', 'Please choose your language:'), reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Could not edit message for language choice, sending new one: {e}")
        await message.reply(messages.get('choose_language_text', 'Please choose your language:'), reply_markup=keyboard)

    await ObjectInfo.choosing_language.set() # Postavi stanje na izbor jezika

# Handler za izbor jezika
@dp.callback_query_handler(lambda c: c.data.startswith('lang_'), state=ObjectInfo.choosing_language)
async def process_language_selection(callback_query: types.CallbackQuery, state: FSMContext):
    lang_code = callback_query.data.split('_')[1]
    await state.update_data(language=lang_code) # Sačuvaj izabrani jezik
    messages = await get_messages_for_user(callback_query.from_user.id, state) # Dohvati poruke na novom jeziku

    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton(messages.get('srbija_button', 'Srbija'), callback_data="country_srbija"),
        InlineKeyboardButton(messages.get('crna_gora_button', 'Crna Gora'), callback_data="country_crna_gora")
    )
    # Ažurirajte poruku (koja je prethodno prikazivala izbor jezika) sa izborom zemlje
    await bot.edit_message_text(
        text=messages.get('choose_country_text', 'Molimo izaberite zemlju:'),
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        reply_markup=keyboard
    )
    await bot.answer_callback_query(callback_query.id)
    await ObjectInfo.choosing_country.set() # Postavi stanje na izbor zemlje


# Handler za izbor zemlje
@dp.callback_query_handler(lambda c: c.data.startswith('country_'), state=ObjectInfo.choosing_country)
async def process_country_selection(callback_query: types.CallbackQuery, state: FSMContext):
    country = callback_query.data.split('_')[1]
    await state.update_data(country=country) # Sačuvaj izabranu zemlju
    messages = await get_messages_for_user(callback_query.from_user.id, state)

    keyboard = InlineKeyboardMarkup(row_width=1)
    if country == 'srbija':
        keyboard.add(
            InlineKeyboardButton(messages.get('heating_installation_button', 'Grejna instalacija'), callback_data="srbija_greinastall"),
            InlineKeyboardButton(messages.get('heat_pump_button', 'Toplotna pumpa'), callback_data="srbija_toplotnapumpa")
        )
        await bot.edit_message_text(
            text=messages.get('srbija_options_text', 'Izaberite opciju za Srbiju:'),
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            reply_markup=keyboard
        )
    elif country == 'crna_gora':
        keyboard.add(
            InlineKeyboardButton(messages.get('heating_installation_button', 'Grejna instalacija'), callback_data="crnagora_greinastall"),
            InlineKeyboardButton(messages.get('heat_pump_button', 'Toplotna pumpa'), callback_data="crnagora_toplotnapumpa")
        )
        await bot.edit_message_text(
            text=messages.get('crna_gora_options_text', 'Izaberite opciju za Crnu Goru:'),
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            reply_markup=keyboard
        )
    await bot.answer_callback_query(callback_query.id)
    # Izlazimo iz stanja izbora zemlje, sledeći handleri će se uhvatiti na osnovu callback_data
    await state.set_state(None) # Opciono: možete postaviti na neko opštije stanje, npr. MAIN_MENU

# --- HANDLERI ZA INSTALACIJU (AŽURIRANI) ---

# Srbija – Grejna instalacija
@dp.callback_query_handler(lambda c: c.data == "srbija_greinastall")
async def process_srbija_greinastall(callback_query: types.CallbackQuery, state: FSMContext):
    messages = await get_messages_for_user(callback_query.from_user.id, state)
    keyboard = InlineKeyboardMarkup(row_width=1)
    options = [
        (messages.get('radiators_button', 'Radijatori'), "srbija_inst_radijatori"),
        (messages.get('fancoils_button', 'Fancoil-i'), "srbija_inst_fancoil"),
        (messages.get('underfloor_heating_button', 'Podno grejanje'), "srbija_inst_podno"),
        (messages.get('underfloor_heating_fancoils_button', 'Podno grejanje + Fancoil-i'), "srbija_inst_podno_fancoil"),
        (messages.get('complete_offer_hp_button', 'Komplet ponuda sa toplotnom pumpom'), "srbija_inst_komplet")
    ]
    for text, data in options:
        keyboard.add(InlineKeyboardButton(text, callback_data=data))
    await bot.edit_message_text(
        text=messages.get('heating_installation_sub_options_text', 'Izaberite opciju grejne instalacije za Srbiju:'), # Dodat novi ključ
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        reply_markup=keyboard
    )
    await bot.answer_callback_query(callback_query.id)

# Srbija – Toplotna pumpa
@dp.callback_query_handler(lambda c: c.data == "srbija_toplotnapumpa")
async def process_srbija_toplotnapumpa(callback_query: types.CallbackQuery, state: FSMContext):
    messages = await get_messages_for_user(callback_query.from_user.id, state)
    keyboard = InlineKeyboardMarkup(row_width=1)
    options = [
        (messages.get('water_to_water_hp_button', 'Voda-voda'), "srbija_toplotna_voda"),
        (messages.get('air_to_water_hp_button', 'Vazduh-voda'), "srbija_toplotna_vazduh")
    ]
    for text, data in options:
        keyboard.add(InlineKeyboardButton(text, callback_data=data))
    await bot.edit_message_text(
        text=messages.get('heat_pump_sub_options_text', 'Izaberite opciju toplotne pumpe za Srbiju:'), # Dodat novi ključ
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        reply_markup=keyboard
    )
    await bot.answer_callback_query(callback_query.id)

# Crna Gora – Grejna instalacija (sve 5 opcija)
@dp.callback_query_handler(lambda c: c.data == "crnagora_greinastall")
async def process_crnagora_greinastall(callback_query: types.CallbackQuery, state: FSMContext):
    messages = await get_messages_for_user(callback_query.from_user.id, state)
    keyboard = InlineKeyboardMarkup(row_width=1)
    options = [
        (messages.get('radiators_button', 'Radijatori'), "crnagora_inst_radijatori"),
        (messages.get('fancoils_button', 'Fancoil-i'), "crnagora_inst_fancoil"),
        (messages.get('underfloor_heating_button', 'Podno grejanje'), "crnagora_inst_podno"),
        (messages.get('underfloor_heating_fancoils_button', 'Podno grejanje + Fancoil-i'), "crnagora_inst_podno_fancoil"),
        (messages.get('complete_offer_hp_button', 'Komplet ponuda sa toplotnom pumpom'), "crnagora_inst_komplet")
    ]
    for text, data in options:
        keyboard.add(InlineKeyboardButton(text, callback_data=data))
    await bot.edit_message_text(
        text=messages.get('heating_installation_sub_options_text', 'Izaberite opciju grejne instalacije za Crnu Goru:'), # Dodat novi ključ
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        reply_markup=keyboard
    )
    await bot.answer_callback_query(callback_query.id)

# Crna Gora – Toplotna pumpa
@dp.callback_query_handler(lambda c: c.data == "crnagora_toplotnapumpa")
async def process_crnagora_toplotnapumpa(callback_query: types.CallbackQuery, state: FSMContext):
    messages = await get_messages_for_user(callback_query.from_user.id, state)
    keyboard = InlineKeyboardMarkup(row_width=1)
    # Za Crnu Goru se nudi samo opcija vazduh-voda
    keyboard.add(InlineKeyboardButton(messages.get('air_to_water_hp_button', 'Vazduh-voda'), callback_data="crnagora_toplotna_vazduh"))
    await bot.edit_message_text(
        text=messages.get('heat_pump_sub_options_text', 'Izaberite opciju toplotne pumpe za Crnu Goru:'), # Dodat novi ključ
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        reply_markup=keyboard
    )
    await bot.answer_callback_query(callback_query.id)

# Handler za instalacijske i HP opcije – krećemo unos podataka o objektu
@dp.callback_query_handler(lambda c: c.data in [
    "srbija_inst_radijatori", "srbija_inst_fancoil", "srbija_inst_podno", "srbija_inst_podno_fancoil", "srbija_inst_komplet",
    "crnagora_inst_radijatori", "crnagora_inst_fancoil", "crnagora_inst_podno", "crnagora_inst_podno_fancoil", "crnagora_inst_komplet",
    "srbija_toplotna_voda", "srbija_toplotna_vazduh", "crnagora_toplotna_vazduh"
])
async def process_selection_and_start_object_info(callback_query: types.CallbackQuery, state: FSMContext):
    user_choice = callback_query.data
    await state.update_data(installation_choice=user_choice)
    messages = await get_messages_for_user(callback_query.from_user.id, state)
    await bot.edit_message_text(
        text=messages.get('object_type_prompt', "Molimo unesite tip objekta (npr. kuća, stan, poslovni prostor):"),
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        reply_markup=None # Ukloni dugmad
    )
    await ObjectInfo.awaiting_object_type.set()
    await bot.answer_callback_query(callback_query.id)

# FSM – unos tipa objekta
@dp.message_handler(state=ObjectInfo.awaiting_object_type)
async def process_object_type(message: types.Message, state: FSMContext):
    await state.update_data(object_type=message.text)
    messages = await get_messages_for_user(message.from_user.id, state)
    await message.reply(messages.get('area_prompt', "Unesite površinu objekta (u m²):"))
    await ObjectInfo.awaiting_area.set()

# FSM – unos površine
@dp.message_handler(state=ObjectInfo.awaiting_area)
async def process_area(message: types.Message, state: FSMContext):
    # Provera da li je uneta vrednost numerička
    try:
        area_value = float(message.text.replace(',', '.')) # Omogućava i unos sa zarezom
        if area_value <= 0:
            raise ValueError
        await state.update_data(area=str(area_value)) # Čuvamo kao string, ali znamo da je validan broj
    except ValueError:
        messages = await get_messages_for_user(message.from_user.id, state)
        await message.reply(messages.get('invalid_area_input', "Nevažeći unos. Molimo unesite samo broj (npr. '120')."))
        return # Ostajemo u istom stanju

    messages = await get_messages_for_user(message.from_user.id, state)
    await message.reply(messages.get('floors_prompt', "Unesite broj etaža:"))
    await ObjectInfo.awaiting_floors.set()

# FSM – unos broja etaža
@dp.message_handler(state=ObjectInfo.awaiting_floors)
async def process_floors(message: types.Message, state: FSMContext):
    # Provera da li je uneta vrednost numerička
    try:
        floors_value = int(message.text)
        if floors_value <= 0:
            raise ValueError
        await state.update_data(floors=str(floors_value))
    except ValueError:
        messages = await get_messages_for_user(message.from_user.id, state)
        await message.reply(messages.get('invalid_floors_input', "Nevažeći unos. Molimo unesite samo ceo broj (npr. '2').")) # Dodajte novi ključ
        return # Ostajemo u istom stanju

    messages = await get_messages_for_user(message.from_user.id, state)
    await message.reply(messages.get('sketch_prompt', "Ako želite, pošaljite skicu objekta kao sliku. Ako ne, napišite 'preskoči'."))
    await ObjectInfo.awaiting_sketch.set()

# FSM – unos skice (slika ili tekst „preskoči“)
@dp.message_handler(state=ObjectInfo.awaiting_sketch, content_types=types.ContentTypes.ANY)
async def process_sketch(message: types.Message, state: FSMContext):
    sketch = None
    messages = await get_messages_for_user(message.from_user.id, state)
    
    # Provera da li 'skip_text' postoji u messages, inače koristite 'preskoči' kao default
    skip_word = messages.get('skip_text', 'preskoči').lower()

    if message.text and message.text.lower() == skip_word:
        sketch = None
    elif message.photo:
        photo = message.photo[-1].file_id # bira se najveća slika
        sketch = photo
    elif not message.text and not message.photo: # Ako korisnik pošalje nešto što nije tekst ili slika
        await message.reply(messages.get('invalid_sketch_input', 'Nevažeći unos. Molimo pošaljite sliku ili napišite "preskoči".')) # Dodajte novi ključ
        return # Ostajemo u istom stanju

    await state.update_data(sketch=sketch)

    data = await state.get_data()
    sketch_status = messages.get('sketch_provided_label', 'Dostavljena') if sketch else messages.get('sketch_not_provided_label', 'Nije dostavljena')
    summary = messages.get('summary_text', '').format(
        object_type=data.get('object_type'),
        area=data.get('area'),
        floors=data.get('floors'),
        sketch_status=sketch_status
    )

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(messages.get('send_inquiry_button', 'Pošalji upit'), callback_data="confirm_send"))
    await message.reply(summary, reply_markup=keyboard)
    await ObjectInfo.confirming.set()

# Finalni handler – potvrda i slanje upita
@dp.callback_query_handler(lambda c: c.data == "confirm_send", state=ObjectInfo.confirming)
async def send_upit(callback_query: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    installation_choice = data.get("installation_choice")
    object_type = data.get("object_type")
    area = data.get("area")
    floors = data.get("floors")
    sketch = data.get("sketch")
    selected_language = data.get('language', 'sr') # Dohvati izabrani jezik
    messages = ALL_MESSAGES.get(selected_language, ALL_MESSAGES.get('sr', {})) # Koristi ALL_MESSAGES direktno, fallback na prazan dict ako ni 'sr' ne postoji

    contractor_info = None
    manufacturer_info = None
    country_name = ""
    
    # Odredi državu i informacije o kontaktu
    if installation_choice.startswith("srbija_"):
        country_name = messages.get('srbija_button', 'Srbija')
        contractor_info = contact_info['srbija'].get('contractor')
        manufacturer_info = contact_info['srbija'].get('manufacturer')
    elif installation_choice.startswith("crnagora_"):
        country_name = messages.get('crna_gora_button', 'Crna Gora')
        contractor_info = contact_info['crna_gora'].get('contractor')
    
    # Priprema poruke o upitu
    upit_details = messages.get('inquiry_details_prefix', "Nova porudžbina:") + "\n\n"
    upit_details += f"{messages.get('country_label', 'Država:')} {country_name}\n" # Dodaj ključ u JSON

    # Detalji izabrane opcije
    option_label = ""
    option_type_text = ""
    option_name = ""

    if installation_choice.startswith("srbija_inst_"):
        option_type_text = messages.get('heating_installation_button', 'Grejna instalacija')
        option_name = installation_choice.replace('srbija_inst_', '').replace('_', ' ').capitalize()
    elif installation_choice.startswith("srbija_toplotna_"):
        option_type_text = messages.get('heat_pump_button', 'Toplotna pumpa')
        option_name = installation_choice.replace('srbija_toplotna_', '').replace('_', ' ').capitalize()
    elif installation_choice.startswith("crnagora_inst_"):
        option_type_text = messages.get('heating_installation_button', 'Grejna instalacija')
        option_name = installation_choice.replace('crnagora_inst_', '').replace('_', ' ').capitalize()
    elif installation_choice.startswith("crnagora_toplotna_"):
        option_type_text = messages.get('heat_pump_button', 'Toplotna pumpa')
        option_name = installation_choice.replace('crnagora_toplotna_', '').replace('_', ' ').capitalize()

    if option_type_text and option_name:
        upit_details += f"{messages.get('option_chosen_label', 'Izabrana opcija:')} {option_type_text} ({option_name})\n"
    else:
        upit_details += messages.get('unknown_option', 'Nepoznata opcija.') + "\n"

    # Dodatne informacije za "Komplet ponuda sa toplotnom pumpom"
    if installation_choice == "srbija_inst_komplet" and manufacturer_info:
        upit_details += (
            f"\n{messages.get('complete_offer_hp_button', 'Komplet ponuda sa toplotnom pumpom')} (Microma)\n"
            f"{messages.get('contact_manufacturer_label', 'Kontakt proizvođača:')} {manufacturer_info.get('phone', 'N/A')}, {manufacturer_info.get('email', 'N/A')}\n"
        )
    elif installation_choice == "crnagora_inst_komplet" and contractor_info:
        upit_details += (
            f"\n{messages.get('complete_offer_hp_button', 'Komplet ponuda sa toplotnom pumpom')} (Instal M - Vazduh-voda)\n"
            f"{messages.get('contact_label', 'Kontakt:')} {contractor_info.get('phone', 'N/A')}, {contractor_info.get('email', 'N/A')}\n"
        )
            
    # Podaci o objektu
    upit_details += (
        f"\n{messages.get('object_data_label', 'Podaci o objektu:')}\n"
        f"{messages.get('object_type_label', 'Tip:')} {object_type}\n"
        f"{messages.get('area_label', 'Površina:')} {area} m²\n"
        f"{messages.get('floors_label', 'Broj etaža:')} {floors}\n"
        f"{messages.get('sketch_label', 'Skica:')} {messages.get('sketch_provided_label', 'Dostavljena') if sketch else messages.get('sketch_not_provided_label', 'Nije dostavljena')}\n"
    )

    # Informacije o korisniku
    user_info = callback_query.from_user
    upit_details += (
        f"\n--- {messages.get('user_info_label', 'Informacije o korisniku')} ---\n" # Dodaj ključ
        f"{messages.get('user_id_label', 'ID Korisnika:')} {user_info.id}\n" # Dodaj ključ
        f"{messages.get('first_name_label', 'Ime:')} {user_info.first_name or 'N/A'}\n" # Dodaj ključ
        f"{messages.get('last_name_label', 'Prezime:')} {user_info.last_name or 'N/A'}\n" # Dodaj ključ
        f"{messages.get('username_label', 'Korisničko ime:')} @{user_info.username or 'N/A'}\n" # Dodaj ključ
    )

    # Slanje upita administratorima
    for admin_id in ADMIN_IDS:
        await bot.send_message(admin_id, upit_details)
        if sketch:
            await bot.send_photo(admin_id, photo=sketch) # Šalji skicu kao posebnu poruku
    
    # Slanje potvrde korisniku
    await bot.send_message(callback_query.from_user.id, messages.get('inquiry_sent_success', "Vaš upit je poslat. Hvala!"))
    await state.finish() # Resetuj FSM stanje
    await bot.answer_callback_query(callback_query.id) # Odgovori na callback query

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)