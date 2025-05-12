import os
import sys
import logging
import torch
from typing import Dict, Any, Optional

# Настройка логирования
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('TranscriberService')

# Добавляем путь к локальному whisperx в sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
whisperx_path = os.path.join(current_dir, 'whisperx')
if whisperx_path not in sys.path:
    sys.path.append(whisperx_path)
    sys.path.append(current_dir)
import whisperx

class TranscriberService:
    """
    Сервис для транскрибации аудио с использованием WhisperX
    """

    def __init__(self, model_name: str = "large-v2"):
        """
        Инициализация сервиса транскрибации

        Args:
            model_name: Название модели Whisper для использования (tiny, base, small, medium, large-v2)
        """
        self.model_name = model_name
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        logger.info(f"Initializing TranscriberService with model {model_name} on {self.device}")

        self.model = None
        self.vad_model = None
        self.alignment_model = None
        self.diarization_model = None

    def _load_models(self):
        """
        Загрузка моделей при первом использовании
        """
        try:
            logger.info(f"Loading WhisperX model: {self.model_name}")
            compute_type = "float16" if self.device == "cuda" else "int8"

            self.model = whisperx.load_model(
                self.model_name,
                self.device,
                compute_type=compute_type
            )
            logger.info(f"WhisperX model loaded successfully")

        except Exception as e:
            logger.error(f"Error loading WhisperX model: {str(e)}")
            raise

    def transcribe(self, audio_path: str, batch_size: int = 16, language: Optional[str] = None) -> Dict[str, Any]:
        """
        Транскрибация аудиофайла

        Args:
            audio_path: Путь к аудиофайлу
            batch_size: Размер батча для обработки
            language: Код языка (если None, будет определен автоматически)

        Returns:
            Dict: Результат транскрибации с сегментами и метаданными
        """
        try:
            # Импортируем локальный whisperx
            

            # Проверяем, загружена ли модель
            if self.model is None:
                self._load_models()

            logger.info(f"Transcribing audio file: {audio_path}")
            audio = whisperx.load_audio(audio_path)
            result = self.model.transcribe(
                audio,
                batch_size=batch_size,
                language=language,
                print_progress=True
            )

            detected_language = result.get("language", "en")
            logger.info(f"Detected language: {detected_language}")

            logger.info(f"Loading alignment model for language: {detected_language}")
            alignment_model, metadata = whisperx.load_align_model(
                language_code=detected_language,
                device=self.device
            )

            # Выполняем выравнивание для получения точных временных меток
            logger.info("Aligning transcription")
            result = whisperx.align(
                result["segments"],
                alignment_model,
                metadata,
                audio,
                self.device,
                return_char_alignments=False
            )

            logger.info(f"Transcription completed successfully with {len(result['segments'])} segments")
            return result

        except Exception as e:
            logger.exception(f"Error during transcription: {str(e)}")
            raise

    def diarize(self, audio_path: str, result: Dict[str, Any], hf_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Выполнение диаризации (определение говорящих) для транскрибированного аудио

        Args:
            audio_path: Путь к аудиофайлу
            result: Результат транскрипции
            hf_token: Токен Hugging Face для доступа к моделям

        Returns:
            Dict: Результат транскрипции с добавленными метками говорящих
        """
        try:
            logger.info(f"Starting diarization for audio: {audio_path}")
            diarize_model = whisperx.diarize.DiarizationPipeline(
                use_auth_token=hf_token,
                device=self.device
            )

            # Загружаем аудио
            audio = whisperx.load_audio(audio_path)
            diarize_segments = diarize_model(audio)

            # Назначаем метки говорящих словам в транскрипции
            result_with_speakers = whisperx.assign_word_speakers(diarize_segments,result)

            logger.info("Diarization completed successfully")
            return result_with_speakers

        except Exception as e:
            logger.exception(f"Error during diarization: {str(e)}")
            return result

    def cleanup(self):
        """
        Освобождение ресурсов, занимаемых моделями
        """
        if self.model is not None:
            del self.model
            self.model = None

        if self.alignment_model is not None:
            del self.alignment_model
            self.alignment_model = None

        if self.diarization_model is not None:
            del self.diarization_model
            self.diarization_model = None

        # Очистка кэша CUDA, если используется
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        logger.info("Resources cleaned up")