# config.py
import os

# Telegram Bot Token - Učitava se iz environment varijabli na Renderu
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Vaš BCC email za praćenje upita - Učitava se iz environment varijabli
MY_BCC_EMAIL = os.getenv("MY_BCC_EMAIL")

# SMTP podaci za slanje emailova - Učitavaju se iz environment varijabli
SMTP_EMAIL_USER = os.getenv("SMTP_EMAIL_USER")
SMTP_EMAIL_PASSWORD = os.getenv("SMTP_EMAIL_PASSWORD")

# WEBHOOK_URL - Render automatski postavlja RENDER_EXTERNAL_HOSTNAME
WEBHOOK_URL = os.getenv("RENDER_EXTERNAL_HOSTNAME")
# WEBHOOK_SECRET - Preporučeno za sigurnost
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")


# Podaci o izvođačima i firmama
CONTACTS = {
    "Srbija": {
        "grejanje": {
            "ime": "Igor Bošković",
            "email": "boskovicigor83@gmail.com",
            "telefon": "+381 60 3932566",
            "telegram": "@IgorNS1983"
        },
        "toplotna_pumpa": {
            "firma": "Microma",
            "kontakt_osoba": "Borislav Dakić",
            "email": "office@microma.rs",
            "telefon": "+381 63 582068",
            "web": "https://microma.rs"
        }
    },
    "Crna Gora": {
        "general": { # Instal M je generalni partner za sve u CG
            "firma": "Instal M",
            "kontakt_osoba": "Ivan Mujović",
            "email": "office@instalm.me",
            "telefon": "+382 67 423 237",
            "telegram": "@ivanmujovic"
        }
    }
}

# Jezici (ovo ćemo kasnije proširiti sa celim prevodima)
LANGUAGES = {
    "sr": "Srpski",
    "en": "English",
    "ru": "Русский"
}

# Početni tekstovi (ovo ćemo kasnije prebaciti u prevode)
START_MESSAGES = {
    "sr": "Dobrodošli! Molimo izaberite jezik:",
    "en": "Welcome! Please choose your language:",
    "ru": "Добро пожаловать! Пожалуйста, выберите язык:"
}