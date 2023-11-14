import sqlite3

def create_db_table():
    conn = sqlite3.connect("pia_database.db")
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dependencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dependency_name TEXT,
            version TEXT,
            pia_score INTEGER
        )
    ''')

    conn.commit()
    conn.close()

def insert_dependency(dependency_name, version, pia_score):
    conn = sqlite3.connect("pia_database.db")
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO dependencies (dependency_name, version, pia_score)
        VALUES (?, ?, ?)
    ''', (dependency_name, version, pia_score))

    conn.commit()
    conn.close()

def retrieve_all_dependencies():
    conn = sqlite3.connect("pia_database.db")
    cursor = conn.cursor()

    cursor.execute('''
        SELECT dependency_name, version, pia_score FROM dependencies
    ''')

    dependencies = cursor.fetchall()

    conn.close()

    return dependencies
