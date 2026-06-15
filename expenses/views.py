from django.shortcuts import render

# Create your views here.
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .balances import get_expense_breakdown_for_user, get_group_balance_summary, get_user_balance_in_group
from .forms import AddMemberForm, CSVImportForm, ExpenseForm, GroupForm, RemoveMemberForm, SettlementForm
from .importer import USD_TO_INR_RATE, get_or_create_user, run_import
from .models import (
    Expense, ExpenseShare, Group, GroupMembership, ImportBatch, ImportRow, Settlement,
)


def home(request):
    return render(request, 'expenses/home.html')


@login_required
def dashboard(request):
    groups = Group.objects.filter(memberships__user=request.user).distinct()
    group_data = []
    for group in groups:
        balance = get_user_balance_in_group(group, request.user)
        group_data.append({'group': group, 'balance': balance})
    return render(request, 'expenses/dashboard.html', {'group_data': group_data})


@login_required
def group_list(request):
    groups = Group.objects.all()
    return render(request, 'expenses/group_list.html', {'groups': groups})


@login_required
def group_create(request):
    if request.method == 'POST':
        form = GroupForm(request.POST)
        if form.is_valid():
            group = form.save(commit=False)
            group.created_by = request.user
            group.save()
            GroupMembership.objects.create(group=group, user=request.user, joined_on=timezone.now().date())
            messages.success(request, f'Group "{group.name}" created.')
            return redirect('expenses:group_detail', pk=group.pk)
    else:
        form = GroupForm()
    return render(request, 'expenses/group_form.html', {'form': form})


@login_required
def group_detail(request, pk):
    group = get_object_or_404(Group, pk=pk)
    summary = get_group_balance_summary(group)
    memberships = group.memberships.select_related('user').order_by('joined_on')
    expenses = Expense.objects.filter(group=group).select_related('paid_by').prefetch_related('shares__user').order_by('-date', '-id')[:50]
    settlements = Settlement.objects.filter(group=group).select_related('paid_by', 'paid_to').order_by('-date')[:20]
    return render(request, 'expenses/group_detail.html', {
        'group': group,
        'summary': summary,
        'memberships': memberships,
        'expenses': expenses,
        'settlements': settlements,
    })


@login_required
def group_members(request, pk):
    group = get_object_or_404(Group, pk=pk)
    memberships = group.memberships.select_related('user').order_by('joined_on')
    add_form = AddMemberForm()
    if request.method == 'POST':
        if 'add_member' in request.POST:
            add_form = AddMemberForm(request.POST)
            if add_form.is_valid():
                username = add_form.cleaned_data['username'].strip().lower()
                joined_on = add_form.cleaned_data['joined_on']
                user = get_or_create_user(username)
                existing = GroupMembership.objects.filter(group=group, user=user, left_on__isnull=True).first()
                if existing:
                    messages.warning(request, f'{user.username} is already an active member.')
                else:
                    GroupMembership.objects.create(group=group, user=user, joined_on=joined_on)
                    messages.success(request, f'{user.username} added to the group from {joined_on}.')
                return redirect('expenses:group_members', pk=group.pk)
        elif 'remove_member' in request.POST:
            membership_id = request.POST.get('membership_id')
            remove_form = RemoveMemberForm(request.POST)
            if remove_form.is_valid():
                membership = get_object_or_404(GroupMembership, pk=membership_id, group=group)
                membership.left_on = remove_form.cleaned_data['left_on']
                membership.save()
                messages.success(request, f'{membership.user.username} marked as left from {membership.left_on}.')
                return redirect('expenses:group_members', pk=group.pk)

    return render(request, 'expenses/group_members.html', {
        'group': group,
        'memberships': memberships,
        'add_form': add_form,
        'remove_form': RemoveMemberForm(),
    })


@login_required
def expense_create(request, pk):
    group = get_object_or_404(Group, pk=pk)
    if request.method == 'POST':
        form = ExpenseForm(request.POST, group=group)
        members_selected = request.POST.getlist('split_members')
        if form.is_valid() and members_selected:
            data = form.cleaned_data
            amount = data['amount']
            currency = data['currency']
            fx_rate = USD_TO_INR_RATE if currency == 'USD' else Decimal('1.00')
            amount_inr = (amount * fx_rate).quantize(Decimal('0.01'))

            expense = Expense.objects.create(
                group=group,
                description=data['description'],
                paid_by=data['paid_by'],
                date=data['date'],
                split_type=data['split_type'],
                amount_inr=amount_inr,
                original_amount=amount,
                original_currency=currency,
                fx_rate_to_inr=fx_rate,
                notes=data['notes'],
                created_by=request.user,
                is_refund=amount < 0,
            )

            member_users = User.objects.filter(id__in=members_selected)
            shares = compute_manual_shares(request, data['split_type'], amount_inr, member_users)
            for user_obj, amt in shares.items():
                ExpenseShare.objects.create(expense=expense, user=user_obj, share_amount_inr=amt)

            messages.success(request, 'Expense added.')
            return redirect('expenses:group_detail', pk=group.pk)
        elif not members_selected:
            messages.error(request, 'Select at least one member to split with.')
    else:
        form = ExpenseForm(group=group, initial={'currency': 'INR', 'split_type': 'equal'})

    members = group.active_members()
    return render(request, 'expenses/expense_form.html', {'form': form, 'group': group, 'members': members})


def compute_manual_shares(request, split_type, amount_inr, member_users):
    shares = {}
    members_list = list(member_users)
    n = len(members_list)
    if n == 0:
        return shares

    if split_type == 'equal':
        base = (amount_inr / n).quantize(Decimal('0.01'))
        total = base * n
        remainder = (amount_inr - total).quantize(Decimal('0.01'))
        for i, u in enumerate(members_list):
            shares[u] = base + (remainder if i == 0 else Decimal('0.00'))

    elif split_type == 'unequal':
        running = Decimal('0.00')
        for u in members_list:
            raw = request.POST.get(f'amount_{u.id}', '0')
            try:
                val = Decimal(raw).quantize(Decimal('0.01'))
            except InvalidOperation:
                val = Decimal('0.00')
            shares[u] = val
            running += val
        diff = (amount_inr - running).quantize(Decimal('0.01'))
        if diff != Decimal('0.00'):
            shares[members_list[0]] += diff

    elif split_type == 'percentage':
        total_pct = Decimal('0.00')
        pcts = {}
        for u in members_list:
            raw = request.POST.get(f'percent_{u.id}', '0')
            try:
                val = Decimal(raw)
            except InvalidOperation:
                val = Decimal('0.00')
            pcts[u] = val
            total_pct += val
        if total_pct == Decimal('0.00'):
            total_pct = Decimal(n)
            for u in members_list:
                pcts[u] = Decimal('1')
        running = Decimal('0.00')
        for i, u in enumerate(members_list):
            if i == n - 1:
                shares[u] = (amount_inr - running).quantize(Decimal('0.01'))
            else:
                amt = (amount_inr * pcts[u] / total_pct).quantize(Decimal('0.01'))
                shares[u] = amt
                running += amt

    elif split_type == 'share':
        total_shares = Decimal('0.00')
        unit_shares = {}
        for u in members_list:
            raw = request.POST.get(f'share_{u.id}', '1')
            try:
                val = Decimal(raw)
            except InvalidOperation:
                val = Decimal('1')
            unit_shares[u] = val
            total_shares += val
        if total_shares == Decimal('0.00'):
            total_shares = Decimal(n)
            for u in members_list:
                unit_shares[u] = Decimal('1')
        running = Decimal('0.00')
        for i, u in enumerate(members_list):
            if i == n - 1:
                shares[u] = (amount_inr - running).quantize(Decimal('0.01'))
            else:
                amt = (amount_inr * unit_shares[u] / total_shares).quantize(Decimal('0.01'))
                shares[u] = amt
                running += amt

    return shares


@login_required
def expense_detail(request, pk, expense_id):
    group = get_object_or_404(Group, pk=pk)
    expense = get_object_or_404(Expense, pk=expense_id, group=group)
    shares = expense.shares.select_related('user').all()
    return render(request, 'expenses/expense_detail.html', {'group': group, 'expense': expense, 'shares': shares})


@login_required
def expense_delete(request, pk, expense_id):
    group = get_object_or_404(Group, pk=pk)
    expense = get_object_or_404(Expense, pk=expense_id, group=group)
    if request.method == 'POST':
        expense.delete()
        messages.success(request, 'Expense deleted.')
        return redirect('expenses:group_detail', pk=group.pk)
    return render(request, 'expenses/expense_confirm_delete.html', {'group': group, 'expense': expense})


@login_required
def settlement_create(request, pk):
    group = get_object_or_404(Group, pk=pk)
    if request.method == 'POST':
        form = SettlementForm(request.POST, group=group)
        if form.is_valid():
            data = form.cleaned_data
            if data['paid_by'] == data['paid_to']:
                messages.error(request, 'A person cannot settle with themselves.')
            else:
                Settlement.objects.create(
                    group=group,
                    paid_by=data['paid_by'],
                    paid_to=data['paid_to'],
                    amount_inr=data['amount'],
                    date=data['date'],
                    notes=data['notes'],
                    created_by=request.user,
                )
                messages.success(request, 'Payment recorded.')
                return redirect('expenses:group_detail', pk=group.pk)
    else:
        form = SettlementForm(group=group)
    return render(request, 'expenses/settlement_form.html', {'form': form, 'group': group})


@login_required
def balance_detail(request, pk):
    group = get_object_or_404(Group, pk=pk)
    user_id = request.GET.get('user')
    if user_id:
        target_user = get_object_or_404(User, pk=user_id)
    else:
        target_user = request.user
    balance = get_user_balance_in_group(group, target_user)
    breakdown = get_expense_breakdown_for_user(group, target_user)
    members = group.all_members_ever()
    return render(request, 'expenses/balance_detail.html', {
        'group': group,
        'target_user': target_user,
        'balance': balance,
        'breakdown': breakdown,
        'members': members,
    })


@login_required
def import_csv(request, pk):
    group = get_object_or_404(Group, pk=pk)
    if request.method == 'POST':
        form = CSVImportForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = form.cleaned_data['csv_file']
            batch = run_import(group, csv_file, request.user, filename=csv_file.name)
            messages.success(request, f'Import complete: {batch.rows_created} created, {batch.rows_skipped} skipped, {batch.rows_pending} pending review.')
            return redirect('expenses:import_report', pk=group.pk, batch_id=batch.pk)
    else:
        form = CSVImportForm()
    return render(request, 'expenses/import_form.html', {'form': form, 'group': group})


@login_required
def import_report(request, pk, batch_id):
    group = get_object_or_404(Group, pk=pk)
    batch = get_object_or_404(ImportBatch, pk=batch_id, group=group)
    rows = batch.rows.all()
    return render(request, 'expenses/import_report.html', {'group': group, 'batch': batch, 'rows': rows})


@login_required
def import_review(request, pk, batch_id):
    group = get_object_or_404(Group, pk=pk)
    batch = get_object_or_404(ImportBatch, pk=batch_id, group=group)
    pending_rows = batch.rows.filter(status='pending')

    if request.method == 'POST':
        row_id = request.POST.get('row_id')
        action = request.POST.get('action')
        row = get_object_or_404(ImportRow, pk=row_id, batch=batch)
        if action == 'reject':
            row.status = 'rejected'
            row.action_taken += ' Rejected by reviewer; no expense was created.'
        elif action == 'approve':
            row.status = 'approved'
            row.action_taken += ' Approved by reviewer for manual entry; please add the corresponding expense or settlement manually if needed.'
        row.reviewed_by = request.user
        row.reviewed_at = timezone.now()
        row.save()
        batch.rows_pending = batch.rows.filter(status='pending').count()
        batch.save()
        messages.success(request, 'Row updated.')
        return redirect('expenses:import_review', pk=group.pk, batch_id=batch.pk)

    return render(request, 'expenses/import_review.html', {'group': group, 'batch': batch, 'pending_rows': pending_rows})