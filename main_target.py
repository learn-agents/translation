import os
import re
import argparse
import subprocess
import shutil
import concurrent.futures
from pathlib import Path
from typing import List, Dict, Tuple, Any
from dotenv import load_dotenv
from openai import OpenAI

# Импортируем наши утилиты
from utils import (
    log_info, log_error, log_warning, setup_logging,
    load_config, get_system_prompt, load_glossary,
    is_binary_file, extract_frontmatter, restore_frontmatter, split_content,
    translate_frontmatter, Translator, get_changed_files_in_dir # Добавили get_changed_files_in_dir
)

# Константы для директорий языков относительно корня репозитория книги
# Используем POSIX-разделители, т.к. они часто используются в конфигурациях и Git
LANG_DIRS = {
    'ru': 'i18n/ru/docusaurus-plugin-content-docs/current',
    'en': 'docs',
    'es': 'i18n/es/docusaurus-plugin-content-docs/current',
    'zh': 'i18n/zh/docusaurus-plugin-content-docs/current'
}

# Глобальная конфигурация (загружается позже в main)
CONFIG = {}

def process_changed_file(
    ru_file_path: str, # Полный путь к исходному RU файлу
    rel_path: str, # Путь относительно базовой директории RU (с POSIX разделителями)
    target_language: str,
    book_repo_path: str, # Абсолютный путь к корню репозитория книги
    translator: Translator,
    max_tokens: int,
    system_prompt: str  # Передаем готовый системный промпт
) -> bool:
    """
    Обрабатывает один измененный файл: переводит (.md/.mdx) или копирует остальные.
    Сохраняет результат непосредственно в целевую языковую директорию внутри репозитория книги.

    Args:
        ru_file_path: Полный абсолютный путь к исходному файлу на русском.
        rel_path: Путь файла относительно базовой директории 'ru' (например, 'section/page.mdx').
        target_language: Код целевого языка ('en', 'es', 'zh').
        book_repo_path: Абсолютный путь к корню репозитория книги.
        translator: Экземпляр класса Translator.
        max_tokens: Максимальное количество токенов для разбиения контента.
        system_prompt: Системный промпт для данной языковой пары.
    
    Возвращает:
        bool: True, если обработка прошла успешно, иначе False.
    """
    try:
        target_lang_dir_rel = LANG_DIRS.get(target_language)
        if not target_lang_dir_rel:
            log_error(f"Не найден путь для целевого языка: {target_language}")
            return False

        # Формируем абсолютный путь к целевой директории и файлу
        target_base_dir = os.path.join(book_repo_path, target_lang_dir_rel)
        # Используем rel_path (который в POSIX формате) для создания пути в целевой директории
        output_file_path = os.path.join(target_base_dir, rel_path)
        
        # Создаем родительские директории для выходного файла, если они не существуют
        os.makedirs(os.path.dirname(output_file_path), exist_ok=True)

        # Определяем, нужно ли переводить файл
        should_translate = ru_file_path.lower().endswith(('.md', '.mdx')) and not is_binary_file(ru_file_path)

        if not should_translate:
            log_info(f"[{target_language}] Копирование файла: {rel_path}")
            shutil.copy2(ru_file_path, output_file_path) # Копируем с сохранением метаданных
            return True

        # --- Обработка .md / .mdx файла (перевод) ---
        log_info(f"[{target_language}] Перевод файла: {rel_path}")
        
        try:
            with open(ru_file_path, 'r', encoding='utf-8') as file:
                content = file.read()
        except Exception as e:
             log_error(f"[{target_language}] Ошибка чтения файла {ru_file_path}: {e}")
             return False

        # Регулярное выражение для поиска блоков LOCAL TEXT
        # Используем r-string и экранируем метасимволы: {, }, *, /
        local_text_pattern = r"\{\s*\/\*\s*LOCAL TEXT START\s*\*\/\s*\}(.*?)\{\s*\/\*\s*LOCAL TEXT END\s*\*\/\s*\}"
        
        # Удаляем блоки LOCAL TEXT перед дальнейшей обработкой
        # Используем флаг re.DOTALL, чтобы '.' соответствовал и переносам строк
        content = re.sub(local_text_pattern, "", content, flags=re.DOTALL | re.IGNORECASE)

        # Извлекаем фронтматтер
        has_frontmatter, frontmatter, main_content = extract_frontmatter(content)

        # Переводим фронтматтер, если он есть
        if has_frontmatter and frontmatter:
            log_info(f"[{target_language}] Перевод frontmatter для {rel_path}")
            try:
                frontmatter = translate_frontmatter(frontmatter, translator.translate_text, target_language, system_prompt)
            except Exception as e:
                log_error(f"[{target_language}] Ошибка перевода frontmatter для {rel_path}: {e}")
                # Решаем продолжать без переведенного frontmatter или вернуть ошибку
                # Пока что продолжаем, но можно изменить логику
                pass # Оставляем исходный frontmatter

        # Разбиваем основной контент на части
        parts = split_content(main_content, max_tokens)
        translated_parts = []
        # Контекст сбрасывается для каждого файла, но сохраняется между частями одного файла
        context = {"translated_terms": {}, "part_number": 1, "total_tokens": 0} 

        for i, part in enumerate(parts):
            log_info(f"[{target_language}] Перевод части {i+1}/{len(parts)} файла {rel_path}")
            try:
                # Передаем контекст, он обновляется внутри метода
                translated_part, context = translator.translate_text(part, target_language, system_prompt, context)
                translated_parts.append(translated_part)
            except Exception as e:
                 log_error(f"[{target_language}] Ошибка перевода части {i+1} файла {rel_path}: {e}")
                 # Пропускаем эту часть или прерываем обработку файла?
                 # Пока пропустим часть, чтобы попытаться сохранить остальное
                 translated_parts.append(f"[ОШИБКА ПЕРЕВОДА ЧАСТИ {i+1}: {e}]") # Добавляем заглушку об ошибке

        # Объединяем переведенные части
        translated_content = '\n\n'.join(translated_parts)

        # Восстанавливаем фронтматтер, если он был (даже если не перевелся)
        if has_frontmatter:
            translated_content = restore_frontmatter(frontmatter, translated_content)

        # Сохраняем переведенный файл
        try:
            with open(output_file_path, 'w', encoding='utf-8') as file:
                file.write(translated_content)
            log_info(f"[{target_language}] Файл переведен и сохранен: {output_file_path}")
            return True
        except Exception as e:
            log_error(f"[{target_language}] Ошибка сохранения файла {output_file_path}: {e}")
            return False

    except Exception as e:
        # Ловим общие ошибки на уровне файла
        log_error(f"[{target_language}] Общая ошибка при обработке файла {rel_path}: {str(e)}")
        # Здесь можно добавить traceback для детальной отладки, если нужно
        # import traceback
        # log_error(traceback.format_exc())
        return False

def parse_arguments():
    """Разбирает аргументы командной строки."""
    parser = argparse.ArgumentParser(description='Перевод измененных файлов документации в Git репозитории.')
    # Добавляем 'all' в список допустимых языков
    parser.add_argument('--language', type=str, default='all',
                        choices=['en', 'es', 'zh', 'all'],  # Поддерживаемые языки
                        help="Целевой язык перевода (en, es, zh) или 'all' для всех")
    parser.add_argument('--log_level', type=str, default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], help='Уровень логирования')
    parser.add_argument('--log_file', type=str, help='Файл для сохранения логов')
    parser.add_argument('--max_workers', type=int, help="Количество параллельных потоков (default из config.yml)")
    parser.add_argument('--max_tokens', type=int, help="Макс. токенов для разбиения контента (default из config.yml)")
    return parser.parse_args()

def main():
    """Основная функция для запуска процесса перевода измененных файлов."""
    global CONFIG  # Используем глобальную переменную для конфига

    # 1. Загрузка конфигурации и окружения
    load_dotenv()
    CONFIG = load_config()  # Загружаем config.yml
    CONFIG = load_config() # Загружаем config.yml

    # 2. Разбор аргументов командной строки
    args = parse_arguments()

    # 3. Настройка логирования
    setup_logging(args.log_level, args.log_file)

    # 4. Получение и проверка пути к репозиторию книги из .env
    book_repo_path_str = os.getenv("BOOK_PATH")
    if not book_repo_path_str:
        log_error("Переменная окружения BOOK_PATH не установлена в .env файле.")
        return
    
    # Используем Path для работы с путями и resolve() для получения абсолютного пути
    book_repo_path = Path(book_repo_path_str).resolve()
    log_info(f"Проверка пути к репозиторию: {book_repo_path}")

    # Проверяем, что путь существует, является директорией и Git-репозиторием
    if not book_repo_path.is_dir():
         log_error(f"Указанный BOOK_PATH '{book_repo_path}' не является директорией.")
         return
    if not (book_repo_path / ".git").is_dir():
         # Проверяем наличие .git в родительских директориях, если BOOK_PATH - поддиректория
         try:
             subprocess.run(['git', 'rev-parse', '--is-inside-work-tree'], 
                            cwd=str(book_repo_path), check=True, capture_output=True)
             log_info(f"Найден Git репозиторий для '{book_repo_path}'")
         except (subprocess.CalledProcessError, FileNotFoundError):
             # Используем одинарные кавычки внутри f-string, если путь содержит фигурные скобки
             log_error(f"Указанный BOOK_PATH '{book_repo_path}' не является Git репозиторием или его частью.")
             return

    # 5. Получение параметров обработки
    max_tokens = args.max_tokens or CONFIG.get("general", {}).get("max_tokens", 8000)
    max_workers = args.max_workers or CONFIG.get("general", {}).get("max_workers", 4)

    # 6. Определение исходной директории (RU) и получение списка измененных файлов
    ru_dir_rel = LANG_DIRS.get('ru')
    if not ru_dir_rel:
        log_error("Конфигурация для русской директории (ru) отсутствует в LANG_DIRS.")
        return
        
    # Путь к директории ru относительно корня репозитория, используем POSIX формат для git_utils
    ru_dir_rel_posix = Path(ru_dir_rel).as_posix() 
    
    # Используем одинарные кавычки внутри f-string
    log_info(f"Поиск измененных файлов в директории: '{ru_dir_rel_posix}'")
    # Передаем абсолютный путь к репозиторию и относительный путь к поддиректории
    changed_relative_paths = get_changed_files_in_dir(str(book_repo_path), ru_dir_rel_posix)

    if not changed_relative_paths:
        # Используем одинарные кавычки внутри f-string
        log_info(f"В директории '{ru_dir_rel_posix}' нет измененных файлов для обработки.")
        return

    log_info(f"Найдено {len(changed_relative_paths)} измененных/новых файлов для обработки.")
    # log_debug(f"Список файлов: {changed_relative_paths}") # Логируем список в DEBUG

    # 7. Инициализация OpenAI клиента и загрузка глоссария
    try:
        client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=CONFIG.get("api", {}).get("base_url", os.getenv("OPENAI_BASE_URL"))
        )
        # Простой пинг для проверки доступности API (опционально)
        # client.models.list() 
        log_info("Клиент OpenAI успешно инициализирован.")
    except Exception as e:
        log_error(f"Ошибка инициализации клиента OpenAI: {e}")
        return
        
    glossary = load_glossary()
    model_name = CONFIG.get("api", {}).get("model_name", os.getenv("MODEL_NAME", "gpt-4o-mini"))
    log_info(f"Используемая модель: {model_name}")

    # 8. Определение целевых языков
    if args.language == 'all':
        target_languages = ['en', 'es', 'zh']
    else:
        target_languages = [args.language]

    # Используем стандартные кавычки для f-string
    log_info(f"Целевые языки для перевода: {', '.join(target_languages)}")
    log_info(f"Максимальное количество токенов для разбиения: {max_tokens}")
    log_info(f"Максимальное количество потоков: {max_workers}")

    # 9. Обработка файлов для каждого целевого языка
    total_processed_tokens_all_langs = 0
    global_success_count = 0
    global_failed_files: Dict[str, List[str]] = {lang: [] for lang in target_languages} # Словарь для ошибок по языкам

    for target_language in target_languages:
        log_info(f"--- Начало обработки для языка: {target_language} ---")
        
        # Создаем экземпляр переводчика для каждого языка (чтобы счетчик токенов был свой)
        translator = Translator(client, model_name, glossary)
        
        # Получаем системный промпт один раз для языка
        system_prompt = get_system_prompt(CONFIG, target_language)
        
        # Формируем список задач для ThreadPoolExecutor
        tasks = []
        ru_dir_abs = book_repo_path / ru_dir_rel_posix # Абсолютный путь к директории ru

        for rel_path in changed_relative_paths:
            # Формируем полный абсолютный путь к исходному файлу
            ru_file_full_path = str(ru_dir_abs / rel_path) 
            if not os.path.exists(ru_file_full_path):
                log_warning(f"[{target_language}] Исходный файл не найден, пропуск: {ru_file_full_path}")
                continue
            # Добавляем аргументы для функции process_changed_file
            tasks.append((
                ru_file_full_path, 
                rel_path, 
                target_language, 
                str(book_repo_path), 
                translator, 
                max_tokens,
                system_prompt # Передаем промпт
            ))

        # Обрабатываем файлы параллельно
        lang_success_count = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Создаем словарь future -> rel_path для отслеживания
            future_to_rel_path = {executor.submit(process_changed_file, *task_args): task_args[1] for task_args in tasks}

            for future in concurrent.futures.as_completed(future_to_rel_path):
                rel_path = future_to_rel_path[future]
                try:
                    result = future.result() # Получаем результат (True/False)
                    if result:
                        lang_success_count += 1
                    else:
                        global_failed_files[target_language].append(rel_path)
                except Exception as exc:
                     log_error(f"[{target_language}] Необработанное исключение при обработке файла {rel_path}: {exc}")
                     # import traceback
                     # log_error(traceback.format_exc()) # Для детальной отладки
                     global_failed_files[target_language].append(rel_path)

        # Подводим итоги для текущего языка
        lang_total_tokens = translator.get_total_tokens()
        total_processed_tokens_all_langs += lang_total_tokens
        global_success_count += lang_success_count # Считаем общий успех (может быть неточным, если файл упал на одном языке)

        # Используем одинарные кавычки для f-string
        log_info(f"--- Обработка для языка '{target_language}' завершена ---")
        # Используем одинарные кавычки для f-string
        log_info(f"Успешно обработано файлов для '{target_language}': {lang_success_count}/{len(tasks)}")
        if global_failed_files[target_language]:
            # Используем одинарные кавычки для f-string и join
            log_warning(f"Не удалось обработать файлы для '{target_language}': {', '.join(global_failed_files[target_language])}")
        # Используем одинарные кавычки для f-string
        log_info(f"Токенов использовано для '{target_language}': ~{int(lang_total_tokens):,}")
        print("-" * 30) # Добавляем разделитель в консоль

    # 10. Финальные итоги
    log_info("="*20 + " Весь процесс перевода завершен " + "="*20)
    total_failed_count = sum(len(files) for files in global_failed_files.values())
    total_processed_count = len(changed_relative_paths) * len(target_languages) # Общее количество попыток обработки
    
    log_info(f"Всего файлов для обработки (по всем языкам): {total_processed_count}")
    # Успех лучше считать по языкам, как сделано выше. Общий успех сложно определить однозначно.
    if total_failed_count > 0:
         log_warning(f"Всего неудачных попыток обработки файлов: {total_failed_count}")
         # Можно вывести детали по ошибкам еще раз
         # for lang, files in global_failed_files.items():
         #    if files: log_warning(f"Ошибки [{lang}]: {files}")
             # Используем стандартные кавычки для f-string
    log_info(f"Итого токенов использовано по всем языкам: ~{int(total_processed_tokens_all_langs):,}")
    log_info("Работа скрипта завершена.")


if __name__ == "__main__":
    main() 