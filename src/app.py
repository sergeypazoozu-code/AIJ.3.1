import requests
from flask import Flask, render_template, request
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из файла .env (если он есть).
load_dotenv()

app = Flask(__name__)

# По умолчанию используем заданный в ТЗ endpoint Mentorpiece
MENTORPIECE_API_ENDPOINT = os.getenv(
    "MENTORPIECE_API_ENDPOINT",
    "https://api.mentorpiece.org/v1/process-ai-request",
)

# API-key для Mentorpiece берём из переменных окружения.
# QA: при интеграционном тестировании убедитесь, что переменная
# `MENTORPIECE_API_KEY` задана в окружении или в файле .env.
MENTORPIECE_API_KEY = os.getenv("MENTORPIECE_API_KEY")


def call_llm(model_name, messages):
    """
    Универсальная обёртка для отправки запросов к LLM через HTTP.

    Параметры:
    - model_name (str): имя модели, например "Qwen/Qwen3-VL-30B-A3B-Instruct"
    - messages (list[str] | str): список сообщений/строк или одна строка.

    Возвращает:
    - str: текст ответа от LLM (поле "response" в JSON), либо читаемое сообщение об ошибке.

    Поведение и обработка ошибок подробно прокомментированы для QA:
    - Собираем `prompt` из списка сообщений (разделитель — перенос строки).
    - Делаем `requests.post` с JSON-форматом согласно контракту: {"model_name":..., "prompt":...}
    - Таймаут установлен на 15 сек — чтобы тестировщик видел поведение при таймаутах.
    - При HTTP-ошибке (4xx/5xx) возвращаем текст с кодом ошибки и телом ответа (если есть).
    - При сетевой ошибке возвращаем краткую диагностическую строку с исключением.
    - При некорректном JSON возвращаем понятную ошибку для QA (полезно при интеграционных тестах).
    """

    # Валидация входных данных: ожидаем строку или список/кортеж строк
    if not isinstance(messages, (str, list, tuple)):
        return "Ошибка: некорректный тип параметра messages"

    # Нормализуем вход: если передали строку, преобразуем в список с одним элементом
    if isinstance(messages, str):
        messages = [messages]

    # Собираем текстовый prompt
    prompt = "\n".join(m.strip() for m in messages if m is not None)

    # Проверка на пустой prompt
    if not prompt or not prompt.strip():
        return "Ошибка: пустой prompt"

    # Ограничение размера prompt (предотвращает отправку сверхдлинных запросов)
    if len(prompt) > 10000:
        return "Ошибка: слишком длинный текст"

    payload = {"model_name": model_name, "prompt": prompt}

    # Подготовка заголовков: только `Content-Type` — авторизация по ключу не нужна.
    headers = {"Content-Type": "application/json"}

    try:
        # Выполняем POST-запрос к Mentorpiece
        resp = requests.post(MENTORPIECE_API_ENDPOINT, json=payload, headers=headers, timeout=15)

        # Если сервер вернул код, отличный от 2xx, собираем диагностическое сообщение.
        if resp.status_code >= 400:
            # Обработка 401 — подсказка про ошибку с ключом
            if resp.status_code == 401:
                return "Ошибка: Unauthorized (401) от Mentorpiece. Проверьте значение MENTORPIECE_API_KEY."
            # Пытаемся получить текст ответа (если сервер вернул JSON или текст)
            try:
                body = resp.text
            except Exception:
                body = "<не удалось прочитать тело ответа>"
            return f"Ошибка HTTP {resp.status_code} от LLM: {body}"

        # Попробуем распарсить JSON и извлечь поле `response`.
        try:
            data = resp.json()
        except ValueError:
            return "Ошибка: получен некорректный JSON от LLM"

        # Ожидаемый формат: {"response": "..."}
        if isinstance(data, dict) and "response" in data:
            # Гарантируем, что возвращаем строку
            val = data.get("response")
            return val if isinstance(val, str) else str(val)

        # Если ключа нет — вернём диагностическое сообщение с сырьём ответа
        return f"Ошибка: в ответе отсутствует поле 'response' — получено: {data}"

    except requests.exceptions.Timeout:
        return "Ошибка: таймаут при обращении к LLM (timeout=15s)"
    except requests.exceptions.ConnectionError as e:
        return f"Ошибка соединения с LLM: {e}"
    except requests.exceptions.RequestException as e:
        # Ловим любые другие исключения requests
        return f"Ошибка запроса к LLM: {e}"


@app.route('/', methods=['GET'])
def index_get():
    """
    Рендерит форму для ввода текста и выбора языка.

    QA-инструкция:
    - Открыть страницу и проверить, что поля пустые по-умолчанию.
    - Убедиться, что селектор языка содержит: English, French, German.
    """
    return render_template('index.html', original="", translation="", evaluation="", language="English")


@app.route('/', methods=['POST'])
def index_post():
    """
    Обрабатывает форму:
    1) Получает исходный текст и выбранный язык
    2) Вызывает LLM для перевода (модель Qwen...)
    3) Вызывает LLM для оценки перевода (модель Claude...)
    4) Рендерит шаблон с оригиналом, переводом и оценкой

    Комментарии для QA:
    - При пустом тексте возвращаем понятное сообщение об ошибке.
    - При ошибке от LLM (таймаут/HTTP-ошибка/некорректный JSON) сообщение об ошибке отображается в поле перевода или оценки.
    - Можно эмулировать ошибки, запуская прокси, который возвращает 500, или отдавая не-JSON.
    """

    original_text = request.form.get('text', '').strip()
    language = request.form.get('language', 'English')

    if not original_text:
        # В интерфейсе отобразим подсказку в поле `evaluation`
        evaluation = 'Пожалуйста, введите текст для перевода.'
        return render_template('index.html', original=original_text, translation='', evaluation=evaluation, language=language)

    # --- Шаг 1: перевод ---
    translate_model = "Qwen/Qwen3-VL-30B-A3B-Instruct"
    translate_prompt = [f"Переведи следующий текст на {language}:", original_text]
    translation = call_llm(translate_model, translate_prompt)

    # --- Шаг 2: оценка качества перевода ---
    judge_model = "claude-sonnet-4-5-20250929"
    judge_prompt = ["Оцени качество перевода от 1 до 10 и аргументируй.", "Оригинал:", original_text, "Перевод:", translation]
    evaluation = call_llm(judge_model, judge_prompt)

    # Рендерим шаблон, показываем оригинал, перевод и оценку
    return render_template('index.html', original=original_text, translation=translation, evaluation=evaluation, language=language)


if __name__ == '__main__':
    # Запуск dev-сервера. Для продакшна используйте gunicorn/uwsgi.
    port = int(os.getenv('PORT', '5000'))
    app.run(host='0.0.0.0', port=port, debug=True)
# Файл был очищён — удалён по просьбе пользо



def call_openai(model_name, messages):
    """
    Простая интеграция с OpenAI Chat Completions API через HTTP.

    - `model_name` передаётся как поле `model`.
    - `messages` объединяются в единый текст и передаются как одно сообщение от пользователя.

    Возвращает текстовый ответ или сообщение об ошибке.
    """
    url = "https://api.openai.com/v1/chat/completions"
    prompt = "\n".join(messages)
    payload = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 1024,
    }
    # Защищённо подготовим ключ: убираем случайный префикс "Bearer " если он есть.
    api_key = (OPENAI_API_KEY or "").strip()
    if api_key.lower().startswith("bearer "):
        api_key = api_key.split(" ", 1)[1]

    if not api_key:
        return "Ошибка: OPENAI_API_KEY не задан. Установите переменную окружения OPENAI_API_KEY."

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=20)

        # Обрабатываем явный 401 — даём понятную подсказку для QA/developer
        if resp.status_code == 401:
            return ("Ошибка: Unauthorized (401) от OpenAI. Проверьте значение OPENAI_API_KEY; "
                    "ключ отсутствует или недействителен.")

        resp.raise_for_status()

        data = resp.json()
        # Структура ответа: choices[0].message.content
        choices = data.get("choices") or []
        if choices and isinstance(choices, list):
            msg = choices[0].get("message", {})
            return msg.get("content", "")
        # fallback: try top-level text
        return data.get("text", "")
    except requests.exceptions.RequestException as e:
        return f"Ошибка запроса к OpenAI: {e}"
    except ValueError:
        return "Ошибка: получен неверный формат ответа от OpenAI (не JSON)"


@app.route('/', methods=['GET'])
def index_get():
    """
    Рендерит HTML-форму для ввода текста и выбора языка.
    При первом заходе все поля пустые.
    """
    # По умолчанию: приложение автоматически использует OpenAI, если задан OPENAI_API_KEY,
    # иначе используется встроенный mock-режим.
    return render_template('index.html', original="", translation="", evaluation="", language="English")


@app.route('/', methods=['POST'])
def index_post():
    """
    Обрабатывает отправку формы:
    1) Получаем исходный текст и целевой язык.
    2) Вызываем LLM для перевода (модель Qwen...).
    3) Вызываем LLM для оценки качества перевода (модель Claude Sonnet).
    4) Рендерим результаты в шаблоне.

    Комментарий для QA: при тестировании проверяйте поведение при пустом тексте,
    при недоступном API и при ошибочном / медленном ответе внешнего сервиса.
    """

    # Получаем данные из формы
    original_text = request.form.get('text', '').strip()
    language = request.form.get('language', 'English')
    # Без текста нет смысла вызывать LLM — вернем понятную ошибку в интерфейс
    if not original_text:
        translation = ""
        evaluation = "Пожалуйста, введите текст для перевода."
        return render_template('index.html', original=original_text, translation=translation, evaluation=evaluation, language=language)

    # --- Шаг 1: перевод ---
    translate_model = "Qwen/Qwen3-VL-30B-A3B-Instruct"

    # Формируем промпт: просим модель перевести на выбранный язык.
    translate_messages = [
        f"Переведи следующий текст на {language}:",
        original_text
    ]

    # Единый поведенческий путь: используем OpenAI если есть ключ, иначе mock
    translation = call_llm(translate_model, translate_messages)

    # --- Шаг 2: оценка качества перевода ---
    judge_model = "claude-sonnet-4-5-20250929"

    # Промпт для судьи: просим оценить по шкале 1-10 и аргументировать.
    judge_messages = [
        "Оцени качество перевода от 1 до 10 и аргументируй.",
        "Оригинал:",
        original_text,
        "Перевод:",
        translation
    ]

    evaluation = call_llm(judge_model, judge_messages)

    # Рендерим шаблон с результатами — шаблон покажет оригинал, перевод и оценку
    return render_template('index.html', original=original_text, translation=translation, evaluation=evaluation, language=language)


if __name__ == '__main__':
    # Запуск dev-сервера Flask. Порт можно переопределить через переменную окружения PORT.
    # В проде используйте WSGI-сервер (gunicorn/uvicorn).
    port = int(os.getenv('PORT', '5000'))
    app.run(host='0.0.0.0', port=port, debug=True)
