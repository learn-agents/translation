import os
import time
import logging
from typing import Optional

# Настройка логгера
logger = logging.getLogger("translation_system")

def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None) -> None:
    """
    Настраивает систему логирования с указанным уровнем и, опционально, выводом в файл.
    
    Args:
        log_level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Опциональный путь к файлу для сохранения логов
    """
    # Преобразование строки уровня логирования в константу
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Базовая конфигурация
    log_format = "[%(asctime)s] %(levelname)s: %(message)s"
    date_format = "%H:%M:%S"
    
    # Настройка обработчиков в зависимости от наличия файла логов
    handlers = []
    
    # Консольный обработчик
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(log_format, date_format))
    handlers.append(console_handler)
    
    # Файловый обработчик (если указан файл)
    if log_file:
        # Создаем директорию для файла логов, если она не существует
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(logging.Formatter(
            "[%(asctime)s] %(levelname)s: %(message)s",
            "%Y-%m-%d %H:%M:%S"
        ))
        handlers.append(file_handler)
    
    # Конфигурация логгера
    logging.basicConfig(
        level=numeric_level,
        handlers=handlers,
        format=log_format,
        datefmt=date_format
    )
    
    # Устанавливаем уровень для нашего логгера
    logger.setLevel(numeric_level)
    
    # Добавляем обработчики к нашему логгеру
    for handler in handlers:
        logger.addHandler(handler)
    
    logger.info(f"Логирование настроено с уровнем {log_level}")

def log_info(message: str) -> None:
    """
    Выводит информационное сообщение с отметкой времени.
    
    Args:
        message: Текст сообщения
    """
    timestamp = time.strftime('%H:%M:%S', time.localtime())
    print(f"[{timestamp}] {message}")
    logger.info(message)

def log_error(message: str) -> None:
    """
    Выводит сообщение об ошибке с отметкой времени.
    
    Args:
        message: Текст сообщения об ошибке
    """
    timestamp = time.strftime('%H:%M:%S', time.localtime())
    print(f"[{timestamp}] ОШИБКА: {message}")
    logger.error(message)

def log_debug(message: str) -> None:
    """
    Выводит отладочное сообщение (только если уровень логирования DEBUG).
    
    Args:
        message: Текст отладочного сообщения
    """
    logger.debug(message)

def log_warning(message: str) -> None:
    """
    Выводит предупреждение.
    
    Args:
        message: Текст предупреждения
    """
    timestamp = time.strftime('%H:%M:%S', time.localtime())
    print(f"[{timestamp}] ПРЕДУПРЕЖДЕНИЕ: {message}")
    logger.warning(message) 