from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags
from django.db.models import Sum
from .models import User
from .forms import RegisterForm, LoginForm, ProfileUpdateForm, PasswordChangeForm
from core.models import Transaction, Budget, SharedBudget, Alert


def send_html_email(subject, template_name, context, recipient_list):
    """Utility to send HTML emails."""
    try:
        html_content = render_to_string(template_name, context)
        text_content = strip_tags(html_content)
        msg = EmailMultiAlternatives(subject, text_content, settings.DEFAULT_FROM_EMAIL, recipient_list)
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=True)
    except Exception as e:
        print(f"Email error: {e}")


def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        # Notify admin
        send_html_email(
            subject=f'[BudgetFlow] New account pending: {user.full_name}',
            template_name='accounts/emails/new_account_admin.html',
            context={'user': user, 'admin_url': request.build_absolute_uri('/admin-panel/')},
            recipient_list=[settings.ADMIN_EMAIL]
        )
        messages.success(request, 'Account created! Please wait for admin approval.')
        return redirect('login')
    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.cleaned_data['user']
        login(request, user)
        messages.success(request, f'Welcome back, {user.first_name}!')
        next_url = request.GET.get('next', 'dashboard')
        return redirect(next_url)
    return render(request, 'accounts/login.html', {'form': form})


@login_required
def logout_view(request):
    logout(request)
    messages.info(request, 'You have been signed out.')
    return redirect('landing')


@login_required
def profile_view(request):
    profile_form = ProfileUpdateForm(instance=request.user)
    password_form = PasswordChangeForm()

    if request.method == 'POST':
        if 'update_profile' in request.POST:
            profile_form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, 'Profile updated successfully!')
                return redirect('profile')

        elif 'change_password' in request.POST:
            password_form = PasswordChangeForm(request.POST)
            if password_form.is_valid():
                if not request.user.check_password(password_form.cleaned_data['current_password']):
                    messages.error(request, 'Current password is incorrect.')
                else:
                    request.user.set_password(password_form.cleaned_data['new_password'])
                    request.user.save()
                    messages.success(request, 'Password changed successfully!')
                    return redirect('login')

        elif 'request_deletion' in request.POST:
            request.user.status = 'deletion_requested'
            request.user.save()
            send_html_email(
                subject=f'[BudgetFlow] Account deletion request: {request.user.full_name}',
                template_name='accounts/emails/deletion_request_admin.html',
                context={'user': request.user},
                recipient_list=[settings.ADMIN_EMAIL]
            )
            messages.warning(request, 'Account deletion requested. Admin will process it.')
            return redirect('profile')

    # Stats
    tx_count = Transaction.objects.filter(user=request.user).count()
    income = Transaction.objects.filter(user=request.user, type='income').aggregate(t=Sum('amount'))['t'] or 0
    expense = Transaction.objects.filter(user=request.user, type='expense').aggregate(t=Sum('amount'))['t'] or 0

    return render(request, 'accounts/profile.html', {
        'profile_form': profile_form,
        'password_form': password_form,
        'tx_count': tx_count,
        'total_income': income,
        'total_expense': expense,
    })
