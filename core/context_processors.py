from .models import Alert, SharedBudgetInvitation
from accounts.models import User


def global_context(request):
    context = {}
    if request.user.is_authenticated:
        # Unread alerts count
        context['unread_alerts'] = Alert.objects.filter(
            user=request.user,
            is_read=False
        ).count()

        # Pending invitations count for sidebar badge
        context['pending_inv_count'] = SharedBudgetInvitation.objects.filter(
            invited_user=request.user,
            status='pending'
        ).count()

        # Admin pending users count
        if request.user.is_admin:
            context['pending_admin_count'] = User.objects.filter(
                status='pending'
            ).count()

    return context