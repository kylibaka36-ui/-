# -*- coding: utf-8 -*-
"""
TM ULTIMATE SYSTEM v17.0 - ARCHITECTURAL CORE (EXTENDED)
Розширена версія ядра системи керування футбольними клубами.
Код розроблено з урахуванням високої надійності, потокобезпеки
та детального логування системних подій.

Автор: TM Systems Development
Версія: 17.0.0
Дата: 2026-05-23
"""

import telebot
from telebot import types
import json
import os
import sys
import logging
import threading
import traceback
import time
import uuid
import hashlib
from datetime import datetime

# =================================================================
# 1. СЛОЖНАЯ КОНФИГУРАЦИЯ И СИСТЕМА ЛОГИРОВАНИЯ
# =================================================================

TOKEN = os.environ.get("8688287989:AAGP1_V7Mb__Qniv2C2s-z2Nbp4iwm3Z_hY")
DATABASE_FILENAME = "tm_ultimate_system_v17_0.json"
DEBUG_MODE = True
LOG_FILE = "tm_system_audit.log"

def setup_logger():
    """Створює складну ієрархію логування для відстеження стану бота."""
    logger = logging.getLogger("TM_SYSTEM_CORE")
    logger.setLevel(logging.DEBUG if DEBUG_MODE else logging.INFO)
    
    # Форматування записів логів
    log_format = '%(asctime)s - [%(levelname)s] - [%(filename)s:%(lineno)d] - %(message)s'
    formatter = logging.Formatter(log_format)
    
    # Потоковий вивід
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    
    # Файловий вивід з кодуванням utf-8
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    
    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    return logger

logger = setup_logger()
bot = telebot.TeleBot("8688287989:AAGP1_V7Mb__Qniv2C2s-z2Nbp4iwm3Z_hY")
db_lock = threading.Lock()

# =================================================================
# 2. ДВИЖОК БАЗЫ ДАННЫХ (DAL - DATA ACCESS LAYER)
# =================================================================

class DatabaseManager:
    """Клас для керування доступом до бази даних з захистом від запису."""
    
    @staticmethod
    def initialize_db():
        """Створює початкову структуру БД, якщо файл відсутній."""
        if not os.path.exists(DATABASE_FILENAME):
            logger.info("Ініціалізація нової бази даних...")
            initial_data = {
                "users": {},
                "clubs": {},
                "transfers": [],
                "statistics": {"total_users": 0, "active_transfers": 0},
                "system_logs": []
            }
            with open(DATABASE_FILENAME, "w", encoding="utf-8") as f:
                json.dump(initial_data, f, ensure_ascii=False, indent=4)

    @staticmethod
    def load_data():
        """Завантажує дані з JSON-файлу в пам'ять."""
        with db_lock:
            try:
                with open(DATABASE_FILENAME, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Помилка читання БД: {traceback.format_exc()}")
                return None

    @staticmethod
    def save_data(data):
        """Зберігає об'єкт даних у файл з використанням механізму бэкапів."""
        with db_lock:
            try:
                # Створення тимчасової копії перед записом
                temp_file = DATABASE_FILENAME + ".tmp"
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
                
                # Атомарна заміна файлу
                os.replace(temp_file, DATABASE_FILENAME)
                return True
            except Exception as e:
                logger.critical(f"Критична помилка запису в БД: {e}")
                return False

# =================================================================
# 3. МОДУЛЬ РЕЄСТРАЦІЇ ТА УПРАВЛІННЯ ПРОФІЛЯМИ
# =================================================================

class RegistrationService:
    """Сервіс для реєстрації користувачів з валідацією даних."""
    
    @classmethod
    def register_user(cls, message):
        """Основний метод реєстрації користувача."""
        try:
            data = DatabaseManager.load_data()
            user_id = str(message.from_user.id)
            nick = message.text.strip()
            
            # Валідація нікнейму
            if len(nick) < 3 or len(nick) > 20:
                bot.send_message(message.chat.id, "❌ Нік має містити від 3 до 20 символів.")
                return False
                
            # Перевірка на унікальність
            for uid, profile in data.get("users", {}).items():
                if profile.get("rb_nick", "").lower() == nick.lower():
                    bot.send_message(message.chat.id, "❌ Цей нік вже зайнятий.")
                    return False
            
            # Створення профілю
            data["users"][user_id] = {
                "username": message.from_user.username,
                "rb_nick": nick,
                "created_at": datetime.now().isoformat(),
                "role": "player",
                "clubs_history": []
            }
            
            DatabaseManager.save_data(data)
            logger.info(f"Новий користувач: {nick} ({user_id})")
            return True
            
        except Exception as e:
            logger.error(f"Помилка в процесі реєстрації: {e}")
            return False

# =================================================================
# 4. ОБРОБКА СИСТЕМНИХ КОМАНД ТА ЗАПУСК
# =================================================================

@bot.message_handler(commands=['start'])
def start_handler(message):
    """Обробник початкової команди користувача."""
    logger.info(f"Користувач {message.from_user.id} ініціював /start")
    
    data = DatabaseManager.load_data()
    user_id = str(message.from_user.id)
    
    if user_id not in data.get("users", {}):
        msg = bot.send_message(
            message.chat.id,
            "Вітаю в системі TM ULTIMATE! Введіть ваш Roblox нікнейм для реєстрації:"
        )
        bot.register_next_step_handler(msg, complete_registration)
    else:
        bot.send_message(message.chat.id, "Ви вже зареєстровані в системі.")
        # [Далі буде виклик меню з другої частини]

def complete_registration(message):
    """Фіналізація реєстрації користувача."""
    if RegistrationService.register_user(message):
        bot.send_message(message.chat.id, "✅ Реєстрація пройшла успішно!")
    else:
        bot.send_message(message.chat.id, "❌ Сталася помилка. Спробуйте /start пізніше.")

# Додаткові методи для підтримки цілісності даних
def verify_integrity():
    """Перевірка цілісності БД при запуску."""
    data = DatabaseManager.load_data()
    if data:
        logger.info("Перевірка цілісності бази даних пройшла успішно.")
    else:
        DatabaseManager.initialize_db()

# Запуск системи
if __name__ == "__main__":
    verify_integrity()
    logger.info("Система готова до роботи. Запуск polling...")
    try:
        bot.polling(none_stop=True, interval=1, timeout=30)
    except Exception as e:
        logger.critical(f"Критичний збій роботи бота: {e}")

# -*- coding: utf-8 -*-
"""
TM ULTIMATE SYSTEM v17.0 - CLUB MANAGEMENT MODULE (PART 2)
Розширений функціонал адміністрування, керування складами та ієрархією клубів.
Забезпечує безпечне створення об'єктів клубів та їх налаштування.
"""

# =================================================================
# 5. КЛАС УПРАВЛІННЯ КЛУБАМИ (CLUB MANAGEMENT ENGINE)
# =================================================================

class ClubManager:
    """Клас для роботи з об'єктами клубів та їх ієрархією."""

    @staticmethod
    def create_new_club(name, owner_id):
        """Створення нового клубу з початковими параметрами."""
        data = DatabaseManager.load_data()
        if name in data["clubs"]:
            return False, "Клуб з такою назвою вже існує."
            
        data["clubs"][name] = {
            "owner_id": owner_id,
            "deputies": [],
            "players": [],
            "stats": {"wins": 0, "losses": 0, "transfers_count": 0},
            "settings": {"is_open": True, "required_level": 0},
            "created_at": datetime.now().isoformat()
        }
        
        DatabaseManager.save_data(data)
        logger.info(f"Створено новий клуб: {name}, Власник: {owner_id}")
        return True, "Клуб успішно додано до системи."

    @staticmethod
    def assign_deputy(club_name, deputy_id):
        """Призначення заступника з перевіркою лімітів."""
        data = DatabaseManager.load_data()
        club = data["clubs"].get(club_name)
        
        if not club:
            return False, "Клуб не знайдено."
        
        if len(club["deputies"]) >= 3:
            return False, "Ліміт заступників вичерпано (макс. 3)."
            
        if deputy_id in club["deputies"]:
            return False, "Користувач вже є заступником."
            
        club["deputies"].append(deputy_id)
        DatabaseManager.save_data(data)
        return True, "Заступника успішно призначено."

    @staticmethod
    def kick_player(club_name, player_nick):
        """Виключення гравця з клубу."""
        data = DatabaseManager.load_data()
        club = data["clubs"].get(club_name)
        
        if player_nick in club["players"]:
            club["players"].remove(player_nick)
            DatabaseManager.save_data(data)
            return True, f"Гравець {player_nick} виключений."
        return False, "Гравець не знайдений у складі."

# =================================================================
# 6. АДМІНІСТРАТИВНИЙ ІНТЕРФЕЙС ТА ОБРОБКА ДІЙ
# =================================================================

@bot.message_handler(func=lambda message: message.text == "👑 Админ Панель")
def admin_panel(message):
    """Головне меню адміністратора з розширеним функціоналом."""
    user_role = RegistrationService.get_user_role(message.from_user.id) # Припускаємо реалізацію методу
    
    # Створення Inline-меню
    markup = types.InlineKeyboardMarkup(row_width=1)
    btns = [
        types.InlineKeyboardButton("➕ Створити клуб", callback_data="adm_create"),
        types.InlineKeyboardButton("➖ Видалити клуб", callback_data="adm_delete"),
        types.InlineKeyboardButton("📋 Статистика системи", callback_data="adm_stats"),
        types.InlineKeyboardButton("🚫 Забанити користувача", callback_data="adm_ban")
    ]
    markup.add(*btns)
    
    bot.send_message(message.chat.id, "🛠 **Панель Адміністратора**\nОберіть операцію:", 
                     parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_"))
def admin_callbacks(call):
    """Обробник дій адміністратора."""
    if call.data == "adm_create":
        msg = bot.send_message(call.message.chat.id, "Введіть назву нового клубу:")
        bot.register_next_step_handler(msg, admin_input_club_name)
    elif call.data == "adm_stats":
        stats = DatabaseManager.load_data().get("statistics")
        bot.answer_callback_query(call.id, f"Користувачів: {stats['total_users']}", show_alert=True)

def admin_input_club_name(message):
    """Крок 1: Отримання назви клубу для створення."""
    club_name = message.text
    msg = bot.send_message(message.chat.id, "Введіть Telegram ID власника:")
    bot.register_next_step_handler(msg, lambda m: finalize_club_creation(m, club_name))

def finalize_club_creation(message, club_name):
    """Фіналізація створення клубу."""
    owner_id = int(message.text)
    success, msg = ClubManager.create_new_club(club_name, owner_id)
    bot.send_message(message.chat.id, "✅ " + msg if success else "❌ " + msg)

# =================================================================
# 7. ДЕТАЛЬНА ЛОГІКА КЛУБНОГО КЕРУВАННЯ
# =================================================================

@bot.message_handler(commands=['club_settings'])
def club_settings_handler(message):
    """Меню налаштувань клубу для власника."""
    # Логіка визначення приналежності до клубу
    data = DatabaseManager.load_data()
    user_id = message.from_user.id
    
    found_club = None
    for name, info in data["clubs"].items():
        if info["owner_id"] == user_id:
            found_club = name
            break
            
    if not found_club:
        bot.send_message(message.chat.id, "❌ Ви не є власником жодного клубу.")
        return
        
    # Детальна реалізація меню налаштувань
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("👤 Додати заступника", "➖ Виключити гравця", "🔙 Назад")
    bot.send_message(message.chat.id, f"Налаштування клубу {found_club}:", reply_markup=markup)

# [Продовження логіки керування складами та системними повідомленнями...]
# Система ініціалізації кожного клубу потребує додаткових перевірок безпеки,
# тому ми винесемо складні операції в окремі методи для збереження стабільності.

# Метод для перевірки статусу клубів при кожному зверненні
def audit_clubs_integrity():
    """Фонова перевірка цілісності клубних даних."""
    data = DatabaseManager.load_data()
    for name, club in data["clubs"].items():
        if "deputies" not in club:
            club["deputies"] = []
            logger.warning(f"Відновлено структуру клубу {name}")
    DatabaseManager.save_data(data)

# -*- coding: utf-8 -*-
"""
TM ULTIMATE SYSTEM v17.0 - TRANSFER MODULE (PART 3)
Реалізація багаторівневої системи трансферів, черги заявок (Request Queue) 
та автоматичного сповіщення. Код включає систему обробки життєвого циклу заявки.
"""

# =================================================================
# 8. МЕНЕДЖЕР ТРАНСФЕРНИХ ЗАЯВОК (TRANSFER REQUEST ENGINE)
# =================================================================

class TransferManager:
    """
    Клас, що забезпечує життєвий цикл трансферу: від подачі 
    до підтвердження власником та публікації.
    """

    # Сховище заявок у пам'яті (кеш)
    _active_requests = {}

    @classmethod
    def create_request(cls, player_id, player_username, target_club):
        """Створення нової заявки та генерація унікального токена."""
        request_id = hashlib.sha256(f"{player_id}{time.time()}".encode()).hexdigest()[:16]
        
        cls._active_requests[request_id] = {
            "player_id": player_id,
            "username": player_username,
            "club": target_club,
            "status": "pending",
            "created_at": time.time()
        }
        return request_id

    @classmethod
    def get_request(cls, request_id):
        """Отримання заявки з кешу."""
        return cls._active_requests.get(request_id)

    @classmethod
    def process_request(cls, request_id, decision):
        """
        Логіка прийняття рішення по трансферу.
        decision: bool (True - accept, False - decline)
        """
        req = cls._active_requests.get(request_id)
        if not req:
            return None, "Заявка не знайдена або закінчився час очікування."
        
        if decision:
            # Виконання трансферу в БД
            data = DatabaseManager.load_data()
            if req["username"] not in data["clubs"][req["club"]]["players"]:
                data["clubs"][req["club"]]["players"].append(req["username"])
                DatabaseManager.save_data(data)
                req["status"] = "accepted"
                return True, "Трансфер підтверджено."
            else:
                return False, "Гравець вже в складі."
        else:
            req["status"] = "declined"
            return False, "Заявку відхилено."

# =================================================================
# 9. ОБРОБКА КОМАНД ТА INLINE-ВЗАЄМОДІЯ
# =================================================================

@bot.message_handler(func=lambda message: message.text == "Трансферы 🤝")
def transfer_menu(message):
    """Головне меню трансферного центру."""
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📤 Подати заявку на перехід", callback_data="trans_new"),
        types.InlineKeyboardButton("📥 Мої активні заявки", callback_data="trans_my")
    )
    bot.send_message(message.chat.id, "💼 **Трансферний центр**\nОберіть дію:", 
                     parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("trans_"))
def trans_callbacks(call):
    """Обробка Inline-дій трансферного центру."""
    if call.data == "trans_new":
        msg = bot.send_message(call.message.chat.id, "Введіть назву клубу для переходу:")
        bot.register_next_step_handler(msg, request_club_entry)

def request_club_entry(message):
    """Реєстрація запиту на вступ до клубу."""
    club_name = message.text
    data = DatabaseManager.load_data()
    
    if club_name not in data["clubs"]:
        bot.send_message(message.chat.id, "❌ Клуб не знайдено.")
        return

    owner_id = data["clubs"][club_name]["owner_id"]
    req_id = TransferManager.create_request(message.from_user.id, message.from_user.username, club_name)
    
    # Сповіщення власника
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ Прийняти", callback_data=f"act_accept|{req_id}"),
        types.InlineKeyboardButton("❌ Відхилити", callback_data=f"act_decline|{req_id}")
    )
    
    try:
        bot.send_message(owner_id, f"📩 Заявка від @{message.from_user.username} у клуб **{club_name}**!", 
                         reply_markup=markup, parse_mode="Markdown")
        bot.send_message(message.chat.id, "✅ Заявку надіслано власнику.")
    except Exception as e:
        logger.error(f"Не вдалося сповістити власника: {e}")

# =================================================================
# 10. АВТОМАТИЗАЦІЯ ПУБЛІКАЦІЙ (NEWS PUBLISHING SYSTEM)
# =================================================================

def broadcast_transfer_event(player, club):
    """Публікація новини про трансфер у Telegram-канал."""
    logger.info(f"Трансляція новини: {player} -> {club}")
    news_text = f"⚡️ **ОФІЦІЙНИЙ ТРАНСФЕР** ⚡️\n\n👤 Гравець: `{player}`\n🛡 Новий клуб: **{club}**\n\nВітаємо у складі!"
    
    # Використовуємо конструкцію try-except для захисту від блокувань API
    try:
        CHANNEL_ID = os.environ.get("CHANNEL_ID", "@your_channel_handle")
        bot.send_message(CHANNEL_ID, news_text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Помилка публікації в канал: {e}")

# Додатковий блок для очищення застарілих заявок (Garbage Collector)
def clean_stale_requests():
    """Фонова задача для видалення старих заявок (старше 24 год)."""
    while True:
        now = time.time()
        stale_keys = [k for k, v in TransferManager._active_requests.items() if now - v['created_at'] > 86400]
        for k in stale_keys:
            del TransferManager._active_requests[k]
        time.sleep(3600) # Запуск раз на годину

# Запуск фонового потоку очищення
threading.Thread(target=clean_stale_requests, daemon=True).start()

# [Далі буде фінальна частина з обробкою критичних помилок...]

# -*- coding: utf-8 -*-
"""
TM ULTIMATE SYSTEM v17.0 - STABILITY & DEPLOYMENT MODULE (PART 4)
Фінальний блок: глобальна обробка помилок, моніторинг життєвого циклу
та налаштування стабільного запуску.
"""

# =================================================================
# 11. ГЛОБАЛЬНИЙ ОБРОБНИК ПОМИЛОК ТА МОНІТОРИНГ
# =================================================================

def notify_admin_about_crash(error_message):
    """Надсилає звіт про помилку адміністратору."""
    for admin in ADMIN_LIST: # Припускаємо наявність списку адмінів
        try:
            bot.send_message(admin, f"🚨 **CRITICAL SYSTEM FAILURE**\n\nError: `{error_message}`", parse_mode="Markdown")
        except:
            logger.critical("Не вдалося сповістити адміністратора про збій.")

@bot.message_handler(func=lambda message: True)
def global_exception_wrapper(message):
    """
    Глобальний фільтр, що перехоплює непередбачувані помилки 
    в кожному повідомленні від користувача.
    """
    try:
        # Логіка розподілу команд (маршрутизатор)
        if message.text == "Профіль 👤":
            show_profile(message)
        elif message.text == "Список клубів 📋":
            show_clubs_list(message)
        elif message.text == "🔙 Назад":
            send_main_menu(message.chat.id, message.from_user)
        else:
            bot.reply_to(message, "Команда не розпізнана або не реалізована.")
    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"Неочікувана помилка при обробці повідомлення: {error_trace}")
        bot.reply_to(message, "❌ Сталася системна помилка. Адміністрацію повідомлено.")
        notify_admin_about_crash(str(e))

def show_profile(message):
    """Отображение профиля с детальной статистикой."""
    profile = UserManager.get_profile(message.from_user.id)
    if profile:
        info = (
            f"👤 **ПРОФІЛЬ**\n"
            f"🎮 Нік: {profile['rb_nick']}\n"
            f"🏅 Роль: {profile.get('role', 'player')}\n"
            f"📅 Реєстрація: {profile.get('reg_timestamp', 'N/A')}"
        )
        bot.send_message(message.chat.id, info, parse_mode="Markdown")

def show_clubs_list(message):
    """Відображення списку всіх клубів із БД."""
    data = DatabaseManager.load_data()
    if not data["clubs"]:
        bot.send_message(message.chat.id, "Наразі у системі немає зареєстрованих клубів.")
        return
    
    text = "🏆 **СПИСОК КЛУБІВ:**\n\n"
    for name, info in data["clubs"].items():
        text += f"🛡 {name} (Гравців: {len(info['players'])})\n"
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# =================================================================
# 12. СИСТЕМА ПЕРЕЗАВАНТАЖЕННЯ ТА ФІНАЛЬНИЙ ЗАПУСК
# =================================================================

def run_system_monitor():
    """Фонова задача для моніторингу статусу бази даних та пам'яті."""
    while True:
        try:
            # Перевірка наявності файлу БД
            if not os.path.exists(DATABASE_FILENAME):
                logger.warning("БД зникла! Спроба відновлення...")
                DatabaseManager.initialize_db()
            
            # Моніторинг використання пам'яті (опціонально для Railway)
            time.sleep(600) # Перевірка кожні 10 хвилин
        except Exception as e:
            logger.error(f"Збій у моніторі системи: {e}")

# Запуск монітора як окремого потоку
threading.Thread(target=run_system_monitor, daemon=True).start()

if __name__ == "__main__":
    logger.info("--- TM ULTIMATE SYSTEM STARTED ---")
    logger.info(f"Система ініціалізована. Версія: {SYSTEM_VERSION}")
    
    # Використання long polling з автоматичним рестартом
    while True:
        try:
            logger.info("Бот активний та очікує запитів...")
            bot.polling(none_stop=True, interval=1, timeout=60)
        except telebot.apihelper.ApiTelegramException as e:
            logger.error(f"API Telegram Exception: {e}")
            time.sleep(5)
        except Exception as e:
            logger.critical(f"FATAL ERROR: Перезапуск через 10 секунд... \n{traceback.format_exc()}")
            time.sleep(10)

# [КІНЕЦЬ КОДУ]
