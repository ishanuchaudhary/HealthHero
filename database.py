import sqlite3
import aiosqlite
from datetime import datetime
from typing import List, Dict, Optional
import hashlib
import secrets

DB_PATH = "healthhero.db"

async def init_db():
    """Initialize database tables"""
    async with aiosqlite.connect(DB_PATH) as db:
        # Users table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Sessions table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # Messages table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)
        
        # Health tracking table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS health_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                metric_type TEXT NOT NULL,
                value REAL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # Reminders table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                reminder_type TEXT NOT NULL,
                scheduled_time TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # User profiles table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                email TEXT,
                age INTEGER,
                gender TEXT,
                height REAL,
                weight REAL,
                conditions TEXT,
                medications TEXT,
                allergies TEXT,
                avatar TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # User settings table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                unit_system TEXT DEFAULT 'metric',
                timezone TEXT,
                date_format TEXT DEFAULT 'MM/DD/YYYY',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # Goals table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                goal_type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                target_value REAL NOT NULL,
                current_value REAL DEFAULT 0,
                unit TEXT,
                start_date TEXT NOT NULL,
                end_date TEXT,
                is_active INTEGER DEFAULT 1,
                completed_at TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # Goal progress tracking table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS goal_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                value REAL NOT NULL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (goal_id) REFERENCES goals(id)
            )
        """)
        
        await db.commit()

async def hash_password(password: str) -> str:
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

async def create_user(username: str, email: str, password: str) -> Optional[int]:
    """Create a new user"""
    try:
        password_hash = await hash_password(password)
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                (username, email, password_hash)
            )
            await db.commit()
            return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None

async def verify_user(username: str, password: str) -> Optional[Dict]:
    """Verify user credentials"""
    password_hash = await hash_password(password)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, username, email FROM users WHERE username = ? AND password_hash = ?",
            (username, password_hash)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"id": row[0], "username": row[1], "email": row[2]}
    return None

async def get_or_create_session(session_id: str, user_id: Optional[int] = None) -> str:
    """Get or create a session"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id FROM sessions WHERE id = ?", (session_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                await db.execute(
                    "INSERT INTO sessions (id, user_id) VALUES (?, ?)",
                    (session_id, user_id)
                )
                await db.commit()
            else:
                await db.execute(
                    "UPDATE sessions SET updated_at = ? WHERE id = ?",
                    (datetime.now().isoformat(), session_id)
                )
                await db.commit()
    return session_id

async def save_message(session_id: str, role: str, content: str):
    """Save a message to the database"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content)
        )
        await db.commit()

async def get_messages(session_id: str) -> List[Dict[str, str]]:
    """Get all messages for a session"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [{"role": row["role"], "content": row["content"]} for row in rows]

async def add_health_metric(user_id: int, metric_type: str, value: float, notes: str = ""):
    """Add a health tracking metric"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO health_tracking (user_id, metric_type, value, notes) VALUES (?, ?, ?, ?)",
            (user_id, metric_type, value, notes)
        )
        await db.commit()

async def get_health_metrics(user_id: int, metric_type: Optional[str] = None, days: int = 30) -> List[Dict]:
    """Get health metrics for a user"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = """
            SELECT metric_type, value, notes, created_at 
            FROM health_tracking 
            WHERE user_id = ? AND datetime(created_at) >= datetime('now', '-' || ? || ' days')
        """
        params = [user_id, str(days)]
        if metric_type:
            query += " AND metric_type = ?"
            params.append(metric_type)
        query += " ORDER BY created_at DESC"
        
        try:
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            print(f"Error getting health metrics: {e}")
            return []

async def create_reminder(user_id: int, title: str, description: str, reminder_type: str, scheduled_time: str):
    """Create a reminder"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO reminders (user_id, title, description, reminder_type, scheduled_time) VALUES (?, ?, ?, ?, ?)",
            (user_id, title, description, reminder_type, scheduled_time)
        )
        await db.commit()

async def get_reminders(user_id: int, active_only: bool = True) -> List[Dict]:
    """Get reminders for a user"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT id, title, description, reminder_type, scheduled_time, is_active FROM reminders WHERE user_id = ?"
        if active_only:
            query += " AND is_active = 1"
        query += " ORDER BY scheduled_time ASC"
        
        async with db.execute(query, (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def get_user_sessions(user_id: int) -> List[Dict]:
    """Get all sessions for a user"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, created_at, updated_at FROM sessions WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def get_user_profile(user_id: int) -> Optional[Dict]:
    """Get user profile"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM user_profiles WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
    return None

async def save_user_profile(user_id: int, profile_data: Dict):
    """Save or update user profile"""
    async with aiosqlite.connect(DB_PATH) as db:
        # Check if profile exists
        async with db.execute(
            "SELECT user_id FROM user_profiles WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            exists = await cursor.fetchone()
        
        if exists:
            await db.execute("""
                UPDATE user_profiles 
                SET username = ?, email = ?, age = ?, gender = ?, height = ?, 
                    weight = ?, conditions = ?, medications = ?, allergies = ?, 
                    avatar = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (
                profile_data.get("username"),
                profile_data.get("email"),
                profile_data.get("age"),
                profile_data.get("gender"),
                profile_data.get("height"),
                profile_data.get("weight"),
                profile_data.get("conditions"),
                profile_data.get("medications"),
                profile_data.get("allergies"),
                profile_data.get("avatar"),
                user_id
            ))
        else:
            await db.execute("""
                INSERT INTO user_profiles 
                (user_id, username, email, age, gender, height, weight, 
                 conditions, medications, allergies, avatar)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                profile_data.get("username"),
                profile_data.get("email"),
                profile_data.get("age"),
                profile_data.get("gender"),
                profile_data.get("height"),
                profile_data.get("weight"),
                profile_data.get("conditions"),
                profile_data.get("medications"),
                profile_data.get("allergies"),
                profile_data.get("avatar")
            ))
        await db.commit()

async def get_user_settings(user_id: int) -> Optional[Dict]:
    """Get user settings"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM user_settings WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
    return None

async def save_user_settings(user_id: int, settings_data: Dict):
    """Save or update user settings"""
    async with aiosqlite.connect(DB_PATH) as db:
        # Check if settings exist
        async with db.execute(
            "SELECT user_id FROM user_settings WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            exists = await cursor.fetchone()
        
        if exists:
            await db.execute("""
                UPDATE user_settings 
                SET unit_system = ?, timezone = ?, date_format = ?, 
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (
                settings_data.get("unitSystem"),
                settings_data.get("timezone"),
                settings_data.get("dateFormat"),
                user_id
            ))
        else:
            await db.execute("""
                INSERT INTO user_settings 
                (user_id, unit_system, timezone, date_format)
                VALUES (?, ?, ?, ?)
            """, (
                user_id,
                settings_data.get("unitSystem"),
                settings_data.get("timezone"),
                settings_data.get("dateFormat")
            ))
        await db.commit()

async def get_user_profile(user_id: int) -> Optional[Dict]:
    """Get user profile"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM user_profiles WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
    return None

async def save_user_profile(user_id: int, profile_data: Dict):
    """Save or update user profile"""
    async with aiosqlite.connect(DB_PATH) as db:
        # Check if profile exists
        async with db.execute(
            "SELECT user_id FROM user_profiles WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            exists = await cursor.fetchone()
        
        if exists:
            await db.execute("""
                UPDATE user_profiles 
                SET username = ?, email = ?, age = ?, gender = ?, height = ?, 
                    weight = ?, conditions = ?, medications = ?, allergies = ?, 
                    avatar = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (
                profile_data.get("username"),
                profile_data.get("email"),
                profile_data.get("age"),
                profile_data.get("gender"),
                profile_data.get("height"),
                profile_data.get("weight"),
                profile_data.get("conditions"),
                profile_data.get("medications"),
                profile_data.get("allergies"),
                profile_data.get("avatar"),
                user_id
            ))
        else:
            await db.execute("""
                INSERT INTO user_profiles 
                (user_id, username, email, age, gender, height, weight, 
                 conditions, medications, allergies, avatar)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                profile_data.get("username"),
                profile_data.get("email"),
                profile_data.get("age"),
                profile_data.get("gender"),
                profile_data.get("height"),
                profile_data.get("weight"),
                profile_data.get("conditions"),
                profile_data.get("medications"),
                profile_data.get("allergies"),
                profile_data.get("avatar")
            ))
        await db.commit()

async def get_user_settings(user_id: int) -> Optional[Dict]:
    """Get user settings"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM user_settings WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
    return None

async def save_user_settings(user_id: int, settings_data: Dict):
    """Save or update user settings"""
    async with aiosqlite.connect(DB_PATH) as db:
        # Check if settings exist
        async with db.execute(
            "SELECT user_id FROM user_settings WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            exists = await cursor.fetchone()
        
        if exists:
            await db.execute("""
                UPDATE user_settings 
                SET unit_system = ?, timezone = ?, date_format = ?, 
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (
                settings_data.get("unitSystem"),
                settings_data.get("timezone"),
                settings_data.get("dateFormat"),
                user_id
            ))
        else:
            await db.execute("""
                INSERT INTO user_settings 
                (user_id, unit_system, timezone, date_format)
                VALUES (?, ?, ?, ?)
            """, (
                user_id,
                settings_data.get("unitSystem"),
                settings_data.get("timezone"),
                settings_data.get("dateFormat")
            ))
        await db.commit()



# Goals functions
# Goals functions
async def create_goal(user_id: int, goal_type: str, title: str, description: str, 
                     target_value: float, unit: str, start_date: str, end_date: str = None) -> int:
    """Create a new goal"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO goals 
            (user_id, goal_type, title, description, target_value, unit, start_date, end_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, goal_type, title, description, target_value, unit, start_date, end_date))
        await db.commit()
        return cursor.lastrowid

async def get_user_goals(user_id: int, active_only: bool = True) -> List[Dict]:
    """Get goals for a user"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM goals WHERE user_id = ?"
        params = [user_id]
        if active_only:
            query += " AND is_active = 1"
        query += " ORDER BY created_at DESC"
        
        async with db.execute(query, tuple(params)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def update_goal(goal_id: int, user_id: int, **kwargs) -> bool:
    """Update a goal"""
    allowed_fields = ['title', 'description', 'target_value', 'current_value', 
                     'unit', 'end_date', 'is_active', 'completed_at']
    updates = []
    values = []
    
    for key, value in kwargs.items():
        if key in allowed_fields:
            updates.append(f"{key} = ?")
            values.append(value)
    
    if not updates:
        return False
    
    values.append(goal_id)
    values.append(user_id)
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"""
            UPDATE goals 
            SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
        """, tuple(values))
        await db.commit()
        return True

async def delete_goal(goal_id: int, user_id: int) -> bool:
    """Delete a goal"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM goals WHERE id = ? AND user_id = ?",
            (goal_id, user_id)
        )
        await db.commit()
        return cursor.rowcount > 0

async def add_goal_progress(goal_id: int, date: str, value: float, notes: str = ""):
    """Add progress entry for a goal"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO goal_progress (goal_id, date, value, notes)
            VALUES (?, ?, ?, ?)
        """, (goal_id, date, value, notes))
        await db.commit()

async def get_goal_progress(goal_id: int, days: int = 30) -> List[Dict]:
    """Get progress entries for a goal"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM goal_progress 
            WHERE goal_id = ? 
            AND date >= date('now', '-' || ? || ' days')
            ORDER BY date ASC
        """, (goal_id, str(days))) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def calculate_goal_progress(goal_id: int) -> Dict:
    """Calculate current progress for a goal"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Get goal
        async with db.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)) as cursor:
            goal = await cursor.fetchone()
            if not goal:
                return None
            goal_dict = dict(goal)
        
        # Get total progress from progress entries
        async with db.execute("""
            SELECT SUM(value) as total FROM goal_progress WHERE goal_id = ?
        """, (goal_id,)) as cursor:
            row = await cursor.fetchone()
            total_progress = row[0] if row and row[0] else 0
        
        target = goal_dict['target_value']
        current = goal_dict['current_value'] + total_progress
        progress_percent = min(100, (current / target * 100) if target > 0 else 0)
        
        return {
            'goal_id': goal_id,
            'current_value': current,
            'target_value': target,
            'progress_percent': progress_percent,
            'remaining': max(0, target - current),
            'is_completed': current >= target
        }

