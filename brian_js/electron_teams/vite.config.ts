import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import Pages from 'vite-plugin-pages'
import { resolve } from 'path'

export default defineConfig({
  plugins: [
    react(),
    Pages({
      dirs: 'src/pages',
      extensions: ['tsx', 'ts'],
      exclude: ['**/components/**', '**/hooks/**', '**/lib/**']
    })
  ],
  resolve: {
    alias: {
      '@': resolve('src')
    }
  },
  root: '.',
  publicDir: 'public',
  build: {
    rollupOptions: {
      input: {
        index: resolve(__dirname, 'index.html')
      }
    }
  }
})