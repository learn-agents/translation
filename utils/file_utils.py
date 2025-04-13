import os
import re
import yaml
import shutil
from typing import List, Dict, Tuple, Optional, Any
from utils.logger import log_info, log_error

def is_binary_file(file_path: str) -> bool:
    """
    Проверяет, является ли файл бинарным.
    
    Args:
        file_path: Путь к файлу
        
    Returns:
        bool: True, если файл бинарный, иначе False
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            file.read(1024)
        return False
    except UnicodeDecodeError:
        return True

def extract_frontmatter(content: str) -> Tuple[bool, Optional[str], str]:
    """
    Извлекает фронтматтер из markdown-содержимого, если он есть.
    
    Args:
        content: Содержимое файла
        
    Returns:
        Tuple[bool, Optional[str], str]: (имеет ли фронтматтер, фронтматтер, основной контент)
    """
    if content.startswith('---'):
        end_frontmatter = content.find('---', 3)
        if end_frontmatter != -1:
            frontmatter = content[:end_frontmatter + 3]
            main_content = content[end_frontmatter + 3:].strip()
            return True, frontmatter, main_content
    
    return False, None, content

def restore_frontmatter(frontmatter: Optional[str], translated_content: str) -> str:
    """
    Восстанавливает фронтматтер в переведенном содержимом.
    
    Args:
        frontmatter: Строка с фронтматтером
        translated_content: Переведенное основное содержимое
        
    Returns:
        str: Объединенный контент с фронтматтером
    """
    if frontmatter:
        return f"{frontmatter}\n\n{translated_content}"
    return translated_content

def split_content(content: str, max_tokens: int = 8000) -> List[str]:
    """
    Разбивает содержимое на части с учетом ограничения по токенам и сохранением структуры markdown.
    
    Args:
        content: Текст для разбиения
        max_tokens: Максимальное количество токенов в одной части
        
    Returns:
        List[str]: Список частей текста
    """
    # Если текст короткий, возвращаем его как есть
    if len(content) / 4 <= max_tokens:
        return [content]
    
    # Разделяем текст по разделам Markdown
    sections = []
    lines = content.split('\n')
    current_section = []
    current_header_level = 0
    in_code_block = False
    in_table = False
    in_list = False
    list_indent = 0
    
    for i, line in enumerate(lines):
        # Проверка наличия Code Block
        if line.strip().startswith('```'):
            in_code_block = not in_code_block
            current_section.append(line)
            continue
        
        # Пропускаем строки внутри блока кода
        if in_code_block:
            current_section.append(line)
            continue
        
        # Проверка наличия таблицы
        if line.strip().startswith('|') and ('|' in line[1:]):
            if not in_table:
                in_table = True
            current_section.append(line)
            continue
        elif in_table and line.strip() == '':
            in_table = False
            current_section.append(line)
            continue
        
        # Проверка наличия списка
        list_match = re.match(r'^(\s*)[-*+]\s', line)
        if list_match:
            indent = len(list_match.group(1))
            if not in_list:
                in_list = True
                list_indent = indent
            current_section.append(line)
            continue
        elif in_list and line.strip() == '':
            # Проверяем, если следующая строка продолжает список
            if i + 1 < len(lines) and re.match(r'^(\s*)[-*+]\s', lines[i+1]):
                current_section.append(line)
                continue
            else:
                in_list = False
                current_section.append(line)
                continue
        
        # Определяем заголовок
        header_match = re.match(r'^(#{1,6})\s+(.+)$', line)
        
        if header_match:
            header_level = len(header_match.group(1))
            
            # Если уже есть данные и встретили новый заголовок того же или более высокого уровня
            if current_section and (header_level <= current_header_level or current_header_level == 0):
                sections.append('\n'.join(current_section))
                current_section = []
            
            current_header_level = header_level
        
        current_section.append(line)
    
    # Добавляем последний раздел
    if current_section:
        sections.append('\n'.join(current_section))
    
    # Объединяем разделы в части с учетом ограничения по токенам
    parts = []
    current_part = []
    current_tokens = 0
    
    for section in sections:
        section_tokens = len(section) / 4  # Примерная оценка количества токенов
        
        # Если раздел слишком большой, разбиваем его на абзацы
        if section_tokens > max_tokens:
            # Сохраняем текущую часть перед обработкой большого раздела
            if current_part:
                parts.append('\n\n'.join(current_part))
                current_part = []
                current_tokens = 0
                            
            # Разбиваем большой раздел
            section_lines = section.split('\n')
            
            # Обработка больших секций: разбиваем по абзацам сохраняя структуру
            paragraphs = []
            current_paragraph = []
            
            for line in section_lines:
                if line.strip() == '':
                    if current_paragraph:
                        paragraphs.append('\n'.join(current_paragraph))
                        current_paragraph = []
                else:
                    current_paragraph.append(line)
            
            if current_paragraph:
                paragraphs.append('\n'.join(current_paragraph))
            
            # Группируем абзацы в части с учетом ограничения по токенам
            sub_current_part = []
            sub_current_tokens = 0
            
            for paragraph in paragraphs:
                paragraph_tokens = len(paragraph) / 4
                
                if sub_current_tokens + paragraph_tokens > max_tokens:
                    if sub_current_part:
                        parts.append('\n\n'.join(sub_current_part))
                        sub_current_part = []
                        sub_current_tokens = 0
                
                sub_current_part.append(paragraph)
                sub_current_tokens += paragraph_tokens
            
            if sub_current_part:
                parts.append('\n\n'.join(sub_current_part))
        else:
            # Проверяем, поместится ли раздел в текущую часть
            if current_tokens + section_tokens > max_tokens:
                if current_part:
                    parts.append('\n\n'.join(current_part))
                    current_part = []
                    current_tokens = 0
            
            current_part.append(section)
            current_tokens += section_tokens
    
    # Добавляем последнюю часть
    if current_part:
        parts.append('\n\n'.join(current_part))
    
    log_info(f"Файл разбит на {len(parts):,} частей с сохранением логической структуры Markdown")
    
    # Вывод информации о размерах частей
    for i, part in enumerate(parts):
        part_tokens = len(part) / 4
        log_info(f"Часть #{i+1}: ~{int(part_tokens):,} токенов, {len(part):,} символов")
    
    return parts 