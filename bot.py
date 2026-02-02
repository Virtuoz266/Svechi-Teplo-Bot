import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, 
    ContextTypes, CallbackQueryHandler, ConversationHandler
)

# Импортируем конфигурацию и товары
from config import TOKEN, ADMIN_CHAT_ID
from products import PRODUCTS

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы для callback данных
PREV_BUTTON = "prev"
NEXT_BUTTON = "next"
ADD_TO_CART_BUTTON = "add_to_cart"
CLEAR_CART_BUTTON = "clear_cart"
START_ORDER_BUTTON = "start_order"

# Состояния для ConversationHandler
GET_NAME, GET_PHONE = range(2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    user = update.effective_user
    await update.message.reply_text(
        f"🕯️ Добро пожаловать в наш магазин ароматических свечей, {user.first_name}!\n\n"
        f"Здесь вы найдете уникальные свечи ручной работы с натуральными ароматами.\n\n"
        f"📋 Для просмотра каталога товаров используйте команду /catalog\n"
        f"🛒 Просмотреть корзину - /cart\n"
        f"❓ Помощь - /help",
    )

async def catalog(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /catalog - показывает первый товар"""
    if not PRODUCTS:
        await update.message.reply_text("Каталог товаров пуст.")
        return
    
    context.user_data['current_product_index'] = 0
    product = PRODUCTS[0]
    keyboard = create_product_keyboard(0)
    caption = create_product_caption(product)
    
    try:
        if os.path.exists(product['photo']):
            with open(product['photo'], 'rb') as photo_file:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=photo_file,
                    caption=caption,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
        else:
            logger.error(f"Файл не найден: {product['photo']}")
            await update.message.reply_text(
                f"{caption}\n\n⚠️ Фото временно недоступно",
                parse_mode='HTML',
                reply_markup=keyboard
            )
    except Exception as e:
        logger.error(f"Ошибка при отправке фото: {e}")
        await update.message.reply_text(
            f"{caption}\n\n⚠️ Произошла ошибка при загрузке фото",
            parse_mode='HTML',
            reply_markup=keyboard
        )

def create_product_keyboard(current_index: int) -> InlineKeyboardMarkup:
    """Создает клавиатуру для товара"""
    keyboard = [
        [
            InlineKeyboardButton("⬅️", callback_data=PREV_BUTTON),
            InlineKeyboardButton("В корзину 🛒", callback_data=ADD_TO_CART_BUTTON),
            InlineKeyboardButton("➡️", callback_data=NEXT_BUTTON),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_product_caption(product: dict) -> str:
    """Создает описание товара"""
    try:
        product_index = PRODUCTS.index(product)
    except ValueError:
        product_index = 0
    
    return (
        f"<b>{product['name']}</b>\n\n"
        f"{product['description']}\n\n"
        f"💰 <b>Цена:</b> {product['price']} руб.\n"
        f"🆔 <b>Код товара:</b> {product['id']}\n"
        f"📦 Товар {product_index + 1} из {len(PRODUCTS)}"
    )

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик нажатий на inline кнопки (кроме start_order)"""
    query = update.callback_query
    user_data = context.user_data
    current_index = user_data.get('current_product_index', 0)
    
    if query.data == PREV_BUTTON or query.data == NEXT_BUTTON:
        await query.answer()
        
        if query.data == PREV_BUTTON:
            new_index = (current_index - 1) % len(PRODUCTS)
        else:
            new_index = (current_index + 1) % len(PRODUCTS)
            
        user_data['current_product_index'] = new_index
        product = PRODUCTS[new_index]
        caption = create_product_caption(product)
        keyboard = create_product_keyboard(new_index)
        
        try:
            if os.path.exists(product['photo']):
                with open(product['photo'], 'rb') as photo_file:
                    await query.edit_message_media(
                        media=InputMediaPhoto(
                            media=photo_file,
                            caption=caption,
                            parse_mode='HTML'
                        ),
                        reply_markup=keyboard
                    )
            else:
                logger.error(f"Файл не найден: {product['photo']}")
                await query.edit_message_caption(
                    caption=f"{caption}\n\n⚠️ Фото временно недоступно",
                    parse_mode='HTML',
                    reply_markup=keyboard
                )
        except Exception as e:
            logger.error(f"Ошибка при обновлении фото: {e}")
            await query.edit_message_caption(
                caption=f"{caption}\n\n⚠️ Произошла ошибка при загрузке фото",
                parse_mode='HTML',
                reply_markup=keyboard
            )
        
    elif query.data == ADD_TO_CART_BUTTON:
        product = PRODUCTS[current_index]
        cart = user_data.setdefault('cart', [])
        cart.append(product['id'])
        await query.answer(f"✅ {product['name']} добавлен в корзину!")
        
    elif query.data == CLEAR_CART_BUTTON:
        await query.answer()
        if 'cart' in user_data and user_data['cart']:
            user_data['cart'] = []
            await query.edit_message_text(
                "🛒 Ваша корзина очищена!\n\n"
                "Для добавления товаров используйте /catalog",
                reply_markup=None
            )
        else:
            await query.answer("Корзина уже пуста!")

async def cart_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /cart - показывает содержимое корзины"""
    user_data = context.user_data
    cart = user_data.get('cart', [])
    
    if not cart:
        await update.message.reply_text(
            "🛒 Ваша корзина пуста!\n\n"
            "Для добавления товаров используйте /catalog"
        )
        return
    
    product_counts = {}
    total_price = 0
    items_list = []
    
    for product_id in cart:
        product_counts[product_id] = product_counts.get(product_id, 0) + 1
    
    for product_id, count in product_counts.items():
        product = next((p for p in PRODUCTS if p['id'] == product_id), None)
        if product:
            product_total = product['price'] * count
            total_price += product_total
            items_list.append(f"• {product['name']} x{count} - {product_total} руб.")
    
    cart_message = (
        f"🛒 <b>Ваша корзина</b>\n\n"
        f"<b>Товары:</b>\n"
        f"{chr(10).join(items_list)}\n\n"
        f"<b>Общая стоимость:</b> {total_price} руб.\n\n"
        f"Товаров в корзине: {len(cart)}"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("🗑️ Очистить корзину", callback_data=CLEAR_CART_BUTTON),
            InlineKeyboardButton("Оформить заказ 📝", callback_data=START_ORDER_BUTTON),
        ]
    ]
    
    await update.message.reply_text(
        cart_message,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# === ConversationHandler (оформление заказа) ===

async def start_order_dialog(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало оформления заказа - вызывается при нажатии кнопки"""
    query = update.callback_query
    await query.answer()
    
    user_data = context.user_data
    cart = user_data.get('cart', [])
    
    if not cart:
        await query.edit_message_text("🛒 Ваша корзина пуста!")
        return ConversationHandler.END
    
    product_counts = {}
    total_price = 0
    items_summary = ""
    
    for product_id in cart:
        product_counts[product_id] = product_counts.get(product_id, 0) + 1
    
    for product_id, count in product_counts.items():
        product = next((p for p in PRODUCTS if p['id'] == product_id), None)
        if product:
            product_total = product['price'] * count
            total_price += product_total
            items_summary += f"• {product['name']} x{count}\n"
    
    await query.edit_message_text(
        f"📝 <b>Оформление заказа</b>\n\n"
        f"<b>Ваш заказ:</b>\n{items_summary}\n"
        f"<b>Итого к оплате:</b> {total_price} руб.\n\n"
        f"Пожалуйста, введите ваше имя:",
        parse_mode='HTML'
    )
    
    # Очищаем флаг ожидания телефона из старой системы (если есть)
    user_data.pop('awaiting_phone', None)
    
    return GET_NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получаем имя от пользователя"""
    name = update.message.text.strip()
    
    if len(name) < 2:
        await update.message.reply_text(
            "❌ Имя слишком короткое. Пожалуйста, введите ваше настоящее имя:"
        )
        return GET_NAME
    
    # Сохраняем имя
    context.user_data['customer_name'] = name
    
    await update.message.reply_text(
        f"Отлично, {name}! Теперь введите ваш номер телефона для связи:\n\n"
        f"<i>Пример: +7 999 123-45-67 или 89991234567</i>",
        parse_mode='HTML'
    )
    
    return GET_PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получаем телефон от пользователя - ТОЛЬКО ОДИН РАЗ!"""
    phone = update.message.text.strip()
    
    # Простая валидация телефона
    phone_digits = ''.join(filter(str.isdigit, phone))
    
    if len(phone_digits) < 10:
        await update.message.reply_text(
            "❌ Номер телефона слишком короткий. Пожалуйста, введите корректный номер:\n\n"
            "<i>Пример: +7 999 123-45-67 или 89991234567</i>",
            parse_mode='HTML'
        )
        return GET_PHONE
    
    # Сохраняем телефон
    context.user_data['customer_phone'] = phone
    
    # Завершаем диалог и обрабатываем заказ
    await process_final_order(update, context)
    
    return ConversationHandler.END

async def process_final_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Собирает полный заказ и отправляет уведомление администратору
    """
    user_data = context.user_data
    
    # Получаем данные из корзины и ConversationHandler
    cart = user_data.get('cart', [])
    customer_name = user_data.get('customer_name', 'Не указано')
    customer_phone = user_data.get('customer_phone', 'Не указано')
    
    # Подсчитываем товары в заказе
    product_counts = {}
    total_price = 0
    order_items = []
    
    # Считаем количество каждого товара
    for product_id in cart:
        product_counts[product_id] = product_counts.get(product_id, 0) + 1
    
    # Формируем список товаров для сообщения
    for product_id, count in product_counts.items():
        product = next((p for p in PRODUCTS if p['id'] == product_id), None)
        if product:
            product_total = product['price'] * count
            total_price += product_total
            order_items.append(f"- {product['name']} ({count} шт.)")
    
    # Формируем красивое сообщение для администратора (Ольги)
    admin_message = (
        f"🔔 НОВЫЙ ЗАКАЗ! 🔔\n\n"
        f"👤 Клиент: {customer_name}\n"
        f"📞 Телефон: {customer_phone}\n\n"
        f"---\n\n"
        f"🛒 Состав заказа:\n"
        f"{chr(10).join(order_items)}\n\n"
        f"---\n\n"
        f"💰 Итого: {total_price} руб."
    )
    
    # Отправляем сообщение администратору
    if ADMIN_CHAT_ID:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=admin_message
            )
            logger.info(f"✅ Заказ отправлен администратору. Клиент: {customer_name}, сумма: {total_price} руб.")
            
            # Отправляем подтверждение пользователю
            await update.message.reply_text(
                "✅ Спасибо за ваш заказ! Мы скоро с вами свяжемся.\n\n"
                "🕯️ Желаем приятного использования наших свечей!"
            )
            
            # Очищаем корзину пользователя
            user_data['cart'] = []
            
            # Очищаем временные данные
            if 'customer_name' in user_data:
                del user_data['customer_name']
            if 'customer_phone' in user_data:
                del user_data['customer_phone']
            
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке заказа администратору: {e}")
            
            # Уведомляем пользователя об ошибке
            await update.message.reply_text(
                "❌ Произошла ошибка при обработке вашего заказа. "
                "Пожалуйста, попробуйте позже или свяжитесь с нами напрямую."
            )
    else:
        logger.warning("ADMIN_CHAT_ID не указан в config.py")
        
        # Все равно уведомляем пользователя
        await update.message.reply_text(
            "✅ Ваш заказ принят! Мы скоро с вами свяжемся.\n\n"
            "🕯️ Желаем приятного использования наших свечей!"
        )
        
        # Очищаем корзину пользователя
        user_data['cart'] = []
        
        # Очищаем временные данные
        if 'customer_name' in user_data:
            del user_data['customer_name']
        if 'customer_phone' in user_data:
            del user_data['customer_phone']

async def cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена оформления заказа"""
    await update.message.reply_text(
        "❌ Оформление заказа отменено.\n\n"
        "Вы можете вернуться к оформлению через команду /cart",
        reply_markup=InlineKeyboardMarkup([])
    )
    
    # Очищаем временные данные
    if 'customer_name' in context.user_data:
        del context.user_data['customer_name']
    if 'customer_phone' in context.user_data:
        del context.user_data['customer_phone']
    
    # Очищаем флаг ожидания из старой системы
    context.user_data.pop('awaiting_phone', None)
    
    return ConversationHandler.END

async def handle_invalid_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка невалидного ввода в ConversationHandler"""
    await update.message.reply_text(
        "❌ Пожалуйста, введите текстовое сообщение.\n"
        "Используйте /cancel для отмены оформления заказа."
    )
    
    return GET_NAME

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help"""
    help_text = (
        "🛍️ <b>Доступные команды:</b>\n\n"
        "/start - Начало работы с ботом\n"
        "/catalog - Показать каталог товаров\n"
        "/cart - Просмотреть корзину\n"
        "/help - Эта справка\n\n"
        "💡 <b>Как оформить заказ:</b>\n"
        "1. Просмотрите каталог (/catalog)\n"
        "2. Добавляйте товары в корзину кнопкой 'В корзину 🛒'\n"
        "3. Просмотрите корзину (/cart)\n"
        "4. Нажмите 'Оформить заказ 📝'\n"
        "5. Введите ваше имя и телефон (один раз)\n\n"
        "🔄 Во время оформления можно отменить заказ командой /cancel"
    )
    await update.message.reply_text(help_text, parse_mode='HTML')

async def show_item(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /item <номер> - показывает подробную информацию о товаре"""
    if not context.args:
        await update.message.reply_text(
            "Пожалуйста, укажите номер товара после команды.\n"
            "Например: /item 1"
        )
        return
    
    try:
        item_id = int(context.args[0])
        product = next((p for p in PRODUCTS if p['id'] == item_id), None)
        
        if product:
            caption = create_product_caption(product)
            
            try:
                if os.path.exists(product['photo']):
                    with open(product['photo'], 'rb') as photo_file:
                        await context.bot.send_photo(
                            chat_id=update.effective_chat.id,
                            photo=photo_file,
                            caption=caption,
                            parse_mode='HTML'
                        )
                else:
                    await update.message.reply_text(
                        f"{caption}\n\n⚠️ Фото временно недоступно",
                        parse_mode='HTML'
                    )
            except Exception as e:
                logger.error(f"Ошибка при отправке фото товара: {e}")
                await update.message.reply_text(
                    f"{caption}\n\n⚠️ Произошла ошибка при загрузке фото",
                    parse_mode='HTML'
                )
        else:
            await update.message.reply_text(f"❌ Товар с ID {item_id} не найден.")
    
    except ValueError:
        await update.message.reply_text("⚠️ Пожалуйста, введите корректный номер товара.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик обычных сообщений - НЕ для оформления заказа"""
    # Просто логируем сообщение, но не обрабатываем как заказ
    logger.info(f"Пользователь {update.effective_user.id} отправил: {update.message.text}")
    
    # Можно отправить подсказку
    await update.message.reply_text(
        "Для оформления заказа используйте команду /cart и нажмите 'Оформить заказ 📝'"
    )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик ошибок"""
    logger.error(f"Ошибка при обработке обновления {update}: {context.error}")
    
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ Произошла ошибка. Пожалуйста, попробуйте позже или свяжитесь с администратором."
            )
        except:
            pass

def main() -> None:
    """Запуск бота"""
    # Создаем приложение
    application = Application.builder().token(TOKEN).build()
    
    # Создаем ConversationHandler для оформления заказа
    order_conversation = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_order_dialog, pattern=f"^{START_ORDER_BUTTON}$")],
        states={
            GET_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_name),
            ],
            GET_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_order),
        ],
    )
    
    # Регистрируем обработчики команд
    application.add_handler(order_conversation)  # ВАЖНО: Сначала ConversationHandler!
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("catalog", catalog))
    application.add_handler(CommandHandler("cart", cart_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("item", show_item))
    
    # Регистрируем обработчик остальных inline кнопок
    application.add_handler(CallbackQueryHandler(
        handle_callback_query, 
        pattern=f"^({PREV_BUTTON}|{NEXT_BUTTON}|{ADD_TO_CART_BUTTON}|{CLEAR_CART_BUTTON})$"
    ))
    
    # Регистрируем обработчик обычных сообщений (после всех остальных!)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Обработчик ошибок
    application.add_error_handler(error_handler)
    
    # Запускаем бота
    print("🕯️ Бот-магазин свечей запущен...")
    print(f"📦 В каталоге {len(PRODUCTS)} товаров")
    print("📞 ConversationHandler для оформления заказа активирован")
    
    if ADMIN_CHAT_ID:
        print(f"👤 Уведомления будут отправляться администратору (ID: {ADMIN_CHAT_ID})")
    else:
        print("⚠️ ADMIN_CHAT_ID не указан! Уведомления администратору отправляться не будут")
    
    print("\n✅ Бот готов к работе! Теперь телефон запрашивается только один раз.")
    
    # ИСПРАВЛЕНО: убрано Update.ALL_UPDATES
    application.run_polling()

if __name__ == '__main__':
    main()