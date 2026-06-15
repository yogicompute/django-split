import csv
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction

from .models import (
    Expense, ExpenseShare, Group, GroupMembership, ImportBatch, ImportRow, Settlement,
)


USD_TO_INR_RATE = Decimal(str(getattr(settings, 'USD_TO_INR_RATE', 87.00)))

NAME_ALIASES = {
    'priya s': 'priya',
    'priya': 'priya',
    'rohan': 'rohan',
    'aisha': 'aisha',
    'meera': 'meera',
    'dev': 'dev',
    'sam': 'sam',
}


def normalize_name(raw_name):
    if raw_name is None:
        return ''
    cleaned = raw_name.strip().lower()
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return NAME_ALIASES.get(cleaned, cleaned)


def normalize_amount(raw_amount):
    if raw_amount is None:
        return None, []
    text = str(raw_amount).strip()
    if text == '':
        return None, ['missing_amount']
    notes = []
    if ',' in text:
        text = text.replace(',', '')
        notes.append('amount_had_thousands_separator')
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None, ['unparseable_amount']
    if value != value.quantize(Decimal('0.01')):
        notes.append('amount_had_excess_decimal_precision')
        value = value.quantize(Decimal('0.01'))
    return value, notes


DATE_FORMATS = [
    ('%Y-%m-%d', 'iso'),
    ('%d/%m/%Y', 'dmy_slash'),
]


def normalize_date(raw_date, default_year=2026):
    text = str(raw_date).strip()
    notes = []

    for fmt, label in DATE_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt).date()
            if label == 'dmy_slash':
                notes.append('date_format_dmy_slash')
            return parsed, notes
        except ValueError:
            continue

    match = re.match(r'^([A-Za-z]{3,})\s+(\d{1,2})$', text)
    if match:
        month_str, day_str = match.groups()
        try:
            parsed = datetime.strptime(f'{month_str} {day_str} {default_year}', '%b %d %Y').date()
            notes.append('date_missing_year_assumed_current_year')
            return parsed, notes
        except ValueError:
            pass

    match = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', text)
    if match:
        a, b, year = (int(x) for x in match.groups())
        if a > 12 and b <= 12:
            try:
                parsed = date(year, b, a)
                notes.append('date_format_dmy_slash')
                return parsed, notes
            except ValueError:
                pass
        elif a <= 12 and b <= 12:
            try:
                parsed = date(year, a, b)
                notes.append('date_ambiguous_dm_assumed_dmy')
                return parsed, notes
            except ValueError:
                pass

    return None, ['unparseable_date']


def parse_split_with(raw_split_with):
    if not raw_split_with:
        return []
    parts = [p.strip() for p in str(raw_split_with).split(';')]
    return [p for p in parts if p]


def parse_split_details(raw_details):
    result = {}
    if not raw_details:
        return result
    parts = [p.strip() for p in str(raw_details).split(';')]
    for part in parts:
        if not part:
            continue
        match = re.match(r'^(.+?)\s+([\d.]+)\s*%?$', part)
        if match:
            name = normalize_name(match.group(1))
            value = match.group(2)
            result[name] = value
    return result


def get_or_create_user(username):
    username = username.lower().strip()
    user, _ = User.objects.get_or_create(
        username=username,
        defaults={'first_name': username.capitalize()}
    )
    if not user.has_usable_password():
        user.set_password('changeme123')
        user.save()
    return user


def ensure_membership(group, user, joined_on, left_on=None):
    existing = GroupMembership.objects.filter(group=group, user=user).order_by('joined_on').first()
    if existing is None:
        GroupMembership.objects.create(group=group, user=user, joined_on=joined_on, left_on=left_on)
        return
    if joined_on < existing.joined_on:
        existing.joined_on = joined_on
        existing.save()


KNOWN_MEMBERSHIP_PLAN = {
    'aisha': (date(2026, 2, 1), None),
    'rohan': (date(2026, 2, 1), None),
    'priya': (date(2026, 2, 1), None),
    'meera': (date(2026, 2, 1), date(2026, 3, 31)),
    'dev': (date(2026, 3, 1), date(2026, 3, 31)),
    'sam': (date(2026, 4, 1), None),
}


def setup_known_memberships(group):
    for name, (joined_on, left_on) in KNOWN_MEMBERSHIP_PLAN.items():
        user = get_or_create_user(name)
        ensure_membership(group, user, joined_on, left_on)


def build_dedup_key(parsed):
    desc = re.sub(r'[^a-z0-9]', '', parsed['description'].lower())
    return (parsed['date'], parsed['paid_by_norm'], desc[:6], str(parsed['amount_inr']))


def build_conflict_key(parsed):
    stopwords = {'at', 'the', 'a', 'an', 'for', 'of', 'dinner', 'lunch', 'order'}
    words = re.findall(r'[a-z0-9]+', parsed['description'].lower())
    significant = [w for w in words if w not in stopwords and len(w) > 2]
    if not significant:
        significant = words
    return (parsed['date'], frozenset(significant))


class ImportResult:
    def __init__(self, batch):
        self.batch = batch
        self.rows = []


def run_import(group, csv_file, user, filename='expenses_export.csv'):
    setup_known_memberships(group)

    batch = ImportBatch.objects.create(group=group, filename=filename, imported_by=user)

    decoded = csv_file.read()
    if isinstance(decoded, bytes):
        decoded = decoded.decode('utf-8-sig')
    reader = csv.DictReader(decoded.splitlines())

    parsed_rows = []
    for idx, raw_row in enumerate(reader, start=1):
        parsed_rows.append((idx, raw_row))

    seen_dedup_keys = {}
    conflict_groups = {}

    prelim = []
    for idx, raw_row in parsed_rows:
        info = preprocess_row(idx, raw_row)
        prelim.append(info)
        if info['amount_inr'] is not None and info['date'] is not None and info['paid_by_norm']:
            dedup_key = build_dedup_key(info)
            if dedup_key in seen_dedup_keys:
                info['anomalies'].append('exact_duplicate_of_row_' + str(seen_dedup_keys[dedup_key]))
                info['is_exact_duplicate'] = True
            else:
                seen_dedup_keys[dedup_key] = idx

        if info['date'] is not None and info['description']:
            ckey = build_conflict_key(info)
            conflict_groups.setdefault(ckey, []).append(idx)

    for info in prelim:
        if info['date'] is not None and info['description']:
            ckey = build_conflict_key(info)
            others = [r for r in conflict_groups.get(ckey, []) if r != info['row_number']]
            if others and not info.get('is_exact_duplicate'):
                for other_idx in others:
                    other = next(r for r in prelim if r['row_number'] == other_idx)
                    if (other['amount_inr'] != info['amount_inr']
                            and not other.get('is_exact_duplicate')
                            and other['amount_inr'] is not None and info['amount_inr'] is not None):
                        info['anomalies'].append('possible_duplicate_conflicting_amount_with_row_' + str(other_idx))

    total = len(prelim)
    rows_created = 0
    rows_skipped = 0
    rows_pending = 0

    with transaction.atomic():
        for info in prelim:
            status, action, extra_anomalies = apply_policy_and_create(group, info, user, batch)
            info['anomalies'].extend(extra_anomalies)
            ImportRow.objects.create(
                batch=batch,
                row_number=info['row_number'],
                raw_data=info['raw_row'],
                status=status,
                anomalies=info['anomalies'],
                action_taken=action,
            )
            if status == 'created':
                rows_created += 1
            elif status == 'skipped':
                rows_skipped += 1
            elif status == 'pending':
                rows_pending += 1

    batch.total_rows = total
    batch.rows_created = rows_created
    batch.rows_skipped = rows_skipped
    batch.rows_pending = rows_pending
    batch.save()

    return batch


def preprocess_row(idx, raw_row):
    anomalies = []

    raw_date = raw_row.get('date', '')
    parsed_date, date_notes = normalize_date(raw_date)
    anomalies.extend(date_notes)

    raw_paid_by = raw_row.get('paid_by', '')
    paid_by_norm = normalize_name(raw_paid_by)

    if raw_paid_by.strip() == '':
        anomalies.append('missing_paid_by')
    elif normalize_name(raw_paid_by) != raw_paid_by.strip().lower():
        anomalies.append('paid_by_name_normalized')

    if raw_paid_by != raw_paid_by.strip():
        anomalies.append('paid_by_had_whitespace')

    raw_amount = raw_row.get('amount', '')
    amount_value, amount_notes = normalize_amount(raw_amount)
    anomalies.extend(amount_notes)

    raw_currency = (raw_row.get('currency') or '').strip().upper()
    if raw_currency == '':
        anomalies.append('missing_currency_assumed_inr')
        raw_currency = 'INR'
    elif raw_currency not in ('INR', 'USD'):
        anomalies.append('unrecognized_currency_assumed_inr')
        raw_currency = 'INR'

    fx_rate = Decimal('1.00')
    amount_inr = amount_value
    if amount_value is not None:
        if raw_currency == 'USD':
            fx_rate = USD_TO_INR_RATE
            amount_inr = (amount_value * fx_rate).quantize(Decimal('0.01'))
            anomalies.append('currency_converted_usd_to_inr')

    is_refund = False
    if amount_value is not None and amount_value < 0:
        is_refund = True
        anomalies.append('negative_amount_treated_as_refund')

    if amount_value is not None and amount_value == 0:
        anomalies.append('zero_amount_expense')

    raw_split_type = (raw_row.get('split_type') or '').strip().lower()
    raw_split_with = raw_row.get('split_with', '')
    raw_split_details = raw_row.get('split_details', '')
    raw_notes = raw_row.get('notes', '')

    split_members_raw = parse_split_with(raw_split_with)
    split_members_norm = [normalize_name(m) for m in split_members_raw]

    is_settlement = False
    if len(split_members_norm) == 1 and split_members_norm[0] != paid_by_norm and split_members_norm[0] in NAME_ALIASES:
        is_settlement = True
        anomalies.append('settlement_logged_as_expense')

    return {
        'row_number': idx,
        'raw_row': raw_row,
        'anomalies': anomalies,
        'date': parsed_date,
        'description': (raw_row.get('description') or '').strip(),
        'paid_by_norm': paid_by_norm,
        'paid_by_raw': raw_paid_by,
        'amount_value': amount_value,
        'amount_inr': amount_inr,
        'original_currency': raw_currency,
        'fx_rate': fx_rate,
        'is_refund': is_refund,
        'split_type': raw_split_type,
        'split_members_norm': split_members_norm,
        'split_details_raw': raw_split_details,
        'split_details_parsed': parse_split_details(raw_split_details),
        'notes': raw_notes,
        'is_settlement': is_settlement,
        'is_exact_duplicate': False,
    }


def apply_policy_and_create(group, info, user, batch):
    anomalies = list(info['anomalies'])

    if 'unparseable_date' in anomalies:
        return 'skipped', 'Row skipped: date could not be parsed in any known format.', []

    if 'unparseable_amount' in anomalies or 'missing_amount' in anomalies:
        return 'skipped', 'Row skipped: amount missing or unparseable.', []

    if any(a.startswith('exact_duplicate_of_row_') for a in anomalies):
        return 'skipped', 'Row skipped: identical to an earlier row (same date, payer, amount, and similar description). Treated as a duplicate log entry by two flatmates.', []

    if 'missing_paid_by' in anomalies:
        return 'pending', 'Row held for review: payer is missing and cannot be safely guessed. Meera must confirm who paid before this is recorded.', []

    if info['is_settlement']:
        return create_settlement_from_row(group, info, user, batch)

    if any(a.startswith('possible_duplicate_conflicting_amount_with_row_') for a in anomalies):
        return 'pending', 'Row held for review: another row on the same date with a similar description has a different amount. Meera must confirm which one is correct (or whether both are real expenses) before this is recorded.', []

    return create_expense_from_row(group, info, user, batch)


def create_settlement_from_row(group, info, user, batch):
    paid_by_user = get_or_create_user(info['paid_by_norm'])
    target_raw = info['split_members_norm'][0] if info['split_members_norm'] else ''
    if not target_raw:
        return 'pending', 'Row held for review: this looks like a settlement (split_with has a single recipient who is not the payer) but no recipient could be determined.', []

    paid_to_user = get_or_create_user(target_raw)

    settlement = Settlement.objects.create(
        group=group,
        paid_by=paid_by_user,
        paid_to=paid_to_user,
        amount_inr=info['amount_inr'],
        date=info['date'],
        notes=info['notes'] or 'Imported from CSV; row had a single recipient in split_with who is not the payer, interpreted as a cash settlement rather than a shared expense.',
        created_by=user,
    )
    settlement.save()

    action = (
        f"Detected as a settlement, not a shared expense (split_with names exactly one person who is not the payer, "
        f"so this represents one person paying another back rather than a cost to divide). "
        f"Recorded as a direct payment of {info['amount_inr']} INR from {info['paid_by_norm']} to {target_raw}, "
        f"outside the expense ledger so it does not get split among the group."
    )
    return 'created', action, []


def create_expense_from_row(group, info, user, batch):
    anomalies = []
    paid_by_user = get_or_create_user(info['paid_by_norm'])

    split_type = info['split_type'] or 'equal'
    if split_type not in ('equal', 'unequal', 'percentage', 'share'):
        split_type = 'equal'
        anomalies.append('unknown_split_type_defaulted_to_equal')

    raw_members = info['split_members_norm']
    valid_members = []
    for raw_name, norm_name in zip(parse_split_with(info['raw_row'].get('split_with', '')), raw_members):
        if "'s friend" in raw_name.lower() or norm_name not in NAME_ALIASES:
            anomalies.append(f'unrecognized_split_member_excluded:{raw_name.strip()}')
            continue
        if norm_name not in valid_members:
            valid_members.append(norm_name)

    if not valid_members:
        return 'pending', 'Row held for review: no recognizable group members in split_with.', anomalies

    plan = KNOWN_MEMBERSHIP_PLAN
    final_members = []
    for name in valid_members:
        joined_on, left_on = plan.get(name, (date(2026, 1, 1), None))
        if info['date'] < joined_on:
            anomalies.append(f'member_not_yet_joined_excluded_from_split:{name}')
            continue
        if left_on is not None and info['date'] > left_on:
            anomalies.append(f'member_already_left_excluded_from_split:{name}')
            continue
        final_members.append(name)

    if not final_members:
        return 'pending', 'Row held for review: after applying membership dates, no valid members remain in the split.', anomalies

    if info['split_type'] == 'equal' and info['split_details_raw']:
        anomalies.append('split_details_present_but_split_type_equal_ignored')

    shares = {}
    amount_inr = info['amount_inr']

    if split_type == 'equal':
        n = len(final_members)
        base = (amount_inr / n).quantize(Decimal('0.01'))
        total_assigned = base * n
        remainder = (amount_inr - total_assigned).quantize(Decimal('0.01'))
        for i, name in enumerate(final_members):
            shares[name] = base + (remainder if i == 0 else Decimal('0.00'))

    elif split_type == 'unequal':
        details = info['split_details_parsed']
        total_specified = Decimal('0.00')
        for name in final_members:
            val = details.get(name)
            if val is None:
                anomalies.append(f'unequal_split_missing_amount_for:{name}')
                val = '0'
            try:
                amt = Decimal(val).quantize(Decimal('0.01'))
            except InvalidOperation:
                amt = Decimal('0.00')
            shares[name] = amt
            total_specified += amt
        diff = (amount_inr - total_specified).quantize(Decimal('0.01'))
        if diff != Decimal('0.00'):
            anomalies.append('unequal_split_does_not_sum_to_total_adjusted_largest_share')
            largest = max(shares, key=lambda k: shares[k])
            shares[largest] = (shares[largest] + diff).quantize(Decimal('0.01'))

    elif split_type == 'percentage':
        details = info['split_details_parsed']
        total_pct = Decimal('0.00')
        raw_pcts = {}
        for name in final_members:
            val = details.get(name)
            if val is None:
                anomalies.append(f'percentage_split_missing_value_for:{name}')
                val = '0'
            try:
                pct = Decimal(val)
            except InvalidOperation:
                pct = Decimal('0.00')
            raw_pcts[name] = pct
            total_pct += pct

        if total_pct != Decimal('100'):
            anomalies.append(f'percentage_split_does_not_sum_to_100_total_was_{total_pct}_normalized')
            if total_pct == Decimal('0.00'):
                n = len(final_members)
                for name in final_members:
                    raw_pcts[name] = Decimal('100') / n
                total_pct = Decimal('100')

        running_total = Decimal('0.00')
        names_sorted = sorted(final_members)
        for i, name in enumerate(names_sorted):
            if i == len(names_sorted) - 1:
                amt = (amount_inr - running_total).quantize(Decimal('0.01'))
            else:
                pct = raw_pcts.get(name, Decimal('0.00'))
                amt = (amount_inr * pct / total_pct).quantize(Decimal('0.01'))
                running_total += amt
            shares[name] = amt

    elif split_type == 'share':
        details = info['split_details_parsed']
        raw_shares = {}
        total_shares = Decimal('0.00')
        for name in final_members:
            val = details.get(name)
            if val is None:
                anomalies.append(f'share_split_missing_value_for:{name}')
                val = '1'
            try:
                s = Decimal(val)
            except InvalidOperation:
                s = Decimal('1')
            raw_shares[name] = s
            total_shares += s

        if total_shares == Decimal('0.00'):
            total_shares = Decimal(len(final_members))
            for name in final_members:
                raw_shares[name] = Decimal('1')

        running_total = Decimal('0.00')
        names_sorted = sorted(final_members)
        for i, name in enumerate(names_sorted):
            if i == len(names_sorted) - 1:
                amt = (amount_inr - running_total).quantize(Decimal('0.01'))
            else:
                s = raw_shares.get(name, Decimal('1'))
                amt = (amount_inr * s / total_shares).quantize(Decimal('0.01'))
                running_total += amt
            shares[name] = amt

    expense = Expense.objects.create(
        group=group,
        description=info['description'],
        paid_by=paid_by_user,
        date=info['date'],
        split_type=split_type,
        amount_inr=amount_inr,
        original_amount=info['amount_value'],
        original_currency=info['original_currency'],
        fx_rate_to_inr=info['fx_rate'],
        notes=info['notes'],
        created_by=user,
        is_refund=info['is_refund'],
    )

    for name, amt in shares.items():
        member_user = get_or_create_user(name)
        ExpenseShare.objects.create(
            expense=expense,
            user=member_user,
            share_amount_inr=amt,
            raw_value=info['split_details_parsed'].get(name, ''),
        )

    action_parts = [f"Created expense '{info['description']}' on {info['date']} for {amount_inr} INR, split {split_type} among: {', '.join(final_members)}."]
    if info['original_currency'] == 'USD':
        action_parts.append(f"Converted from {info['amount_value']} USD at a fixed rate of {info['fx_rate']} INR/USD.")
    if info['is_refund']:
        action_parts.append("Negative amount kept as a negative expense (a refund), reducing the payer's and each split member's balances proportionally rather than being treated as a data error.")
    if any(a.startswith('member_already_left_excluded_from_split:') for a in anomalies):
        excluded = [a.split(':')[1] for a in anomalies if a.startswith('member_already_left_excluded_from_split:')]
        action_parts.append(f"Excluded {', '.join(excluded)} from the split because they had already left the flat before this expense date.")
    if any(a.startswith('member_not_yet_joined_excluded_from_split:') for a in anomalies):
        excluded = [a.split(':')[1] for a in anomalies if a.startswith('member_not_yet_joined_excluded_from_split:')]
        action_parts.append(f"Excluded {', '.join(excluded)} from the split because they had not yet joined the flat on this expense date.")
    if any(a.startswith('unrecognized_split_member_excluded:') for a in anomalies):
        excluded = [a.split(':')[1] for a in anomalies if a.startswith('unrecognized_split_member_excluded:')]
        action_parts.append(f"Excluded {', '.join(excluded)} from the split because they are not a recognized flatmate (one-off guest).")
    if any('percentage_split_does_not_sum_to_100' in a for a in anomalies):
        action_parts.append('Percentages in the source row did not add up to 100; the listed percentages were used as relative weights of the total amount instead, with the last member absorbing the rounding remainder.')
    if 'unequal_split_does_not_sum_to_total_adjusted_largest_share' in anomalies:
        action_parts.append('The unequal split amounts in the source row did not add up to the total expense amount; the difference was added to the largest share so the expense total stays correct.')
    if 'split_details_present_but_split_type_equal_ignored' in anomalies:
        action_parts.append('The row marked this as an equal split but also included per-person share numbers; the equal split was kept as authoritative and the extra share data was ignored.')

    return 'created', ' '.join(action_parts), anomalies