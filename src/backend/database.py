import sqlite3
from flask import session

# connect to a local SQLite database file (file will be created automatically)
conn = sqlite3.connect("database.sqlite", check_same_thread=False)
cursor = conn.cursor()

# create "user_info" table to store user info and permissions tokens
cursor.execute("""
CREATE TABLE IF NOT EXISTS user_sessions (
    google_id TEXT PRIMARY KEY,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    name TEXT,
    user_email TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    gemini_api_key TEXT
)
""")
conn.commit()

# create "chats" table to map thread_id to google_id
cursor.execute("""
CREATE TABLE IF NOT EXISTS chats (
    thread_id TEXT PRIMARY KEY,
    google_id TEXT NOT NULL,
    chat_name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()

# create "messages" table for UI messages for every thread_id chat
cursor.execute("""
  CREATE TABLE IF NOT EXISTS messages (
  thread_id TEXT NOT NULL,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  message_type TEXT DEFAULT 'regular',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (thread_id) REFERENCES chats(thread_id)
);
""")
conn.commit()

def get_gemini_api_key():
    google_id = session.get("google_id", "")
    if not google_id:
        print("No google id found.")
        return ""
        
    try:
        local_cursor = conn.cursor()
        local_cursor.execute("""
            SELECT gemini_api_key 
            FROM user_sessions 
            WHERE google_id = ?
        """, (google_id,))
        
        row = local_cursor.fetchone()
        local_cursor.close()

        if row:
            gemini_api_key = row[0] if row[0] is not None else ""
            return gemini_api_key
        
        return ""
    except Exception as e:
        print(e)
        return ""

def get_user_info(google_id):
    local_cursor = conn.cursor()
    local_cursor.execute("""
        SELECT google_id, access_token, refresh_token, name, user_email, created_at
        FROM user_sessions
        WHERE google_id = ?
    """, (google_id,))

    # get the result
    user_info = local_cursor.fetchone()
    local_cursor.close()

    print({"google_id": google_id, "access_token": user_info[1], "refresh_token": user_info[2], "name": user_info[3], "user_email": user_info[4], "created_at": user_info[5]})

    if not user_info:
        return {}

    return {"google_id": google_id, "access_token": user_info[1], "refresh_token": user_info[2], "name": user_info[3], "user_email": user_info[4], "created_at": user_info[5]}

def addMessage(thread_id, role, content, message_type="regular"):
    try:
        local_cursor = conn.cursor()
        local_cursor.execute(
            "INSERT INTO messages (thread_id, role, content, message_type) VALUES (?, ?, ?, ?)",
            (thread_id, role, content, message_type)
        )
        conn.commit()
        local_cursor.close()
        return True
    except Exception as e:
        print("Error saving message to db:", e)
        return False