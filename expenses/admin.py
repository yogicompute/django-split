from django.contrib import admin
from .models import (
    Group, GroupMembership, Expense, ExpenseShare, Settlement,
    ImportBatch, ImportRow,
)

admin.site.register(Group)
admin.site.register(GroupMembership)
admin.site.register(Expense)
admin.site.register(ExpenseShare)
admin.site.register(Settlement)
admin.site.register(ImportBatch)
admin.site.register(ImportRow)