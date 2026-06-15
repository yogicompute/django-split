from django.contrib.auth.models import User
from django.db import models


class Group(models.Model):
    name = models.CharField(max_length=120)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='groups_created')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def active_members(self, on_date=None):
        qs = self.memberships.all()
        if on_date is not None:
            qs = qs.filter(joined_on__lte=on_date).filter(
                models.Q(left_on__isnull=True) | models.Q(left_on__gte=on_date)
            )
        else:
            qs = qs.filter(left_on__isnull=True)
        return User.objects.filter(id__in=qs.values_list('user_id', flat=True))

    def all_members_ever(self):
        return User.objects.filter(id__in=self.memberships.values_list('user_id', flat=True)).distinct()


class GroupMembership(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='group_memberships')
    joined_on = models.DateField()
    left_on = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = ('group', 'user', 'joined_on')

    def __str__(self):
        return f'{self.user} in {self.group} from {self.joined_on} to {self.left_on or "now"}'

    def covers_date(self, the_date):
        if the_date < self.joined_on:
            return False
        if self.left_on is not None and the_date > self.left_on:
            return False
        return True


SPLIT_TYPE_CHOICES = [
    ('equal', 'Equal'),
    ('unequal', 'Unequal (exact amounts)'),
    ('percentage', 'Percentage'),
    ('share', 'Share-based'),
]


class Expense(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='expenses')
    description = models.CharField(max_length=255)
    paid_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='expenses_paid')
    date = models.DateField()
    split_type = models.CharField(max_length=20, choices=SPLIT_TYPE_CHOICES, default='equal')

    amount_inr = models.DecimalField(max_digits=12, decimal_places=2)
    original_amount = models.DecimalField(max_digits=12, decimal_places=2)
    original_currency = models.CharField(max_length=10, default='INR')
    fx_rate_to_inr = models.DecimalField(max_digits=10, decimal_places=4, default=1)

    notes = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='expenses_created')
    created_at = models.DateTimeField(auto_now_add=True)
    is_refund = models.BooleanField(default=False)

    source_import_row = models.ForeignKey(
        'ImportRow', on_delete=models.SET_NULL, null=True, blank=True, related_name='created_expenses'
    )

    def __str__(self):
        return f'{self.description} ({self.amount_inr} INR, {self.date})'


class ExpenseShare(models.Model):
    expense = models.ForeignKey(Expense, on_delete=models.CASCADE, related_name='shares')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='expense_shares')
    share_amount_inr = models.DecimalField(max_digits=12, decimal_places=2)
    raw_value = models.CharField(max_length=50, blank=True, default='')

    class Meta:
        unique_together = ('expense', 'user')

    def __str__(self):
        return f'{self.user} owes {self.share_amount_inr} for {self.expense}'


class Settlement(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='settlements')
    paid_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='settlements_paid')
    paid_to = models.ForeignKey(User, on_delete=models.CASCADE, related_name='settlements_received')
    amount_inr = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()
    notes = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='settlements_created')
    created_at = models.DateTimeField(auto_now_add=True)

    source_import_row = models.ForeignKey(
        'ImportRow', on_delete=models.SET_NULL, null=True, blank=True, related_name='created_settlements'
    )

    def __str__(self):
        return f'{self.paid_by} paid {self.paid_to} {self.amount_inr} on {self.date}'


class ImportBatch(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='import_batches')
    filename = models.CharField(max_length=255)
    imported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    imported_at = models.DateTimeField(auto_now_add=True)
    total_rows = models.IntegerField(default=0)
    rows_created = models.IntegerField(default=0)
    rows_skipped = models.IntegerField(default=0)
    rows_pending = models.IntegerField(default=0)

    def __str__(self):
        return f'Import of {self.filename} into {self.group} at {self.imported_at}'


class ImportRow(models.Model):
    STATUS_CHOICES = [
        ('created', 'Created'),
        ('skipped', 'Skipped'),
        ('pending', 'Pending review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    batch = models.ForeignKey(ImportBatch, on_delete=models.CASCADE, related_name='rows')
    row_number = models.IntegerField()
    raw_data = models.JSONField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='created')
    anomalies = models.JSONField(default=list)
    action_taken = models.TextField(blank=True, default='')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['row_number']

    def __str__(self):
        return f'Row {self.row_number} of batch {self.batch_id} - {self.status}'