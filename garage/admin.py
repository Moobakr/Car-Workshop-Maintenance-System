from django.contrib import admin
from .models import Client, Car, Visit, Worker

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    search_fields = ["name", "phone"]
    list_display = ["name", "phone"]

@admin.register(Car)
class CarAdmin(admin.ModelAdmin):
    search_fields = ["vin", "plate_number", "client__phone", "client__name"]
    list_display = ["vin", "plate_number", "client", "current_km"]
    list_filter = ["created_at"]

@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    search_fields = ["car__vin", "worker__name", "work_description"]
    list_display = ["car", "visit_date", "km_at_visit", "worker"]
    list_filter = ["visit_date"]


@admin.register(Worker)
class WorkerAdmin(admin.ModelAdmin):
    search_fields = ["name", "phone"]
    list_display = ["name", "phone"]
