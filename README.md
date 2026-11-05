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
```

**Note:** This project uses Node.js 22. Use `nvm use` to switch to the correct version if you have nvm installed.

### 1a. Lint/format frontend JS with Docker

From `static/js`:

```bash
docker build -t rsstag-js-lint -f Dockerfile.lint .
```

Run linting and tests:

```bash
docker run --rm -v "$PWD":/workspace rsstag-js-lint npm run lint
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

If you prefer to use host networking for Docker-based checks, the commands also work with `--network=host`:

```bash
docker run --rm --network=host -v "$PWD":/workspace rsstag-js-lint npm run lint
docker run --rm --network=host -v "$PWD":/workspace rsstag-js-lint npm run test
docker run --rm --network=host -v "$PWD":/workspace rsstag-js-lint npm run format:check
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

### 6. Run DB-backed tests

The integration-style test suites expect MongoDB on `127.0.0.1:8765`.

Start the test database:

```bash
docker compose -f docker-compose.test.yml up -d
```

Run the worker-focused tests:

```bash
python3 -m unittest tests.test_worker_bootstrap tests.test_worker_external_loop tests.test_worker_registry_completeness tests.test_worker_dispatcher_init tests.test_worker_task_dispatch tests.test_worker_process_lifecycle tests.test_worker_classes_init
```

If MongoDB is already running on the host on `127.0.0.1:8765`, you can run the tests in Docker with host networking instead of starting `docker-compose.test.yml`:

```bash
docker build -t rsstag-test -f Dockerfile.test .
docker run --rm --network=host -v "$PWD":/work -w /work rsstag-test \
  python3 -m unittest tests.test_worker_bootstrap tests.test_worker_external_loop tests.test_worker_registry_completeness tests.test_worker_dispatcher_init tests.test_worker_task_dispatch tests.test_worker_process_lifecycle tests.test_worker_classes_init
```

To run the whole test suite in the same container:

```bash
docker run --rm --network=host -v "$PWD":/work -w /work rsstag-test
```

Stop the test database when finished:

```bash
docker compose -f docker-compose.test.yml down
```

### Decisions API clients

`rsstag.decisions` supports hosted TypeSafe/Jev and a local Jev-compatible
llama.cpp server. Both send native typed questions to `/v1/systemone` and return
validated answers with probabilities, model metadata, and token usage.
The local server must expose that endpoint.

Configure `[decisions]` in `default.conf` with `provider=jev` or
`provider=llamacpp` and a request `timeout` in seconds. Hosted credentials and
model settings belong in `[jev]`; local settings belong in
`[llamacpp_decisions]`. Hosts may include a proxy prefix or end in `/v1`.
Local authentication is optional. Keep API tokens in server configuration.
Users can select Worker and Realtime decisions providers independently in
Settings, just as they can for LLMs. Web/API handlers use
`create_decisions_client(config, user_settings=user["settings"])`, which reads
`realtime_decisions`. Workers pass `provider_key="worker_decisions"` with the
same saved preferences. Each unset preference uses the server default, and an
explicit `provider` takes precedence.

```python
from rsstag.decisions import NoulQuestion, create_decisions_client

client = create_decisions_client(config)
response = client.call(
    state={"message": "I was charged twice this month."},
    questions={
        "duplicate_charge": NoulQuestion(
            instructions="Does the message report a duplicate charge?"
        ),
    },
)
probability = response.answers["duplicate_charge"].noul
```

`ChoiceQuestion`, `ScoreQuestion`, and `BoxQuestion` are also available, and
questions can be bundled in one call. Raw question dictionaries are accepted.
Calls with image `assets` or box questions set the image opt-in header;
`long_context=True` sets the long-context opt-in header. Image assets use the
JSON/base64 format in the
[TypeSafe API schema](https://api.typesafe.ai/openapi.json).
HTTP, transport, and invalid response failures raise `DecisionsError`; invalid
request data raises `ValueError`. Application code owns thresholds and actions.
