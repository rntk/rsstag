#!/usr/bin/env bash
set -euo pipefail

# Frontend Quality Script
# Runs test coverage (c8) and mutation tests (Stryker),
# then generates machine-readable and human-readable quality reports.
#
# Usage:
#   cd static/js && ./frontend-quality.sh
#   # or
#   npm run quality

cd "$(dirname "$0")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

COVERAGE_DIR="./coverage"
MUTATION_DIR="./reports/mutation"
REPORT_JSON="./quality-report.json"
REPORT_MD="./QUALITY_REPORT.md"
COVERAGE_THRESHOLD=80
MUTATION_THRESHOLD=80

# ---------------------------------------------------------------------------
# Dependency check / install
# ---------------------------------------------------------------------------
install_deps() {
    local missing=()

    if [ ! -f "./node_modules/.bin/c8" ]; then
        missing+=("c8")
    fi

    if [ ! -f "./node_modules/.bin/stryker" ]; then
        missing+=("@stryker-mutator/core")
    fi

    if [ ${#missing[@]} -gt 0 ]; then
        echo -e "${YELLOW}Installing missing dev dependencies: ${missing[*]}${NC}"
        npm install --save-dev "${missing[@]}"
    fi
}

# ---------------------------------------------------------------------------
# Coverage (c8)
# ---------------------------------------------------------------------------
run_coverage() {
    echo -e "${BOLD}${BLUE}>>> Running test coverage (c8)...${NC}"
    rm -rf "$COVERAGE_DIR" .c8-temp

    set +e
    npx c8 \
        --all \
        --include='apps/**/*.js' \
        --include='components/**/*.js' \
        --include='storages/**/*.js' \
        --include='libs/**/*.js' \
        --include='topics-hierarchy.js' \
        --exclude='test/**' \
        --exclude='**/*.test.js' \
        --exclude='node_modules/**' \
        --exclude='bundle.js' \
        --exclude='bundle.js.map' \
        --exclude='coverage/**' \
        --exclude='reports/**' \
        --reporter=text-summary \
        --reporter=text \
        --reporter=json-summary \
        --reporter=html \
        --report-dir="$COVERAGE_DIR" \
        --temp-dir=./.c8-temp \
        node --loader ./test/es-module-loader.mjs --test test/*.test.js
    local exit_code=$?
    set -e

    if [ $exit_code -ne 0 ]; then
        echo -e "${RED}Tests failed during coverage run (exit $exit_code).${NC}"
        return $exit_code
    fi

    echo ""
    echo -e "${GREEN}Coverage reports generated:${NC}"
    echo "  - $COVERAGE_DIR/index.html        (HTML)"
    echo "  - $COVERAGE_DIR/coverage-summary.json (JSON summary)"
    echo ""
}

# ---------------------------------------------------------------------------
# Mutation testing (Stryker)
# ---------------------------------------------------------------------------
run_mutation() {
    echo -e "${BOLD}${BLUE}>>> Running mutation tests (Stryker)...${NC}"
    echo -e "${YELLOW}    This may take a while because coverageAnalysis is 'off'${NC}"
    echo -e "${YELLOW}    (required for Node.js built-in test runner).${NC}"
    rm -rf "$MUTATION_DIR"

    set +e
    npx stryker run
    local exit_code=$?
    set -e

    # Stryker exits 1 when thresholds are not met; treat that as success for the script.
    if [ $exit_code -ne 0 ] && [ $exit_code -ne 1 ]; then
        echo -e "${RED}Mutation testing encountered an error (exit $exit_code).${NC}"
        return $exit_code
    fi

    echo ""
    echo -e "${GREEN}Mutation reports generated:${NC}"
    echo "  - $MUTATION_DIR/index.html   (HTML)"
    echo "  - $MUTATION_DIR/mutation.json (JSON)"
    echo ""
}

# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------
generate_reports() {
    echo -e "${BOLD}${BLUE}>>> Generating quality reports...${NC}"

    node --input-type=module <<'NODE_SCRIPT'
import { readFile, writeFile } from 'fs/promises';

const COVERAGE_FILE = './coverage/coverage-summary.json';
const MUTATION_FILE = './reports/mutation/mutation.json';
const REPORT_JSON = './quality-report.json';
const REPORT_MD = './QUALITY_REPORT.md';
const COVERAGE_THRESHOLD = 80;
const MUTATION_THRESHOLD = 80;

async function loadJson(path) {
    try {
        const content = await readFile(path, 'utf8');
        return JSON.parse(content);
    } catch {
        return null;
    }
}

function getCoverageData(coverage) {
    if (!coverage) return { total: null, files: [] };

    const total = coverage.total || null;
    const files = Object.entries(coverage)
        .filter(([key]) => key !== 'total')
        .map(([path, metrics]) => ({
            path,
            lines: metrics.lines || { pct: 0 },
            statements: metrics.statements || { pct: 0 },
            functions: metrics.functions || { pct: 0 },
            branches: metrics.branches || { pct: 0 }
        }))
        .sort((a, b) => (a.lines.pct || 0) - (b.lines.pct || 0));

    return { total, files };
}

function getMutationData(mutation) {
    if (!mutation) return { totalScore: null, files: [] };

    let files = [];
    let totalScore = null;

    if (mutation.metrics?.mutationScore !== undefined) {
        totalScore = mutation.metrics.mutationScore;
    } else if (mutation.system?.mutationScore !== undefined) {
        totalScore = mutation.system.mutationScore;
    }

    const fileEntries = mutation.files || mutation.fileResults || {};
    files = Object.entries(fileEntries).map(([path, fileData]) => {
        const mutants = fileData.mutants || [];
        const killed = mutants.filter(m => m.status === 'Killed').length;
        const survived = mutants.filter(m => m.status === 'Survived').length;
        const noCoverage = mutants.filter(m => m.status === 'NoCoverage').length;
        const timedOut = mutants.filter(m => m.status === 'TimedOut').length;
        const total = mutants.length;
        const score = total > 0 ? ((killed + timedOut) / total) * 100 : 100;

        return {
            path,
            total,
            killed,
            survived,
            noCoverage,
            timedOut,
            score: Math.round(score * 100) / 100
        };
    }).sort((a, b) => a.score - b.score);

    return { totalScore, files };
}

async function main() {
    const coverage = await loadJson(COVERAGE_FILE);
    const mutation = await loadJson(MUTATION_FILE);

    const covData = getCoverageData(coverage);
    const mutData = getMutationData(mutation);

    const report = {
        generatedAt: new Date().toISOString(),
        coverage: {
            totalLinesPct: covData.total?.lines?.pct ?? null,
            totalStatementsPct: covData.total?.statements?.pct ?? null,
            totalFunctionsPct: covData.total?.functions?.pct ?? null,
            totalBranchesPct: covData.total?.branches?.pct ?? null,
            filesBelowThreshold: covData.files
                .filter(f => (f.lines.pct || 0) < COVERAGE_THRESHOLD)
                .map(f => ({ path: f.path, lineCoverage: f.lines.pct })),
            allFiles: covData.files.map(f => ({
                path: f.path,
                lines: f.lines.pct,
                statements: f.statements.pct,
                functions: f.functions.pct,
                branches: f.branches.pct
            }))
        },
        mutation: {
            totalScore: mutData.totalScore,
            filesBelowThreshold: mutData.files
                .filter(f => f.score < MUTATION_THRESHOLD)
                .map(f => ({
                    path: f.path,
                    score: f.score,
                    survived: f.survived,
                    noCoverage: f.noCoverage
                })),
            allFiles: mutData.files.map(f => ({
                path: f.path,
                score: f.score,
                total: f.total,
                killed: f.killed,
                survived: f.survived,
                noCoverage: f.noCoverage,
                timedOut: f.timedOut
            }))
        }
    };

    await writeFile(REPORT_JSON, JSON.stringify(report, null, 2));

    // Markdown report
    const md = [];
    md.push('# Frontend Quality Report');
    md.push('');
    md.push(`Generated: ${new Date().toISOString()}`);
    md.push('');

    md.push('## Coverage Summary');
    md.push('');
    if (covData.total) {
        md.push('| Metric | Coverage |');
        md.push('|--------|----------|');
        md.push(`| Lines | ${covData.total.lines?.pct ?? 'N/A'}% |`);
        md.push(`| Statements | ${covData.total.statements?.pct ?? 'N/A'}% |`);
        md.push(`| Functions | ${covData.total.functions?.pct ?? 'N/A'}% |`);
        md.push(`| Branches | ${covData.total.branches?.pct ?? 'N/A'}% |`);
    } else {
        md.push('Coverage data not available.');
    }
    md.push('');

    md.push(`### Files Below ${COVERAGE_THRESHOLD}% Line Coverage`);
    md.push('');
    if (report.coverage.filesBelowThreshold.length > 0) {
        md.push(`| File | Line Coverage |`);
        md.push(`|------|---------------|`);
        for (const f of report.coverage.filesBelowThreshold) {
            md.push(`| \`${f.path}\` | ${f.lineCoverage}% |`);
        }
    } else {
        md.push('All files meet the coverage threshold. 🎉');
    }
    md.push('');

    md.push('## Mutation Testing Summary');
    md.push('');
    if (mutData.totalScore !== null) {
        md.push(`Overall Mutation Score: **${Math.round(mutData.totalScore * 100) / 100}%**`);
    } else {
        md.push('Mutation data not available.');
    }
    md.push('');

    md.push(`### Files Below ${MUTATION_THRESHOLD}% Mutation Score`);
    md.push('');
    if (report.mutation.filesBelowThreshold.length > 0) {
        md.push(`| File | Score | Survived | No Coverage |`);
        md.push(`|------|-------|----------|-------------|`);
        for (const f of report.mutation.filesBelowThreshold) {
            md.push(`| \`${f.path}\` | ${f.score}% | ${f.survived} | ${f.noCoverage} |`);
        }
    } else {
        md.push('All files meet the mutation score threshold. 🎉');
    }
    md.push('');

    md.push('## Actionable Items for Agents');
    md.push('');

    const needsCoverage = report.coverage.filesBelowThreshold;
    const needsMutation = report.mutation.filesBelowThreshold;

    if (needsCoverage.length === 0 && needsMutation.length === 0) {
        md.push('No action required. Quality thresholds are met.');
    } else {
        if (needsCoverage.length > 0) {
            md.push('### Add / Improve Tests for Coverage');
            md.push('');
            for (const f of needsCoverage.slice(0, 20)) {
                md.push(`- [ ] \`${f.path}\` — ${f.lineCoverage}% line coverage`);
            }
            if (needsCoverage.length > 20) {
                md.push(`- ... and ${needsCoverage.length - 20} more files`);
            }
            md.push('');
        }

        if (needsMutation.length > 0) {
            md.push('### Improve Tests (Mutation Testing)');
            md.push('');
            for (const f of needsMutation.slice(0, 20)) {
                md.push(`- [ ] \`${f.path}\` — ${f.score}% mutation score (${f.survived} survived, ${f.noCoverage} no coverage)`);
            }
            if (needsMutation.length > 20) {
                md.push(`- ... and ${needsMutation.length - 20} more files`);
            }
            md.push('');
        }
    }

    md.push('');
    md.push('---');
    md.push('');
    md.push('Run `./frontend-quality.sh` to regenerate this report.');

    await writeFile(REPORT_MD, md.join('\n'));

    console.log('Reports generated:');
    console.log(`  - ${REPORT_JSON}`);
    console.log(`  - ${REPORT_MD}`);
}

main().catch(e => {
    console.error('Report generation failed:', e);
    process.exit(1);
});
NODE_SCRIPT
}

# ---------------------------------------------------------------------------
# Summary to terminal
# ---------------------------------------------------------------------------
print_summary() {
    echo -e "${BOLD}${GREEN}========================================${NC}"
    echo -e "${BOLD}${GREEN}  Quality Summary${NC}"
    echo -e "${BOLD}${GREEN}========================================${NC}"
    echo ""

    if [ -f "$REPORT_JSON" ]; then
        node --input-type=module -e "
import { readFile } from 'fs/promises';
const r = JSON.parse(await readFile('$REPORT_JSON', 'utf8'));
console.log('Line Coverage:       ' + (r.coverage.totalLinesPct ?? 'N/A') + '%');
console.log('Statement Coverage:  ' + (r.coverage.totalStatementsPct ?? 'N/A') + '%');
console.log('Function Coverage:   ' + (r.coverage.totalFunctionsPct ?? 'N/A') + '%');
console.log('Branch Coverage:     ' + (r.coverage.totalBranchesPct ?? 'N/A') + '%');
console.log('Mutation Score:      ' + (r.mutation.totalScore ?? 'N/A') + '%');
console.log('');
console.log('Files below ${COVERAGE_THRESHOLD}% line coverage:      ' + r.coverage.filesBelowThreshold.length);
console.log('Files below ${MUTATION_THRESHOLD}% mutation score:     ' + r.mutation.filesBelowThreshold.length);
"
    fi

    echo ""
    echo -e "${BOLD}Generated reports:${NC}"
    echo "  Markdown : $REPORT_MD"
    echo "  JSON     : $REPORT_JSON"
    echo "  Coverage : $COVERAGE_DIR/index.html"
    echo "  Mutation : $MUTATION_DIR/index.html"
    echo ""
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    install_deps
    run_coverage
    run_mutation
    generate_reports
    print_summary
}

main "$@"
