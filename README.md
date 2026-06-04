# HealthHero - AI Health Coach Application

A modern, full-featured health coaching chatbot application with authentication, health tracking, reminders, and analytics.

## Features

✅ **User Authentication** - Secure registration and login with JWT tokens  
✅ **AI-Powered Chat** - OpenAI integration with fallback to mock responses  
✅ **Real-time Communication** - WebSocket support for instant responses  
✅ **Health Tracking** - Log water intake, steps, sleep, exercise, weight, and heart rate  
✅ **Reminders** - Set reminders for medications, water, exercise, meals, and more  
✅ **Analytics Dashboard** - View insights and statistics about your health metrics  
✅ **Modern Medical UI** - Beautiful, responsive design with medical theme  
✅ **Database Persistence** - SQLite database for all data storage  
✅ **Error Handling** - Comprehensive error handling and user feedback  

## Setup

### 1. Install Dependencies

Open a terminal in the project directory and run:

```bash
pip install -r requirements.txt
```

**Note**: Make sure you have Python 3.8+ installed.

### 2. API Key Setup (Optional but Recommended)

The application will automatically use your OpenAI API key from one of these sources (in order of priority):

1. **Environment Variable** (highest priority):
   ```bash
   # Windows PowerShell
   $env:OPENAI_API_KEY="your-api-key-here"
   
   # Windows CMD
   set OPENAI_API_KEY=your-api-key-here
   
   # Linux/Mac
   export OPENAI_API_KEY="your-api-key-here"
   ```

2. **API Key File**: The file `HealthHero API Key.txt` (already in your project)
   - The app automatically reads the key from this file
   - The key will be extracted automatically (handles quotes and formatting)

**If no API key is found**, the app will use mock responses for demonstration.

You can also set these optional environment variables:
- `OPENAI_BASE_URL` - Custom API endpoint (default: https://api.openai.com/v1)
- `OPENAI_MODEL` - Model to use (default: gpt-4o-mini)
- `JWT_SECRET` - Secret key for JWT tokens (auto-generated if not set)

### 3. Run the Application

In the project directory, run:

```bash
uvicorn app:app --reload
```

The `--reload` flag enables auto-reload on code changes (useful for development).

### 4. Access the Application

Once the server starts, you'll see output like:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

Open your web browser and navigate to:
```
http://localhost:8000
```

or

```
http://127.0.0.1:8000
```

### 5. First Time Setup

1. **Register a new account** - Click "Register" and create your account
2. **Login** - Use your credentials to login
3. **Start chatting** - Ask HealthHero about your health and wellness goals!

The database (`healthhero.db`) will be automatically created on first run.

## Usage

1. **Register/Login**: Create an account or login with existing credentials
2. **Chat**: Ask HealthHero about health, wellness, and goals
3. **Track Metrics**: Log your daily health metrics (water, steps, sleep, etc.)
4. **Set Reminders**: Create reminders for health-related activities
5. **View Analytics**: Check your health statistics and trends

## Database

The application uses SQLite (`healthhero.db`) to store:
- User accounts
- Chat sessions and messages
- Health metrics
- Reminders

The database is automatically created on first run.

## API Endpoints

- `POST /api/register` - Register new user
- `POST /api/login` - Login and get JWT token
- `POST /api/chat` - Send chat message (requires auth)
- `GET /api/chat/stream` - Stream chat response (requires auth)
- `WebSocket /ws` - Real-time chat via WebSocket (requires auth)
- `GET /api/health/metrics` - Get health metrics (requires auth)
- `POST /api/health/metrics` - Add health metric (requires auth)
- `GET /api/reminders` - Get reminders (requires auth)
- `POST /api/reminders` - Create reminder (requires auth)
- `GET /api/analytics` - Get analytics (requires auth)

## Tech Stack

- **Backend**: FastAPI, Python
- **Database**: SQLite (aiosqlite)
- **Authentication**: JWT (python-jose)
- **AI**: OpenAI API (with mock fallback)
- **Frontend**: Vanilla JavaScript, HTML5, CSS3
- **Real-time**: WebSocket

## Notes

- If `OPENAI_API_KEY` is not set, the app will use mock responses
- All API endpoints (except register/login) require JWT authentication
- Sessions are persisted in the database
- The UI is fully responsive and works on mobile devices


setx OPENAI_API_KEY "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"
Optional:
setx OPENAI_BASE_URL "https://api.openai.com/v1"
setx OPENAI_MODEL "gpt-4o-mini"

python -m uvicorn app:app --reload