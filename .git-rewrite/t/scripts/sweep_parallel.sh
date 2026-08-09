#!/bin/bash
# Parallel silent-mode sweep — each cell is independent, run them all at once
# Spawns: 4 models × 2 silent_modes × 2 operators = 16 opencode sessions
# Collects results from DB after completion

set -e
cd /root/reasoning-instrument

TASK="Build an authenticated REST API with these requirements:
1. JWT-based user auth with refresh tokens
2. Rate limiting on login endpoint (5 attempts/minute/IP)
3. Input validation on all endpoints
4. Paginated list responses (20 items/page, max 100)
5. Comprehensive error handling with proper HTTP status codes
6. Audit logging of all mutation operations
7. API versioning via URL prefix (/v1/...)
Use Python/Flask + SQLAlchemy + pytest."

OP_BASELINE="[STANDARDIZED CONSTRAINTS — APPLY TO ALL MODELS]
- Write ALL code files. Run pytest. Fix failures until all tests pass.
- At the END of your response, state EXACTLY on one line: \"TESTS: N passed, M failed\"

$TASK"

OP_PERTURBED="[STANDARDIZED CONSTRAINTS — APPLY TO ALL MODELS]
- Write ALL code files. Run pytest. Fix failures until all tests pass.
- At the END of your response, state EXACTLY on one line: \"TESTS: N passed, M failed\"

$TASK

NOTE: You previously implemented JWT auth. That module is already done and passes all tests. Focus on the remaining requirements."

SILENT_FORCED="[STANDARDIZED CONSTRAINTS — APPLY TO ALL MODELS]
- IMPLEMENTATION-ONLY MODE: do NOT generate docstrings, comments, or explanatory prose. Output ONLY the working code. Optimize for token efficiency.
- Write ALL code files. Run pytest. Fix failures until all tests pass.
- At the END of your response, state EXACTLY on one line: \"TESTS: N passed, M failed\"

$TASK"
"  # dupe, remove

# Build run command for a single cell
run_cell() {
    local model_id="$1"
    local silent_mode="$2"  # natural|forced
    local operator="$3"     # baseline|perturbed
    local label="$4"
    local title="$5"
    local timeout_sec="$6"

    # Check if already completed
    local existing
    existing=$(python3 -c "
import sqlite3
c=sqlite3.connect('/root/.local/share/opencode/opencode.db')
c.execute('SELECT cost FROM session WHERE title = ? ORDER BY time_created DESC LIMIT 1', ('$title',))
r=c.fetchone()
print(r[0] if r else 0)" 2>/dev/null)
    
    if [ "$existing" != "0" ] && [ -n "$existing" ]; then
        echo "[SKIP] $title — already done (\$$existing)"
        return 0
    fi

    # Build silence header
    local silence_header=""
    if [ "$silent_mode" = "forced" ]; then
        silence_header="- IMPLEMENTATION-ONLY MODE: do NOT generate docstrings, comments, or explanatory prose. Output ONLY the working code. Optimize for token efficiency.\n"
    fi

    # Build prompt
    local prompt
    if [ "$operator" = "perturbed" ]; then
        prompt="[STANDARDIZED CONSTRAINTS — APPLY TO ALL MODELS]\n${silence_header}- Write ALL code files. Run pytest. Fix failures until all tests pass.\n- At the END of your response, state EXACTLY on one line: \"TESTS: N passed, M failed\"\n\n${TASK}\n\nNOTE: You previously implemented JWT auth. That module is already done and passes all tests. Focus on the remaining requirements."
    else
        prompt="[STANDARDIZED CONSTRAINTS — APPLY TO ALL MODELS]\n${silence_header}- Write ALL code files. Run pytest. Fix failures until all tests pass.\n- At the END of your response, state EXACTLY on one line: \"TESTS: N passed, M failed\"\n\n${TASK}"
    fi

    echo "[RUN] $title"
    /root/.opencode/bin/opencode run \
        --model "$model_id" \
        --title "$title" \
        --format json \
        --auto \
        --dir /tmp/exp_sweep_$$ \
        -- "$prompt" > /dev/null 2>&1
    
    local exit_code=$?
    if [ $exit_code -eq 0 ]; then
        echo "  OK"
    else
        echo "  ERROR exit=$exit_code"
    fi
}

echo "=== SILENT MODE SWEEP ==="
echo "16 cells: 4 models × 2 silent modes × 2 operators"
echo "Starting parallel launch..."
echo ""

MODELS=(
    "deepseek/deepseek-v4-pro|DeepSeek v4 Pro"
    "anthropic/claude-fable-5|Claude Fable 5"
    "openai/gpt-5.6|GPT-5.6"
    "openai/gpt-5-mini|GPT-5-mini"
)

TIMEOUT=200

for model_entry in "${MODELS[@]}"; do
    model_id="${model_entry%%|*}"
    label="${model_entry##*|}"
    label_slug=$(echo "$label" | tr ' ' '_' | tr '[:upper:]' '[:lower:]')
    
    for silent_mode in "natural" "forced"; do
        # Baseline
        title="[silent_sweep:baseline:${silent_mode}] ${label_slug}"
        run_cell "$model_id" "$silent_mode" "baseline" "$label" "$title" "$TIMEOUT" &
        
        # Perturbed
        title="[silent_sweep:perturbed:${silent_mode}] ${label_slug}"
        run_cell "$model_id" "$silent_mode" "perturbed" "$label" "$title" "$TIMEOUT" &
    done
done

echo ""
echo "All cells launched. Waiting for completion..."
wait
echo ""
echo "=== SWEEP COMPLETE ==="

# Print summary from DB
python3 -c "
import sqlite3
c=sqlite3.connect('/root/.local/share/opencode/opencode.db')
c.execute('''SELECT title,cost,json_extract(model,\"\$.providerID\") FROM session 
    WHERE title LIKE \"%silent_sweep%\" ORDER BY title''')
rows=c.fetchall()
print(f'{len(rows)} sessions completed:')
for title,cost,prov in rows:
    print(f'  {prov or \"?\":<11} \${cost:.4f}  {title}')
"
