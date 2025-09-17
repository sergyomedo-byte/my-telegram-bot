import os
import logging
import time
import json
import threading
import http.server
import socketserver
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)
from telegram.error import TelegramError

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Простой HTTP server для Render
class HealthHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Bot is alive!')
        else:
            self.send_response(404)
            self.end_headers()

def run_health_server():
    port = int(os.environ.get("PORT", 5000))
    with socketserver.TCPServer(("", port), HealthHandler) as httpd:
        logger.info(f"Health server running on port {port}")
        httpd.serve_forever()

# Конфигурация
TOKEN = os.getenv('TOKEN', '8091371448:AAERHwxB8CseSenyfCoHPuk-Y2BmNSo5kmU')
GROUP_ID = int(os.getenv('TELEGRAM_GROUP_ID', '-1002789329715'))

# Состояния для ConversationHandler
TEXT, PHOTO_OR_DOC = range(2)

# Главное меню
def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("1. 🛍️ Выбор товара", callback_data="product_selection")],
        [InlineKeyboardButton("2. ❓ Помощь", callback_data="help")],
        [InlineKeyboardButton("3. 📞 Контакты", callback_data="contacts")],
        [InlineKeyboardButton("4. 📢 Новости/Отгрузки", callback_data="news_feed")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Меню выбора категорий товаров
def get_categories_keyboard():
    categories = [
        ("🚗 Автомобильные товары", "auto"),
        ("🏍️ Мотоциклы и питбайки", "moto"),
        ("🧸 Игрушки", "toys"),
        ("👜 Сумки", "bags"),
        ("👕 Одежда", "clothes"),
        ("⚽ Спортивный инвентарь", "sport"),
        ("📱 Электроника", "electronics"),
        ("🏠 Бытовая техника", "appliances"),
        ("🏠 Домашний декор", "decor"),
        ("💄 Красота и здоровье", "beauty"),
        ("💍 Ювелирка и аксессуары", "jewelry"),
        ("🛠️ Инструменты и оборудование", "tools"),
        ("📊 Офисные товары", "office"),
        ("🧒 Детские товары", "kids"),
        ("⚙️ Станки и механизмы", "machinery"),
        ("📦 Другие товары", "other_items")
    ]
    
    # Создаем кнопки по 2 в ряд
    buttons = []
    for i in range(0, len(categories), 2):
        row = []
        if i < len(categories):
            row.append(InlineKeyboardButton(categories[i][0], callback_data=f"category_{categories[i][1]}"))
        if i + 1 < len(categories):
            row.append(InlineKeyboardButton(categories[i+1][0], callback_data=f"category_{categories[i+1][1]}"))
        buttons.append(row)
    
    # Добавляем кнопку "Назад" в главное меню
    buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(buttons)

def get_cancel_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="cancel")]])

# Функции для работы с новостями
def get_news_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'news.json')

def load_news():
    try:
        news_path = get_news_path()
        with open(news_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_news(news):
    news_path = get_news_path()
    with open(news_path, 'w', encoding='utf-8') as f:
        json.dump(news, f, ensure_ascii=False, indent=4)

# Вспомогательные функции
async def cancel_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    if update.callback_query:
        await update.callback_query.edit_message_text(
            "❌ Запрос отменён.",
            reply_markup=get_main_keyboard()
        )
    else:
        await update.message.reply_text(
            "❌ Запрос отменён.",
            reply_markup=get_main_keyboard()
        )

async def send_to_group(context: ContextTypes.DEFAULT_TYPE, message: str, photo=None, document=None, username=None, request_id=None, category=None):
    logger.info(f"Sending to group {GROUP_ID}: {message}")
    try:
        full_message = f"Запрос #{request_id} из категории '{category}' от @{username if username else 'неизвестный'}:\n{message}"
        await context.bot.send_message(chat_id=GROUP_ID, text=full_message)
        if photo:
            await context.bot.send_photo(chat_id=GROUP_ID, photo=photo[-1].file_id)
        if document:
            await context.bot.send_document(chat_id=GROUP_ID, document=document.file_id)
    except TelegramError as e:
        logger.error(f"Ошибка Telegram: {e}")
        raise
    except Exception as e:
        logger.error(f"Неизвестная ошибка отправки: {e}")
        raise

# Обработчики
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    logger.info(f"Received /start from chat_id: {chat_id}")
    
    welcome_text = (
        "Добро пожаловать в 'Товары из Китая'! 🛒\n\n"
        "Мы ваш надежный партнер для импорта из Китая. Специализируемся на автомобильной индустрии, "
        "но можем привезти абсолютно всё: от запчастей и станков до игрушек.\n\n"
        "🚀 Быстрая коммуникация с поставщиками\n"
        "💰 Выгодные цены\n"
        "📦 Удобная доставка\n\n"
        "Выберите раздел в меню ниже:"
    )
    
    await update.message.reply_text(welcome_text, reply_markup=get_main_keyboard())

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    logger.info(f"Button pressed: {data}")

    if data == "cancel":
        await cancel_request(update, context)
        return

    if data == "back_to_main":
        await query.edit_message_text(
            "Главное меню:",
            reply_markup=get_main_keyboard()
        )
        return

    if data == "product_selection":
        await query.edit_message_text(
            "🏪 Выберите категорию товара:",
            reply_markup=get_categories_keyboard()
        )
        return

    if data == "help":
        await query.edit_message_text(
            "❓ Опишите вашу проблему или предложение:",
            reply_markup=get_cancel_keyboard()
        )
        context.user_data['help_request'] = True
        return

    if data == "contacts":
        contacts_text = (
            "📞 Наши контакты:\n\n"
            "🌐 Сайт: yuemo-logistics.ru\n"
            "📱 WhatsApp: +86 153 2332 5277\n"
            "✉️ Email: info@yuemo-logistics.ru\n\n"
            "🕒 Время работы: 24/7"
        )
        await query.edit_message_text(
            contacts_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]])
        )
        return

    if data == "news_feed":
        news = load_news()
        if not news:
            await query.edit_message_text(
                "📢 Пока новостей нет. Проверьте позже!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]])
            )
        else:
            await query.edit_message_text(
                "📢 Последние новости и отгрузки:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="back_to_main")]])
            )
            for item in news:
                if item.get('text'):
                    await context.bot.send_message(
                        chat_id=query.message.chat_id,
                        text=f"📅 {item['text']}"
                    )
                if item.get('photo'):
                    await context.bot.send_photo(
                        chat_id=query.message.chat_id,
                        photo=item['photo']
                    )
        return

    if data.startswith("category_"):
        category_map = {
            "auto": "🚗 Автомобильные товары",
            "moto": "🏍️ Мотоциклы и питбайки",
            "toys": "🧸 Игрушки",
            "bags": "👜 Сумки",
            "clothes": "👕 Одежда",
            "sport": "⚽ Спортивный инвентарь",
            "electronics": "📱 Электроника",
            "appliances": "🏠 Бытовая техника",
            "decor": "🏠 Домашний декор",
            "beauty": "💄 Красота и здоровье",
            "jewelry": "💍 Ювелирка и аксессуары",
            "tools": "🛠️ Инструменты и оборудование",
            "office": "📊 Офисные товары",
            "kids": "🧒 Детские товары",
            "machinery": "⚙️ Станки и механизмы",
            "other_items": "📦 Другие товары"
        }
        
        category_key = data.replace("category_", "")
        category = category_map.get(category_key, "📦 Неизвестная категория")
        context.user_data['category'] = category
        
        if category == "🚗 Автомобильные товары":
            await query.edit_message_text(
                f"Вы выбрали: {category}\n\n"
                "🔍 Рекомендации для быстрого поиска:\n"
                "• VIN номер\n"
                "• Номер кузова\n" 
                "• Марка и модель\n"
                "• Год выпуска\n"
                "• Код запчасти\n\n"
                "📝 Опишите ваш запрос или приложите фото:",
                reply_markup=get_cancel_keyboard()
            )
        else:
            await query.edit_message_text(
                f"Вы выбрали: {category}\n\n"
                "🔍 Рекомендации для быстрого поиска:\n"
                "• Код товара или артикул\n"
                "• Фотографии товара\n"
                "• Видео обзор\n"
                "• Технические характеристики\n\n"
                "📝 Опишите ваш запрос или приложите фото:",
                reply_markup=get_cancel_keyboard()
            )
        context.user_data['free_request'] = True
        return

# Обработчик для добавления новостей
async def start_add_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📝 Введите текст новости (или отправьте /cancel для отмены):"
    )
    return TEXT

async def get_news_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['news_text'] = update.message.text
    await update.message.reply_text(
        "📸 Теперь отправьте фото (или документ, если нужно). Если не хотите, просто отправьте /skip:"
    )
    return PHOTO_OR_DOC

async def get_news_photo_or_doc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text and update.message.text.lower() == "/skip":
        photo = None
        document = None
    else:
        photo = update.message.photo[-1].file_id if update.message.photo else None
        document = update.message.document.file_id if update.message.document else None

    news = load_news()
    news.append({
        "text": context.user_data['news_text'],
        "photo": photo,
        "document": document,
        "timestamp": time.time()
    })
    save_news(news)
    await update.message.reply_text(
        "✅ Новость добавлена в раздел Новости/Отгрузки.",
        reply_markup=get_main_keyboard()
    )
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❌ Добавление новости отменено.",
        reply_markup=get_main_keyboard()
    )
    context.user_data.clear()
    return ConversationHandler.END

# Обработчик команды /cancel
async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cancel_request(update, context)

# Настройка ConversationHandler для добавления новостей
news_conv_handler = ConversationHandler(
    entry_points=[CommandHandler("add_news", start_add_news)],
    states={
        TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_news_text)],
        PHOTO_OR_DOC: [
            MessageHandler(filters.PHOTO, get_news_photo_or_doc),
            MessageHandler(filters.Document.ALL, get_news_photo_or_doc),
            CommandHandler("skip", get_news_photo_or_doc)
        ]
    },
    fallbacks=[CommandHandler("cancel", cancel_news)]
)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    text = update.message.text or update.message.caption
    photo = update.message.photo
    document = update.message.document
    username = update.effective_user.username
    logger.info(f"Received message from @{username}: {text}")

    if text and text.lower() == "отмена":
        await cancel_request(update, context)
        return

    if user_data.get('help_request'):
        if not text and not photo and not document:
            await update.message.reply_text(
                "📝 Пожалуйста, опишите проблему или предложение.",
                reply_markup=get_cancel_keyboard()
            )
            return
        message = f"Запрос помощи от @{username}:\n{text}"
        try:
            await send_to_group(context, message, photo, document, username)
            await update.message.reply_text(
                "✅ Ваш запрос помощи отправлен. Ожидайте ответа в ближайшее время.",
                reply_markup=get_main_keyboard()
            )
        except Exception as e:
            logger.error(f"Help request error: {e}")
            await update.message.reply_text(
                "❌ Не удалось отправить запрос. Попробуйте позже.",
                reply_markup=get_main_keyboard()
            )
        user_data.clear()
        return

    if user_data.get('free_request'):
        if not text and not photo and not document:
            await update.message.reply_text(
                "📝 Пожалуйста, добавьте описание, фото или документ к вашему запросу.",
                reply_markup=get_cancel_keyboard()
            )
            return
        request_id = int(time.time())
        category = user_data.get('category', 'Неизвестно')
        message = f"Запрос из категории '{category}' от @{username}:\n{text}"
        try:
            await send_to_group(context, message, photo, document, username, request_id, category)
            await update.message.reply_text(
                f"✅ Ваш запрос #{request_id} отправлен поставщикам!\n\n"
                "⚡ Будет обработан в ближайшее время.\n"
                "📞 Мы свяжемся с вами для уточнения деталей.",
                reply_markup=get_main_keyboard()
            )
        except Exception as e:
            logger.error(f"Free request error: {e}")
            await update.message.reply_text(
                "❌ Не удалось отправить запрос. Попробуйте позже.",
                reply_markup=get_main_keyboard()
            )
        user_data.clear()
        return

# Запуск бота
def run_bot():
    logger.info("Starting Telegram bot...")
    
    application = Application.builder().token(TOKEN).build()

    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(news_conv_handler)

    # Обработчики callback и сообщений
    application.add_handler(CallbackQueryHandler(handle_button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_message))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_message))

    # Запуск
    logger.info("Bot starting polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

def main():
    logger.info("Application starting...")
    
    # Запускаем HTTP сервер в отдельном потоке
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()
    
    # Запускаем бота в основном потоке
    run_bot()

if __name__ == '__main__':
    main()