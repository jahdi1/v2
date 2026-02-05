import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)
import sqlite3
import requests
from datetime import datetime

# تنظیمات
TOKEN = "6149717348:AAHLSQUwBOPewqDicfStDIF-iitia4s4QJw"
ADMIN_IDS = [678099805]  # ایدی ادمین‌ها
ZARINPAL_MERCHANT = "YOUR_MERCHANT_CODE"  # مرچنت کد زرین‌پال

# وضعیت‌های گفتگو
PACKAGE, USERS, PAYMENT, SUPPORT = range(4)

# دیتابیس
conn = sqlite3.connect('bot.db', check_same_thread=False)
cursor = conn.cursor()

# ایجاد جدول‌ها
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    join_date DATETIME,
    total_spent INTEGER DEFAULT 0
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    package TEXT,
    users_count INTEGER,
    price INTEGER,
    status TEXT DEFAULT 'pending',
    payment_date DATETIME,
    config_sent BOOLEAN DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users (user_id)
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS admin_messages (
    msg_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    admin_id INTEGER,
    message TEXT,
    timestamp DATETIME
)
''')
conn.commit()

# لاگ‌گیری
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ---------- توابع کمکی ----------
async def save_user(user_id, username, first_name):
    """ذخیره کاربر در دیتابیس"""
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, first_name, join_date)
        VALUES (?, ?, ?, ?)
    ''', (user_id, username, first_name, datetime.now()))
    conn.commit()

async def update_user_spent(user_id, amount):
    """به روزرسانی مجموع خرید کاربر"""
    cursor.execute('''
        UPDATE users SET total_spent = total_spent + ? 
        WHERE user_id = ?
    ''', (amount, user_id))
    conn.commit()

# ---------- منوها ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع ربات"""
    user = update.effective_user
    
    # ذخیره کاربر
    await save_user(user.id, user.username, user.first_name)
    
    # نمایش منوی اصلی
    keyboard = [
        [InlineKeyboardButton("🛒 خرید کانفیگ", callback_data='buy')],
        [InlineKeyboardButton("🛟 پشتیبانی", callback_data='support')],
        [InlineKeyboardButton("📞 ارتباط با مدیر", url="https://t.me/YourUsername")],
        [InlineKeyboardButton("ℹ️ راهنما", callback_data='help')]
    ]
    
    if user.id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("👑 پنل مدیریت", callback_data='admin')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = f"""
🌟 سلام {user.first_name}!

به ربات فروش کانفیگ خوش آمدید!

🔹 **امکانات ربات:**
• خرید آنلاین کانفیگ
• پشتیبانی 24 ساعته
• ارسال سریع کانفیگ

💳 **روش پرداخت:** زرین‌پال
⚡️ **ارسال کانفیگ:** بلافاصله پس از پرداخت

لطفاً گزینه مورد نظر را انتخاب کنید:
    """
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    return ConversationHandler.END

async def buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """منوی خرید"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [
            InlineKeyboardButton("50 گیگ", callback_data='package_50'),
            InlineKeyboardButton("100 گیگ", callback_data='package_100')
        ],
        [InlineKeyboardButton("نامحدود 1 ماهه", callback_data='package_unlimited')],
        [InlineKeyboardButton("🔙 برگشت", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📦 **لیست بسته‌ها:**\n\n"
        "1️⃣ **50 گیگ**\n"
        "   ⏱ مدت: 30 روز\n"
        "   💰 قیمت: 30,000 تومان\n\n"
        "2️⃣ **100 گیگ**\n"
        "   ⏱ مدت: 30 روز\n"
        "   💰 قیمت: 60,000 تومان\n\n"
        "3️⃣ **نامحدود 1 ماهه**\n"
        "   ⏱ مدت: 30 روز\n"
        "   💰 قیمت: 200,000 تومان\n\n"
        "لطفاً بسته مورد نظر را انتخاب کنید:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return PACKAGE

async def package_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """انتخاب بسته"""
    query = update.callback_query
    await query.answer()
    
    package_data = query.data
    context.user_data['package'] = package_data
    
    # تعیین قیمت پایه
    prices = {
        'package_50': 30000,
        'package_100': 60000,
        'package_unlimited': 200000
    }
    context.user_data['base_price'] = prices.get(package_data, 30000)
    
    keyboard = [
        [
            InlineKeyboardButton("1 کاربر", callback_data='users_1'),
            InlineKeyboardButton("2 کاربر", callback_data='users_2'),
            InlineKeyboardButton("5 کاربر", callback_data='users_5')
        ],
        [InlineKeyboardButton("🔙 برگشت", callback_data='buy')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    package_name = {
        'package_50': '50 گیگ',
        'package_100': '100 گیگ',
        'package_unlimited': 'نامحدود 1 ماهه'
    }.get(package_data, 'نامشخص')
    
    await query.edit_message_text(
        f"✅ **بسته انتخاب شده:** {package_name}\n"
        f"💰 **قیمت پایه:** {context.user_data['base_price']:,} تومان\n\n"
        "👥 **تعداد کاربران همزمان:**\n\n"
        "• 1 کاربر ➜ قیمت پایه\n"
        "• 2 کاربر ➜ +50,000 تومان\n"
        "• 5 کاربر ➜ +100,000 تومان\n\n"
        "لطفاً تعداد کاربران را انتخاب کنید:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return USERS

async def users_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """انتخاب تعداد کاربر"""
    query = update.callback_query
    await query.answer()
    
    users_data = query.data
    users_count = int(users_data.split('_')[1])
    context.user_data['users_count'] = users_count
    
    # محاسبه قیمت نهایی
    base_price = context.user_data['base_price']
    if users_count == 2:
        final_price = base_price + 50000
    elif users_count == 5:
        final_price = base_price + 100000
    else:
        final_price = base_price
    
    context.user_data['final_price'] = final_price
    
    keyboard = [
        [InlineKeyboardButton("💳 پرداخت نهایی", callback_data='payment_zarinpal')],
        [InlineKeyboardButton("🔙 تغییر بسته", callback_data='buy')],
        [InlineKeyboardButton("🏠 منوی اصلی", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    package_name = {
        'package_50': '50 گیگ',
        'package_100': '100 گیگ',
        'package_unlimited': 'نامحدود 1 ماهه'
    }.get(context.user_data['package'], 'نامشخص')
    
    await query.edit_message_text(
        f"🧾 **فاکتور خرید**\n\n"
        f"📦 بسته: {package_name}\n"
        f"👥 تعداد کاربر همزمان: {users_count} نفر\n"
        f"💰 قیمت پایه: {base_price:,} تومان\n"
        f"➕ اضافه‌بها کاربران: {final_price - base_price:,} تومان\n"
        f"🔸 مبلغ قابل پرداخت: **{final_price:,} تومان**\n\n"
        "برای تکمیل خرید روی دکمه پرداخت کلیک کنید:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return PAYMENT

async def payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پرداخت با زرین‌پال"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    final_price = context.user_data['final_price']
    
    # ذخیره سفارش در دیتابیس (وضعیت pending)
    cursor.execute('''
        INSERT INTO orders (user_id, package, users_count, price, status, payment_date)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user.id, context.user_data['package'], 
          context.user_data['users_count'], final_price, 
          'pending', datetime.now()))
    order_id = cursor.lastrowid
    conn.commit()
    
    # ایجاد درخواست پرداخت زرین‌پال
    payment_data = {
        "merchant_id": ZARINPAL_MERCHANT,
        "amount": final_price * 10,  # تبدیل به ریال (هر تومان = 10 ریال)
        "callback_url": "https://your-website.com/verify",
        "description": f"خرید کانفیگ - شماره سفارش: {order_id}",
        "metadata": {
            "order_id": order_id,
            "user_id": user.id
        }
    }
    
    try:
        response = requests.post(
            "https://api.zarinpal.com/pg/v4/payment/request.json",
            json=payment_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            data = response.json()
            if data['data']['code'] == 100:
                authority = data['data']['authority']
                payment_url = f"https://www.zarinpal.com/pg/StartPay/{authority}"
                
                # ذخیره authority در دیتابیس
                cursor.execute('''
                    UPDATE orders SET metadata = ? WHERE order_id = ?
                ''', (authority, order_id))
                conn.commit()
                
                keyboard = [
                    [InlineKeyboardButton("🔗 پرداخت آنلاین", url=payment_url)],
                    [InlineKeyboardButton("✅ پرداخت کردم", callback_data=f'check_payment_{order_id}')],
                    [InlineKeyboardButton("❌ انصراف", callback_data='back_to_main')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    f"✅ درخواست پرداخت ایجاد شد\n\n"
                    f"🆔 شماره سفارش: `{order_id}`\n"
                    f"👤 خریدار: {user.first_name}\n"
                    f"💰 مبلغ: {final_price:,} تومان\n\n"
                    "لطفاً روی دکمه زیر کلیک و پرداخت را انجام دهید:\n\n"
                    "⚠️ پس از پرداخت، روی دکمه '✅ پرداخت کردم' کلیک کنید.",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                
                # ارسال پیام به ادمین
                for admin_id in ADMIN_IDS:
                    try:
                        await context.bot.send_message(
                            admin_id,
                            f"🛒 **سفارش جدید**\n\n"
                            f"🆔 سفارش: {order_id}\n"
                            f"👤 کاربر: {user.first_name} (@{user.username or 'بدون یوزر'})\n"
                            f"🆔 ایدی: {user.id}\n"
                            f"📦 بسته: {context.user_data['package']}\n"
                            f"👥 کاربران: {context.user_data['users_count']}\n"
                            f"💰 مبلغ: {final_price:,} تومان\n"
                            f"⏰ زمان: {datetime.now().strftime('%H:%M:%S %Y-%m-%d')}",
                            parse_mode='Markdown'
                        )
                    except:
                        pass
                
            else:
                await query.edit_message_text("❌ خطا در ایجاد درگاه پرداخت. لطفاً مجدداً تلاش کنید.")
        else:
            await query.edit_message_text("❌ خطا در ارتباط با درگاه پرداخت.")
    
    except Exception as e:
        logging.error(f"Payment error: {e}")
        await query.edit_message_text("❌ خطای سیستمی در پرداخت.")
    
    return ConversationHandler.END

async def support_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """منوی پشتیبانی"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📞 ارتباط مستقیم با مدیر", url="https://t.me/YourUsername")],
        [InlineKeyboardButton("💬 ارسال پیام به پشتیبانی", callback_data='send_message')],
        [InlineKeyboardButton("🔙 برگشت", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🛟 **پشتیبانی آنلاین**\n\n"
        "• ساعت پاسخگویی: 24 ساعته\n"
        "• زمان پاسخ: حداکثر 15 دقیقه\n"
        "• روش‌های ارتباطی:\n\n"
        "1️⃣ ارتباط مستقیم با مدیر (توصیه می‌شود)\n"
        "2️⃣ ارسال پیام از طریق ربات\n\n"
        "لطفاً روش مورد نظر را انتخاب کنید:",
        reply_markup=reply_markup
    )

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پنل مدیریت"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if user_id not in ADMIN_IDS:
        await query.message.reply_text("⛔️ دسترسی غیرمجاز")
        return
    
    # آمار
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'completed'")
    total_orders = cursor.fetchone()[0]
    
    cursor.execute("SELECT SUM(price) FROM orders WHERE status = 'completed'")
    total_income = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'pending'")
    pending_orders = cursor.fetchone()[0]
    
    keyboard = [
        [InlineKeyboardButton("📊 آمار کامل", callback_data='admin_stats')],
        [InlineKeyboardButton("📦 مدیریت سفارشات", callback_data='admin_orders')],
        [InlineKeyboardButton("📩 ارسال کانفیگ", callback_data='admin_send_config')],
        [InlineKeyboardButton("👥 کاربران VIP", callback_data='admin_vip')],
        [InlineKeyboardButton("🔙 منوی اصلی", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    stats_text = f"""
👑 **پنل مدیریت**

📈 **آمار سریع:**
• 👥 کاربران کل: {total_users}
• ✅ سفارشات تکمیل شده: {total_orders}
• ⏳ سفارشات در انتظار: {pending_orders}
• 💰 درآمد کل: {total_income:,} تومان

لطفاً گزینه مورد نظر را انتخاب کنید:
    """
    
    await query.edit_message_text(stats_text, reply_markup=reply_markup)

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بازگشت به منوی اصلی"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    
    keyboard = [
        [InlineKeyboardButton("🛒 خرید کانفیگ", callback_data='buy')],
        [InlineKeyboardButton("🛟 پشتیبانی", callback_data='support')],
        [InlineKeyboardButton("📞 ارتباط با مدیر", url="https://t.me/YourUsername")],
        [InlineKeyboardButton("ℹ️ راهنما", callback_data='help')]
    ]
    
    if user.id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("👑 پنل مدیریت", callback_data='admin')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🏠 **منوی اصلی**\n\n"
        "لطفاً گزینه مورد نظر را انتخاب کنید:",
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور راهنما"""
    query = update.callback_query
    await query.answer()
    
    help_text = """
📚 **راهنمای استفاده از ربات**

🔹 **مراحل خرید:**
1️⃣ انتخاب بسته مورد نظر
2️⃣ انتخاب تعداد کاربران
3️⃣ پرداخت آنلاین
4️⃣ دریافت کانفیگ (بلافاصله پس از پرداخت)

🔹 **روش‌های ارتباط:**
• پشتیبانی: منوی پشتیبانی
• مدیر: @YourUsername

🔹 **مشکلات رایج:**
• اگر کانفیگ را دریافت نکردید، به پشتیبانی پیام دهید
• در صورت مشکل در پرداخت، مجدداً تلاش کنید
• شماره سفارش خود را نزد خود نگه دارید

⚠️ **توجه:**
• کانفیگ فقط برای مصارف قانونی
• مسئولیت استفاده بر عهده کاربر
    """
    
    keyboard = [[InlineKeyboardButton("🔙 برگشت", callback_data='back_to_main')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(help_text, reply_markup=reply_markup)

# ---------- main ----------
def main():
    """اجرای ربات"""
    application = ApplicationBuilder().token(TOKEN).build()
    
    # ConversationHandler برای خرید
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(buy_callback, pattern='^buy$')],
        states={
            PACKAGE: [CallbackQueryHandler(package_selected, pattern='^package_')],
            USERS: [CallbackQueryHandler(users_selected, pattern='^users_')],
            PAYMENT: [CallbackQueryHandler(payment_handler, pattern='^payment_')],
        },
        fallbacks=[
            CallbackQueryHandler(back_to_main, pattern='^back_to_main$'),
            CallbackQueryHandler(buy_callback, pattern='^buy$')
        ],
        per_message=False
    )
    
    # هندلرهای اصلی
    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(support_handler, pattern='^support$'))
    application.add_handler(CallbackQueryHandler(admin_panel, pattern='^admin$'))
    application.add_handler(CallbackQueryHandler(back_to_main, pattern='^back_to_main$'))
    application.add_handler(CallbackQueryHandler(help_command, pattern='^help$'))
    
    # هندلر پیام‌های متنی
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: None))
    
    print("🤖 ربات در حال اجراست...")
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()