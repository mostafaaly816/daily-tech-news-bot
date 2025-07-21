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

# تحميل المتغيرات
load_dotenv()
TOKEN = os.getenv('TELEGRAM_TOKEN')
ADMIN_ID = os.getenv('ADMIN_ID')

# قاعدة البيانات
conn = sqlite3.connect('subscriptions.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS users
                (user_id INTEGER PRIMARY KEY, 
                subscription_end TEXT,
                plan TEXT)''')
conn.commit()


async def fetch_github_trending():
    """جلب المشاريع الرائجة من GitHub"""
    url = "https://github.com/trending"
    headers = {'User-Agent': 'Mozilla/5.0'}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        projects = []
        for repo in soup.find_all('article', class_='Box-row')[:5]:
            title = repo.find('h2').get_text(strip=True).replace('\n', '').replace(' ', '')
            link = "https://github.com" + repo.find('h2').a['href']
            desc = repo.find('p').get_text(strip=True) if repo.find('p') else "لا يوجد وصف"
            stars = repo.find('a', href=lambda x: x and 'stargazers' in x).get_text(strip=True)

            projects.append(f"""
<b>{title}</b>
📝 {desc}
⭐ {stars}
🔗 <a href="{link}">رابط المشروع</a>
━━━━━━━━━━━━""")

        return "🚀 <b>مشاريع GitHub الرائجة اليوم:</b>\n" + "\n".join(projects)

    except Exception as e:
        print(f"Error fetching GitHub: {e}")
        return "⚠️ تعذر جلب مشاريع GitHub حالياً"


async def fetch_hackernews():
    """جلب أهم أخبار HackerNews"""
    url = "https://news.ycombinator.com/"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        news = []
        for item in soup.select('tr.athing')[:5]:
            title = item.find('span', class_='titleline').a.get_text()
            link = item.find('span', class_='titleline').a['href']
            news.append(f"• <a href='{link}'>{title}</a>")

        return "📰 <b>أهم أخبار HackerNews:</b>\n" + "\n".join(news)

    except Exception as e:
        print(f"Error fetching HackerNews: {e}")
        return "⚠️ تعذر جلب أخبار HackerNews حالياً"


async def fetch_devto_articles():
    """جلب أحدث مقالات Dev.to"""
    url = "https://dev.to/t/programming"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        articles = []
        for article in soup.find_all('div', class_='crayons-story')[:3]:
            title = article.find('h2').get_text(strip=True)
            link = "https://dev.to" + article.find('h2').a['href']
            articles.append(f"• <a href='{link}'>{title}</a>")

        return "📚 <b>أحدث المقالات التعليمية:</b>\n" + "\n".join(articles)

    except Exception as e:
        print(f"Error fetching Dev.to: {e}")
        return "⚠️ تعذر جلب المقالات التعليمية حالياً"


async def send_news(user_id: int):
    """إرسال الأخبار للمستخدم"""
    try:
        bot = Bot(token=TOKEN)

        today = datetime.now().strftime("%Y-%m-%d")
        news_message = f"""
📢 <b>تقرير يوم {today} عن عالم البرمجة</b>
━━━━━━━━━━━━
{await fetch_github_trending()}

{await fetch_hackernews()}

{await fetch_devto_articles()}
        """

        await bot.send_message(
            chat_id=user_id,
            text=news_message,
            parse_mode='HTML',
            disable_web_page_preview=True
        )
    except Exception as e:
        print(f"Error sending news: {e}")


async def daily_job():
    """مهمة يومية لإرسال الأخبار"""
    cursor.execute("""
        SELECT user_id FROM users 
        WHERE subscription_end >= date('now')
        OR (plan = 'trial' AND subscription_end >= date('now', '-3 days'))
    """)

    for user in cursor.fetchall():
        await send_news(user[0])


async def start(update: Update, context):
    """عرض خيارات الاشتراك"""
    user = update.effective_user
    keyboard = [
        [{"text": "اشتراك شهري ($5)", "callback_data": "monthly"}],
        [{"text": "اشتراك سنوي ($50)", "callback_data": "yearly"}],
        [{"text": "تجربة مجانية (3 أيام)", "callback_data": "trial"}]
    ]

    await update.message.reply_text(
        f"مرحباً {user.first_name}! 👋\n\nاختر خطة الاشتراك:",
        reply_markup={"inline_keyboard": keyboard}
    )


async def handle_subscription(update: Update, context):
    """معالجة اختيار الاشتراك"""
    query = update.callback_query
    user_id = query.from_user.id

    if query.data == "monthly":
        end_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        cursor.execute("INSERT OR REPLACE INTO users VALUES (?, ?, ?)",
                       (user_id, end_date, 'monthly'))
        conn.commit()
        await query.edit_message_text("✅ تم تفعيل الاشتراك الشهري بنجاح!\nستصلك الأخبار يومياً الساعة 8 صباحاً.")

    elif query.data == "trial":
        end_date = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d')
        cursor.execute("INSERT OR REPLACE INTO users VALUES (?, ?, ?)",
                       (user_id, end_date, 'trial'))
        conn.commit()
        await query.edit_message_text("🎁 تم تفعيل النسخة التجريبية لمدة 3 أيام!")
        await send_news(user_id)  # إرسال الأخبار فوراً


async def admin_stats(update: Update, context):
    """إحصائيات للمشرف"""
    if str(update.message.from_user.id) != ADMIN_ID:
        return

    cursor.execute("SELECT COUNT(*) FROM users")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE plan='monthly'")
    monthly = cursor.fetchone()[0]

    await update.message.reply_text(f"""
📊 <b>إحصائيات البوت:</b>
━━━━━━━━━━━━
👥 إجمالي المشتركين: {total}
💰 مشتركين شهريين: {monthly}
💵 إيرادات متوقعة: ${monthly * 5}/شهر
""", parse_mode='HTML')


def main():
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