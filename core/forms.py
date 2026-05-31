from django import forms
from django.utils import timezone
from django.db.models import Q
from .models import Transaction, Budget, BudgetCategory, SharedBudget, Category, Comment


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['type', 'description', 'amount', 'date', 'category', 'notes', 'shared_budget']
        widgets = {
            'type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Monthly salary...'}),
            'amount': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.001', 'min': '0'}),
            'date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3, 'placeholder': 'Add a note...'}),
            'shared_budget': forms.Select(attrs={'class': 'form-select'}),
        }

    # FIX: Removed duplicate __init__ — only one clean version kept
    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = Category.objects.filter(
            Q(is_default=True) | Q(user=user)
        )
        self.fields['shared_budget'].queryset = SharedBudget.objects.filter(members=user)
        self.fields['shared_budget'].required = False
        self.fields['notes'].required = False
        self.fields['date'].initial = timezone.now().date()


class BudgetForm(forms.ModelForm):
    class Meta:
        model = Budget
        fields = ['name', 'period', 'total_ceiling', 'start_date', 'end_date']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. May 2026 budget'}),
            'period': forms.Select(attrs={'class': 'form-select'}),
            'total_ceiling': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.001'}),
            'start_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['end_date'].required = False


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'icon', 'color', 'is_income']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input'}),
            'icon': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '🏠'}),
            'color': forms.TextInput(attrs={'class': 'form-input', 'type': 'color'}),
            'is_income': forms.CheckboxInput(),
        }


class SharedBudgetForm(forms.ModelForm):
    class Meta:
        model = SharedBudget
        fields = ['name', 'emoji', 'total_ceiling', 'period', 'start_date', 'end_date']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input'}),
            'emoji': forms.TextInput(attrs={'class': 'form-input'}),
            'total_ceiling': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.001'}),
            'period': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['end_date'].required = False


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2, 'placeholder': 'Add a comment...'}),
        }
