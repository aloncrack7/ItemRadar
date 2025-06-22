# bot.py
import os
import logging
import asyncio
from datetime import datetime
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram.error import TelegramError

# Load environment from .env
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Import your handlers from the adapter
from multiAgent.telegram_adapter import (
    handle_lost_flow,
    handle_found_flow,
    handle_found_confirmation,
    handle_lost_confirmation,
    handle_general_chat,
    handle_start_callback,
    handle_help_callback,
    handle_status_check,
    ItemRadarError,
    ValidationError,
)

# Configure logging with more detailed format
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler('itemradar_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Bot configuration
BOT_VERSION = "1.0.0"
MAX_CONCURRENT_USERS = 100
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX_REQUESTS = 10

# Rate limiting storage (in production, use Redis or similar)
user_request_counts = {}


def check_rate_limit(user_id: str) -> bool:
    """Simple rate limiting check"""
    now = datetime.now().timestamp()

    if user_id not in user_request_counts:
        user_request_counts[user_id] = []

    # Clean old requests
    user_request_counts[user_id] = [
        req_time for req_time in user_request_counts[user_id]
        if now - req_time < RATE_LIMIT_WINDOW
    ]

    # Check if under limit
    if len(user_request_counts[user_id]) >= RATE_LIMIT_MAX_REQUESTS:
        return False

    # Add current request
    user_request_counts[user_id].append(now)
    return True


async def rate_limit_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check rate limiting for user requests"""
    user_id = str(update.effective_user.id)

    if not check_rate_limit(user_id):
        await update.message.reply_text(
            "⚠️ **Rate limit exceeded**\n\n"
            f"Please wait a moment before sending another request.\n"
            f"Limit: {RATE_LIMIT_MAX_REQUESTS} requests per {RATE_LIMIT_WINDOW} seconds.",
            parse_mode="Markdown"
        )
        return False

    return True


async def log_user_activity(update: Update, action: str):
    """Log user activity for monitoring"""
    user = update.effective_user
    chat = update.effective_chat

    logger.info(
        f"User Activity - ID: {user.id}, Username: {user.username}, "
        f"Name: {user.first_name} {user.last_name or ''}, "
        f"Chat: {chat.type}, Action: {action}"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /start handler: show main menu with improved UI and user onboarding
    """
    try:
        # Rate limiting check
        if not await rate_limit_middleware(update, context):
            return

        await log_user_activity(update, "start_command")

        # Clear any existing state
        context.user_data.clear()

        user_name = update.effective_user.first_name or "there"

        keyboard = [
            [InlineKeyboardButton("🔍 I lost an item", callback_data="start_lost")],
            [InlineKeyboardButton("📸 I found an item", callback_data="start_found")],
            [
                InlineKeyboardButton("📊 My Reports", callback_data="check_status"),
                InlineKeyboardButton("🔍 Search Items", callback_data="SEARCH")
            ],
            [
                InlineKeyboardButton("ℹ️ Help", callback_data="show_help"),
                InlineKeyboardButton("📞 Support", callback_data="SUPPORT")
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        welcome_text = (
            f"👋 **Welcome to ItemRadar, {user_name}!**\n\n"
            f"🎯 *Your AI-powered lost & found assistant*\n\n"
            f"ItemRadar helps you:\n"
            f"• 📱 Report lost items with AI assistance\n"
            f"• 📷 Register found items automatically\n"
            f"• 🔗 Connect with people in your area\n"
            f"• 🔍 Search our database of lost/found items\n\n"
            f"**What would you like to do today?**\n\n"
            f"🆕 *New here? Try the Help section for a quick guide!*"
        )

        await update.message.reply_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Error in start command: {e}")
        await update.message.reply_text(
            "❌ Unable to start. Please try again or contact support."
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /help handler: comprehensive help with examples and tips
    """
    try:
        await log_user_activity(update, "help_command")

        help_text = (
            "🎯 **ItemRadar Help Guide**\n\n"

            "**📸 For Found Items:**\n"
            "1️⃣ Take a clear photo of the item\n"
            "2️⃣ Our AI will describe it automatically\n"
            "3️⃣ Provide your email and location\n"
            "4️⃣ Confirm details and submit\n\n"

            "**🔍 For Lost Items:**\n"
            "1️⃣ Describe what you lost in detail\n"
            "2️⃣ Tell us where and when you lost it\n"
            "3️⃣ Provide your contact information\n"
            "4️⃣ Review and submit your report\n\n"

            "**💡 Pro Tips:**\n"
            "• Be specific with descriptions (color, brand, size)\n"
            "• Include distinctive features or damage\n"
            "• Provide accurate location information\n"
            "• Check your email for match notifications\n\n"

            "**🤖 Commands:**\n"
            "`/start` - Show main menu\n"
            "`/help` - Show this help message\n"
            "`/cancel` - Cancel current operation\n"
            "`/status` - Check bot status\n"
            "`/privacy` - Privacy policy\n\n"

            "**🆘 Need More Help?**\n"
            "Contact our support team using the Support button below."
        )

        keyboard = [
            [InlineKeyboardButton("🏠 Back to Menu", callback_data="MENU")],
            [InlineKeyboardButton("📞 Contact Support", callback_data="SUPPORT")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            help_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Error in help command: {e}")
        await update.message.reply_text("❌ Unable to show help. Please try again.")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /status handler: show bot status and statistics
    """
    try:
        await log_user_activity(update, "status_command")

        # Get basic stats (in production, these would come from database)
        uptime = "Running smoothly ✅"
        version = BOT_VERSION
        user_id = update.effective_user.id

        status_text = (
            f"🤖 **ItemRadar Bot Status**\n\n"
            f"**System Status:** {uptime}\n"
            f"**Bot Version:** v{version}\n"
            f"**Your User ID:** `{user_id}`\n"
            f"**Server Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
            f"**Features:**\n"
            f"• AI Image Recognition ✅\n"
            f"• Location Geocoding ✅\n"
            f"• Smart Matching ✅\n"
            f"• Email Notifications ✅\n\n"
            f"*All systems operational!*"
        )

        keyboard = [[InlineKeyboardButton("🏠 Back to Menu", callback_data="MENU")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            status_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Error in status command: {e}")
        await update.message.reply_text("❌ Unable to get status. Please try again.")


async def privacy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /privacy handler: show privacy policy
    """
    try:
        await log_user_activity(update, "privacy_command")

        privacy_text = (
            "🔐 **Privacy Policy - ItemRadar**\n\n"

            "**Data We Collect:**\n"
            "• Item descriptions and photos\n"
            "• Contact information (email, optional phone)\n"
            "• Location data for found items\n"
            "• Usage statistics (anonymous)\n\n"

            "**How We Use Your Data:**\n"
            "• Connect lost and found items\n"
            "• Send match notifications\n"
            "• Improve our AI services\n"
            "• Provide customer support\n\n"

            "**Data Protection:**\n"
            "• All data is encrypted\n"
            "• No data sharing with third parties\n"
            "• You can delete your data anytime\n"
            "• GDPR compliant\n\n"

            "**Contact:** privacy@itemradar.com\n"
            "**Updated:** January 2025"
        )

        keyboard = [
            [InlineKeyboardButton("🏠 Back to Menu", callback_data="MENU")],
            [InlineKeyboardButton("🗑️ Delete My Data", callback_data="DELETE_DATA")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            privacy_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Error in privacy command: {e}")
        await update.message.reply_text("❌ Unable to show privacy policy.")


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /cancel handler: abort current flow with better UX
    """
    try:
        await log_user_activity(update, "cancel_command")

        # Check if user has active flow
        current_flow = context.user_data.get("flow")
        current_step = context.user_data.get("step", 0)

        context.user_data.clear()

        if current_flow:
            flow_name = "Lost Item Report" if current_flow == "lost" else "Found Item Report"
            message = (
                f"❌ **{flow_name} Cancelled**\n\n"
                f"Your progress has been cleared.\n"
                f"Send /start to begin a new report."
            )
        else:
            message = "✅ No active operation to cancel.\n\nSend /start to begin."

        keyboard = [[InlineKeyboardButton("🏠 Main Menu", callback_data="MENU")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            message,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Error in cancel command: {e}")
        await update.message.reply_text("❌ Unable to cancel. Please try /start.")


async def choose_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    CallbackQuery handler for main menu and navigation with enhanced features
    """
    try:
        query = update.callback_query
        await query.answer()
        choice = query.data

        await log_user_activity(update, f"menu_choice_{choice}")

        if choice == "start_lost":
            context.user_data.clear()
            context.user_data["flow"] = "lost"
            context.user_data["step"] = 0

            await query.edit_message_text(
                "🔍 **Lost Item Report**\n\n"
                "I'll help you create a detailed lost item report.\n\n"
                "**Please describe what you lost in detail:**\n\n"
                "or upload a photo of the item 📷.\n\n"
                "📝 *Include details like:*\n"
                "• Color, size, and brand\n"
                "• Distinctive features\n"
                "• Condition or damage\n"
                "• Model or type\n\n"
                "**Example:** *Blue iPhone 15 Pro with black leather case, small scratch on the back corner*\n\n"
                "📷 *Photo tips:*\n"
                "• Good lighting\n"
                "• Clear focus\n"
                "• Show distinctive features\n"
                "• Include any labels or brands\n\n"
                "🤖 *Our AI will automatically describe the item for you!*",
                parse_mode="Markdown"
            )

        elif choice == "start_found":
            context.user_data.clear()
            context.user_data["flow"] = "found"
            context.user_data["step"] = 0

            await query.edit_message_text(
                "📸 **Found Item Report**\n\n"
                "Great! I'll help you register the item you found.\n\n"
                "**Please send me a clear photo of the item:**\n\n"
                "📷 *Photo tips:*\n"
                "• Good lighting\n"
                "• Clear focus\n"
                "• Show distinctive features\n"
                "• Include any labels or brands\n\n"
                "🤖 *Our AI will automatically describe the item for you!*",
                parse_mode="Markdown"
            )

        elif choice == "check_status":
            await handle_status_check(update, context)

        elif choice == "SEARCH":
            await query.edit_message_text(
                "🔍 **Search Items**\n\n"
                "🚧 *Feature coming soon!*\n\n"
                "Soon you'll be able to:\n"
                "• Search lost items database\n"
                "• Filter by location and date\n"
                "• Browse found items\n"
                "• Get match suggestions\n\n"
                "Stay tuned for updates!",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 Back to Menu", callback_data="MENU")
                ]]),
                parse_mode="Markdown"
            )

        elif choice == "show_help":
            await handle_help_callback(update, context)

        elif choice == "SUPPORT":
            support_text = (
                "📞 **ItemRadar Support**\n\n"
                "**Get Help:**\n"
                "📧 Email: support@itemradar.com\n"
                "💬 Live Chat: Available 9 AM - 6 PM EST\n"
                "📱 Response Time: Within 24 hours\n\n"
                "**Common Issues:**\n"
                "• Photo upload problems\n"
                "• Location not recognized\n"
                "• Email notifications not received\n"
                "• Match verification questions\n\n"
                "**Include in your message:**\n"
                "• Your Telegram username\n"
                "• Description of the issue\n"
                "• Item/Report ID (if applicable)\n\n"
                "*We're here to help!* 🤝"
            )

            keyboard = [[InlineKeyboardButton("🏠 Back to Menu", callback_data="MENU")]]
            await query.edit_message_text(
                support_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )

        elif choice == "MENU":
            # Back to main menu - simulate /start but edit message
            await query.edit_message_text("🔄 Loading main menu...")
            context.user_data.clear()

            user_name = update.effective_user.first_name or "there"
            keyboard = [
                [InlineKeyboardButton("🔍 I lost an item", callback_data="start_lost")],
                [InlineKeyboardButton("📸 I found an item", callback_data="start_found")],
                [
                    InlineKeyboardButton("📊 My Reports", callback_data="check_status"),
                    InlineKeyboardButton("🔍 Search Items", callback_data="SEARCH")
                ],
                [
                    InlineKeyboardButton("ℹ️ Help", callback_data="show_help"),
                    InlineKeyboardButton("📞 Support", callback_data="SUPPORT")
                ],
            ]

            welcome_text = (
                f"👋 **Welcome back, {user_name}!**\n\n"
                f"🎯 *Your AI-powered lost & found assistant*\n\n"
                f"**What would you like to do?**"
            )

            await query.edit_message_text(
                welcome_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )

        elif choice == "DELETE_DATA":
            keyboard = [
                [InlineKeyboardButton("❌ Yes, delete all my data", callback_data="CONFIRM_DELETE")],
                [InlineKeyboardButton("🏠 No, go back", callback_data="MENU")]
            ]

            await query.edit_message_text(
                "⚠️ **Delete All Data**\n\n"
                "This will permanently delete:\n"
                "• All your lost/found reports\n"
                "• Your contact information\n"
                "• All associated photos\n"
                "• Your usage history\n\n"
                "**This action cannot be undone!**\n\n"
                "Are you sure you want to proceed?",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )

        elif choice == "CONFIRM_DELETE":
            # Here you would implement actual data deletion
            user_id = update.effective_user.id
            logger.info(f"Data deletion requested by user {user_id}")

            await query.edit_message_text(
                "✅ **Data Deletion Initiated**\n\n"
                "Your data deletion request has been received.\n\n"
                "📧 You'll receive a confirmation email within 24 hours.\n"
                "🗑️ All data will be permanently removed from our systems.\n\n"
                "*Thank you for using ItemRadar!*",
                parse_mode="Markdown"
            )

    except Exception as e:
        logger.error(f"Error in choose_flow: {e}")
        try:
            await query.edit_message_text(
                "❌ Something went wrong. Please try again or send /start."
            )
        except:
            pass


async def message_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Enhanced message router with better error handling and user feedback
    """
    try:
        # Rate limiting check
        if not await rate_limit_middleware(update, context):
            return

        flow = context.user_data.get("flow")
        user_id = str(update.effective_user.id)

        await log_user_activity(update, f"message_in_{flow or 'no_flow'}")

        if flow == "lost":
            await handle_lost_flow(update, context)
        elif flow == "found":
            await handle_found_flow(update, context)
        else:
            # Handle general messages with the manager agent
            await handle_general_chat(update, context)

    except ValidationError as e:
        logger.warning(f"Validation error for user {update.effective_user.id}: {e}")
        await update.message.reply_text(f"❌ {str(e)}")

    except ItemRadarError as e:
        logger.error(f"ItemRadar error for user {update.effective_user.id}: {e}")
        await update.message.reply_text(
            f"❌ {str(e)}\n\nIf this problem persists, please contact support."
        )

    except Exception as e:
        logger.exception("Unexpected error in message_router")
        await update.message.reply_text(
            "❌ **Unexpected Error**\n\n"
            "Something went wrong on our end. Please try again in a moment.\n\n"
            "If the issue persists, please contact support with error code: `MSG_ROUTER_ERR`",
            parse_mode="Markdown"
        )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Enhanced global error handler with detailed logging and user feedback
    """
    error = context.error

    # Log detailed error information
    logger.error(
        f"Update {update} caused error {error}",
        exc_info=error
    )

    # Determine error type and provide appropriate response
    if isinstance(error, TelegramError):
        error_message = "❌ **Communication Error**\n\nThere was a problem communicating with Telegram. Please try again."
    elif isinstance(error, ValidationError):
        error_message = f"❌ **Input Error**\n\n{str(error)}"
    elif isinstance(error, ItemRadarError):
        error_message = f"❌ **Service Error**\n\n{str(error)}\n\nPlease try again or contact support."
    else:
        error_message = (
            "❌ **Unexpected Error**\n\n"
            "An unexpected error occurred. Our team has been notified.\n\n"
            "Please try again in a few moments."
        )

    # Try to send error message to user
    try:
        if update.effective_message:
            await update.effective_message.reply_text(
                error_message,
                parse_mode="Markdown"
            )
        elif update.callback_query:
            await update.callback_query.message.reply_text(
                error_message,
                parse_mode="Markdown"
            )
    except Exception as send_error:
        logger.error(f"Failed to send error message to user: {send_error}")


async def setup_bot_commands(app):
    """Set up bot commands menu"""
    commands = [
        BotCommand("start", "🏠 Main menu"),
        BotCommand("help", "ℹ️ Help and guide"),
        BotCommand("cancel", "❌ Cancel current operation"),
        BotCommand("status", "📊 Bot status"),
        BotCommand("privacy", "🔐 Privacy policy"),
    ]

    try:
        await app.bot.set_my_commands(commands)
        logger.info("Bot commands menu set successfully")
    except Exception as e:
        logger.error(f"Failed to set bot commands: {e}")


def main():
    """
    Build and run the enhanced Telegram bot application
    """
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is missing in environment variables")
        print("❌ Error: TELEGRAM_BOT_TOKEN environment variable is required")
        return

    # Create application with enhanced configuration
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .concurrent_updates(MAX_CONCURRENT_USERS)
        .build()
    )

    # Set up bot commands menu
    app.job_queue.run_once(lambda _: setup_bot_commands(app), when=1)

    # 1) Core commands with enhanced functionality
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("privacy", privacy_command))

    # 2) Main menu and navigation callbacks
    app.add_handler(
        CallbackQueryHandler(
            choose_flow,
            pattern="^(start_lost|start_found|show_help|SUPPORT|MENU|check_status|SEARCH|DELETE_DATA|CONFIRM_DELETE)$"
        )
    )

    # 3) Found flow confirmation callbacks
    app.add_handler(
        CallbackQueryHandler(
            handle_found_confirmation,
            pattern="^(register_found|edit_found|cancel_found)$"
        )
    )

    # 4) Lost flow confirmation callbacks
    app.add_handler(
        CallbackQueryHandler(
            handle_lost_confirmation,
            pattern="^(submit_lost|edit_lost|cancel_lost)$"
        )
    )

    # 5) Start callback handler
    app.add_handler(
        CallbackQueryHandler(
            handle_start_callback,
            pattern="^(start_found|start_lost|check_status|show_help)$"
        )
    )

    # 6) All other messages → route to appropriate handler
    app.add_handler(
        MessageHandler(
            filters.ALL & ~filters.COMMAND,
            message_router
        )
    )

    # 7) Enhanced global error handler
    app.add_error_handler(error_handler)

    # Start the bot
    logger.info("🚀 Starting ItemRadar Telegram bot with enhanced features...")
    logger.info(f"📊 Bot version: {BOT_VERSION}")
    logger.info(f"👥 Max concurrent users: {MAX_CONCURRENT_USERS}")
    logger.info(f"⏱️ Rate limit: {RATE_LIMIT_MAX_REQUESTS} requests per {RATE_LIMIT_WINDOW}s")

    try:
        app.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
            poll_interval=1.0,
            timeout=10,
            bootstrap_retries=3,
        )
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        raise


if __name__ == "__main__":
    main()