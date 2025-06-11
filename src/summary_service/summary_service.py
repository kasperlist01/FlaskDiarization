import json
import logging
import os
from typing import Dict, Any, List

import requests

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class SummaryService:
    """
    Создаёт многоуровневое саммари созвона.

    Алгоритм:
      1. Краткое содержание встречи;
      2. Темы & задачи (текст + JSON);
      3. Дедлайны для каждой задачи (последняя озвученная дата).
    """

    def __init__(self) -> None:
        self.api_url: str = os.getenv("OPENAI_API_URL", "http://localhost:8000/v1/chat/completions")
        self.model: str = os.getenv("SUMMARY_MODEL", "claude-3-7-sonnet-20250219")
        self.temperature: float = float(os.getenv("SUMMARY_TEMPERATURE", "0.7"))

    def _chat(
        self, messages: List[Dict[str, str]]) -> str:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "stream": False,
        }
        logger.debug("→ LLM payload: %s", payload)

        resp = requests.post(self.api_url, json=payload, proxies={"http": None, "https": None})
        resp.raise_for_status()

        data = resp.json()
        answer = data["choices"][0]["message"]["content"].strip()
        logger.debug("← LLM answer: %s", answer)
        return answer

    # ------------------------------------------------------------------
    # STEP‑1 ▸ Краткое содержание
    # ------------------------------------------------------------------
    def _brief_summary(self, transcript: list) -> str:
        return self._chat(
            [
                {
                    "role": "user",
                    "content": "Ты — ассистент, сделай саммари, что произошло на созвоне.",
                },
                {
                    "role": "user",
                    "content": (
                        "Проанализируй следующий транскрипт и составь Саммари созвона по блоками"
                        "укажи временные метки ключевых моментов (начало обсуждения тем, решений и важных задач).\n\n"
                        "Формат:\n"
                        "<Саммари(вмеру подробное) каждой темы>\n"
                        "Временные метки:\n"
                        "- [12:34] Обсуждение <тема>\n"
                        "- [23:10] Принято решение <резюме>\n"
                        "\nТранскрипт:\n"
                        f"{transcript}"
                    ),
                },
            ],
        )

    # STEP‑2 ▸ Темы + задачи + дедлайны + временные метки
    def _topics_and_tasks(self, transcript: list) -> str:
        return self._chat(
            [
                {
                    "role": "user",
                    "content": (
                        "Ты — аналитик встреч. Твоя задача — извлечь все темы, задачи, дедлайны и временные метки из транскрипта."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Сделай следующее:\n"
                        "1. Выдели темы обсуждения\n"
                        "2. Для каждой темы укажи задачи, их дедлайны (если есть) и временные метки\n"
                        "\nФормат:\n"
                        "{\n"
                        "  \"topics\": [\n"
                        "    {\n"
                        "      \"name\": \"<тема>\",\n"
                        "      \"timestamp\": \"<00:12:34>\",\n"
                        "      \"summary\": \"<краткое содержание темы>\",\n"
                        "      \"tasks\": [\n"
                        "        {\n"
                        "          \"title\": \"<задача>\",\n"
                        "          \"date\": \"<дедлайн или 'Дедлайн не установлен'>\",\n"
                        "          \"deadline_timestamp\": \"<00:15:20>\"  # если есть\n"
                        "        }\n"
                        "      ]\n"
                        "    }\n"
                        "  ]\n"
                        "}\n"
                        "Никакого другого текста после JSON.\n\n"
                        f"Транскрипт:\n{transcript}"
                    ),
                },
            ],
        )

    # STEP‑3 ▸ Расширенный анализ дедлайнов с цитатами и метками
    def _deadlines_for_tasks(self, transcript: list, topics: str) -> str:
        return self._chat(
            [
                {
                    "role": "user",
                    "content": (
                        "Ты — аналитик, специализирующийся на извлечении информации о сроках выполнения задач из транскриптов совещаний."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Проанализируй транскрипт и найди дедлайны для каждой темы из списка. "
                        "Для каждой темы:\n"
                        "1. Укажи краткое описание (summary)\n"
                        "2. Отметь временные метки начала темы и дедлайнов\n"
                        "3. Для каждой задачи покажи её дедлайн и контекст цитаты\n\n"
                        "Формат:\n"
                        "## <Название темы> [начало: 00:12:34, конец: 00:23:10]\n"
                        "- Summary: <краткое описание обсуждения>\n"
                        "- Deadlines:\n"
                        "  - Задача: <название задачи>\n"
                        "    - Дата: <дата или 'Дедлайн не установлен'>\n"
                        "    - Метка: <00:15:20>\n"
                        "    - Контекст: \"<цитата из транскрипта>\"\n"
                        "\nТранскрипт:\n"
                        f"{transcript}\n\nТемы:\n{topics}"
                    ),
                },
            ],
        )

    # ------------------------------------------------------------------
    # PUBLIC ▸ create_summary
    # ------------------------------------------------------------------
    def create_summary(self, transcript: dict[any, any]) -> str:
        cleaned_data = []
        for item in transcript:
            cleaned_item = {k: v for k, v in item.items() if k != 'words'}
            # Преобразование временных меток
            cleaned_item['start'] = format_time(cleaned_item['start'])
            cleaned_item['end'] = format_time(cleaned_item['end'])
            cleaned_data.append(cleaned_item)
        logger.info("[Summary] 1/3 — краткое содержание")
        brief = self._brief_summary(cleaned_data)

        logger.info("[Summary] 2/3 — темы и задачи")
        topics = self._topics_and_tasks(cleaned_data)

        logger.info("[Summary] 3/3 — дедлайны")
        deadlines = self._deadlines_for_tasks(cleaned_data, topics)

        # Сборка отчёта
        parts: list[str] = [
            brief,
            deadlines,
        ]

        report = "\n".join(parts).strip()
        logger.info("[Summary] Report ready (%d chars)", len(report))
        return report

def format_time(seconds) -> str:
    """Преобразует секунды в формат мм:сс"""
    minutes = int(seconds // 60)
    seconds = int(seconds % 60)
    return f"{minutes:02d}:{seconds:02d}"
