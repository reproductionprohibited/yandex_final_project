from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode


TOKEN = '7135061417:AAFc2OfObCI9t2ds5uyoFvo7hIKGt4SZjXc'
bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
