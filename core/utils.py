from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.db import models
from django.db.models import Sum
from .models import Alert, Transaction, Budget


def send_html_email(subject, template_name, context, recipient_list):
    html_content = render_to_string(template_name, context)
    text_content = strip_tags(html_content)
    msg = EmailMultiAlternatives(subject, text_content, settings.DEFAULT_FROM_EMAIL, recipient_list)
    msg.attach_alternative(html_content, "text/html")
    try:
        msg.send()
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False


def check_budget_alerts(user):
    """Check all budgets and create alerts if thresholds exceeded."""
    from .models import Budget
    budgets = Budget.objects.filter(user=user)
    for budget in budgets:
        pct = budget.percentage
        existing_exceeded = Alert.objects.filter(
            user=user, budget=budget, type='budget_exceeded'
        ).exists()
        existing_warning = Alert.objects.filter(
            user=user, budget=budget, type='budget_warning'
        ).exists()

        if pct >= 100 and not existing_exceeded:
            Alert.objects.create(
                user=user,
                type='budget_exceeded',
                level='danger',
                title=f'{budget.name} budget exceeded!',
                message=f'You have spent {budget.spent:.3f} TND out of your '
                        f'{float(budget.total_ceiling):.3f} TND limit ({pct}%).',
                budget=budget
            )
            send_html_email(
                subject=f'[BudgetFlow] Budget exceeded: {budget.name}',
                template_name='accounts/emails/budget_alert.html',
                context={'user': user, 'budget': budget, 'pct': pct, 'level': 'exceeded'},
                recipient_list=[user.email]
            )

        elif pct >= 90 and not existing_warning and not existing_exceeded:
            Alert.objects.create(
                user=user,
                type='budget_warning',
                level='warn',
                title=f'{budget.name} budget near limit',
                message=f'You have used {pct}% of your {budget.name} budget. '
                        f'Only {budget.remaining:.3f} TND remaining.',
                budget=budget
            )
            send_html_email(
                subject=f'[BudgetFlow] Budget warning: {budget.name}',
                template_name='accounts/emails/budget_alert.html',
                context={'user': user, 'budget': budget, 'pct': pct, 'level': 'warning'},
                recipient_list=[user.email]
            )


def get_dashboard_stats(user):
    """Compute dashboard statistics for a user."""
    from django.db.models import Sum
    from django.utils import timezone
    import calendar
    import datetime

    now = timezone.now().date()
    first_day = now.replace(day=1)
    last_day = now.replace(day=calendar.monthrange(now.year, now.month)[1])

    tx = user.transactions
    month_income = tx.filter(type='income', date__gte=first_day, date__lte=last_day
                              ).aggregate(t=Sum('amount'))['t'] or 0
    month_expense = tx.filter(type='expense', date__gte=first_day, date__lte=last_day
                               ).aggregate(t=Sum('amount'))['t'] or 0
    balance = float(month_income) - float(month_expense)

    # Category breakdown
    cat_data = tx.filter(
        type='expense', date__gte=first_day, date__lte=last_day
    ).values('category__name', 'category__icon', 'category__color').annotate(
        total=Sum('amount')
    ).order_by('-total')[:6]

    # Monthly chart data (last 6 months)
    chart_data = []
    for i in range(5, -1, -1):
        month_offset = (now.month - 1 - i) % 12 + 1
        year_offset = now.year + ((now.month - 1 - i) // 12)
        fd = datetime.date(year_offset, month_offset, 1)
        ld = datetime.date(year_offset, month_offset,
                           calendar.monthrange(year_offset, month_offset)[1])
        inc = tx.filter(type='income', date__gte=fd, date__lte=ld
                        ).aggregate(t=Sum('amount'))['t'] or 0
        exp = tx.filter(type='expense', date__gte=fd, date__lte=ld
                        ).aggregate(t=Sum('amount'))['t'] or 0
        chart_data.append({
            'month': fd.strftime('%b'),
            'income': float(inc),
            'expense': float(exp),
        })

# Budget used = same spent/ceiling values shown on the budgets page
    budgets = user.budgets.filter(
        start_date__lte=last_day
    ).filter(
        models.Q(end_date__isnull=True) | models.Q(end_date__gte=first_day)
    )
    if budgets.exists():
        total_ceiling = sum(float(b.total_ceiling) for b in budgets)
        # Use each budget's own .spent property (respects date range per budget)
        total_spent = sum(b.spent for b in budgets)
        if total_ceiling > 0:
            raw_pct = round((total_spent / total_ceiling) * 100)
            budget_pct = min(raw_pct, 999)
        else:
            budget_pct = 0
    else:
        budget_pct = 0

    return {
        'month_income': float(month_income),
        'month_expense': float(month_expense),
        'balance': balance,
        'budget_pct': budget_pct,
        'cat_data': list(cat_data),
        'chart_data': chart_data,
    }

def check_shared_budget_alerts(shared_budget, user):
    """Check shared budget thresholds and create alerts for a member."""
    from .models import Alert, SharedBudget

    pct = shared_budget.percentage

    existing_exceeded = Alert.objects.filter(
        user=user,
        type='budget_exceeded',
        title__icontains=shared_budget.name
    ).exists()

    existing_warning = Alert.objects.filter(
        user=user,
        type='budget_warning',
        title__icontains=shared_budget.name
    ).exists()

    if pct >= 100 and not existing_exceeded:
        Alert.objects.create(
            user=user,
            type='budget_exceeded',
            level='danger',
            title=f'Shared budget "{shared_budget.name}" exceeded!',
            message=(
                f'The shared budget "{shared_budget.name}" has reached '
                f'{pct:.0f}% of its ceiling. '
                f'{shared_budget.total_spent:.3f} TND spent of '
                f'{float(shared_budget.total_ceiling):.3f} TND.'
            ),
        )
        # Send email to member
        from django.conf import settings
        send_html_email(
            subject=f'[BudgetFlow] Shared budget exceeded: {shared_budget.name}',
            template_name='accounts/emails/budget_alert.html',
            context={
                'user': user,
                'budget': shared_budget,
                'pct': pct,
                'level': 'exceeded'
            },
            recipient_list=[user.email]
        )

    elif pct >= 90 and not existing_warning and not existing_exceeded:
        Alert.objects.create(
            user=user,
            type='budget_warning',
            level='warn',
            title=f'Shared budget "{shared_budget.name}" near limit',
            message=(
                f'The shared budget "{shared_budget.name}" has reached '
                f'{pct:.0f}% of its ceiling. '
                f'Only {shared_budget.remaining:.3f} TND remaining.'
            ),
        )