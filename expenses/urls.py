from django.urls import path
from . import views

app_name = 'expenses'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('groups/', views.group_list, name='group_list'),
    path('groups/new/', views.group_create, name='group_create'),
    path('groups/<int:pk>/', views.group_detail, name='group_detail'),
    path('groups/<int:pk>/members/', views.group_members, name='group_members'),
    path('groups/<int:pk>/expenses/new/', views.expense_create, name='expense_create'),
    path('groups/<int:pk>/expenses/<int:expense_id>/', views.expense_detail, name='expense_detail'),
    path('groups/<int:pk>/expenses/<int:expense_id>/delete/', views.expense_delete, name='expense_delete'),
    path('groups/<int:pk>/settlements/new/', views.settlement_create, name='settlement_create'),
    path('groups/<int:pk>/balance/', views.balance_detail, name='balance_detail'),
    path('groups/<int:pk>/import/', views.import_csv, name='import_csv'),
    path('groups/<int:pk>/import/<int:batch_id>/report/', views.import_report, name='import_report'),
    path('groups/<int:pk>/import/<int:batch_id>/review/', views.import_review, name='import_review'),
]