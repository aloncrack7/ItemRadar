# ItemRadarAI 🔍

**Connecting People with Lost Belongings**

A citizen network that reunites people with their lost belongings in minutes using AI-powered multi-agent technology.

## Overview

ItemRadarAI is an innovative platform designed to connect residents of any city with individuals who find lost items, streamlining the recovery process and providing valuable insights into loss patterns across urban environments.

### Key Features

- **For Lost Item Owners**: Conversational chatbot accessible via WhatsApp, web, or mobile app that matches descriptions or photos with found items in seconds
- **For Item Finders**: Simple photo capture with GPS location upload to instantly add items to the database
- **For Municipalities**: Analytical dashboards displaying loss hotspots, peak times, and item categories to optimize urban cleaning and safety operations

## How It Works

ItemRadarAI operates through a sophisticated multi-agent AI system:

### 1. **Lens Agent** (For Finders)
- Captures photo, geolocation, and timestamp
- Extracts detailed descriptions using Gemini Vision
- Generates embeddings and stores in Firestore with Vertex AI Vector Search

### 2. **Chatbot Agent** (For Owners)
- Engages in natural dialogue to understand the lost item
- Generates accurate descriptions and corresponding embeddings
- Publishes description-ready events to the system

### 3. **ItemMatcher Agent**
- Queries Vertex AI Vector Search to retrieve top matching candidates
- Returns ranked results based on similarity scores

### 4. **Reducer Agent**
- Handles multiple matches by generating discriminative questions
- Examples: "Does it have handles?", "What color is the strap?"

### 5. **Filter**
- Applies user responses to refine candidate lists
- Iterates until reaching either one match or no matches

### 6. **Results**
- **Single Match**: Notifies both users with pickup instructions
- **No Match**: Informs user and offers optional future notifications

## Technology Stack

### Core Infrastructure
- **ADK (Python)**: Primary development framework
- **Firestore**: Data storage
- **FastAPI**: REST API server for frontend integration
- **Next.js**: Modern React frontend with TypeScript

### AI & Machine Learning
- **Gemini Embeddings & Vision**: Item description and image processing
- **Vertex AI Vector Search**: Fast, accurate matching (< 500ms)
- **Gemini**: Powers conversational chatbot

### User Interface & Analytics
- **Next.js Frontend**: Modern web interface for lost/found item reporting
- **Firebase UI**: Found item intake interface
- **Looker Studio**: Municipal dashboard visualization
- **Multi-channel Support**: WhatsApp, web, and mobile app integration

## Getting Started

### Prerequisites
- Google Cloud Platform account with enabled APIs
- Python 3.8+ environment
- Node.js 18+ environment
- ADK framework installation

### Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd ItemRadar
   ```

2. **Set up environment variables**
   ```bash
   cp env.template .env
   # Edit .env with your actual API keys and configuration
   ```

3. **Start the development environment**
   ```bash
   ./start_dev.sh
   ```

This will:
- Install all dependencies (Python and Node.js)
- Start the API server on http://localhost:8000
- Start the frontend on http://localhost:9002
- Open API documentation at http://localhost:8000/docs

### Manual Setup

If you prefer to set up manually:

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend
npm install

# Start API server (in one terminal)
python api/main.py

# Start frontend (in another terminal)
cd frontend
npm run dev
```

### Configuration

1. Set up Firestore database
2. Configure Vertex AI Vector Search index
3. Enable required Google Cloud APIs
4. Set environment variables for API keys and endpoints

## API Integration

The system now includes a FastAPI server that connects the frontend with the multiagent system:

- **Lost Item Reports**: Connect to `chatbot_manager` agent for search workflow
- **Found Item Reports**: Connect to `lens_agent` for geocoding and registration
- **Search Status**: Track ongoing lost item searches

See [API_INTEGRATION.md](API_INTEGRATION.md) for detailed documentation.

## Testing

Run the API integration tests:

```bash
python test_api.py
```

## Development

### Project Structure
```
ItemRadar/
├── api/                 # FastAPI server
├── frontend/           # Next.js frontend
├── multiAgent/         # Multi-agent AI system
├── start_dev.sh        # Development startup script
├── test_api.py         # API integration tests
└── API_INTEGRATION.md  # API documentation
```

### Key Files
- `api/main.py`: FastAPI server with endpoints
- `frontend/src/app/actions.ts`: Frontend API calls
- `multiAgent/chatbot_manager/agent.py`: Lost item processing
- `multiAgent/lens_agent/agent.py`: Found item processing

## License

This project is licensed under the MIT License - see the LICENSE file for details.

