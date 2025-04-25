import re
from typing import Dict, Tuple, Any, Optional
from openai import OpenAI
from utils.logger import log_info, log_error
from utils.prompt_utils import load_prompt_improvements

class Translator:
    """Класс для перевода текста с использованием OpenAI API."""
    
    def __init__(self, client: OpenAI, model_name: str, glossary: Dict[str, Dict[str, str]]):
        """
        Инициализирует переводчик.
        
        Args:
            client: Клиент OpenAI API
            model_name: Название модели для использования
            glossary: Словарь с терминами для глоссария
        """
        self.client = client
        self.model_name = model_name
        self.glossary = glossary
        self.total_tokens_processed = 0
    
    def translate_text(self, text: str, target_language: str, system_prompt: str, 
                       context: Optional[Dict[str, Any]] = None) -> Tuple[str, Dict[str, Any]]:
        """
        Переводит текст на указанный язык с использованием глоссария и контекста.
        
        Args:
            text: Текст для перевода
            target_language: Целевой язык перевода
            system_prompt: Системный промпт для перевода
            context: Словарь с контекстной информацией между частями
            
        Returns:
            Tuple[str, Dict[str, Any]]: Переведенный текст и обновленный контекст
        """
        # Инициализация контекста, если он не передан
        if context is None:
            context = {
                "translated_terms": {},  # Словарь для согласованного перевода терминов
                "part_number": 1,        # Номер текущей части
                "total_tokens": 0        # Общее количество обработанных токенов
            }
        
        # Добавляем глоссарий к системному промпту
        glossary_prompt = "\nГлоссарий терминов (русский -> целевой язык):\n"
        for ru_term, translations in self.glossary.items():
            if target_language in translations:
                glossary_prompt += f"'{ru_term}' -> '{translations[target_language]}'\n"
        
        # Добавляем предыдущие переводы терминов для согласованности
        if context["translated_terms"]:
            glossary_prompt += "\nПредыдущие переводы терминов в этом документе:\n"
            for term, translation in context["translated_terms"].items():
                glossary_prompt += f"'{term}' -> '{translation}'\n"
        
        # Добавляем улучшения промпта на основе предыдущих ошибок
        improvements = load_prompt_improvements(target_language)
        
        # Формируем итоговый промпт
        enhanced_system_prompt = system_prompt + glossary_prompt + improvements
        
        # Больше не добавляем информацию о части, т.к. она не должна быть в итоговом файле
        user_prompt = text
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": enhanced_system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.0
            )
            translated_text = response.choices[0].message.content
            
            # Подсчитываем токены
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            total_tokens = prompt_tokens + completion_tokens
            
            # Увеличиваем глобальный счетчик
            self.total_tokens_processed += total_tokens
            context["total_tokens"] += total_tokens
            
            # Проверяем, не содержит ли ответ дополнительные объяснения
            # Если ответ начинается с "Translation:" или подобных фраз, удаляем их
            if translated_text.lower().startswith(("translation:", "перевод:", "translated text:", "переведенный текст:")):
                translated_text = translated_text.split(":", 1)[1].strip()
            
            # Удаляем возможные маркеры начала и конца перевода
            translated_text = re.sub(r'^```.*\n', '', translated_text)
            translated_text = re.sub(r'\n```$', '', translated_text)
            
            # Обновляем номер части для следующего вызова
            context["part_number"] += 1
            
            # Обновляем переведенные термины
            self._update_translated_terms(text, target_language, context)
            
            return translated_text, context
        
        except Exception as e:
            log_error(f"Ошибка при переводе текста: {e}")
            return text, context
    
    def _update_translated_terms(self, text: str, target_language: str, context: Dict[str, Any]) -> None:
        """
        Обновляет список переведенных терминов в контексте.
        
        Args:
            text: Исходный текст
            target_language: Целевой язык перевода
            context: Контекст с переведенными терминами
        """
        for ru_term in self.glossary.keys():
            if ru_term in text and ru_term not in context["translated_terms"]:
                if target_language in self.glossary[ru_term]:
                    context["translated_terms"][ru_term] = self.glossary[ru_term][target_language]
    
    def get_total_tokens(self) -> int:
        """
        Возвращает общее количество обработанных токенов.
        
        Returns:
            int: Количество токенов
        """
        return self.total_tokens_processed 