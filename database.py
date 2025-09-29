import sqlite3
from datetime import datetime


class Database:
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Таблица для заметок
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                tags TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                parent_id INTEGER,
                FOREIGN KEY (parent_id) REFERENCES notes (id)
            )
        ''')

        # Таблица для связей между заметками
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS note_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_note_id INTEGER,
                to_note_id INTEGER,
                FOREIGN KEY (from_note_id) REFERENCES notes (id),
                FOREIGN KEY (to_note_id) REFERENCES notes (id)
            )
        ''')

        conn.commit()
        conn.close()

    def add_note(self, user_id, title, content, tags="", parent_id=None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO notes (user_id, title, content, tags, parent_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, title, content, tags, parent_id))

        note_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return note_id

    def get_note(self, note_id, user_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM notes WHERE id = ? AND user_id = ?
        ''', (note_id, user_id))

        note = cursor.fetchone()
        conn.close()
        return note

    def get_user_notes(self, user_id, limit=50):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, title, created_at FROM notes 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT ?
        ''', (user_id, limit))

        notes = cursor.fetchall()
        conn.close()
        return notes

    def search_notes(self, user_id, query):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, title, content, tags FROM notes 
            WHERE user_id = ? AND (
                title LIKE ? OR content LIKE ? OR tags LIKE ?
            )
        ''', (user_id, f'%{query}%', f'%{query}%', f'%{query}%'))

        notes = cursor.fetchall()
        conn.close()
        return notes

    def add_link(self, from_note_id, to_note_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO note_links (from_note_id, to_note_id)
            VALUES (?, ?)
        ''', (from_note_id, to_note_id))

        conn.commit()
        conn.close()

    def get_linked_notes(self, note_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT n.id, n.title FROM notes n
            JOIN note_links nl ON n.id = nl.to_note_id
            WHERE nl.from_note_id = ?
            UNION
            SELECT n.id, n.title FROM notes n
            JOIN note_links nl ON n.id = nl.from_note_id
            WHERE nl.to_note_id = ?
        ''', (note_id, note_id))

        links = cursor.fetchall()
        conn.close()
        return links