# shein_coupon_bot_final_v2.py

import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

# ---- Configuration ----
DATA_FILE = "coupons.json"
AMOUNTS = ["500", "1000", "2000", "4000"]
CHANNEL_USERNAME = "@couponsheinn"  # Replace with your Telegram channel username

# ---- Helper Functions ----
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ---- Inline Menus ----
def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("➕ Add Coupon", callback_data="add"),
         InlineKeyboardButton("❌ Delete Coupon", callback_data="delete")],
        [InlineKeyboardButton("👀 View Coupons", callback_data="view")],
        [InlineKeyboardButton("🏠 Home", callback_data="home")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_amount_menu(flow_type):
    # flow_type: "delete" or "view"
    keyboard = [[InlineKeyboardButton(f"{amt} 💰", callback_data=f"{flow_type}_amount_{amt}") for amt in AMOUNTS]]
    keyboard.append([InlineKeyboardButton("All 🗂️", callback_data=f"{flow_type}_amount_all")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="home")])
    return InlineKeyboardMarkup(keyboard)

def get_nav_menu():
    # only home button for text input steps
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Home", callback_data="home")]])

# ---- Bot Handlers ----

# Check if user is member of channel
async def is_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        if member.status in ["member", "administrator", "creator"]:
            return True
    except:
        pass
    return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_member(update, context):
        await update.message.reply_text(
            f"⚠️ You must join our channel {CHANNEL_USERNAME} to use this bot.\nPlease join and then press /start again."
        )
        return
    user_id = str(update.effective_user.id)
    data = load_data()
    if user_id not in data:
        data[user_id] = {amt: [] for amt in AMOUNTS}
        save_data(data)
    await update.message.reply_text(
        f"👋 Hello {update.effective_user.first_name}! Welcome to Shein Coupon Manager.",
        reply_markup=get_main_menu()
    )

# ---- Callback Query for main actions ----
async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(update.effective_user.id)
    data = load_data()
    if user_id not in data:
        data[user_id] = {amt: [] for amt in AMOUNTS}
        save_data(data)

    if query.data == "add":
        context.user_data["flow"] = "add"
        await query.edit_message_text("✏️ Enter your coupon code:", reply_markup=get_nav_menu())
    elif query.data == "delete":
        context.user_data["flow"] = "delete_select_amount"
        await query.edit_message_text("Select category to delete coupons:", reply_markup=get_amount_menu("delete"))
    elif query.data == "view":
        context.user_data["flow"] = "view_select_amount"
        await query.edit_message_text("Select category to view coupons:", reply_markup=get_amount_menu("view"))
    elif query.data == "home":
        context.user_data.pop("flow", None)
        await query.edit_message_text("🏠 Main Menu:", reply_markup=get_main_menu())

# ---- Text input handler for Add Coupon and Delete serial ----
async def text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    if "flow" not in context.user_data:
        await update.message.reply_text("Please select an option from the menu.", reply_markup=get_main_menu())
        return

    flow = context.user_data["flow"]

    # Adding coupon flow
    if flow == "add":
        context.user_data["new_coupon"] = {"code": update.message.text}
        context.user_data["flow"] = "add_amount"
        await update.message.reply_text("💰 Enter the amount for this coupon (500, 1000, 2000, 4000):", reply_markup=get_nav_menu())
    elif flow == "add_amount":
        amount = update.message.text
        if amount not in AMOUNTS:
            await update.message.reply_text("❌ Invalid amount. Please enter 500, 1000, 2000, or 4000:")
            return
        data[user_id][amount].append(context.user_data["new_coupon"]["code"])
        save_data(data)
        context.user_data.pop("new_coupon")
        context.user_data.pop("flow")
        await update.message.reply_text(f"✅ Coupon added under {amount} 💰!", reply_markup=get_main_menu())

    # Deleting coupon by serial number
    elif flow == "delete_choose":
        try:
            serial = int(update.message.text)
        except ValueError:
            await update.message.reply_text("❌ Invalid input. Enter a valid serial number:")
            return
        delete_list = context.user_data.get("delete_list", [])
        if serial < 1 or serial > len(delete_list):
            await update.message.reply_text("❌ Serial number out of range. Try again:")
            return
        amt, code = delete_list[serial - 1]
        data[user_id][amt].remove(code)
        save_data(data)
        context.user_data.pop("delete_list")
        context.user_data.pop("flow")
        await update.message.reply_text(f"✅ Coupon [{code}] deleted!", reply_markup=get_main_menu())
    else:
        await update.message.reply_text("Please select an option from the menu.", reply_markup=get_main_menu())

# ---- Amount selection callback for delete/view ----
async def amount_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(update.effective_user.id)
    data = load_data()

    flow_type, _, category = query.data.partition("_amount_")  # flow_type = delete/view, category = 500/1000/all

    # Delete flow
    if flow_type == "delete":
        delete_list = []
        display_text = "❌ Select a coupon to delete:\n"
        count = 1
        for amt in AMOUNTS:
            if category != "all" and amt != category:
                continue
            for c in data[user_id].get(amt, []):
                display_text += f"{count}. [{amt} 💰] {c}\n"
                delete_list.append((amt, c))
                count += 1
        if not delete_list:
            await query.edit_message_text("⚠️ No coupons found in this category.", reply_markup=get_main_menu())
            return
        context.user_data["delete_list"] = delete_list
        context.user_data["flow"] = "delete_choose"
        await query.edit_message_text(display_text + "\nSend the serial number to delete:", reply_markup=get_nav_menu())

    # View flow
    elif flow_type == "view":
        display_text = ""
        if category == "all":
            for amt in AMOUNTS:
                coupons = data[user_id].get(amt, [])
                if coupons:
                    display_text += f"--- {amt} 💰 ---\n" + "\n".join(coupons) + "\n\n"
        else:
            coupons = data[user_id].get(category, [])
            if coupons:
                display_text += f"--- {category} 💰 ---\n" + "\n".join(coupons)
            else:
                display_text = "⚠️ No coupons found in this category."
        await query.edit_message_text(display_text or "⚠️ No coupons found.", reply_markup=get_main_menu())
        context.user_data.pop("flow", None)

# ---- Main ----
def main():
    TOKEN = "8381922403:AAE0ivq6hB5KSrbaYCPI4Zs2eFnN-khMkpc"  # Replace with your token
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^(add|delete|view|home)$"))
    app.add_handler(CallbackQueryHandler(amount_callback, pattern="^(delete|view)_amount_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_input))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()

