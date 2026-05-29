import type { Config } from 'tailwindcss'

/**
 * Tailwind CSS configuration.
 *
 * Scans both frontend source files and Flask templates
 * to ensure all utility classes are included in the build.
 */
export default {
  content: [
    './src/**/*.{js,ts,jsx,tsx}',
    '../src/app/templates/**/*.html',
  ],
  theme: {
    extend: {},
  },
  plugins: [],
} satisfies Config
