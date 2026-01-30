"""
Telegram Bot Service for PC-1 Paper Console.

This module provides a Telegram bot interface for conversational AI interactions
with print capabilities. The bot runs as a background service on the device,
requiring no cloud infrastructure.

Features:
- Natural conversation with Claude or OpenAI
- Print on command ("print that", "/print", etc.)
- Per-user conversation history
- Authorization via Telegram user ID whitelist
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Try to import telegram library
try:
    from telegram import Update
    from telegram.ext import (
        Application,
        CommandHandler,
        MessageHandler,
        ContextTypes,
        filters,
    )
    HAS_TELEGRAM = True
except ImportError:
    HAS_TELEGRAM = False
    # Provide placeholder types for annotations when library not installed
    Update = Any
    ContextTypes = Any
    logger.warning("python-telegram-bot not installed. Telegram bot will not function.")

# Try to import AI libraries
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


# --- Constants ---

SYSTEM_PROMPT = """You are a helpful AI assistant connected to a thermal receipt printer (PC-1 Paper Console).

IMPORTANT: When the user wants to PRINT something, you must respond with a JSON object:
{"print": true, "content": "The content to print", "title": "Short title"}

Examples of print requests:
- "print a pasta recipe" → Generate a pasta recipe and return JSON to print it
- "print that" or "print the above" → Return JSON with the last thing you discussed
- "can you print me a haiku about coffee" → Generate haiku and return JSON to print it
- "I want to print a shopping list for tacos" → Generate list and return JSON to print it

For normal conversation (no printing), just respond normally with plain text.

Guidelines for printed content:
- Keep content concise (thermal printer is narrow, ~32 chars wide)
- Use simple formatting: short paragraphs, bullet points
- No markdown headers or complex formatting
- Title should be 2-4 words max

You're running on a small home device. Be warm, helpful, and conversational."""

MAX_HISTORY_LENGTH = 20  # Keep last N messages per user


@dataclass
class ConversationState:
    """Tracks conversation history for a user."""
    messages: List[Dict[str, str]] = field(default_factory=list)


class TelegramBotService:
    """
    Manages the Telegram bot lifecycle and message handling.
    
    This service runs as a background task, polling Telegram for messages
    and routing them through the AI and printer systems.
    """
    
    def __init__(self, config):
        """
        Initialize the bot service.
        
        Args:
            config: TelegramBotConfig instance with bot settings
        """
        self.config = config
        self.application: Optional[Any] = None
        self.conversations: Dict[int, ConversationState] = {}
        self._running = False
        self._ai_client = None
        
    @property
    def is_running(self) -> bool:
        return self._running
    
    def _init_ai_client(self):
        """Initialize the appropriate AI client based on config."""
        if not self.config.ai_api_key:
            logger.warning("No AI API key configured for Telegram bot")
            return
            
        provider = self.config.ai_provider.lower()
        
        if provider == "anthropic":
            if not HAS_ANTHROPIC:
                logger.error("Anthropic library not installed")
                return
            self._ai_client = anthropic.Anthropic(api_key=self.config.ai_api_key)
            
        elif provider == "openai":
            if not HAS_OPENAI:
                logger.error("OpenAI library not installed")
                return
            self._ai_client = openai.OpenAI(api_key=self.config.ai_api_key)
            
        else:
            logger.error(f"Unknown AI provider: {provider}")
    
    def _get_ai_model(self) -> str:
        """Get the AI model to use, with sensible defaults."""
        if self.config.ai_model:
            return self.config.ai_model
            
        provider = self.config.ai_provider.lower()
        if provider == "anthropic":
            return "claude-sonnet-4-20250514"
        elif provider == "openai":
            return "gpt-4o-mini"
        return "claude-sonnet-4-20250514"
    
    async def _call_ai(self, user_id: int, message: str) -> str:
        """
        Send a message to the AI and get a response.
        
        Args:
            user_id: Telegram user ID for conversation tracking
            message: User's message
            
        Returns:
            AI response text
        """
        if not self._ai_client:
            return "AI is not configured. Please add an API key in settings."
        
        # Get or create conversation state
        if user_id not in self.conversations:
            self.conversations[user_id] = ConversationState()
        
        state = self.conversations[user_id]
        
        # Add user message to history
        state.messages.append({"role": "user", "content": message})
        
        # Trim history if too long
        if len(state.messages) > MAX_HISTORY_LENGTH:
            state.messages = state.messages[-MAX_HISTORY_LENGTH:]
        
        try:
            provider = self.config.ai_provider.lower()
            model = self._get_ai_model()
            
            if provider == "anthropic":
                response = self._ai_client.messages.create(
                    model=model,
                    max_tokens=1024,
                    system=SYSTEM_PROMPT,
                    messages=state.messages,
                )
                reply = response.content[0].text
                
            elif provider == "openai":
                messages = [{"role": "system", "content": SYSTEM_PROMPT}]
                messages.extend(state.messages)
                
                response = self._ai_client.chat.completions.create(
                    model=model,
                    max_tokens=1024,
                    messages=messages,
                )
                reply = response.choices[0].message.content
                
            else:
                reply = "Unknown AI provider configured."
            
            # Store response in history and cache
            state.messages.append({"role": "assistant", "content": reply})
            state.last_bot_response = reply
            
            return reply
            
        except Exception as e:
            logger.error(f"AI API error: {e}", exc_info=True)
            return f"Sorry, I encountered an error: {str(e)}"
    
    def _parse_print_response(self, response: str) -> Optional[Dict[str, Any]]:
        """
        Try to parse a print instruction from AI response.
        
        Returns dict with 'content' and 'title' if print requested, None otherwise.
        """
        response = response.strip()
        
        # Check if response looks like JSON
        if not (response.startswith('{') and response.endswith('}')):
            return None
        
        try:
            data = json.loads(response)
            if data.get('print') and data.get('content'):
                return {
                    'content': data['content'],
                    'title': data.get('title', 'TELEGRAM')[:30]  # Limit title length
                }
        except json.JSONDecodeError:
            pass
        
        return None
    
    def _is_user_authorized(self, user_id: int) -> bool:
        """Check if a user is authorized to use the bot."""
        # If no users configured, allow anyone (open mode)
        if not self.config.allowed_user_ids:
            return True
        return user_id in self.config.allowed_user_ids
    
    async def _send_to_printer(self, content: str, title: str = "TELEGRAM") -> bool:
        """
        Send content to the thermal printer.
        
        Args:
            content: Text content to print
            title: Header title for the printout
            
        Returns:
            True if print succeeded
        """
        try:
            from app.hardware import printer
            from app.config import settings
            from app.selection_mode import exit_selection_mode
            from datetime import datetime
            
            # Exit any active selection mode
            exit_selection_mode()
            
            # Reset printer buffer
            if hasattr(printer, "reset_buffer"):
                max_lines = getattr(settings, "max_print_lines", 200)
                printer.reset_buffer(max_lines)
            
            # Print header
            printer.print_header(title.upper(), icon="chat")
            printer.print_caption(datetime.now().strftime("%A, %B %d, %Y %I:%M %p"))
            printer.print_line()
            
            # Print content
            printer.print_body(content)
            printer.print_line()
            
            # Flush to hardware
            if hasattr(printer, "flush_buffer"):
                printer.flush_buffer()
            
            logger.info("Telegram print job completed")
            return True
            
        except Exception as e:
            logger.error(f"Print error: {e}", exc_info=True)
            return False
    
    async def _handle_message(self, update: Update, context: Any):
        """Handle incoming messages."""
        if not update.message or not update.message.text:
            return
        
        user = update.effective_user
        if not user:
            return
        
        user_id = user.id
        message = update.message.text
        
        # Authorization check
        if not self._is_user_authorized(user_id):
            logger.warning(f"Unauthorized user {user_id} attempted to use bot")
            return  # Silently ignore unauthorized users
        
        logger.info(f"Message from {user_id}: {message[:50]}...")
        
        # Show typing indicator
        await update.message.chat.send_action("typing")
        
        # Call AI
        response = await asyncio.to_thread(self._call_ai_sync, user_id, message)
        
        # Check if AI wants to print something
        print_data = self._parse_print_response(response)
        
        if print_data:
            # AI returned a print instruction
            await update.message.reply_text(f"🖨️ Printing: {print_data['title']}...")
            
            # Print in background thread
            success = await asyncio.to_thread(
                self._print_sync, print_data['content'], print_data['title']
            )
            
            if success:
                await update.message.reply_text("✅ Done! Check your printer.")
            else:
                await update.message.reply_text("❌ Print failed. Check printer connection.")
        else:
            # Normal conversation - just send the response
            await update.message.reply_text(response)
    
    def _call_ai_sync(self, user_id: int, message: str) -> str:
        """Synchronous wrapper for AI call (for thread pool)."""
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self._call_ai(user_id, message))
        finally:
            loop.close()
    
    def _print_sync(self, content: str, title: str = "TELEGRAM") -> bool:
        """Synchronous print wrapper for thread pool."""
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self._send_to_printer(content, title))
        finally:
            loop.close()
    
    async def _handle_start(self, update: Update, context: Any):
        """Handle /start command."""
        user = update.effective_user
        if not user:
            return
            
        if not self._is_user_authorized(user.id):
            return
        
        await update.message.reply_text(
            f"👋 Hi {user.first_name}! I'm your PC-1 assistant.\n\n"
            "Just chat with me! When you want to print something, just ask:\n"
            "• 'Print a pasta recipe'\n"
            "• 'Print me a haiku about coffee'\n"
            "• 'Print a shopping list for tacos'\n\n"
            f"Your Telegram ID is: {user.id}"
        )
    
    async def _handle_help(self, update: Update, context: Any):
        """Handle /help command."""
        user = update.effective_user
        if not user or not self._is_user_authorized(user.id):
            return
            
        await update.message.reply_text(
            "🖨️ **PC-1 Telegram Bot**\n\n"
            "**How to print:**\n"
            "• 'Print a joke'\n"
            "• 'Print me a recipe for cookies'\n"
            "• 'Print a motivational quote'\n\n"
            "**Commands:**\n"
            "• /start - Welcome message\n"
            "• /help - This message\n"
            "• /id - Show your Telegram user ID\n\n"
            f"Your ID: {user.id}"
        )
    
    async def _handle_id(self, update: Update, context: Any):
        """Handle /id command - shows user their Telegram ID."""
        user = update.effective_user
        if not user:
            return
            
        await update.message.reply_text(
            f"Your Telegram user ID is: `{user.id}`\n\n"
            "Add this to your PC-1 Telegram settings to authorize this account."
        )
    
    async def run(self):
        """
        Run the bot (blocking).
        
        This is designed to be run as an asyncio task.
        """
        if not HAS_TELEGRAM:
            logger.error("Cannot start Telegram bot: python-telegram-bot not installed")
            return
        
        if not self.config.bot_token:
            logger.error("Cannot start Telegram bot: no bot token configured")
            return
        
        self._init_ai_client()
        
        try:
            # Build application
            self.application = (
                Application.builder()
                .token(self.config.bot_token)
                .build()
            )
            
            # Register handlers
            self.application.add_handler(CommandHandler("start", self._handle_start))
            self.application.add_handler(CommandHandler("help", self._handle_help))
            self.application.add_handler(CommandHandler("id", self._handle_id))
            self.application.add_handler(CommandHandler("print", self._handle_print_command))
            self.application.add_handler(
                MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
            )
            
            logger.info("Starting Telegram bot...")
            self._running = True
            
            # Run polling (this blocks until stop is called)
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling(drop_pending_updates=True)
            
            # Keep running until cancelled
            while self._running:
                await asyncio.sleep(1)
                
        except asyncio.CancelledError:
            logger.info("Telegram bot task cancelled")
        except Exception as e:
            logger.error(f"Telegram bot error: {e}", exc_info=True)
        finally:
            await self.stop()
    
    async def _handle_print_command(self, update: Update, context: Any):
        """Handle /print command - redirect to help text."""
        user = update.effective_user
        if not user or not self._is_user_authorized(user.id):
            return
        await update.message.reply_text(
            "Just tell me what you want to print!\n\n"
            "Try: 'Print a joke' or 'Print me a haiku'"
        )
    
    async def stop(self):
        """Stop the bot gracefully."""
        self._running = False
        
        if self.application:
            try:
                if self.application.updater and self.application.updater.running:
                    await self.application.updater.stop()
                if self.application.running:
                    await self.application.stop()
                await self.application.shutdown()
            except Exception as e:
                logger.warning(f"Error during bot shutdown: {e}")
            
        logger.info("Telegram bot stopped")


# --- Module-level convenience functions ---

_active_service: Optional[TelegramBotService] = None


async def start_telegram_bot(config) -> Optional[TelegramBotService]:
    """
    Start the Telegram bot service.
    
    Args:
        config: TelegramBotConfig instance
        
    Returns:
        TelegramBotService instance if started, None otherwise
    """
    global _active_service
    
    if not HAS_TELEGRAM:
        logger.warning("Telegram bot not available: library not installed")
        return None
    
    if not config.enabled:
        logger.info("Telegram bot is disabled in config")
        return None
    
    if not config.bot_token:
        logger.warning("Telegram bot token not configured")
        return None
    
    _active_service = TelegramBotService(config)
    return _active_service


async def stop_telegram_bot():
    """Stop the active Telegram bot service."""
    global _active_service
    
    if _active_service:
        await _active_service.stop()
        _active_service = None


def get_telegram_bot_status() -> Dict[str, Any]:
    """Get the current status of the Telegram bot."""
    global _active_service
    
    return {
        "available": HAS_TELEGRAM,
        "running": _active_service is not None and _active_service.is_running,
        "users_connected": len(_active_service.conversations) if _active_service else 0,
    }
