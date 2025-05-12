import os
import uuid
import logging
from datetime import datetime

from src.db_service.db import DatabaseService
from src.db_service.models import TaskStatus

# Импортируем наш сервис базы данных

# Настройка логирования
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('TaskManager')


class TaskManager:
    """Менеджер задач для управления процессом транскрибации"""

    def __init__(self, db_service=None, upload_dir='uploads'):
        """
        Инициализация менеджера задач

        Args:
            db_service: Экземпляр сервиса базы данных
            upload_dir: Директория для хранения загруженных файлов
        """
        self.db = db_service or DatabaseService()
        self.upload_dir = upload_dir

        # Создаем директорию для загрузок, если она не существует
        os.makedirs(self.upload_dir, exist_ok=True)

    def create_task(self, audio_file, options=None):
        """
        Создает новую задачу транскрибации

        Args:
            audio_file: Файловый объект с аудио
            options: Словарь с опциями транскрибации

        Returns:
            task_id: Идентификатор созданной задачи
        """
        # Генерируем уникальный ID задачи
        task_id = str(uuid.uuid4())

        # Сохраняем аудиофайл
        filename = f"{task_id}_{os.path.basename(audio_file.filename)}"
        file_path = os.path.join(self.upload_dir, filename)

        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        audio_file.save(file_path)

        logger.info(f"Created task {task_id}, saved file to {file_path}")

        # Сохраняем информацию о задаче в БД
        self.db.save_task(
            task_id=task_id,
            status=TaskStatus.PENDING.value,
            file_path=file_path,
            options=options
        )

        return task_id

    def update_task_status(self, task_id, status):
        """
        Обновляет статус задачи

        Args:
            task_id: Идентификатор задачи
            status: Новый статус (из TaskStatus)

        Returns:
            bool: True если обновление успешно, False в противном случае
        """
        # Проверяем, что статус валидный
        if isinstance(status, TaskStatus):
            status = status.value

        logger.info(f"Updating task {task_id} status to {status}")
        return self.db.update_task_status(task_id, status)

    def get_task(self, task_id):
        """
        Получает информацию о задаче

        Args:
            task_id: Идентификатор задачи

        Returns:
            dict: Информация о задаче или None, если задача не найдена
        """
        return self.db.get_task(task_id)

    def get_full_task_info(self, task_id):
        """
        Получает полную информацию о задаче, включая транскрипцию и отчеты

        Args:
            task_id: Идентификатор задачи

        Returns:
            dict: Полная информация о задаче
        """
        return self.db.get_task_full_info(task_id)