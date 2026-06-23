#!/bin/bash
# Telemetría de uso de skills — PostToolUse (matcher: Skill)
# Appenda {"timestamp":"...","skill":"..."} a .claude/skill-ledger.jsonl (gitignored)
SKILL=$(python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('skill', 'unknown'))
except Exception:
    print('unknown')
" 2>/dev/null || echo "unknown")
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "{\"timestamp\":\"$TIMESTAMP\",\"skill\":\"$SKILL\"}" >> .claude/skill-ledger.jsonl
