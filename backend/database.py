import sqlite3

def connect_db():
    conn = sqlite3.connect("interview.db")
    return conn

def create_tables():
    conn = connect_db()
    cursor = conn.cursor()

    # Questions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        candidate_id TEXT,
        question TEXT
    )
    """)

    # Results table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS results (
        candidate_id TEXT,
        name TEXT,
        face_emotion TEXT,
        voice_emotion TEXT,
        score REAL,
        decision TEXT
    )
    """)

    conn.commit()
    conn.close() 