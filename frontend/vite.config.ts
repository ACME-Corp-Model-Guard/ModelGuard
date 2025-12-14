import { defineConfig } from 'vite'
import { tanstackStart } from '@tanstack/react-start/plugin/vite'
import viteReact from '@vitejs/plugin-react'
import viteTsConfigPaths from 'vite-tsconfig-paths'
import tailwindcss from '@tailwindcss/vite'

const config = defineConfig({
  plugins: [
    // this is the plugin that enables path aliases
    viteTsConfigPaths({
      projects: ['./tsconfig.json'],
    }),
    tailwindcss(),
    tanstackStart(),
    viteReact(),
  ],
  server: {
    proxy: {
      // Proxy API requests to backend
      // Update this to match your backend API URL
      '/health': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
      '/artifacts': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
      '/artifact': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
      '/lineage': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    },
  },
})

export default config
