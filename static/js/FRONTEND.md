# Frontend Build System Documentation

## Overview

The rsstag frontend is built using:
- **React 18** - UI component library
- **Vite 8** - Bundler (library-mode IIFE build, output `bundle.js`)
- **Native CSS** - plain modern CSS (nesting, custom properties), served as-is with no build step. See [Stylesheets](#stylesheets).
- **D3.js** - Data visualization

## Project Structure

```
static/js/
├── apps/           # Main application entry points
├── components/     # React components
├── storages/       # Data management modules
├── libs/           # Utility libraries
├── test/           # Unit and integration tests
├── vite.config.mjs         # Vite build configuration
├── eslint.config.cjs       # ESLint configuration
├── vitest.config.cjs       # Vitest configuration (optional)
├── package.json            # Dependencies and scripts
├── build.sh               # Docker build script
└── .nvmrc                 # Node.js version specification
```

## Stylesheets

CSS is not part of the Vite build. Templates load one file, `/static/css/style.css`, and that file is only an `@import` manifest. The rules live in the partials it lists, in that order:

- `tokens.css` — palette, type, spacing
- `legacy.css` and `pages/legacy-pages.css` — unscoped names that have no page owner yet
- `pages/*.css` — one file per page or feature banner
- `utilities.css` — the local utility layer, including the sharp-corner overrides
- `chrome.css` — site header, page meta, footer
- the canvas and tag-explorer partials, which come last so they can override the utilities

Do not add rules to `style.css` and do not reorder the imports. Later files win by source order, the same way they did when this was one file. A new token goes in `tokens.css`; a scoped page rule goes in that page's partial; an unscoped class with no owner yet goes in `legacy.css`.

## Build System Features

### Modern Configuration
- ✅ Vite with proper mode configuration (dev/production)
- ✅ React 18 with latest optimizations
- ✅ Modern browser targeting (Vite default `baseline-widely-available`)
- ✅ Source maps for both development and production
- ✅ Zero security vulnerabilities in dependencies
- ✅ ES Module support with Node.js 22

### Development Workflow
- Watch mode for continuous rebuilding (`npm run watch`)
- Fast development builds with full source maps

### Production Optimizations
- Automatic code minification and tree-shaking
- Proper source maps for debugging
- Bundle size warnings

## NPM Scripts

| Script | Description |
|--------|-------------|
| `npm run build` | Production build with minification and source maps |
| `npm run build:dev` | Development build with full source maps |
| `npm run watch` | Development build with auto-rebuild on file changes |
| `npm run clean` | Remove generated bundle files |
| `npm run lint` | Run ESLint on JS/JSX sources |
| `npm run lint:fix` | Run ESLint with auto-fixes |
| `npm run format` | Format files with Prettier |
| `npm run format:check` | Check formatting without writing changes |
| `npm run test` | Run frontend tests using Node.js test runner |
| `npm run test:watch` | Run frontend tests in watch mode |

## Building

### Quick Start

```bash
cd static/js
npm install
npm run build
```

### Development Build

For faster builds during development:

```bash
npm run build:dev
```

### Watch Mode

Automatically rebuild when source files change:

```bash
npm run watch
```

### Docker Build

For consistent builds across environments:

```bash
docker run -it --rm \
  -v `pwd`/../css:/css \
  -v `pwd`:/app \
  -w /app \
  node:22 ./build.sh
```

## Testing

The project uses the built-in Node.js test runner for fast, dependency-free testing.

Run tests once:
```bash
npm run test
```

Run tests in watch mode:
```bash
npm run test:watch
```

Tests are located in the `test/` directory and follow the `*.test.js` naming convention.

## Linting and Formatting

Run linting and formatting locally:

```bash
npm run lint
npm run format:check
```

Apply fixes:

```bash
npm run lint:fix
npm run format
```

### Docker Lint/Format/Test

Build the lint container from `static/js`:

```bash
docker build -t rsstag-js-lint -f Dockerfile.lint .
```

Run linting:

```bash
docker run --rm -v "$PWD":/workspace rsstag-js-lint npm run lint
```

Run tests:

```bash
docker run --rm -v "$PWD":/workspace rsstag-js-lint npm run test
```

Apply lint fixes (optional):

```bash
docker run --rm -v "$PWD":/workspace rsstag-js-lint npm run lint:fix
```

Check formatting:

```bash
docker run --rm -v "$PWD":/workspace rsstag-js-lint npm run format:check
```

If you want the container to use host networking, these commands are equivalent:

```bash
docker run --rm --network=host -v "$PWD":/workspace rsstag-js-lint npm run lint
docker run --rm --network=host -v "$PWD":/workspace rsstag-js-lint npm run test
docker run --rm --network=host -v "$PWD":/workspace rsstag-js-lint npm run format:check
```

Apply formatting (optional):

```bash
docker run --rm -v "$PWD":/workspace rsstag-js-lint npm run format
```

## Output

The build process generates:
- `bundle.js` - Main application bundle
- `bundle.js.map` - Source map for debugging

## Dependencies

### Production Dependencies
- **d3** - Data visualization library
- **sunburst-chart** - Hierarchical data visualization

### Development Dependencies
- **vite** - Bundler and build tool
- **react** & **react-dom** - UI library

## Upgrading Dependencies

To update all dependencies to their latest versions:

```bash
npm update
```

To check for outdated packages:

```bash
npm outdated
```

To audit for security vulnerabilities:

```bash
npm audit
```

## Troubleshooting

### Module Not Found Errors

If you get module resolution errors:
1. Delete `node_modules` and `package-lock.json`
2. Run `npm install` again

### Build Performance

For faster builds:
- Use `npm run build:dev` instead of `npm run build` during development
- Use `npm run watch` to avoid repeated build startups

### Docker Build Issues

If the Docker build fails:
- Ensure the CSS directory is properly mounted: `-v $(pwd)/../css:/css`
- Check that the node:22 image is available: `docker pull node:22`

## Node.js Version

This project requires Node.js 20.19 or higher (Node.js 22 recommended), as required by Vite 8.

Use `.nvmrc` to automatically switch to the correct version:

```bash
nvm use
```

## Recent Improvements (2026)

- ⬆️ Upgraded React from 17 to 18
- 🔁 Migrated bundling from Webpack + Babel to Vite
- ➕ Added Node.js built-in test runner for frontend
- ➕ Added ES Module support via `"type": "module"`
- 🔒 Fixed all npm security vulnerabilities (4 → 0)
- 📝 Added proper npm scripts for common tasks
- 📝 Added comprehensive documentation
- 🎯 Improved source map configuration for better debugging
