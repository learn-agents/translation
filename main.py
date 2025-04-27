import os
import re
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Tuple, Any
from dotenv import load_dotenv
from openai import OpenAI

# Импортируем наши утилиты
from utils import (
    log_info, log_error, log_warning, setup_logging,
    load_config, get_system_prompt, load_glossary,
    is_binary_file, extract_frontmatter, restore_frontmatter, split_content,
    translate_frontmatter, Translator
)

# Добавляем глобальный счетчик токенов для всех языков
global_total_tokens_processed = 0

def process_file(file_path: str, rel_path: str, output_dir: str, target_language: str,
                 translator: Translator, max_tokens: int) -> bool:
    """
    Обрабатывает файл: переводит его содержимое и сохраняет в выходной директории.
    
    Args:
        file_path: Полный путь к файлу
        rel_path: Относительный путь от input_dir
        output_dir: Выходная директория
        target_language: Целевой язык перевода
        translator: Экземпляр переводчика
        max_tokens: Максимальное количество токенов для разбиения
        
    Returns:
        bool: True если обработка успешна, False в противном случае
    """
    try:
        # Создаем выходную директорию для языка, если она не существует
        lang_output_dir = os.path.join(output_dir, target_language)
        output_file_path = os.path.join(lang_output_dir, rel_path)
        os.makedirs(os.path.dirname(output_file_path), exist_ok=True)
        
        # Если файл бинарный, просто копируем его
        if is_binary_file(file_path):
            log_info(f"Копирование бинарного файла: {rel_path}")
            import shutil
            shutil.copy2(file_path, output_file_path)
            return True
        
        # Обрабатываем только файлы .md и .mdx
        if not file_path.endswith(('.md', '.mdx')):
            log_info(f"Копирование файла с расширением {os.path.splitext(file_path)[1]}: {rel_path}")
            import shutil
            shutil.copy2(file_path, output_file_path)
            return True
        
        # Читаем содержимое файла
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # Удаляем блоки локального текста перед дальнейшей обработкой
        # Используем флаг re.DOTALL, чтобы '.' соответствовал и переносам строк
        content = re.sub(r"\{\s*/\*\s*LOCAL TEXT START\s*\*/\s*\}(.*?)\{\s*/\*\s*LOCAL TEXT END\s*\*/\s*\}", 
                         "", content, flags=re.DOTALL | re.IGNORECASE)
        
        # Извлекаем фронтматтер
        has_frontmatter, frontmatter, main_content = extract_frontmatter(content)
        
        # Получаем системный промпт для выбранного языка
        system_prompt = get_system_prompt(CONFIG, target_language)
        
        # Если есть фронтматтер, переводим его
        if has_frontmatter and frontmatter:
            log_info(f"Обработка фронтматтера файла {rel_path}")
            frontmatter = translate_frontmatter(frontmatter, translator.translate_text, target_language, system_prompt)
        
        # Разбиваем содержимое на части с учетом MAX_TOKENS
        parts = split_content(main_content, max_tokens)
        
        # Переводим каждую часть с использованием контекста между частями
        translated_parts = []
        context = {
            "translated_terms": {},
            "part_number": 1,
            "total_tokens": 0
        }
        
        for i, part in enumerate(parts):
            log_info(f"Перевод части {i+1}/{len(parts)} файла {rel_path}")
            translated_part, context = translator.translate_text(part, target_language, system_prompt, context)
            translated_parts.append(translated_part)
        
        # Объединяем переведенные части
        translated_content = '\n\n'.join(translated_parts)
        
        # Восстанавливаем фронтматтер, если он был
        if has_frontmatter:
            translated_content = restore_frontmatter(frontmatter, translated_content)
        
        # Сохраняем переведенный файл
        with open(output_file_path, 'w', encoding='utf-8') as file:
            file.write(translated_content)
        
        log_info(f"Файл переведен и сохранен: {output_file_path}")
        return True
    
    except Exception as e:
        log_error(f"Ошибка при обработке файла {rel_path}: {str(e)}")
        return False

def process_directory(input_dir: str, output_dir: str, target_language: str, 
                     translator: Translator, max_tokens: int, max_workers: int) -> int:
    """
    Рекурсивно обрабатывает все файлы в директории.
    
    Args:
        input_dir: Входная директория
        output_dir: Выходная директория
        target_language: Целевой язык перевода
        translator: Экземпляр переводчика
        max_tokens: Максимальное количество токенов для разбиения
        max_workers: Максимальное количество потоков
    """
    # Получаем список всех файлов в директории и поддиректориях
    all_files = []
    for root, _, files in os.walk(input_dir):
        for file in sorted(files):  # Сортируем для стабильного порядка обработки
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, input_dir)
            all_files.append((file_path, rel_path))
    
    log_info(f"Найдено {len(all_files):,} файлов для обработки")
    
    # Создаем выходную директорию для языка, если она не существует
    lang_output_dir = os.path.join(output_dir, target_language)
    os.makedirs(lang_output_dir, exist_ok=True)
    
    # Обрабатываем файлы параллельно
    total_tokens_for_lang = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(process_file, args[0], args[1], output_dir, target_language, translator, max_tokens)
            for args in all_files
        ]
        results = [f.result() for f in futures] # Используем f.result() для получения результатов или исключений
    
    # Подводим итоги
    success_count = results.count(True)
    total_tokens_for_lang = translator.get_total_tokens() # Получаем токены от этого экземпляра
    log_info(f"Обработка для языка '{target_language}' завершена. Успешно: {success_count}/{len(all_files)}")
    log_info(f"Количество токенов для языка '{target_language}': ~{int(total_tokens_for_lang):,}")
    return total_tokens_for_lang # Возвращаем токены, обработанные этим языком

def parse_arguments():
    """
    Разбирает аргументы командной строки.
    
    Returns:
        argparse.Namespace: Объект с аргументами
    """
    parser = argparse.ArgumentParser(description='Система автоматизированного перевода документации')
    # Добавляем 'all' в список допустимых языков и используем zh вместо de
    parser.add_argument('--language', type=str, default='en', 
                        choices=['en', 'es', 'zh', 'all'], # Используем en, es, zh, all
                        help='Целевой язык перевода (en, es, zh) или \'all\' для всех трех')
    parser.add_argument('--input_dir', type=str, default='input', help='Директория с исходными файлами')
    parser.add_argument('--output_dir', type=str, default='output', help='Директория для сохранения результатов')
    parser.add_argument('--log_level', type=str, default='INFO', 
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], help='Уровень логирования')
    parser.add_argument('--log_file', type=str, help='Файл для сохранения логов')
    parser.add_argument('--max_workers', type=int, help='Количество параллельных потоков')
    parser.add_argument('--max_tokens', type=int, help='Максимальное количество токенов для разбиения')
    return parser.parse_args()

# Загрузка переменных окружения
load_dotenv()

# Глобальная конфигурация
CONFIG = load_config()

def main():
    """Основная функция для запуска процесса перевода."""
    global global_total_tokens_processed # Используем глобальный счетчик
    global_total_tokens_processed = 0    # Сбрасываем перед запуском
    
    # Разбор аргументов командной строки
    args = parse_arguments()
    
    # Настройка логирования
    setup_logging(args.log_level, args.log_file)
    
    # Получаем параметры из конфигурации и аргументов
    input_dir = args.input_dir
    output_dir = args.output_dir
    max_tokens = args.max_tokens or CONFIG.get("general", {}).get("max_tokens", 8000)
    max_workers = args.max_workers or CONFIG.get("general", {}).get("max_workers", 4)
    
    # Определяем целевые языки
    if args.language == 'all':
        target_languages = ['en', 'es', 'zh'] # Используем en, es, zh
    else:
        target_languages = [args.language]
        
    log_info(f"Целевые языки: {', '.join(target_languages)}")
    log_info(f"Входная директория: {input_dir}")
    log_info(f"Выходная директория: {output_dir}")
    log_info(f"Макс. токенов для разбиения: {max_tokens}")
    log_info(f"Макс. потоков: {max_workers}")
    
    # Проверяем наличие входной директории
    if not os.path.exists(input_dir):
        log_error(f"Входная директория '{input_dir}' не найдена")
        return
    
    # Создаем общую выходную директорию, если она не существует
    os.makedirs(output_dir, exist_ok=True)
    
    # Загрузка глоссария
    glossary = load_glossary()
    
    # Инициализация клиента OpenAI (делаем один раз)
    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=CONFIG.get("api", {}).get("base_url", os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    )
    model_name = CONFIG.get("api", {}).get("model_name", os.getenv("MODEL_NAME", "gpt-4o-mini"))
    
    # Цикл по целевым языкам
    for target_language in target_languages:
        log_info(f"Начинаем перевод файлов из '{input_dir}' на язык '{target_language}'")
        
        # Создаем экземпляр переводчика для каждого языка (чтобы счетчик токенов был свой)
        translator = Translator(client, model_name, glossary)
        
        # Запускаем обработку директории для текущего языка
        tokens_for_lang = process_directory(input_dir, output_dir, target_language, translator, max_tokens, max_workers)
        global_total_tokens_processed += tokens_for_lang # Добавляем токены к общему счетчику
        
        log_info(f"Перевод на язык '{target_language}' завершен.")

    log_info("Весь процесс перевода завершен.")
    log_info(f"Итого обработано токенов по всем языкам: ~{int(global_total_tokens_processed):,}")

if __name__ == "__main__":
    main() 