"""
Unit tests for `src/app.py` using pytest.

These tests mock network calls to the external Mentorpiece API so that
no real HTTP requests are made during testing.

Run with:
  pytest -q

Notes for QA engineers:
- We insert `src/` into `sys.path` so we can import the application module
  as a plain `import app` which mirrors running the Flask app from `src/`.
- We patch `app.requests.post` (the `requests` used by the app module)
  so the tests intercept outgoing HTTP calls and return controlled values.
"""
import sys
import os
import importlib
from unittest.mock import patch
import requests


class MockResponse:
    """Простой mock-объект, имитирующий `requests.Response` с json()."""
    def __init__(self, status_code=200, json_data=None, text_data=None):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text_data or str(self._json)

    def json(self):
        return self._json


def import_app_module():
    """Импортируем модуль `app` из папки `src` и возвращаем его объект.

    Мы явно добавляем `src` в `sys.path`, чтобы импорт был детерминированным
    и не зависел от окружения теста.
    """
    src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
    # Удаляем существующий модуль `app` из кеша, чтобы перезагрузка была чистой
    if 'app' in sys.modules:
        del sys.modules['app']
    import app as app_module
    return app_module


def test_call_llm_success_for_translate_and_judge():
    """Positive Test: ensure call_llm возвращает ожидаемые строки при 200 OK.

    Мы замокаем `requests.post` так, чтобы возвращать разные ответы в
    зависимости от `model_name`, переданного в JSON-пейлоаде.
    """
    app = import_app_module()

    def fake_post(url, json, headers=None, timeout=None):
        model = (json or {}).get('model_name')
        if model == "Qwen/Qwen3-VL-30B-A3B-Instruct":
            return MockResponse(200, {"response": "Mocked Translation: The sun is shining."})
        if model == "claude-sonnet-4-5-20250929":
            return MockResponse(200, {"response": "Mocked Grade: 9/10. Fluent and accurate."})
        return MockResponse(500, {"error": "unknown model"})

    with patch.object(app, 'requests') as requests_module:
        requests_module.post.side_effect = fake_post

        translate = app.call_llm("Qwen/Qwen3-VL-30B-A3B-Instruct", ["Переведи", "Солнце светит."])
        assert "Mocked Translation: The sun is shining." in translate

        grade = app.call_llm("claude-sonnet-4-5-20250929", ["Оцени", "Солнце светит."])
        assert "Mocked Grade: 9/10" in grade


def test_environment_loading(monkeypatch):
    """Environment Test: проверяем, что значение `MENTORPIECE_API_KEY` берётся из окружения.

    Мы задаём переменную окружения, затем импортируем (или перезагружаем)
    модуль `app` и убеждаемся, что константа содержит ожидаемое значение.
    """
    monkeypatch.setenv('MENTORPIECE_API_KEY', 'test-env-key')
    # Перезагружаем модуль, чтобы он прочитал текущие переменные окружения
    app = import_app_module()
    assert getattr(app, 'MENTORPIECE_API_KEY') == 'test-env-key'

    # Удалим переменную и перезагрузим — ожидаем None или пустую строку
    monkeypatch.delenv('MENTORPIECE_API_KEY', raising=False)
    app = import_app_module()
    # приложение читает переменную при импорте; если её нет — значение может быть None
    assert getattr(app, 'MENTORPIECE_API_KEY') in (None, '')


def test_call_llm_handles_exceptions_gracefully():
    """Error Handling: когда requests.post выбрасывает исключение, функция должна вернуть строку ошибки.

    Здесь проверяем поведение при ConnectionError и Timeout.
    """
    app = import_app_module()

    with patch.object(app, 'requests') as requests_module:
        # Симулируем ConnectionError
        requests_module.post.side_effect = requests.exceptions.ConnectionError("conn failed")
        res = app.call_llm('any-model', ['hi'])
        assert isinstance(res, str)
        assert 'Ошибка соединения' in res or 'Ошибка запроса' in res

        # Симулируем Timeout
        requests_module.post.side_effect = requests.exceptions.Timeout()
        res2 = app.call_llm('any-model', ['hi'])
        assert isinstance(res2, str)
        assert 'таймаут' in res2 or 'тайм' in res2


def test_call_llm_timeout_slow_response():
    """Timeout / Slow Response Test: симулируем таймаут запроса и проверяем fallback."""
    app = import_app_module()

    with patch.object(app, 'requests') as requests_module:
        # Симулируем явный Timeout
        requests_module.post.side_effect = requests.exceptions.Timeout()
        res = app.call_llm('some-model', ['hello'])
        assert isinstance(res, str)
        assert 'таймаут' in res or 'Timeout' in res or 'timeout' in res


def test_call_llm_invalid_input():
    """Invalid Input Test: передаём некорректные типы и пустой ввод и проверяем валидацию."""
    app = import_app_module()

    # Неподдерживаемый тип
    res = app.call_llm('m', 12345)
    assert isinstance(res, str)
    assert 'некорректный тип' in res or 'Ошибка' in res

    # Пустая строка
    res2 = app.call_llm('m', '')
    assert isinstance(res2, str)
    assert 'пустой' in res2 or 'Ошибка' in res2

    # Слишком длинный текст
    long_text = 'x' * 20000
    res3 = app.call_llm('m', long_text)
    assert isinstance(res3, str)
    assert 'слишком длин' in res3 or 'Ошибка' in res3


def test_call_llm_malformed_api_response():
    """Malformed API Response Test: API возвращает структуру без поля 'response'."""
    app = import_app_module()

    def fake_post(url, json, headers=None, timeout=None):
        return MockResponse(200, {"unexpected": "value"})

    with patch.object(app, 'requests') as requests_module:
        requests_module.post.side_effect = fake_post
        res = app.call_llm('m', ['hi'])
        assert isinstance(res, str)
        assert "в ответе отсутствует поле 'response'" in res or 'response' in res
