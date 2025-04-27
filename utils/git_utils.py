import os
import subprocess
from pathlib import Path
from typing import List, Set
from .logger import log_info, log_error, log_warning

def get_changed_files_in_dir(repo_path: str, target_subdir: str) -> List[str]:
    """
    Получает список измененных (модифицированных, добавленных, переименованных в) 
    файлов в указанной поддиректории Git репозитория.

    Args:
        repo_path: Абсолютный путь к корню Git репозитория.
        target_subdir: Путь к целевой поддиректории относительно корня репозитория 
                       (используйте POSIX-разделители '/').

    Returns:
        Список путей к измененным файлам относительно target_subdir 
        (с POSIX-разделителями).
    """
    changed_files: Set[str] = set()
    
    # Нормализуем target_subdir к POSIX формату на всякий случай
    target_subdir_posix = Path(target_subdir).as_posix()
    # Убедимся, что путь к поддиректории не начинается и не заканчивается слешем для согласованности
    target_subdir_clean = target_subdir_posix.strip('/')

    # Создаем полный путь к директории для проверки существования
    full_target_path = os.path.join(repo_path, target_subdir_clean)
    if not os.path.isdir(full_target_path):
        log_warning(f"Целевая директория для проверки Git не существует: {full_target_path}")
        return []

    try:
        # Используем git status --porcelain=v1 для стабильного формата вывода
        # Передаем target_subdir_clean как аргумент для ограничения области поиска git status
        # '--' используется для отделения путей от опций
        git_command = ['git', 'status', '--porcelain=v1', '--untracked-files=all', '--', target_subdir_clean]
        log_info(f"Выполнение команды git: {' '.join(git_command)} в {repo_path}")

        result = subprocess.run(
            git_command,
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
            encoding='utf-8' # Явно указываем кодировку
        )
        
        # Разделяем вывод по строкам, учитывая разные символы конца строки
        output_lines = result.stdout.strip().splitlines()
        
        if not output_lines or (len(output_lines) == 1 and not output_lines[0]):
             log_info(f"Нет изменений или неотслеживаемых файлов в {target_subdir_clean}")
             return []

        # Получаем имя корневой папки репозитория для возможной очистки префикса
        repo_root_name = Path(repo_path).name

        final_changed_files: Set[str] = set()
        for line in output_lines:
            if not line.strip():
                continue

            parts = line.split(maxsplit=2)
            status = parts[0]
            file_path_rel_repo = parts[1]

            if status in ('R', 'C') and '->' in parts[1]:
                path_parts = parts[1].split(' -> ')
                if len(path_parts) == 2:
                    file_path_rel_repo = path_parts[1]
                else:
                    log_warning(f"Не удалось разобрать путь для {status}: {parts[1]}")
                    continue
            
            # Убираем кавычки, если Git их добавляет для путей с пробелами
            file_path_rel_repo = file_path_rel_repo.strip('"')

            # Преобразуем путь к POSIX формату
            file_path_rel_repo_posix = Path(file_path_rel_repo).as_posix()
            
            # --- Новая логика: Обработка префикса ---
            # Проверяем, не начинается ли путь с имени корневой папки репозитория
            prefix_to_check = f"{repo_root_name}/"
            cleaned_path = file_path_rel_repo_posix
            if file_path_rel_repo_posix.startswith(prefix_to_check):
                cleaned_path = file_path_rel_repo_posix[len(prefix_to_check):]
                # log_debug(f"Удален префикс '{prefix_to_check}' из пути: '{file_path_rel_repo_posix}' -> '{cleaned_path}'") # Опциональный дебаг

            # Проверяем, находится ли ОЧИЩЕННЫЙ путь внутри нашей целевой директории
            if cleaned_path.startswith(target_subdir_clean + '/'):
                # Получаем путь относительно target_subdir_clean
                try:
                    # Используем очищенный путь для вычисления относительного пути
                    relative_path = os.path.relpath(cleaned_path, target_subdir_clean)
                    # Снова преобразуем в POSIX для единообразия вывода
                    final_changed_files.add(Path(relative_path).as_posix())
                except ValueError as ve:
                     log_warning(f"Не удалось вычислить относительный путь для '{cleaned_path}' относительно '{target_subdir_clean}': {ve}")

        sorted_files = sorted(list(final_changed_files)) # Используем final_changed_files
        if sorted_files:
            log_info(f"Найдено {len(sorted_files)} измененных/новых файлов в '{target_subdir_clean}'")
        else:
            # Логируем как INFO, если файлы были в выводе git status, но отфильтровались (не должны при правильной логике)
            if changed_files: # Используем исходный set до очистки префикса для этой проверки
                 log_warning(f"Найдены изменения в git status, но не в '{target_subdir_clean}' после фильтрации.")
            else:
                 log_info(f"Нет изменений или неотслеживаемых файлов в '{target_subdir_clean}'")

        # log_debug(f"Список файлов для обработки: {sorted_files}") # Опциональный дебаг
        return sorted_files

    except subprocess.CalledProcessError as e:
        # Логируем stderr для диагностики
        error_message = e.stderr.strip() if e.stderr else str(e)
        # Попытка декодировать stderr, если это байты
        if isinstance(error_message, bytes):
            try:
                error_message = error_message.decode('utf-8', errors='replace')
            except Exception:
                 error_message = str(error_message) # Fallback
        log_error(f"Ошибка выполнения git status в {repo_path}: {error_message}")
        return []
    except FileNotFoundError:
        log_error("Команда 'git' не найдена. Убедитесь, что Git установлен и доступен в системном PATH.")
        return []
    except Exception as e:
        log_error(f"Неожиданная ошибка при проверке статуса Git в {repo_path}: {str(e)}")
        return [] 