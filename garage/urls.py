from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),

    path("clients/", views.client_list, name="client_list"),
    path("clients/new/", views.client_create, name="client_create"),
    path("clients/<int:client_id>/edit/", views.client_edit, name="client_edit"),

    path("cars/", views.car_list, name="car_list"),
    path("cars/new/", views.car_create, name="car_create"),
    path("cars/new/<int:client_id>/", views.car_create_for_client, name="car_create_for_client"),

    path("cars/<str:vin>/", views.car_detail, name="car_detail"),
    path("cars/<str:vin>/edit/", views.car_edit, name="car_edit"),

    path("cars/<str:vin>/visits/new/", views.visit_create, name="visit_create"),

    path("workers/", views.workers_list, name="workers_list"),
    
    path("visits/id/<int:visit_id>/", views.visit_detail, name="visit_detail"),
    path("visit/<int:visit_id>/edit/", views.visit_edit, name="visit_edit"),

    path("visits/<int:visit_id>/invoice.pdf", views.visit_invoice_pdf, name="visit_invoice_pdf"),
    path("visits/<int:visit_id>/whatsapp", views.visit_whatsapp, name="visit_whatsapp"),
    path("accounting/", views.accounting_dashboard, name="accounting_dashboard"),
    path("accounting/expenses/", views.expenses_list, name="expenses_list"),
    path("accounting/expenses/<int:expense_id>/delete/", views.expense_delete, name="expense_delete"),
    path("reports/car/<str:vin>/", views.car_report, name="car_report"),

]
