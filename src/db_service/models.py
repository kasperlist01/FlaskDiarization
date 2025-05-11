from enum import Enum


class TaskStatus(Enum):
    """Перечисление возможных статусов задачи"""
    PENDING = "pending"  # Задача создана, ожидает обработки
    TRANSCRIBING = "transcribing"  # Идет процесс транскрибации аудио
    TRANSCRIBED = "transcribed"  # Транскрипция завершена
    SUMMARIZING = "summarizing"  # Идет процесс создания саммари
    SUMMARIZED = "summarized"  # Саммари создано
    FINALIZING = "finalizing"  # Идет процесс создания финального отчета
    COMPLETED = "completed"  # Задача полностью завершена
    FAILED = "failed"  # Задача завершилась с ошибкой

    @classmethod
    def is_final(cls, status):
        """Проверяет, является ли статус финальным (задача завершена)"""
        return status in [cls.COMPLETED.value, cls.FAILED.value]

    @classmethod
    def from_string(cls, status_str):
        """Преобразует строковое представление в объект TaskStatus"""
        for status in cls:
            if status.value == status_str:
                return status
        raise ValueError(f"Unknown task status: {status_str}")