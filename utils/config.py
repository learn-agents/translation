import os
import yaml
from typing import Dict, Any, Optional
from utils.logger import log_error

def load_config(config_path: str = 'config.yaml') -> Dict[str, Any]:
    """
    Загружает конфигурацию из YAML файла.
    
    Args:
        config_path: Путь к файлу конфигурации
        
    Returns:
        Dict[str, Any]: Словарь с конфигурацией
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            return config
    except Exception as e:
        log_error(f"Ошибка загрузки конфигурации из {config_path}: {e}")
        return {"general": {"max_tokens": 8000, "max_workers": 4}, "api": {}, "languages": {}}

def get_language_config(config: Dict[str, Any], target_language: str) -> Dict[str, Any]:
    """
    Получает конфигурацию для указанного языка.
    
    Args:
        config: Словарь с общей конфигурацией
        target_language: Код целевого языка
        
    Returns:
        Dict[str, Any]: Конфигурация языка или пустой словарь
    """
    return config.get("languages", {}).get(target_language, {})

def get_system_prompt(config: Dict[str, Any], target_language: str) -> str:
    """
    Получает системный промпт для указанного языка из конфигурации.
    
    Args:
        config: Словарь с общей конфигурацией
        target_language: Код целевого языка
        
    Returns:
        str: Системный промпт для перевода
    """
    # Получаем промпт из конфигурации
    language_config = get_language_config(config, target_language)
    system_prompt = language_config.get("system_prompt", "")
    
    # Если промпт не найден, используем стандартный промпт
    if not system_prompt:
        if target_language == "en":
            system_prompt = """
            Translate the following markdown text from Russian to English.
            Preserve all markdown formatting, code blocks, and structure.
            Keep technical terms consistent throughout the translation.
            Do not translate code snippets, variable names, or commands inside code blocks.
            
            IMPORTANT: Return ONLY the translated text without any explanations, comments, or additional information.
            Do not include the original Russian text in your response.
            Do not add any explanations about your translation process.
            """
        elif target_language == "es":
            system_prompt = """
            Traduce el siguiente texto markdown del ruso al español.
            Conserva todo el formato markdown, bloques de código y estructura.
            Mantén los términos técnicos consistentes a lo largo de la traducción.
            No traduzcas fragmentos de código, nombres de variables o comandos dentro de bloques de código.
            
            IMPORTANTE: Devuelve SOLO el texto traducido sin explicaciones, comentarios o información adicional.
            No incluyas el texto original en ruso en tu respuesta.
            No agregues explicaciones sobre tu proceso de traducción.
            """
        elif target_language == "zh":
            system_prompt = """
            将以下markdown文本从俄语翻译成中文。
            保留所有markdown格式、代码块和结构。
            在整个翻译过程中保持技术术语的一致性。
            不要翻译代码块中的代码片段、变量名或命令。
            
            重要提示：仅返回翻译后的文本，不要添加任何解释、评论或额外信息。
            不要在回复中包含原始俄语文本。
            不要添加关于您翻译过程的解释。
            """
        else:
            system_prompt = f"""
            Translate the following markdown text from Russian to {target_language}.
            Preserve all markdown formatting, code blocks, and structure.
            Keep technical terms consistent throughout the translation.
            Do not translate code snippets, variable names, or commands inside code blocks.
            
            IMPORTANT: Return ONLY the translated text without any explanations, comments, or additional information.
            Do not include the original Russian text in your response.
            Do not add any explanations about your translation process.
            """
    
    return system_prompt.strip()

def get_validation_prompt(config: Dict[str, Any], target_language: str) -> str:
    """
    Получает валидационный промпт для указанного языка из конфигурации.
    
    Args:
        config: Словарь с общей конфигурацией
        target_language: Код целевого языка
        
    Returns:
        str: Валидационный промпт
    """
    # Получаем промпт из конфигурации
    language_config = get_language_config(config, target_language)
    validation_prompt = language_config.get("validation_prompt", "")
    
    # Если промпт не найден, используем стандартный промпт
    if not validation_prompt:
        validation_prompt = f"""Ты эксперт по валидации переводов с русского на {target_language}.

Твоя задача - найти ТОЛЬКО СЕРЬЕЗНЫЕ ошибки перевода, игнорируя стилистические вариации. 

При проверке придерживайся следующих принципов:
1. Проверяй соответствие ТОЛЬКО терминов из глоссария - отмечай термины, которые ОДНОЗНАЧНО противоречат глоссарию.
2. Проверяй сохранение форматирования markdown.
3. Проверяй точность передачи смысла.
4. Проверяй сохранность кода и технических элементов.

НЕ ОТМЕЧАЙ как ошибки:
- Стилистические вариации перевода
- Правильно переведенные термины из глоссария
- Незначительные различия в пунктуации
- Разные способы выражения одной и той же мысли

Возвращай ТОЛЬКО JSON с массивом issues, где каждый элемент содержит:
- file_path: путь к файлу
- original: фрагмент из оригинала с ошибкой
- translated: соответствующий фрагмент в переводе
- reason: короткое объяснение ошибки (1 предложение)

Если ошибок нет, верни пустой массив issues: []."""
    
    return validation_prompt.strip()

def load_glossary(glossary_path: str = 'glossary.yaml') -> Dict[str, Dict[str, str]]:
    """
    Загружает глоссарий из YAML файла.
    
    Args:
        glossary_path: Путь к файлу глоссария
        
    Returns:
        Dict[str, Dict[str, str]]: Словарь терминов с переводами
    """
    try:
        with open(glossary_path, 'r', encoding='utf-8') as f:
            glossary = yaml.safe_load(f)
            return glossary.get('terms', {})
    except Exception as e:
        log_error(f"Ошибка загрузки глоссария из {glossary_path}: {e}")
        return {} 