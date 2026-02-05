import logging
import sqlite3
import requests
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    Filters,
    CallbackContext,
    ConversationHandler
)

# تنظیمات - توکن رو از متغیر محیطی بگیر
import os
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '6149717348:AAHLSQUwBOPewqDicfStDIF-iitia4s4QJw')
ADMIN_IDS = [678099805]
ZARINPAL_MERCHANT = os.environ.get('ZARINPAL_MERCHANT', 'مرچنت_کد_خودت')

# وضعیت‌ها
PACKAGE, USERS, PAYMENT = range(3)

# دیتابیس
conn = sqlite3.connect('bot.db', check_same_thread=False)
c = conn.cursor()

# ایجاد جدول
c.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    join_date TEXT
)
''')

c.execute('''
CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    package TEXT,
    price INTEGER,
    status TEXT DEFAULT 'pending'
)
''')
conn.commit()

# لاگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---- منوها ----
def start(update: Update, context: CallbackContext):
    user = update.effective_user
    
    # ذخیره کاربر
    c.execute('''
        INSERT OR IGNORE INTO users (user_id, username, first_name, join_date)
        VALUES (?, ?, ?, ?)
    ''', (user.id, user.username, user.first_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    
    keyboard = [
        [InlineKeyboardButton("🛒 خرید", callback_data='buy')],
        [InlineKeyboardButton("📞 پشتیبانی", url="https://t.me/username")],
        [InlineKeyboardButton("ℹ️ راهنما", callback_data='help')]
    ]
    if user.id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("👑 ادمین", callback_data='admin')])
    
    update.message.reply_text(
        f"سلام {user.first_name}!\nربات فروش کانفیگ",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END

def buy(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    
    keyboard = [
        [InlineKeyboardButton("50 گیگ - 30 هزار", callback_data='pkg_50')],
        [InlineKeyboardButton("100 گیگ - 60 هزار", callback_data='pkg_100')],
        [InlineKeyboardButton("🔙 برگشت", callback_data='back')]
    ]
    
    query.edit_message_text(
        "📦 انتخاب بسته:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return PACKAGE

def package(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    
    pkg = query.data
    if pkg == 'pkg_50':
        context.user_data['price'] = 30000
        context.user_data['pkg_name'] = "50 گیگ"
    else:
        context.user_data['price'] = 60000
        context.user_data['pkg_name'] = "100 گیگ"
    
    keyboard = [
        [InlineKeyboardButton("1 کاربر", callback_data='usr_1')],
        [InlineKeyboardButton("2 کاربر", callback_data='usr_2')],
        [InlineKeyboardButton("🔙 برگشت", callback_data='buy')]
    ]
    
    query.edit_message_text(
        f"✅ بسته: {context.user_data['pkg_name']}\n💰 قیمت پایه: {context.user_data['price']:,}\n\nتعداد کاربر:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return USERS

def users(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    
    users = int(query.data.split('_')[1])
    base = context.user_data['price']
    final = base + (50000 if users == 2 else 0)
    context.user_data['final'] = final
    context.user_data['users'] = users
    
    # ایجاد سفارش
    c.execute('''
        INSERT INTO orders (user_id, package, price) 
        VALUES (?, ?, ?)
    ''', (query.from_user.id, context.user_data['pkg_name'], final))
    order_id = c.lastrowid
    conn.commit()
    
    # درخواست پرداخت زرین‌پال
    payment_data = {
        "merchant_id": ZARINPAL_MERCHANT,
        "amount": final * 10,
        "callback_url": "https://google.com",
        "description": f"خرید کانفیگ - سفارش {order_id}"
    }
    
    try:
        r = requests.post(
            "https://api.zarinpal.com/pg/v4/payment/request.json",
            json=payment_data,
            headers={"Content-Type": "application/json"}
        )
        
        data = r.json()
        if data['data']['code'] == 100:
            auth = data['data']['authority']
            url = f"https://www.zarinpal.com/pg/StartPay/{auth}"
            
            keyboard = [
                [InlineKeyboardButton("💳 پرداخت", url=url)],
                [InlineKeyboardButton("✅ پرداخت کردم", callback_data=f'check_{order_id}')],
                [InlineKeyboardButton("❌ انصراف", callback_data='back')]
            ]
            
            query.edit_message_text(
                f"🆔 سفارش: {order_id}\n💰 مبلغ: {final:,}\n\nلینک پرداخت:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            query.edit_message_text("خطا در درگاه")
    except Exception as e:
        logger.error(f"Payment error: {e}")
        query.edit_message_text("خطا در ارتباط")
    
    return PAYMENT

def payment_check(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    query.edit_message_text("✅ پرداخت تایید شد\nکانفیگ به زودی ارسال می‌شود")
    return ConversationHandler.END

def help_cmd(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    query.edit_message_text("📞 پشتیبانی: @username\n💳 پرداخت: زرین‌پال")

def admin_panel(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    
    if query.from_user.id not in ADMIN_IDS:
        query.edit_message_text("⛔️ دسترسی ندارید")
        return
    
    c.execute("SELECT COUNT(*) FROM users")
    users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM orders")
    orders = c.fetchone()[0]
    
    query.edit_message_text(
        f"📊 آمار:\n👥 کاربران: {users}\n📦 سفارشات: {orders}"
    )

def back(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🛒 خرید", callback_data='buy')],
        [InlineKeyboardButton("📞 پشتیبانی", url="https://t.me/username")],
        [InlineKeyboardButton("ℹ️ راهنما", callback_data='help')]
    ]
    if query.from_user.id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("👑 ادمین", callback_data='admin')])
    
    query.edit_message_text(
        "منوی اصلی:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END

# ---- اجرا ----
def main():
    # تنظیم پورت برای Render
    port = int(os.environ.get('PORT', 8443))
    
    # ایجاد آپدیت‌ر
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    
    # هندلر خرید
    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(buy, pattern='^buy$')],
        states={
            PACKAGE: [CallbackQueryHandler(package, pattern='^pkg_')],
            USERS: [CallbackQueryHandler(users, pattern='^usr_')],
            PAYMENT: [CallbackQueryHandler(payment_check, pattern='^check_')]
        },
        fallbacks=[
            CallbackQueryHandler(back, pattern='^back$'),
            CallbackQueryHandler(buy, pattern='^buy$')
        ]
    )
    
    # سایر هندلرها
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(conv)
    dp.add_handler(CallbackQueryHandler(help_cmd, pattern='^help$'))
    dp.add_handler(CallbackQueryHandler(admin_panel, pattern='^admin$'))
    dp.add_handler(CallbackQueryHandler(back, pattern='^back$'))
    
    # شروع ربات
    logger.info("🤖 ربات در حال شروع...")
    
    # روی Render باید polling استفاده کنیم
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
