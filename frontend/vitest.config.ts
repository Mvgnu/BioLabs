import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    include: ['app/**/__tests__/**/*.test.ts?(x)'],
    exclude: ['e2e/**'],
    environment: 'jsdom',
  },
})
