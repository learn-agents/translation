import os
import json
from typing import Dict, List, Any
from utils.logger import log_info, log_error

def get_improvements_dir() -> str:
    """
    Возвращает полный путь к директории с улучшениями промптов.
    
    Returns:
        str: Путь к директории prompt_improvements
    """
    # Получаем абсолютный путь к текущему файлу (__file__ содержит путь к prompt_utils.py)
    current_file_path = os.path.abspath(__file__)
    
    # Переходим к родительской директории (utils)
    utils_dir = os.path.dirname(current_file_path)
    
    # Переходим к родительской директории (minimal_translation)
    project_dir = os.path.dirname(utils_dir)
    
    # Полный путь к директории с улучшениями
    improvements_dir = os.path.join(project_dir, "prompt_improvements")
    
    return improvements_dir

def load_prompt_improvements(target_language: str) -> str:
    """
    Загружает и применяет улучшения промпта из файла для указанного языка.
    
    Args:
        target_language: Код целевого языка
        
    Returns:
        str: Дополнительный контекст для промпта на основе предыдущих ошибок
    """
    # Путь к директории с улучшениями
    improvements_dir = get_improvements_dir()
    
    # Полный путь к файлу улучшений
    improvements_file = os.path.join(improvements_dir, f"prompt_improvements_{target_language}.json")
    
    try:
        if not os.path.exists(improvements_file):
            log_info(f"Файл улучшений промпта '{improvements_file}' не найден, используем базовый промпт")
            return ""
        
        with open(improvements_file, 'r', encoding='utf-8') as f:
            improvements = json.load(f)
        
        if not improvements or not isinstance(improvements, list):
            return ""
        
        # Формируем контекст для улучшения промпта
        context = "\n\nBased on previous translation issues, pay special attention to these cases:\n"
        
        for idx, improvement in enumerate(improvements[-10:], 1):  # Берем только последние 10 улучшений
            original = improvement.get("original", "")
            translated = improvement.get("translated", "")
            reason = improvement.get("reason", "")
            
            if original and translated and reason:
                context += f"{idx}. Issue: {reason}\n"
                context += f"   Original: {original}\n"
                context += f"   Incorrect translation: {translated}\n"
                context += f"   Avoid this mistake.\n\n"
        
        log_info(f"Применено {min(len(improvements), 10)} улучшений промпта для языка '{target_language}'")
        return context
    
    except Exception as e:
        log_error(f"Ошибка при загрузке улучшений промпта: {e}")
        return ""

def save_prompt_improvement(target_language: str, issue: Dict[str, str]) -> None:
    """
    Сохраняет новое улучшение промпта на основе найденной проблемы.
    
    Args:
        target_language: Код целевого языка
        issue: Информация о проблеме (оригинал, перевод, причина)
    """
    # Путь к директории с улучшениями
    improvements_dir = get_improvements_dir()
    
    # Создаем директорию, если она не существует
    os.makedirs(improvements_dir, exist_ok=True)
    
    # Полный путь к файлу улучшений
    improvements_file = os.path.join(improvements_dir, f"prompt_improvements_{target_language}.json")
    
    try:
        # Загружаем существующие улучшения
        existing_improvements = []
        
        if os.path.exists(improvements_file):
            with open(improvements_file, 'r', encoding='utf-8') as f:
                existing_improvements = json.load(f)
        
        # Получаем данные из проблемы
        original = issue.get("original", "").strip()
        translated = issue.get("translated", "").strip()
        reason = issue.get("reason", "").strip()
        
        # Если одно из полей пустое, пропускаем сохранение
        if not original or not translated or not reason:
            log_info("Неполные данные в проблеме, пропускаем сохранение улучшения")
            return
            
        # Проверка на дубликаты и схожие проблемы
        is_duplicate = False
        
        for existing in existing_improvements:
            existing_original = existing.get("original", "").strip()
            existing_translated = existing.get("translated", "").strip()
            existing_reason = existing.get("reason", "").strip()
            
            # Проверка на точное совпадение (как было раньше)
            if original == existing_original and translated == existing_translated:
                log_info("Точное совпадение улучшения найдено, пропускаем")
                return
            
            # Проверка на схожесть проблем
            # 1. Проверяем схожесть причины проблемы
            reason_similarity = calculate_similarity(reason.lower(), existing_reason.lower())
            
            # 2. Проверяем схожесть текста оригинала и перевода
            original_similarity = calculate_similarity(original.lower(), existing_original.lower())
            translated_similarity = calculate_similarity(translated.lower(), existing_translated.lower())
            
            # Если и причина и тексты достаточно похожи, считаем проблему дубликатом
            if (reason_similarity > 0.7 and 
                (original_similarity > 0.6 or translated_similarity > 0.6)):
                log_info(f"Схожая проблема уже существует (схожесть причины: {reason_similarity:.2f}, " 
                        f"схожесть оригинала: {original_similarity:.2f}, "
                        f"схожесть перевода: {translated_similarity:.2f})")
                is_duplicate = True
                break
        
        if is_duplicate:
            return
        
        # Добавляем новое улучшение
        existing_improvements.append({
            "original": original,
            "translated": translated,
            "reason": reason
        })
        
        # Сохраняем обновленный список улучшений
        with open(improvements_file, 'w', encoding='utf-8') as f:
            json.dump(existing_improvements, f, ensure_ascii=False, indent=2)
        
        log_info(f"Добавлено новое улучшение промпта для языка '{target_language}'")
    
    except Exception as e:
        log_error(f"Ошибка при сохранении улучшения промпта: {e}")

def calculate_similarity(text1: str, text2: str) -> float:
    """
    Рассчитывает коэффициент схожести двух текстов, используя отношение Жаккара для n-грамм.
    
    Args:
        text1: Первый текст для сравнения
        text2: Второй текст для сравнения
        
    Returns:
        float: Значение от 0 до 1, где 1 означает полное совпадение
    """
    if not text1 or not text2:
        return 0.0
        
    # Если тексты идентичны
    if text1 == text2:
        return 1.0
    
    # Разбиваем тексты на n-граммы (триграммы слов и символов)
    words1 = text1.split()
    words2 = text2.split()
    
    # Для очень коротких текстов используем простое сравнение слов
    if len(words1) < 3 or len(words2) < 3:
        # Создаем множества слов
        set1 = set(words1)
        set2 = set(words2)
        
        # Коэффициент Жаккара: размер пересечения / размер объединения
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        
        return intersection / union if union > 0 else 0.0
    
    # Для более длинных текстов используем n-граммы
    # Создаем триграммы слов
    word_trigrams1 = set()
    word_trigrams2 = set()
    
    for i in range(len(words1) - 2):
        trigram = ' '.join(words1[i:i+3])
        word_trigrams1.add(trigram)
    
    for i in range(len(words2) - 2):
        trigram = ' '.join(words2[i:i+3])
        word_trigrams2.add(trigram)
    
    # Рассчитываем схожесть по триграммам слов
    word_intersection = len(word_trigrams1.intersection(word_trigrams2))
    word_union = len(word_trigrams1.union(word_trigrams2))
    word_similarity = word_intersection / word_union if word_union > 0 else 0.0
    
    # Для повышения точности также учитываем схожесть символьных n-грамм
    # (особенно важно для короткого текста или текста на языках, где слова не разделены пробелами)
    char_trigrams1 = set()
    char_trigrams2 = set()
    
    text1_clean = ''.join(c for c in text1 if c.isalnum() or c.isspace())
    text2_clean = ''.join(c for c in text2 if c.isalnum() or c.isspace())
    
    for i in range(len(text1_clean) - 2):
        char_trigrams1.add(text1_clean[i:i+3])
    
    for i in range(len(text2_clean) - 2):
        char_trigrams2.add(text2_clean[i:i+3])
    
    char_intersection = len(char_trigrams1.intersection(char_trigrams2))
    char_union = len(char_trigrams1.union(char_trigrams2))
    char_similarity = char_intersection / char_union if char_union > 0 else 0.0
    
    # Финальный коэффициент схожести - комбинация схожести слов и символов
    # с большим весом для схожести слов
    return 0.7 * word_similarity + 0.3 * char_similarity

def translate_frontmatter(frontmatter: str, translate_text_func, target_language: str, system_prompt: str) -> str:
    """
    Парсит YAML фронтматтер, переводит значения (но не ключи) и восстанавливает структуру.
    
    Args:
        frontmatter: Строка с фронтматтером в формате YAML
        translate_text_func: Функция для перевода текста
        target_language: Целевой язык перевода
        system_prompt: Системный промпт для перевода
        
    Returns:
        str: Переведенный фронтматтер в формате YAML
    """
    import yaml
    import re
    from utils.logger import log_info, log_error
    
    # Удаляем маркеры '---' для парсинга
    yaml_content = frontmatter.strip().replace('---', '', 1)
    end_pos = yaml_content.rfind('---')
    if end_pos != -1:
        yaml_content = yaml_content[:end_pos].strip()
    
    try:
        # Парсим YAML
        frontmatter_data = yaml.safe_load(yaml_content)
        
        if not frontmatter_data or not isinstance(frontmatter_data, dict):
            log_info("Фронтматтер пуст или не является словарем, оставляем без изменений")
            return frontmatter
        
        # Переводим значения полей фронтматтера
        translated_data = {}
        for key, value in frontmatter_data.items():
            if isinstance(value, str) and value.strip():
                log_info(f"Перевод поля фронтматтера: {key}")
                
                # Создаем специальный промпт для фронтматтера, чтобы избежать многострочных переводов
                frontmatter_system_prompt = f"""
                Translate the following short text from Russian to {target_language}.
                IMPORTANT: The text is a single field in a YAML frontmatter, so the translation MUST be a SINGLE LINE.
                DO NOT add any explanations, quotes, or multiple lines.
                DO NOT include the original Russian text in your response.
                JUST translate the text as concisely as possible.
                """
                
                # Специальный контекст для фронтматтера
                frontmatter_context = {
                    "translated_terms": {},
                    "part_number": 1,
                    "total_tokens": 0
                }
                
                # Используем тот же механизм перевода, но с модифицированным промптом
                translated_value, _ = translate_text_func(value, target_language, frontmatter_system_prompt, frontmatter_context)
                
                # Проверяем, не содержит ли ответ дополнительные объяснения
                if translated_value.lower().startswith(("translation:", "перевод:", "translated text:", "переведенный текст:")):
                    translated_value = translated_value.split(":", 1)[1].strip()
                
                # Удаляем возможные маркеры начала и конца перевода
                translated_value = re.sub(r'^```.*\n', '', translated_value)
                translated_value = re.sub(r'\n```$', '', translated_value)
                
                # Очищаем от кавычек
                translated_value = translated_value.strip('"\'')
                
                # Обязательно убеждаемся, что перевод - это одна строка без переносов
                translated_value = translated_value.replace('\n', ' ').strip()
                
                translated_data[key] = translated_value
            else:
                # Непереводимые значения (числа, массивы, пустые строки) оставляем как есть
                translated_data[key] = value
        
        # Преобразуем обратно в YAML
        translated_yaml = yaml.dump(translated_data, allow_unicode=True, sort_keys=False)
        
        # Восстанавливаем маркеры '---'
        return f"---\n{translated_yaml}---"
    
    except Exception as e:
        log_error(f"Ошибка при обработке фронтматтера: {e}")
        # В случае ошибки возвращаем оригинальный фронтматтер
        return frontmatter 