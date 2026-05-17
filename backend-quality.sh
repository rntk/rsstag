#!/usr/bin/env bash
# backend-quality.sh — Python code quality metrics for the rsstag codebase
#
# Metrics produced:
#   1. Test coverage (line + branch) via coverage.py
#   2. Mutation testing score via mutmut
#
# Usage:
#   ./backend-quality.sh              # run both coverage and mutation tests
#   ./backend-quality.sh --coverage   # run coverage only
#   ./backend-quality.sh --mutation   # run mutation only (requires coverage data)
#
# Exit codes:
#   0 — all checks passed
#   1 — coverage below threshold or mutation failures detected

set -euo pipefail

# ── Configuration ──────────────────────────────────────────────────────────────

COVERAGE_THRESHOLD=80          # minimum line coverage % to pass
BRANCH_COVERAGE_THRESHOLD=60   # minimum branch coverage % to pass
MUTATION_TIMEOUT=300           # seconds per mutant (5 min)
MUTATION_BASE_DIR="rsstag"     # source directory to mutate
TEST_DIR="tests"               # test directory

# Optional quality gates (set --all to enable)
LINT_CHECK=false               # run ruff linting
TYPECHECK=false                # run mypy type checking

# Packages that must be installed (added at runtime if missing)
COVERAGE_PKG="coverage"
MUTMUT_PKG="mutmut"
LINT_PKG="ruff"
TYPECHECK_PKG="mypy"

# ── Helpers ────────────────────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}▶ $*${NC}"; }
ok()    { echo -e "${GREEN}✔ $*${NC}"; }
warn()  { echo -e "${YELLOW}⚠ $*${NC}"; }
fail()  { echo -e "${RED}✘ $*${NC}"; }

check_dep() {
    if ! python3 -c "import $1" 2>/dev/null; then
        warn "$1 not installed — installing $1…"
        pip install --quiet "$1"
    fi
}

# ── Parse arguments ────────────────────────────────────────────────────────────

RUN_COVERAGE=true
RUN_MUTATION=true

while [[ $# -gt 0 ]]; do
    case "$1" in
        --coverage)  RUN_COVERAGE=true;  RUN_MUTATION=false; shift ;;
        --mutation)  RUN_COVERAGE=false; RUN_MUTATION=true;  shift ;;
        --all)       LINT_CHECK=true; TYPECHECK=true; shift ;;
        --help|-h)
            echo "Usage: $0 [--coverage|--mutation|--all]"
            echo ""
            echo "  --coverage   Run coverage analysis only"
            echo "  --mutation   Run mutation testing only (requires prior coverage data)"
            echo "  --all        Run coverage, mutation, linting, and type checking"
            echo "  (default)    Run coverage and mutation testing"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# ── Dependencies ───────────────────────────────────────────────────────────────

info "Checking dependencies…"
if $RUN_COVERAGE; then
    check_dep "$COVERAGE_PKG"
fi
if $RUN_MUTATION; then
    check_dep "$MUTMUT_PKG"
fi
ok "Dependencies ready"

# ── Pre-flight checks ──────────────────────────────────────────────────────────

preflight_check() {
    info "Running pre-flight checks…"

    # Check MongoDB is reachable
    if python3 -c "from pymongo import MongoClient; MongoClient('localhost', 27017, serverSelectionTimeoutMS=2000).admin.command('ping')" 2>/dev/null; then
        ok "MongoDB reachable at localhost:27017"
    else
        warn "MongoDB not reachable at localhost:27017 — test isolation disabled"
    fi

    # Check ClickHouse is reachable
    if python3 -c "
import clickhouse_driver
c = clickhouse_driver.Client(host='localhost', port=9000, settings={'connect_timeout': 2})
c.execute('SELECT 1')
c.disconnect()
" 2>/dev/null; then
        ok "ClickHouse reachable at localhost:9000"
    else
        warn "ClickHouse not reachable at localhost:9000 — some integration tests may fail"
    fi

    # Check that test directory exists and is non-empty
    if [[ ! -d "$TEST_DIR" ]]; then
        fail "Test directory '$TEST_DIR' does not exist"
        return 1
    fi

    local test_count
    test_count=$(find "$TEST_DIR" -name 'test_*.py' -type f 2>/dev/null | wc -l)
    if [[ "$test_count" -eq 0 ]]; then
        fail "No test files found in '$TEST_DIR'"
        return 1
    fi
    ok "Found ${test_count} test files in ${TEST_DIR}/"
}

if $RUN_COVERAGE || $RUN_MUTATION; then
    preflight_check || warn "Pre-flight checks had warnings"
fi

# ── Linting ────────────────────────────────────────────────────────────────────

run_lint() {
    if ! $LINT_CHECK; then
        return 0
    fi
    check_dep "$LINT_PKG"
    info "Running linting via ruff…"
    if python3 -m ruff check "${MUTATION_BASE_DIR}" "${TEST_DIR}"; then
        ok "Linting passed"
        return 0
    else
        fail "Linting found issues"
        return 1
    fi
}

run_typecheck() {
    if ! $TYPECHECK; then
        return 0
    fi
    check_dep "$TYPECHECK_PKG"
    info "Running type checking via mypy…"
    if python3 -m mypy "${MUTATION_BASE_DIR}" --ignore-missing-imports; then
        ok "Type checking passed"
        return 0
    else
        fail "Type checking found issues"
        return 1
    fi
}

# ── Coverage ───────────────────────────────────────────────────────────────────

run_coverage() {
    info "Running test coverage on ${MUTATION_BASE_DIR}/…"

    # Erase any stale coverage data
    coverage erase

    # Run tests under coverage with branch tracking.
    PYTHONPATH=. coverage run \
        --branch \
        --source="${MUTATION_BASE_DIR}" \
        -m unittest discover -s "${TEST_DIR}" --top-level-dir . -v

    # Produce an HTML report for human inspection
    coverage html -d htmlcov --show-contexts --title "rsstag coverage"

    # Capture textual summary
    local report
    report=$(coverage report --show-missing --fail-under=0)
    echo "$report"

    # Parse line and branch coverage from the JSON report.
    # coverage report's text TOTAL line only ever has one % (the combined Cover
    # figure), so we must use `coverage json` to get separate line/branch counts.
    local line_pct branch_pct
    local json_report
    json_report=$(coverage json -o /dev/stdout -q 2>/dev/null)

    if [[ -z "$json_report" ]]; then
        fail "Could not generate coverage JSON report"
        return 1
    fi

    line_pct=$(echo "$json_report" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(int(d['totals']['percent_covered']))
" 2>/dev/null || echo "")

    branch_pct=$(echo "$json_report" | python3 -c "
import sys, json
d = json.load(sys.stdin)
t = d['totals']
nb = t.get('num_branches', 0)
cb = t.get('covered_branches', 0)
print(int(cb * 100 / nb) if nb else 'N/A')
" 2>/dev/null || echo "N/A")

    if [[ -z "$line_pct" ]]; then
        fail "Could not parse line coverage from JSON report"
        return 1
    fi
    if [[ "$branch_pct" == "N/A" ]]; then
        warn "No branch coverage data — skipping branch check"
    fi

    echo ""
    info "Coverage summary:"
    echo "  Line coverage:   ${line_pct}%"
    echo "  Branch coverage: ${branch_pct}%"
    echo "  Full report:     htmlcov/index.html"
    echo ""

    # Threshold checks
    local failed=false
    if (( line_pct < COVERAGE_THRESHOLD )); then
        fail "Line coverage ${line_pct}% is below threshold ${COVERAGE_THRESHOLD}%"
        failed=true
    else
        ok "Line coverage ${line_pct}% meets threshold ${COVERAGE_THRESHOLD}%"
    fi

    if [[ "$branch_pct" != "N/A" ]] && (( branch_pct < BRANCH_COVERAGE_THRESHOLD )); then
        fail "Branch coverage ${branch_pct}% is below threshold ${BRANCH_COVERAGE_THRESHOLD}%"
        failed=true
    elif [[ "$branch_pct" != "N/A" ]]; then
        ok "Branch coverage ${branch_pct}% meets threshold ${BRANCH_COVERAGE_THRESHOLD}%"
    fi

    # Generate Cobertura XML report (useful for CI/tooling integration)
    coverage xml -o coverage.xml 2>/dev/null || true

    if $failed; then
        return 1
    fi
    return 0
}

if $RUN_COVERAGE; then
    COVERAGE_EXIT=0
    run_coverage || COVERAGE_EXIT=$?
    echo ""
fi

# ── Linting / type checking ──────────────────────────────────────────────────

LINT_EXIT=0
TYPECHECK_EXIT=0

run_lint || LINT_EXIT=$?
run_typecheck || TYPECHECK_EXIT=$?
if $LINT_CHECK || $TYPECHECK; then
    echo ""
fi

# ── Mutation testing ──────────────────────────────────────────────────────────

run_mutation() {
    info "Running mutation testing on ${MUTATION_BASE_DIR}/…"
    local mutmut="python3 -m mutmut"

    # mutmut reads config from setup.cfg [mutmut] section.
    # Required: paths_to_mutate and runner (or test_command).

    # Run mutation testing.
    # mutmut run mutates code and checks if tests catch the mutations.
    # Surviving mutants indicate gaps in test coverage.
    # Capture output so we can parse the summary line from the run's progress output.
    local mutmut_exit=0
    local run_output
    run_output=$($mutmut run --timeout "$MUTATION_TIMEOUT" 2>&1) || mutmut_exit=$?
    echo "$run_output"
    # mutmut exits 2 when mutants survive (expected), other non-zero may be real errors
    if [[ $mutmut_exit -ne 0 && $mutmut_exit -ne 2 ]]; then
        fail "mutmut run failed with exit code $mutmut_exit"
        return 1
    fi

    # Fetch the full per-mutant listing for counting and display.
    # --all shows every mutant (killed + survived + timeout + suspicious).
    local results_text
    results_text=$($mutmut results --all 2>&1 || true)

    echo ""
    info "Mutation testing results:"
    echo "$results_text"
    echo ""

    # Parse counts. mutmut run emits a summary like:
    #   🎉 30 killed, 10 survived, 1 timeout, 1 suspicious out of 42 total
    # Try that first; fall back to counting per-mutant lines from `mutmut results --all`.
    local total=0 killed=0 survived=0 timeout_count=0 suspicious=0

    if echo "$run_output" | grep -qP '(?:killed|survived|timeout|suspicious).*total'; then
        local summary_line
        summary_line=$(echo "$run_output" | grep -P '(?:killed|survived|timeout|suspicious).*total' | tail -1)
        killed=$(echo      "$summary_line" | grep -oP '\d+(?=\s+killed)'     || echo "0")
        survived=$(echo    "$summary_line" | grep -oP '\d+(?=\s+survived)'   || echo "0")
        timeout_count=$(echo "$summary_line" | grep -oP '\d+(?=\s+timeout)' || echo "0")
        suspicious=$(echo  "$summary_line" | grep -oP '\d+(?=\s+suspicious)' || echo "0")
        total=$(echo       "$summary_line" | grep -oP '\d+(?=\s+total)'      || echo "0")
    fi

    # Fallback: count individual mutant status lines from `mutmut results --all`
    if [[ "$total" == "0" || -z "$total" ]]; then
        killed=$(echo        "$results_text" | grep -cP '\d+\.\s+killed'      || echo "0")
        survived=$(echo      "$results_text" | grep -cP '\d+\.\s+survived'    || echo "0")
        timeout_count=$(echo "$results_text" | grep -cP '\d+\.\s+timeout'     || echo "0")
        suspicious=$(echo    "$results_text" | grep -cP '\d+\.\s+suspicious'  || echo "0")
        total=$(( killed + survived + timeout_count + suspicious ))
    fi

    echo "  Total mutants:    ${total}"
    echo "  Killed:           ${killed}"
    echo "  Survived:         ${survived}"
    echo "  Timeouts:         ${timeout_count}"
    echo "  Suspicious:       ${suspicious}"

    # Calculate mutation score
    local mutation_score=0
    if (( total > 0 )); then
        mutation_score=$(( (killed * 100) / total ))
    fi
    echo "  Mutation score:   ${mutation_score}%"
    echo ""

    # List surviving mutants for agents to target
    if (( survived > 0 )); then
        warn "Surviving mutants (add tests for these):"
        $mutmut results 2>&1 | head -30 || true
        echo ""
    fi

    # Return non-zero if any mutants survived or timed out
    if (( survived > 0 || timeout_count > 0 )); then
        fail "${survived} mutant(s) survived, ${timeout_count} timeout(s) — tests need improvement"
        return 1
    elif (( total == 0 )); then
        warn "No mutants were generated — check mutmut configuration"
        return 0
    else
        ok "All ${killed} mutant(s) killed — tests are strong"
        return 0
    fi
}

if $RUN_MUTATION; then
    MUTATION_EXIT=0
    run_mutation || MUTATION_EXIT=$?
    echo ""
fi

# ── Final summary ──────────────────────────────────────────────────────────────

echo "═══════════════════════════════════════════════════════════"
echo "  Backend quality report — $(date '+%Y-%m-%d %H:%M')"
echo "═══════════════════════════════════════════════════════════"

if $RUN_COVERAGE && [[ -n "${COVERAGE_EXIT:-}" ]]; then
    if (( COVERAGE_EXIT == 0 )); then
        ok "Coverage: PASSED"
    else
        fail "Coverage: FAILED"
    fi
fi

if $RUN_MUTATION && [[ -n "${MUTATION_EXIT:-}" ]]; then
    if (( MUTATION_EXIT == 0 )); then
        ok "Mutation testing: PASSED"
    else
        fail "Mutation testing: FAILED"
    fi
fi

if $LINT_CHECK || $TYPECHECK; then
    echo "--- Static analysis ---"
fi

if $LINT_CHECK; then
    if (( LINT_EXIT == 0 )); then
        ok "Linting (ruff): PASSED"
    else
        fail "Linting (ruff): FAILED"
    fi
fi

if $TYPECHECK; then
    if (( TYPECHECK_EXIT == 0 )); then
        ok "Type checking (mypy): PASSED"
    else
        fail "Type checking (mypy): FAILED"
    fi
fi

echo ""

if [[ "${COVERAGE_EXIT:-0}" -ne 0 || "${MUTATION_EXIT:-0}" -ne 0 || "${LINT_EXIT:-0}" -ne 0 || "${TYPECHECK_EXIT:-0}" -ne 0 ]]; then
    fail "One or more quality checks failed. See details above."
    exit 1
fi

ok "All quality checks passed"
exit 0
