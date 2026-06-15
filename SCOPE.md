# SCOPE.md: Database Schema & Anomaly Detection

## Database Schema

### Overview

The application uses SQLite with Django ORM. Five main data models handle the core functionality:

### 1. **Group Model**
Represents a shared expense group (e.g., flatmates, friend group).

```python
class Group(models.Model):
    name: CharField(max_length=120)           # Group name
    created_by: ForeignKey(User)             # Creator
    created_at: DateTimeField(auto_now_add=True)  # Creation timestamp
```

**Methods:**
- `active_members(on_date=None)` - Get active members on a specific date
- `all_members_ever()` - Get all members who ever joined

---

### 2. **GroupMembership Model**
Links users to groups with join/leave dates.

```python
class GroupMembership(models.Model):
    group: ForeignKey(Group)                  # Which group
    user: ForeignKey(User)                    # Which user
    joined_on: DateField()                    # Join date
    left_on: DateField(null=True, blank=True) # Leave date (null if still member)
    
    unique_together = ('group', 'user', 'joined_on')  # No duplicate memberships
```

**Purpose:** Validates which members should be included in expense splits based on their membership status at the expense date.

---

### 3. **Expense Model**
Represents a shared expense.

```python
class Expense(models.Model):
    group: ForeignKey(Group)                  # Which group
    description: CharField(max_length=255)   # "Dinner", "Groceries", etc.
    paid_by: ForeignKey(User)                # Who paid
    date: DateField()                         # Expense date
    split_type: CharField()                   # 'equal', 'unequal', 'percentage', 'share'
    
    # Amount tracking
    amount_inr: DecimalField(12, 2)          # Amount in INR (calculated)
    original_amount: DecimalField(12, 2)     # Original amount (as provided)
    original_currency: CharField(max_length=10)  # Original currency ('INR', 'USD', etc.)
    fx_rate_to_inr: DecimalField(10, 4)      # Exchange rate used
    
    # Metadata
    notes: TextField(blank=True)              # Optional notes
    created_by: ForeignKey(User)             # Who created this record
    created_at: DateTimeField(auto_now_add=True)
    is_refund: BooleanField(default=False)   # Negative amount treated as refund
    source_import_row: ForeignKey(ImportRow, null=True)  # If imported
```

**Split Types:**
- `equal` - Divide evenly among members
- `unequal` - Specify exact amount per person
- `percentage` - Specify percentage per person
- `share` - Specify shares (e.g., 2 shares vs 1 share)

---

### 4. **ExpenseShare Model**
Records how an expense is split among members.

```python
class ExpenseShare(models.Model):
    expense: ForeignKey(Expense)              # Which expense
    user: ForeignKey(User)                    # Which user's share
    share_amount_inr: DecimalField(12, 2)     # Amount they owe in INR
    raw_value: CharField(max_length=50)       # Original value from split_details
    
    unique_together = ('expense', 'user')     # One share per person per expense
```

**Purpose:** Denormalizes share calculations for fast balance queries. Enables answering "How much does Alice owe for Expense X?" in O(1) time.

---

### 5. **Settlement Model**
Represents direct cash payments between members (not expenses, but balance settlements).

```python
class Settlement(models.Model):
    group: ForeignKey(Group)                  # Which group
    paid_by: ForeignKey(User)                # Who paid
    paid_to: ForeignKey(User)                # Who received
    amount_inr: DecimalField(12, 2)          # Amount in INR
    date: DateField()                         # Payment date
    notes: TextField(blank=True)              # Optional notes
    created_by: ForeignKey(User)             # Who recorded this
    created_at: DateTimeField(auto_now_add=True)
    source_import_row: ForeignKey(ImportRow, null=True)  # If imported
```

**Purpose:** Tracks "Alice paid Bob ₹500" transactions that settle balances. Distinct from Expenses because settlements don't get split—they're direct transfers.

---

### 6. **ImportBatch Model**
Tracks a CSV import session.

```python
class ImportBatch(models.Model):
    group: ForeignKey(Group)                  # Which group
    filename: CharField(max_length=255)       # Original filename
    imported_by: ForeignKey(User)             # Who imported
    imported_at: DateTimeField(auto_now_add=True)
    
    # Counters
    total_rows: IntegerField()                # Total CSV rows processed
    rows_created: IntegerField()              # Rows successfully created
    rows_skipped: IntegerField()              # Rows rejected (fatal errors)
    rows_pending: IntegerField()              # Rows awaiting manual review
```

---

### 7. **ImportRow Model**
Detailed record of a single CSV row processing.

```python
class ImportRow(models.Model):
    batch: ForeignKey(ImportBatch)            # Which import batch
    row_number: IntegerField()                # Row # in CSV (1-indexed)
    raw_data: JSONField()                     # Original CSV row (all columns)
    status: CharField()                       # 'created', 'skipped', 'pending', 'approved', 'rejected'
    anomalies: JSONField(default=list)        # List of anomaly codes detected
    action_taken: TextField()                 # Description of what was done
    reviewed_by: ForeignKey(User, null=True)  # Who reviewed (if pending → approved/rejected)
    reviewed_at: DateTimeField(null=True)     # When reviewed
```

---

## Anomaly Detection Log

The importer detects 40+ types of anomalies during CSV processing. Each is a code that appears in the `anomalies` list.

### Date Anomalies

| Code | Meaning | Handling |
|------|---------|----------|
| `unparseable_date` | Date couldn't be parsed in any known format | **SKIP ROW** (fatal) |
| `date_format_iso` | Date in ISO format (YYYY-MM-DD) | Auto-corrected |
| `date_format_dmy_slash` | Date in DD/MM/YYYY format | Auto-corrected |
| `date_missing_year_assumed_current_year` | Date like "June 15" without year | Assumed 2026 |
| `date_ambiguous_dm_assumed_dmy` | Date like "06/05/2026" (DD or MM first?) | Assumed DD/MM |

### Amount Anomalies

| Code | Meaning | Handling |
|------|---------|----------|
| `missing_amount` | Amount field is empty | **SKIP ROW** (fatal) |
| `unparseable_amount` | Amount couldn't be parsed as a number | **SKIP ROW** (fatal) |
| `amount_had_thousands_separator` | Amount like "1,000.50" | Comma removed |
| `amount_had_excess_decimal_precision` | Amount like "500.123" (3+ decimals) | Rounded to 2 decimals |
| `zero_amount_expense` | Amount is 0.00 | **HOLD FOR REVIEW** (warning) |

### Currency Anomalies

| Code | Meaning | Handling |
|------|---------|----------|
| `missing_currency_assumed_inr` | Currency field empty | Assumed INR |
| `unrecognized_currency_assumed_inr` | Currency like "EUR" or "GBP" | Assumed INR (user might notice wrong total) |
| `currency_converted_usd_to_inr` | USD detected and converted | Converted at fixed rate (87.00) |

### Payer Anomalies

| Code | Meaning | Handling |
|------|---------|----------|
| `missing_paid_by` | Payer field empty | **HOLD FOR REVIEW** (need human to confirm) |
| `paid_by_had_whitespace` | Payer like " priya " (extra spaces) | Stripped automatically |
| `paid_by_name_normalized` | Payer alias normalized (e.g., "Priya S" → "priya") | Auto-corrected |

### Refund Handling

| Code | Meaning | Handling |
|------|---------|----------|
| `negative_amount_treated_as_refund` | Amount is negative (e.g., -500) | Recorded as refund with `is_refund=True` |

### Settlement Detection

| Code | Meaning | Handling |
|------|---------|----------|
| `settlement_logged_as_expense` | Split has 1 person (not payer) | **CONVERT TO SETTLEMENT** not expense |

### Duplicate Detection

| Code | Meaning | Handling |
|------|---------|----------|
| `exact_duplicate_of_row_N` | Identical to row N (same date, payer, amount, similar desc) | **SKIP ROW** (assumed duplicate log entry) |
| `possible_duplicate_conflicting_amount_with_row_N` | Similar desc & date but different amount than row N | **HOLD FOR REVIEW** (which is right?) |

### Split Type Anomalies

| Code | Meaning | Handling |
|------|---------|----------|
| `unknown_split_type_defaulted_to_equal` | Split type not recognized | Default to 'equal' |
| `split_details_present_but_split_type_equal_ignored` | Equal split specified but split_details also given | Ignored split_details |

### Split Member Anomalies

| Code | Meaning | Handling |
|------|---------|----------|
| `unrecognized_split_member_excluded:NAME` | Member "NAME" not in known aliases | **EXCLUDE FROM SPLIT** (treat as guest) |
| `member_not_yet_joined_excluded_from_split:NAME` | NAME hadn't joined on expense date | **EXCLUDE FROM SPLIT** |
| `member_already_left_excluded_from_split:NAME` | NAME had left before expense date | **EXCLUDE FROM SPLIT** |

### Split Amount Anomalies

| Code | Meaning | Handling |
|------|---------|----------|
| `unequal_split_missing_amount_for:NAME` | Unequal split but no amount for NAME | Set to 0, note discrepancy |
| `unequal_split_does_not_sum_to_total_adjusted_largest_share` | Unequal amounts don't add up to total | Add remainder to largest share |
| `percentage_split_missing_value_for:NAME` | Percentage split missing value for NAME | Set to 0%, recalculate |
| `percentage_split_does_not_sum_to_100_total_was_X_normalized` | Percentages don't sum to 100% | Treat as relative weights |
| `share_split_missing_value_for:NAME` | Share split missing value for NAME | Set to 1 share |

### No Valid Members

| Code | Meaning | Handling |
|------|---------|----------|
| `no_recognizable_members_in_split_with` | Split with no known members | **HOLD FOR REVIEW** |
| `after_membership_dates_no_members_remain` | After excluding by dates, nobody left | **HOLD FOR REVIEW** |

---

## Anomaly Severity Levels

### 🔴 **FATAL** (Row is Skipped)
- `unparseable_date`
- `missing_amount` or `unparseable_amount`
- `exact_duplicate_of_row_N` (duplicate)

**Reason:** Data is corrupted or invalid; no safe way to interpret it.

### 🟡 **HOLD** (Row Pending Human Review)
- `missing_paid_by` (who paid is unknown)
- `possible_duplicate_conflicting_amount_with_row_N` (conflicting info)
- Zero amount or no valid members after filtering
- Settlement with no recipient

**Reason:** System could guess, but it's ambiguous enough that a human should verify.

### 🟢 **AUTO-FIX** (Row is Created with Adjustments)
- All other anomalies (date format, currency conversion, name normalization, rounding, membership date filtering, etc.)

**Reason:** Clear intent evident; applying reasonable defaults is safe.

---

## Known Membership Plan

Hard-coded in `importer.py`:

```python
KNOWN_MEMBERSHIP_PLAN = {
    'aisha': (2026-02-01, None),              # Joined Feb 1, never left
    'rohan': (2026-02-01, None),              # Joined Feb 1, never left
    'priya': (2026-02-01, None),              # Joined Feb 1, never left
    'meera': (2026-02-01, 2026-03-31),        # Joined Feb 1, left Mar 31
    'dev': (2026-03-01, 2026-03-31),          # Joined Mar 1, left Mar 31
    'sam': (2026-04-01, None),                # Joined Apr 1, never left
}
```

**Use:** When a member appears in `split_with` but has left (or not yet joined) on the expense date, they're automatically excluded from the split.

---

## Name Aliases

The `NAME_ALIASES` dictionary normalizes names:

```python
NAME_ALIASES = {
    'priya s': 'priya',       # "Priya S" becomes "priya"
    'priya': 'priya',
    'rohan': 'rohan',
    'aisha': 'aisha',
    'meera': 'meera',
    'dev': 'dev',
    'sam': 'sam',
}
```

Any unrecognized name (e.g., "alice_friend", "guest_aman") is treated as a non-member and excluded.

---

## Deduplication Strategy

### Exact Duplicates
A row is marked `exact_duplicate_of_row_N` if:
- Same date
- Same normalized payer name
- Same amount (to 2 decimals)
- Description has same first 6 characters (after stripping non-alphanumeric)

**Example:**
```
Row 5:  2026-06-15, "Dinner with team", priya, 1200 INR
Row 12: 2026-06-15, "Dinner at restaurant", priya, 1200 INR
```
Both reference first 6 chars of desc, same date/payer/amount → likely duplicate log entry by two flatmates.

### Possible Duplicates
A row is flagged `possible_duplicate_conflicting_amount_with_row_N` if:
- Same date
- Description has significant word overlap (excluding stopwords like "the", "at", "a")
- BUT amounts differ

**Example:**
```
Row 3:  2026-06-20, "Costco grocery run", rohan, 2500 INR
Row 8:  2026-06-20, "Costco groceries", rohan, 3200 INR
```
Same date/payer/description words but different amounts → **held for review**.

---

## Currency Conversion

**Fixed Rate:** 87.00 INR per USD (configurable in settings.py)

When a row has `currency: USD`:
1. `fx_rate_to_inr` set to 87.00
2. `amount_inr` = `original_amount` × 87.00, rounded to 2 decimals
3. Anomaly logged: `currency_converted_usd_to_inr`

**Note:** Fixed rate is static to ensure reproducibility. In production, consider fetching live rates.

---

## Refund Handling

When `amount` is negative (e.g., -500):
1. Record created with `is_refund = True`
2. `amount_inr` stored as negative
3. Splits also computed with negative amounts
4. Anomaly logged: `negative_amount_treated_as_refund`

**Effect:** Negative expenses reduce the payer's balance (they're refunding instead of spending).

---

## Split Calculation Logic

### Equal Split
Amount divided evenly, with remainder assigned to first member.

```python
n = len(final_members)
base = amount_inr / n (rounded to 2 decimals)
Each member gets: base
First member gets: base + remainder
```

### Unequal Split
Per-person amounts specified in `split_details`.

If amounts don't sum to total:
- Calculate difference
- Add difference to largest share

### Percentage Split
Per-person percentages specified in `split_details`.

If percentages don't sum to 100%:
- Treat as relative weights
- Normalize to 100%
- Calculate amounts

If all percentages are 0%:
- Treat as equal split (100% / n per person)

### Share-based Split
Per-person shares specified (e.g., 2 shares, 1 share, 1 share).

If any shares are missing:
- Default to 1 share
- Recalculate

If all shares sum to 0:
- Default all to 1 share

Total allocated: `amount_inr * (share / total_shares)`

---

## Data Validation Rules

1. **Date Validation**
   - Must be parseable in ISO (YYYY-MM-DD) or DD/MM/YYYY format
   - Falls back to "Month Day" parsing (assumed current year)

2. **Amount Validation**
   - Must be numeric (decimals allowed)
   - Rounded to 2 decimal places
   - Negative amounts valid (refunds)

3. **Payer Validation**
   - Must not be empty
   - Normalized to lowercase
   - Matched against NAME_ALIASES

4. **Member Validation**
   - Names in `split_with` normalized and checked
   - Unrecognized names excluded
   - Membership dates checked (must be active on expense date)

5. **Amount Distribution**
   - All shares must sum to total amount (within rounding tolerance)
   - Adjusted automatically if needed

6. **Duplicate Detection**
   - Exact duplicates skipped
   - Possible duplicates held for review

---

## Related Files

- [DECISIONS.md](DECISIONS.md) - Design decisions that led to this schema
- [AI_USAGE.md](AI_USAGE.md) - How AI was used to build this logic
- [README.md](README.md) - Usage and setup guide

---

**Last Updated:** June 15, 2026
