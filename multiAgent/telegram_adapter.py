# itemradar_ai/telegram_adapter.py

import os
import io
import base64
import logging
from typing import Tuple, Optional, Dict, Any
import json
import traceback
import asyncio
from datetime import datetime

import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from telegram.error import BadRequest, TelegramError
from google.genai import types
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

# Import your ADK agents
from multiAgent.lens_agent.agent import root_agent as lens_agent
from multiAgent.chatbot_manager.agent import root_agent as manager_agent

logger = logging.getLogger(__name__)

# Initialize session service and runners
session_service = InMemorySessionService()
APP_NAME = "itemradar_telegram"

# Create runners for agents
lens_runner = Runner(
    agent=lens_agent,
    app_name=APP_NAME,
    session_service=session_service
)

manager_runner = Runner(
    agent=manager_agent,
    app_name=APP_NAME,
    session_service=session_service
)

# Constants
MAX_RETRIES = 3
TIMEOUT_SECONDS = 30
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
MIN_DESCRIPTION_LENGTH = 10
MAX_DESCRIPTION_LENGTH = 1000


class ItemRadarError(Exception):
    """Custom exception for ItemRadar operations"""
    pass


class ValidationError(ItemRadarError):
    """Validation error for user input"""
    pass


async def download_photo(file_id: str, context: ContextTypes.DEFAULT_TYPE) -> bytes:
    """
    Download a Telegram photo file into memory and return its bytes.
    Includes size validation and error handling.
    """
    try:
        file = await context.bot.get_file(file_id)

        if file.file_size and file.file_size > MAX_IMAGE_SIZE:
            raise ValidationError(f"Image too large. Maximum size is {MAX_IMAGE_SIZE // (1024 * 1024)}MB")

        bio = io.BytesIO()
        await file.download_to_memory(out=bio)
        image_bytes = bio.getvalue()

        if len(image_bytes) > MAX_IMAGE_SIZE:
            raise ValidationError(f"Image too large. Maximum size is {MAX_IMAGE_SIZE // (1024 * 1024)}MB")

        logger.info(f"Successfully downloaded photo {file_id}, size: {len(image_bytes)} bytes")
        return image_bytes

    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"Failed to download photo {file_id}: {e}")
        raise ItemRadarError(f"Failed to download image: {str(e)}")


def validate_email(email: str) -> bool:
    """Basic email validation"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email.strip()))


def _split_email_location(text: str) -> Optional[Tuple[str, str]]:
    """
    Parse "email, location" from user message with improved validation.
    Returns (email, location) or None.
    """
    if not text or "@" not in text:
        return None

    parts = text.split(",", 1)
    if len(parts) != 2:
        return None

    email = parts[0].strip()
    location = parts[1].strip()

    if not validate_email(email):
        return None

    if len(location) < 3:
        return None

    return (email, location)


async def run_agent_with_timeout(runner: Runner, user_id: str, message: str,
                                 image_bytes: bytes = None, timeout: int = TIMEOUT_SECONDS) -> str:
    """
    Run an ADK agent with timeout protection.
    """
    try:
        return await asyncio.wait_for(
            run_agent_with_message(runner, user_id, message, image_bytes),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        logger.error(f"Agent timeout for user {user_id}")
        raise ItemRadarError("Request timed out. Please try again.")


async def run_agent_with_message(runner: Runner, user_id: str, message: str, image_bytes: bytes = None) -> str:
    """
    Run an ADK agent with a message and optional image, return the final response.
    Enhanced with better error handling and logging.
    """
    session_id = f"{user_id}_session"

    try:
        # Create or get session with retry logic
        for attempt in range(MAX_RETRIES):
            try:
                await session_service.create_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)
                logger.info(f"Created session: {session_id} (attempt {attempt + 1})")
                break
            except Exception as e:
                if attempt == MAX_RETRIES - 1:
                    raise ItemRadarError(f"Failed to create session after {MAX_RETRIES} attempts")
                logger.warning(f"Session creation attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(1)

        # Verify session exists
        session = await session_service.get_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)
        if not session:
            raise ItemRadarError("Failed to retrieve session")

        logger.info(f"Session retrieved successfully: {session_id}")

        # Prepare message parts
        parts = [types.Part(text=message)]

        # Add image if provided
        if image_bytes:
            image_b64 = base64.b64encode(image_bytes).decode('utf-8')
            parts.append(types.Part(
                inline_data=types.Blob(
                    mime_type="image/jpeg",
                    data=image_b64
                )
            ))
            logger.info(f"Added image to message, size: {len(image_bytes)} bytes")

        user_content = types.Content(role='user', parts=parts)

        # Run the agent and collect the final response
        final_response = ""
        response_received = False

        async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=user_content
        ):
            if event.is_final_response() and event.content and event.content.parts:
                final_response = event.content.parts[0].text
                response_received = True
                break

        if not response_received or not final_response.strip():
            raise ItemRadarError("No valid response received from agent")

        logger.info(f"Agent response received for user {user_id}, length: {len(final_response)}")
        return final_response.strip()

    except ItemRadarError:
        raise
    except Exception as e:
        logger.error(f"Failed to run agent for user {user_id}: {e}")
        logger.error(traceback.format_exc())
        raise ItemRadarError(f"Agent execution failed: {str(e)}")


def escape_markdown(text: str) -> str:
    """
    Escape special characters for Telegram MarkdownV2.
    """
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    return text


async def safe_send_message(update: Update, text: str, reply_markup=None, parse_mode=None, max_length=4096):
    """
    Safely send a message with error handling for parse mode issues and length limits.
    """
    if len(text) > max_length:
        text = text[:max_length - 50] + "...\n\n[Message truncated]"

    try:
        if parse_mode == "Markdown":
            escaped_text = escape_markdown(text)
            await update.message.reply_text(escaped_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2)
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except BadRequest as e:
        logger.warning(f"Markdown parsing failed, sending as plain text: {e}")
        try:
            await update.message.reply_text(text, reply_markup=reply_markup)
        except TelegramError as te:
            logger.error(f"Failed to send message even as plain text: {te}")
            await update.message.reply_text("❌ Unable to send response. Please try again.")


async def safe_edit_message(update: Update, text: str, reply_markup=None, parse_mode=None, max_length=4096):
    """
    Safely edit a message with error handling and length limits.
    """
    if len(text) > max_length:
        text = text[:max_length - 50] + "...\n\n[Message truncated]"

    try:
        if parse_mode == "Markdown":
            escaped_text = escape_markdown(text)
            await update.callback_query.edit_message_text(
                escaped_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN_V2
            )
        else:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except BadRequest as e:
        logger.warning(f"Message editing failed: {e}")
        try:
            await update.callback_query.message.reply_text(text, reply_markup=reply_markup)
        except TelegramError as fallback_e:
            logger.error(f"Fallback message send also failed: {fallback_e}")
            await update.callback_query.message.reply_text("❌ Unable to update message. Please try again.")


def generate_item_id(prefix: str, *args) -> str:
    """Generate a unique item ID"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    hash_input = "".join(str(arg) for arg in args) + timestamp
    hash_value = str(abs(hash(hash_input)))[:8]
    return f"{prefix}_{timestamp}_{hash_value}"


# ─── FOUND ITEM FLOW (Using Lens Agent) ────────────────────────────────

async def handle_found_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Workflow for reporting a FOUND item using the lens agent for image analysis
    and the manager agent for registration and processing.
    """
    try:
        step = context.user_data.get("step", 0)
        user_id = str(update.effective_user.id)

        # Step 0: Receive and process photo with lens agent
        if step == 0:
            if not update.message.photo:
                await update.message.reply_text(
                    "📷 **Found Item Registration**\n\n"
                    "Please send me a photo of the item you found.\n\n"
                    "💡 *Make sure the photo is clear and shows the item details.*"
                )
                return

            processing_msg = await update.message.reply_text("🔍 Analyzing your image with AI...")

            try:
                # Download image
                file_id = update.message.photo[-1].file_id
                img_bytes = await download_photo(file_id, context)

                # Use lens agent to analyze the found item
                lens_prompt = """
                Analyze this image of a found item and provide:
                1. A detailed description including color, brand, condition, size
                2. Any distinctive features or markings
                3. Estimated value category (low/medium/high)
                4. Suggested keywords for matching

                Format your response as a clear, detailed description that would help someone identify if this is their lost item.
                """

                description = await run_agent_with_timeout(
                    lens_runner,
                    user_id,
                    lens_prompt,
                    img_bytes
                )

                await processing_msg.delete()

            except ValidationError as e:
                await processing_msg.edit_text(f"❌ {str(e)}")
                return
            except ItemRadarError as e:
                await processing_msg.edit_text(
                    f"❌ {str(e)}\n\nPlease try again or describe the item manually."
                )
                return
            except Exception as e:
                logger.error("Lens agent failed: %s", e)
                await processing_msg.edit_text(
                    "⚠️ I couldn't automatically analyze the image. "
                    "Please describe the item in your own words in the next message."
                )
                description = "MANUAL_DESCRIPTION_REQUIRED"

            # Store description and advance
            context.user_data["description"] = description
            context.user_data["step"] = 1

            if description != "MANUAL_DESCRIPTION_REQUIRED":
                text = (
                    f"🖼️ **AI Analysis Complete**\n\n"
                    f"**Item Description:**\n{description}\n\n"
                    f"📧 **Next Step:** Please provide your contact email and the location where you found this item.\n\n"
                    f"**Format:** your.email@example.com, Central Park near the fountain"
                )
            else:
                text = (
                    "📝 **Manual Description Required**\n\n"
                    "Please describe the item you found in detail, including:\n"
                    "• Color and size\n"
                    "• Brand or distinctive features\n"
                    "• Condition\n"
                    "• Any text or markings"
                )

            await update.message.reply_text(text, parse_mode="Markdown")
            return

        # Step 1: Handle manual description or email/location
        if step == 1:
            text = (update.message.text or "").strip()

            # Check if we need manual description
            if context.user_data.get("description") == "MANUAL_DESCRIPTION_REQUIRED":
                if len(text) < MIN_DESCRIPTION_LENGTH:
                    await update.message.reply_text(
                        f"❌ Please provide a more detailed description (at least {MIN_DESCRIPTION_LENGTH} characters)."
                    )
                    return

                context.user_data["description"] = text
                await update.message.reply_text(
                    "📧 **Contact Information**\n\n"
                    "Please provide your email and the location where you found the item.\n\n"
                    "**Format:** your.email@example.com, Central Park near the fountain",
                    parse_mode="Markdown"
                )
                return

            # Parse email and location
            parsed = _split_email_location(text)
            if not parsed:
                await update.message.reply_text(
                    "❌ **Invalid Format**\n\n"
                    "Please use: **your.email@example.com, Location Name**\n\n"
                    "Make sure to:\n"
                    "• Include a valid email address\n"
                    "• Separate email and location with a comma\n"
                    "• Be specific about the location",
                    parse_mode="Markdown"
                )
                return

            email, location = parsed
            context.user_data["email"] = email
            context.user_data["location"] = location
            context.user_data["step"] = 2

            # Show confirmation
            desc = context.user_data["description"]

            summary = (
                f"📋 **Found Item Summary**\n\n"
                f"**Item:** {desc[:200]}{'...' if len(desc) > 200 else ''}\n\n"
                f"**Email:** {email}\n"
                f"**Location:** {location}\n\n"
                f"Ready to register this found item?"
            )

            keyboard = [
                [InlineKeyboardButton("✅ Register Found Item", callback_data="register_found")],
                [InlineKeyboardButton("✏️ Edit Details", callback_data="edit_found")],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel_found")],
            ]

            await update.message.reply_text(
                summary,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
            return

        # Fallback
        context.user_data.clear()
        await update.message.reply_text("❌ Something went wrong. Please send /start to begin again.")

    except Exception as e:
        logger.error(f"Error in handle_found_flow: {e}")
        logger.error(traceback.format_exc())
        await update.message.reply_text(
            "❌ An unexpected error occurred. Please try again or send /start to restart."
        )
        context.user_data.clear()


async def handle_found_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle found item confirmation using manager agent for registration.
    """
    try:
        await update.callback_query.answer()
        choice = update.callback_query.data
        user_id = str(update.effective_user.id)

        if choice == "register_found":
            desc = context.user_data.get("description", "")
            email = context.user_data.get("email", "")
            location = context.user_data.get("location", "")

            await update.callback_query.edit_message_text("🔄 Registering found item...")

            try:
                # Generate item ID
                item_id = generate_item_id("FOUND", desc, email, location)

                # Use manager agent to register the found item
                registration_data = {
                    "action": "register_found_item",
                    "item_id": item_id,
                    "description": desc,
                    "finder_email": email,
                    "found_location": location,
                    "timestamp": datetime.now().isoformat(),
                    "user_id": user_id
                }

                manager_prompt = f"""
                REGISTER_FOUND_ITEM:
                {json.dumps(registration_data, indent=2)}

                Please register this found item in the system and check for any potential matches with lost items.
                Provide confirmation of registration and any immediate matches found.
                """

                response = await run_agent_with_timeout(
                    manager_runner,
                    user_id,
                    manager_prompt
                )

                success_text = (
                    f"✅ **Found Item Registered Successfully!**\n\n"
                    f"📋 **Item ID:** `{item_id}`\n"
                    f"📧 **Contact:** {email}\n"
                    f"📍 **Location:** {location}\n"
                    f"📅 **Registered:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                    f"🤖 **System Response:**\n{response}\n\n"
                    f"💡 *We'll notify you if someone reports a matching lost item.*"
                )

                await safe_edit_message(update, success_text, parse_mode="Markdown")

            except Exception as e:
                logger.error(f"Found item registration failed: {e}")
                error_text = (
                    f"❌ **Registration Failed**\n\n"
                    f"Error: {str(e)}\n\n"
                    f"Please try again later."
                )
                await safe_edit_message(update, error_text, parse_mode="Markdown")
            finally:
                context.user_data.clear()

        elif choice == "edit_found":
            context.user_data["step"] = 0
            await safe_edit_message(
                update,
                "✏️ **Edit Found Item**\n\n"
                "Please send a new photo of the item you found:",
                parse_mode="Markdown"
            )

        else:  # cancel_found
            context.user_data.clear()
            await safe_edit_message(
                update,
                "❌ **Registration cancelled.**\n\n"
                "Send /start if you want to register an item.",
                parse_mode="Markdown"
            )

    except Exception as e:
        logger.error(f"Error in handle_found_confirmation: {e}")
        try:
            await update.callback_query.edit_message_text(
                "❌ An error occurred. Please send /start to restart."
            )
        except:
            pass
        context.user_data.clear()


# ─── LOST ITEM FLOW (Using Manager Agent) ──────────────────────────────

async def handle_lost_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Workflow for reporting a LOST item using the manager agent for processing and matching.
    """
    try:
        step = context.user_data.get("step", 0)
        text = (update.message.text or "").strip()
        user_id = str(update.effective_user.id)

        # Step 0: Item description
        if step == 0:
            if len(text) < MIN_DESCRIPTION_LENGTH:
                await update.message.reply_text(
                    f"📝 **Lost Item Report**\n\n"
                    f"Please provide a detailed description of what you lost (at least {MIN_DESCRIPTION_LENGTH} characters).\n\n"
                    f"**Include:**\n"
                    f"• Color, size, brand\n"
                    f"• Distinctive features\n"
                    f"• Model or type\n"
                    f"• Condition\n\n"
                    f"**Example:** Blue iPhone 15 Pro with black leather case, small scratch on back corner",
                    parse_mode="Markdown"
                )
                return

            if len(text) > MAX_DESCRIPTION_LENGTH:
                await update.message.reply_text(
                    f"❌ Description too long. Please keep it under {MAX_DESCRIPTION_LENGTH} characters."
                )
                return

            context.user_data["description"] = text
            context.user_data["step"] = 1

            # Use manager agent to analyze the description and suggest categories
            analysis_prompt = f"""
            Analyze this lost item description and provide:
            1. Item category classification
            2. Key identifying features
            3. Suggested search keywords
            4. Questions to help narrow down the search

            Description: {text}

            Provide a helpful response to guide the user for better reporting.
            """

            try:
                analysis = await run_agent_with_timeout(
                    manager_runner,
                    user_id,
                    analysis_prompt
                )

                response_text = (
                    f"📊 **Item Analysis Complete**\n\n"
                    f"{analysis}\n\n"
                    f"📍 **Next Step:** Please tell me where and when you lost this item."
                )
            except Exception as e:
                logger.warning(f"Analysis failed: {e}")
                response_text = "📍 **Where and when did you lose this item?**\n\nPlease be as specific as possible about the location and time."

            await update.message.reply_text(response_text, parse_mode="Markdown")
            return

        # Step 1: Location and time
        if step == 1:
            if len(text) < 10:
                await update.message.reply_text(
                    "❌ Please provide more details about where and when you lost the item.\n\n"
                    "**Example:** Central Park near the playground, yesterday around 3 PM"
                )
                return

            context.user_data["location_time"] = text
            context.user_data["step"] = 2
            await update.message.reply_text(
                "📧 **Contact Information**\n\n"
                "Please provide your email address (and optionally phone number):\n\n"
                "**Examples:**\n"
                "• john@example.com\n"
                "• john@example.com, +1-555-1234",
                parse_mode="Markdown"
            )
            return

        # Step 2: Contact information
        if step == 2:
            email_part = text.split(',')[0].strip()
            if not validate_email(email_part):
                await update.message.reply_text(
                    "❌ Please provide a valid email address.\n\n"
                    "**Format:** your.email@example.com"
                )
                return

            context.user_data["contact"] = text
            context.user_data["step"] = 3

            # Show summary and immediate search using manager agent
            desc = context.user_data["description"]
            loc_time = context.user_data["location_time"]
            contact = context.user_data["contact"]

            # Show processing message
            processing_msg = await update.message.reply_text("🔍 Searching for potential matches...")

            # Use manager agent to search for matches
            search_prompt = f"""
            Search for potential matches for this lost item:

            Description: {desc}
            Location/Time: {loc_time}
            Contact: {contact}

            Please search the found items database and provide:
            1. Any potential matches
            2. Similarity scores
            3. Recommendations for the user
            4. Next steps
            """

            try:
                search_results = await run_agent_with_timeout(
                    manager_runner,
                    user_id,
                    search_prompt
                )
                await processing_msg.delete()
            except Exception as e:
                logger.warning(f"Initial search failed: {e}")
                search_results = "Initial search completed. We'll continue monitoring for matches."
                await processing_msg.delete()

            summary = (
                f"📋 **Lost Item Report Summary**\n\n"
                f"🔍 **Item:** {desc}\n\n"
                f"📍 **Where/When:** {loc_time}\n\n"
                f"📧 **Contact:** {contact}\n\n"
                f"🔍 **Search Results:**\n{search_results}\n\n"
                f"❓ **Ready to submit this report?**"
            )

            keyboard = [
                [InlineKeyboardButton("✅ Submit Report", callback_data="submit_lost")],
                [InlineKeyboardButton("✏️ Edit Details", callback_data="edit_lost")],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel_lost")],
            ]

            await update.message.reply_text(
                summary,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
            return

        # Fallback
        context.user_data.clear()
        await update.message.reply_text("❌ Something went wrong. Please send /start to restart.")

    except Exception as e:
        logger.error(f"Error in handle_lost_flow: {e}")
        logger.error(traceback.format_exc())
        await update.message.reply_text(
            "❌ An unexpected error occurred. Please try again or send /start to restart."
        )
        context.user_data.clear()


async def handle_lost_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle lost item confirmation using manager agent for registration and ongoing monitoring.
    """
    try:
        await update.callback_query.answer()
        choice = update.callback_query.data
        user_id = str(update.effective_user.id)

        if choice == "submit_lost":
            desc = context.user_data.get("description", "")
            loc_time = context.user_data.get("location_time", "")
            contact = context.user_data.get("contact", "")

            await update.callback_query.edit_message_text("🔄 Submitting lost item report...")

            try:
                # Generate report ID
                report_id = generate_item_id("LOST", desc, loc_time, contact)

                # Use manager agent to register the lost item
                registration_data = {
                    "action": "register_lost_item",
                    "report_id": report_id,
                    "description": desc,
                    "location_time": loc_time,
                    "contact": contact,
                    "timestamp": datetime.now().isoformat(),
                    "user_id": user_id
                }

                manager_prompt = f"""
                REGISTER_LOST_ITEM:
                {json.dumps(registration_data, indent=2)}

                Please:
                1. Register this lost item in the system
                2. Set up monitoring for future found items
                3. Continue searching for existing matches
                4. Provide confirmation and next steps for the user
                """

                response = await run_agent_with_timeout(
                    manager_runner,
                    user_id,
                    manager_prompt
                )

                success_text = (
                    f"✅ **Lost Item Report Submitted!**\n\n"
                    f"📋 **Report ID:** `{report_id}`\n"
                    f"📅 **Submitted:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                    f"🤖 **System Response:**\n{response}\n\n"
                    f"💡 *We'll notify you immediately if someone reports finding a matching item. "
                    f"Save your Report ID for reference.*"
                )

                await safe_edit_message(update, success_text, parse_mode="Markdown")

            except Exception as e:
                logger.error(f"Lost item registration failed: {e}")
                error_text = (
                    f"❌ **Submission Failed**\n\n"
                    f"Error: {str(e)}\n\n"
                    f"Please try again later."
                )
                await safe_edit_message(update, error_text, parse_mode="Markdown")
            finally:
                context.user_data.clear()

        elif choice == "edit_lost":
            context.user_data["step"] = 0
            await safe_edit_message(
                update,
                "✏️ **Edit Lost Item Report**\n\n"
                "Please describe what you lost in detail:",
                parse_mode="Markdown"
            )

        else:  # cancel_lost
            context.user_data.clear()
            await safe_edit_message(
                update,
                "❌ **Lost report cancelled.**\n\n"
                "Send /start if you want to create a new report.",
                parse_mode="Markdown"
            )

    except Exception as e:
        logger.error(f"Error in handle_lost_confirmation: {e}")
        try:
            await update.callback_query.edit_message_text(
                "❌ An error occurred. Please send /start to restart."
            )
        except:
            pass
        context.user_data.clear()


# ─── GENERAL CHAT HANDLER (Using Manager Agent) ────────────────────────

async def handle_general_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle general questions and queries using the manager agent.
    """
    try:
        user_id = str(update.effective_user.id)
        message = update.message.text or ""

        # Show typing indicator
        await update.message.chat.send_action("typing")

        # Use manager agent for general queries
        general_prompt = f"""
        User Query: {message}

        This is a general question about ItemRadar lost and found service. Please provide helpful information about:
        - How the service works
        - Features available
        - Status of items
        - General support

        Be helpful, concise, and guide users to appropriate actions if needed.
        """

        try:
            response = await run_agent_with_timeout(
                manager_runner,
                user_id,
                general_prompt
            )

            await safe_send_message(update, response, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"General chat failed: {e}")
            fallback_response = (
                "I'm here to help with lost and found items! 📱\n\n"
                "• Send /start to report a found or lost item\n"
                "• Send /help for more information\n"
                "• Send /status to check your reports\n\n"
                "What would you like to do?"
            )
            await update.message.reply_text(fallback_response)

    except Exception as e:
        logger.error(f"Error in handle_general_chat: {e}")
        await update.message.reply_text(
            "❌ Sorry, I'm having trouble right now. Please try /start to begin."
        )


# ─── ADDITIONAL COMMAND HANDLERS ────────────────────────────────────────

async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /start command - main menu.
    """
    try:
        context.user_data.clear()  # Clear any existing workflow state

        user_name = update.effective_user.first_name or "there"

        welcome_text = (
            f"👋 **Welcome to ItemRadar, {user_name}!**\n\n"
            f"🔍 Your AI-powered lost and found assistant\n\n"
            f"**What would you like to do?**"
        )

        keyboard = [
            [InlineKeyboardButton("📷 I Found Something", callback_data="start_found")],
            [InlineKeyboardButton("🔍 I Lost Something", callback_data="start_lost")],
            [InlineKeyboardButton("📊 Check My Reports", callback_data="check_status")],
            [InlineKeyboardButton("❓ Help", callback_data="show_help")],
        ]

        await update.message.reply_text(
            welcome_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Error in handle_start: {e}")
        await update.message.reply_text("❌ Something went wrong. Please try again.")


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /help command.
    """
    help_text = (
        "❓ **ItemRadar Help**\n\n"
        "**🔍 How It Works:**\n"
        "• Report found items with photos\n"
        "• Report lost items with descriptions\n"
        "• AI matches items automatically\n"
        "• Get notified when matches are found\n\n"
        "**📱 Commands:**\n"
        "• `/start` - Main menu\n"
        "• `/help` - This help message\n"
        "• `/status` - Check your reports\n"
        "• `/cancel` - Cancel current operation\n\n"
        "**💡 Tips:**\n"
        "• Use clear, well-lit photos\n"
        "• Include detailed descriptions\n"
        "• Be specific about locations\n"
        "• Provide accurate contact info\n\n"
        "**🛠️ Support:**\n"
        "For assistance, contact @itemradar_support"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def handle_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel any ongoing operation"""
    context.user_data.clear()
    await update.message.reply_text(
        "🛑 All operations cancelled.\n\n"
        "Send /start to begin a new action."
    )


async def handle_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check status of user reports"""
    try:
        user_id = str(update.effective_user.id)
        processing_msg = await update.message.reply_text("🔍 Retrieving your reports...")

        # Use manager agent to get status
        status_prompt = f"""
        USER_STATUS_REQUEST:
        user_id: {user_id}

        Please provide a summary of all lost and found reports for this user, including:
        - Report IDs and types (lost/found)
        - Brief descriptions
        - Current status (open, matched, closed)
        - Timestamps

        Format the response clearly for the user.
        """

        try:
            status_report = await run_agent_with_timeout(
                manager_runner,
                user_id,
                status_prompt
            )
            await processing_msg.delete()
            response = (
                f"📊 **Your ItemRadar Reports**\n\n"
                f"{status_report}\n\n"
                f"💡 *Use your Report ID to check for updates*"
            )
        except Exception as e:
            logger.error(f"Status check failed: {e}")
            await processing_msg.delete()
            response = (
                "❌ Could not retrieve reports at this time.\n\n"
                "Please try again later or contact support."
            )

        await update.message.reply_text(response, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error in handle_status: {e}")
        await update.message.reply_text(
            "❌ An error occurred while fetching your reports. Please try again."
        )


async def handle_help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle help button press"""
    try:
        await update.callback_query.answer()
        await safe_edit_message(
            update,
            "❓ **ItemRadar Help**\n\n"
            "**🔍 How It Works:**\n"
            "• Report found items with photos\n"
            "• Report lost items with descriptions\n"
            "• AI matches items automatically\n"
            "• Get notified when matches are found\n\n"
            "**📱 Commands:**\n"
            "• `/start` - Main menu\n"
            "• `/help` - This help message\n"
            "• `/status` - Check your reports\n"
            "• `/cancel` - Cancel current operation\n\n"
            "**💡 Tips:**\n"
            "• Use clear, well-lit photos\n"
            "• Include detailed descriptions\n"
            "• Be specific about locations\n"
            "• Provide accurate contact info\n\n"
            "**🛠️ Support:**\n"
            "For assistance, contact @itemradar_support",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error in handle_help_callback: {e}")
        await update.callback_query.edit_message_text("❌ Couldn't show help. Please try /help")


async def handle_status_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle status check button press"""
    try:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("🔍 Retrieving your reports...")

        user_id = str(update.effective_user.id)

        # Use manager agent to get status
        status_prompt = f"""
        USER_STATUS_REQUEST:
        user_id: {user_id}

        Please provide a summary of all lost and found reports for this user, including:
        - Report IDs and types (lost/found)
        - Brief descriptions
        - Current status (open, matched, closed)
        - Timestamps

        Format the response clearly for the user.
        """

        try:
            status_report = await run_agent_with_timeout(
                manager_runner,
                user_id,
                status_prompt
            )
            response = (
                f"📊 **Your ItemRadar Reports**\n\n"
                f"{status_report}\n\n"
                f"💡 *Use your Report ID to check for updates*"
            )
        except Exception as e:
            logger.error(f"Status check failed: {e}")
            response = (
                "❌ Could not retrieve reports at this time.\n\n"
                "Please try again later or contact support."
            )

        await safe_edit_message(update, response, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error in handle_status_check: {e}")
        await update.callback_query.edit_message_text("❌ Couldn't retrieve reports. Please try /status")


async def handle_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle start menu callbacks.
    """
    try:
        await update.callback_query.answer()
        choice = update.callback_query.data

        if choice == "start_found":
            context.user_data.clear()
            context.user_data["step"] = 0
            context.user_data["flow"] = "found"

            await safe_edit_message(
                update,
                "📷 **Found Item Registration**\n\n"
                "Great! You found something. Let's help reunite it with its owner.\n\n"
                "Please send me a clear photo of the item you found.",
                parse_mode="Markdown"
            )

        elif choice == "start_lost":
            context.user_data.clear()
            context.user_data["step"] = 0
            context.user_data["flow"] = "lost"

            await safe_edit_message(
                update,
                "🔍 **Lost Item Report**\n\n"
                "I'm sorry you lost something. Let's help you find it!\n\n"
                "Please describe what you lost in detail (color, brand, size, distinctive features, etc.):",
                parse_mode="Markdown"
            )

        elif choice == "check_status":
            await handle_status_check(update, context)

        elif choice == "show_help":
            await handle_help_callback(update, context)

    except Exception as e:
        logger.error(f"Error in handle_start_callback: {e}")
        try:
            await update.callback_query.edit_message_text("❌ An error occurred. Please send /start to restart.")
        except:
            pass