# AI_USAGE.md: AI Development & Errors

This document logs the use of AI tools during development, key prompts, and cases where the AI produced incorrect code and how it was caught and fixed.

---

## AI Tools Used

### Primary Tool: GitHub Copilot (Claude Haiku 4.5)

- **Model:** Claude Haiku 4.5 (as declared)
- **Role:** Code generation, architecture suggestions, template creation
- **Trigger:** Code comments, partial code, natural language requests
- **Integration:** VS Code IDE

---

## Key Development Phases & AI Usage

### Phase 1: Django Project Setup

**Prompt:** "Create a Django project structure for expense splitting with Group, Expense, and User models"

**AI Output:** Generated `models.py` with initial schema

**Issues Caught:** 
- ✅ Models were correct, but decimal field precision not specified
- 🔧 Fixed: Changed `DecimalField()` to `DecimalField(max_digits=12, decimal_places=2)`

---

### Phase 2: CSV Import Logic (Most Complex Component)

**Prompt:** "Write an importer for CSV with these columns: date, description, paid_by, amount, currency, split_type, split_with, split_details. Handle anomalies like duplicate detection, date format variations, and currency conversion."

**AI Output:** Complete `importer.py` with 600+ lines

**Issues Caught:** (See details below)

---

### Phase 3: Balance Calculation

**Prompt:** "Create a balance calculation function that sums all expenses and settlements to determine if a user owes or is owed money in a group"

**AI Output:** `balances.py` with balance calculation logic

**Issues Caught:** ✅ Correct logic, but UI didn't format negative numbers clearly

---

### Phase 4: Views & Templates

**Prompt:** "Create Django views for group detail, expense creation, and import workflow"

**AI Output:** All views and template structure

**Issues Caught:** ✅ No major issues; templates were functional

---

## Case Studies: AI Errors & Corrections

### Case 1: ❌ UNEQUAL SPLIT ROUNDING ERROR

**Situation:**
An unequal split didn't account for rounding properly. If expense is ₹1000 and split unequal as [₹333.33, ₹333.33, ₹333.34], the total should equal ₹1000, not ₹999.90.

**AI's Code:**
```python
# WRONG: Doesn't handle remainder
for name in final_members:
    shares[name] = (amount_inr / len(final_members)).quantize(Decimal('0.01'))
```

**Problem Found:**
During import of sample CSV, a 3-way split of ₹1000 resulted in [₹333.33, ₹333.33, ₹333.33] = ₹999.99. Balance calculated was off by ₹0.01.

**How Caught:**
1. Manual calculation of balances in test case
2. Noticed sum didn't match total expense
3. Realized each person was charged ₹333.33 but total needed ₹1000

**Fix:**
```python
# CORRECT: Add remainder to first person
n = len(final_members)
base = (amount_inr / n).quantize(Decimal('0.01'))
total_assigned = base * n
remainder = (amount_inr - total_assigned).quantize(Decimal('0.01'))

for i, name in enumerate(final_members):
    shares[name] = base + (remainder if i == 0 else Decimal('0.00'))
```

**Result:** ✅ Now correctly distributes remainder to first member; total always matches input amount.

---

### Case 2: ❌ PERCENTAGE NORMALIZATION LOGIC

**Situation:**
CSV has percentage split: rohan 30%, aisha 30%, dev 20% (totals 80%, not 100%). AI should normalize these as relative weights.

**AI's Code:**
```python
# WRONG: Divides by percentages exactly, not treating as weights
for name in final_members:
    pct = raw_pcts[name]
    amt = (amount_inr * pct / Decimal('100')).quantize(Decimal('0.01'))
    shares[name] = amt
```

**Problem Found:**
Importing a ₹1000 expense with percentages [30, 30, 20] resulted in shares [₹300, ₹300, ₹200] = ₹800 total. Missing ₹200!

**How Caught:**
1. ImportRow showed anomaly: `percentage_split_does_not_sum_to_100_total_was_80_normalized`
2. Expense still created, but balance was wrong (₹200 vanished)
3. Noticed created expense sum ≠ input amount

**Fix:**
```python
# CORRECT: Treat as relative weights; divide by actual total percentage
if total_pct != Decimal('100'):
    anomalies.append(f'percentage_split_does_not_sum_to_100_total_was_{total_pct}_normalized')
    # Normalize the percentages
    for name in final_members:
        raw_pcts[name] = (raw_pcts[name] / total_pct * Decimal('100')).quantize(Decimal('0.01'))
```

**Result:** ✅ Now treats [30, 30, 20] as relative weights (30:30:20 = 3:3:2), so shares become [₹375, ₹375, ₹250].

---

### Case 3: ❌ MEMBERSHIP DATE EXCLUSION (LOGIC ERROR)

**Situation:**
Meera left on 2026-03-31. An expense on 2026-03-31 should include Meera. An expense on 2026-04-01 should exclude her.

**AI's Code:**
```python
# WRONG: Excludes on left_on date (should exclude AFTER)
if left_on is not None and info['date'] >= left_on:  # WRONG: >= should be >
    anomalies.append(f'member_already_left_excluded_from_split:{name}')
    continue
```

**Problem Found:**
Created expenses on 2026-03-31 with Meera excluded. But Meera didn't leave until end of day 2026-03-31, so should be included.

**How Caught:**
1. User said, "Meera paid for drinks on March 31st, but she's not in the split."
2. Checked membership: `left_on = 2026-03-31`
3. Checked condition: `info['date'] = 2026-03-31`, `left_on = 2026-03-31`, so `2026-03-31 >= 2026-03-31` is True → excluded

**Fix:**
```python
# CORRECT: Exclude if date is AFTER left_on
if left_on is not None and info['date'] > left_on:  # > instead of >=
    anomalies.append(f'member_already_left_excluded_from_split:{name}')
    continue
```

**Result:** ✅ Now correctly includes member on their last day; excludes only from the day after.

---

## AI Strengths (What It Did Well)

### 1. **Boilerplate Code**
✅ Generated correct Django models, views, URL routing, forms

### 2. **Template Structure**
✅ Created functional HTML templates with Django tags; styling was adequate

### 3. **Anomaly Category Lists**
✅ Comprehensive list of ~40 anomaly types; naming conventions consistent

### 4. **Error Messages**
✅ User-friendly error descriptions in anomaly actions

### 5. **Code Organization**
✅ Logical function breakdown (normalize_date, normalize_amount, parse_split_with, etc.)

---

## AI Limitations (What Required Human Fix)

### 1. **Decimal Precision**
❌ AI used `DecimalField()` without parameters (field was too small)
✅ Manually specified `max_digits=12, decimal_places=2`

### 2. **Rounding Logic**
❌ Didn't account for remainders in split calculations
✅ Manually added logic to assign remainder to first member

### 3. **Date Boundary Conditions**
❌ Off-by-one error in membership date checks (`>=` vs `>`)
✅ Manually corrected comparison operator

### 4. **Percentage Normalization**
❌ Treated percentages as absolute, not relative weights
✅ Manually added normalization when sum ≠ 100%

### 5. **Edge Cases**
❌ Didn't handle all edge cases (negative amounts, zero amounts, empty splits)
✅ Manually added checks for all edge cases

### 6. **Testing**
❌ AI generated code without unit tests
✅ Manually created test imports with edge cases

---

## Patterns in AI Errors

1. **Off-by-One:** Boundary conditions often off by one (> vs >=, <= vs <)
2. **Rounding:** Didn't think about remainders, rounding errors accumulating
3. **Edge Cases:** Happy path worked; edge cases not covered (negative, zero, empty)
4. **Precision:** Numeric precision issues (decimal places, significant figures)
5. **Business Logic:** Complex financial logic needed human validation

---

## Verification Strategy Used

### For Each Module:

1. **Read Generated Code:** Check for obvious issues
2. **Create Test Cases:** Edge cases, boundary conditions
3. **Run Import:** Process test CSV with various anomalies
4. **Inspect Results:** Check database for correctness
5. **Manual Calculation:** Verify balances by hand
6. **User Testing:** Have flatmate test end-to-end

### For Financial Calculations Specifically:

- ✅ Verify: (Paid by person A) - (Sum of splits) = Balance
- ✅ Verify: Sum of all individual balances = 0 (balanced system)
- ✅ Verify: No amount lost or duplicated (conservation of money)

---

## Prompts That Worked Best

### 1. ✅ **Specific, Example-Based**
**Prompt:** "Create a function that normalizes dates in these formats: YYYY-MM-DD or DD/MM/YYYY. Example: '2026-06-15' → 2026-06-15, '15/06/2026' → 2026-06-15. Return (date, anomalies_list)."
**Result:** Very accurate; AI understood exactly what to parse and how.

### 2. ✅ **With Decision Trees**
**Prompt:** "When importing a CSV row, apply this policy: If date unparseable, SKIP. If payer missing, HOLD. Otherwise, CREATE. Return (status, action_description)."
**Result:** Policy logic clear; AI generated correct branching.

### 3. ✅ **With Table/Matrix**
**Prompt:** "Here's a table of anomalies... [table]. For each, the action is... [actions]. Generate code to implement this."
**Result:** Structured input → structured code; very reliable.

### 4. ❌ **Vague**
**Prompt:** "Handle rounding in expense splits."
**Result:** Incomplete; didn't handle all cases.

### 5. ❌ **Too Much at Once**
**Prompt:** "Write the entire importer from CSV parsing to balance calculation."
**Result:** 600 lines, several bugs; hard to debug.

---

## Recommendations for Future AI-Assisted Development

1. **Break into Small Pieces**
   - Don't ask AI for 500-line modules
   - Ask for 50-line functions, then integrate manually

2. **Use Concrete Examples**
   - Include at least 3 test cases per feature
   - Show expected input/output

3. **Explicit Boundary Conditions**
   - Say "including X date boundary"
   - Mention "if 0, then...", "if empty, then..."

4. **Financial Logic Critical**
   - Never use AI-generated financial code without manual verification
   - Always verify: Sum of balances = 0, no money lost
   - Unit tests mandatory

5. **Decimal vs Float**
   - Always specify Decimal for money (not float)
   - Show precision requirements: "12 digits total, 2 decimal places"

6. **Test-Driven**
   - Generate test cases first
   - Have AI generate code to pass tests

---

## Performance & Reliability

| Component | AI-Generated | Manual Fix | Current Status |
|-----------|---|---|---|
| Models | 100% | 10% precision | ✅ Reliable |
| Views | 95% | 5% validation | ✅ Reliable |
| Importer Logic | 80% | 20% edge cases | ✅ Reliable |
| Balance Calc | 75% | 25% rounding | ✅ Reliable |
| Templates | 90% | 10% styling | ✅ Reliable |
| Tests | 0% | 100% written | ⚠️ Limited coverage |

---

## Overall Assessment

### AI Capability: **Strong for Structure, Weak for Logic**

✅ **Excellent at:**
- Boilerplate (models, views, forms, templates)
- API conventions and Django best practices
- Code organization and naming
- Error handling structure

❌ **Weak at:**
- Financial logic and rounding
- Edge case handling
- Boundary condition testing
- Complex business rules

### Recommendation
**Use AI for rapid prototyping, but mandatory code review for:**
- Financial calculations
- Data validation
- Complex business logic

---

## Time Investment

| Phase | Hours | AI Contribution | Manual Work |
|-------|-------|---|---|
| Models & Setup | 2h | 90% | 10% |
| Views & Forms | 4h | 85% | 15% |
| Importer | 8h | 50% | 50% |
| Balance Calculation | 3h | 40% | 60% |
| Templates & UI | 3h | 80% | 20% |
| Testing & Debugging | 6h | 10% | 90% |
| Documentation | 4h | 5% | 95% |
| **Total** | **30h** | **~50%** | **~50%** |

**Conclusion:** AI accelerated development by ~50%, but careful review and testing were essential.

---

## Future: Hybrid Approach

### For Next Version:

1. **AI-Generated Unit Tests First**
   - AI writes tests based on spec
   - Human refines and adds edge cases
   - AI generates code to pass tests

2. **Staged Review**
   - AI generates code in small chunks
   - Human reviews before merging
   - Automated tests run on every commit

3. **Type Hints Throughout**
   - Better IDE support, less ambiguity
   - AI can generate more accurate code with types

4. **Domain-Specific Examples**
   - Build library of good (and bad) examples
   - Show AI the patterns that worked

---

## Lessons Learned

1. **AI is a Junior Developer:** Fast at routine work, needs experienced review for critical logic
2. **Clarity is Key:** Specific, example-based prompts → better code
3. **Financial Code = High Risk:** Mandatory testing and verification
4. **Hybrid Works:** AI for scaffolding, humans for logic
5. **Documentation Pays:** Writing decisions down helps catch AI mistakes

---

## Conclusion

GitHub Copilot significantly accelerated development, reducing time-to-MVP. The AI excelled at boilerplate and structure but required human oversight for complex financial logic, edge cases, and rounding issues.

**Recommendation:** Continue using AI for rapid prototyping, with mandatory code review for business logic, financial calculations, and data integrity features.

---

**Last Updated:** June 15, 2026  
**Document Status:** Complete  
**Cases Documented:** 3 major errors, all resolved  
**Overall AI Utility:** High (with caveats)
