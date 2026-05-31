from django.urls import path
from . import views

urlpatterns = [
    # ── MAIN ──
    path('dashboard/', views.dashboard, name='dashboard'),

    # ── TRANSACTIONS ──
    path('transactions/', views.transactions, name='transactions'),
    path('transactions/<int:pk>/edit/', views.edit_transaction, name='edit_transaction'),
    path('transactions/export/', views.export_transactions_csv, name='export_csv'),

    # ── BUDGETS ──
    path('budgets/', views.budgets, name='budgets'),

    # ── CATEGORIES ──
    path('categories/', views.categories, name='categories'),

    # ── SHARED BUDGETS ──
    path('shared-budgets/', views.shared_budgets, name='shared_budgets'),
    path('shared-budgets/<int:pk>/', views.shared_budget_detail, name='shared_budget_detail'),
    path('shared-budgets/<int:pk>/invite/', views.invite_friend, name='invite_friend'),

    # ── INVITATIONS ──
    path('my-invitations/', views.my_invitations, name='my_invitations'),
    path('my-invitations/<int:pk>/respond/', views.accept_invitation, name='accept_invitation'),

    # ── ALERTS ──
    path('alerts/', views.alerts_view, name='alerts'),

    # ── ADMIN ──
    path('admin-panel/', views.admin_panel, name='admin_panel'),
    path('admin-panel/shared-budgets/', views.admin_shared_budgets, name='admin_shared_budgets'),
    path('admin-panel/shared-budgets/<int:pk>/', views.admin_shared_budget_detail, name='admin_shared_budget_detail'),
]