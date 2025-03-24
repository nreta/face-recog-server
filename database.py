import sqlite3

# Connect to SQLite database (or create it if it doesn't exist)
conn = sqlite3.connect('employees.db')
cursor = conn.cursor()

# Create a table to store employee faces
cursor.execute('''
CREATE TABLE IF NOT EXISTS employee_faces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    image BLOB NOT NULL,
    face_encoding BLOB NOT NULL
)
''')


conn.commit()
conn.close()