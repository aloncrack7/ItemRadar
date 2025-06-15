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
from itemradar_ai.lens_agent.agent import root_agent as lens_agent
from itemradar_ai.chatbot_agent.agent import root_agent as lost_agent
from itemradar_ai.registration_agent.agent import registration_agent

logger = logging.getLogger(__name__)

# Initialize session service and runners
session_service = InMemorySessionService()
APP_NAME = "itemradar_telegram"

# Create runners for your agents
lens_runner = Runner(
    agent=lens_agent,
    app_name=APP_NAME,
    session_service=session_service
)

lost_runner = Runner(
    agent=lost_agent,
    app_name=APP_NAME,
    session_service=session_service
)

# Registration agent runner with proper configuration
registration_runner = Runner(
    agent=registration_agent,
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


class RegistrationError(ItemRadarError):
    """Registration-specific error"""
    pass


async def download_photo(file_id: str, context: ContextTypes.DEFAULT_TYPE) -> bytes:
    """
    Download a Telegram photo file into memory and return its bytes.
    Includes size validation and error handling.
    """
    try:
        # Get the File object
        file = await context.bot.get_file(file_id)

        # Check file size
        if file.file_size and file.file_size > MAX_IMAGE_SIZE:
            raise ValidationError(f"Image too large. Maximum size is {MAX_IMAGE_SIZE // (1024 * 1024)}MB")

        bio = io.BytesIO()
        await file.download_to_memory(out=bio)
        image_bytes = bio.getvalue()

        # Additional size check after download
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

    # Validate email format
    if not validate_email(email):
        return None

    # Validate location (minimum length)
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
                await asyncio.sleep(1)  # Brief delay before retry

        # Verify session exists
        session = await session_service.get_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)
        if not session:
            raise ItemRadarError("Failed to retrieve session")

        logger.info(f"Session retrieved successfully: {session_id}")

        # Prepare message parts
        parts = [types.Part(text=message)]

        # Add image if provided
        if image_bytes:
            # Convert image bytes to base64
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


async def register_found_item(user_id: str, item_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Register a found item using the registration agent with proper error handling.

    Args:
        user_id: Telegram user ID
        item_data: Dictionary containing item details

    Returns:
        Dictionary with registration result
    """
    try:
        # Create a structured registration message
        registration_message = {
            "action": "register_found_item",
            "item_id": item_data.get("item_id"),
            "description": item_data.get("description"),
            "email": item_data.get("email"),
            "location": item_data.get("location"),
            "timestamp": item_data.get("timestamp", datetime.now().isoformat()),
            "user_id": user_id
        }

        # Convert to JSON string for the agent
        message_text = f"REGISTER_FOUND_ITEM: {json.dumps(registration_message, indent=2)}"

        logger.info(f"Registering found item for user {user_id}: {item_data.get('item_id')}")

        # Use a dedicated session for registration
        session_id = f"{user_id}_registration_{item_data.get('item_id')}"

        # Create session
        await session_service.create_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id
        )

        # Prepare the message
        user_content = types.Content(
            role='user',
            parts=[types.Part(text=message_text)]
        )

        # Run the registration agent
        registration_response = ""
        async for event in registration_runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=user_content
        ):
            if event.is_final_response() and event.content and event.content.parts:
                registration_response = event.content.parts[0].text
                break

        if not registration_response:
            raise RegistrationError("No response from registration agent")

        # Try to parse the response as JSON
        try:
            result = json.loads(registration_response)
            if not isinstance(result, dict):
                raise ValueError("Response is not a dictionary")
        except (json.JSONDecodeError, ValueError):
            # If not JSON, create a structured response
            result = {
                "success": "success" in registration_response.lower() and "error" not in registration_response.lower(),
                "message": registration_response,
                "item_id": item_data.get("item_id"),
                "timestamp": datetime.now().isoformat()
            }

        logger.info(f"Registration completed for item {item_data.get('item_id')}: {result.get('success', False)}")
        return result

    except Exception as e:
        logger.error(f"Registration failed for user {user_id}: {e}")
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": str(e),
            "item_id": item_data.get("item_id"),
            "timestamp": datetime.now().isoformat()
        }


async def register_lost_item(user_id: str, item_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Register a lost item using the registration agent with proper error handling.

    Args:
        user_id: Telegram user ID
        item_data: Dictionary containing item details

    Returns:
        Dictionary with registration result
    """
    try:
        # Create a structured registration message
        registration_message = {
            "action": "register_lost_item",
            "report_id": item_data.get("report_id"),
            "description": item_data.get("description"),
            "location_time": item_data.get("location_time"),
            "contact": item_data.get("contact"),
            "timestamp": item_data.get("timestamp", datetime.now().isoformat()),
            "user_id": user_id
        }

        # Convert to JSON string for the agent
        message_text = f"REGISTER_LOST_ITEM: {json.dumps(registration_message, indent=2)}"

        logger.info(f"Registering lost item for user {user_id}: {item_data.get('report_id')}")

        # Use a dedicated session for registration
        session_id = f"{user_id}_lost_registration_{item_data.get('report_id')}"

        # Create session
        await session_service.create_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id
        )

        # Prepare the message
        user_content = types.Content(
            role='user',
            parts=[types.Part(text=message_text)]
        )

        # Run the registration agent
        registration_response = ""
        async for event in registration_runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=user_content
        ):
            if event.is_final_response() and event.content and event.content.parts:
                registration_response = event.content.parts[0].text
                break

        if not registration_response:
            raise RegistrationError("No response from registration agent")

        # Try to parse the response as JSON
        try:
            result = json.loads(registration_response)
            if not isinstance(result, dict):
                raise ValueError("Response is not a dictionary")
        except (json.JSONDecodeError, ValueError):
            # If not JSON, create a structured response
            result = {
                "success": "success" in registration_response.lower() and "error" not in registration_response.lower(),
                "message": registration_response,
                "report_id": item_data.get("report_id"),
                "timestamp": datetime.now().isoformat()
            }

        logger.info(
            f"Lost item registration completed for {item_data.get('report_id')}: {result.get('success', False)}")
        return result

    except Exception as e:
        logger.error(f"Lost item registration failed for user {user_id}: {e}")
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": str(e),
            "report_id": item_data.get("report_id"),
            "timestamp": datetime.now().isoformat()
        }


def escape_markdown(text: str) -> str:
    """
    Escape special characters for Telegram MarkdownV2.
    """
    # Characters that need escaping in MarkdownV2
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    return text


async def safe_send_message(update: Update, text: str, reply_markup=None, parse_mode=None, max_length=4096):
    """
    Safely send a message with error handling for parse mode issues and length limits.
    """
    # Truncate message if too long
    if len(text) > max_length:
        text = text[:max_length - 50] + "...\n\n[Message truncated]"

    try:
        if parse_mode == "Markdown":
            # Try MarkdownV2 first
            escaped_text = escape_markdown(text)
            await update.message.reply_text(escaped_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2)
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except BadRequest as e:
        logger.warning(f"Markdown parsing failed, sending as plain text: {e}")
        # Fall back to plain text
        try:
            await update.message.reply_text(text, reply_markup=reply_markup)
        except TelegramError as te:
            logger.error(f"Failed to send message even as plain text: {te}")
            # Final fallback - send error message
            await update.message.reply_text("❌ Unable to send response. Please try again.")


async def safe_edit_message(update: Update, text: str, reply_markup=None, parse_mode=None, max_length=4096):
    """
    Safely edit a message with error handling and length limits.
    """
    # Truncate message if too long
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
        # Try to send a new message instead
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


# ─── FOUND flow ─────────────────────────────────────────────────────────

async def handle_found_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Workflow for reporting a FOUND item with enhanced error handling and validation.
    """
    try:
        step = context.user_data.get("step", 0)
        user_id = str(update.effective_user.id)

        # 0) receive photo
        if step == 0:
            if not update.message.photo:
                await update.message.reply_text(
                    "❌ Please send me a photo of the item you found.\n\n"
                    "📷 Make sure the photo is clear and shows the item details."
                )
                return

            # Show processing message
            processing_msg = await update.message.reply_text("🔄 Processing your image...")

            try:
                # Download image bytes
                file_id = update.message.photo[-1].file_id
                img_bytes = await download_photo(file_id, context)

                # Run the lens_agent with an image
                description = await run_agent_with_timeout(
                    lens_runner,
                    user_id,
                    "Please describe this item that was found. Provide a clear, detailed description including color, brand, condition, and any distinctive features.",
                    img_bytes
                )

                # Delete processing message
                try:
                    await processing_msg.delete()
                except:
                    pass

            except ValidationError as e:
                await processing_msg.edit_text(f"❌ {str(e)}")
                return
            except ItemRadarError as e:
                await processing_msg.edit_text(
                    f"❌ {str(e)}\n\nPlease try again or describe the item manually."
                )
                return
            except Exception as e:
                logger.error("LensAgent failed: %s", e)
                await processing_msg.edit_text(
                    "⚠️ I couldn't automatically describe the image. "
                    "Please describe the item in your own words in the next message."
                )
                description = "Manual description required"

            # Store and advance
            context.user_data["description"] = description
            context.user_data["step"] = 1

            if description != "Manual description required":
                text = (
                    f"🖼️ **Item Description:**\n{description}\n\n"
                    f"📧 Now please send me your email and the location where you found it.\n\n"
                    f"**Format:** your.email@example.com, Central Park near the pond\n\n"
                    f"ℹ️ *Make sure to include both your email and location separated by a comma.*"
                )
            else:
                text = (
                    "📝 Please describe the item you found in detail, then provide your email and location.\n\n"
                    "**Format:** your.email@example.com, Central Park near the pond"
                )

            await update.message.reply_text(text, parse_mode="Markdown")
            return

        # 1) receive email+location or manual description
        if step == 1:
            text = (update.message.text or "").strip()

            # Check if this is a manual description (no email format)
            if context.user_data.get("description") == "Manual description required" and "@" not in text:
                if len(text) < MIN_DESCRIPTION_LENGTH:
                    await update.message.reply_text(
                        f"❌ Please provide a more detailed description (at least {MIN_DESCRIPTION_LENGTH} characters)."
                    )
                    return

                context.user_data["description"] = text
                await update.message.reply_text(
                    "📧 Great! Now please send me your email and the location where you found it.\n\n"
                    "**Format:** your.email@example.com, Central Park near the pond",
                    parse_mode="Markdown"
                )
                return

            # Parse email and location
            parsed = _split_email_location(text)
            if not parsed:
                await update.message.reply_text(
                    "❌ Please use the correct format:\n\n"
                    "**your.email@example.com, Location Name**\n\n"
                    "Make sure to:\n"
                    "• Include a valid email address\n"
                    "• Separate email and location with a comma\n"
                    "• Provide a specific location",
                    parse_mode="Markdown"
                )
                return

            email, location = parsed
            context.user_data["email"] = email
            context.user_data["location_text"] = location
            context.user_data["step"] = 2

            # Show processing message for geocoding
            processing_msg = await update.message.reply_text("🗺️ Looking up location...")

            try:
                # Ask lens_agent to geocode the location
                geocode_message = f"Please geocode this location and return ONLY the formatted address with no additional text: {location}"
                geocode_resp = await run_agent_with_timeout(lens_runner, user_id, geocode_message)

                # Extract only the address from the agent's response
                # Remove any prefix like "OK. The geocoded location is:"
                if ":" in geocode_resp:
                    # Take the part after the last colon
                    address = geocode_resp.split(":")[-1].strip()
                else:
                    address = geocode_resp.strip()

                # Remove any surrounding quotes
                if address.startswith('"') and address.endswith('"'):
                    address = address[1:-1].strip()

                logger.info(f"Geocoded '{location}' to '{address}'")
                await processing_msg.delete()
            except Exception as e:
                logger.error("Geocoding failed: %s", e)
                address = location
                await processing_msg.edit_text("⚠️ Couldn't verify location, using as provided.")

            context.user_data["geocoded_address"] = address

            # Ask the user to confirm using inline buttons
            keyboard = [
                [InlineKeyboardButton("✅ Yes, that's correct", callback_data="location_yes")],
                [InlineKeyboardButton("❌ No, let me retry", callback_data="location_no")],
            ]
            reply = f"📍 **Location Confirmation**\n\nDid you mean: **{address}**?"
            await update.message.reply_text(reply, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            return

        # Fallback for unexpected step
        context.user_data.clear()
        await update.message.reply_text("❌ Something went wrong. Please send /start to begin again.")

    except Exception as e:
        logger.error(f"Error in handle_found_flow: {e}")
        logger.error(traceback.format_exc())
        await update.message.reply_text(
            "❌ An unexpected error occurred. Please try again or send /start to restart."
        )
        context.user_data.clear()


async def handle_location_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    CallbackQuery for FOUND: user confirms or denies the geocoded location.
    Enhanced with proper registration agent usage.
    """
    try:
        await update.callback_query.answer()
        data = update.callback_query.data
        user_id = str(update.effective_user.id)

        if data == "location_yes":
            # User accepted location → register the found item
            desc = context.user_data.get("description", "No description")
            email = context.user_data.get("email", "No email")
            location = context.user_data.get("geocoded_address", "No location")

            # Show processing message
            await update.callback_query.edit_message_text("🔄 Registering your found item...")

            try:
                # Generate item ID
                item_id = generate_item_id("FOUND", desc, email, location)

                # Prepare item data for registration
                item_data = {
                    "item_id": item_id,
                    "description": desc,
                    "email": email,
                    "location": location,
                    "timestamp": datetime.now().isoformat()
                }

                # Register the found item using the dedicated function
                registration_result = await register_found_item(user_id, item_data)

                if registration_result.get("success"):
                    text = (
                        f"✅ **Found Item Registered Successfully!**\n\n"
                        f"📋 **Item ID:** `{item_id}`\n"
                        f"📧 **Contact:** {email}\n"
                        f"📍 **Location:** {location}\n"
                        f"📅 **Registered:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                        f"💡 *Your item has been added to our database. "
                        f"We'll notify you if someone reports a matching lost item.*"
                    )

                    if registration_result.get("message"):
                        text += f"\n\n🤖 **System Note:** {registration_result['message']}"

                else:
                    error_msg = registration_result.get("error", "Unknown error")
                    text = (
                        f"❌ **Registration Failed**\n\n"
                        f"📋 **Item ID:** `{item_id}`\n"
                        f"❗ **Error:** {error_msg}\n\n"
                        f"Please try again later or contact support."
                    )

            except Exception as e:
                logger.error("Unexpected error in found item registration: %s", e)
                text = "❌ Registration failed due to a technical error. Please try again later."
            finally:
                # Clear state
                context.user_data.clear()

            await safe_edit_message(update, text, parse_mode="Markdown")

        else:  # location_no
            # User denied → go back to step 1
            context.user_data["step"] = 1
            await safe_edit_message(
                update,
                "📧 Please send your email and location again:\n\n"
                "**Format:** your.email@example.com, Correct Location Name",
                parse_mode="Markdown"
            )

    except Exception as e:
        logger.error(f"Error in handle_location_confirmation: {e}")
        try:
            await update.callback_query.edit_message_text(
                "❌ An error occurred. Please send /start to restart."
            )
        except:
            pass
        context.user_data.clear()


# ─── LOST flow ──────────────────────────────────────────────────────────

async def handle_lost_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Workflow for reporting a LOST item with enhanced validation and user experience.
    """
    try:
        step = context.user_data.get("step", 0)
        text = (update.message.text or "").strip()

        # 0) description
        if step == 0:
            if len(text) < MIN_DESCRIPTION_LENGTH:
                await update.message.reply_text(
                    f"❌ Please provide a more detailed description (at least {MIN_DESCRIPTION_LENGTH} characters).\n\n"
                    f"**Include details like:**\n"
                    f"• Color and size\n"
                    f"• Brand or model\n"
                    f"• Distinctive features\n"
                    f"• Condition\n\n"
                    f"**Example:** Blue iPhone 15 Pro with black case, small scratch on back",
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
            await update.message.reply_text(
                "📍 **Where and when did you lose it?**\n\n"
                "Please be as specific as possible:\n\n"
                "**Example:** Central Park near the pond, yesterday around 3 PM",
                parse_mode="Markdown"
            )
            return

        # 1) location/time
        if step == 1:
            if len(text) < 10:
                await update.message.reply_text(
                    "❌ Please provide more details about where and when you lost the item."
                )
                return

            context.user_data["location_time"] = text
            context.user_data["step"] = 2
            await update.message.reply_text(
                "📧 **Contact Information**\n\n"
                "Please provide your email address and optionally your phone number:\n\n"
                "**Examples:**\n"
                "• john@example.com\n"
                "• john@example.com, +1-555-1234",
                parse_mode="Markdown"
            )
            return

        # 2) contact
        if step == 2:
            # Validate email
            email_part = text.split(',')[0].strip()
            if not validate_email(email_part):
                await update.message.reply_text(
                    "❌ Please provide a valid email address.\n\n"
                    "**Format:** your.email@example.com"
                )
                return

            context.user_data["contact"] = text
            context.user_data["step"] = 3

            # Show confirmation summary
            desc = context.user_data["description"]
            loc = context.user_data["location_time"]
            contact = context.user_data["contact"]

            summary = (
                f"📋 **Lost Item Report Summary**\n\n"
                f"🔍 **Item:** {desc}\n\n"
                f"📍 **Where/When:** {loc}\n\n"
                f"📧 **Contact:** {contact}\n\n"
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

        # Fallback for unexpected step
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
    CallbackQuery for LOST: submit, edit or cancel with enhanced user experience.
    """
    try:
        await update.callback_query.answer()
        choice = update.callback_query.data
        user_id = str(update.effective_user.id)

        if choice == "submit_lost":
            desc = context.user_data.get("description", "No description")
            loc_time = context.user_data.get("location_time", "No location/time")
            contact = context.user_data.get("contact", "No contact")

            # Show processing message
            await update.callback_query.edit_message_text("🔄 Submitting your lost item report...")

            try:
                # Generate report ID
                report_id = generate_item_id("LOST", desc, loc_time, contact)

                # Ask the lost agent to register the lost item
                register_message = f"""Please register a lost item with these details:
Report ID: {report_id}
Description: {desc}
Location and Time: {loc_time}
Contact: {contact}
Date Reported: {datetime.now().strftime('%Y-%m-%d %H:%M')}

Please confirm registration and provide guidance for next steps."""

                resp = await run_agent_with_timeout(lost_runner, user_id, register_message)

                text = (
                    f"✅ **Lost Item Report Submitted!**\n\n"
                    f"📋 **Report ID:** `{report_id}`\n"
                    f"📅 **Submitted:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                    f"🤖 **System Response:**\n{resp}\n\n"
                    f"💡 *We'll notify you immediately if someone reports finding a matching item. "
                    f"Keep your Report ID for reference.*"
                )

            except ItemRadarError as e:
                text = f"❌ Failed to submit report: {str(e)}\n\nPlease try again later."
            except Exception as e:
                logger.error("Lost registration error: %s", e)
                text = "❌ Failed to submit lost report due to a technical error. Please try again later."
            finally:
                context.user_data.clear()

            await safe_edit_message(update, text, parse_mode="Markdown")

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
        logger.error(traceback.format_exc())
        try:
            await update.callback_query.edit_message_text(
                "❌ An error occurred. Please send /start to restart."
            )
        except:
            pass
        context.user_data.clear()