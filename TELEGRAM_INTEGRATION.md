# ItemRadar API Integration

This document describes the integration between the ItemRadar Telegram Bot and the multiagent system.

## Architecture Overview

The system consists of:
- **Bot**: [bot.py](bot.py) application
- **Adapter**: [multiagent/telegram_adapter.py](multiagent/telegram_adapter.py) 
- **Multiagent System**: Python-based AI agents for processing lost and found items

## Bot menu (/start)

### Lost Item Processing
- I lost an item
  - Connects to `chatbot_manager` agent
  - Initiates search workflow for lost items
  - Works with description and photos of the object

### Found Item Processing  
- I foudn an item
  - Connects to `lens_agent` 
  - Processes found items with geocoding
  - Registers items in the system

### My Reports (/status)
- Not available right now.

### Search Items 
- Not available right now.

### Help (/help)
-  Shows all how the bot works, tips and support
-  Display the commands

### Support 
- Show the support information

## Data Flow

### Lost Item Flow
1. User submits lost item form on the bot
2. Bot call via the adapter the agents
4. `chatbot_manager` agent initiates search workflow
5. Search results are stored and tracked
6. User receives confirmation with search ID

### Found Item Flow
1. User submits found item form on bot  
2. Bot call via the adapter the agents
3. API server processes the request
4. `lens_agent` geocodes the location
5. Item is registered in the system
6. User receives confirmation with item ID

## Development Setup

### Prerequisites
- Python 3.8+
- Node.js 18+
- Required environment variables (see `env.template` file)

### Running the bot and agents

- Install the requirements (you can use a virtual enviroment if needed)

```bash 
pip install -r requirements.txt
```

- Running the bot

```bash
# Run the development startup script
python bot.py
```

This will:
- Install dependencies for both bot and agents
- Start the bot for telegram
- Start the required agents

## Environment Variables

Create a `.env` file in the project root with:

```env
# Google Cloud Configuration
PROJECT_ID=your-project-id
REGION=us-central1
INDEX_ID=your-index-id
GOOGLE_API_KEY=your-google-api-key
GEOCODING_API_KEY=your-geocoding-api-key

# Telegram Token
TELEGRAM_BOT_TOKEN=your-bot-token
```

## Testing and use of the bot

1. Start the bot using `python bot.py`
2. Send a /start message to yout bot on telegram
3. Try reporting a lost item - should connect to chatbot_manager
4. Try reporting a found item - should connect to lens_agent

## Troubleshooting

**Import Errors**
- Make sure all Python dependencies are installed
- Check that the multiagent modules are in the correct path
- Verify environment variables are set

## Future Enhancements

- [ ] Add analytics and reporting features 