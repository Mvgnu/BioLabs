import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    include: ['app/**/__tests__/**/*.test.ts'],
    exclude: ['e2e/**'],
    environment: 'node',
  },
})
