import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
ORS_API_KEY = os.getenv('ORS_API_KEY')
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///tsp_bot.db')

MAX_POINTS_FOR_EXACT_SOLUTION = 10