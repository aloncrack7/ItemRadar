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

### 5. **Filter Agent**
- Applies user responses to refine candidate lists
- Iterates until reaching either one match or no matches

### 6. **Results**
- **Single Match**: Notifies both users with pickup instructions
- **No Match**: Informs user and offers optional future notifications

## Technology Stack

### Core Infrastructure
- **ADK (Python)**: Primary development framework
- **Cloud Run**: Hosts all AI agents
- **Pub/Sub & Cloud Functions**: Event-driven architecture
- **Firestore & BigQuery**: Data storage and analytics

### AI & Machine Learning
- **Gemini Embeddings & Vision**: Item description and image processing
- **Vertex AI Vector Search**: Fast, accurate matching (< 500ms)
- **Dialogflow CX**: Powers conversational chatbot

### User Interface & Analytics
- **Firebase UI**: Found item intake interface
- **Looker Studio**: Municipal dashboard visualization
- **Multi-channel Support**: WhatsApp, web, and mobile app integration

## Key Differentiators

| Traditional Challenge | ItemRadarAI Solution |
|----------------------|---------------------|
| Slow manual lost item catalogs | Vector Search + embeddings: matches in < 500ms |
| Limited visibility of loss hotspots | BigQuery + Looker Studio dashboards with heatmaps |
| Confusing verification processes | Reducer + Filter agents with automatic discriminative questions |
| Low user engagement | Multi-channel chatbot with push/email reminders |

## Current Status

✅ **Completed**
- Fully functional MVP with all agents running on Cloud Run
- Synthetic dataset of over 10,000 items for comprehensive stress testing
- Contributed PR to ADK: VectorSearchTool for upsert and batch search operations

## 2025 Roadmap

🎯 **Immediate Goals**
- Launch pilot program with municipal authority
- Implement multilingual support for diverse communities
- Develop public API for integration with mobility and transportation apps

🚀 **Future Enhancements**
- Machine learning model improvements based on real-world data
- Integration with smart city infrastructure
- Expansion to multiple cities and regions

## Getting Started

### Prerequisites
- Google Cloud Platform account with enabled APIs
- Python 3.8+ environment
- ADK framework installation

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/itemradar-ai.git
cd itemradar-ai

# Install dependencies
pip install -r requirements.txt

# Configure Google Cloud credentials
gcloud auth application-default login

# Deploy agents to Cloud Run
./deploy.sh
```

### Configuration

1. Set up Firestore database
2. Configure Vertex AI Vector Search index
3. Enable required Google Cloud APIs
4. Set environment variables for API keys and endpoints

## Contributing

We welcome contributions to ItemRadarAI! Please read our contributing guidelines and submit pull requests for any improvements.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contact

For questions, partnerships, or pilot program inquiries, please contact:
- Email: contact@itemradar.ai
- Website: https://itemradar.ai

---

*ItemRadarAI transforms small losses into quick reunions while providing valuable urban insights. By leveraging cutting-edge AI and user-friendly interfaces, we empower communities to recover lost items efficiently and help cities optimize their operations.*
