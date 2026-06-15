# DECISIONS.md: Design & Architecture Decisions

This document logs significant decisions made during the development of the Splitwise app, the options considered, and the rationale.

---

## Decision 1: Framework Choice — Django vs. Flask vs. FastAPI

**Date:** Project Inception  
**Status:** ✅ ACCEPTED

### Problem
Need a web framework to build an expense tracking app with user authentication, database ORM, and CSV import features.

### Options Considered

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| **Django** | Full-featured ORM, built-in auth, admin panel, migrations, Django templates | Heavier, steeper learning curve, convention-over-configuration |  |
| **Flask** | Lightweight, flexible, easy to learn, minimal boilerplate | Need to build/integrate auth, ORM, admin manually | |
| **FastAPI** | Modern async, auto API docs (Swagger), type hints | Overkill for server-rendered app, less mature ecosystem | |

### Decision: **Django**
### Rationale
- CSV import requires robust ORM for complex queries (membership dates, duplicate detection, balance calculation)
- Built-in authentication saves security implementation time
- Django admin panel allows non-technical users to inspect/debug data
- Structured project layout reduces decision fatigue for future contributors
- Mature ecosystem with well-documented patterns

### Trade-offs Accepted
- Heavier framework adds some complexity
- Convention-over-configuration means less flexibility (acceptable for internal tool)

---

## Decision 2: Database — SQLite vs. PostgreSQL vs. MySQL

**Date:** Project Inception  
**Status:** ✅ ACCEPTED

### Problem
Need a persistent data store with ACID guarantees and relational querying.

### Options Considered

| Option | Pros | Cons | Use Case |
|--------|------|------|----------|
| **SQLite** | Zero setup, file-based, Django default, sufficient for small groups | Limited concurrency (flatmate app, not banking) | Single machine, <50 concurrent users |
| **PostgreSQL** | Production-grade, JSONB, full-text search, advanced features | Requires server, setup complexity | High-scale, complex queries |
| **MySQL** | Fast, scalable, popular | Less flexible than Postgres, more setup | Traditional web apps |

### Decision: **SQLite**
### Rationale
- Flatmate expense app: <10 concurrent users typical
- All users in same physical location (shared flat/office)
- Zero deployment overhead—file goes with app
- Easy backup (just copy `.sqlite3` file)
- Django ORM hides implementation details; can migrate later if needed

### Trade-offs Accepted
- Not suitable for global-scale app
- Concurrent writes would block (acceptable for this use case)
- Acceptable risk of single-file database corruption (small data volume)

### Migration Path
Schema designed to work with any Django-supported database. If PostgreSQL needed later: `python manage.py migrate` after switching `DATABASES` setting.

---

## Decision 3: Multi-Currency Handling — Fixed Rate vs. Live API vs. Per-Transaction Rate

**Date:** Development Phase  
**Status:** ✅ ACCEPTED

### Problem
Users in international flats may expense in USD, EUR, GBP, etc. Need consistent conversion to INR for balance calculation.

### Options Considered

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| **Fixed Rate** | Reproducible, no external dependencies, simple | Becomes inaccurate over time | ✅ Current |
| **Live API** | Always up-to-date rates | External dependency, latency, API rate limits | Future |
| **Per-Transaction Rate** | Allow user to specify rate | Adds UI complexity, manual entry error-prone | Not chosen |

### Decision: **Fixed Rate (Configurable)**
### Rationale
- Flatmate app context: most expenses happen within weeks, rate changes minimal
- Simplifies logic and ensures reproducibility (important for debugging)
- Stored in `settings.py` (easy to update): `USD_TO_INR_RATE = 87.00`
- Logged explicitly in anomalies (`currency_converted_usd_to_inr`) so users know rates are fixed

### Trade-offs Accepted
- Inaccuracy if rates fluctuate significantly (acceptable for small amounts, short time periods)
- Manual update required when rates change

### Future Enhancement
Could add:
1. Date-based historical rates (if more accuracy needed)
2. Live API fetch with caching (if global scale)
3. Per-user currency preference (default to INR for Indian users)

---

## Decision 4: Membership Date Validation — Automatic vs. Manual vs. Inferred

**Date:** Development Phase  
**Status:** ✅ ACCEPTED

### Problem
Alice joined the flat on Feb 1. An expense from Jan 20 lists Alice in the split. Should she be charged?

### Options Considered

| Approach | How It Works | Pros | Cons |
|----------|-------------|------|------|
| **Automatic Exclusion** | Hard-code membership dates (KNOWN_MEMBERSHIP_PLAN); exclude if expense outside their date range | Clear, deterministic, no ambiguity | Requires knowing dates in advance |
| **Manual Entry** | User adds/removes members manually via UI before importing | Flexible, visual | Error-prone, tedious for large imports |
| **Inferred from First Expense** | First expense date = join date; last expense date = leave date | Automatic, requires no pre-setup | Circular logic (need correct splits to infer dates) |
| **Prompt Per Row** | For each anomaly, ask user during import | Most flexible | Tedious if 100+ rows |

### Decision: **Automatic Exclusion with Manual Override Option**
### Rationale
- Most flatmates know their join/leave dates
- Hard-coding in `KNOWN_MEMBERSHIP_PLAN` ensures deterministic imports (good for reproducibility, debugging)
- Anomaly logged when member excluded due to dates (auditable)
- Can be updated if dates change

### Implementation
```python
KNOWN_MEMBERSHIP_PLAN = {
    'aisha': (date(2026, 2, 1), None),
    'meera': (date(2026, 2, 1), date(2026, 3, 31)),
    ...
}
```

### Trade-offs Accepted
- Must update `importer.py` if membership changes (not ideal, but acceptable)
- Conservative: excludes members instead of including with risk
- Alternative: could UI to update dates, but adds complexity

---

## Decision 5: Duplicate Detection — Exact Match vs. Fuzzy vs. Manual

**Date:** Development Phase  
**Status:** ✅ ACCEPTED

### Problem
Flatmates often log the same expense twice by accident (both snap photos of receipt). How to detect and handle?

### Options Considered

| Approach | Detection | Pros | Cons |
|----------|-----------|------|------|
| **Exact Match** | Same date + payer + amount + similar description | Fast, zero false positives, clear rules | Misses slight variations (600 vs 599.50) |
| **Fuzzy (Levenshtein)** | String distance < threshold | Catches variations | Expensive to compute, needs threshold tuning |
| **Manual (UI)** | Show user side-by-side potential dupes | Most accurate, user decides | Tedious for large imports |
| **None** | Accept all rows | Simple | Balances corrupted by duplicates |

### Decision: **Two-Tier: Exact Match (Skip) + Fuzzy (Hold for Review)**
### Rationale

**Tier 1: Exact Duplicates (SKIP)**
- Same date + normalized payer + amount + first 6 chars of description
- Skip automatically; log as `exact_duplicate_of_row_N`
- **Rationale:** Extremely unlikely to be coincidental; high confidence

**Tier 2: Possible Duplicates (HOLD)**
- Same date + significant description words
- BUT different amount
- Hold for manual review with anomaly: `possible_duplicate_conflicting_amount_with_row_N`
- **Rationale:** Could be two separate expenses or one duplicate with typo; human should decide

### Implementation
```python
def build_dedup_key(parsed):
    desc = re.sub(r'[^a-z0-9]', '', parsed['description'].lower())
    return (parsed['date'], parsed['paid_by_norm'], desc[:6], str(parsed['amount_inr']))

def build_conflict_key(parsed):
    # Extract significant words (stopwords excluded)
    stopwords = {'at', 'the', 'a', 'an', 'for', 'of', 'dinner', 'lunch', 'order'}
    words = re.findall(r'[a-z0-9]+', parsed['description'].lower())
    significant = [w for w in words if w not in stopwords and len(w) > 2]
    return (parsed['date'], frozenset(significant))
```

### Trade-offs Accepted
- Stopword list is hardcoded (easy to miss context-specific words)
- 6-character description limit might miss subtle differences
- Possible duplicates still require manual review (not fully automated)

---

## Decision 6: Settlement Detection — Automatic vs. Explicit Column vs. Amount Threshold

**Date:** Development Phase  
**Status:** ✅ ACCEPTED

### Problem
Sometimes flatmates just pay each other back (not a shared expense). CSV row: "Alice pays Bob ₹500". Should be a Settlement, not an Expense split 5 ways.

### Options Considered

| Approach | Detection | Pros | Cons |
|----------|-----------|------|------|
| **Automatic** | If split_with has exactly 1 person (who is not payer), it's a settlement | Simple heuristic, no extra column needed | Could misidentify: "Rent - paid to landlord" (1 person) as settlement |
| **Explicit Column** | Add "type" column: "expense" vs "settlement" | Explicit, unambiguous | Requires CSV format change, manual entry |
| **Threshold** | If split_with has 1 person AND amount < some threshold, settlement | More conservative | Arbitrary threshold, still wrong for high-value one-on-one |

### Decision: **Automatic (Single Recipient = Settlement)**
### Rationale
- Flatmate expense context: settlements are typically between two people
- Heuristic: "If payer pays exactly one other person, it's a settlement not a shared cost"
- CSV format stays simple (no new column)
- Logged explicitly in anomalies: `settlement_logged_as_expense` → then converted

### Implementation
```python
is_settlement = False
if len(split_members_norm) == 1 and split_members_norm[0] != paid_by_norm:
    is_settlement = True
    anomalies.append('settlement_logged_as_expense')
```

### Trade-offs Accepted
- False positives possible but unlikely ("Rent" with one recipient unusual)
- Fallback: still creates Expense; user can manually delete and create Settlement

---

## Decision 7: Refund Handling — Separate Table vs. Negative Amount vs. Reverse Transaction

**Date:** Development Phase  
**Status:** ✅ ACCEPTED

### Problem
Alice returned groceries and got ₹200 refund. How to track "negative" expenses?

### Options Considered

| Approach | Mechanism | Pros | Cons |
|----------|-----------|------|------|
| **Separate Table** | Create Refund model, join at query time | Explicit, queryable | Duplicates Expense logic |
| **Negative Amount** | Store amount as -200 in Expense.amount_inr | Simple, minimal schema | Confusing semantics (is -200 a cost or credit?) |
| **Reverse Transaction** | Create opposite transaction on refund date | Explicit, visible in history | Doubles storage, confusing UI |

### Decision: **Negative Amount**
### Rationale
- Minimal schema change (just store negative)
- Splits naturally work with negative amounts
- Balance calculation: Alice paid ₹200 → reduces her owed balance
- Logged in anomalies: `negative_amount_treated_as_refund`
- **Semantics:** "Alice paid -₹200 on groceries" means "refund of ₹200 reduces Alice's share"

### Implementation
```python
if amount_value < 0:
    is_refund = True
    anomalies.append('negative_amount_treated_as_refund')
```

### Trade-offs Accepted
- UI must explicitly show "Refund" badge (can't infer from negative alone)
- Query logic must handle negatives carefully
- Semantic confusion possible (is -₹200 "paid negative" or "refund"?)

**Mitigation:** Always display with emoji and label ("🔄 Refund").

---

## Decision 8: Balance Calculation — Denormalization vs. On-Demand

**Date:** Development Phase  
**Status:** ✅ ACCEPTED (Denormalized)

### Problem
To show "Alice's balance is +₹500", must sum all expenses where Alice paid or was split. For large groups with 1000s of expenses, this query gets slow.

### Options Considered

| Approach | Storage | Calculation | Pros | Cons |
|----------|---------|-------------|------|------|
| **On-Demand** | Just Expense + ExpenseShare | Calculate at query time | Fresh, no sync risk, minimal storage | Slow for large datasets |
| **Denormalized** | Add Balance table, update on each Expense | Pre-calculated, fast queries | Fast UI, simple reports | Sync risks, storage overhead |
| **Materialized View** | Database materialized view | Periodic refresh | Very fast, simple | Database-specific, refresh lag |

### Decision: **Partial Denormalization via ExpenseShare**
### Rationale
- Created `ExpenseShare` table to denormalize "who owes what for this expense"
- This allows balance query: `sum(ExpenseShare.share_amount - Expense.paid_by)` in single pass
- Not a separate Balance table (avoids sync issues)
- Django ORM can still express queries efficiently

### Implementation
**ExpenseShare model:**
```python
class ExpenseShare(models.Model):
    expense = ForeignKey(Expense)
    user = ForeignKey(User)
    share_amount_inr = DecimalField()  # Pre-calculated
```

**Balance calculation:** (from balances.py)
```python
# Sums across all expenses
total_owed = sum of (share_amount for each expense)
total_paid = sum of (amount for expenses where paid_by == user)
balance = total_paid - total_owed
```

### Trade-offs Accepted
- Deletion of an Expense must cascade delete ExpenseShare (handled by ForeignKey)
- Slight denormalization adds one extra table (acceptable)
- Queries more efficient than ad-hoc joins

---

## Decision 9: Split Type Strategy — Flexible Parsing vs. Strict Schema

**Date:** Development Phase  
**Status:** ✅ ACCEPTED (Flexible Parsing)

### Problem
CSV might have split info in many formats:
- "rohan 500; aisha 300" (unequal amounts)
- "rohan 50; aisha 30; dev 20" (percentages, no "%" symbol)
- "rohan 2; aisha 1" (shares, context-dependent)

How to parse without ambiguity?

### Options Considered

| Approach | Format | Parsing | Pros | Cons |
|----------|--------|---------|------|------|
| **Flexible** | CSV has `split_type` column; split_details formatted per type | User specifies type, we parse accordingly | Unambiguous, user in control | Requires format discipline |
| **Auto-Detect** | Infer from context (all < 100 = shares, all < 1 = percents, etc.) | Heuristic-based | Might work, user-friendly | Ambiguous edge cases (50 could be amount or percent) |
| **Separate Columns** | "split_share_rohan", "split_share_aisha", etc. | Explicit columns | Ultra-clear | Bloats CSV, breaks for variable member count |

### Decision: **Flexible with Explicit `split_type`**
### Rationale
- CSV includes `split_type` column: "equal", "unequal", "percentage", "share"
- `split_details` formatted per type (specified in README)
- User responsible for correct format (with validation)
- If format wrong: logged as anomaly, **held for review**

### Implementation
```python
def parse_split_details(raw_details, split_type):
    if split_type == 'unequal':
        # Expect "name amount; name amount"
        result = {'rohan': '500', 'aisha': '300'}
    elif split_type == 'percentage':
        # Expect "name percent; name percent" (or with %)
        result = {'rohan': '50', 'aisha': '30'}
    elif split_type == 'share':
        # Expect "name shares; name shares"
        result = {'rohan': '2', 'aisha': '1'}
    ...
```

### Trade-offs Accepted
- Requires user discipline in CSV format
- Fallback: hold for review if anomalies detected
- Documentation critical (README includes examples)

---

## Decision 10: Permission Model — Flat vs. Admin vs. Role-Based

**Date:** Development Phase  
**Status:** ✅ ACCEPTED (Flat)

### Problem
Should Alice (flatmate) be able to edit/delete Bob's expenses? Who can import CSV?

### Options Considered

| Model | Access Rules | Pros | Cons |
|-------|--------------|------|------|
| **Flat** | All group members can view/edit/delete all group data | Simple, trusting | No accountability, anyone can corrupt data |
| **Admin** | Only group creator/Meera can edit; others only view | Strict, accountable | Single point of failure, curator fatigue |
| **Role-Based** | Roles: Owner, Editor, Viewer; granular permissions | Flexible, auditable | Complex, might be overkill |

### Decision: **Flat (All Members = Editors)**
### Rationale
- Flatmate context: small, trusted group (5-10 people)
- Familiarity reduces necessity for strict permissions
- All members have incentive to keep data honest (their own balances)
- Simpler implementation
- Can add roles later if needed

### Current Implementation
```python
# In views: if user in group.memberships, allow all operations
if user not in group.active_members():
    raise PermissionDenied
```

### Trade-offs Accepted
- No audit trail of who changed what (could add later)
- Accidental deletions not prevented (rely on backups)
- Requires trust among flatmates

### Future: Could enhance with:
1. User roles (Owner, Editor, Viewer)
2. Audit trail (created_by, updated_by, updated_at fields)
3. Soft delete (archive instead of hard delete)

---

## Decision 11: Anomaly Severity — Skip vs. Hold vs. Auto-Correct

**Date:** Development Phase  
**Status:** ✅ ACCEPTED (Three-Tier)

### Problem
Different anomalies warrant different responses:
- `unparseable_date`: Skip (data corrupted)
- `missing_paid_by`: Hold (user must clarify)
- `date_format_dmy_slash`: Auto-correct (clear intent)

Who decides the policy?

### Options Considered

| Approach | Decision Maker | Pros | Cons |
|----------|---|---|---|
| **Hard-Coded** | Developer (in importer.py) | Consistent, predictable | Inflexible for user preferences |
| **Configurable** | Admin UI to set policies | Flexible, user-controlled | Complex UI, maintenance burden |
| **Per-Row** | User reviews each row before creation | Most transparent | Very tedious for 100+ rows |

### Decision: **Hard-Coded (Three-Tier)**

**Tier 1: Auto-Correct** (most anomalies)
- Apply reasonable defaults
- Log the action
- Create expense
- **Rationale:** Clear intent evident; defaults safe

**Tier 2: Hold for Review** (ambiguous cases)
- Missing critical info (payer unknown)
- Conflicting info (duplicate with different amount)
- Can't safely guess
- **Rationale:** Error cost > inconvenience of review

**Tier 3: Skip** (fatal errors)
- Data unparseable (no date, no amount)
- Exact duplicates (likely user error)
- **Rationale:** No safe interpretation possible

### Implementation
```python
def apply_policy_and_create(group, info, user, batch):
    if 'unparseable_date' in anomalies:
        return 'skipped', 'Date could not be parsed', []
    
    if 'missing_paid_by' in anomalies:
        return 'pending', 'Payer is missing; Meera must confirm', []
    
    # All others: auto-correct
    return create_expense_from_row(group, info, user, batch)
```

### Trade-offs Accepted
- Hard-coded policy can't adapt per user
- Mitigation: clearly documented, can be updated if needed

---

## Decision 12: UI Framework — Django Templates vs. React vs. Alpine.js

**Date:** UI Phase  
**Status:** ✅ ACCEPTED (Django Templates)

### Problem
Need views for login, expense dashboard, group detail, import report, etc.

### Options Considered

| Framework | Pros | Cons |
|-----------|------|------|
| **Django Templates** | Server-rendered, simple, built-in | Limited interactivity, no SPA |
| **React** | Component-based, interactive, modern | Learning curve, build tool setup, SPA overhead |
| **Alpine.js** | Lightweight, minimal JS, rapid dev | Limited for complex UIs |

### Decision: **Django Templates with Minimal Custom CSS**
### Rationale
- Flatmate app: forms + tables, limited interactivity
- Server-rendered is sufficient
- No SPA complexity needed
- Django templates integrate seamlessly with ORM
- Rapid development (form rendering, error messages automatic)

### Trade-offs Accepted
- Page reloads on form submit (not ideal but acceptable for this scale)
- Limited real-time updates (not needed)
- Can add Alpine.js later for interactivity (e.g., date picker, live calculation)

---

## Decision 13: Deployment Target — Localhost vs. Cloud vs. Containerized

**Date:** Project Scope  
**Status:** ✅ ACCEPTED (Localhost-First)

### Problem
Where will the app live? How will flatmates access it?

### Options Considered

| Target | Setup | Access | Maintenance | Verdict |
|--------|-------|--------|-------------|---------|
| **Localhost** | Just `python manage.py runserver` | One person's laptop | Depends on uptime | ✅ Current |
| **Cloud (AWS/Azure)** | Server, domain, SSL, monitoring | Global URL, reliable | DevOps overhead | Overkill for now |
| **Docker** | Containerized, easy deploy | Same as cloud | Moderate overhead | Future option |

### Decision: **Localhost-First**
### Rationale
- MVP for testing with flatmate group (5-10 people)
- Easy to run and debug locally
- Can push to cloud later if needed
- No infrastructure cost

### Trade-offs Accepted
- Not accessible when owner's laptop is off
- No automatic backup
- Single machine failure = data loss

### Mitigation
- SQLite file backed up to cloud (Google Drive, etc.)
- Can migrate to cloud with `manage.py dump` + `manage.py load`

### Future: Could add Docker + Railway/Heroku for global access.

---

## Summary of Key Principles

1. **Pragmatic Defaults:** Prefer auto-correcting common issues over blocking the user
2. **Transparency:** Every action logged in anomalies; user knows what was changed
3. **Simplicity First:** Avoid features until needed; complexity added only when justified
4. **Auditability:** Data provenance tracked (who imported, when, what changed)
5. **Small Team:** Assume users are trusted; prioritize ease of use over strict permissions
6. **Reproducibility:** Fixed rates, deterministic logic, testable rules

---

**Last Updated:** June 15, 2026  
**Total Decisions Documented:** 13  
**Status:** Active (Updated as new decisions are made)
