import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

const debugTransformPlugin = () => ({
  name: 'debug-transform-plugin',
  enforce: 'pre',
  transform(code, id) {
    // Only log during test runs to avoid noisy output in dev
    if (process.env.VITEST) {
      // Print to stderr so vitest still formats output
      // eslint-disable-next-line no-console
      console.error('[vite-transform] ', id);
      try {
        const sample = code.slice(0, 200).replace(/\n/g, '\\n');
        console.error('[vite-transform-sample] len=', code.length, sample);
      } catch (e) {
        console.error('[vite-transform-sample] cannot read code');
      }
      // Try to parse quickly with acorn to surface parse errors with file id
      try {
        // require acorn which is a dependency of rollup/vite
        // eslint-disable-next-line global-require
        const acorn = require('acorn');
        try {
          acorn.parse(code, { ecmaVersion: 2024, sourceType: 'module' });
        } catch (parseErr) {
          console.error('[vite-transform-parse-error] id=', id);
          console.error('[vite-transform-parse-error] message=', parseErr && parseErr.message);
          // print a bit more of the source around the error if location available
          if (parseErr && parseErr.loc) {
            const lines = code.split(/\r?\n/);
            const ln = Math.max(0, parseErr.loc.line - 3);
            const snippet = lines.slice(ln, ln + 6).join('\n');
            console.error('[vite-transform-parse-error] snippet:\n', snippet);
          }
        }
      } catch (e) {
        // ignore if acorn not available
      }
    }
    return null;
  }
});

export default defineConfig({
  plugins: [debugTransformPlugin(), react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.js'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: [
        'node_modules/',
        'src/test-setup.js',
        'src/index.js',
        'public/',
        'build/',
        '**/*.config.js',
        'coverage/'
      ]
    }
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
  ,
  'lucide-react': path.resolve(__dirname, './src/test-stubs/lucide-react.js'),
  '../Selectors': path.resolve(__dirname, './src/test-stubs/Selectors.js'),
  './Selectors': path.resolve(__dirname, './src/test-stubs/Selectors.js'),
  '../ChatInterface': path.resolve(__dirname, './src/test-stubs/ChatInterface.js'),
  './ChatInterface': path.resolve(__dirname, './src/test-stubs/ChatInterface.js'),
  '../MobileLayout': path.resolve(__dirname, './src/test-stubs/MobileLayout.js'),
  './MobileLayout': path.resolve(__dirname, './src/test-stubs/MobileLayout.js'),
  // Absolute-path aliases to catch direct resolved ids
  [path.resolve(__dirname, './src/components/Selectors.js')]: path.resolve(__dirname, './src/test-stubs/Selectors.js'),
  [path.resolve(__dirname, './src/components/ChatInterface.js')]: path.resolve(__dirname, './src/test-stubs/ChatInterface.js'),
  [path.resolve(__dirname, './src/components/MobileLayout.js')]: path.resolve(__dirname, './src/test-stubs/MobileLayout.js')
    }
  }
});
