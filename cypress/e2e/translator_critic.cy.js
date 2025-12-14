// Cypress end-to-end tests for AI Translator & Critic
//
// Эти тесты перехватывают сетевые запросы к внешнему API Mentorpiece
// с помощью `cy.intercept()` и проверяют поведение UI при успешных и
// ошибочных ответах от сервиса.

describe('AI Translator & Critic UI', () => {
  // Путь к внешнему API, который мы будем перехватывать
  const MENTORPIECE_URL = 'https://api.mentorpiece.org/v1/process-ai-request'

  it('Successful translation and evaluation (mocks for two models)', () => {
    // Перехватываем все POST-запросы к Mentorpiece и возвращаем разный
    // ответ в зависимости от поля `model_name` в теле запроса.
    cy.intercept({ method: 'POST', url: MENTORPIECE_URL }, (req) => {
      // `req.body` содержит JSON-пейлоад, который отправляет приложение.
      const model = req.body && req.body.model_name
      if (model === 'Qwen/Qwen3-VL-30B-A3B-Instruct') {
        // Пометим этот вызов alias'ом, чтобы потом ждать его явным образом
        req.alias = 'translate'
        req.reply({ statusCode: 200, body: { response: 'Mocked Translation: The sun is shining.' } })
      } else if (model === 'claude-sonnet-4-5-20250929') {
        req.alias = 'judge'
        req.reply({ statusCode: 200, body: { response: 'Mocked Grade: 9/10. Fluent and accurate.' } })
      } else {
        // На всякий случай — нормальный fallback
        req.reply({ statusCode: 200, body: { response: 'Mocked fallback' } })
      }
    })

    // Открываем приложение (предполагается, что dev сервер запущен на localhost:5000)
    cy.visit('/')

    // Вводим текст в textarea
    cy.get('textarea#text').clear().type('Солнце светит.')

    // Выбираем язык (опция имеет текст 'English' в шаблоне)
    cy.get('select#language').select('English')

    // Нажимаем кнопку "Перевести" — это отправит POST и должно вызвать наш mock для translate
    cy.contains('button', 'Перевести').click()

    // Ждём явного вызова alias'а translate и проверяем, что он был выполнен
    cy.wait('@translate')

    // В шаблоне результат перевода находится во втором .result-box (0-based index)
    cy.get('.result-box').eq(1).should('contain.text', 'Mocked Translation: The sun is shining.')

    // Теперь нажимаем кнопку оценки (хотя сервер в этом приложении обычно выполнит и перевод, и оценку
    // за один POST — мы всё равно нажмём вторую кнопку, как описано в задаче)
    cy.contains('button', 'Оценить при помощи LLM-as-a-Judge').click()

    // Ждём alias'а judge и проверяем текст в блоке оценки (третья .result-box)
    cy.wait('@judge')
    cy.get('.result-box').eq(2).should('contain.text', 'Mocked Grade: 9/10. Fluent and accurate.')
  })

  it('Handles API failure gracefully (500 responses)', () => {
    // Мокаем все запросы к API, возвращая 500 Internal Server Error
    cy.intercept({ method: 'POST', url: MENTORPIECE_URL }, (req) => {
      req.reply({ statusCode: 500, body: { error: 'Internal Server Error' } })
    }).as('apiFail')

    cy.visit('/')
    cy.get('textarea#text').clear().type('Солнце светит.')
    cy.get('select#language').select('English')
    cy.contains('button', 'Перевести').click()

    // Ждём, пока приложение выполнит сетевой запрос (alias apiFail)
    cy.wait('@apiFail')

    // Проверяем, что приложение показывает сообщение об ошибке в блоке перевода
    // (ожидаем, что в тексте будет слово 'Ошибка' или похожее сообщение)
    cy.get('.result-box').eq(1).should(($el) => {
      const txt = $el.text()
      expect(txt.length).to.be.greaterThan(0)
      expect(/ошиб/i.test(txt) || /error/i.test(txt)).to.be.true
    })
  })
})

/*
  Комментарии по работе `cy.intercept()`:
  - `cy.intercept(routeMatcher, handler)` позволяет перехватывать сетевые запросы
    и либо наблюдать их, либо отвечать локально.
  - В handler'е мы получаем объект `req` и можем вызвать `req.reply()` чтобы
    вернуть произвольный ответ. Также можно присвоить `req.alias` чтобы затем
    использовать `cy.wait('@alias')` для синхронизации теста с конкретным запросом.

  Проверка асинхронного контента:
  - После отправки формы приложение делает сетевой вызов и затем обновляет DOM.
  - `cy.wait('@translate')` гарантирует, что mock-ответ пришёл, а затем
    делаем утверждение вида `cy.get(...).should('contain.text', ...)`.
*/
