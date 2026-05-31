import json
import csv
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Sum, Q
from django.http import HttpResponse
from django.utils import timezone
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings

from accounts.models import User as UserModel
from .models import (
    Transaction, Budget, BudgetCategory,
    SharedBudget, SharedBudgetMember,
    Category, Alert, Comment,
    SharedBudgetInvitation
)
from .utils import check_budget_alerts, check_shared_budget_alerts, get_dashboard_stats


def is_admin(user):
    return user.is_authenticated and user.is_admin


# ══════════════════════════════════════════════
# LANDING
# ══════════════════════════════════════════════
def landing_page(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'landing.html')


# ══════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════
@login_required
def dashboard(request):
    stats = get_dashboard_stats(request.user)
    recent_tx = Transaction.objects.filter(user=request.user)[:8]
    budgets = Budget.objects.filter(user=request.user)[:5]
    unread_alerts = Alert.objects.filter(
        user=request.user, is_read=False
    ).count()
    return render(request, 'core/dashboard.html', {
        'stats': stats,
        'recent_tx': recent_tx,
        'budgets': budgets,
        'unread_alerts': unread_alerts,
        'chart_data_json': json.dumps(stats['chart_data']),
        'cat_data_json': json.dumps(stats['cat_data'], default=str),
    })


# ══════════════════════════════════════════════
# TRANSACTIONS
# ══════════════════════════════════════════════
@login_required
def transactions(request):
    qs = Transaction.objects.filter(user=request.user)
    tx_type = request.GET.get('type', '')
    category_id = request.GET.get('category', '')
    month = request.GET.get('month', '')

    if tx_type:
        qs = qs.filter(type=tx_type)
    if category_id:
        qs = qs.filter(category_id=category_id)
    if month:
        try:
            y, m = month.split('-')
            qs = qs.filter(date__year=y, date__month=m)
        except (ValueError, AttributeError):
            pass

    categories = Category.objects.filter(
        Q(is_default=True) | Q(user=request.user)
    )

    if request.method == 'POST':
        if 'delete_tx' in request.POST:
            tx = get_object_or_404(
                Transaction,
                id=request.POST.get('tx_id'),
                user=request.user
            )
            tx.delete()
            messages.success(request, '✓ Transaction deleted.')
            check_budget_alerts(request.user)
            return redirect('transactions')

        description = request.POST.get('description', '').strip()
        amount = request.POST.get('amount')
        date = request.POST.get('date')
        tx_type_post = request.POST.get('type', 'expense')
        category_id_post = request.POST.get('category') or None
        notes = request.POST.get('notes', '')

        if description and amount and date:
            Transaction.objects.create(
                user=request.user,
                type=tx_type_post,
                description=description,
                amount=amount,
                date=date,
                category_id=category_id_post,
                notes=notes,
            )
            messages.success(request, '✓ Transaction added!')
            check_budget_alerts(request.user)
        else:
            messages.error(request, '✗ Please fill all required fields.')
        return redirect('transactions')

    return render(request, 'core/transactions.html', {
        'transactions': qs,
        'categories': categories,
        'selected_type': tx_type,
        'selected_category': category_id,
    })


@login_required
def edit_transaction(request, pk):
    tx = get_object_or_404(Transaction, pk=pk, user=request.user)
    categories = Category.objects.filter(
        Q(is_default=True) | Q(user=request.user)
    )
    if request.method == 'POST':
        tx.type = request.POST.get('type', tx.type)
        tx.description = request.POST.get('description', tx.description)
        tx.amount = request.POST.get('amount', tx.amount)
        tx.date = request.POST.get('date', tx.date)
        tx.notes = request.POST.get('notes', tx.notes)
        tx.category_id = request.POST.get('category') or None
        tx.save()
        messages.success(request, '✓ Transaction updated.')
        check_budget_alerts(request.user)
        return redirect('transactions')
    return render(request, 'core/transaction_edit.html', {
        'tx': tx,
        'categories': categories,
    })


@login_required
def export_transactions_csv(request):
    qs = Transaction.objects.filter(user=request.user)
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="transactions.csv"'
    writer = csv.writer(response)
    writer.writerow(['Date', 'Type', 'Description', 'Amount', 'Category', 'Notes'])
    for tx in qs:
        writer.writerow([
            tx.date, tx.type, tx.description,
            tx.amount,
            tx.category.name if tx.category else '',
            tx.notes,
        ])
    return response


# ══════════════════════════════════════════════
# BUDGETS
# ══════════════════════════════════════════════
@login_required
def budgets(request):
    user_budgets = Budget.objects.filter(
        user=request.user,
        is_shared=False
    )

    if request.method == 'POST':
        if 'delete_budget' in request.POST:
            b = get_object_or_404(
                Budget,
                id=request.POST.get('budget_id'),
                user=request.user
            )
            b.delete()
            messages.success(request, '✓ Budget deleted.')
            return redirect('budgets')

        # ── CREATE NEW BUDGET ──
        name = request.POST.get('name', '').strip()
        total_ceiling = request.POST.get('total_ceiling')
        period = request.POST.get('period', 'monthly')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date') or None
        category_id = request.POST.get('category') or None

        if name and total_ceiling and start_date:
            Budget.objects.create(
                user=request.user,
                name=name,
                total_ceiling=total_ceiling,
                period=period,
                start_date=start_date,
                end_date=end_date,
                category_id=category_id,
                is_shared=False,
            )
            messages.success(request, '✓ Budget created!')
        else:
            messages.error(request, '✗ Please fill all required fields.')

        return redirect('budgets')

    # ── Summary stats ──
    total_ceiling = sum(float(b.total_ceiling) for b in user_budgets)
    total_spent = sum(b.spent for b in user_budgets)
    total_remaining = total_ceiling - total_spent

    # ── Categories for the form ──
    from django.db.models import Q
    categories = Category.objects.filter(
        Q(is_default=True) | Q(user=request.user)
    )

    return render(request, 'core/budgets.html', {
        'budgets': user_budgets,
        'total_ceiling': total_ceiling,
        'total_spent': total_spent,
        'total_remaining': total_remaining,
        'categories': categories,
    })


# ══════════════════════════════════════════════
# CATEGORIES
# ══════════════════════════════════════════════
@login_required
def categories(request):
    user_cats = Category.objects.filter(
        Q(is_default=True) | Q(user=request.user)
    )

    if request.method == 'POST':
        if 'delete_cat' in request.POST:
            cat = get_object_or_404(
                Category,
                id=request.POST.get('cat_id'),
                user=request.user
            )
            cat.delete()
            messages.success(request, '✓ Category deleted.')
            return redirect('categories')

        name = request.POST.get('name', '').strip()
        icon = request.POST.get('icon', '💰').strip()
        color = request.POST.get('color', '#6ee7b7')
        is_income = 'is_income' in request.POST

        if name:
            Category.objects.create(
                user=request.user,
                name=name,
                icon=icon,
                color=color,
                is_income=is_income,
                is_default=False,
            )
            messages.success(request, '✓ Category created!')
        else:
            messages.error(request, '✗ Category name is required.')
        return redirect('categories')

    return render(request, 'core/categories.html', {
        'categories': user_cats,
    })


# ══════════════════════════════════════════════
# SHARED BUDGETS — LIST
# ══════════════════════════════════════════════
@login_required
def shared_budgets(request):
    my_shared = SharedBudget.objects.filter(members=request.user)
    pending_invitations = SharedBudgetInvitation.objects.filter(
        invited_user=request.user,
        status='pending'
    ).select_related('shared_budget', 'invited_by')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create':
            name = request.POST.get('name', '').strip()
            emoji = request.POST.get('emoji', '🏠').strip()
            total_ceiling = request.POST.get('total_ceiling')
            period = request.POST.get('period', 'monthly')
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date') or None

            if name and total_ceiling and start_date:
                sb = SharedBudget.objects.create(
                    name=name,
                    emoji=emoji,
                    owner=request.user,
                    total_ceiling=total_ceiling,
                    period=period,
                    start_date=start_date,
                    end_date=end_date,
                )
                SharedBudgetMember.objects.create(
                    shared_budget=sb,
                    user=request.user,
                    role='owner'
                )
                messages.success(
                    request,
                    f'✓ "{sb.name}" created! Invite code: {sb.invite_code}'
                )
            else:
                messages.error(request, '✗ Please fill all required fields.')

        elif action == 'join':
            code = request.POST.get('invite_code', '').strip().upper()
            try:
                sb = SharedBudget.objects.get(invite_code=code)
                if SharedBudgetMember.objects.filter(
                    shared_budget=sb, user=request.user
                ).exists():
                    messages.info(request, 'You are already a member.')
                else:
                    SharedBudgetMember.objects.create(
                        shared_budget=sb,
                        user=request.user,
                        role='member'
                    )
                    messages.success(
                        request,
                        f'✓ Joined "{sb.name}" successfully!'
                    )
            except SharedBudget.DoesNotExist:
                messages.error(request, '✗ Invalid invite code.')

        return redirect('shared_budgets')

    return render(request, 'core/shared_budgets.html', {
        'shared_budgets': my_shared,
        'pending_invitations': pending_invitations,
    })


# ══════════════════════════════════════════════
# SHARED BUDGET — DETAIL (with comments + category ceilings)
# ══════════════════════════════════════════════
@login_required
def shared_budget_detail(request, pk):
    sb = get_object_or_404(SharedBudget, pk=pk, members=request.user)
    transactions_qs = sb.transactions.all().select_related(
        'user', 'category'
    ).prefetch_related('comments__user')
    members = SharedBudgetMember.objects.filter(
        shared_budget=sb
    ).select_related('user')
    categories = Category.objects.filter(
        Q(is_default=True) | Q(user=request.user)
    )
    category_ceilings = BudgetCategory.objects.filter(
        budget__is_shared=True
    )

    # Check if current user is owner
    is_owner = SharedBudgetMember.objects.filter(
        shared_budget=sb,
        user=request.user,
        role='owner'
    ).exists()

    if request.method == 'POST':
        action = request.POST.get('action', 'add_tx')

        # ── ADD TRANSACTION ──
        if action == 'add_tx':
            tx_type = request.POST.get('type', 'expense')
            description = request.POST.get('description', '').strip()
            amount = request.POST.get('amount')
            date = request.POST.get('date')
            category_id = request.POST.get('category') or None
            notes = request.POST.get('notes', '')

            if description and amount and date:
                Transaction.objects.create(
                    user=request.user,
                    shared_budget=sb,
                    type=tx_type,
                    description=description,
                    amount=amount,
                    date=date,
                    category_id=category_id,
                    notes=notes,
                )
                messages.success(request, '✓ Transaction added.')
                # Check alerts for all members
                for member in members:
                    check_shared_budget_alerts(sb, member.user)
            else:
                messages.error(request, '✗ Please fill all required fields.')

        # ── ADD COMMENT ──
        elif action == 'add_comment':
            tx_id = request.POST.get('tx_id')
            content = request.POST.get('content', '').strip()
            if tx_id and content:
                tx = get_object_or_404(
                    Transaction,
                    pk=tx_id,
                    shared_budget=sb
                )
                Comment.objects.create(
                    transaction=tx,
                    user=request.user,
                    content=content
                )
                messages.success(request, '✓ Comment added.')
            else:
                messages.error(request, '✗ Comment cannot be empty.')

        # ── DELETE COMMENT ──
        elif action == 'delete_comment':
            comment_id = request.POST.get('comment_id')
            comment = get_object_or_404(
                Comment,
                pk=comment_id,
                user=request.user
            )
            comment.delete()
            messages.success(request, '✓ Comment deleted.')

        # ── REMOVE MEMBER (owner only) ──
        elif action == 'remove_member':
            if is_owner:
                member_id = request.POST.get('member_id')
                member_obj = get_object_or_404(
                    SharedBudgetMember,
                    pk=member_id,
                    shared_budget=sb
                )
                if member_obj.role == 'owner':
                    messages.error(
                        request,
                        '✗ Cannot remove the budget owner.'
                    )
                else:
                    member_name = member_obj.user.full_name
                    member_obj.delete()
                    messages.success(
                        request,
                        f'✓ {member_name} removed from budget.'
                    )
            else:
                messages.error(
                    request,
                    '✗ Only the budget owner can remove members.'
                )

        # ── SET CATEGORY CEILING (owner only) ──
        elif action == 'set_category_ceiling':
            if is_owner:
                cat_id = request.POST.get('category_id')
                ceiling = request.POST.get('ceiling')
                if cat_id and ceiling:
                    # We use a Budget object linked to shared budget
                    # Create or get the shared budget's Budget record
                    budget_obj, _ = Budget.objects.get_or_create(
                        user=sb.owner,
                        name=f'[Shared] {sb.name}',
                        defaults={
                            'total_ceiling': sb.total_ceiling,
                            'period': sb.period,
                            'start_date': sb.start_date,
                            'end_date': sb.end_date,
                            'is_shared': True,
                        }
                    )
                    cat = get_object_or_404(Category, pk=cat_id)
                    BudgetCategory.objects.update_or_create(
                        budget=budget_obj,
                        category=cat,
                        defaults={'ceiling': ceiling}
                    )
                    messages.success(
                        request,
                        f'✓ Ceiling set for {cat.name}: {ceiling} TND'
                    )
            else:
                messages.error(
                    request,
                    '✗ Only the budget owner can set category ceilings.'
                )

        # ── DELETE TRANSACTION (author or owner) ──
        elif action == 'delete_tx':
            tx_id = request.POST.get('tx_id')
            tx = get_object_or_404(
                Transaction,
                pk=tx_id,
                shared_budget=sb
            )
            if tx.user == request.user or is_owner:
                tx.delete()
                messages.success(request, '✓ Transaction deleted.')
            else:
                messages.error(
                    request,
                    '✗ You can only delete your own transactions.'
                )

        return redirect('shared_budget_detail', pk=pk)

        # ── Category spending summary ──
    cat_spending = sb.transactions.filter(
        type='expense'
    ).values(
        'category__name',
        'category__icon',
        'category__color',
        'category__id'
    ).annotate(total=Sum('amount')).order_by('-total')

    # ── Member spending summary ──
    member_spending = sb.transactions.filter(
        type='expense'
    ).values(
        'user__first_name',
        'user__last_name',
        'user__email'
    ).annotate(total=Sum('amount')).order_by('-total')

    # ── Compute remaining values ──
    total_ceiling = float(sb.total_ceiling)
    total_spent = float(sb.total_spent)
    remaining = total_ceiling - total_spent
    percentage = sb.percentage

    return render(request, 'core/shared_budget_detail.html', {
        'sb': sb,
        'transactions': transactions_qs,
        'members': members,
        'categories': categories,
        'is_owner': is_owner,
        'cat_spending': cat_spending,
        'member_spending': member_spending,
        'total_ceiling': total_ceiling,
        'total_spent': total_spent,
        'remaining': remaining,
        'percentage': percentage,
    })


# ══════════════════════════════════════════════
# INVITE FRIEND
# ══════════════════════════════════════════════
@login_required
def invite_friend(request, pk):
    sb = get_object_or_404(SharedBudget, pk=pk, members=request.user)

    if request.method == 'POST':
        email = request.POST.get('friend_email', '').strip().lower()

        if not email:
            messages.error(request, '✗ Please enter an email address.')
            return redirect('shared_budget_detail', pk=pk)

        # Check email exists
        try:
            friend = UserModel.objects.get(email=email)
        except UserModel.DoesNotExist:
            messages.error(
                request,
                f'✗ No BudgetFlow account found with "{email}". '
                f'Ask your friend to register first.'
            )
            return redirect('shared_budget_detail', pk=pk)

        if friend == request.user:
            messages.error(request, '✗ You cannot invite yourself.')
            return redirect('shared_budget_detail', pk=pk)

        if SharedBudgetMember.objects.filter(
            shared_budget=sb, user=friend
        ).exists():
            messages.warning(
                request,
                f'⚠ {friend.full_name} is already a member.'
            )
            return redirect('shared_budget_detail', pk=pk)

        if SharedBudgetInvitation.objects.filter(
            shared_budget=sb,
            invited_user=friend,
            status='pending'
        ).exists():
            messages.warning(
                request,
                f'⚠ {friend.full_name} already has a pending invitation.'
            )
            return redirect('shared_budget_detail', pk=pk)

        # Create invitation
        SharedBudgetInvitation.objects.create(
            shared_budget=sb,
            invited_by=request.user,
            invited_user=friend,
            status='pending'
        )

        # Send email
        try:
            html_content = render_to_string(
                'accounts/emails/budget_invitation.html',
                {
                    'friend': friend,
                    'invited_by': request.user,
                    'budget': sb,
                    'invite_code': sb.invite_code,
                    'join_url': request.build_absolute_uri('/my-invitations/'),
                    'admin_email': settings.ADMIN_EMAIL,
                }
            )
            msg = EmailMultiAlternatives(
                subject=(
                    f'🎉 {request.user.full_name} invited you to join '
                    f'"{sb.name}" on BudgetFlow!'
                ),
                body=strip_tags(html_content),
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[friend.email],
            )
            msg.attach_alternative(html_content, 'text/html')
            msg.send(fail_silently=False)
            messages.success(
                request,
                f'✓ Invitation sent to {friend.full_name} ({friend.email})!'
            )
        except Exception as e:
            print(f'Email error: {e}')
            messages.warning(
                request,
                f'✓ Invitation created but email failed. '
                f'Share code manually: {sb.invite_code}'
            )

        return redirect('shared_budget_detail', pk=pk)

    return redirect('shared_budget_detail', pk=pk)


# ══════════════════════════════════════════════
# MY INVITATIONS
# ══════════════════════════════════════════════
@login_required
def my_invitations(request):
    invitations = SharedBudgetInvitation.objects.filter(
        invited_user=request.user,
        status='pending'
    ).select_related('shared_budget', 'invited_by')
    return render(request, 'core/my_invitations.html', {
        'invitations': invitations,
    })


# ══════════════════════════════════════════════
# ACCEPT / DECLINE INVITATION
# ══════════════════════════════════════════════
@login_required
def accept_invitation(request, pk):
    invitation = get_object_or_404(
        SharedBudgetInvitation,
        pk=pk,
        invited_user=request.user,
        status='pending'
    )
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'accept':
            SharedBudgetMember.objects.get_or_create(
                shared_budget=invitation.shared_budget,
                user=request.user,
                defaults={'role': 'member'}
            )
            invitation.status = 'accepted'
            invitation.save()
            messages.success(
                request,
                f'🎉 You joined "{invitation.shared_budget.name}"!'
            )
            return redirect(
                'shared_budget_detail',
                pk=invitation.shared_budget.pk
            )
        elif action == 'decline':
            invitation.status = 'rejected'
            invitation.save()
            messages.info(request, 'You declined the invitation.')
            return redirect('my_invitations')

    return render(request, 'core/accept_invitation.html', {
        'invitation': invitation,
        'budget': invitation.shared_budget,
        'invited_by': invitation.invited_by,
    })


# ══════════════════════════════════════════════
# ALERTS
# ══════════════════════════════════════════════
@login_required
def alerts_view(request):
    check_budget_alerts(request.user)
    user_alerts = Alert.objects.filter(user=request.user)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'dismiss':
            Alert.objects.filter(
                id=request.POST.get('alert_id'),
                user=request.user
            ).update(is_read=True)
        elif action == 'dismiss_all':
            Alert.objects.filter(user=request.user).update(is_read=True)
        return redirect('alerts')

    return render(request, 'core/alerts.html', {'alerts': user_alerts})


# ══════════════════════════════════════════════
# ADMIN PANEL
# ══════════════════════════════════════════════
@login_required
@user_passes_test(is_admin, login_url='/dashboard/')
def admin_panel(request):
    from accounts.views import send_html_email
    users = UserModel.objects.all().order_by('-date_joined')

    if request.method == 'POST':
        action = request.POST.get('action')
        user_id = request.POST.get('user_id')
        target_user = get_object_or_404(UserModel, id=user_id)

        if action == 'approve':
            target_user.is_approved = True
            target_user.status = 'active'
            target_user.save()
            sent = send_html_email(
                subject='✓ Your BudgetFlow account has been approved!',
                template_name='accounts/emails/account_approved.html',
                context={
                    'user': target_user,
                    'login_url': request.build_absolute_uri('/accounts/login/'),
                },
                recipient_list=[target_user.email]
            )
            if sent:
                messages.success(
                    request,
                    f'✓ {target_user.full_name} approved. Email sent.'
                )
            else:
                messages.warning(
                    request,
                    f'✓ {target_user.full_name} approved but email failed.'
                )

        elif action == 'reject':
            name = target_user.full_name
            target_user.delete()
            messages.warning(request, f'✗ {name} rejected and removed.')

        elif action == 'approve_deletion':
            target_user.status = 'deleted'
            target_user.is_active = False
            target_user.save()
            send_html_email(
                subject='BudgetFlow — Account deletion confirmed',
                template_name='accounts/emails/account_deleted.html',
                context={'user': target_user},
                recipient_list=[target_user.email]
            )
            messages.success(
                request,
                f'✓ {target_user.full_name} account deleted.'
            )

        elif action == 'change_role':
            new_role = request.POST.get('role')
            if new_role in ['user', 'admin']:
                target_user.role = new_role
                target_user.is_staff = (new_role == 'admin')
                target_user.save()
                messages.success(
                    request,
                    f'✓ {target_user.full_name} role → {new_role}.'
                )

        return redirect('admin_panel')

    total_tx = Transaction.objects.count()
    total_income = Transaction.objects.filter(
        type='income'
    ).aggregate(t=Sum('amount'))['t'] or 0
    total_expense = Transaction.objects.filter(
        type='expense'
    ).aggregate(t=Sum('amount'))['t'] or 0
    total_shared = SharedBudget.objects.count()
    pending_count = users.filter(status='pending').count()
    deletion_count = users.filter(status='deletion_requested').count()

    return render(request, 'core/admin_panel.html', {
        'users': users,
        'pending_count': pending_count,
        'deletion_count': deletion_count,
        'total_tx': total_tx,
        'total_income': float(total_income),
        'total_expense': float(total_expense),
        'total_shared': total_shared,
        'total_users': users.count(),
    })


# ══════════════════════════════════════════════
# ADMIN — ALL SHARED BUDGETS VIEW
# ══════════════════════════════════════════════
@login_required
@user_passes_test(is_admin, login_url='/dashboard/')
def admin_shared_budgets(request):
    all_shared = SharedBudget.objects.all().prefetch_related(
        'members'
    ).select_related('owner').order_by('-created_at')

    return render(request, 'core/admin_shared_budgets.html', {
        'all_shared': all_shared,
    })


@login_required
@user_passes_test(is_admin, login_url='/dashboard/')
def admin_shared_budget_detail(request, pk):
    sb = get_object_or_404(SharedBudget, pk=pk)
    transactions_qs = sb.transactions.all().select_related(
        'user', 'category'
    )
    members = SharedBudgetMember.objects.filter(
        shared_budget=sb
    ).select_related('user')

    return render(request, 'core/admin_shared_budget_detail.html', {
        'sb': sb,
        'transactions': transactions_qs,
        'members': members,
    })