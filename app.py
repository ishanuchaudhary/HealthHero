from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException, Depends, status
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import List, Dict, Any, Optional
import asyncio
import uuid
from datetime import datetime
from llm import generate, stream_generate
from database import (
    init_db, create_user, verify_user, get_or_create_session,
    save_message, get_messages, add_health_metric, get_health_metrics,
    create_reminder, get_reminders, get_user_sessions,
    get_user_profile, save_user_profile, get_user_settings, save_user_settings,
    create_goal, get_user_goals, update_goal, delete_goal, 
    add_goal_progress, get_goal_progress, calculate_goal_progress
)
from auth import create_access_token, get_current_user, verify_token_string

app = FastAPI(title="HealthHero", version="2.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Initialize database on startup
@app.on_event("startup")
async def startup():
    await init_db()

# Pydantic models
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    session_id: str
    message: str

class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class HealthMetricRequest(BaseModel):
    metric_type: str
    value: float
    notes: Optional[str] = ""

class ReminderRequest(BaseModel):
    title: str
    description: Optional[str] = ""
    reminder_type: str
    scheduled_time: str

class ProfileRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    conditions: Optional[str] = None
    medications: Optional[str] = None
    allergies: Optional[str] = None
    avatar: Optional[str] = None

class SettingsRequest(BaseModel):
    unitSystem: Optional[str] = None
    timezone: Optional[str] = None
    dateFormat: Optional[str] = None

class GoalRequest(BaseModel):
    goal_type: str
    title: str
    description: Optional[str] = ""
    target_value: float
    unit: str
    start_date: str
    end_date: Optional[str] = None

class GoalProgressRequest(BaseModel):
    goal_id: int
    date: str
    value: float
    notes: Optional[str] = ""

# Routes
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/register")
async def register(req: RegisterRequest):
    """Register a new user"""
    try:
        user_id = await create_user(req.username, req.email, req.password)
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username or email already exists"
            )
        
        access_token = create_access_token(
            data={"sub": str(user_id), "username": req.username}
        )
        return JSONResponse({
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": user_id,
            "username": req.username,
            "email": req.email
        })
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )

@app.post("/api/login")
async def login(req: LoginRequest):
    """Login and get access token"""
    try:
        user = await verify_user(req.username, req.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )
        
        access_token = create_access_token(
            data={"sub": str(user["id"]), "username": user["username"]}
        )
        return JSONResponse({
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": user["id"],
            "username": user["username"],
            "email": user.get("email", "")
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )

@app.post("/api/chat")
async def chat(req: ChatRequest, current_user: dict = Depends(get_current_user)):
    """Synchronous chat endpoint"""
    try:
        user_id = current_user["user_id"]
        session_id = await get_or_create_session(req.session_id, user_id)
        
        # Get conversation history
        convo = await get_messages(session_id)
        convo.append({"role": "user", "content": req.message})
        
        # Save user message
        await save_message(session_id, "user", req.message)
        
        # Generate response
        print(f"Generating response for user {user_id}, session {session_id}")
        reply = await generate(convo)
        print(f"Generated reply: {reply[:100]}...")
        
        # Save assistant message
        await save_message(session_id, "assistant", reply)
        
        return JSONResponse({"reply": reply})
    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat error: {str(e)}"
        )

@app.get("/api/chat/stream")
async def chat_stream(session_id: str, q: str, current_user: dict = Depends(get_current_user)):
    """Streaming chat endpoint"""
    try:
        user_id = current_user["user_id"]
        session_id = await get_or_create_session(session_id, user_id)
        
        convo = await get_messages(session_id)
        convo.append({"role": "user", "content": q})
        await save_message(session_id, "user", q)
        
        full_reply = ""
        
        async def token_gen():
            nonlocal full_reply
            async for token in stream_generate(convo):
                full_reply += token
                yield token
            await save_message(session_id, "assistant", full_reply)
            yield "[[END]]"
        
        return StreamingResponse(token_gen(), media_type="text/plain")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Streaming error: {str(e)}"
        )

@app.websocket("/ws")
async def ws_chat(websocket: WebSocket):
    """WebSocket chat endpoint"""
    await websocket.accept()
    user_id = None
    
    try:
        # Always require authentication via message (more reliable)
        print("WebSocket connected, waiting for authentication...")
        import asyncio
        
        # Wait for auth message with timeout
        try:
            data = await asyncio.wait_for(websocket.receive_json(), timeout=10.0)
        except asyncio.TimeoutError:
            print("✗ WebSocket auth timeout")
            await websocket.send_json({"type": "error", "message": "Authentication timeout"})
            return
        
        # Handle authentication
        if data.get("type") == "auth":
            token = data.get("token")
            if not token:
                # Try query params as fallback
                token = websocket.query_params.get("token")
            
            if token:
                try:
                    payload = verify_token_string(token)
                    user_id = payload.get("sub")
                    # Ensure user_id is int
                    if isinstance(user_id, str):
                        user_id = int(user_id)
                    print(f"✓ WebSocket authenticated, user_id: {user_id}")
                    await websocket.send_json({"type": "auth_success", "user_id": user_id})
                except Exception as e:
                    print(f"✗ WebSocket auth failed: {e}")
                    import traceback
                    traceback.print_exc()
                    await websocket.send_json({"type": "auth_error", "message": f"Invalid token: {str(e)}"})
                    return
            else:
                await websocket.send_json({"type": "auth_error", "message": "No token provided"})
                return
        else:
            # First message is not auth, might be chat message (if token was in query params)
            # Try to authenticate from query params
            auth_token = websocket.query_params.get("token")
            if auth_token:
                try:
                    payload = verify_token_string(auth_token)
                    user_id = payload.get("sub")
                    # Ensure user_id is int
                    if isinstance(user_id, str):
                        user_id = int(user_id)
                    print(f"✓ WebSocket authenticated via query param, user_id: {user_id}")
                except Exception as e:
                    print(f"✗ WebSocket query param auth failed: {e}")
                    await websocket.send_json({"type": "error", "message": "Authentication required"})
                    return
            else:
                await websocket.send_json({"type": "error", "message": "Authentication required. Please send auth message first."})
                return
        
        # Verify we have user_id
        if not user_id:
            await websocket.send_json({"type": "error", "message": "Authentication required"})
            return
        
        # Main message loop
        # Process the first message if it was a chat message
        if data.get("type") != "auth" and data.get("session_id") and data.get("message"):
            # This was a chat message, process it
            session_id = data.get("session_id")
            message = data.get("message")
            session_id = await get_or_create_session(session_id, user_id)
            convo = await get_messages(session_id)
            convo.append({"role": "user", "content": message})
            await save_message(session_id, "user", message)
            
            full_reply = ""
            try:
                async for token in stream_generate(convo):
                    full_reply += token
                    await websocket.send_json({"type": "token", "content": token})
                await save_message(session_id, "assistant", full_reply)
                await websocket.send_json({"type": "end"})
            except Exception as e:
                print(f"Error generating response: {e}")
                await websocket.send_json({"type": "error", "message": f"Error generating response: {str(e)}"})
        
        # Continue with normal message loop
        while True:
            data = await websocket.receive_json()
            
            # Skip auth messages if already authenticated
            if data.get("type") == "auth":
                continue
            
            session_id = data.get("session_id")
            message = data.get("message")
            
            if not session_id or not message:
                await websocket.send_json({"type": "error", "message": "Missing session_id or message"})
                continue
            
            session_id = await get_or_create_session(session_id, user_id)
            
            convo = await get_messages(session_id)
            convo.append({"role": "user", "content": message})
            await save_message(session_id, "user", message)
            
            full_reply = ""
            try:
                async for token in stream_generate(convo):
                    full_reply += token
                    await websocket.send_json({"type": "token", "content": token})
                
                await save_message(session_id, "assistant", full_reply)
                await websocket.send_json({"type": "end"})
            except Exception as e:
                print(f"Error generating response: {e}")
                await websocket.send_json({"type": "error", "message": f"Error generating response: {str(e)}"})
            
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass

@app.get("/api/sessions")
async def get_sessions(current_user: dict = Depends(get_current_user)):
    """Get all sessions for current user"""
    try:
        sessions = await get_user_sessions(current_user["user_id"])
        return JSONResponse({"sessions": sessions})
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.get("/api/health/metrics")
async def get_metrics(
    metric_type: Optional[str] = None,
    days: int = 30,
    current_user: dict = Depends(get_current_user)
):
    """Get health metrics"""
    try:
        metrics = await get_health_metrics(current_user["user_id"], metric_type, days)
        return JSONResponse({"metrics": metrics})
    except Exception as e:
        print(f"Error in get_metrics endpoint: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving metrics: {str(e)}"
        )

@app.post("/api/health/metrics")
async def add_metric(req: HealthMetricRequest, current_user: dict = Depends(get_current_user)):
    """Add a health metric"""
    try:
        await add_health_metric(
            current_user["user_id"],
            req.metric_type,
            req.value,
            req.notes
        )
        return JSONResponse({"status": "success"})
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.get("/api/reminders")
async def get_user_reminders(current_user: dict = Depends(get_current_user)):
    """Get user reminders"""
    try:
        reminders = await get_reminders(current_user["user_id"])
        return JSONResponse({"reminders": reminders})
    except Exception as e:
        print(f"Error in get_user_reminders endpoint: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving reminders: {str(e)}"
        )

@app.post("/api/reminders")
async def create_user_reminder(req: ReminderRequest, current_user: dict = Depends(get_current_user)):
    """Create a reminder"""
    try:
        await create_reminder(
            current_user["user_id"],
            req.title,
            req.description,
            req.reminder_type,
            req.scheduled_time
        )
        return JSONResponse({"status": "success"})
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.get("/api/analytics")
async def get_analytics(current_user: dict = Depends(get_current_user)):
    """Get health analytics"""
    try:
        user_id = current_user["user_id"]
        
        # Get metrics for last 30 days
        all_metrics = await get_health_metrics(user_id, days=30)
        
        # Calculate statistics
        metrics_by_type = {}
        for metric in all_metrics:
            mtype = metric["metric_type"]
            if mtype not in metrics_by_type:
                metrics_by_type[mtype] = []
            try:
                value = float(metric["value"])
                metrics_by_type[mtype].append(value)
            except (ValueError, TypeError):
                continue
        
        analytics = {}
        for mtype, values in metrics_by_type.items():
            if values:
                analytics[mtype] = {
                    "count": len(values),
                    "average": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                    "latest": values[0] if values else None
                }
        
        reminders = await get_reminders(user_id)
        
        return JSONResponse({
            "metrics": analytics,
            "reminder_count": len(reminders),
            "active_reminders": len([r for r in reminders if r.get("is_active", 1)])
        })
    except Exception as e:
        print(f"Error in get_analytics endpoint: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving analytics: {str(e)}"
        )

@app.get("/api/profile")
async def get_profile(current_user: dict = Depends(get_current_user)):
    """Get user profile"""
    try:
        user_id = current_user["user_id"]
        profile = await get_user_profile(user_id)
        if profile:
            return JSONResponse(profile)
        return JSONResponse({
            "user_id": user_id,
            "username": current_user.get("username"),
            "email": None
        })
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving profile: {str(e)}"
        )

@app.post("/api/profile")
async def update_profile(req: ProfileRequest, current_user: dict = Depends(get_current_user)):
    """Update user profile"""
    try:
        user_id = current_user["user_id"]
        profile_data = req.dict(exclude_none=True)
        await save_user_profile(user_id, profile_data)
        return JSONResponse({"status": "success"})
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating profile: {str(e)}"
        )

@app.get("/api/settings")
async def get_settings(current_user: dict = Depends(get_current_user)):
    """Get user settings"""
    try:
        user_id = current_user["user_id"]
        settings = await get_user_settings(user_id)
        if settings:
            return JSONResponse({
                "unitSystem": settings.get("unit_system", "metric"),
                "timezone": settings.get("timezone"),
                "dateFormat": settings.get("date_format", "MM/DD/YYYY")
            })
        return JSONResponse({
            "unitSystem": "metric",
            "timezone": None,
            "dateFormat": "MM/DD/YYYY"
        })
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving settings: {str(e)}"
        )

@app.post("/api/settings")
async def update_settings(req: SettingsRequest, current_user: dict = Depends(get_current_user)):
    """Update user settings"""
    try:
        user_id = current_user["user_id"]
        settings_data = req.dict(exclude_none=True)
        await save_user_settings(user_id, settings_data)
        return JSONResponse({"status": "success"})
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating settings: {str(e)}"
        )

# Goals endpoints
@app.get("/api/goals")
async def get_goals(active_only: bool = True, current_user: dict = Depends(get_current_user)):
    """Get user goals"""
    try:
        user_id = current_user["user_id"]
        goals = await get_user_goals(user_id, active_only)
        # Calculate progress for each goal
        goals_with_progress = []
        for goal in goals:
            progress = await calculate_goal_progress(goal["id"])
            goal_dict = dict(goal)
            if progress:
                goal_dict.update(progress)
            goals_with_progress.append(goal_dict)
        return JSONResponse({"goals": goals_with_progress})
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving goals: {str(e)}"
        )

@app.post("/api/goals")
async def create_user_goal(req: GoalRequest, current_user: dict = Depends(get_current_user)):
    """Create a new goal"""
    try:
        user_id = current_user["user_id"]
        goal_id = await create_goal(
            user_id, req.goal_type, req.title, req.description,
            req.target_value, req.unit, req.start_date, req.end_date
        )
        return JSONResponse({"status": "success", "goal_id": goal_id})
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating goal: {str(e)}"
        )

@app.put("/api/goals/{goal_id}")
async def update_user_goal(goal_id: int, req: Request, current_user: dict = Depends(get_current_user)):
    """Update a goal"""
    try:
        user_id = current_user["user_id"]
        req_data = await req.json()
        success = await update_goal(goal_id, user_id, **req_data)
        if success:
            return JSONResponse({"status": "success"})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid update")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating goal: {str(e)}"
        )

@app.delete("/api/goals/{goal_id}")
async def delete_user_goal(goal_id: int, current_user: dict = Depends(get_current_user)):
    """Delete a goal"""
    try:
        user_id = current_user["user_id"]
        success = await delete_goal(goal_id, user_id)
        if success:
            return JSONResponse({"status": "success"})
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting goal: {str(e)}"
        )

@app.post("/api/goals/progress")
async def add_progress(req: GoalProgressRequest, current_user: dict = Depends(get_current_user)):
    """Add progress to a goal"""
    try:
        await add_goal_progress(req.goal_id, req.date, req.value, req.notes)
        # Update goal current value
        progress = await calculate_goal_progress(req.goal_id)
        if progress and progress.get("is_completed"):
            await update_goal(req.goal_id, current_user["user_id"], 
                             completed_at=datetime.now().isoformat(), is_active=0)
        return JSONResponse({"status": "success"})
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding progress: {str(e)}"
        )

@app.get("/api/goals/{goal_id}/progress")
async def get_progress(goal_id: int, days: int = 30, current_user: dict = Depends(get_current_user)):
    """Get progress for a goal"""
    try:
        progress_entries = await get_goal_progress(goal_id, days)
        progress_calc = await calculate_goal_progress(goal_id)
        return JSONResponse({
            "progress": progress_entries,
            "summary": progress_calc
        })
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving progress: {str(e)}"
        )

@app.get("/api/reports")
async def get_health_report(period: str = "week", current_user: dict = Depends(get_current_user)):
    """Generate health report"""
    try:
        user_id = current_user["user_id"]
        days = 7 if period == "week" else 30
        
        # Get metrics
        metrics = await get_health_metrics(user_id, days=days)
        reminders = await get_reminders(user_id)
        goals = await get_user_goals(user_id, active_only=True)
        
        # Calculate trends
        metrics_by_type = {}
        for metric in metrics:
            mtype = metric["metric_type"]
            if mtype not in metrics_by_type:
                metrics_by_type[mtype] = []
            try:
                metrics_by_type[mtype].append(float(metric["value"]))
            except (ValueError, TypeError):
                continue
        
        trends = {}
        for mtype, values in metrics_by_type.items():
            if len(values) >= 2:
                first_half = values[:len(values)//2]
                second_half = values[len(values)//2:]
                avg_first = sum(first_half) / len(first_half)
                avg_second = sum(second_half) / len(second_half)
                change = ((avg_second - avg_first) / avg_first * 100) if avg_first > 0 else 0
                trends[mtype] = {
                    "change_percent": round(change, 1),
                    "trend": "improving" if change > 0 else "declining" if change < 0 else "stable"
                }
        
        # Goal progress
        goal_summaries = []
        for goal in goals[:5]:  # Top 5 goals
            progress = await calculate_goal_progress(goal["id"])
            if progress:
                goal_summaries.append({
                    "title": goal["title"],
                    "progress_percent": progress["progress_percent"],
                    "is_completed": progress["is_completed"]
                })
        
        return JSONResponse({
            "period": period,
            "days": days,
            "metrics_count": len(metrics),
            "reminders_count": len(reminders),
            "active_goals": len(goals),
            "trends": trends,
            "goal_summaries": goal_summaries,
            "generated_at": datetime.now().isoformat()
        })
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating report: {str(e)}"
        )

# run: uvicorn app:app --reload
