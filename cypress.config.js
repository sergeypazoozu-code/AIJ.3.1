const { defineConfig } = require('cypress')

module.exports = defineConfig({
  e2e: {
    baseUrl: 'http://localhost:5000', // измените на ваш URL
    setupNodeEvents(on, config) {
      // implement node event listeners here
    },
  },
})