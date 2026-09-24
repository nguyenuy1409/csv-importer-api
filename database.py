import sqlite3

DB_NAME = "data.db"

def get_connection():
    # Function to open and return the connection to SQLite file
    conn = sqlite3.connect(DB_NAME)
    # Help extract date based on columns name instead of index 
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            age INTEGER
    );
""")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS imported_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            checksum TEXT UNIQUE NOT NULL,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit();
    conn.close();

if __name__ == "__main__":
    init_db()