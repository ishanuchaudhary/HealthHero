# 🏥 HealthHero — AI Health Assistant

> An intelligent, offline-first health coaching application powered by a locally trained Machine Learning model. No API key required.

[![Python](https://img.shields.io/badge/Python-3.8+-blue?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![scikit-learn](https://img.shields.io/badge/scikit--learn-1.5-orange?logo=scikit-learn&logoColor=white)](https://scikit-learn.org)
[![License](https://img.shields.io/badge/License-MIT-purple)](LICENSE)

---

## 📌 Overview

HealthHero is a full-stack AI health assistant that predicts possible diseases based on user-reported symptoms using a **locally trained Random Forest classifier**. It provides structured, empathetic health guidance — including what the condition could be, what to do, and when to see a doctor — all running completely offline on your machine.

Built as a Final Year B.Tech Computer Science project at **Galgotias University**.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🤖 **Local ML Model** | RandomForest trained on 25 diseases & 60 symptoms — no API key needed |
| 🔐 **JWT Authentication** | Secure user registration and login with token-based auth |
| 💬 **Real-time Chat** | WebSocket-powered instant responses with streaming |
| 📊 **Health Tracking** | Log water intake, steps, sleep, exercise, weight, heart rate |
| ⏰ **Smart Reminders** | Set reminders for medications, water, exercise, and meals |
| 📈 **Analytics Dashboard** | Visual insights and trends from your health metrics |
| 🚨 **Red Flag Detection** | Automatically detects emergency symptoms and escalates |
| 🎨 **Medical UI** | Clean, responsive design with a professional medical theme |
| 💾 **Persistent Storage** | SQLite database for all user data and sessions |

---

## 🧠 How the AI Works

Unlike typical chatbots that rely on external APIs, HealthHero uses a **locally trained ML model**:

```
User Message → Symptom Extraction → RandomForest Model → Disease Prediction → Structured Response
```

1. **Symptom Extraction** — Parses free-text input to identify medical symptoms using keyword matching against a vocabulary of 60+ symptoms
2. **Disease Prediction** — A trained RandomForest classifier predicts the top 3 most likely conditions with confidence scores
3. **Response Generation** — Builds a structured health response with advice, red flags, and follow-up plan
4. **Red Flag Safety Layer** — Always-on emergency detection regardless of prediction results

---

## 🗂️ Project Structure

```
HealthHero/
├── app.py              # FastAPI application — routes, WebSocket, API endpoints
├── auth.py             # JWT authentication — login, register, token validation
├── database.py         # SQLite schema — users, sessions, metrics, reminders
├── llm.py              # Local ML inference engine — symptom extraction + response
├── train_model.py      # One-time training script — builds and saves the model
├── requirements.txt    # Python dependencies
├── static/             # Frontend assets — CSS, JavaScript
├── templates/          # HTML templates
└── model/              # Saved model artifacts (auto-generated)
    ├── model.pkl       # Trained RandomForest classifier
    ├── encoder.pkl     # Label encoder for disease names
    ├── symptoms.pkl    # Ordered symptom feature list
    └── diseases.pkl    # All disease class names
```

---

## ⚙️ Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | FastAPI, Python 3.8+ |
| **AI / ML** | scikit-learn (RandomForest), pandas, numpy, joblib |
| **Database** | SQLite via aiosqlite |
| **Authentication** | JWT via python-jose |
| **Frontend** | Vanilla JavaScript, HTML5, CSS3 |
| **Real-time** | WebSocket |
| **Server** | Uvicorn (ASGI) |

---

## 🚀 Setup & Installation

### Prerequisites
- Python 3.8 or higher
- pip

### Step 1 — Clone the Repository
```bash
git clone https://github.com/ishanuchaudhary/HealthHero.git
cd HealthHero
```

### Step 2 — Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 3 — Train the Model *(one time only)*
```bash
python train_model.py
```
This will:
- Download or use the built-in disease-symptom dataset
- Train a RandomForest classifier
- Save model artifacts to the `model/` folder
- Print accuracy metrics on completion

Expected output:
```
✅ Done! Model accuracy: 95.0%+
Run: uvicorn app:app --reload
HealthHero now runs fully offline — no API key needed!
```

### Step 4 — Run the Application
```bash
uvicorn app:app --reload
```

### Step 5 — Open in Browser
```
http://localhost:8000
```

---

## 🖥️ First Time Use

1. Click **Register** and create your account
2. **Login** with your credentials
3. Describe your symptoms in the chat — e.g. *"I have fever, chills and joint pain"*
4. HealthHero will predict possible conditions and give structured guidance
5. Use the dashboard to track health metrics and set reminders

---

## 🔌 API Endpoints

### Authentication
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/register` | Register a new user |
| `POST` | `/api/login` | Login and receive JWT token |

### Chat
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/chat` | Send a message (requires auth) |
| `GET` | `/api/chat/stream` | Stream response (requires auth) |
| `WebSocket` | `/ws` | Real-time chat (requires auth) |

### Health Tracking
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health/metrics` | Retrieve health metrics |
| `POST` | `/api/health/metrics` | Log a new health metric |
| `GET` | `/api/reminders` | Get all reminders |
| `POST` | `/api/reminders` | Create a reminder |
| `GET` | `/api/analytics` | Get analytics and trends |

> All endpoints except `/api/register` and `/api/login` require a valid JWT token in the `Authorization` header.

---

## 🤖 ML Model Details

| Property | Value |
|---|---|
| Algorithm | Random Forest Classifier |
| Training Samples | 3,000+ |
| Diseases Covered | 25 |
| Symptoms (Features) | 60 |
| Test Accuracy | ~95% |
| Inference Time | < 10ms |
| External API | None — fully offline |

---

## 📋 Notes

- All API endpoints except register/login require JWT authentication
- The database is auto-created on first run
- Run `python llm.py` to test the ML model with sample inputs
- The UI is fully responsive and works on mobile devices
- Red flag symptoms (chest pain, difficulty breathing, etc.) always trigger an emergency alert regardless of prediction

---

## 👨‍💻 Author

**Sanskar Singh**
Final Year B.Tech — Computer Science
Galgotias University, Greater Noida

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-blue?logo=linkedin)](https://www.linkedin.com/in/sanskar9929/)
[![GitHub](https://img.shields.io/badge/GitHub-Follow-black?logo=github)](https://github.com/ishanuchaudhary)

---

> *"Code with purpose. Design with empathy. Deploy with pride."*
