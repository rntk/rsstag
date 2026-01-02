## Steps to run:
### 1. Build js bundle
`cd static/js`

```docker run -it --rm -v `pwd`/../css:/css -v `pwd`:/app -w /app node:22 ./build.sh```

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
