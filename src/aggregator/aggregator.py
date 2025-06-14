# src/aggregator/aggregator.py

import logging
import os
import time

from src.db_service.db import DatabaseService
from src.db_service.models import TaskStatus
from src.task_manager.manager import TaskManager
from src.summary_service import SummaryService
from transcriber_service import TranscriberService

# Настройка логирования
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Aggregator')


class TranscriberAggregator:
    """
    Оркестратор процесса транскрибации и создания саммари
    Координирует работу различных сервисов и отслеживает статус задачи
    """

    def __init__(self, db_service=None, task_manager=None,
                 transcriber_service=None, summary_service=None):
        """
        Инициализация оркестратора

        Args:
            db_service: Сервис базы данных
            task_manager: Менеджер задач
            transcriber_service: Сервис транскрибации
            summary_service: Сервис создания саммари
        """
        self.db = db_service or DatabaseService()
        self.task_manager = task_manager or TaskManager(db_service=self.db)
        self.transcriber_service = transcriber_service or TranscriberService()
        self.summary_service = summary_service or SummaryService()

    def process_task(self, task_id):
        """
        Запускает обработку задачи

        Args:
            task_id: Идентификатор задачи

        Returns:
            bool: True если задача успешно обработана, False в противном случае
        """
        logger.info(f"Starting processing task {task_id}")
        return self._process_task_workflow(task_id)

    def _process_task_workflow(self, task_id):
        """
        Основной поток обработки задачи

        Args:
            task_id: Идентификатор задачи

        Returns:
            bool: True если задача успешно обработана, False в противном случае
        """
        try:
            # Получаем информацию о задаче
            task = self.db.get_task(task_id)
            if not task:
                logger.error(f"Task {task_id} not found")
                return False

            # Шаг 1: Транскрибация
            self._run_transcriber(task_id, task['file_path'], task.get('options', {}))

            self.transcriber_service.cleanup()

            # Шаг 2: Диаризация
            self._run_diarization(task_id, task['file_path'], task.get('options', {}))

            self.transcriber_service.cleanup()
            self._cleanup_audio_file(task['file_path'])

            # Шаг 3: Суммаризация
            transcript = self.db.get_diarization_result(task_id)
            if not transcript:
                logger.error(f"Transcription for task {task_id} not found")
                self.task_manager.update_task_status(task_id, TaskStatus.FAILED)
                return False

            self._run_summarization(task_id, transcript['segments'])

            # Отмечаем задачу как завершенную
            self.task_manager.update_task_status(task_id, TaskStatus.COMPLETED)
            logger.info(f"Task {task_id} completed successfully")
            return True

        except Exception as e:
            logger.exception(f"Error processing task {task_id}: {str(e)}")
            self.task_manager.update_task_status(task_id, TaskStatus.FAILED)
            return False

    def _run_transcriber(self, task_id, file_path, options):
        """
        Запускает процесс транскрибации

        Args:
            task_id: Идентификатор задачи
            file_path: Путь к аудиофайлу
            options: Опции транскрибации
        """
        logger.info(f"Starting transcriber for task {task_id}")
        self.task_manager.update_task_status(task_id, TaskStatus.TRANSCRIBING)

        try:
            batch_size = options.get('batch_size', 24)
            language = options.get('language', None)

            result = self.transcriber_service.transcribe(
                file_path,
                batch_size=batch_size,
                language=language
            )

            # Извлекаем полный текст транскрипции из сегментов
            full_transcript = ""
            for segment in result.get("segments", []):
                full_transcript += segment.get("text", "") + " "

            self.db.save_transcription(task_id, full_transcript)

            self.db.save_transcription_details(task_id, result)

            self.task_manager.update_task_status(task_id, TaskStatus.TRANSCRIBED)
            logger.info(f"Transcription completed for task {task_id}")

        except Exception as e:
            logger.exception(f"Error during transcription: {str(e)}")
            self.task_manager.update_task_status(task_id, TaskStatus.FAILED)
            raise

    def _run_diarization(self, task_id, file_path, options):
        """
        Запускает процесс диаризации (определение говорящих)

        Args:
            task_id: Идентификатор задачи
            file_path: Путь к аудиофайлу
            options: Опции диаризации
        """
        logger.info(f"Starting diarization for task {task_id}")

        try:
            transcription_details = self.db.get_transcription_details(task_id)
            if not transcription_details:
                logger.warning(f"No transcription details found for task {task_id}, skipping diarization")
                return

            result_with_speakers = self.transcriber_service.diarize(
                file_path,
                transcription_details,
                # hf_token=''
            )

            # Сохраняем результат диаризации
            self.db.save_diarization_result(task_id, result_with_speakers)

            logger.info(f"Diarization completed for task {task_id}")

        except Exception as e:
            logger.exception(f"Error during diarization: {str(e)}")
            # Не прерываем процесс, если диаризация не удалась
            # Просто логируем ошибку и продолжаем

    def _run_summarization(self, task_id, transcript):
        """
        Запускает процесс создания саммари

        Args:
            task_id: Идентификатор задачи
            transcript: Текст транскрипции
        """
        logger.info(f"Starting summarization for task {task_id}")
        self.task_manager.update_task_status(task_id, TaskStatus.SUMMARIZING)

        try:
            summary = self.summary_service.create_summary(transcript)
            self.db.save_summary(task_id, summary)

            self.task_manager.update_task_status(task_id, TaskStatus.SUMMARIZED)
            logger.info(f"Summarization completed for task {task_id}")

        except Exception as e:
            logger.exception(f"Error during summarization: {str(e)}")
            self.task_manager.update_task_status(task_id, TaskStatus.FAILED)
            raise


    def get_task_progress(self, task_id):
        """
        Получает информацию о прогрессе выполнения задачи

        Args:
            task_id: Идентификатор задачи

        Returns:
            dict: Информация о прогрессе
        """
        task = self.db.get_task(task_id)
        if not task:
            return None

        progress = {
            'task_id': task_id,
            'status': task['status'],
            'created_at': task['created_at'],
            'updated_at': task['updated_at'],
        }

        # Добавляем информацию о завершенных этапах
        if task['status'] not in [TaskStatus.PENDING.value, TaskStatus.TRANSCRIBING.value]:
            transcription = self.db.get_transcription(task_id)
            if transcription:
                progress['transcription_completed'] = transcription['completed_at']

        if task['status'] in [TaskStatus.SUMMARIZED.value, TaskStatus.FINALIZING.value, TaskStatus.COMPLETED.value]:
            summary_chunks = self.db.get_summary_chunks(task_id)
            if summary_chunks:
                progress['summary_chunks_count'] = len(summary_chunks)

        if task['status'] == TaskStatus.COMPLETED.value:
            final_report = self.db.get_final_report(task_id)
            if final_report:
                progress['final_report_completed'] = final_report['completed_at']

        return progress

    def _cleanup_audio_file(self, file_path):
        """
        Удаляет аудиофайл после обработки

        Args:
            file_path: Путь к аудиофайлу
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Successfully deleted audio file: {file_path}")
            else:
                logger.warning(f"Audio file not found for deletion: {file_path}")
        except Exception as e:
            logger.error(f"Error deleting audio file {file_path}: {str(e)}")



if __name__ == '__main__':
    t = TranscriberAggregator()
    transcript = ''
    task_id = ''
    t._run_summarization(task_id, transcript)