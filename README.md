## Steps to run:
### 1. Build js bundle

#### Option A: Using Docker (recommended for consistency)
`cd static/js`

```bash
docker run -it --rm -v `pwd`/../css:/css -v `pwd`:/app -w /app node:22 ./build.sh
```

#### Option B: Using local Node.js (faster for development)
`cd static/js`

```bash
# Install dependencies (first time only)
npm install

# Production build
npm run build

# Development build with source maps
npm run build:dev

# Development with auto-rebuild on file changes
npm run watch

# Development with live reload server (port 8886)
npm run dev
```

**Note:** This project uses Node.js 22. Use `nvm use` to switch to the correct version if you have nvm installed.

### 1a. Lint/format frontend JS with Docker

From `static/js`:

```bash
docker build -t rsstag-js-lint -f Dockerfile.lint .
```

Run linting:

```bash
docker run --rm -v "$PWD":/workspace rsstag-js-lint npm run lint
```

Apply lint fixes (optional):

```bash
docker run --rm -v "$PWD":/workspace rsstag-js-lint npm run lint:fix
```

Check formatting:

```bash
docker run --rm -v "$PWD":/workspace rsstag-js-lint npm run format:check
```

Apply formatting (optional):

```bash
docker run --rm -v "$PWD":/workspace rsstag-js-lint npm run format
```

### 2. Prepare config files

Copy default.conf to rsscloud.conf.

Set fields:

`db_host = mongodb`

`db_port = 27017`.

### 3. Build the rsstag image

At the root of the project run:

```docker build -t rsstag```

### 3a. Lint/format with Docker

Build the lint container:

```docker build -t rsstag-lint -f Dockerfile.lint .```

Run lint + format checks:

```docker run --rm -v "$PWD":/work -w /work rsstag-lint```

Apply formatting (optional):

```docker run --rm -v "$PWD":/work -w /work --entrypoint ruff rsstag-lint format .```

Apply lint fixes (optional):

```docker run --rm -v "$PWD":/work -w /work --entrypoint ruff rsstag-lint check --fix .```

### 4. Run
At the root of the project run:

```docker compose up```

### 5. Open

Use browser to open `http://127.0.0.1:8885`
