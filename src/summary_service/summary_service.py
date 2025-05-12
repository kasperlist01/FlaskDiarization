# src/summary_service/summary_service.py
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class SummaryService:
    """Сервис для создания саммари текста транскрибации"""

    def __init__(self):
        """Инициализация сервиса суммаризации"""
        logger.info("Initializing SummaryService")

    def create_summary(self, transcript: str) -> str:
        """
        Создание саммари из текста транскрибации

        Args:
            transcript: Текст транскрибации

        Returns:
            str: Саммари текста
        """
        try:
            logger.info("Creating summary from transcript")

            # В реальном приложении здесь будет вызов модели суммаризации
            # Например, с использованием трансформеров или API OpenAI

            # Демонстрационная версия - возвращаем первые 200 символов
            if len(transcript) > 200:
                summary = transcript[:200] + "... (summary continues)"
            else:
                summary = transcript

            return summary

        except Exception as e:
            logger.exception(f"Error creating summary: {str(e)}")
            return "Failed to create summary due to an error."

    def create_structured_summary(self, segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Создание структурированного саммари из сегментов транскрибации

        Args:
            segments: Список сегментов транскрибации

        Returns:
            Dict: Структурированное саммари
        """
        try:
            logger.info("Creating structured summary from segments")

            # Объединяем весь текст для общего саммари
            full_text = " ".join([segment.get("text", "") for segment in segments])

            # Создаем саммари
            summary = self.create_summary(full_text)

            # Можно добавить выделение ключевых моментов, тем и т.д.
            key_points = ["Point 1 from transcript", "Point 2 from transcript"]

            return {
                "summary": summary,
                "key_points": key_points,
                "segment_count": len(segments),
                "duration": segments[-1]["end"] if segments else 0
            }

        except Exception as e:
            logger.exception(f"Error creating structured summary: {str(e)}")
            return {"summary": "Failed to create summary due to an error."}