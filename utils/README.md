# Модули утилит для системы перевода

Этот каталог содержит вспомогательные модули, используемые основной системой перевода.

## Структура модулей

### `__init__.py`
Инициализационный файл, который экспортирует основные функции и классы из всех модулей для удобного импорта.

### `logger.py`
Модуль для логирования, предоставляющий следующие функции:
- `setup_logging` - настройка системы логирования с опциональным выводом в файл
- `log_info` - вывод информационных сообщений
- `log_error` - вывод сообщений об ошибках
- `log_debug` - вывод отладочных сообщений (только при уровне DEBUG)
- `log_warning` - вывод предупреждений

### `config.py`
Модуль для работы с конфигурацией:
- `load_config` - загрузка конфигурации из файла YAML
- `get_language_config` - получение конфигурации для указанного языка
- `get_system_prompt` - получение системного промпта для перевода
- `get_validation_prompt` - получение промпта для валидации
- `load_glossary` - загрузка глоссария терминов

### `file_utils.py`
Модуль для работы с файлами и их содержимым:
- `is_binary_file` - проверка является ли файл бинарным
- `extract_frontmatter` - извлечение фронтматтера из markdown-файла
- `restore_frontmatter` - восстановление фронтматтера в переведенном файле
- `split_content` - интеллектуальное разбиение контента на части с учетом маркдаун-структуры

### `prompt_utils.py`
Модуль для работы с промптами и их улучшениями:
- `load_prompt_improvements` - загрузка улучшений промптов из JSON-файла
- `save_prompt_improvement` - сохранение нового улучшения промпта
- `translate_frontmatter` - специализированный перевод фронтматтера

### `translator.py`
Модуль с основным классом для перевода:
- `Translator` - класс для перевода текста с использованием OpenAI API
  - `translate_text` - метод для перевода текста с сохранением контекста
  - `get_total_tokens` - получение общего количества использованных токенов

## Использование

```python
# Импорт всех утилит
from utils import (
    log_info, setup_logging,
    load_config, load_glossary,
    is_binary_file, split_content,
    Translator
)

# Или импорт отдельных модулей
from utils.logger import log_info, setup_logging
from utils.config import load_config
from utils.file_utils import split_content
from utils.translator import Translator
``` 