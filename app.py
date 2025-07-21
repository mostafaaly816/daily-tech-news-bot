import os
import asyncio
import sqlite3
from datetime import datetime, timedelta
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
import time

# تحميل المتغيرات
load_dotenv()
TOKEN = os.getenv('TELEGRAM_TOKEN')
ADMIN_ID = os.getenv('ADMIN_ID')

# إعداد Flask لإبقاء البوت نشطًا
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    while True:
        try:
            requests.get("https://your-bot-name.onrender.com")  # استبدل your-bot-name باسم مشروعك
        except:
            pass
        time.sleep(300)  # كل 5 دقائق

# قاعدة البيانات
conn = sqlite3.connect('subscriptions.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS users
                (user_id INTEGER PRIMARY KEY, 
                subscription_end TEXT,
                plan TEXT)''')
conn.commit()

# ... [كل الدوال الأخرى تبقى كما هي بدون تغيير] ...

def main():
    # بدء تشغيل Flask في خيط منفصل
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # بدء تشغيل ping في خيط منفصل
    ping_thread = Thread(target=keep_alive)
    ping_thread.daemon = True
    ping_thread.start()

    # إعداد بوت التليجرام
    app = Application.builder().token(TOKEN).build()

    # التسجيل
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_subscription))
    app.add_handler(CommandHandler("stats", admin_stats))

    # الجدولة
    scheduler = AsyncIOScheduler()
    scheduler.add_job(daily_job, 'cron', hour=8, timezone="Africa/Cairo")
    scheduler.start()

    app.run_polling()

if __name__ == "__main__":
    main()