import asyncio
import logging
import os
import json
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv("BOT_TOKEN")
if not API_TOKEN:
    raise ValueError("BOT_TOKEN nije postavljen u ENV!")

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- PODACI ZA KONTAKT I ADMINI ---
contact_info = {
    'srbija': {
        'contractor': {
            'name': 'Igor Boskovic',
            'phone': '+381603932566',
            'email': 'boskovicigor83@gmail.com',
            'website': '',
            'telegram': '@IgorNS1983'
        },
        'manufacturer': {
            'name': 'Microma',
            'phone': '+38163582068',
            'email': 'office@microma.rs',
            'website': 'https://microma.rs',
            'telegram': ''
        }
    },
    'crna_gora': {
        'contractor': {
            'name': 'Instal M',
            'phone': '+38267423237',
            'email': 'office@instalm.me',
            'website': '',
            'telegram': '@ivanmujovic'
        }
    }
}

ADMIN_IDS = [
    6869162490, 
]

ALL_MESSAGES = {}

def load_messages():
    messages = {}
    script_dir = os.path.dirname(__file__)
    
    for lang in ['en', 'sr', 'de', 'ru']:
        file_path = os.path.join(script_dir, f'messages_{lang}.json')
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                messages[lang] = json.load(f)
            logger.info(f"Successfully loaded messages_{lang}.json from {file_path}")
        except FileNotFoundError:
            logger.error(f"messages_{lang}.json not found at {file_path}. Creating empty dict for {lang}.")
            messages[lang] = {}
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from {file_path}. Check file format.")
            messages[lang] = {}
    return messages

ALL_MESSAGES = load_messages()

async def get_messages_for_user(user_data_obj, state: FSMContext):
    user_state_data = await state.get_data()
    lang = user_state_data.get('language')

    if not lang:
        if isinstance(user_data_obj, types.Message):
            lang = user_data_obj.from_user.language_code
        elif isinstance(user_data_obj, types.CallbackQuery):
            lang = user_data_obj.from_user.language_code
        
        if lang and '-' in lang:
            lang = lang.split('-')[0]

        if lang not in ALL_MESSAGES or not ALL_MESSAGES[lang]:
            logger.warning(f"Jezik '{lang}' (automatski detektovan) nije pronađen ili je prazan. Vraćam na 'sr'.")
            lang = 'sr'
    
    if not lang:
        lang = 'sr'

    if lang not in ALL_MESSAGES or not ALL_MESSAGES[lang]:
        logger.error(f"Ni fallback jezik 'sr' nije pronađen ili je prazan. Vraćam prazan rječnik.")
        return {}
    
    if user_state_data.get('language') != lang:
        await state.update_data(language=lang)
    
    return ALL_MESSAGES[lang]


class ObjectInfo(StatesGroup):
    awaiting_object_type = State()
    awaiting_area = State()
    awaiting_floors = State()
    awaiting_sketch = State()
    confirming = State()
    choosing_language = State()
    choosing_country = State()

@dp.message(CommandStart())
async def send_welcome(message: types.Message, state: FSMContext) -> None:
    user_data = await state.get_data()
    if "language" not in user_data: # Koristi 'language' da bude konzistentno sa FSMContext
        # Pokusaj automatsku detekciju jezika pri prvom pokretanju
        detected_lang = message.from_user.language_code.split('-')[0] if message.from_user.language_code else 'sr'
        if detected_lang not in ALL_MESSAGES or not ALL_MESSAGES[detected_lang]:
            detected_lang = 'sr' # Fallback na srpski ako detektovani nije dostupan
        await state.update_data(language=detected_lang)
        user_data = await state.get_data() # Refresh user_data after update

    current_lang = user_data.get("language", "sr") # Sada će 'language' uvek biti postavljen
    messages = ALL_MESSAGES.get(current_lang, ALL_MESSAGES.get('sr', {}))

    keyboard_buttons = [
        [InlineKeyboardButton(text=messages['select_lang'], callback_data="select_language")],
        [InlineKeyboardButton(text=messages['set_temp'], callback_data="set_temperature")],
        [InlineKeyboardButton(text=messages['auto_mode'], callback_data="auto_mode")],
        [InlineKeyboardButton(text=messages['manual_mode'], callback_data="manual_mode")],
        [InlineKeyboardButton(text=messages['status'], callback_data="status")]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await message.answer(messages['welcome_message'], reply_markup=keyboard)


@dp.callback_query(lambda c: c.data == "select_language")
async def request_language_selection(callback_query: types.CallbackQuery, state: FSMContext):
    messages = await get_messages_for_user(callback_query, state)

    keyboard_buttons = [
        [InlineKeyboardButton(text="English 🇬🇧", callback_data="lang_en")],
        [InlineKeyboardButton(text="Srpski 🇷🇸", callback_data="lang_sr")],
        [InlineKeyboardButton(text="Deutsch 🇩🇪", callback_data="lang_de")],
        [InlineKeyboardButton(text="Русский 🇷🇺", callback_data="lang_ru")]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await bot.edit_message_text(
        text=messages.get('choose_language_text', 'Molimo odaberite jezik:'),
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message.id,
        reply_markup=keyboard
    )
    await callback_query.answer()
    await state.set_state(ObjectInfo.choosing_language)

@dp.callback_query(lambda c: c.data.startswith('lang_'), ObjectInfo.choosing_language)
async def process_language_selection(callback_query: types.CallbackQuery, state: FSMContext):
    lang_code = callback_query.data.split('_')[1]
    await state.update_data(language=lang_code)
    messages = await get_messages_for_user(callback_query, state)

    keyboard_buttons = [
        [InlineKeyboardButton(text=messages.get('srbija_button', 'Srbija'), callback_data="country_srbija")],
        [InlineKeyboardButton(text=messages.get('crna_gora_button', 'Crna Gora'), callback_data="country_crna_gora")]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await bot.edit_message_text(
        text=messages.get('choose_country_text', 'Molimo izaberite zemlju:'),
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        reply_markup=keyboard
    )
    await callback_query.answer()
    await state.set_state(ObjectInfo.choosing_country)


@dp.callback_query(lambda c: c.data.startswith('country_'), ObjectInfo.choosing_country)
async def process_country_selection(callback_query: types.CallbackQuery, state: FSMContext):
    country = callback_query.data.split('_')[1]
    await state.update_data(country=country)
    messages = await get_messages_for_user(callback_query, state)

    if country == 'srbija':
        keyboard_buttons = [
            [InlineKeyboardButton(text=messages.get('heating_installation_button', 'Grejna instalacija'), callback_data="srbija_greinastall")],
            [InlineKeyboardButton(text=messages.get('heat_pump_button', 'Toplotna pumpa'), callback_data="srbija_toplotnapumpa")]
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        text_message = messages.get('srbija_options_text', 'Izaberite opciju za Srbiju:')
    elif country == 'crna_gora':
        keyboard_buttons = [
            [InlineKeyboardButton(text=messages.get('heating_installation_button', 'Grejna instalacija'), callback_data="crnagora_greinastall")],
            [InlineKeyboardButton(text=messages.get('heat_pump_button', 'Toplotna pumpa'), callback_data="crnagora_toplotnapumpa")]
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        text_message = messages.get('crna_gora_options_text', 'Izaberite opciju za Crnu Goru:')
    else:
        # Fallback ako je country nepoznat
        await callback_query.answer("Nepoznata zemlja. Molimo pokušajte ponovo.")
        await state.clear() # Resetuj stanje
        return

    await bot.edit_message_text(
        text=text_message,
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        reply_markup=keyboard
    )
    await callback_query.answer()
    await state.set_state(None) # Izlazimo iz stanja izbora zemlje, dalje handleri hvataju na osnovu callback_data


@dp.callback_query(lambda c: c.data == "srbija_greinastall")
async def process_srbija_greinastall(callback_query: types.CallbackQuery, state: FSMContext):
    messages = await get_messages_for_user(callback_query, state)
    options = [
        (messages.get('radiators_button', 'Radijatori'), "srbija_inst_radijatori"),
        (messages.get('fancoils_button', 'Fancoil-i'), "srbija_inst_fancoil"),
        (messages.get('underfloor_heating_button', 'Podno grejanje'), "srbija_inst_podno"),
        (messages.get('underfloor_heating_fancoils_button', 'Podno grejanje + Fancoil-i'), "srbija_inst_podno_fancoil"),
        (messages.get('complete_offer_hp_button', 'Komplet ponuda sa toplotnom pumpom'), "srbija_inst_komplet")
    ]
    keyboard_buttons = [[InlineKeyboardButton(text, callback_data=data)] for text, data in options]
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await bot.edit_message_text(
        text=messages.get('heating_installation_sub_options_text', 'Izaberite opciju grejne instalacije za Srbiju:'),
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        reply_markup=keyboard
    )
    await callback_query.answer()

@dp.callback_query(lambda c: c.data == "srbija_toplotnapumpa")
async def process_srbija_toplotnapumpa(callback_query: types.CallbackQuery, state: FSMContext):
    messages = await get_messages_for_user(callback_query, state)
    options = [
        (messages.get('water_to_water_hp_button', 'Voda-voda'), "srbija_toplotna_voda"),
        (messages.get('air_to_water_hp_button', 'Vazduh-voda'), "srbija_toplotna_vazduh")
    ]
    keyboard_buttons = [[InlineKeyboardButton(text, callback_data=data)] for text, data in options]
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await bot.edit_message_text(
        text=messages.get('heat_pump_sub_options_text', 'Izaberite opciju toplotne pumpe za Srbiju:'),
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        reply_markup=keyboard
    )
    await callback_query.answer()

@dp.callback_query(lambda c: c.data == "crnagora_greinastall")
async def process_crnagora_greinastall(callback_query: types.CallbackQuery, state: FSMContext):
    messages = await get_messages_for_user(callback_query, state)
    options = [
        (messages.get('radiators_button', 'Radijatori'), "crnagora_inst_radijatori"),
        (messages.get('fancoils_button', 'Fancoil-i'), "crnagora_inst_fancoil"),
        (messages.get('underfloor_heating_button', 'Podno grejanje'), "crnagora_inst_podno"),
        (messages.get('underfloor_heating_fancoils_button', 'Podno grejanje + Fancoil-i'), "crnagora_inst_podno_fancoil"),
        (messages.get('complete_offer_hp_button', 'Komplet ponuda sa toplotnom pumpom'), "crnagora_inst_komplet")
    ]
    keyboard_buttons = [[InlineKeyboardButton(text, callback_data=data)] for text, data in options]
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await bot.edit_message_text(
        text=messages.get('heating_installation_sub_options_text', 'Izaberite opciju grejne instalacije za Crnu Goru:'),
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        reply_markup=keyboard
    )
    await callback_query.answer()

@dp.callback_query(lambda c: c.data == "crnagora_toplotnapumpa")
async def process_crnagora_toplotnapumpa(callback_query: types.CallbackQuery, state: FSMContext):
    messages = await get_messages_for_user(callback_query, state)
    keyboard_buttons = [
        [InlineKeyboardButton(messages.get('air_to_water_hp_button', 'Vazduh-voda'), callback_data="crnagora_toplotna_vazduh")]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await bot.edit_message_text(
        text=messages.get('heat_pump_sub_options_text', 'Izaberite opciju toplotne pumpe za Crnu Goru:'),
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        reply_markup=keyboard
    )
    await callback_query.answer()

@dp.callback_query(lambda c: c.data in [
    "srbija_inst_radijatori", "srbija_inst_fancoil", "srbija_inst_podno", "srbija_inst_podno_fancoil", "srbija_inst_komplet",
    "crnagora_inst_radijatori", "crnagora_inst_fancoil", "crnagora_inst_podno", "crnagora_inst_podno_fancoil", "crnagora_inst_komplet",
    "srbija_toplotna_voda", "srbija_toplotna_vazduh", "crnagora_toplotna_vazduh"
])
async def process_selection_and_start_object_info(callback_query: types.CallbackQuery, state: FSMContext):
    user_choice = callback_query.data
    await state.update_data(installation_choice=user_choice)
    messages = await get_messages_for_user(callback_query, state)
    await bot.edit_message_text(
        text=messages.get('object_type_prompt', "Molimo unesite tip objekta (npr. kuća, stan, poslovni prostor):"),
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        reply_markup=None
    )
    await state.set_state(ObjectInfo.awaiting_object_type)
    await callback_query.answer()

@dp.message(ObjectInfo.awaiting_object_type)
async def process_object_type(message: types.Message, state: FSMContext):
    await state.update_data(object_type=message.text)
    messages = await get_messages_for_user(message, state)
    await message.reply(messages.get('area_prompt', "Unesite površinu objekta (u m²):"))
    await state.set_state(ObjectInfo.awaiting_area)

@dp.message(ObjectInfo.awaiting_area)
async def process_area(message: types.Message, state: FSMContext):
    try:
        area_value = float(message.text.replace(',', '.'))
        if area_value <= 0:
            raise ValueError
        await state.update_data(area=str(area_value))
    except ValueError:
        messages = await get_messages_for_user(message, state)
        await message.reply(messages.get('invalid_area_input', "Nevažeći unos. Molimo unesite samo broj (npr. '120')."))
        return

    messages = await get_messages_for_user(message, state)
    await message.reply(messages.get('floors_prompt', "Unesite broj etaža:"))
    await state.set_state(ObjectInfo.awaiting_floors)

@dp.message(ObjectInfo.awaiting_floors)
async def process_floors(message: types.Message, state: FSMContext):
    try:
        floors_value = int(message.text)
        if floors_value <= 0:
            raise ValueError
        await state.update_data(floors=str(floors_value))
    except ValueError:
        messages = await get_messages_for_user(message, state)
        await message.reply(messages.get('invalid_floors_input', "Nevažeći unos. Molimo unesite samo ceo broj (npr. '2')."))
        return

    messages = await get_messages_for_user(message, state)
    await message.reply(messages.get('sketch_prompt', "Ako želite, pošaljite skicu objekta kao sliku. Ako ne, napišite 'preskoči'."))
    await state.set_state(ObjectInfo.awaiting_sketch)

@dp.message(ObjectInfo.awaiting_sketch)
async def process_sketch(message: types.Message, state: FSMContext):
    sketch = None
    messages = await get_messages_for_user(message, state)
    
    skip_word = messages.get('skip_text', 'preskoči').lower()

    if message.text and message.text.lower() == skip_word:
        sketch = None
    elif message.photo:
        photo = message.photo[-1].file_id
        sketch = photo
    elif not message.text and not message.photo:
        await message.reply(messages.get('invalid_sketch_input', 'Nevažeći unos. Molimo pošaljite sliku ili napišite "preskoči".'))
        return

    await state.update_data(sketch=sketch)

    data = await state.get_data()
    sketch_status = messages.get('sketch_provided_label', 'Dostavljena') if sketch else messages.get('sketch_not_provided_label', 'Nije dostavljena')
    
    summary_text_key = 'summary_text'
    summary = messages.get(summary_text_key, 'Sumarni pregled:\nTip objekta: {object_type}\nPovršina: {area} m²\nBroj etaža: {floors}\nSkica: {sketch_status}').format(
        object_type=data.get('object_type'),
        area=data.get('area'),
        floors=data.get('floors'),
        sketch_status=sketch_status
    )

    keyboard_buttons = [
        [InlineKeyboardButton(text=messages.get('send_inquiry_button', 'Pošalji upit'), callback_data="confirm_send")]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await message.reply(summary, reply_markup=keyboard)
    await state.set_state(ObjectInfo.confirming)

@dp.callback_query(lambda c: c.data == "confirm_send", ObjectInfo.confirming)
async def send_upit(callback_query: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    installation_choice = data.get("installation_choice")
    object_type = data.get("object_type")
    area = data.get("area")
    floors = data.get("floors")
    sketch = data.get("sketch")
    selected_language = data.get('language', 'sr')
    messages = ALL_MESSAGES.get(selected_language, ALL_MESSAGES.get('sr', {}))

    contractor_info = None
    manufacturer_info = None
    country_name = ""
    
    if installation_choice.startswith("srbija_"):
        country_name = messages.get('srbija_button', 'Srbija')
        contractor_info = contact_info['srbija'].get('contractor')
        manufacturer_info = contact_info['srbija'].get('manufacturer')
    elif installation_choice.startswith("crnagora_"):
        country_name = messages.get('crna_gora_button', 'Crna Gora')
        contractor_info = contact_info['crna_gora'].get('contractor')
    
    upit_details = messages.get('inquiry_details_prefix', "Nova porudžbina:") + "\n\n"
    upit_details += f"{messages.get('country_label', 'Država:')} {country_name}\n"

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

    if installation_choice == "srbija_inst_komplet" and manufacturer_info:
        upit_details += (
            f"\n{messages.get('complete_offer_hp_button', 'Komplet ponuda sa toplotnom pumpom')} ({manufacturer_info.get('name', 'N/A')})\n"
            f"{messages.get('contact_manufacturer_label', 'Kontakt proizvođača:')} {manufacturer_info.get('phone', 'N/A')}, {manufacturer_info.get('email', 'N/A')}\n"
        )
    elif installation_choice == "crnagora_inst_komplet" and contractor_info:
        upit_details += (
            f"\n{messages.get('complete_offer_hp_button', 'Komplet ponuda sa toplotnom pumpom')} ({contractor_info.get('name', 'N/A')} - Vazduh-voda)\n"
            f"{messages.get('contact_label', 'Kontakt:')} {contractor_info.get('phone', 'N/A')}, {contractor_info.get('email', 'N/A')}\n"
        )
            
    upit_details += (
        f"\n{messages.get('object_data_label', 'Podaci o objektu:')}\n"
        f"{messages.get('object_type_label', 'Tip:')} {object_type}\n"
        f"{messages.get('area_label', 'Površina:')} {area} m²\n"
        f"{messages.get('floors_label', 'Broj etaža:')} {floors}\n"
        f"{messages.get('sketch_label', 'Skica:')} {messages.get('sketch_provided_label', 'Dostavljena') if sketch else messages.get('sketch_not_provided_label', 'Nije dostavljena')}\n"
    )

    user_info = callback_query.from_user
    upit_details += (
        f"\n--- {messages.get('user_info_label', 'Informacije o korisniku')} ---\n"
        f"{messages.get('user_id_label', 'ID Korisnika:')} {user_info.id}\n"
        f"{messages.get('first_name_label', 'Ime:')} {user_info.first_name or 'N/A'}\n"
        f"{messages.get('last_name_label', 'Prezime:')} {user_info.last_name or 'N/A'}\n"
        f"{messages.get('username_label', 'Korisničko ime:')} @{user_info.username or 'N/A'}\n"
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, upit_details)
            if sketch:
                await bot.send_photo(admin_id, photo=sketch)
        except Exception as e:
            logger.error(f"Greška pri slanju poruke adminu {admin_id}: {e}")
    
    await bot.send_message(callback_query.from_user.id, messages.get('inquiry_sent_success', "Vaš upit je poslat. Hvala!"))
    await state.clear()
    await callback_query.answer()

async def main():
    logger.info("Starting bot...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())