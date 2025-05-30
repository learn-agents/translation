# TODO: Улучшения системы перевода

## Приоритет: Высокий
1. ✅ **Исправление отчета валидации**
   - ✅ Исправить заглушку "путь к файлу" на реальные пути в JSON-отчете
   - ✅ Убедиться, что все 4 поля заполняются корректными данными

2. ✅ **Создание config.yaml**
   - ✅ Перенести настройки из .env в config.yaml
   - ✅ Добавить поддержку выбора языка через конфигурационный файл
   - ✅ Создать профили для разных языков перевода с отдельными системными промптами

3. ✅ **Улучшение разбиения по маркдаун-структуре**
   - ✅ Доработать алгоритм разбиения для лучшего сохранения логических блоков
   - ✅ Не разрывать заголовки от содержимого
   - ✅ Сохранять целостность списков, таблиц и других структур

## Приоритет: Средний
4. ✅ **Система самообучения**
   - ✅ Разработать механизм автоматического улучшения системного промпта
   - ✅ Добавлять проблемные места из отчета валидации в промпты для улучшения будущих переводов
   - ✅ Создать историю улучшений для отслеживания прогресса

5. ✅ **Система "памяти" между частями**
   - ✅ Реализовать передачу контекста между частями разбитого файла
   - ✅ Сохранять согласованность терминологии при переводе больших файлов
   - ✅ Улучшить объединение частей после перевода

## Приоритет: Низкий
6. ✅ **Расширение глоссария**
   - ✅ Добавить больше терминов в глоссарий
   - ✅ Расширить поддержку языков в глоссарии

7. ✅ **Документация**
   - ✅ Создать README с подробным описанием возможностей
   - ✅ Добавить примеры использования
   - ✅ Документировать конфигурационные параметры

## Технический долг
8. ✅ **Рефакторинг кода**
   - ✅ Улучшить модульность кода
   - ✅ Добавить обработку ошибок
   - ✅ Улучшить логирование

## Следующие задачи для реализации
9. **Дедупликация улучшений промптов**
   - ✅ Предотвращение дублирования записей в файлах улучшений промптов
   - ✅ Добавление проверки схожести проблем перед сохранением 
   - Объединение похожих проблем для получения более сжатых улучшений

10. **Расширение возможностей валидации**
    - Улучшение анализа ошибок в переводе (более детальные категории проблем)
    - Добавление статистики по типам ошибок
    - Визуализация отчетов о качестве перевода

11. ✅ **Мониторинг использования API**
    - ✅ Добавление подсчета использованных токенов при валидации
    - ✅ Логирование информации о токенах для каждого файла и всего процесса
    - Добавление ежемесячных отчетов по использованию токенов

12. **Оптимизация процесса** 
    - Уменьшение используемых токенов при валидации
    - Адаптивный выбор модели в зависимости от сложности текста
    - Кэширование результатов валидации для одинаковых текстов 