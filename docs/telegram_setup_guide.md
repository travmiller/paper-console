# PC-1 Telegram Bot Setup Guide

Control your PC-1 through Telegram with AI-powered conversations and instant printing.

## Quick Start

### 1. Create Your Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` and follow the prompts
3. Choose a name (e.g., "My PC-1 Bot")
4. Choose a username (must end in `bot`, e.g., `mypc1_bot`)
5. Copy the **bot token** - it looks like: `123456789:ABCdefGHI-jklMNO_pqrSTU`

### 2. Get Your Telegram User ID

1. Open Telegram and search for **@userinfobot** (or similar)
2. Send any message to get your numeric user ID
3. Alternatively, send `/id` to your new bot after setup

### 3. Get an AI API Key

**For Claude (Anthropic):**
- Go to [console.anthropic.com](https://console.anthropic.com)
- Create an account and add billing
- Generate an API key

**For ChatGPT (OpenAI):**
- Go to [platform.openai.com](https://platform.openai.com)
- Create an account and add billing
- Generate an API key

### 4. Configure Your PC-1

1. Open PC-1 Settings in your browser
2. Go to **General** tab
3. Scroll down to **Telegram Bot**
4. Enter:
   - ✅ Enable Telegram Bot
   - Bot Token (from step 1)
   - Your User ID (from step 2)
   - AI Provider (Claude or OpenAI)
   - AI API Key (from step 3)
5. Click **Apply & Restart Bot**

## Using the Bot

### Just Ask to Print!
Include "print" in your message and the bot will generate content and print it automatically:

> "Print a pasta recipe"  
> "Print me a haiku about coffee"  
> "Print a shopping list for tacos"  
> "Can you print a motivational quote?"

The bot will generate the content and send it directly to your printer.

### Normal Chat
Without "print" in your message, it's just a regular conversation:

> "What's the weather like in Paris?"  
> "Tell me a joke"  

### Bot Commands
- `/start` - Welcome message
- `/help` - List of commands  
- `/id` - Show your Telegram user ID

## Troubleshooting

### Bot Not Responding
- Check that the bot is enabled in settings
- Verify your bot token is correct
- Make sure your User ID is in the allowed list
- Check your internet connection

### Print Not Working
- Ensure the PC-1 is connected and paper is loaded
- Check the printer connection in PC-1 settings

### AI Errors
- Verify your API key is correct
- Check that your AI account has billing set up
- Try switching to a different AI provider

## Security Notes

- **Bot Token**: Keep this secret - anyone with it can control your bot
- **User IDs**: Only listed user IDs can interact with your bot
- **API Keys**: Stored locally on your PC-1, never sent to third parties

## Cost Considerations

- **Telegram**: Free
- **AI APIs**: Pay-per-use based on tokens
  - Claude: ~$0.003 per 1K input tokens
  - GPT-4o-mini: ~$0.00015 per 1K input tokens
  
Typical conversations cost fractions of a cent.
