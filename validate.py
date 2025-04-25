import os
import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv
from openai import OpenAI

# Импортируем наши утилиты
from utils import (
    log_info, log_error, log_warning, setup_logging,
    load_config, get_validation_prompt, load_glossary,
    save_prompt_improvement
)

# Глобальный счетчик токенов
total_tokens_used = 0

def validate_translation(original_text: str, translated_text: str, target_language: str, file_path: str,
                         client: OpenAI, model_name: str, glossary: Dict[str, Dict[str, str]],
                         config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Валидирует перевод с использованием GPT.
    
    Args:
        original_text: Исходный текст на русском
        translated_text: Переведенный текст
        target_language: Целевой язык перевода
        file_path: Путь к файлу для включения в отчет
        client: Клиент OpenAI API
        model_name: Название модели для валидации
        glossary: Словарь с терминами для глоссария
        config: Общая конфигурация
        
    Returns:
        Dict: Результат валидации в формате JSON
    """
    global total_tokens_used
    
    # Получаем валидационный промпт
    system_prompt = get_validation_prompt(config, target_language)
    
    # Формируем промпт с глоссарием
    glossary_prompt = "\nГлоссарий терминов (русский -> целевой язык):\n"
    for ru_term, translations in glossary.items():
        if target_language in translations:
            glossary_prompt += f"'{ru_term}' -> '{translations[target_language]}'\n"
    
    enhanced_system_prompt = f"{system_prompt}\n{glossary_prompt}\n\nВАЖНО: Возвращай ответ ТОЛЬКО в JSON формате с полем 'issues'. Проверяй ТОЛЬКО на серьезные ошибки перевода. НЕ отмечай как ошибки правильно переведенные термины из глоссария. Если ошибок нет, верни пустой массив issues: []."
    
    try:
        # Подготовка пользовательского сообщения
        user_message = f"""
        ОРИГИНАЛЬНЫЙ ТЕКСТ (русский):
        {original_text}
        
        ПЕРЕВЕДЕННЫЙ ТЕКСТ ({target_language}):
        {translated_text}
        
        Проведи анализ качества перевода и найди ТОЛЬКО РЕАЛЬНЫЕ ошибки, игнорируя стилистические различия.
        
        Возвращай результат СТРОГО в следующем JSON формате:
        {{
          "issues": [
            {{
              "file_path": "{file_path}",
              "original": "проблемное место в исходном тексте (только фрагмент с ошибкой)",
              "translated": "проблемное место в переводе (только фрагмент с ошибкой)",
              "reason": "краткая причина проблемы (макс. 1 предложение)"
            }}
          ]
        }}
        
        Если ошибок нет, верни:
        {{
          "issues": []
        }}
        """
        
        # Отправка запроса на валидацию
        log_info(f"Отправка запроса на валидацию перевода для {file_path}")
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": enhanced_system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.0,  # Уменьшаем температуру для более предсказуемых результатов
            response_format={"type": "json_object"},  # Указываем формат ответа как JSON
            max_tokens=2000
        )
        
        # Подсчет токенов
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        file_total_tokens = prompt_tokens + completion_tokens
        total_tokens_used += file_total_tokens
        
        # Логируем информацию о токенах
        log_info(f"Использовано токенов для {file_path}: {file_total_tokens} (промпт: {prompt_tokens}, ответ: {completion_tokens})")
        
        # Получение и разбор ответа
        validation_result = response.choices[0].message.content.strip()
        
        # Пытаемся распарсить JSON из ответа
        try:
            validation_data = json.loads(validation_result)
            
            # Фильтруем ложные срабатывания и очищаем данные
            filtered_issues = []
            if "issues" in validation_data and validation_data["issues"]:
                for issue in validation_data["issues"]:
                    # Проверяем, относится ли "ошибка" к термину из глоссария
                    is_false_positive = False
                    
                    original = issue.get("original", "").lower()
                    translated = issue.get("translated", "").lower()
                    reason = issue.get("reason", "").lower()
                    
                    for ru_term, translations in glossary.items():
                        if ru_term.lower() in original and target_language in translations:
                            term_translation = translations[target_language].lower()
                            # Если перевод термина соответствует глоссарию, но модель считает это ошибкой
                            if term_translation in translated and ("глоссари" in reason or "словар" in reason or "термин" in reason):
                                is_false_positive = True
                                log_info(f"Отфильтровано ложное срабатывание: '{original}' -> '{translated}'")
                                break
                    
                    # Исключаем неполные или слишком короткие сообщения
                    if not original or not translated or not reason or len(original) < 3 or len(translated) < 3:
                        is_false_positive = True
                    
                    if not is_false_positive:
                        # Убеждаемся, что file_path установлен правильно
                        issue["file_path"] = file_path
                        filtered_issues.append(issue)
                        
                        # Сохраняем улучшение промпта для будущих переводов
                        save_prompt_improvement(target_language, issue)
            
            # Заменяем оригинальные issues на отфильтрованные
            validation_data["issues"] = filtered_issues
            return validation_data
        
        except json.JSONDecodeError as e:
            log_error(f"Ошибка парсинга JSON из ответа: {e}")
            return {"issues": []}
    
    except Exception as e:
        log_error(f"Ошибка при валидации перевода: {e}")
        return {"issues": []}

def validate_file(original_file: str, translated_file: str, target_language: str,
                 client: OpenAI, model_name: str, glossary: Dict[str, Dict[str, str]],
                 config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Валидирует перевод одного файла.
    
    Args:
        original_file: Путь к оригинальному файлу
        translated_file: Путь к переведенному файлу
        target_language: Целевой язык перевода
        client: Клиент OpenAI API
        model_name: Название модели для валидации
        glossary: Словарь с терминами для глоссария
        config: Общая конфигурация
        
    Returns:
        Optional[Dict[str, Any]]: Результат валидации или None в случае ошибки
    """
    try:
        # Проверяем, существуют ли файлы
        if not os.path.exists(original_file):
            log_error(f"Оригинальный файл не найден: {original_file}")
            return None
        
        if not os.path.exists(translated_file):
            log_error(f"Переведенный файл не найден: {translated_file}")
            return None
        
        # Читаем содержимое файлов
        with open(original_file, 'r', encoding='utf-8') as f_orig:
            original_text = f_orig.read()
        
        with open(translated_file, 'r', encoding='utf-8') as f_trans:
            translated_text = f_trans.read()
        
        # Получаем относительный путь для отчета
        rel_path = os.path.relpath(translated_file)
        
        # Валидируем перевод
        validation_result = validate_translation(
            original_text, translated_text, target_language, rel_path,
            client, model_name, glossary, config
        )
        
        return validation_result
    
    except Exception as e:
        log_error(f"Ошибка при валидации файла {original_file}: {e}")
        return None

def create_validation_report(validation_results: List[Dict[str, Any]], target_language: str, 
                            report_file: Optional[str] = None) -> None:
    """
    Создает отчет о валидации.
    
    Args:
        validation_results: Список результатов валидации
        target_language: Целевой язык перевода
        report_file: Имя файла для сохранения отчета (опционально)
    """
    try:
        # Объединяем все проблемы из всех файлов
        all_issues = []
        for result in validation_results:
            if result and "issues" in result:
                all_issues.extend(result["issues"])
        
        # Формируем итоговый отчет
        report = {
            "language": target_language,
            "total_files": len(validation_results),
            "total_issues": len(all_issues),
            "issues": all_issues
        }
        
        # Определяем имя файла отчета, если не указано
        if not report_file:
            report_file = f"validation_report_{target_language}.json"
        
        # Сохраняем отчет в файл
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        log_info(f"Отчет о валидации сохранен в файл: {report_file}")
        log_info(f"Всего проблем: {len(all_issues)}")
        
        # Выводим первые 5 проблем (если есть)
        if all_issues:
            log_info("Примеры проблем:")
            for i, issue in enumerate(all_issues[:5]):
                log_info(f"[{i+1}] Файл: {issue.get('file_path', 'N/A')}")
                log_info(f"    Проблема: {issue.get('reason', 'N/A')}")
                log_info(f"    Оригинал: {issue.get('original', 'N/A')}")
                log_info(f"    Перевод: {issue.get('translated', 'N/A')}")
    
    except Exception as e:
        log_error(f"Ошибка при создании отчета о валидации: {e}")

def validate_translations(input_dir: str, output_dir: str, target_language: str, report_file: Optional[str] = None) -> None:
    """
    Валидирует все переведенные файлы.
    
    Args:
        input_dir: Директория с оригинальными файлами
        output_dir: Директория с переведенными файлами
        target_language: Целевой язык перевода
        report_file: Имя файла для сохранения отчета (опционально)
    """
    global total_tokens_used
    # Сбрасываем счетчик токенов
    total_tokens_used = 0
    
    # Загрузка конфигурации
    config = load_config()
    
    # Загрузка глоссария
    glossary = load_glossary()
    
    # Инициализация клиента OpenAI
    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=config.get("api", {}).get("base_url", os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    )
    
    # Получение названия модели из конфигурации
    model_name = config.get("api", {}).get("model_name", os.getenv("MODEL_NAME", "gpt-4o-mini"))
    
    # Полный путь к директории с переведенными файлами
    target_output_dir = os.path.join(output_dir, target_language)
    
    # Проверяем, существуют ли директории
    if not os.path.exists(input_dir):
        log_error(f"Директория с оригинальными файлами не найдена: {input_dir}")
        return
    
    if not os.path.exists(target_output_dir):
        log_error(f"Директория с переведенными файлами не найдена: {target_output_dir}")
        return
    
    log_info(f"Начало валидации переводов с языка '{target_language}'")
    
    # Получаем список всех переведенных файлов .md/.mdx
    validation_results = []
    validated_files_count = 0
    
    for root, _, files in os.walk(target_output_dir):
        for file in sorted(files):
            if file.endswith(('.md', '.mdx')):
                translated_file = os.path.join(root, file)
                
                # Формируем путь к оригинальному файлу
                rel_path = os.path.relpath(translated_file, target_output_dir)
                original_file = os.path.join(input_dir, rel_path)
                
                # Проверяем наличие оригинального файла
                if os.path.exists(original_file):
                    log_info(f"Валидация файла: {rel_path}")
                    validated_files_count += 1
                    
                    # Валидируем перевод
                    result = validate_file(
                        original_file, translated_file, target_language,
                        client, model_name, glossary, config
                    )
                    
                    if result:
                        validation_results.append(result)
    
    # Создаем отчет о валидации
    create_validation_report(validation_results, target_language, report_file)
    
    # Логируем общую информацию о токенах
    log_info(f"Всего проверено файлов: {validated_files_count}")
    log_info(f"Всего использовано токенов: {total_tokens_used}")
    if validated_files_count > 0:
        avg_tokens = total_tokens_used / validated_files_count
        log_info(f"Среднее количество токенов на файл: {avg_tokens:.2f}")
    
    log_info("Валидация завершена")

def parse_arguments():
    """
    Разбирает аргументы командной строки.
    
    Returns:
        argparse.Namespace: Объект с аргументами
    """
    parser = argparse.ArgumentParser(description='Валидация переводов документации')
    parser.add_argument('--language', type=str, default='en', help='Целевой язык перевода (en, es, zh)')
    parser.add_argument('--input_dir', type=str, default='input', help='Директория с исходными файлами')
    parser.add_argument('--output_dir', type=str, default='output', help='Директория с переведенными файлами')
    parser.add_argument('--report', type=str, help='Файл для сохранения отчета о валидации')
    parser.add_argument('--log_level', type=str, default='INFO', 
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], help='Уровень логирования')
    parser.add_argument('--log_file', type=str, help='Файл для сохранения логов')
    return parser.parse_args()

# Загрузка переменных окружения
load_dotenv()

def main():
    """Основная функция для запуска валидации переводов."""
    # Разбор аргументов командной строки
    args = parse_arguments()
    
    # Настройка логирования
    setup_logging(args.log_level, args.log_file)
    
    # Запуск валидации
    validate_translations(
        args.input_dir, 
        args.output_dir, 
        args.language, 
        args.report
    )

if __name__ == "__main__":
    main() 