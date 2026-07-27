import sqlite3

conn = sqlite3.connect(r'data\legal_rag.db')
cur = conn.cursor()
try:
    cur.execute("DROP TABLE alembic_version")
    print("Dropped alembic_version")
except Exception as e:
    print("alembic_version error:", e)

try:
    cur.execute("DROP TABLE users")
    print("Dropped users")
except Exception as e:
    print("users error:", e)
    
try:
    cur.execute("CREATE TABLE conversations_backup AS SELECT id, title, created_at FROM conversations")
    cur.execute("DROP TABLE conversations")
    cur.execute('''
    CREATE TABLE conversations (
        id VARCHAR NOT NULL, 
        title VARCHAR, 
        created_at DATETIME, 
        PRIMARY KEY (id)
    )''')
    cur.execute("INSERT INTO conversations SELECT * FROM conversations_backup")
    cur.execute("DROP TABLE conversations_backup")
    print("Restored conversations schema")
except Exception as e:
    print("conversations error:", e)

conn.commit()
conn.close()
