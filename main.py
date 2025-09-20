import telebot
from telebot import types
from datetime import datetime, timedelta
import time
import threading
import os

# Конфигурация бота
TOKEN = '7624136254:AAHudHeO0ZScnHqlIZmMOW4R1GoAJizqBqg'
TARGET_CHANNEL_1 = '-1002702796095'  # Первый чат (без ID пользователя)
TARGET_CHANNEL_2 = '-1003035422039'  # Второй чат (с ID пользователя) - ЗАМЕНИТЕ НА РЕАЛЬНЫЙ ID
ADMINS = [6172742677, 1616523146, 5683628958, 5093260880, 6685714039, 5762430690]  # ID администраторов

# Чёрный список: {user_id: {'unban_time': datetime или None, 'reason': str, 'banned_by': int, 'ban_date': str}}
BLACKLIST = {}

# Настройки очистки кэша
CACHE_CLEAN_INTERVAL = 10  # дней
LAST_CACHE_CLEAN = datetime.now()

bot = telebot.TeleBot(TOKEN)


def clean_cache():
    """Функция для очистки кэша"""
    global LAST_CACHE_CLEAN

    # Здесь можно добавить очистку временных файлов или других данных
    print(f"[{datetime.now()}] Выполняется очистка кэша...")

    # Пример очистки: удаляем старые баны (если есть)
    current_time = datetime.now()
    expired_bans = [
        user_id for user_id, data in BLACKLIST.items()
        if data['unban_time'] and data['unban_time'] < current_time
    ]

    for user_id in expired_bans:
        del BLACKLIST[user_id]

    LAST_CACHE_CLEAN = current_time
    print(f"[{datetime.now()}] Очистка кэша завершена. Удалено {len(expired_bans)} просроченных банов.")


def cache_clean_scheduler():
    """Планировщик для регулярной очистки кэша"""
    while True:
        time.sleep(60 * 60 * 24)  # Проверяем каждый день
        if (datetime.now() - LAST_CACHE_CLEAN).days >= CACHE_CLEAN_INTERVAL:
            clean_cache()


# Запускаем планировщик в отдельном потоке
cleaner_thread = threading.Thread(target=cache_clean_scheduler, daemon=True)
cleaner_thread.start()


def format_timedelta(delta):
    """Форматирует timedelta в читаемый вид"""
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{days}д")
    if hours > 0:
        parts.append(f"{hours}ч")
    if minutes > 0:
        parts.append(f"{minutes}м")
    if seconds > 0 or not parts:
        parts.append(f"{seconds}с")

    return ' '.join(parts)


def is_user_banned(user_id):
    """Проверяет, забанен ли пользователь и возвращает оставшееся время"""
    if user_id not in BLACKLIST:
        return False, None

    ban_data = BLACKLIST[user_id]
    unban_time = ban_data['unban_time']

    if unban_time is None:  # Перманентный бан
        return True, "навсегда"

    if datetime.now() < unban_time:  # Временный бан активен
        remaining = unban_time - datetime.now()
        return True, format_timedelta(remaining)

    # Бан истёк
    del BLACKLIST[user_id]
    return False, None


def parse_ban_time(time_str):
    """Парсит время бана и возвращает datetime или None для перманентного бана"""
    if time_str.lower() == 'p':
        return None

    unit = time_str[-1].lower()
    if unit.isalpha():
        num = int(time_str[:-1])
    else:
        num = int(time_str)
        unit = 's'  # По умолчанию секунды

    if unit == 's':
        return datetime.now() + timedelta(seconds=num)
    elif unit == 'm':
        return datetime.now() + timedelta(minutes=num)
    elif unit == 'h':
        return datetime.now() + timedelta(hours=num)
    elif unit == 'd':
        return datetime.now() + timedelta(days=num)
    else:
        return datetime.now() + timedelta(minutes=1)  # По умолчанию 1 минута


@bot.message_handler(commands=['start'])
def handle_start(message):
    bot.reply_to(message,
                 "Привет👋, это бот канала подслушано.🤫\nНапиши текст чтоб я его отправил в подслушано😶‍🌫\n\nпредупреждаю что чат модерируется админами и за злоупотребление ботом вы будете внесены в чс бота(подробнее можно узнать в закрепе в канале)⛔")


@bot.message_handler(commands=['clean_cache'], func=lambda m: m.from_user.id in ADMINS)
def handle_clean_cache(message):
    """Ручная очистка кэша по команде администратора"""
    clean_cache()
    bot.reply_to(message, "✅ Кэш успешно очищен")


@bot.message_handler(commands=['banlist'], func=lambda m: m.from_user.id in ADMINS)
def handle_banlist(message):
    """Показывает список забаненных пользователей"""
    if not BLACKLIST:
        bot.reply_to(message, "🟢 Чёрный список пуст")
        return

    response = "🔴 Забаненные пользователи:\n\n"
    for user_id, ban_data in BLACKLIST.items():
        admin_id = ban_data['banned_by']
        reason = ban_data['reason']
        ban_date = ban_data['ban_date']

        if ban_data['unban_time'] is None:
            time_left = "НАВСЕГДА"
        else:
            time_left = f"до {ban_data['unban_time'].strftime('%Y-%m-%d %H:%M')}"

        response += (
            f"👤 ID: {user_id}\n"
            f"⏳ Срок: {time_left}\n"
            f"📅 Дата бана: {ban_date}\n"
            f"🛡 Админ: {admin_id}\n"
            f"📌 Причина: {reason}\n"
            f"───────────────────\n"
        )

    if len(response) > 4000:
        parts = [response[i:i + 4000] for i in range(0, len(response), 4000)]
        for part in parts:
            bot.send_message(message.chat.id, part)
    else:
        bot.send_message(message.chat.id, response)


@bot.message_handler(commands=['unban'], func=lambda m: m.from_user.id in ADMINS)
def handle_unban(message):
    """Разбан пользователя с возможностью указания причины"""
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 2:
            bot.reply_to(message,
                         "Использование:\n/unban [user_id] - разбан без причины\n/unban [user_id] [причина] - разбан с причиной\nПример:\n/unban 123456\n/unban 123456 ошибка модерации")
            return

        user_id = int(parts[1])
        reason = parts[2] if len(parts) > 2 else "Причина не указана"

        if user_id not in BLACKLIST:
            bot.reply_to(message, f"ℹ️ Пользователь {user_id} не в чёрном списке")
            return

        # Удаляем из чёрного списка
        del BLACKLIST[user_id]

        # Отправляем подтверждение администратору
        bot.reply_to(message, f"🟢 Пользователь {user_id} разбанен\nПричина: {reason}")

        # Уведомляем пользователя о разбане
        try:
            unban_msg = (
                f"✅ ВАС РАЗБАНИЛИ!\n"
                f"Причина: {reason}\n\n"
                f"Теперь вы можете снова отправлять сообщения."
            )
            bot.send_message(user_id, unban_msg)
        except Exception as e:
            print(f"Не удалось уведомить пользователя {user_id} о разбане: {e}")

    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {str(e)}")


@bot.message_handler(commands=['ban'], func=lambda m: m.from_user.id in ADMINS)
def handle_ban(message):
    """Обработчик команды /ban для администраторов"""
    try:
        parts = message.text.split(maxsplit=2)
        if len(parts) < 2:
            bot.reply_to(message,
                         "Использование:\n/ban [user_id] [время] [причина]\nПримеры:\n/ban 123456 30m спам\n/ban 789012 p нарушение правил")
            return

        user_id = int(parts[1])

        if user_id in ADMINS:
            bot.reply_to(message, "❌ Нельзя забанить администратора!")
            return

        if len(parts) > 2:
            time_part = parts[2].split(maxsplit=1)
            ban_time = parse_ban_time(time_part[0])
            reason = time_part[1] if len(time_part) > 1 else "Не указана"
        else:
            ban_time = parse_ban_time('1h')
            reason = "Не указана"

        BLACKLIST[user_id] = {
            'unban_time': ban_time,
            'reason': reason,
            'banned_by': message.from_user.id,
            'ban_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        if ban_time is None:
            response = f"🔴 Пользователь {user_id} забанен НАВСЕГДА\nПричина: {reason}"
        else:
            response = f"🔴 Пользователь {user_id} забанен до {ban_time.strftime('%Y-%m-%d %H:%M:%S')}\nПричина: {reason}"

        bot.reply_to(message, response)

        try:
            if ban_time is None:
                ban_msg = "⛔ ВЫ ЗАБАНЕНЫ НАВСЕГДА!\nПричина: " + reason
            else:
                ban_msg = f"⛔ ВЫ ЗАБАНЕНЫ НА {format_timedelta(ban_time - datetime.now())}\nПричина: " + reason
            bot.send_message(user_id, ban_msg)
        except Exception as e:
            print(f"Не удалось уведомить пользователя {user_id}: {e}")

    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {str(e)}")


def forward_to_channels(message, caption_with_id, caption_without_id):
    """Пересылает сообщение в оба канала с разными подписями"""
    try:
        if message.content_type == 'text':
            # В первый канал (без ID)
            bot.send_message(TARGET_CHANNEL_1, caption_without_id)
            # Во второй канал (с ID)
            bot.send_message(TARGET_CHANNEL_2, caption_with_id)

        elif message.content_type == 'photo':
            bot.send_photo(TARGET_CHANNEL_1, message.photo[-1].file_id, caption=caption_without_id)
            bot.send_photo(TARGET_CHANNEL_2, message.photo[-1].file_id, caption=caption_with_id)

        elif message.content_type == 'video':
            bot.send_video(TARGET_CHANNEL_1, message.video.file_id, caption=caption_without_id)
            bot.send_video(TARGET_CHANNEL_2, message.video.file_id, caption=caption_with_id)

        elif message.content_type == 'document':
            bot.send_document(TARGET_CHANNEL_1, message.document.file_id, caption=caption_without_id)
            bot.send_document(TARGET_CHANNEL_2, message.document.file_id, caption=caption_with_id)

        elif message.content_type == 'audio':
            bot.send_audio(TARGET_CHANNEL_1, message.audio.file_id, caption=caption_without_id)
            bot.send_audio(TARGET_CHANNEL_2, message.audio.file_id, caption=caption_with_id)

        elif message.content_type == 'voice':
            bot.send_voice(TARGET_CHANNEL_1, message.voice.file_id, caption=caption_without_id)
            bot.send_voice(TARGET_CHANNEL_2, message.voice.file_id, caption=caption_with_id)

        elif message.content_type == 'video_note':
            bot.send_video_note(TARGET_CHANNEL_1, message.video_note.file_id)
            bot.send_video_note(TARGET_CHANNEL_2, message.video_note.file_id)

    except Exception as e:
        print(f"Ошибка при пересылке в каналы: {e}")


@bot.message_handler(content_types=[
    'text', 'photo', 'video', 'document',
    'audio', 'voice', 'sticker', 'video_note'
])
def handle_all_messages(message):
    user_id = message.from_user.id

    if message.text and message.text.startswith('/start'):
        return

    banned, remaining = is_user_banned(user_id)
    if banned:
        if remaining == "навсегда":
            bot.reply_to(message, "⛔ ВЫ ЗАБАНЕНЫ НАВСЕГДА!")
        else:
            bot.reply_to(message, f"⛔ ВЫ ЗАБАНЕНЫ! Осталось: {remaining}")
        return

    # Подпись для первого канала (без ID пользователя)
    caption_without_id = ""
    if message.caption:
        caption_without_id = message.caption
    elif message.text:
        caption_without_id = message.text

    # Подпись для второго канала (с ID пользователя)
    caption_with_id = f"📨 Сообщение от пользователя (ID: {user_id})"
    if message.caption:
        caption_with_id += f"\n\n{message.caption}"
    elif message.text:
        caption_with_id += f"\n\n{message.text}"

    forward_to_channels(message, caption_with_id, caption_without_id)


if __name__ == '__main__':
    print("Бот запущен и готов к работе!")
    print(f"Следующая очистка кэша через {CACHE_CLEAN_INTERVAL} дней")
    print(f"Сообщения будут отправляться в:")
    print(f"1. Канал без ID: {TARGET_CHANNEL_1}")
    print(f"2. Канал с ID: {TARGET_CHANNEL_2}")

while True:
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        print(e)
        time.sleep(15)




