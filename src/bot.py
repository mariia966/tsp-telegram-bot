import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import config

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Привет! Я бот для решения задачи коммивояжёра.\n\n"
        "Отправь мне список городов или координат, и я найду оптимальный маршрут!\n\n"
        "Формат ввода:\n"
        "Москва, Красная площадь\n"
        "Санкт-Петербург, Эрмитаж\n"
        "Казань, Кремль"
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "📋 Как пользоваться ботом:\n\n"
        "1. Отправь список точек (каждая с новой строки)\n"
        "2. Можно использовать названия или координаты\n"
        "3. Пример координат: 55.751244, 37.618423\n"
        "4. Я найду самый короткий маршрут через все точки!"
    )

@dp.message()
async def handle_points(message: types.Message):
    points = message.text.strip().split('\n')
    if len(points) < 2:
        await message.answer("❌ Нужно как минимум 2 точки для построения маршрута!")
        return
    
    await message.answer(f"🔍 Обрабатываю {len(points)} точек...\nСкоро вернусь с результатом!")

async def main():
    print("Бот запускается...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
