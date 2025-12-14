AQA Test Additions

Добавлены дополнительные unit-тесты для покрытия сценариев AQA:

4) Timeout / Slow Response Test
- Файл: tests/unit/test_app.py
- Тест: test_call_llm_timeout_slow_response
- Описание: замокан `requests.post` с выбрасыванием `requests.exceptions.Timeout`.
  Проверяется, что `call_llm` возвращает строку с описанием таймаута и не вызывает исключение.

5) Invalid Input Test
- Файл: tests/unit/test_app.py
- Тест: test_call_llm_invalid_input
- Описание: проверяются случаи некорректного типа `messages` (int), пустой строки и
  слишком длинного текста. Для корректного прохождения теста в `src/app.py` реализована
  базовая валидация: тип, пустой prompt и ограничение длины (10000 символов).

6) Malformed API Response Test
- Файл: tests/unit/test_app.py
- Тест: test_call_llm_malformed_api_response
- Описание: замокан ответ API без поля `response`. Проверяется, что `call_llm`
  возвращает диагностическое сообщение и не падает.

Как запускать

1) Убедитесь, что вы находитесь в виртуальном окружении и установили pytest:
   python -m venv .venv
   source .venv/bin/activate
   pip install pytest

2) Запуск всех unit-тестов:
   pytest tests/unit -q

Примечания для QA-инженера
- Тесты используют мок `patch.object(app, 'requests')`, поэтому реальные HTTP-запросы
  не выполняются.
- Если вы меняете поведение `call_llm` (формат ошибок или текст сообщений), обновите
  соответствующие утверждения в тестах.
- Для интеграционных проверок (без моков) убедитесь, что сервис Mentorpiece доступен
  и правильные endpoint/ключи заданы в окружении.
