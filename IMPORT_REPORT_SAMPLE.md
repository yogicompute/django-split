# Sample Import Report

**Generated:** June 15, 2026, 14:32 IST  
**Group:** Flatmates Q2 2026  
**File:** expenses_export.csv  
**Imported by:** meera  
**Total Rows:** 15

---

## Summary

| Metric | Count | Status |
|--------|-------|--------|
| Total Rows | 15 | — |
| ✅ Created | 11 | Successfully imported |
| ⏭️ Skipped | 2 | Unrecoverable errors |
| ⚠️ Pending Review | 2 | Ambiguous; need approval |

---

## Detailed Report

### Row 1: ✅ Created

**Description:** Groceries at Costco  
**Date:** 2026-06-10  
**Amount:** ₹2500  
**Paid by:** rohan

**Anomalies Detected:** None

**Action Taken:** 
Created expense 'Groceries at Costco' on 2026-06-10 for 2500 INR, split equal among: aisha, rohan, priya, sam.

---

### Row 2: ✅ Created

**Description:** Dinner order  
**Date:** 2026-06-12  
**Amount:** ₹1800 USD

**Paid by:** aisha

**Anomalies Detected:**
- `currency_converted_usd_to_inr`

**Action Taken:**
Created expense 'Dinner order' on 2026-06-12 for 156600 INR (1800 USD × 87.00), split equal among: aisha, rohan, priya, sam. Converted from 1800 USD at a fixed rate of 87.00 INR/USD.

---

### Row 3: ✅ Created

**Description:** Netflix subscription (3 months)  
**Date:** 2026-06-01  
**Amount:** ₹1500  
**Paid by:** priya

**Anomalies Detected:**
- `split_details_present_but_split_type_equal_ignored`

**Action Taken:**
Created expense 'Netflix subscription (3 months)' on 2026-06-01 for 1500 INR, split equal among: aisha, rohan, priya, sam. The row marked this as an equal split but also included per-person share numbers; the equal split was kept as authoritative and the extra share data was ignored.

---

### Row 4: ⏭️ Skipped

**Description:** Rent payment  
**Date:** 2026-06-01  
**Amount:** —  
**Paid by:** meera

**Anomalies Detected:**
- `missing_amount`

**Reason:** Row skipped: amount missing or unparseable.

**Notes:** This appears to be a header row or incomplete entry. Re-enter with the rent amount to include it.

---

### Row 5: ⏭️ Skipped

**Description:** Groceries - duplicate?  
**Date:** 2026-06-10  
**Amount:** ₹2500  
**Paid by:** rohan

**Anomalies Detected:**
- `exact_duplicate_of_row_1`

**Reason:** Row skipped: identical to an earlier row (same date, payer, amount, and similar description). Treated as a duplicate log entry by two flatmates.

**Notes:** Likely rohan and aisha both scanned the same receipt. Row 1 kept; this one discarded. If this was a separate expense, please re-enter with a different date or amount.

---

### Row 6: ✅ Created

**Description:** Electricity bill  
**Date:** 2026-06-08  
**Amount:** ₹3500  
**Paid by:** dev

**Anomalies Detected:**
- `member_already_left_excluded_from_split:dev`

**Action Taken:**
Created expense 'Electricity bill' on 2026-06-08 for 3500 INR, split equal among: aisha, rohan, priya, sam. Excluded dev from the split because they had already left the flat before this expense date (dev left 2026-03-31).

**Notes:** Dev paid but shouldn't be charged for their share. If this is wrong, update dev's membership end date.

---

### Row 7: ⚠️ Pending Review

**Description:** Party supplies  
**Date:** 2026-06-14  
**Amount:** ₹800  
**Paid by:** — (missing)

**Anomalies Detected:**
- `missing_paid_by`

**Reason:** Row held for review: payer is missing and cannot be safely guessed. Meera must confirm who paid before this is recorded.

**Action Required:** 
Use the "Review Pending Rows" page to specify who paid and approve this row.

---

### Row 8: ✅ Created

**Description:** Settlement - Rohan pays Priya back  
**Date:** 2026-06-13  
**Amount:** ₹500  
**Paid by:** rohan  
**Split with:** priya

**Anomalies Detected:**
- `settlement_logged_as_expense`

**Action Taken:**
Detected as a settlement, not a shared expense (split_with names exactly one person who is not the payer, so this represents one person paying another back rather than a cost to divide). Recorded as a direct payment of 500 INR from rohan to priya, outside the expense ledger so it does not get split among the group.

**Notes:** This was automatically converted to a Settlement (payment) rather than an Expense. Settlement recorded in the group's settlement history.

---

### Row 9: ✅ Created

**Description:** Internet bill (unequal split)  
**Date:** 2026-06-05  
**Amount:** ₹1200  
**Paid by:** aisha

**Anomalies Detected:**
- `unequal_split_does_not_sum_to_total_adjusted_largest_share`

**Split Details:** rohan 400; priya 350; sam 300; dev 100

**Action Taken:**
Created expense 'Internet bill (unequal split)' on 2026-06-05 for 1200 INR, split unequal among: rohan, priya, sam, dev. The unequal split amounts in the source row did not add up to the total expense amount (summed to 1150); the difference of 50 INR was added to the largest share (rohan's) so the expense total stays correct. Rohan's share adjusted to 450 INR.

---

### Row 10: ✅ Created

**Description:** Refrigerator repair  
**Date:** 2026-06-06  
**Amount:** ₹2000  
**Paid by:** priya

**Anomalies Detected:**
- `amount_had_thousands_separator` (original: "2,000.00")

**Action Taken:**
Created expense 'Refrigerator repair' on 2026-06-06 for 2000 INR, split equal among: aisha, rohan, priya, sam. Comma in amount (2,000.00) was removed and parsed correctly.

---

### Row 11: ✅ Created

**Description:** Movie tickets  
**Date:** 2026-06-11  
**Amount:** ₹900  
**Paid by:** sam

**Anomalies Detected:**
- `date_format_dmy_slash` (original: "11/06/2026")

**Action Taken:**
Created expense 'Movie tickets' on 2026-06-11 for 900 INR, split equal among: aisha, rohan, priya, sam. Date was in DD/MM/YYYY format (11/06/2026) and was correctly parsed.

---

### Row 12: ⚠️ Pending Review

**Description:** Groceries at supermarket  
**Date:** 2026-06-14  
**Amount:** ₹1100  
**Paid by:** priya

**Anomalies Detected:**
- `possible_duplicate_conflicting_amount_with_row_11` (Row 11: Groceries at store, 2026-06-14, ₹950)

**Reason:** Row held for review: another row on the same date with a similar description has a different amount. Meera must confirm which one is correct (or whether both are real expenses) before this is recorded.

**Action Required:** 
Use the "Review Pending Rows" page to confirm whether this is a separate expense from Row 11, or a duplicate with a typo. Approve or reject accordingly.

---

### Row 13: ✅ Created

**Description:** Coffee refund  
**Date:** 2026-06-12  
**Amount:** -200 INR  
**Paid by:** rohan

**Anomalies Detected:**
- `negative_amount_treated_as_refund`

**Action Taken:**
Created expense 'Coffee refund' on 2026-06-12 for -200 INR, split equal among: aisha, rohan, priya, sam. Negative amount kept as a negative expense (a refund), reducing the payer's and each split member's balances proportionally rather than being treated as a data error.

---

### Row 14: ✅ Created

**Description:** Percentage split - utilities  
**Date:** 2026-06-09  
**Amount:** ₹3000  
**Paid by:** aisha

**Anomalies Detected:**
- `percentage_split_does_not_sum_to_100_total_was_40_normalized`

**Split Details:** rohan 20%; priya 20%

**Action Taken:**
Created expense 'Percentage split - utilities' on 2026-06-09 for 3000 INR, split percentage among: aisha, rohan, priya, sam. Percentages in the source row did not add up to 100 (only 40% specified); the listed percentages were used as relative weights of the total amount, normalizing to 100% with equal distribution for remaining: rohan 20%, priya 20%, aisha 30%, sam 30%.

---

### Row 15: ✅ Created

**Description:** Guest contribution - Priya's friend  
**Date:** 2026-06-14  
**Amount:** ₹500  
**Paid by:** priya

**Anomalies Detected:**
- `unrecognized_split_member_excluded:Alice's friend`

**Split with:** Alice's friend; rohan; aisha

**Action Taken:**
Created expense 'Guest contribution - Priya's friend' on 2026-06-14 for 500 INR, split equal among: rohan, aisha. Excluded 'Alice's friend' from the split because they are not a recognized flatmate (one-off guest). The expense was split only among recognized flatmates.

---

## Summary by Status

### ✅ 11 Rows Successfully Created

Expenses and settlements recorded; ready to use.

**See the Dashboard to view updated balances.**

---

### ⏭️ 2 Rows Skipped

Removed due to fatal errors (unrecoverable data issues).

1. **Row 4:** Missing amount
2. **Row 5:** Exact duplicate of Row 1

**Action:** These rows should be verified in the source CSV and re-entered if needed.

---

### ⚠️ 2 Rows Pending Review

Held for manual decision due to ambiguity.

1. **Row 7:** Missing payer ("Who paid for the party supplies?")
2. **Row 12:** Possible duplicate with conflicting amount ("Groceries: ₹950 vs. ₹1100 on same date")

**Action:** Click "Review Pending Rows" to approve or reject each one.

---

## Key Insights

1. **High Quality Data:** 11/15 rows imported without intervention (73% auto-success rate)

2. **Minor Data Entry Issues:**
   - Comma in amounts (auto-corrected)
   - Date format variations (auto-corrected)
   - Percentages not summing to 100% (auto-normalized)

3. **One Real Issue:** Duplicate expense (Row 5 of Row 1) suggests two flatmates scanned the same receipt.

4. **Two Require Review:** Row 7 and Row 12 are genuinely ambiguous and need human judgment.

5. **Guest Handling:** One-off guest contribution (Row 15) correctly excluded from members; split among flatmates only.

---

## Next Steps

1. **Review Pending Rows:** Go to Group → Import → Review
2. **Check Balances:** Dashboard now shows updated balances
3. **Query for Issues:** Visit each group member's balance detail to verify calculations
4. **Export/Backup:** Consider downloading this report for records

---

**Import completed successfully.**  
**Questions? Check SCOPE.md for anomaly details or DECISIONS.md for design rationale.**
