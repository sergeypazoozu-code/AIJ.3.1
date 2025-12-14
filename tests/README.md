Тесты для проекта AI Translator & Critic

Unit tests (pytest)

1. Установите зависимости (виртуальное окружение рекомендуется):

   python -m venv .venv
   source .venv/bin/activate
   pip install -U pip
   pip install pytest

2. Запуск тестов:

   pytest -q

Тесты находятся в tests/unit/test_app.py. Все HTTP-вызовы мокируются.

UI tests (Cypress)

1. Установите Node.js и npm.
2. Инициализируйте package.json при необходимости: npm init -y
3. Установите Cypress: npm install cypress --save-dev

Запуск:

1. В одном терминале запустите dev-сервер Flask:
   python src/app.py
2. В другом терминале откройте Cypress GUI:
   npx cypress open
   или запустите headless:
   npx cypress run --spec "cypress/e2e/translator_critic.cy.js"

Примечания:
- Cypress тесты используют cy.intercept() для перехвата запросов к
  https://api.mentorpiece.org/v1/process-ai-request — реальных вызовов нет.
- Убедитесь, что приложение доступно по http://localhost:5000
