import sqlite3

def create_db_table():
    conn = sqlite3.connect("pia_database.db")
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dependencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dependency_name TEXT,
            metric1 TEXT,
            metric2 TEXT,
            metric3 TEXT,
            metric4 TEXT,
            metric5 TEXT,
            metric6 TEXT,
            pia_score TEXT
        )
    ''')

    conn.commit()
    conn.close()

def insert_dependency(dependency_name, result_string1, result_string2, result_string3,
        result_string4, result_string5, result_string6, pia_score):
    conn = sqlite3.connect("pia_database.db")
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO dependencies (
            dependency_name,
            metric1, metric2, metric3, metric4, metric5, metric6,
            pia_score
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        dependency_name,
        result_string1, result_string2, result_string3,
        result_string4, result_string5, result_string6,
        pia_score
    ))

    conn.commit()
    conn.close()

def retrieve_all_dependencies():
    conn = sqlite3.connect("pia_database.db")
    cursor = conn.cursor()

    cursor.execute('''
        SELECT dependency_name, metric1, metric2, metric3,
        metric4, metric5, metric6, pia_score FROM dependencies
    ''')

    dependencies = cursor.fetchall()

    conn.close()

    return dependencies
