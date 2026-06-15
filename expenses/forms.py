from django import forms
from django.contrib.auth.models import User

from .models import Group, SPLIT_TYPE_CHOICES


class GroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ['name']


class AddMemberForm(forms.Form):
    username = forms.CharField(max_length=150, help_text='Existing or new username of the user to add.')
    joined_on = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))


class RemoveMemberForm(forms.Form):
    left_on = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))


class CSVImportForm(forms.Form):
    csv_file = forms.FileField()


SPLIT_CHOICES = SPLIT_TYPE_CHOICES


class ExpenseForm(forms.Form):
    description = forms.CharField(max_length=255)
    date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    amount = forms.DecimalField(max_digits=12, decimal_places=2)
    currency = forms.ChoiceField(choices=[('INR', 'INR'), ('USD', 'USD')])
    paid_by = forms.ModelChoiceField(queryset=User.objects.none())
    split_type = forms.ChoiceField(choices=SPLIT_CHOICES)
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}))

    def __init__(self, *args, group=None, on_date=None, **kwargs):
        super().__init__(*args, **kwargs)
        if group is not None:
            members = group.active_members(on_date=on_date) if on_date else group.active_members()
            self.fields['paid_by'].queryset = members
            self.members = members
        else:
            self.members = User.objects.none()


class SettlementForm(forms.Form):
    paid_by = forms.ModelChoiceField(queryset=User.objects.none())
    paid_to = forms.ModelChoiceField(queryset=User.objects.none())
    amount = forms.DecimalField(max_digits=12, decimal_places=2)
    date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}))

    def __init__(self, *args, group=None, **kwargs):
        super().__init__(*args, **kwargs)
        if group is not None:
            members = group.all_members_ever()
            self.fields['paid_by'].queryset = members
            self.fields['paid_to'].queryset = members