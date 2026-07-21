import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

/**
 * Vite configuration for React Islands architecture.
 *
 * Key design decisions:
 * - Output to Flask's static directory for production builds
 * - Generate manifest.json so Flask can resolve hashed asset paths
 * - Dev server on port 5174 provides HMR for development
 * - Path alias @/* maps to src/* for clean imports
 */
export default defineConfig({
  plugins: [react()],

  // Path aliases for cleaner imports
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },

  // Development server configuration
  server: {
    port: 5174,
    strictPort: true,
    // Allow Flask (port 5000) to load assets
    cors: true,
    // Origin header for HMR WebSocket connection
    origin: 'http://localhost:5174',
  },

  // Build configuration
  build: {
    // Output to Flask's static directory
    outDir: '../src/app/static',
    emptyOutDir: true,

    // Generate manifest for Flask to resolve hashed filenames
    manifest: true,

    // Entry point
    rollupOptions: {
      input: {
        main: path.resolve(__dirname, 'src/main.ts'),
      },
      output: {
        // Asset naming with hash for cache busting
        entryFileNames: 'assets/[name]-[hash].js',
        chunkFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash].[ext]',
      },
    },
  },
})
