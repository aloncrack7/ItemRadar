# ItemRadar API Integration

This document describes the integration between the ItemRadar frontend and the multiagent system.

## Architecture Overview

The system consists of:
- **Frontend**: Next.js application (port 9002)
- **API Server**: FastAPI server (port 8000) 
- **Multiagent System**: Python-based AI agents for processing lost and found items

## API Endpoints

### Lost Item Processing
- **POST** `/api/lost-item`
  - Connects to `chatbot_manager` agent
  - Initiates search workflow for lost items
  - Returns search ID for tracking

### Found Item Processing  
- **POST** `/api/found-item`
  - Connects to `lens_agent` 
  - Processes found items with geocoding
  - Registers items in the system

### Search Status
- **GET** `/api/search-status/{search_id}`
  - Check status of ongoing lost item searches

## Data Flow

### Lost Item Flow
1. User submits lost item form on frontend
2. Frontend calls `/api/lost-item` endpoint
3. API server creates search context
4. `chatbot_manager` agent initiates search workflow
5. Search results are stored and tracked
6. User receives confirmation with search ID

### Found Item Flow
1. User submits found item form on frontend  
2. Frontend calls `/api/found-item` endpoint
3. API server processes the request
4. `lens_agent` geocodes the location
5. Item is registered in the system
6. User receives confirmation with item ID

## Development Setup

### Prerequisites
- Python 3.8+
- Node.js 18+
- Required environment variables (see `.env` file)

### Quick Start
```bash
# Run the development startup script
./start_dev.sh
```

This will:
- Install dependencies for both frontend and API
- Start the API server on http://localhost:8000
- Start the frontend on http://localhost:9002
- Open API documentation at http://localhost:8000/docs

### Manual Setup
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

## Environment Variables

Create a `.env` file in the project root with:

```env
# Google Cloud Configuration
PROJECT_ID=your-project-id
REGION=us-central1
INDEX_ID=your-index-id
GOOGLE_API_KEY=your-google-api-key
GEOCODING_API_KEY=your-geocoding-api-key

# Frontend Configuration  
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## API Documentation

Once the API server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Testing the Integration

1. Start both servers using `./start_dev.sh`
2. Navigate to http://localhost:9002
3. Try reporting a lost item - should connect to chatbot_manager
4. Try reporting a found item - should connect to lens_agent
5. Check the API logs for successful processing

## Troubleshooting

### Common Issues

**API Connection Failed**
- Ensure the API server is running on port 8000
- Check that `NEXT_PUBLIC_API_URL` is set correctly
- Verify CORS settings in the API

**Import Errors**
- Make sure all Python dependencies are installed
- Check that the multiagent modules are in the correct path
- Verify environment variables are set

**Frontend Build Errors**
- Ensure Node.js version is compatible
- Clear node_modules and reinstall if needed
- Check for TypeScript compilation errors

### Debug Mode

To run in debug mode with more verbose logging:

```bash
# API with debug logging
python -m uvicorn api.main:app --reload --log-level debug

# Frontend with debug logging  
cd frontend
DEBUG=* npm run dev
```

## Production Deployment

For production deployment:

1. **API Server**: Deploy to Google Cloud Run or similar
2. **Frontend**: Deploy to Vercel, Netlify, or similar
3. **Environment**: Set production environment variables
4. **CORS**: Update CORS origins for production domains

## Future Enhancements

- [ ] Add authentication and user management
- [ ] Implement real-time notifications
- [ ] Create admin dashboard for managing items
- [ ] Add analytics and reporting features 