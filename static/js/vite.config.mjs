import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';

const rootDir = path.dirname(fileURLToPath(import.meta.url));

/**
 * Single IIFE bundle consumed by the server-rendered templates via
 * `<script src="/static/js/bundle.js">`. Output lands next to the sources so
 * template paths and the Dockerfile stay unchanged.
 */
export default defineConfig(({ mode }) => {
  const isProduction = mode === 'production';
  return {
    // Not rootDir: Vite refuses (warns about) an outDir equal to root.
    root: path.join(rootDir, '..'),
    publicDir: false,
    // Components are JSX in plain .js files.
    oxc: {
      include: /\.[jt]sx?$/,
      jsx: { runtime: 'automatic' },
    },
    // Library mode does not inline NODE_ENV, and React branches on it.
    define: {
      'process.env.NODE_ENV': JSON.stringify(isProduction ? 'production' : 'development'),
    },
    build: {
      outDir: rootDir,
      emptyOutDir: false,
      sourcemap: true,
      minify: isProduction,
      chunkSizeWarningLimit: 1024,
      rolldownOptions: {
        moduleTypes: { '.js': 'jsx' },
      },
      lib: {
        entry: path.join(rootDir, 'apps', 'app.js'),
        formats: ['iife'],
        name: 'RsstagApp',
        fileName: () => 'bundle.js',
      },
    },
  };
});
