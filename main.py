# -*- coding: utf-8 -*-
"""
TM ULTIMATE SYSTEM v16.1 - CORE MODULE (PART 1)
Полная система управления футбольными лигами.
Включает:
- Защиту от одинаковых ников.
- Управление составами (до 3 замов, удаление по кнопке).
- Групповые команды (/invite, /club, /delete).
- Валюта отключена по запросу.
"""

import telebot
from telebot import types
import json
import os
import time
import logging
import datetime
import sys
import threading
import re
import traceback

# =================================================================
# 1. ГЛОБАЛЬНЫЕ НАСТРОЙКИ СИСТЕМЫ И КОНСТАНТЫ
# =================================================================

# Токен твоего бота (замени на актуальный, если нужно)
TOKEN = "8688287989:AAGP1_V7Mb__Qniv2C2s-z2Nbp4iwm3Z_hY"

# ID канала или группы для публикации новостей (должен начинаться с -100)
CHANNEL_ID = '-1003740141875'

# Ник главного администратора (без @), который имеет полный доступ
SUPER_ADMIN = "Nazikrrk"

# Файл базы данных
DATABASE_PATH = "tm_ultimate_system_v16_no_eco.json"

# Настройка логирования для отслеживания ошибок и работы бота
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(name)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("tm_system_audit.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("TM_CORE_V16")

# =================================================================
# 2. АКТУАЛЬНЫЙ РЕЕСТР КЛУБОВ (ИЗ ТВОЕГО СПИСКА)
# =================================================================

# Формат: "Название": {"tag": "юзернейм", "id": Telegram ID}
# Если у клуба 2 владельца (как у PSG или Imperiall), второй ID будет добавлен 
# автоматически в список заместителей при инициализации базы.
INITIAL_CLUBS_DATA = {
    # Официальные клубы
    "Chelsea 🏴󠁧󠁢󠁥󠁮󠁧󠁿": {"tag": "Kazrzz01", "id": 8538078406},
    "Arsenal 🏴󠁧󠁢󠁥󠁮󠁧󠁿": {"tag": "strongerddd", "id": 6641683745},
    "Manchester United 🏴󠁧󠁢󠁥󠁮󠁧󠁿": {"tag": None, "id": None},
    "Manchester City 🏴󠁧󠁢󠁥󠁮󠁧󠁿": {"tag": None, "id": None},
    "Inter Milan 🇮🇹": {"tag": "Banditdontrealme", "id": 7908040352},
    "Napoli 🇮🇹": {"tag": None, "id": None},
    "Juventus 🇮🇹": {"tag": "Topor_12", "id": 8087187813},
    "Milan 🇮🇹": {"tag": None, "id": None},
    "Real Madrid 🇪🇸": {"tag": "exoqwz", "id": 8545364549},
    "Barcelona 🇪🇸": {"tag": None, "id": None},
    "Bayern Munich 🇩🇪": {"tag": "MeowSamat2", "id": 8235156157},
    "Borussia Dortmund 🇩🇪": {"tag": None, "id": None},
    "Benfica 🇵🇹": {"tag": None, "id": None},
    "Porto 🇵🇹": {"tag": None, "id": None},
    "Sporting 🇵🇹": {"tag": None, "id": None},
    "Monaco 🇫🇷": {"tag": None, "id": None},
    "PSG 🇫🇷": {"tag": "verybigsun", "id": 7908057052, "deputy_id": 8975183392},
    
    # Кастомные клубы
    "Imperiall 🇧🇾": {"tag": "kiril777_14", "id": 7677647131, "deputy_id": 8113380110},
    "Sochi 🇷🇺": {"tag": "AMOLIKERGOB", "id": 8452876078},
    "Kalev 🇪🇪": {"tag": "Miha10021", "id": 8461055593},
    "Sunderland 🏴󠁧󠁢󠁥󠁮󠁧󠁿": {"tag": "bldyywar", "id": 7909291812}
}

# =================================================================
# 3. УПРАВЛЕНИЕ БАЗОЙ ДАННЫХ (JSON ENGINE)
# =================================================================

db_lock = threading.Lock()

def load_database():
    """
    Загрузка и первоначальная настройка базы данных.
    Если файла нет, он создается с нуля и заполняется клубами из списка выше.
    """
    with db_lock:
        if not os.path.exists(DATABASE_PATH):
            logger.warning(f"Файл {DATABASE_PATH} не найден. Создание новой базы...")
            
            initial_structure = {
                "users": {},         # Профили: {ID: {username, rb_nick}}
                "admins": [SUPER_ADMIN.lower(), "banditdontrealme", "sipskdo"],
                "clubs": {},         # Данные всех клубов
                "banned_ids": [],    # Черный список
                "config": {
                    "top_text": "🏆 **ТОП КЛУБОВ TM**\n\nВ разработке...",
                    "list_text": "Списки генерируются..."
                }
            }
            
            # Наполнение базы клубами
            for club_name, info in INITIAL_CLUBS_DATA.items():
                owner_id = info["id"]
                owner_tag = info["tag"].lower() if info["tag"] else None
                deputies = []
                
                # Если указан второй ID (как у PSG), добавляем его в замы сразу
                if "deputy_id" in info and info["deputy_id"]:
                    deputies.append(info["deputy_id"])
                    
                initial_structure["clubs"][club_name] = {
                    "owner_tag": owner_tag,
                    "owner_id": owner_id,
                    "deputies": deputies,  # Максимум 3 зама (ID)
                    "players": [],         # Список ников (Roblox)
                    "transfers_count": 0,
                    "reprimands": []
                }
            
            # Сохранение созданной базы
            with open(DATABASE_PATH, "w", encoding="utf-8") as f:
                json.dump(initial_structure, f, ensure_ascii=False, indent=4)
            return initial_structure
            
        try:
            with open(DATABASE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as ex:
            logger.error(f"Ошибка при чтении БД: {ex}")
            return None

def save_database(data):
    """Безопасное сохранение данных."""
    with db_lock:
        if data is None: return False
        try:
            with open(DATABASE_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения: {e}")
            return False

# =================================================================
# 4. ПОИСКОВЫЕ УТИЛИТЫ И ПРОВЕРКИ
# =================================================================

def get_user_by_roblox(nick):
    """Поиск по Roblox нику (для избежания дубликатов)."""
    data = load_database()
    search_nick = nick.strip().lower()
    for uid, profile in data.get("users", {}).items():
        if str(profile.get("rb_nick", "")).lower() == search_nick:
            return uid, profile
    return None, None

def check_permission_level(user_id, username):
    """Определение роли пользователя (Владелец, Зам, Админ, Игрок)."""
    data = load_database()
    uid_str = str(user_id)
    uname_low = (username or "").lower()
    
    if uname_low == SUPER_ADMIN.lower() or uname_low in data.get("admins", []):
        return "admin"
    
    for club_name, info in data.get("clubs", {}).items():
        if str(info.get("owner_id")) == uid_str:
            return "club_owner", club_name
        if user_id in info.get("deputies", []):
            return "deputy", club_name
            
    return "user", None

# =================================================================
# 5. ГЕНЕРАЦИЯ КЛАВИАТУР (ИНТЕРФЕЙС)
# =================================================================

def generate_main_menu(user_id, username):
    """Динамическое главное меню."""
    data = load_database()
    if str(user_id) in data.get("banned_ids", []):
        return types.ReplyKeyboardRemove()

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    role_info = check_permission_level(user_id, username)
    perm_level = role_info[0] if isinstance(role_info, tuple) else role_info

    if perm_level == "admin":
        markup.add(types.KeyboardButton("👑 Админ Панель"))

    markup.add("Свободный агент 🆓", "Профиль 👤")
    
    if perm_level in ["admin", "club_owner", "deputy"]:
        markup.add("Предложить трансфер 🤝", "Опубликовать набор 📢")
    
    if perm_level == "club_owner":
        markup.add("Добавить зама 👤+", "Удалить зама 👤-")

    markup.add("Список клубов 📋", "Топ клубов 🏆")
    markup.add("Изменить ник ✏️", "Написать админам 📩")
    
    return markup

def generate_admin_menu():
    """Меню администратора."""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("Добавить клуб ➕", "Удалить клуб ➖")
    markup.add("🔑 Назначить влд", "🚫 Бан / Разбан")
    markup.add("🗑 Удалить игрока", "📝 Изменить списки")
    markup.add("🔙 Назад в меню")
    return markup

def back_button():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Отмена 🔙")
    return markup

# =================================================================
# 6. РЕГИСТРАЦИЯ И СИСТЕМА НИКОВ
# =================================================================

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def handle_start(message):
    """Точка входа. Создание профиля и проверка ника."""
    data = load_database()
    user_id = message.from_user.id
    uid_s = str(user_id)
    username = (message.from_user.username or "Unknown").lower()
    
    if uid_s in data.get("banned_ids", []):
        bot.send_message(message.chat.id, "🛑 Вы заблокированы.")
        return

    # Запись в БД, если новый пользователь
    if uid_s not in data["users"]:
        data["users"][uid_s] = {
            "username": username,
            "rb_nick": None
        }
        save_database(data)
    else:
        data["users"][uid_s]["username"] = username
        save_database(data)

    user_profile = data["users"][uid_s]
    
    if not user_profile.get("rb_nick"):
        text = (
            "⚽ **Добро пожаловать в TM Unofficial!**\n\n"
            "Пожалуйста, введите ваш точный **Roblox Ник**.\n"
            "⚠️ Внимание: одинаковые ники запрещены! "
            "Если вы введете чужой ник, администрация может удалить вас из базы."
        )
        msg = bot.send_message(message.chat.id, text, parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_nick_registration)
    else:
        bot.send_message(
            message.chat.id, 
            f"✅ Добро пожаловать, `{user_profile['rb_nick']}`!", 
            reply_markup=generate_main_menu(user_id, username),
            parse_mode="Markdown"
        )

def process_nick_registration(message):
    """Проверка уникальности ника и его сохранение."""
    user_id = message.from_user.id
    input_nick = message.text.strip() if message.text else ""
    
    if input_nick.startswith('/'):
        bot.send_message(message.chat.id, "❌ Ошибка. Нажмите /start заново.")
        return

    # Строгая проверка на дубликаты
    conflict_id, _ = get_user_by_roblox(input_nick)
    if conflict_id:
        msg = bot.send_message(message.chat.id, f"❌ Игрок с ником **{input_nick}** уже зарегистрирован!\nВведите свой настоящий ник:")
        bot.register_next_step_handler(msg, process_nick_registration)
        return

    data = load_database()
    data["users"][str(user_id)]["rb_nick"] = input_nick
    
    # Если человек уже был прописан владельцем по ID при инициализации
    owned_club = None
    for c_name, c_info in data["clubs"].items():
        if c_info.get("owner_id") == user_id:
            owned_club = c_name
            break

    save_database(data)
    
    success_msg = f"🎊 Регистрация успешна! Ваш ник: `{input_nick}`"
    if owned_club:
        success_msg += f"\n👑 Система определила вас как владельца клуба **{owned_club}**!"
        
    bot.send_message(
        message.chat.id, 
        success_msg, 
        parse_mode="Markdown",
        reply_markup=generate_main_menu(user_id, (message.from_user.username or ""))
    )

# --- КОНЕЦ ПЕРВОЙ ЧАСТИ ---

# =================================================================
# 7. ГРУППОВЫЕ КОМАНДЫ И УПРАВЛЕНИЕ СОСТАВОМ В ЧАТАХ
# =================================================================

@bot.message_handler(commands=['invite'])
def handle_invite_command(message):
    """
    Команда /invite @username
    Позволяет владельцу или заму пригласить игрока в клуб прямо в группе.
    """
    try:
        args = message.text.split()
        if len(args) < 2:
            bot.reply_to(message, "⚠️ Использование: `/invite @username`", parse_mode="Markdown")
            return

        target_username = args[1].replace("@", "").lower().strip()
        inviter_id = message.from_user.id
        
        # Проверяем права приглашающего
        role, club_name = check_permission_level(inviter_id, message.from_user.username)
        if role not in ["club_owner", "deputy"]:
            bot.reply_to(message, "❌ Только владельцы и заместители могут приглашать игроков.")
            return

        data = load_database()
        
        # Ищем целевого игрока в базе
        target_uid = None
        target_profile = None
        for uid, profile in data.get("users", {}).items():
            if profile.get("username", "").lower() == target_username:
                target_uid = uid
                target_profile = profile
                break

        if not target_uid or not target_profile.get("rb_nick"):
            bot.reply_to(message, f"❌ Пользователь @{target_username} не зарегистрирован в системе или не указал Roblox ник.")
            return

        rb_nick = target_profile["rb_nick"]
        
        # Проверяем, не в клубе ли он уже
        if rb_nick in data["clubs"][club_name]["players"]:
            bot.reply_to(message, f"⚠️ Игрок {rb_nick} уже состоит в вашем клубе.")
            return

        # Отправляем приглашение с inline-кнопками
        markup = types.InlineKeyboardMarkup()
        btn_accept = types.InlineKeyboardButton("✅ Принять", callback_query_data=f"inv_acc|{club_name}|{target_uid}")
        btn_decline = types.InlineKeyboardButton("❌ Отклонить", callback_query_data=f"inv_dec|{club_name}|{target_uid}")
        markup.add(btn_accept, btn_decline)

        bot.send_message(
            int(target_uid), 
            f"📩 **Официальное приглашение!**\n\nВас приглашают вступить в клуб **{club_name}**.\nВы согласны?",
            reply_markup=markup,
            parse_mode="Markdown"
        )
        bot.reply_to(message, f"📨 Приглашение успешно отправлено игроку `{rb_nick}` (@{target_username}).", parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Ошибка в команде /invite: {e}")
        bot.reply_to(message, "❌ Произошла системная ошибка при отправке приглашения.")

@bot.message_handler(commands=['delete'])
def handle_delete_command(message):
    """
    Команда /delete Nickname
    Исключает игрока из состава клуба (доступно владельцу и замам).
    """
    try:
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            bot.reply_to(message, "⚠️ Использование: `/delete RobloxNick`", parse_mode="Markdown")
            return

        target_nick = args[1].strip()
        inviter_id = message.from_user.id
        
        role, club_name = check_permission_level(inviter_id, message.from_user.username)
        if role not in ["club_owner", "deputy"]:
            bot.reply_to(message, "❌ У вас нет прав исключать игроков.")
            return

        data = load_database()
        
        # Поиск с учетом регистра
        players_list = data["clubs"][club_name]["players"]
        player_found = False
        
        for p in players_list:
            if p.lower() == target_nick.lower():
                data["clubs"][club_name]["players"].remove(p)
                player_found = True
                break
                
        if player_found:
            save_database(data)
            bot.reply_to(message, f"✅ Игрок `{target_nick}` успешно исключен из состава **{club_name}**.", parse_mode="Markdown")
            # Попытка уведомить самого игрока
            target_uid, _ = get_user_by_roblox(target_nick)
            if target_uid:
                try:
                    bot.send_message(int(target_uid), f"⚠️ Вы были исключены из состава клуба **{club_name}** руководством.")
                except:
                    pass
        else:
            bot.reply_to(message, f"❌ Игрок `{target_nick}` не найден в составе вашего клуба.", parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Ошибка в команде /delete: {e}")

@bot.message_handler(commands=['club'])
def handle_club_info_command(message):
    """
    Команда /club Название
    Выводит детальную статистику и состав указанного клуба.
    """
    try:
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            bot.reply_to(message, "⚠️ Использование: `/club Название Клуба`", parse_mode="Markdown")
            return

        target_club = args[1].strip().lower()
        data = load_database()
        
        found_club_name = None
        for c_name in data["clubs"].keys():
            if target_club in c_name.lower():
                found_club_name = c_name
                break
                
        if not found_club_name:
            bot.reply_to(message, "❌ Клуб не найден. Проверьте правильность написания.")
            return

        c_info = data["clubs"][found_club_name]
        owner_str = f"@{c_info['owner_tag']}" if c_info.get("owner_tag") else "Отсутствует"
        
        players_str = "\n".join([f"👤 {p}" for p in c_info["players"]]) if c_info["players"] else "Состав пуст"
        
        text = (
            f"🛡 **ИНФОРМАЦИЯ О КЛУБЕ: {found_club_name}**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"👑 Владелец: {owner_str}\n"
            f"👥 Количество замов: {len(c_info['deputies'])}\n"
            f"📈 Проведено трансферов: {c_info['transfers_count']}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📋 **Текущий состав:**\n{players_str}"
        )
        bot.reply_to(message, text, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Ошибка команды /club: {e}")

# =================================================================
# 8. ОБРАБОТЧИКИ INLINE-КНОПОК (ТРАНСФЕРЫ И ПРИГЛАШЕНИЯ)
# =================================================================

@bot.callback_query_handler(func=lambda call: call.data.startswith('inv_'))
def handle_invitation_callback(call):
    """Обработка нажатия на кнопку принятия/отклонения инвайта."""
    try:
        action, club_name, target_uid = call.data.split('|')
        
        if str(call.from_user.id) != target_uid:
            bot.answer_callback_query(call.id, "❌ Это приглашение не для вас!", show_alert=True)
            return

        data = load_database()
        profile = data["users"].get(target_uid)
        rb_nick = profile.get("rb_nick")

        if action == "inv_acc":
            # Удаляем из старого клуба, если он там был
            for c_name, c_info in data["clubs"].items():
                if rb_nick in c_info["players"]:
                    c_info["players"].remove(rb_nick)
            
            # Добавляем в новый
            data["clubs"][club_name]["players"].append(rb_nick)
            data["clubs"][club_name]["transfers_count"] = data["clubs"][club_name].get("transfers_count", 0) + 1
            
            save_database(data)
            
            bot.edit_message_text(f"✅ Вы успешно вступили в клуб **{club_name}**!", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
            
            # Публикация в официальный канал
            news_text = f"⚡️ **ОФИЦИАЛЬНЫЙ ПЕРЕХОД** ⚡️\n\n👤 Игрок `{rb_nick}` подписал контракт с клубом **{club_name}**!"
            bot.send_message(CHANNEL_ID, news_text, parse_mode="Markdown")
            
        elif action == "inv_dec":
            bot.edit_message_text(f"❌ Вы отклонили приглашение от клуба **{club_name}**.", call.message.chat.id, call.message.message_id, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Ошибка Callback inv_: {e}")

# =================================================================
# 9. УПРАВЛЕНИЕ ЗАМЕСТИТЕЛЯМИ (ДОБАВЛЕНИЕ И УДАЛЕНИЕ)
# =================================================================

@bot.message_handler(func=lambda message: message.text == "Добавить зама 👤+")
def add_deputy_process(message):
    role, club_name = check_permission_level(message.from_user.id, message.from_user.username)
    if role != "club_owner":
        bot.send_message(message.chat.id, "❌ Только Владелец может назначать заместителей.")
        return

    data = load_database()
    current_deputies = data["clubs"][club_name].get("deputies", [])
    
    if len(current_deputies) >= 3:
        bot.send_message(message.chat.id, "⚠️ У вас уже максимальное количество заместителей (3). Сначала удалите кого-то.")
        return

    msg = bot.send_message(
        message.chat.id, 
        "👤 Введите **Telegram ID** пользователя, которого хотите назначить заместителем.\n"
        "(Пользователь должен быть зарегистрирован в боте):", 
        reply_markup=back_button()
    )
    bot.register_next_step_handler(msg, process_save_deputy, club_name)

def process_save_deputy(message, club_name):
    if message.text == "Отмена 🔙":
        bot.send_message(message.chat.id, "Отменено.", reply_markup=generate_main_menu(message.from_user.id, message.from_user.username))
        return

    target_id = message.text.strip()
    if not target_id.isdigit():
        bot.send_message(message.chat.id, "❌ ID должен состоять только из цифр.", reply_markup=generate_main_menu(message.from_user.id, message.from_user.username))
        return

    data = load_database()
    
    if target_id not in data["users"]:
        bot.send_message(message.chat.id, "❌ Пользователь с таким ID не найден в базе. Пусть он напишет /start боту.", reply_markup=generate_main_menu(message.from_user.id, message.from_user.username))
        return

    if int(target_id) in data["clubs"][club_name]["deputies"]:
        bot.send_message(message.chat.id, "⚠️ Этот человек уже является вашим заместителем.", reply_markup=generate_main_menu(message.from_user.id, message.from_user.username))
        return

    data["clubs"][club_name]["deputies"].append(int(target_id))
    save_database(data)
    
    bot.send_message(message.chat.id, f"✅ Пользователь успешно назначен заместителем клуба **{club_name}**!", reply_markup=generate_main_menu(message.from_user.id, message.from_user.username))
    try:
        bot.send_message(int(target_id), f"🎉 Владелец назначил вас Заместителем в клубе **{club_name}**!\nОбновите меню командой /start.", parse_mode="Markdown")
    except:
        pass

@bot.message_handler(func=lambda message: message.text == "Удалить зама 👤-")
def remove_deputy_process(message):
    role, club_name = check_permission_level(message.from_user.id, message.from_user.username)
    if role != "club_owner":
        bot.send_message(message.chat.id, "❌ Это действие доступно только Владельцу.")
        return

    data = load_database()
    deputies = data["clubs"][club_name].get("deputies", [])
    
    if not deputies:
        bot.send_message(message.chat.id, "У вас нет назначенных заместителей.")
        return

    markup = types.InlineKeyboardMarkup()
    for idx, dep_id in enumerate(deputies, start=1):
        # Достаем ник заместителя для красоты
        dep_profile = data["users"].get(str(dep_id), {})
        dep_nick = dep_profile.get("rb_nick", f"ID:{dep_id}")
        
        btn = types.InlineKeyboardButton(f"Зам {idx}: {dep_nick}", callback_query_data=f"del_dep|{club_name}|{dep_id}")
        markup.add(btn)

    bot.send_message(message.chat.id, "Выберите заместителя для снятия с должности:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('del_dep|'))
def handle_delete_deputy_callback(call):
    """Снятие заместителя по кнопке."""
    try:
        _, club_name, dep_id = call.data.split('|')
        
        # Защита: только владелец может нажать
        role, c_name = check_permission_level(call.from_user.id, call.from_user.username)
        if role != "club_owner" or c_name != club_name:
            bot.answer_callback_query(call.id, "❌ Вы не владелец этого клуба!", show_alert=True)
            return

        data = load_database()
        if int(dep_id) in data["clubs"][club_name]["deputies"]:
            data["clubs"][club_name]["deputies"].remove(int(dep_id))
            save_database(data)
            bot.edit_message_text(f"✅ Заместитель успешно снят с должности.", call.message.chat.id, call.message.message_id)
            try:
                bot.send_message(int(dep_id), f"⚠️ Вы больше не являетесь заместителем клуба **{club_name}**.")
            except:
                pass
        else:
            bot.edit_message_text("❌ Заместитель уже был удален.", call.message.chat.id, call.message.message_id)
            
    except Exception as e:
        logger.error(f"Ошибка удаления зама: {e}")

# =================================================================
# 10. РАСШИРЕННАЯ АДМИН-ПАНЕЛЬ (УПРАВЛЕНИЕ СИСТЕМОЙ)
# =================================================================

@bot.message_handler(func=lambda message: message.text == "Добавить клуб ➕")
def admin_add_club_advanced(message):
    role, _ = check_permission_level(message.from_user.id, message.from_user.username)
    if role != "admin": return

    msg = bot.send_message(
        message.chat.id, 
        "🛠 Введите данные нового клуба в формате:\n`Название | Telegram_ID_Владельца`\n\n"
        "Если владельца пока нет, напишите просто `Название | None`", 
        parse_mode="Markdown",
        reply_markup=back_button()
    )
    bot.register_next_step_handler(msg, process_advanced_club_creation)

def process_advanced_club_creation(message):
    if message.text == "Отмена 🔙":
        bot.send_message(message.chat.id, "Возврат в админку.", reply_markup=generate_admin_menu())
        return

    try:
        parts = message.text.split('|')
        if len(parts) != 2:
            bot.send_message(message.chat.id, "❌ Неверный формат. Нужно: `Название | ID`", parse_mode="Markdown", reply_markup=generate_admin_menu())
            return
            
        club_name = parts[0].strip()
        owner_str = parts[1].strip()
        
        owner_id = int(owner_str) if owner_str.lower() != "none" and owner_str.isdigit() else None

        data = load_database()
        if club_name in data["clubs"]:
            bot.send_message(message.chat.id, "❌ Клуб с таким названием уже существует.", reply_markup=generate_admin_menu())
            return

        data["clubs"][club_name] = {
            "owner_tag": None,
            "owner_id": owner_id,
            "deputies": [],
            "players": [],
            "transfers_count": 0,
            "reprimands": []
        }
        
        save_database(data)
        bot.send_message(message.chat.id, f"✅ Клуб **{club_name}** успешно создан!", parse_mode="Markdown", reply_markup=generate_admin_menu())
        
        # Автоматическое уведомление владельцу о выдаче клуба
        if owner_id:
            try:
                bot.send_message(
                    owner_id, 
                    f"👑 **Поздравляем!**\nАдминистрация системы назначила вас Владельцем клуба **{club_name}**!\n"
                    f"Нажмите /start чтобы обновить меню управления.",
                    parse_mode="Markdown"
                )
            except Exception as e:
                bot.send_message(message.chat.id, f"⚠️ Клуб создан, но отправить уведомление владельцу (ID: {owner_id}) не удалось. Возможно он заблокировал бота.")
                
    except Exception as e:
        logger.error(f"Ошибка создания клуба: {e}")
        bot.send_message(message.chat.id, "❌ Системная ошибка обработки данных.")

@bot.message_handler(func=lambda message: message.text == "🗑 Удалить игрока")
def admin_delete_player_profile(message):
    role, _ = check_permission_level(message.from_user.id, message.from_user.username)
    if role != "admin": return

    msg = bot.send_message(
        message.chat.id, 
        "⚠️ **Удаление профиля (WIPE)**\nВведите точный Roblox Ник игрока для полного удаления из системы и составов:", 
        parse_mode="Markdown",
        reply_markup=back_button()
    )
    bot.register_next_step_handler(msg, process_full_player_wipe)

def process_full_player_wipe(message):
    if message.text == "Отмена 🔙":
        bot.send_message(message.chat.id, "Отменено.", reply_markup=generate_admin_menu())
        return

    target_nick = message.text.strip().lower()
    data = load_database()
    
    # Ищем ID пользователя по нику
    target_uid = None
    for uid, profile in data["users"].items():
        if profile.get("rb_nick", "").lower() == target_nick:
            target_uid = uid
            break

    if not target_uid:
        bot.send_message(message.chat.id, f"❌ Игрок `{message.text}` не найден в базе.", parse_mode="Markdown", reply_markup=generate_admin_menu())
        return

    # Удаляем со всех клубов
    for c_name, c_info in data["clubs"].items():
        # Из списка игроков
        players_lower = [p.lower() for p in c_info["players"]]
        if target_nick in players_lower:
            actual_nick = c_info["players"][players_lower.index(target_nick)]
            c_info["players"].remove(actual_nick)
        
        # Снимаем с замов
        if int(target_uid) in c_info.get("deputies", []):
            c_info["deputies"].remove(int(target_uid))
            
        # Снимаем с владельцев
        if str(c_info.get("owner_id")) == target_uid:
            c_info["owner_id"] = None
            c_info["owner_tag"] = None

    # Полностью стираем профиль
    del data["users"][target_uid]
    
    save_database(data)
    bot.send_message(message.chat.id, f"✅ Профиль игрока `{message.text}` был полностью стерт из базы данных системы.", parse_mode="Markdown", reply_markup=generate_admin_menu())

# =================================================================
# 11. ПРОСМОТР ПРОФИЛЯ
# =================================================================

@bot.message_handler(func=lambda message: message.text == "Профиль 👤")
def show_personal_profile(message):
    """Отображение профиля и текущего статуса игрока."""
    data = load_database()
    uid_str = str(message.from_user.id)
    profile = data["users"].get(uid_str, {})
    
    if not profile:
        bot.send_message(message.chat.id, "❌ Профиль не найден. Нажмите /start")
        return

    # Определяем местоположение игрока
    club_found = "Свободный агент"
    for c_name, c_info in data["clubs"].items():
        if profile.get("rb_nick") in c_info["players"]:
            club_found = c_name
            break
        if str(c_info.get("owner_id")) == uid_str:
            club_found = f"{c_name} (Владелец)"
            break
        if message.from_user.id in c_info.get("deputies", []):
            club_found = f"{c_name} (Заместитель)"
            break

    text = (
        f"👤 **ПРОФИЛЬ ИГРОКА**\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🎮 Игровой ник: `{profile.get('rb_nick', 'Не указан')}`\n"
        f"⚽ Статус: **{club_found}**\n"
        f"🆔 Системный ID: `{uid_str}`\n"
        f"━━━━━━━━━━━━━━━━━━━"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# =================================================================
# 12. ГЛАВНЫЙ ЦИКЛ БОТА (POLLING)
# =================================================================

if __name__ == "__main__":
    logger.info("TM ULTIMATE v16.1 успешно инициализирован. Запуск polling...")
    
    # Безопасный бесконечный цикл работы
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            logger.error(f"Сбой сети или API: {e}")
            logger.info("Перезапуск соединения через 5 секунд...")
            time.sleep(5)
