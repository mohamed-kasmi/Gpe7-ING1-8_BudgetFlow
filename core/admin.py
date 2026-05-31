from django.contrib import admin
from .models import Category, Transaction, Budget, BudgetCategory, SharedBudget, SharedBudgetMember, Alert, Comment


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'icon', 'color', 'is_default', 'is_income', 'user']
    list_filter = ['is_default', 'is_income']
    search_fields = ['name']


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['description', 'type', 'amount', 'date', 'user', 'category']
    list_filter = ['type', 'date']
    search_fields = ['description', 'user__email']
    ordering = ['-date']


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'total_ceiling', 'period', 'start_date', 'end_date']
    list_filter = ['period']
    search_fields = ['name', 'user__email']


@admin.register(SharedBudget)
class SharedBudgetAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'total_ceiling', 'invite_code', 'created_at']
    search_fields = ['name', 'owner__email', 'invite_code']


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'type', 'level', 'is_read', 'created_at']
    list_filter = ['level', 'type', 'is_read']
    search_fields = ['user__email', 'title']
