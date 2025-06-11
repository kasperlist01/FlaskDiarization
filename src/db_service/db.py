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

            # Таблица для хранения деталей транскрипции (с временными метками)
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS transcription_details (
                task_id TEXT PRIMARY KEY,
                details TEXT,
                completed_at TEXT,
                FOREIGN KEY (task_id) REFERENCES tasks(task_id)
            )
            ''')

            # Таблица для хранения результатов диаризации
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS diarization_results (
                task_id TEXT PRIMARY KEY,
                result TEXT,
                completed_at TEXT,
                FOREIGN KEY (task_id) REFERENCES tasks(task_id)
            )
            ''')

            # Таблица для хранения саммари
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                summary TEXT,
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

    def save_transcription_details(self, task_id, details):
        """Сохранение деталей транскрибации с временными метками"""
        now = datetime.now().isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            INSERT OR REPLACE INTO transcription_details (task_id, details, completed_at)
            VALUES (?, ?, ?)
            ''', (task_id, json.dumps(details), now))

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

    def get_transcription_details(self, task_id):
        """Получение деталей транскрипции с временными метками"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            SELECT details, completed_at
            FROM transcription_details
            WHERE task_id = ?
            ''', (task_id,))

            row = cursor.fetchone()
            if not row:
                return None

            result = dict(row)
            if result['details']:
                result['details'] = json.loads(result['details'])
            return result['details']

    def save_diarization_result(self, task_id, result):
        """Сохранение результата диаризации (определения говорящих)"""
        now = datetime.now().isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            INSERT OR REPLACE INTO diarization_results (task_id, result, completed_at)
            VALUES (?, ?, ?)
            ''', (task_id, json.dumps(result), now))

            conn.commit()

    def get_diarization_result(self, task_id):
        """Получение результата диаризации по ID задачи"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            SELECT result, completed_at
            FROM diarization_results
            WHERE task_id = ?
            ''', (task_id,))

            row = cursor.fetchone()
            if not row:
                return None

            result = dict(row)
            if result['result']:
                result['result'] = json.loads(result['result'])
            return result['result']

    def save_summary(self, task_id, summary):
        """Сохранение саммари"""
        now = datetime.now().isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            INSERT INTO summaries (task_id, summary, completed_at)
            VALUES (?, ?, ?)
            ''', (task_id, summary, now))

            conn.commit()

    def get_summary(self, task_id):
        """Получение саммари по ID задачи"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            SELECT summary, completed_at
            FROM summaries
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

        transcription_details = self.get_transcription_details(task_id)
        if transcription_details:
            task_info['transcription_details'] = transcription_details

        diarization_result = self.get_diarization_result(task_id)
        if diarization_result:
            task_info['diarization_result'] = diarization_result

        summary = self.get_summary(task_id)
        if summary:
            task_info['summary'] = summary

        return task_info

    def get_all_tasks(self, limit=10, offset=0, status=None):
        """Получение списка всех задач с пагинацией"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = '''
            SELECT task_id, status, created_at, updated_at, file_path
            FROM tasks
            '''
            params = []

            if status:
                query += ' WHERE status = ?'
                params.append(status)

            query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
            params.extend([limit, offset])

            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def count_tasks(self, status=None):
        """Подсчет общего количества задач"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = 'SELECT COUNT(*) as count FROM tasks'
            params = []

            if status:
                query += ' WHERE status = ?'
                params.append(status)

            cursor.execute(query, params)
            result = cursor.fetchone()
            return result['count'] if result else 0

    def delete_task(self, task_id):
        """Удаление задачи и всех связанных данных"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Удаляем связанные данные
            tables = [
                'transcriptions',
                'transcription_details',
                'diarization_results',
                'summaries'
            ]

            for table in tables:
                cursor.execute(f'DELETE FROM {table} WHERE task_id = ?', (task_id,))

            # Удаляем саму задачу
            cursor.execute('DELETE FROM tasks WHERE task_id = ?', (task_id,))

            conn.commit()
            return cursor.rowcount > 0