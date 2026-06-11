from flask import Flask
import asyncio
import time
import sys
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.session.aiohttp import AiohttpSession
import config
from tsp_solver import TSPSolverAuto, geocode_address
from database import get_session, get_or_create_user, save_route, get_user_routes, get_user_stats
from visualizer import create_route_html

# Фикс для Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Создаём экземпляр автоматического решателя
solver = TSPSolverAuto()
dp = Dispatcher()


# ==================== КЛАВИАТУРЫ С КНОПКАМИ ====================

def get_main_keyboard():
    """Главная клавиатура с кнопками команд"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔍 Новый маршрут")],
            [KeyboardButton(text="📜 История"), KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="❓ Помощь"), KeyboardButton(text="ℹ️ О боте")]
        ],
        resize_keyboard=True,  # Автоматически подгоняет размер
        input_field_placeholder="Выберите действие или введите города..."
    )
    return keyboard


def get_cancel_keyboard():
    """Клавиатура для отмены действия"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )
    return keyboard


def get_route_actions_keyboard(route_id=None):
    """Инлайн-кнопки после построения маршрута"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗺️ Показать карту", callback_data="show_map")],
        [InlineKeyboardButton(text="📤 Поделиться", callback_data="share_route")],
        [InlineKeyboardButton(text="💾 Сохранить в PDF", callback_data="save_pdf")]
    ])
    return keyboard


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def parse_points(text: str):
    """Разбирает текст на список точек по строкам"""
    return [line.strip() for line in text.split('\n') if line.strip()]


def format_route_response(addresses, path, total_distance, algorithm, computation_time):
    """Форматирует ответ с маршрутом"""
    
    algo_emoji = "⚡" if "heuristic" in algorithm else "🎯"
    
    response = f"{algo_emoji} *Маршрут построен!*\n\n"
    response += f"📐 *Алгоритм:* `{algorithm}`\n\n"
    response += "📍 *Порядок посещения:*\n"
    for i, idx in enumerate(path):
        marker = "🚩" if i == 0 else "•"
        response += f"{marker} {i+1}. {addresses[idx]}\n"
    response += f"\n📏 *Общая дистанция:* `{total_distance:.1f}` км\n"
    response += f"⏱️ *Время расчёта:* `{computation_time:.2f}` сек\n"
    response += "💾 *Маршрут сохранён в историю!*"
    
    return response


async def send_route_map(message: Message, coordinates, addresses, path):
    """Генерирует и отправляет HTML-карту маршрута"""
    
    try:
        html_path = create_route_html(coordinates, addresses, path)
        
        with open(html_path, 'rb') as f:
            await message.answer_document(
                BufferedInputFile(f.read(), filename='route_map.html'),
                caption="🗺️ *Карта маршрута*\n\n"
                       "📥 Скачайте файл и откройте в браузере\n\n"
                       "🟢 Зелёный — старт\n"
                       "🔵 Синий — промежуточная точка\n"
                       "🔴 Красный — финиш\n"
                       "🔵 Синяя линия — путь следования",
                parse_mode="Markdown"
            )
        
        os.unlink(html_path)
        
    except Exception as e:
        print(f"❌ Ошибка отправки карты: {e}")


async def show_main_menu(message: Message):
    """Показывает главное меню с кнопками"""
    await message.answer(
        "🏠 *Главное меню*\n\n"
        "Выберите действие на клавиатуре ниже или просто отправьте список городов:\n\n"
        "📍 *Пример:*\n"
        "```\n"
        "Москва\n"
        "Тула\n"
        "Калуга\n"
        "```",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )


# ==================== КОМАНДЫ ====================

@dp.message(Command("start"))
async def cmd_start(message: Message):
    session = get_session()
    try:
        user = get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )
    finally:
        session.close()
    
    await show_main_menu(message)


@dp.message(Command("menu"))
async def cmd_menu(message: Message):
    """Команда для показа главного меню"""
    await show_main_menu(message)


@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📋 *Помощь по использованию бота*\n\n"
        "1️⃣ *Отправь список точек*\n"
        "   Каждая точка с новой строки\n"
        "   Можно использовать названия городов или координаты\n\n"
        "2️⃣ *Минимальное количество точек:* 2\n"
        "3️⃣ *Максимальное количество:* 15\n\n"
        "📍 *Пример отправки:*\n"
        "```\n"
        "Москва\n"
        "Тула\n"
        "Калуга\n"
        "```\n\n"
        "✨ *Доступные команды:*\n"
        "/start - главное меню\n"
        "/menu - показать меню\n"
        "/help - эта справка\n"
        "/test - тестовый маршрут\n"
        "/history - последние маршруты\n"
        "/stats - ваша статистика\n\n"
        "💡 *Результат:* оптимальный порядок и карта маршрута\n\n"
        "⚙️ *Как работает:*\n"
        "• 2-7 точек → точный алгоритм\n"
        "• 8-15 точек → эвристический алгоритм",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )


@dp.message(Command("test"))
async def cmd_test(message: Message):
    await message.answer("🔍 *Строю тестовый маршрут...*\n\n⏳ Обычно занимает 3-8 секунд", parse_mode="Markdown")
    start_time = time.time()
    test_points = ["Москва", "Санкт-Петербург", "Казань", "Нижний Новгород", "Екатеринбург"]
    
    coordinates = []
    for p in test_points:
        coords = geocode_address(p)
        if coords:
            coordinates.append(coords)
        else:
            await message.answer(f"❌ *Не удалось найти координаты для:* {p}", parse_mode="Markdown")
            return
    
    if len(coordinates) < 2:
        await message.answer("❌ *Недостаточно точек для построения маршрута*", parse_mode="Markdown")
        return
    
    path, distance, algorithm, computation_time = solver.solve(coordinates, fixed_start=0, closed=False)
    
    session = get_session()
    try:
        user = get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )
        
        save_route(
            session,
            user_id=user.id,
            points=test_points,
            coordinates=coordinates,
            order=path,
            total_distance=distance,
            algorithm=algorithm,
            computation_time=computation_time
        )
    finally:
        session.close()
    
    response = "✅ *Тестовый маршрут построен!*\n\n"
    response += f"📐 *Алгоритм:* `{algorithm}`\n\n"
    response += "📍 *Оптимальный порядок посещения:*\n"
    for i, idx in enumerate(path):
        response += f"{i+1}. {test_points[idx]}\n"
    response += f"\n📏 *Общая дистанция:* `{distance:.1f}` км\n"
    response += f"⏱️ *Время расчёта:* `{computation_time:.2f}` сек\n"
    response += "💾 *Маршрут сохранён в историю!*"
    
    await message.answer(response, parse_mode="Markdown")
    await send_route_map(message, coordinates, test_points, path)


@dp.message(Command("history"))
async def cmd_history(message: Message):
    session = get_session()
    try:
        user = get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            username=message.from_user.username
        )
        
        routes = get_user_routes(session, user.id, limit=5)
        
        if not routes:
            await message.answer(
                "📭 *У вас пока нет сохранённых маршрутов*\n\n"
                "Отправьте список городов, чтобы начать!",
                parse_mode="Markdown"
            )
            return
        
        response = "📜 *Ваши последние маршруты:*\n\n"
        for i, route in enumerate(routes, 1):
            date_str = route.created_at.strftime("%d.%m.%Y %H:%M")
            points_short = ", ".join(route.points[:2])
            if len(route.points) > 2:
                points_short += f"... (+{len(route.points)-2})"
            
            algo_emoji = "🎯" if "exact" in route.algorithm else "⚡"
            
            response += f"{i}. 🗺️ *{points_short}*\n"
            response += f"   {algo_emoji} `{route.total_distance:.1f}` км | {route.algorithm}\n"
            response += f"   📅 {date_str}\n\n"
        
        await message.answer(response, parse_mode="Markdown")
        
    finally:
        session.close()


@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    session = get_session()
    try:
        user = get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            username=message.from_user.username
        )
        
        stats = get_user_stats(session, user.id)
        
        if stats["total_routes"] == 0:
            await message.answer(
                "📊 *У вас пока нет статистики*\n\n"
                "Постройте первый маршрут!",
                parse_mode="Markdown"
            )
            return
        
        response = "📊 *Ваша статистика*\n\n"
        response += f"🚀 *Всего маршрутов:* `{stats['total_routes']}`\n"
        response += f"📏 *Общая дистанция:* `{stats['total_distance']}` км\n"
        response += f"⭐ *Средняя длина маршрута:* `{stats['avg_distance']}` км\n"
        
        if stats['last_route_date']:
            date_str = stats['last_route_date'].strftime("%d.%m.%Y %H:%M")
            response += f"🕐 *Последний расчёт:* {date_str}\n"
        
        if stats.get('routes_by_algorithm'):
            response += "\n📊 *Разбивка по алгоритмам:*\n"
            for algo, count in stats['routes_by_algorithm'].items():
                algo_display = "🎯 точный" if "exact" in algo else "⚡ эвристика"
                response += f"   {algo_display}: {count}\n"
        
        await message.answer(response, parse_mode="Markdown")
        
    finally:
        session.close()


@dp.message(lambda message: message.text == "🔍 Новый маршрут")
async def new_route_button(message: Message):
    await message.answer(
        "✏️ *Введите список городов*\n\n"
        "Каждый город с новой строки, например:\n"
        "```\n"
        "Москва\n"
        "Тула\n"
        "Калуга\n"
        "```\n\n"
        "Или отправьте ❌ Отмена",
        parse_mode="Markdown",
        reply_markup=get_cancel_keyboard()
    )


@dp.message(lambda message: message.text == "📜 История")
async def history_button(message: Message):
    await cmd_history(message)


@dp.message(lambda message: message.text == "📊 Статистика")
async def stats_button(message: Message):
    await cmd_stats(message)


@dp.message(lambda message: message.text == "❓ Помощь")
async def help_button(message: Message):
    await cmd_help(message)


@dp.message(lambda message: message.text == "ℹ️ О боте")
async def about_button(message: Message):
    await message.answer(
        "ℹ️ *О боте*\n\n"
        "🤖 *TSP Route Optimizer*\n\n"
        "Бот решает задачу коммивояжёра (TSP) — находит оптимальный маршрут между городами с учётом реальных дорожных расстояний.\n\n"
        "📡 *Технологии:*\n"
        "• Python + Aiogram\n"
        "• OpenRouteService API\n"
        "• Folium для карт\n"
        "• SQLite для хранения\n\n"
        "👨‍💻 *Разработчики:*\n"
        "• Нестерова М.Л.\n"
        "• Хромов Д.\n"
        "• Гормаков Я.\n\n"
        "📅 *Версия:* 2.0\n"
        "© 2025 Тульский государственный университет",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )


@dp.message(lambda message: message.text == "❌ Отмена")
async def cancel_button(message: Message):
    await show_main_menu(message)


# ==================== ОБРАБОТКА СООБЩЕНИЙ ====================

@dp.message()
async def handle_message(message: Message):
    text = message.text.strip()
    
    # Пропускаем команды и кнопки
    if text.startswith('/'):
        return
    
    # Пропускаем текст кнопок
    if text in ["🔍 Новый маршрут", "📜 История", "📊 Статистика", "❓ Помощь", "ℹ️ О боте", "❌ Отмена"]:
        return
    
    addresses = parse_points(text)
    
    if len(addresses) < 2:
        await message.answer(
            "❌ *Нужно минимум 2 точки для построения маршрута!*\n\n"
            "Отправь список городов с новой строки, например:\n"
            "```\n"
            "Москва\n"
            "Тула\n"
            "Калуга\n"
            "```\n\n"
            "Или воспользуйтесь кнопками меню",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        return
    
    if len(addresses) > 15:
        await message.answer(
            "⚠️ *Слишком много точек!*\n\n"
            f"Вы отправили {len(addresses)} точек.\n"
            "Максимум 15 для комфортной работы.",
            parse_mode="Markdown"
        )
        return
    
    status_msg = await message.answer(
        f"🔍 *Обрабатываю {len(addresses)} точек...*\n\n"
        f"⏳ Получаю координаты и строю маршрут",
        parse_mode="Markdown"
    )
    
    try:
        start_time = time.time()
        
        coordinates = []
        for addr in addresses:
            coords = geocode_address(addr)
            if coords:
                coordinates.append(coords)
            else:
                await status_msg.edit_text(
                    f"❌ *Не удалось найти координаты для:* {addr}\n\n"
                    "Проверь правильность написания и попробуй снова.",
                    parse_mode="Markdown"
                )
                return
        
        if len(coordinates) < 2:
            await status_msg.edit_text(
                "❌ *Недостаточно точек для построения маршрута!*\n\n"
                "Убедитесь, что все города найдены.",
                parse_mode="Markdown"
            )
            return
        
        path, total_distance, algorithm, computation_time = solver.solve(coordinates, fixed_start=0, closed=False)
        
        session = get_session()
        try:
            user = get_or_create_user(
                session,
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name
            )
            
            save_route(
                session,
                user_id=user.id,
                points=addresses,
                coordinates=coordinates,
                order=path,
                total_distance=total_distance,
                algorithm=algorithm,
                computation_time=computation_time
            )
        finally:
            session.close()
        
        response = format_route_response(addresses, path, total_distance, algorithm, computation_time)
        await status_msg.edit_text(response, parse_mode="Markdown")
        
        await send_route_map(message, coordinates, addresses, path)
        
    except Exception as e:
        await status_msg.edit_text(
            f"❌ *Произошла ошибка:*\n\n"
            f"`{str(e)}`\n\n"
            "Проверьте:\n"
            "• Правильность написания городов\n"
            "• Наличие интернета\n"
            "• Работу VPN",
            parse_mode="Markdown"
        )


# ==================== ЗАПУСК ====================

async def main():
    # Умное создание сессии: с прокси или без
    use_proxy = os.getenv("USE_PROXY", "false").lower() == "true"
    
    if use_proxy:
        print("🔐 Использую прокси для подключения")
        session = AiohttpSession(proxy="socks5://127.0.0.1:10808")
    else:
        print("🌐 Использую прямое подключение (без прокси)")
        session = AiohttpSession()
    
    bot = Bot(token=config.BOT_TOKEN, session=session)
    
    print("=" * 50)
    print("🤖 БОТ ЗАПУЩЕН!")
    print("=" * 50)
    print(f"📱 Бот: @{(await bot.get_me()).username}")
    print(f"🔑 Токен: {config.BOT_TOKEN[:15]}...")
    print(f"🔗 Режим: {'Прокси SOCKS5' if use_proxy else 'Прямое подключение'}")
    print("=" * 50)
    print("✅ Готов к работе!")
    print("=" * 50)
    print("📊 Режимы:")
    print("   • Точный алгоритм (2-7 точек)")
    print("   • Эвристический (8-15 точек)")
    print("=" * 50)
    print("🎮 Кнопки:")
    print("   • Главное меню с кнопками")
    print("   • Инлайн-кнопки после маршрута")
    print("=" * 50)
    
    await dp.start_polling(bot)


# --- Новый код для веб-сервера ---
def run_web():
    """Запускает минимальный веб-сервер для health checks"""
    web_app = Flask(__name__)
    
    @web_app.route('/')
    @web_app.route('/health')
    def health_check():
        return "OK", 200
    
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    import threading
    # Запускаем веб-сервер в фоновом потоке
    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()
    # Запускаем бота
    asyncio.run(main())