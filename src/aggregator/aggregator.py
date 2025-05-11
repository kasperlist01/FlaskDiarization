import logging
import time
from concurrent.futures import ThreadPoolExecutor

from src.db_service.db import DatabaseService
from src.db_service.models import TaskStatus
from src.task_manager.manager import TaskManager

# Импортируем наши модули

# Настройка логирования
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('Aggregator')


class TranscriptionAggregator:
    """
    Оркестратор процесса транскрибации и создания саммари
    Координирует работу различных сервисов и отслеживает статус задачи
    """

    def __init__(self, db_service=None, task_manager=None,
                 transcription_service=None, summary_service=None):
        """
        Инициализация оркестратора

        Args:
            db_service: Сервис базы данных
            task_manager: Менеджер задач
            transcription_service: Сервис транскрибации
            summary_service: Сервис создания саммари
        """
        self.db = db_service or DatabaseService()
        self.task_manager = task_manager or TaskManager(db_service=self.db)
        self.transcription_service = transcription_service
        self.summary_service = summary_service

        # Пул потоков для асинхронного выполнения задач
        self.executor = ThreadPoolExecutor(max_workers=5)

    def process_task(self, task_id):
        """
        Запускает обработку задачи асинхронно

        Args:
            task_id: Идентификатор задачи

        Returns:
            future: Объект Future для отслеживания выполнения
        """
        logger.info(f"Starting processing task {task_id}")
        return self.executor.submit(self._process_task_workflow, task_id)

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
            self._run_transcription(task_id, task['file_path'], task.get('options', {}))

            # Шаг 2: Саммаризация
            transcript = self.db.get_transcription(task_id)
            if not transcript:
                logger.error(f"Transcription for task {task_id} not found")
                self.task_manager.update_task_status(task_id, TaskStatus.FAILED)
                return False

            self._run_summarization(task_id, transcript['transcript'])

            # Шаг 3: Финализация (создание итогового отчета)
            self._run_finalization(task_id)

            # Отмечаем задачу как завершенную
            self.task_manager.update_task_status(task_id, TaskStatus.COMPLETED)
            logger.info(f"Task {task_id} completed successfully")
            return True

        except Exception as e:
            logger.exception(f"Error processing task {task_id}: {str(e)}")
            self.task_manager.update_task_status(task_id, TaskStatus.FAILED)
            return False

    def _run_transcription(self, task_id, file_path, options):
        """
        Запускает процесс транскрибации

        Args:
            task_id: Идентификатор задачи
            file_path: Путь к аудиофайлу
            options: Опции транскрибации
        """
        logger.info(f"Starting transcription for task {task_id}")
        self.task_manager.update_task_status(task_id, TaskStatus.TRANSCRIBING)

        if self.transcription_service:
            # Вызываем сервис транскрибации
            transcript = self.transcription_service.transcribe(file_path, options)

            # Сохраняем результат
            self.db.save_transcription(task_id, transcript)
            self.task_manager.update_task_status(task_id, TaskStatus.TRANSCRIBED)
            logger.info(f"Transcription completed for task {task_id}")
        else:
            # Для тестирования, если сервис не настроен
            logger.warning("Transcription service not configured, using mock data")
            time.sleep(2)  # Имитация работы
            self.db.save_transcription(task_id, "This is a mock transcript for testing purposes.")
            self.task_manager.update_task_status(task_id, TaskStatus.TRANSCRIBED)

    def _run_summarization(self, task_id, transcript):
        """
        Запускает процесс создания саммари

        Args:
            task_id: Идентификатор задачи
            transcript: Текст транскрипции
        """
        logger.info(f"Starting summarization for task {task_id}")
        self.task_manager.update_task_status(task_id, TaskStatus.SUMMARIZING)

        if self.summary_service:
            # Разбиваем транскрипт на части, если он большой
            chunks = self._split_transcript(transcript)

            # Обрабатываем каждую часть
            for i, chunk in enumerate(chunks):
                summary = self.summary_service.create_summary(chunk)
                self.db.save_summary_chunk(task_id, i, summary)

            self.task_manager.update_task_status(task_id, TaskStatus.SUMMARIZED)
            logger.info(f"Summarization completed for task {task_id}")
        else:
            # Для тестирования
            logger.warning("Summary service not configured, using mock data")
            time.sleep(2)  # Имитация работы
            self.db.save_summary_chunk(task_id, 0, "This is a mock summary for testing purposes.")
            self.task_manager.update_task_status(task_id, TaskStatus.SUMMARIZED)

    def _run_finalization(self, task_id):
        """
        Создает финальный отчет на основе саммари

        Args:
            task_id: Идентификатор задачи
        """
        logger.info(f"Creating final report for task {task_id}")
        self.task_manager.update_task_status(task_id, TaskStatus.FINALIZING)

        # Получаем все части саммари
        summary_chunks = self.db.get_summary_chunks(task_id)

        if not summary_chunks:
            logger.error(f"No summary chunks found for task {task_id}")
            return

        # Объединяем части в финальный отчет
        final_report = self._compile_final_report(summary_chunks)

        # Сохраняем финальный отчет
        self.db.save_final_report(task_id, final_report)
        logger.info(f"Final report created for task {task_id}")

    def _split_transcript(self, transcript, max_chunk_size=5000):
        """
        Разбивает транскрипт на части для обработки

        Args:
            transcript: Полный текст транскрипции
            max_chunk_size: Максимальный размер части в символах

        Returns:
            list: Список частей транскрипта
        """
        # Простой алгоритм разбиения по размеру
        if len(transcript) <= max_chunk_size:
            return [transcript]

        chunks = []
        sentences = transcript.split('. ')
        current_chunk = ""

        for sentence in sentences:
            if len(current_chunk) + len(sentence) + 2 <= max_chunk_size:
                current_chunk += sentence + ". "
            else:
                chunks.append(current_chunk.strip())
                current_chunk = sentence + ". "

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    def _compile_final_report(self, summary_chunks):
        """
        Компилирует финальный отчет из частей саммари

        Args:
            summary_chunks: Список частей саммари

        Returns:
            str: Финальный отчет
        """
        # Объединяем все части в один отчет
        # В реальном приложении здесь может быть более сложная логика
        summaries = [chunk['summary'] for chunk in summary_chunks]

        report = "# Итоговый отчет о разговоре\n\n"

        # Добавляем каждую часть саммари
        for i, summary in enumerate(summaries):
            if i > 0:
                report += "\n\n## Часть " + str(i + 1) + "\n\n"
            report += summary

        return report

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