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

# Packages that must be installed (added at runtime if missing)
COVERAGE_PKG="coverage"
MUTMUT_PKG="mutmut"

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
        --help|-h)
            echo "Usage: $0 [--coverage|--mutation]"
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

# ── Coverage ───────────────────────────────────────────────────────────────────

run_coverage() {
    info "Running test coverage on ${MUTATION_BASE_DIR}/…"

    # Erase any stale coverage data
    coverage erase

    # Run tests under coverage.
    # The project uses unittest discover; we also add branch tracking.
    PYTHONPATH=. coverage run \
        --branch \
        --source="${MUTATION_BASE_DIR}" \
        --parallel-mode \
        -m unittest discover -s "${TEST_DIR}" -v

    # Combine parallel data (if any)
    coverage combine 2>/dev/null || true

    # Produce an HTML report for human inspection
    coverage html -d htmlcov --show-contexts --title "rsstag coverage"

    # Capture textual summary
    local report
    report=$(coverage report --show-missing --fail-under=0)
    echo "$report"

    # Parse line and branch coverage percentages from the TOTAL line
    # coverage report TOTAL line looks like:
    #   TOTAL   1234   567    89    12    54%   43%
    #   (files  lines  missing  branches  partial  line%  branch%)
    local line_pct branch_pct
    local total_line
    total_line=$(echo "$report" | grep '^TOTAL' || echo "")

    if [[ -z "$total_line" ]]; then
        fail "Could not parse coverage report TOTAL line"
        return 1
    fi

    # Extract percentages — last two % values are line and branch coverage
    line_pct=$(echo "$total_line" | grep -oP '\d+%' | head -1 | tr -d '%')
    branch_pct=$(echo "$total_line" | grep -oP '\d+%' | tail -1 | tr -d '%')

    # If line and branch are the same value, branch coverage wasn't measured
    if [[ "$line_pct" == "$branch_pct" ]]; then
        branch_pct="N/A"
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

    # Save coverage data for mutation testing
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

# ── Mutation testing ──────────────────────────────────────────────────────────

run_mutation() {
    info "Running mutation testing on ${MUTATION_BASE_DIR}/…"
    local mutmut="python3 -m mutmut"

    # mutmut reads config from setup.cfg [mutmut] section.
    # Required: paths_to_mutate and runner (or test_command).

    # Run mutation testing.
    # mutmut run mutates code and checks if tests catch the mutations.
    # Surviving mutants indicate gaps in test coverage.
    $mutmut run 2>&1 || true  # mutmut exits non-zero when mutants survive; we handle below

    # Show results
    echo ""
    info "Mutation testing results:"
    $mutmut results --all true || true
    echo ""

    # Parse result counts from mutmut results output
    # mutmut results shows per-file mutant status, e.g.:
    #   rsstag/foo.py:1: survived
    # Summary line at end:
    #   42 total, 30 killed, 10 survived, 1 timeout, 1 suspicious
    local total=0 killed=0 survived=0 timeout_count=0 suspicious=0
    local results_text
    results_text=$($mutmut results --all true 2>&1 || true)

    # Try to parse the summary line
    if echo "$results_text" | grep -qP '\d+.*total'; then
        local summary_line
        summary_line=$(echo "$results_text" | grep -P '\d+.*total' | tail -1)
        total=$(echo "$summary_line" | grep -oP '\d+(?=\s*[, ]?\s*total)' || echo "0")
        killed=$(echo "$summary_line" | grep -oP '\d+(?=\s*[, ]?\s*killed)' || echo "0")
        survived=$(echo "$summary_line" | grep -oP '\d+(?=\s*[, ]?\s*survived)' || echo "0")
        timeout_count=$(echo "$summary_line" | grep -oP '\d+(?=\s*[, ]?\s*timeout)' || echo "0")
        suspicious=$(echo "$summary_line" | grep -oP '\d+(?=\s*[, ]?\s*suspicious)' || echo "0")
    fi

    # If parsing failed, count from individual mutant lines
    if [[ "$total" == "0" || -z "$total" ]]; then
        total=$(echo "$results_text" | grep -cP '\d+\.\s+(killed|survived|timeout|suspicious)' || echo "0")
        killed=$(echo "$results_text" | grep -cP '\d+\.\s+killed' || echo "0")
        survived=$(echo "$results_text" | grep -cP '\d+\.\s+survived' || echo "0")
        timeout_count=$(echo "$results_text" | grep -cP '\d+\.\s+timeout' || echo "0")
        suspicious=$(echo "$results_text" | grep -cP '\d+\.\s+suspicious' || echo "0")
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
        echo "$results_text" | grep -P '\d+\.\s+survived' | head -30 || true
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

echo ""

if [[ "${COVERAGE_EXIT:-0}" -ne 0 || "${MUTATION_EXIT:-0}" -ne 0 ]]; then
    fail "One or more quality checks failed. See details above."
    exit 1
fi

ok "All quality checks passed"
exit 0
