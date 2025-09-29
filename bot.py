import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes,
    ConversationHandler, filters
)

from config import BOT_TOKEN
from database import Database

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Состояния для ConversationHandler
TITLE, CONTENT, TAGS, LINK_NOTES = range(4)

# Инициализация базы данных
db = Database('zettelkasten.db')


class ZettelBot:
    def __init__(self, token):
        self.application = Application.builder().token(token).build()
        self.setup_handlers()

    def setup_handlers(self):
        # Команды
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help))
        self.application.add_handler(CommandHandler("notes", self.list_notes))
        self.application.add_handler(CommandHandler("search", self.search_notes))

        # Conversation для создания заметки
        create_note_conv = ConversationHandler(
            entry_points=[CommandHandler("new", self.new_note)],
            states={
                TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_title)],
                CONTENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_content)],
                TAGS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_tags)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
        )
        self.application.add_handler(create_note_conv)

        # Обработчики callback запросов
        self.application.add_handler(CallbackQueryHandler(self.button_handler))

        # Обработчик текстовых сообщений
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.echo))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        welcome_text = """
🤖 Добро пожаловать в Zettelkasten Bot!

Zettelkasten — это система ведения заметок, где каждая идея связывается с другими.

Доступные команды:
/new - Создать новую заметку
/notes - Показать все заметки
/search - Поиск по заметкам
/help - Помощь

Начните с создания своей первой заметки!
        """
        await update.message.reply_text(welcome_text)

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = """
📚 Помощь по Zettelkasten Bot:

Основные команды:
/new - Создать новую заметку
/notes - Показать список заметок
/search - Поиск по заголовку, содержанию и тегам

Как использовать:
1. Создавайте атомарные заметки (одна идея = одна заметка)
2. Связывайте заметки между собой
3. Используйте теги для категоризации
4. Регулярно пересматривайте и связывайте старые заметки

Принципы Zettelkasten:
- Атомарность: одна заметка = одна идея
- Связность: каждая заметка должна быть связана с другими
- Нелинейность: идеи образуют сеть, а не иерархию
        """
        await update.message.reply_text(help_text)

    async def new_note(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало создания новой заметки"""
        await update.message.reply_text(
            "📝 Создание новой заметки\n\n"
            "Введите заголовок заметки:"
        )
        return TITLE

    async def get_title(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение заголовка заметки"""
        context.user_data['title'] = update.message.text
        await update.message.reply_text(
            "Отлично! Теперь введите содержание заметки:"
        )
        return CONTENT

    async def get_content(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение содержания заметки"""
        context.user_data['content'] = update.message.text
        await update.message.reply_text(
            "Введите теги через запятую (необязательно):"
        )
        return TAGS

    async def get_tags(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение тегов и сохранение заметки"""
        tags = update.message.text
        user_id = update.message.from_user.id

        # Сохранение заметки в базу
        note_id = db.add_note(
            user_id=user_id,
            title=context.user_data['title'],
            content=context.user_data['content'],
            tags=tags
        )

        # Очистка временных данных
        context.user_data.clear()

        await update.message.reply_text(
            f"✅ Заметка успешно создана! (ID: {note_id})\n\n"
            f"Теперь вы можете связать эту заметку с другими через /notes"
        )
        return ConversationHandler.END

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена создания заметки"""
        context.user_data.clear()
        await update.message.reply_text("Создание заметки отменено.")
        return ConversationHandler.END

    async def list_notes(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать список заметок пользователя"""
        user_id = update.message.from_user.id
        notes = db.get_user_notes(user_id)

        if not notes:
            await update.message.reply_text("У вас пока нет заметок. Создайте первую через /new")
            return

        keyboard = []
        for note_id, title, created_at in notes:
            keyboard.append([InlineKeyboardButton(
                f"📄 {title} ({created_at[:10]})",
                callback_data=f"view_note_{note_id}"
            )])

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "📚 Ваши заметки:\n\n"
            "Нажмите на заметку для просмотра и управления:",
            reply_markup=reply_markup
        )

    async def search_notes(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Поиск по заметкам"""
        if not context.args:
            await update.message.reply_text(
                "Использование: /search <запрос>\n"
                "Пример: /search программирование"
            )
            return

        query = " ".join(context.args)
        user_id = update.message.from_user.id
        notes = db.search_notes(user_id, query)

        if not notes:
            await update.message.reply_text("По вашему запросу ничего не найдено.")
            return

        keyboard = []
        for note_id, title, content, tags in notes:
            # Обрезаем длинный контент для кнопки
            short_content = content[:30] + "..." if len(content) > 30 else content
            keyboard.append([InlineKeyboardButton(
                f"🔍 {title}: {short_content}",
                callback_data=f"view_note_{note_id}"
            )])

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"🔎 Результаты поиска по запросу: '{query}'",
            reply_markup=reply_markup
        )

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик нажатий на inline кнопки"""
        query = update.callback_query
        await query.answer()

        data = query.data
        user_id = query.from_user.id

        if data.startswith("view_note_"):
            note_id = int(data.split("_")[2])
            await self.show_note_detail(query, note_id, user_id)

        elif data.startswith("link_note_"):
            note_id = int(data.split("_")[2])
            await self.start_linking(query, note_id, user_id)

        elif data.startswith("create_link_"):
            parts = data.split("_")
            from_note_id = int(parts[2])
            to_note_id = int(parts[3])
            db.add_link(from_note_id, to_note_id)
            await query.edit_message_text("✅ Заметки успешно связаны!")

    async def show_note_detail(self, query, note_id, user_id):
        """Показать детали заметки с кнопками действий"""
        note = db.get_note(note_id, user_id)

        if not note:
            await query.edit_message_text("Заметка не найдена.")
            return

        note_id, user_id, title, content, tags, created_at, parent_id = note

        # Получаем связанные заметки
        linked_notes = db.get_linked_notes(note_id)

        text = f"""
📄 **{title}**

{content}

🏷️ Теги: {tags if tags else "нет"}
📅 Создана: {created_at[:16]}
🔗 Связанные заметки: {len(linked_notes)}
        """

        keyboard = [
            [InlineKeyboardButton("🔗 Связать с другой заметкой", callback_data=f"link_note_{note_id}")],
        ]

        # Добавляем связанные заметки
        if linked_notes:
            text += "\n\nСвязанные заметки:\n"
            for linked_id, linked_title in linked_notes:
                text += f"• {linked_title}\n"

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)

    async def start_linking(self, query, from_note_id, user_id):
        """Начать процесс связывания заметок"""
        notes = db.get_user_notes(user_id)

        if len(notes) < 2:
            await query.edit_message_text("У вас недостаточно заметок для связывания.")
            return

        keyboard = []
        for note_id, title, created_at in notes:
            if note_id != from_note_id:
                keyboard.append([InlineKeyboardButton(
                    f"🔗 {title}",
                    callback_data=f"create_link_{from_note_id}_{note_id}"
                )])

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "Выберите заметку для связывания:",
            reply_markup=reply_markup
        )

    async def echo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик случайных сообщений"""
        await update.message.reply_text(
            "Используйте команды для работы с ботом:\n"
            "/start - Начать работу\n"
            "/help - Помощь\n"
            "/new - Новая заметка\n"
            "/notes - Список заметок\n"
            "/search - Поиск"
        )

    def run(self):
        """Запуск бота"""
        self.application.run_polling()


if __name__ == "__main__":
    bot = ZettelBot(8250247525:AAEKhwC9bU1LQwDUZsNhBLhdMka6P9ofgGQ)
    bot.run()