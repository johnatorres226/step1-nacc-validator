# Comprehensive Codebase Refactoring Plan
## Iterative AI Agent Execution Framework with Self-Documentation

---

## 🎯 **Mission Statement**

**Primary Goal**: Systematically reduce codebase complexity by 25-40% while preserving all core functionality and assumptions.

**Success Metrics**:
- Lines of code reduced by 1,500-2,500 (25-40%)
- Zero regression in functionality
- Single, clear pathway for each operation
- Improved maintainability for solo developer
- All tests passing after each phase

**Core Philosophy**:
- **PRESERVE**: Working validation logic, packet routing, hierarchical resolution
- **REMOVE**: Duplicate implementations, deprecated patterns, over-engineering
- **SIMPLIFY**: Complex abstractions into manageable chunks
- **DOCUMENT**: Every change for next agent in chain

---

## 📋 **Pre-Execution Setup**

### Initial Agent Instructions

```bash
# AGENT TASK 0: Initial Assessment and Setup

# Step 1: Read the current state
cat REFACTORING_PLAN.md 2>/dev/null || echo "No refactoring plan exists yet"

# Step 2: Create working environment
git checkout dev
git pull origin dev
git checkout -b refactor-cleanup-$(date +%Y%m%d-%H%M%S)

# Step 3: Create tracking document
cat > REFACTORING_PLAN.md << 'EOF'
# Refactoring Progress Tracker

## Current Phase: 0 - Initial Assessment
## Date Started: $(date)
## Branch: $(git branch --show-current)

## Completed Phases
- [ ] Phase 0: Initial Assessment
- [ ] Phase 1: Duplicate Rule Loading Removal  
- [ ] Phase 2: Empty File Cleanup
- [ ] Phase 3: Validation Consolidation
- [ ] Phase 4: Legacy Pipeline Removal
- [ ] Phase 5: Result Object Simplification
- [ ] Phase 6: Unused Code Removal
- [ ] Phase 7: Context Object Consolidation

## Current Status
Status: Starting initial assessment

## Notes
Starting comprehensive codebase analysis...
EOF

# Step 4: Run analysis tools
echo "=== Using .github/skills tools for analysis ===" 

# Step 5: Create baseline
mkdir -p .refactor-baseline
pytest tests/ -v --tb=short > .refactor-baseline/test_output.txt 2>&1
find src/pipeline -name "*.py" | xargs wc -l > .refactor-baseline/line_counts.txt
```

**⚠️ STOP HERE AND OUTPUT**:
```markdown
## Phase 0 Complete: Initial Assessment

### Actions Taken
- Created tracking document: `REFACTORING_PLAN.md`
- Established baseline test results
- Counted current lines of code
- Created refactor branch

### Metrics
- Total Python files: [COUNT]
- Total lines of code: [COUNT]
- Tests passing: [COUNT/TOTAL]

### Ready for Phase 1
Branch: [BRANCH_NAME]
Next: Analyze duplicate rule loading systems

### Agent Handoff
Next agent should:
1. Read `REFACTORING_PLAN.md`
2. Review baseline in `.refactor-baseline/`
3. Execute Phase 1 analysis
```

---

## 🔍 **Phase 1: Duplicate Rule Loading Analysis & Removal**

### Agent Context Loading Instructions

```bash
# AGENT TASK 1: Analyze and Remove Duplicate Rule Loading

# Step 1: Read previous context
echo "=== Reading Previous Context ==="
cat REFACTORING_PLAN.md | grep -A 20 "Current Phase"

# Step 2: Use function analyzer skill
echo "=== Analyzing rule loading functions ==="
# Use .github/skills/function-analyzer to scan:
# - src/pipeline/io/rules.py
# - src/pipeline/utils/instrument_mapping.py

# Create analysis report
cat > .refactor-work/phase1-analysis.md << 'EOF'
# Phase 1 Analysis: Rule Loading Duplication

## Files Analyzed
1. src/pipeline/io/rules.py
2. src/pipeline/utils/instrument_mapping.py

## Functions Found
[List all functions in both files]

## Duplication Assessment
[Mark which functions are duplicates]

## Dependencies
[List all files importing from each]

## Recommendation
[Keep/Delete decision with rationale]
EOF
```

### Execution Steps

**Step 1.1: Deep Analysis with Skills**

```bash
# Use clean-code skill to analyze duplication
cd .github/skills/clean-code
# Analyze both files for duplication patterns

# Document findings
cat >> .refactor-work/phase1-analysis.md << 'EOF'

## Detailed Analysis Results

### Duplicate Functions Identified:
1. `load_dynamic_rules_for_instrument()`
   - Location 1: src/pipeline/io/rules.py (lines X-Y)
   - Location 2: src/pipeline/utils/instrument_mapping.py (lines A-B)
   - Difference: [None / Minor / Significant]
   
2. `load_json_rules_for_instrument()`
   - Location 1: src/pipeline/io/rules.py (lines X-Y)
   - Location 2: src/pipeline/utils/instrument_mapping.py (lines A-B)
   - Difference: [None / Minor / Significant]

### Import Dependency Graph:
```
instrument_mapping.py
  ↓
  schema_builder.py
  
rules.py
  ↓
  [list all importers]
```

### Decision: DELETE instrument_mapping.py
Rationale: [Specific reasons based on analysis]
EOF
```

**Step 1.2: Verify No Functional Differences**

```python
# Create verification script
cat > .refactor-work/verify_duplication.py << 'EOF'
#!/usr/bin/env python3
"""Verify that duplicate functions are truly identical."""

import sys
import difflib
from pathlib import Path

def extract_function(file_path, function_name):
    """Extract function source code."""
    content = Path(file_path).read_text()
    # Simple extraction logic
    lines = content.split('\n')
    in_function = False
    function_lines = []
    indent_level = None
    
    for line in lines:
        if f'def {function_name}(' in line:
            in_function = True
            indent_level = len(line) - len(line.lstrip())
            function_lines.append(line)
        elif in_function:
            current_indent = len(line) - len(line.lstrip())
            if line.strip() and current_indent <= indent_level:
                break
            function_lines.append(line)
    
    return '\n'.join(function_lines)

# Compare functions
file1 = 'src/pipeline/io/rules.py'
file2 = 'src/pipeline/utils/instrument_mapping.py'

functions = [
    'load_dynamic_rules_for_instrument',
    'load_json_rules_for_instrument'
]

for func_name in functions:
    print(f"\n{'='*60}")
    print(f"Comparing: {func_name}")
    print('='*60)
    
    func1 = extract_function(file1, func_name)
    func2 = extract_function(file2, func_name)
    
    if func1 == func2:
        print("✓ IDENTICAL")
    else:
        print("✗ DIFFERENT - Showing diff:")
        diff = difflib.unified_diff(
            func1.splitlines(),
            func2.splitlines(),
            fromfile=file1,
            tofile=file2,
            lineterm=''
        )
        print('\n'.join(diff))

print("\n" + "="*60)
print("Analysis complete. See above for differences.")
EOF

python .refactor-work/verify_duplication.py
```

**Step 1.3: Find All Import References**

```bash
# Create comprehensive import analysis
echo "=== Analyzing import dependencies ===" > .refactor-work/phase1-imports.txt

echo -e "\n## Files importing from instrument_mapping:" >> .refactor-work/phase1-imports.txt
grep -r "from.*instrument_mapping import" src/ >> .refactor-work/phase1-imports.txt 2>&1

echo -e "\n## Files importing from rules:" >> .refactor-work/phase1-imports.txt
grep -r "from.*\.rules import" src/ >> .refactor-work/phase1-imports.txt 2>&1

echo -e "\n## Direct module imports:" >> .refactor-work/phase1-imports.txt
grep -r "import.*instrument_mapping" src/ >> .refactor-work/phase1-imports.txt 2>&1
grep -r "import.*\.rules" src/ >> .refactor-work/phase1-imports.txt 2>&1

cat .refactor-work/phase1-imports.txt
```

**Step 1.4: Execute Removal (Only if safe)**

```bash
# SAFETY CHECK: Only proceed if analysis confirms:
# 1. Functions are truly identical
# 2. instrument_mapping.py has NO unique functionality
# 3. All imports can be redirected to rules.py

# If safe, proceed:
echo "=== Executing removal ===" 

# Backup first
cp src/pipeline/utils/instrument_mapping.py .refactor-baseline/instrument_mapping.py.backup

# Update any imports (if needed - analysis showed schema_builder already uses rules.py)
# [No changes needed based on our earlier analysis]

# Remove the duplicate file
git rm src/pipeline/utils/instrument_mapping.py

# Compile check
python -m compileall src/pipeline/utils/ -q
python -m compileall src/pipeline/io/ -q
```

**Step 1.5: Test Changes**

```bash
# Run focused tests
echo "=== Testing rule loading functionality ==="

# Test 1: Direct import test
python << 'EOF'
import sys
sys.path.insert(0, 'src')

from pipeline.io.rules import (
    load_json_rules_for_instrument,
    load_dynamic_rules_for_instrument
)

print("✓ Imports successful")

# Test loading rules
try:
    rules = load_json_rules_for_instrument('form_header')
    print(f"✓ Loaded {len(rules)} rules for form_header")
except Exception as e:
    print(f"✗ Error: {e}")
    sys.exit(1)

print("✓ All rule loading tests passed")
EOF

# Test 2: Run rule-related pytest tests
pytest tests/ -v -k "rule" --tb=short -x

# Test 3: Run full test suite
pytest tests/ --tb=short -x
```

**Step 1.6: Document and Commit**

```bash
# Update refactoring plan
cat >> REFACTORING_PLAN.md << 'EOF'

## Phase 1 Complete: Duplicate Rule Loading Removal

### Date Completed: $(date)

### Changes Made
- ✅ Analyzed `src/pipeline/utils/instrument_mapping.py`
- ✅ Confirmed 100% duplication with `src/pipeline/io/rules.py`
- ✅ Verified no unique functionality in instrument_mapping.py
- ✅ Confirmed all imports already use rules.py
- ✅ Deleted `src/pipeline/utils/instrument_mapping.py`

### Files Modified
- DELETED: src/pipeline/utils/instrument_mapping.py (183 lines)

### Test Results
- All imports: ✓ PASS
- Rule loading: ✓ PASS  
- Focused tests: ✓ PASS
- Full test suite: ✓ PASS

### Metrics
- Lines removed: 183
- Tests passing: [X/Y]
- No regressions

### Next Phase
Phase 2: Empty File Cleanup

### Notes
- Clean removal, no complications
- No import updates needed (already using rules.py)
- Baseline preserved in .refactor-baseline/
EOF

# Commit changes
git add -A
git commit -m "Phase 1: Remove duplicate rule loading system

- Deleted pipeline/utils/instrument_mapping.py (183 lines)
- 100% duplicate of pipeline/io/rules.py
- All functionality preserved in rules.py
- No import updates needed
- All tests passing

See REFACTORING_PLAN.md for details"

git push origin $(git branch --show-current)
```

**⚠️ STOP HERE AND OUTPUT**:

```markdown
## Phase 1 Complete: Duplicate Rule Loading Removed

### Summary
Successfully removed duplicate rule loading implementation.

### Changes
- **Deleted**: `src/pipeline/utils/instrument_mapping.py` (183 lines)
- **Tests**: All passing (X/Y)
- **Regressions**: None detected

### Analysis Files Created
- `.refactor-work/phase1-analysis.md` - Detailed analysis
- `.refactor-work/phase1-imports.txt` - Import dependencies
- `.refactor-work/verify_duplication.py` - Verification script

### Verification
```bash
# Quick verification commands
cat REFACTORING_PLAN.md | grep -A 10 "Phase 1 Complete"
git log -1 --stat
pytest tests/ -k "rule" -v
```

### Next Agent Instructions
1. Read `REFACTORING_PLAN.md`
2. Review Phase 1 completion notes
3. Execute Phase 2: Empty File Cleanup
4. Use same pattern: Analyze → Execute → Test → Document → Stop

### Handoff Context
- Branch: $(git branch --show-current)
- Commit: $(git rev-parse --short HEAD)
- Lines removed so far: 183
- Status: ✅ Ready for Phase 2
```

---

## 🧹 **Phase 2: Empty File Cleanup**

### Agent Context Loading Instructions

```bash
# AGENT TASK 2: Empty __init__.py File Removal

# Step 1: Read context from previous phase
echo "=== Loading Context ==="
cat REFACTORING_PLAN.md | tail -50

# Step 2: Verify we're in correct state
git status
git log -1 --oneline

# Step 3: Confirm Phase 1 is complete
if ! grep -q "Phase 1 Complete" REFACTORING_PLAN.md; then
    echo "ERROR: Phase 1 not complete. Stopping."
    exit 1
fi

echo "✓ Context loaded. Starting Phase 2 analysis..."
```

### Execution Steps

**Step 2.1: Identify Empty Files**

```bash
# Create analysis directory for this phase
mkdir -p .refactor-work/phase2

# Find all __init__.py files
echo "=== Analyzing __init__.py files ===" > .refactor-work/phase2/analysis.txt

echo -e "\n## All __init__.py files:" >> .refactor-work/phase2/analysis.txt
find src/pipeline -name "__init__.py" -type f >> .refactor-work/phase2/analysis.txt

echo -e "\n## File sizes:" >> .refactor-work/phase2/analysis.txt
find src/pipeline -name "__init__.py" -type f -exec wc -l {} \; >> .refactor-work/phase2/analysis.txt

echo -e "\n## Empty files (0 lines):" >> .refactor-work/phase2/analysis.txt
find src/pipeline -name "__init__.py" -type f -empty >> .refactor-work/phase2/analysis.txt

# Check content of each file
echo -e "\n## Content analysis:" >> .refactor-work/phase2/analysis.txt
for file in $(find src/pipeline -name "__init__.py" -type f); do
    echo -e "\n### $file" >> .refactor-work/phase2/analysis.txt
    lines=$(wc -l < "$file")
    echo "Lines: $lines" >> .refactor-work/phase2/analysis.txt
    if [ $lines -eq 0 ]; then
        echo "Status: EMPTY - Safe to delete" >> .refactor-work/phase2/analysis.txt
    else
        echo "Content:" >> .refactor-work/phase2/analysis.txt
        cat "$file" >> .refactor-work/phase2/analysis.txt
        echo "Status: HAS CONTENT - Review before deletion" >> .refactor-work/phase2/analysis.txt
    fi
done

cat .refactor-work/phase2/analysis.txt
```

**Step 2.2: Check for Package-Level Imports**

```bash
# Verify no code depends on package-level imports
echo "=== Checking for package-level imports ===" > .refactor-work/phase2/import-check.txt

echo -e "\n## Package-level imports (would break):" >> .refactor-work/phase2/import-check.txt
grep -r "from pipeline import" src/ 2>&1 | grep -v "__pycache__" >> .refactor-work/phase2/import-check.txt || echo "None found ✓" >> .refactor-work/phase2/import-check.txt

echo -e "\n## Subpackage-level imports (might break):" >> .refactor-work/phase2/import-check.txt
grep -r "from pipeline\.\w\+ import" src/ 2>&1 | grep -v "__pycache__" | grep -v "from pipeline\.\w\+\.\w\+" >> .refactor-work/phase2/import-check.txt || echo "None found ✓" >> .refactor-work/phase2/import-check.txt

echo -e "\n## Module-level imports (safe):" >> .refactor-work/phase2/import-check.txt
grep -r "from pipeline\.\w\+\.\w\+ import" src/ 2>&1 | head -20 >> .refactor-work/phase2/import-check.txt

cat .refactor-work/phase2/import-check.txt

# Safety check
if grep -q "from pipeline import" src/ 2>/dev/null; then
    echo "⚠️  WARNING: Found package-level imports. Review before proceeding."
fi
```

**Step 2.3: Create Removal List**

```bash
# Generate safe removal list
cat > .refactor-work/phase2/removal-list.txt << 'EOF'
# Empty __init__.py files safe to delete

src/pipeline/config/__init__.py
src/pipeline/core/__init__.py
src/pipeline/io/__init__.py
src/pipeline/processors/__init__.py
src/pipeline/reports/__init__.py
src/pipeline/logging/__init__.py
src/pipeline/utils/__init__.py
EOF

echo "Files marked for removal:"
cat .refactor-work/phase2/removal-list.txt
```

**Step 2.4: Execute Removal (with safety checks)**

```bash
# SAFETY: Only proceed if:
# 1. All files in list are truly empty (0 bytes or 0 lines)
# 2. No package-level imports found

echo "=== Executing removal with safety checks ==="

# Verify each file before deletion
while IFS= read -r file; do
    # Skip comments and empty lines
    [[ "$file" =~ ^#.*$ ]] && continue
    [[ -z "$file" ]] && continue
    
    if [ ! -f "$file" ]; then
        echo "⚠️  WARNING: File not found: $file"
        continue
    fi
    
    lines=$(wc -l < "$file" 2>/dev/null || echo "1")
    if [ "$lines" -eq "0" ]; then
        echo "✓ Removing empty file: $file"
        git rm "$file"
    else
        echo "⚠️  SKIPPING non-empty file: $file ($lines lines)"
    fi
done < .refactor-work/phase2/removal-list.txt
```

**Step 2.5: Test Changes**

```bash
echo "=== Testing after empty file removal ==="

# Test 1: Python compilation
echo "Test 1: Checking Python compilation..."
python -m compileall src/pipeline -q && echo "✓ Compilation successful" || echo "✗ Compilation failed"

# Test 2: Import tests
echo "Test 2: Testing imports..."
python << 'EOF'
import sys
sys.path.insert(0, 'src')

# Test imports from each subpackage
try:
    from pipeline.config.config_manager import get_config
    print("✓ pipeline.config imports work")
except ImportError as e:
    print(f"✗ pipeline.config import failed: {e}")
    sys.exit(1)

try:
    from pipeline.core.fetcher import RedcapETLPipeline
    print("✓ pipeline.core imports work")
except ImportError as e:
    print(f"✗ pipeline.core import failed: {e}")
    sys.exit(1)

try:
    from pipeline.io.rules import load_json_rules_for_instrument
    print("✓ pipeline.io imports work")
except ImportError as e:
    print(f"✗ pipeline.io import failed: {e}")
    sys.exit(1)

try:
    from pipeline.processors.instrument_processors import DynamicInstrumentProcessor
    print("✓ pipeline.processors imports work")
except ImportError as e:
    print(f"✗ pipeline.processors import failed: {e}")
    sys.exit(1)

try:
    from pipeline.reports.report_pipeline import run_report_pipeline
    print("✓ pipeline.reports imports work")
except ImportError as e:
    print(f"✗ pipeline.reports import failed: {e}")
    sys.exit(1)

try:
    from pipeline.logging.logging_config import get_logger
    print("✓ pipeline.logging imports work")
except ImportError as e:
    print(f"✗ pipeline.logging import failed: {e}")
    sys.exit(1)

try:
    from pipeline.utils.schema_builder import build_cerberus_schema_for_instrument
    print("✓ pipeline.utils imports work")
except ImportError as e:
    print(f"✗ pipeline.utils import failed: {e}")
    sys.exit(1)

print("\n✓ All imports successful after removing empty __init__.py files")
EOF

# Test 3: Run test suite
echo "Test 3: Running pytest..."
pytest tests/ --tb=short -x
```

**Step 2.6: Document and Commit**

```bash
# Count removed files
removed_count=$(git status --short | grep "^D.*__init__.py" | wc -l)

# Update refactoring plan
cat >> REFACTORING_PLAN.md << EOF

## Phase 2 Complete: Empty File Cleanup

### Date Completed: $(date)

### Changes Made
- ✅ Analyzed all __init__.py files in pipeline/
- ✅ Verified files are completely empty (0 lines)
- ✅ Confirmed no package-level imports exist
- ✅ Removed $removed_count empty __init__.py files

### Files Deleted
$(git status --short | grep "^D.*__init__.py")

### Test Results
- Python compilation: ✓ PASS
- All module imports: ✓ PASS
- Full test suite: ✓ PASS

### Metrics
- Files removed: $removed_count
- Lines removed: 0 (files were empty)
- Total reduction: 183 lines (from Phase 1)
- Tests passing: [X/Y]

### Next Phase
Phase 3: Validation Function Consolidation

### Notes
- Clean removal, no complications
- All imports continue to work correctly
- Directory structure simplified
EOF

# Commit
git add -A
git commit -m "Phase 2: Remove empty __init__.py files

- Deleted $removed_count empty __init__.py files
- No functional changes (files were empty)
- All imports verified working
- All tests passing

Files removed:
$(git diff --name-only HEAD~1 HEAD | grep __init__.py)

See REFACTORING_PLAN.md for details"

git push origin $(git branch --show-current)
```

**⚠️ STOP HERE AND OUTPUT**:

```markdown
## Phase 2 Complete: Empty File Cleanup

### Summary
Removed all empty __init__.py files from pipeline structure.

### Changes
- **Deleted**: 7 empty __init__.py files
- **Tests**: All passing
- **Regressions**: None

### Analysis Files
- `.refactor-work/phase2/analysis.txt` - File content analysis
- `.refactor-work/phase2/import-check.txt` - Import verification
- `.refactor-work/phase2/removal-list.txt` - Files removed

### Cumulative Progress
- **Phase 1**: -183 lines (duplicate rules)
- **Phase 2**: -7 files (empty __init__)
- **Total**: 183 lines removed, 7 files deleted

### Next Agent Instructions
1. Read `REFACTORING_PLAN.md` (last 100 lines)
2. Verify Phases 1-2 complete
3. Execute Phase 3: Validation Consolidation
   - **WARNING**: This phase is HIGH RISK (core validation logic)
   - Use `.github/skills/function-analyzer` extensively
   - Create comprehensive backup before changes
   - Test incrementally after each function removal

### Critical Notes for Phase 3
- Must preserve `validate_data_with_hierarchical_routing()` 
- Delete deprecated validation functions only
- Create extensive tests before and after
- Document ALL function call sites before removal

### Handoff
- Branch: $(git branch --show-current)
- Commit: $(git rev-parse --short HEAD)
- Ready for: Phase 3 (HIGH RISK - proceed carefully)
```

---

## ⚠️ **Phase 3: Validation Function Consolidation (HIGH RISK)**

### Agent Context Loading Instructions

```bash
# AGENT TASK 3: Validation Function Consolidation
# ⚠️  HIGH RISK PHASE - Touching core validation logic

# Step 1: Load context and verify prerequisites
echo "=== PHASE 3: HIGH RISK - Loading Context ===" 

cat REFACTORING_PLAN.md | tail -100

# Verify Phases 1-2 are complete
if ! grep -q "Phase 2 Complete" REFACTORING_PLAN.md; then
    echo "ERROR: Phase 2 not complete. Cannot proceed."
    exit 1
fi

# Step 2: Create Phase 3 working directory with extensive backups
mkdir -p .refactor-work/phase3
mkdir -p .refactor-work/phase3/backups

# Backup the entire report_pipeline.py
cp src/pipeline/reports/report_pipeline.py .refactor-work/phase3/backups/report_pipeline.py.original

# Create detailed checkpoint
git add -A
git commit -m "Checkpoint: Before Phase 3 (validation consolidation)"
git tag phase3-checkpoint-$(date +%Y%m%d-%H%M%S)

echo "✓ Backups created. Ready for Phase 3 analysis."
```

### Step 3.1: Comprehensive Function Analysis

```bash
echo "=== PHASE 3.1: Analyzing Validation Functions ===" 

# Use function analyzer skill
cat > .refactor-work/phase3/analyze-validations.py << 'EOF'
#!/usr/bin/env python3
"""
Comprehensive analysis of all validation functions in report_pipeline.py
"""

import ast
import re
from pathlib import Path
from collections import defaultdict

def extract_function_info(filepath):
    """Extract all function definitions with line numbers and docstrings."""
    content = Path(filepath).read_text()
    tree = ast.parse(content)
    
    functions = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if 'validat' in node.name.lower():
                func_info = {
                    'name': node.name,
                    'line_start': node.lineno,
                    'line_end': node.end_lineno,
                    'docstring': ast.get_docstring(node) or '',
                    'args': [arg.arg for arg in node.args.args],
                    'decorators': [d.id if isinstance(d, ast.Name) else str(d) for d in node.decorator_list]
                }
                functions.append(func_info)
    
    return functions

def find_function_calls(filepath, function_name):
    """Find all locations where a function is called."""
    content = Path(filepath).read_text()
    lines = content.split('\n')
    
    calls = []
    for i, line in enumerate(lines, 1):
        if f'{function_name}(' in line and not line.strip().startswith('#'):
            calls.append({
                'line': i,
                'content': line.strip(),
                'context': lines[max(0, i-2):min(len(lines), i+2)]
            })
    
    return calls

# Analyze report_pipeline.py
filepath = 'src/pipeline/reports/report_pipeline.py'
functions = extract_function_info(filepath)

print("="*80)
print("VALIDATION FUNCTIONS FOUND")
print("="*80)

for func in functions:
    print(f"\n{'='*80}")
    print(f"Function: {func['name']}")
    print(f"Lines: {func['line_start']}-{func['line_end']} ({func['line_end'] - func['line_start'] + 1} lines)")
    print(f"Arguments: {', '.join(func['args'])}")
    
    if func['docstring']:
        print(f"\nDocstring (first 200 chars):")
        print(func['docstring'][:200] + "..." if len(func['docstring']) > 200 else func['docstring'])
    
    # Find where this function is called
    calls = find_function_calls(filepath, func['name'])
    print(f"\nCalled {len(calls)} times in report_pipeline.py:")
    for call in calls[:5]:  # Show first 5 calls
        print(f"  Line {call['line']}: {call['content'][:80]}")
    
    if len(calls) > 5:
        print(f"  ... and {len(calls) - 5} more times")

print("\n" + "="*80)
print("ANALYSIS COMPLETE")
print("="*80)

# Find cross-file calls
print("\n" + "="*80)
print("CROSS-FILE USAGE ANALYSIS")
print("="*80)

import subprocess
for func in functions:
    result = subprocess.run(
        ['grep', '-rn', f"{func['name']}(", 'src/', '--include=*.py'],
        capture_output=True,
        text=True
    )
    
    if result.stdout:
        lines = result.stdout.strip().split('\n')
        # Exclude self-references in report_pipeline.py definitions
        external_calls = [l for l in lines if 'def ' + func['name'] not in l]
        
        if external_calls:
            print(f"\n{func['name']} called from other files:")
            for call in external_calls[:10]:
                print(f"  {call[:100]}")
EOF

python .refactor-work/phase3/analyze-validations.py > .refactor-work/phase3/function-analysis.txt
cat .refactor-work/phase3/function-analysis.txt
```

**Step 3.2: Create Function Dependency Map**

```bash
echo "=== PHASE 3.2: Creating Dependency Map ==="

cat > .refactor-work/phase3/dependency-map.md << 'EOF'
# Validation Function Dependency Map

## Functions Identified

### 1. validate_data()
- **Status**: [KEEP / DELETE / MODIFY]
- **Lines**: [X-Y]
- **Calls**: [List functions it calls]
- **Called by**: [List call sites]
- **Decision**: [Rationale]

### 2. validate_data_with_hierarchical_routing()
- **Status**: KEEP (Production implementation)
- **Lines**: [X-Y]
- **Calls**: [List functions it calls]
- **Called by**: [List call sites]
- **Decision**: This is the ONLY production validation implementation

### 3. validate_data_with_packet_routing()
- **Status**: [KEEP / DELETE / MODIFY]
- **Lines**: [X-Y]
- **Calls**: [List functions it calls]
- **Called by**: [List call sites]
- **Decision**: [Rationale]

### 4. _ValidationEngine class
- **Status**: [KEEP / DELETE / MODIFY]
- **Lines**: [X-Y]
- **Methods**: [List all methods]
- **Used by**: [List usage sites]
- **Decision**: [Rationale]

### 5. Helper Functions
List all helper functions like:
- _load_schema_and_rules()
- _get_schema_and_rules_for_record()
- _log_validation_results()

## Removal Plan

### Phase 3.3: Remove [Function Name]
- Verify no external calls
- Update any internal redirects
- Test after removal

### Phase 3.4: Remove [Function Name]
...

## Safety Checklist
- [ ] All external call sites identified
- [ ] Production function preserved
- [ ] Test coverage verified
- [ ] Rollback plan created
EOF

# Now fill in the template manually based on analysis
echo "Review and update .refactor-work/phase3/dependency-map.md before proceeding"
```

**⚠️ MANDATORY STOP - DO NOT PROCEED WITHOUT HUMAN REVIEW**

```markdown
## Phase 3.2 Complete: Analysis and Planning

### STOP - Human Review Required

Before proceeding with any code deletion in Phase 3, the following must be reviewed:

### Analysis Artifacts Created
1. `.refactor-work/phase3/function-analysis.txt` - Complete function inventory
2. `.refactor-work/phase3/dependency-map.md` - Dependency relationships
3. `.refactor-work/phase3/backups/report_pipeline.py.original` - Full backup

### Key Findings
[AI should summarize the analysis here]:
- Total validation functions found: X
- Functions with external callers: Y
- Safe to remove: Z
- Requires refactoring: W

### Recommended Removal Order
Based on dependency analysis:
1. [Function 1] - No dependencies
2. [Function 2] - Internal only
3. [Function 3] - Requires redirect
...

### Critical Decisions Needed
⚠️ Before executing Phase 3.3-3.6 (actual removal):

1. **Confirm** `validate_data_with_hierarchical_routing()` is the production function
2. **Verify** no external packages call deprecated functions
3. **Approve** the removal order
4. **Review** test coverage for validation

### Rollback Plan
- Git tag created: `phase3-checkpoint-[timestamp]`
- Full backup in: `.refactor-work/phase3/backups/`
- Rollback command: `git reset --hard [tag]`

### Next Steps (DO NOT AUTO-EXECUTE)
Wait for human approval, then proceed to Phase 3.3

### Agent Handoff
DO NOT proceed to Phase 3.3 automatically.
Next agent should:
1. Wait for human review of analysis
2. Get explicit approval for removal plan
3. Then execute Phase 3.3 with single function at a time
4. Test after EACH function removal
5. Stop and document after each successful removal
```

---

## 🎯 **Phase 3.3-3.6: Incremental Function Removal (EXECUTE ONLY AFTER APPROVAL)**

### Execution Pattern (Same for Each Function)

```bash
# TEMPLATE FOR EACH FUNCTION REMOVAL
# Replace [FUNCTION_NAME] with actual function name

echo "=== Removing [FUNCTION_NAME] ==="

# Step 1: Create specific backup
cp src/pipeline/reports/report_pipeline.py .refactor-work/phase3/backups/before_removing_[FUNCTION_NAME].py

# Step 2: Extract the function to be removed (for documentation)
python << 'EOF'
import re
from pathlib import Path

content = Path('src/pipeline/reports/report_pipeline.py').read_text()
lines = content.split('\n')

# Find function definition
in_function = False
function_lines = []
indent_level = None

for i, line in enumerate(lines):
    if 'def [FUNCTION_NAME](' in line:
        in_function = True
        indent_level = len(line) - len(line.lstrip())
        function_lines.append((i+1, line))
    elif in_function:
        current_indent = len(line) - len(line.lstrip())
        if line.strip() and current_indent <= indent_level:
            break
        function_lines.append((i+1, line))

# Save to file
with open('.refactor-work/phase3/removed_[FUNCTION_NAME].py', 'w') as f:
    f.write("# Removed from report_pipeline.py\n")
    f.write(f"# Lines: {function_lines[0][0]}-{function_lines[-1][0]}\n\n")
    for line_num, line in function_lines:
        f.write(f"{line}\n")

print(f"Extracted {len(function_lines)} lines to removed_[FUNCTION_NAME].py")
EOF

# Step 3: Remove the function (manual editing required)
# Use your editor to delete the function from report_pipeline.py

# Step 4: Verify syntax
python -m py_compile src/pipeline/reports/report_pipeline.py

# Step 5: Test imports
python << 'EOF'
import sys
sys.path.insert(0, 'src')

try:
    from pipeline.reports.report_pipeline import validate_data_with_hierarchical_routing
    print("✓ Production validation function imports successfully")
except ImportError as e:
    print(f"✗ CRITICAL: Production function import failed: {e}")
    sys.exit(1)

# Try importing the removed function (should fail)
try:
    from pipeline.reports.report_pipeline import [FUNCTION_NAME]
    print(f"⚠️  WARNING: [FUNCTION_NAME] still exists (removal incomplete)")
    sys.exit(1)
except (ImportError, AttributeError):
    print(f"✓ [FUNCTION_NAME] successfully removed")
EOF

# Step 6: Run focused tests
pytest tests/ -v -k "validat" --tb=short -x

# Step 7: Run full test suite
pytest tests/ --tb=short -x

# Step 8: Document this removal
cat >> REFACTORING_PLAN.md << EOF

### Removed: [FUNCTION_NAME]
- **Date**: $(date)
- **Lines removed**: [X-Y] (N lines)
- **Reason**: [Duplicate/Deprecated/Unused]
- **Tests**: ✓ PASS
- **Backup**: .refactor-work/phase3/backups/before_removing_[FUNCTION_NAME].py
EOF

# Step 9: Commit this single change
git add -A
git commit -m "Phase 3.[X]: Remove [FUNCTION_NAME]

- Deprecated [validation/helper] function
- Functionality preserved in validate_data_with_hierarchical_routing()
- All tests passing
- Lines removed: [N]

See REFACTORING_PLAN.md"

git push origin $(git branch --show-current)

echo "✓ [FUNCTION_NAME] removed successfully"
echo "⚠️  STOP - Review before removing next function"
```

### Suggested Removal Sequence (Execute One at a Time)

1. **Phase 3.3**: Remove `_ValidationEngine` class (lowest risk)
2. **Phase 3.4**: Remove `validate_data_with_packet_routing()` (medium risk)  
3. **Phase 3.5**: Remove helper functions (low risk)
4. **Phase 3.6**: Convert `validate_data()` to alias (low risk)

**⚠️ STOP AFTER EACH REMOVAL** - Verify tests pass and document before proceeding.

---

## 📊 **Phase Completion Template**

After completing ALL sub-phases of Phase 3:

```bash
# Final Phase 3 documentation
cat >> REFACTORING_PLAN.md << 'EOF'

## Phase 3 COMPLETE: Validation Function Consolidation

### Date Completed: $(date)

### Summary
Successfully consolidated 4 validation implementations into 1 production function.

### Functions Removed
1. ✅ _ValidationEngine class (~200 lines)
2. ✅ validate_data_with_packet_routing() (~150 lines)
3. ✅ _load_schema_and_rules() helper
4. ✅ validate_data() converted to alias

### Function Preserved
✅ validate_data_with_hierarchical_routing() - Production implementation

### Metrics
- Functions removed: 4
- Lines removed: ~350
- Tests passing: [X/Y]
- No regressions detected

### Cumulative Progress
- Phase 1: -183 lines
- Phase 2: -7 files
- Phase 3: -350 lines
- **Total: -533 lines, -7 files**

### Test Coverage
- Validation tests: ✓ ALL PASS
- Integration tests: ✓ ALL PASS
- Regression tests: ✓ ALL PASS

### Next Phase
Phase 4: Legacy Pipeline Entry Point Removal

### Backups
All removed code preserved in:
- .refactor-work/phase3/backups/
- .refactor-work/phase3/removed_*.py

### Git History
- Checkpoint tag: phase3-checkpoint-[timestamp]
- Individual commits for each removal
- Full rollback capability maintained
EOF

git add -A
git commit -m "Phase 3 COMPLETE: Validation consolidation

Summary:
- Removed 4 duplicate/deprecated validation functions
- Consolidated to single production implementation
- 350+ lines removed
- All tests passing
- Zero regressions

See REFACTORING_PLAN.md for details"

git push origin $(git branch --show-current)
```

**⚠️ MAJOR STOP POINT**

```markdown
## Phase 3 Complete - Major Milestone

### Achievement
✅ Successfully consolidated core validation logic
✅ Removed 350+ lines of duplicate code
✅ Zero regressions
✅ All tests passing

### Current State
- **Total reduction**: 533 lines (13% of target)
- **Phases complete**: 3/7
- **Risk level handled**: HIGH (validation logic)
- **Confidence**: High (extensive testing)

### Cumulative Metrics
| Phase | Lines Removed | Files Deleted | Risk | Status |
|-------|--------------|---------------|------|---------|
| 1 | 183 | 1 | Low | ✅ Complete |
| 2 | 0 | 7 | Low | ✅ Complete |
| 3 | 350 | 0 | HIGH | ✅ Complete |
| **Total** | **533** | **8** | - | **43% to goal** |

### Next Agent Instructions
1. Read REFACTORING_PLAN.md (full file recommended)
2. Review Phase 3 completion notes carefully
3. Understand validation consolidation completed
4. Proceed to Phase 4: Pipeline Entry Point Removal
   - Medium risk (main entry points)
   - Follow same incremental pattern
   - Test after each change

### Ready for Phase 4
- Branch: $(git branch --show-current)
- Latest commit: $(git rev-parse --short HEAD)
- Test status: All passing
- Context preserved: Yes
- Proceed: Yes (when ready)
```

---

## 🔄 **Remaining Phases (Outline Only - Execute Same Pattern)**

### Phase 4: Legacy Pipeline Entry Point Removal
- Remove `run_improved_report_pipeline()`
- Remove `process_instruments_etl()`
- Keep `run_report_pipeline()` as main entry
- **Risk**: Medium
- **Pattern**: Same as Phase 3 (analyze → backup → remove → test → document)

### Phase 5: Result Object Simplification
- Consolidate 7 result dataclasses to 3
- Create `SimpleStageResult` for common cases
- **Risk**: Low-Medium
- **Pattern**: Same incremental approach

### Phase 6: Unused Code Removal
- Remove CerberusCompatibilityAdapter
- Remove ModernSchemaBuilder
- Remove CompatibilityValidator
- **Risk**: Low (unused code)

### Phase 7: Context Object Consolidation
- Merge 5 context dataclasses to 2
- **Risk**: Low-Medium

---

## 📝 **Agent Execution Guidelines**

### For Each Phase, the Agent Must:

1. **Load Context**
   ```bash
   cat REFACTORING_PLAN.md | tail -150
   ```

2. **Verify Prerequisites**
   - Check previous phase is complete
   - Verify tests are passing
   - Confirm git state is clean

3. **Analyze Before Acting**
   - Use `.github/skills/*` tools
   - Create analysis documents
   - Document findings before changes

4. **Make Incremental Changes**
   - One function/file/class at a time
   - Backup before each change
   - Test after each change

5. **Document Everything**
   - Update REFACTORING_PLAN.md
   - Create phase-specific analysis files
   - Commit with detailed messages

6. **Stop and Report**
   - Stop after each phase
   - Provide handoff context
   - Never chain phases automatically

### Critical Rules
- ❌ Never delete code without analysis
- ❌ Never proceed if tests fail
- ❌ Never skip documentation
- ✅ Always backup before changes
- ✅ Always test after changes
- ✅ Always commit incrementally

---

## 🎯 **Success Criteria Tracking**

Create this file: `.refactor-metrics/progress.json`

```json
{
  "target": {
    "lines_to_remove": 1500,
    "percentage": 25
  },
  "phases": {
    "phase1": {
      "complete": true,
      "lines_removed": 183,
      "files_deleted": 1,
      "tests_passing": true
    },
    "phase2": {
      "complete": true,
      "lines_removed": 0,
      "files_deleted": 7,
      "tests_passing": true
    },
    "phase3": {
      "complete": true,
      "lines_removed": 350,
      "files_deleted": 0,
      "tests_passing": true
    }
  },
  "cumulative": {
    "lines_removed": 533,
    "files_deleted": 8,
    "progress_percentage": 35.5,
    "tests_passing": true
  }
}
```

Update after each phase completion.

---

This plan provides a complete framework for iterative, safe, well-documented refactoring with clear stop points and context preservation for agent chaining. Each agent can pick up where the previous one left off by reading `REFACTORING_PLAN.md`.