# Test Coverage Plan

The user requested an analysis of test coverage and a plan for adding tests to the codebase, along with adding initial tests.

## Initial Coverage Analysis
Based on a recent coverage run (`pytest --cov=rsstag tests/`), the application currently lacks tests for several significant components. Most notably, the `rsstag/web/` directory handlers and a few background workers/providers are mostly untested.

Key files needing test coverage include:
1. `rsstag/web/posts.py` (originally ~8% coverage)
2. `rsstag/web/tags.py` (originally ~5% coverage)
3. `rsstag/web/app.py` (originally ~18% coverage)
4. `rsstag/web/users.py` (originally ~10% coverage)
5. `rsstag/web/context_filter_handlers.py` (originally ~8% coverage)

## Initial Tests Added
To begin addressing this tech debt, two initial test files have been created, adding tests for two of the most critical routing and handler modules:

1. `tests/test_web_posts_2.py`: This file adds basic integration tests via the `MongoWebTestCase` utility for web posts-related endpoints. Coverage of `rsstag/web/posts.py` increased from 8% to 11%.
2. `tests/test_web_tags.py`: This file covers major tag-related endpoints. Coverage of `rsstag/web/tags.py` increased from 5% to 19%.

## Proposed Next Steps for Coverage

1. **Continue Expanding `tests/test_web_posts_2.py` and `tests/test_web_tags.py`**
   - Provide more mocked payload to hit branching paths.
   - Example: test post saving, grouping, reading combinations.

2. **Add `tests/test_web_app.py`**
   - The main `app.py` has low coverage since many error branches and edge routes (like system logs or processing resets) are not covered.
   - We need integration tests for endpoints like `/processing/reset`, `/workers/spawn`, etc.

3. **Add `tests/test_web_users.py`**
   - There are many unverified paths involving user sessions, metadata, and token creation.

4. **Address Providers & LLM integrations**
   - `rsstag/providers/telegram.py` (17%) and `rsstag/providers/gmail.py` (10%) need significant testing.
   - We need mocked API clients for these files.

By methodically implementing these files, the overall project coverage can smoothly approach an acceptable metric.