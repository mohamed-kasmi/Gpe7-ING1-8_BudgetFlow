from django.db import models
from django.utils import timezone
from accounts.models import User


class Category(models.Model):
    ICON_CHOICES = [
        ('🏠', 'Housing'), ('🍔', 'Food'), ('⛽', 'Transport'),
        ('💊', 'Health'), ('🎮', 'Leisure'), ('📚', 'Education'),
        ('💡', 'Utilities'), ('👔', 'Clothing'), ('✈️', 'Travel'),
        ('💰', 'Income'), ('🎉', 'Events'), ('📱', 'Technology'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True,
                             help_text="NULL = default/global category")
    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=10, default='💰')
    color = models.CharField(max_length=20, default='#6ee7b7')
    is_default = models.BooleanField(default=False)
    is_income = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'bf_categories'
        verbose_name_plural = 'Categories'
        ordering = ['name']

    def __str__(self):
        return f"{self.icon} {self.name}"


class Transaction(models.Model):
    TYPE_CHOICES = [('income', 'Income'), ('expense', 'Expense')]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    shared_budget = models.ForeignKey('SharedBudget', on_delete=models.SET_NULL,
                                      null=True, blank=True, related_name='transactions')
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=3)
    description = models.CharField(max_length=255)
    notes = models.TextField(blank=True)
    date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'bf_transactions'
        ordering = ['-date', '-created_at']

    def __str__(self):
        sign = '+' if self.type == 'income' else '-'
        return f"{sign}{self.amount} TND — {self.description}"


class Budget(models.Model):
    PERIOD_CHOICES = [
        ('monthly', 'Monthly'),
        ('weekly', 'Weekly'),
        ('custom', 'Custom'),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='budgets'
    )
    name = models.CharField(max_length=100)
    period = models.CharField(
        max_length=10, choices=PERIOD_CHOICES, default='monthly'
    )
    total_ceiling = models.DecimalField(max_digits=12, decimal_places=3)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_shared = models.BooleanField(default=False)
    # ── Link budget to a specific category (optional) ──
    category = models.ForeignKey(
        'Category',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='budgets',
        help_text='If set, only tracks expenses in this category'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'bf_budgets'
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.name} ({self.user.full_name})"

    @property
    def spent(self):
        """
        Calculate spent amount ONLY within the budget's date range.
        If a category is linked, only count that category's expenses.
        """
        from django.db.models import Sum
        from django.utils import timezone

        # Determine end date
        end = self.end_date or timezone.now().date()

        # Base queryset — only expenses within date range
        qs = Transaction.objects.filter(
            user=self.user,
            type='expense',
            date__gte=self.start_date,
            date__lte=end,
            shared_budget__isnull=True,  # exclude shared budget transactions
        )

        # If budget is linked to a specific category, filter by it
        if self.category:
            qs = qs.filter(category=self.category)

        result = qs.aggregate(t=Sum('amount'))['t'] or 0
        return float(result)

    @property
    def percentage(self):
        if float(self.total_ceiling) == 0:
            return 0
        return min(
            round((self.spent / float(self.total_ceiling)) * 100, 1),
            999
        )

    @property
    def remaining(self):
        return float(self.total_ceiling) - self.spent

    @property
    def status(self):
        p = self.percentage
        if p >= 100:
            return 'over'
        elif p >= 90:
            return 'warn'
        return 'ok'


class BudgetCategory(models.Model):
    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name='category_limits')
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    ceiling = models.DecimalField(max_digits=12, decimal_places=3)

    class Meta:
        db_table = 'bf_budget_categories'
        unique_together = ['budget', 'category']

    @property
    def spent(self):
        from django.db.models import Sum
        result = Transaction.objects.filter(
            user=self.budget.user,
            category=self.category,
            type='expense',
            date__gte=self.budget.start_date,
            date__lte=self.budget.end_date or timezone.now().date()
        ).aggregate(t=Sum('amount'))['t'] or 0
        return float(result)

    @property
    def percentage(self):
        if float(self.ceiling) == 0:
            return 0
        return min(round((self.spent / float(self.ceiling)) * 100, 1), 999)

    @property
    def status(self):
        p = self.percentage
        if p >= 100:
            return 'over'
        elif p >= 90:
            return 'warn'
        return 'ok'


class SharedBudget(models.Model):
    name = models.CharField(max_length=100)
    emoji = models.CharField(max_length=10, default='💰')
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_shared_budgets')
    members = models.ManyToManyField(User, through='SharedBudgetMember', related_name='shared_budgets')
    total_ceiling = models.DecimalField(max_digits=12, decimal_places=3)
    period = models.CharField(max_length=10, choices=Budget.PERIOD_CHOICES, default='monthly')
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    invite_code = models.CharField(max_length=12, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'bf_shared_budgets'

    def __str__(self):
        return f"{self.emoji} {self.name}"

    def save(self, *args, **kwargs):
        if not self.invite_code:
            import random
            import string
            self.invite_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        super().save(*args, **kwargs)

    @property
    def total_spent(self):
        from django.db.models import Sum
        result = self.transactions.filter(type='expense').aggregate(t=Sum('amount'))['t'] or 0
        return float(result)

    @property
    def percentage(self):
        if float(self.total_ceiling) == 0:
            return 0
        return min(round((self.total_spent / float(self.total_ceiling)) * 100, 1), 999)
    @property
    def total_spent(self):
        from django.db.models import Sum
        result = self.transactions.filter(
            type='expense'
        ).aggregate(t=Sum('amount'))['t'] or 0
        return float(result)

    @property
    def total_income(self):
        from django.db.models import Sum
        result = self.transactions.filter(
            type='income'
        ).aggregate(t=Sum('amount'))['t'] or 0
        return float(result)

    @property
    def remaining(self):
        # remaining = ceiling - spent
        return float(self.total_ceiling) - self.total_spent

    @property
    def percentage(self):
        if float(self.total_ceiling) == 0:
            return 0
        return min(
            round((self.total_spent / float(self.total_ceiling)) * 100, 1),
            999
        )


class SharedBudgetMember(models.Model):
    ROLE_CHOICES = [('owner', 'Owner'), ('member', 'Member')]
    shared_budget = models.ForeignKey(SharedBudget, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='member')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'bf_shared_budget_members'
        unique_together = ['shared_budget', 'user']


class Alert(models.Model):
    TYPE_CHOICES = [
        ('budget_exceeded', 'Budget Exceeded'),
        ('budget_warning', 'Budget Warning'),
        ('monthly_report', 'Monthly Report'),
        ('shared_update', 'Shared Budget Update'),
        ('account_approved', 'Account Approved'),
        ('info', 'Information'),
    ]
    LEVEL_CHOICES = [('info', 'Info'), ('warn', 'Warning'), ('danger', 'Danger')]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='alerts')
    type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default='info')
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    budget = models.ForeignKey(Budget, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'bf_alerts'
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.level}] {self.title}"


class Comment(models.Model):
    transaction = models.ForeignKey(
        Transaction,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'bf_comments'
        ordering = ['created_at']

    def __str__(self):
        return f"{self.user.full_name}: {self.content[:50]}"


class SharedBudgetInvitation(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ]

    shared_budget = models.ForeignKey(
        SharedBudget,
        on_delete=models.CASCADE,
        related_name='invitations'
    )
    invited_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sent_invitations'
    )
    invited_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='received_invitations'
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='pending'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'bf_shared_budget_invitations'
        ordering = ['-created_at']
        unique_together = ['shared_budget', 'invited_user']

    def __str__(self):
        return (
            f"Invite: {self.invited_by.full_name} → "
            f"{self.invited_user.full_name} "
            f"({self.shared_budget.name})"
        )
