import sqlite3
import json
import os
from datetime import datetime
from contextlib import contextmanager


class DatabaseService:
    """Сервис для работы с SQLite базой данных"""

    def __init__(self, db_path="transcription.db"):
        """Инициализация сервиса базы данных"""
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Инициализация структуры базы данных"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Таблица задач
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                file_path TEXT,
                options TEXT
            )
            ''')

            # Таблица для хранения результатов транскрибации
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS transcriptions (
                task_id TEXT PRIMARY KEY,
                transcript TEXT,
                completed_at TEXT,
                FOREIGN KEY (task_id) REFERENCES tasks(task_id)
            )
            ''')

            # Таблица для хранения саммари
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                chunk_index INTEGER,
                summary TEXT,
                completed_at TEXT,
                FOREIGN KEY (task_id) REFERENCES tasks(task_id)
            )
            ''')

            # Таблица для хранения финального отчета
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS final_reports (
                task_id TEXT PRIMARY KEY,
                report TEXT,
                completed_at TEXT,
                FOREIGN KEY (task_id) REFERENCES tasks(task_id)
            )
            ''')

            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Контекстный менеджер для соединения с БД"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def save_task(self, task_id, status, file_path=None, options=None):
        """Сохранение новой задачи или обновление существующей"""
        now = datetime.now().isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Проверяем, существует ли задача
            cursor.execute("SELECT task_id FROM tasks WHERE task_id = ?", (task_id,))
            task_exists = cursor.fetchone() is not None

            if task_exists:
                # Обновляем существующую задачу
                cursor.execute('''
                UPDATE tasks 
                SET status = ?, updated_at = ?, file_path = ?, options = ?
                WHERE task_id = ?
                ''', (status, now, file_path, json.dumps(options) if options else None, task_id))
            else:
                # Создаем новую задачу
                cursor.execute('''
                INSERT INTO tasks (task_id, status, created_at, updated_at, file_path, options)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (task_id, status, now, now, file_path, json.dumps(options) if options else None))

            conn.commit()

    def update_task_status(self, task_id, status):
        """Обновление статуса задачи"""
        now = datetime.now().isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            UPDATE tasks 
            SET status = ?, updated_at = ?
            WHERE task_id = ?
            ''', (status, now, task_id))

            conn.commit()
            return cursor.rowcount > 0

    def get_task(self, task_id):
        """Получение информации о задаче по ID"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            SELECT task_id, status, created_at, updated_at, file_path, options
            FROM tasks
            WHERE task_id = ?
            ''', (task_id,))

            row = cursor.fetchone()
            if not row:
                return None

            task = dict(row)
            if task['options']:
                task['options'] = json.loads(task['options'])

            return task

    def save_transcription(self, task_id, transcript):
        """Сохранение результата транскрибации"""
        now = datetime.now().isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            INSERT OR REPLACE INTO transcriptions (task_id, transcript, completed_at)
            VALUES (?, ?, ?)
            ''', (task_id, transcript, now))

            conn.commit()

    def get_transcription(self, task_id):
        """Получение транскрипции по ID задачи"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            SELECT transcript, completed_at
            FROM transcriptions
            WHERE task_id = ?
            ''', (task_id,))

            row = cursor.fetchone()
            return dict(row) if row else None

    def save_summary_chunk(self, task_id, chunk_index, summary):
        """Сохранение части саммари"""
        now = datetime.now().isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            INSERT INTO summaries (task_id, chunk_index, summary, completed_at)
            VALUES (?, ?, ?, ?)
            ''', (task_id, chunk_index, summary, now))

            conn.commit()

    def get_summary_chunks(self, task_id):
        """Получение всех частей саммари для задачи"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            SELECT chunk_index, summary, completed_at
            FROM summaries
            WHERE task_id = ?
            ORDER BY chunk_index
            ''', (task_id,))

            return [dict(row) for row in cursor.fetchall()]

    def save_final_report(self, task_id, report):
        """Сохранение финального отчета"""
        now = datetime.now().isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            INSERT OR REPLACE INTO final_reports (task_id, report, completed_at)
            VALUES (?, ?, ?)
            ''', (task_id, report, now))

            conn.commit()

    def get_final_report(self, task_id):
        """Получение финального отчета по ID задачи"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            SELECT report, completed_at
            FROM final_reports
            WHERE task_id = ?
            ''', (task_id,))

            row = cursor.fetchone()
            return dict(row) if row else None

    def get_task_full_info(self, task_id):
        """Получение полной информации о задаче, включая транскрипцию и отчет"""
        task_info = self.get_task(task_id)
        if not task_info:
            return None

        transcription = self.get_transcription(task_id)
        if transcription:
            task_info['transcription'] = transcription

        summary_chunks = self.get_summary_chunks(task_id)
        if summary_chunks:
            task_info['summary_chunks'] = summary_chunks

        final_report = self.get_final_report(task_id)
        if final_report:
            task_info['final_report'] = final_report

        return task_info