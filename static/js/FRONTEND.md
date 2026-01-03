# Frontend Build System Documentation

## Overview

The rsstag frontend is built using:
- **React 18** - UI component library
- **Webpack 5** - Module bundler
- **Babel** - JavaScript transpiler
- **SASS** - CSS preprocessor
- **D3.js** - Data visualization

## Project Structure

```
static/js/
├── apps/           # Main application entry points
├── components/     # React components
├── storages/       # Data management modules
├── libs/           # Utility libraries
├── webpack.config.js       # Production webpack configuration
├── webpack.dev.config.js   # Development server configuration
├── package.json            # Dependencies and scripts
├── build.sh               # Docker build script
└── .nvmrc                 # Node.js version specification
```

## Build System Features

### Modern Configuration
- ✅ Webpack 5 with proper mode configuration (dev/production)
- ✅ React 18 with latest optimizations
- ✅ Babel with modern preset-env targeting
- ✅ Automatic SASS compilation with error handling
- ✅ Source maps for both development and production
- ✅ Build performance optimizations (caching, code splitting ready)
- ✅ Zero security vulnerabilities in dependencies

### Development Workflow
- Hot Module Replacement (HMR) support via webpack-dev-server
- Watch mode for continuous rebuilding
- Fast development builds with eval-source-map
- Proxy support for backend API during development

### Production Optimizations
- Automatic code minification and tree-shaking
- Proper source maps for debugging
- Bundle size warnings and optimization hints
- Modern browser targeting with polyfills only where needed

## NPM Scripts

| Script | Description |
|--------|-------------|
| `npm run build` | Production build with minification and source maps |
| `npm run build:dev` | Development build with full source maps |
| `npm run watch` | Development build with auto-rebuild on file changes |
| `npm run dev` | Start webpack-dev-server with hot reload (port 8886) |
| `npm run clean` | Remove generated bundle files |

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

### Development Server

Run a development server with hot module replacement:

```bash
npm run dev
```

Then open `http://localhost:8886` in your browser. The dev server proxies API requests to the main backend on port 8885.

### Docker Build

For consistent builds across environments:

```bash
docker run -it --rm \
  -v `pwd`/../css:/css \
  -v `pwd`:/app \
  -w /app \
  node:22 ./build.sh
```

## Output

The build process generates:
- `bundle.js` - Main application bundle
- `bundle.js.map` - Source map for debugging
- `bundle.js.LICENSE.txt` - Third-party license information
- `../css/style.css` - Compiled CSS from SASS

## Dependencies

### Production Dependencies
- **d3** - Data visualization library
- **sunburst-chart** - Hierarchical data visualization

### Development Dependencies
- **@babel/core** - JavaScript transpiler core
- **@babel/preset-env** - Smart preset for modern JavaScript
- **@babel/preset-react** - JSX and React transformation
- **babel-loader** - Webpack loader for Babel
- **core-js** - Polyfills for modern JavaScript features
- **react** & **react-dom** - UI library
- **sass** - CSS preprocessor
- **webpack** - Module bundler
- **webpack-cli** - Command line interface for webpack
- **webpack-dev-server** - Development server with live reload

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

### SASS Compilation Errors

If SASS compilation fails, the build will continue but warn you. Check that:
- `../css/style.scss` exists
- The SCSS syntax is valid

### Module Not Found Errors

If you get module resolution errors:
1. Delete `node_modules` and `package-lock.json`
2. Run `npm install` again

### Build Performance

For faster builds:
- Use `npm run build:dev` instead of `npm run build` during development
- Use `npm run watch` to avoid repeated build startups
- Ensure you have enough RAM (webpack can be memory-intensive)

### Docker Build Issues

If the Docker build fails:
- Ensure the CSS directory is properly mounted: `-v $(pwd)/../css:/css`
- Check that the node:22 image is available: `docker pull node:22`

## Node.js Version

This project requires Node.js 18 or higher (Node.js 22 recommended).

Use `.nvmrc` to automatically switch to the correct version:

```bash
nvm use
```

## Recent Improvements (2026)

- ⬆️ Upgraded React from 17 to 18
- ⬆️ Upgraded Babel dependencies to latest versions
- ⬆️ Upgraded webpack-cli from 4 to 5
- ➕ Added webpack-dev-server for better DX
- ➕ Added core-js for optimized polyfills
- 🐛 Fixed SASS compilation path (was using absolute `/css/` path)
- 🐛 Fixed webpack mode configuration
- 🔒 Fixed all npm security vulnerabilities (4 → 0)
- ⚡ Improved build performance with caching
- 📝 Added proper npm scripts for common tasks
- 📝 Added comprehensive documentation
- 🎯 Improved source map configuration for better debugging
