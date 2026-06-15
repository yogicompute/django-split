from collections import defaultdict
from decimal import Decimal

from .models import Expense, ExpenseShare, Settlement


def compute_group_balances(group):
    net = defaultdict(Decimal)

    expenses = Expense.objects.filter(group=group).prefetch_related('shares__user', 'paid_by')
    for expense in expenses:
        net[expense.paid_by_id] += expense.amount_inr
        for share in expense.shares.all():
            net[share.user_id] -= share.share_amount_inr

    settlements = Settlement.objects.filter(group=group)
    for settlement in settlements:
        net[settlement.paid_by_id] += settlement.amount_inr
        net[settlement.paid_to_id] -= settlement.amount_inr

    return net


def simplify_debts(net_balances, users_by_id):
    creditors = []
    debtors = []
    for user_id, amount in net_balances.items():
        amount = amount.quantize(Decimal('0.01'))
        if amount > Decimal('0.00'):
            creditors.append([user_id, amount])
        elif amount < Decimal('0.00'):
            debtors.append([user_id, -amount])

    creditors.sort(key=lambda x: -x[1])
    debtors.sort(key=lambda x: -x[1])

    transactions = []
    i, j = 0, 0
    while i < len(debtors) and j < len(creditors):
        debtor_id, debt_amt = debtors[i]
        creditor_id, credit_amt = creditors[j]
        settled = min(debt_amt, credit_amt)
        if settled > Decimal('0.00'):
            transactions.append({
                'from_user': users_by_id[debtor_id],
                'to_user': users_by_id[creditor_id],
                'amount': settled,
            })
        debtors[i][1] -= settled
        creditors[j][1] -= settled
        if debtors[i][1] <= Decimal('0.00'):
            i += 1
        if creditors[j][1] <= Decimal('0.00'):
            j += 1

    return transactions


def get_group_balance_summary(group):
    from django.contrib.auth.models import User

    net = compute_group_balances(group)
    member_ids = set(net.keys())
    users_by_id = {u.id: u for u in User.objects.filter(id__in=member_ids)}

    member_balances = []
    for user_id, amount in net.items():
        amount = amount.quantize(Decimal('0.01'))
        if amount == Decimal('0.00'):
            continue
        member_balances.append({
            'user': users_by_id.get(user_id),
            'net': amount,
        })
    member_balances.sort(key=lambda x: -x['net'])

    transactions = simplify_debts(net, users_by_id)

    return {
        'member_balances': member_balances,
        'transactions': transactions,
    }


def get_user_balance_in_group(group, user):
    summary = get_group_balance_summary(group)
    net_for_user = Decimal('0.00')
    for mb in summary['member_balances']:
        if mb['user'] and mb['user'].id == user.id:
            net_for_user = mb['net']
            break

    owed_to_user = []
    owed_by_user = []
    for t in summary['transactions']:
        if t['to_user'].id == user.id:
            owed_to_user.append(t)
        elif t['from_user'].id == user.id:
            owed_by_user.append(t)

    return {
        'net': net_for_user,
        'owed_to_user': owed_to_user,
        'owed_by_user': owed_by_user,
    }


def get_expense_breakdown_for_user(group, user):
    expenses = Expense.objects.filter(group=group, shares__user=user).distinct().order_by('-date')
    rows = []
    for expense in expenses:
        try:
            share = expense.shares.get(user=user)
        except ExpenseShare.DoesNotExist:
            continue
        paid_amount = expense.amount_inr if expense.paid_by_id == user.id else Decimal('0.00')
        rows.append({
            'expense': expense,
            'share_amount': share.share_amount_inr,
            'paid_amount': paid_amount,
            'net_effect': paid_amount - share.share_amount_inr,
        })
    return rows