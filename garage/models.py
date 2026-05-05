from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone


class Client(models.Model):
    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=30, unique=True)

    def __str__(self):
        return f"{self.name} ({self.phone})"


class Car(models.Model):
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="cars")
    vin = models.CharField("رقم الهيكل (VIN)", max_length=64, unique=True, db_index=True)
    plate_number = models.CharField("رقم اللوحة", max_length=32, blank=True, db_index=True)
    important_detail = models.CharField("معلومة مهمة", max_length=255, blank=True)
    current_km = models.PositiveIntegerField("العداد الحالي (KM)", default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.vin} - {self.plate_number}"


class Worker(models.Model):
    name = models.CharField("اسم الفني", max_length=120, unique=True)
    phone = models.CharField("رقم الهاتف", max_length=30, blank=True)

    def __str__(self):
        return self.name


class Visit(models.Model):
    car = models.ForeignKey(Car, on_delete=models.CASCADE, related_name="visits")
    visit_date = models.DateTimeField(default=timezone.now)

    km_at_visit = models.PositiveIntegerField("العداد عند الزيارة", validators=[MinValueValidator(0)])
    worker = models.ForeignKey(Worker, on_delete=models.PROTECT, related_name="visits", verbose_name="الفني")
    work_description = models.TextField("وصف التصليح")
    parts_used = models.TextField("قطع الغيار المستخدمة", blank=True)
    notes = models.TextField("ملاحظات", blank=True)
    invoice_no = models.CharField("رقم الفاتورة", max_length=20, unique=True, null=True, blank=True, db_index=True)
    labor_cost = models.DecimalField("المصنعيه", max_digits=10, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-visit_date", "-id"]
        indexes = [
            models.Index(fields=["car", "visit_date"]),
        ]

    def __str__(self):
        return f"{self.car.vin} @ {self.visit_date:%Y-%m-%d}"

class VisitPart(models.Model):
    visit = models.ForeignKey(Visit, on_delete=models.CASCADE, related_name="visit_parts")
    part_name = models.CharField("اسم القطعة", max_length=200)
    client_cost = models.DecimalField("على العميل", max_digits=10, decimal_places=2, default=0)
    workshop_cost = models.DecimalField("على الورشة", max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return self.part_name
    
class Payment(models.Model):
    visit = models.ForeignKey(Visit, on_delete=models.CASCADE, related_name="payments")
    cash_amount = models.DecimalField("المبلغ كاش", max_digits=12, decimal_places=2, default=0)
    insta_amount = models.DecimalField("المبلغ على انستا باي", max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.visit} - {self.cash_amount + self.insta_amount}"

class InvoiceCounter(models.Model):
    year = models.PositiveIntegerField(unique=True)
    last_number = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.year}: {self.last_number}"
    

class Expense(models.Model):
    date = models.DateField()
    category = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    note = models.TextField(blank=True)

    visit_part = models.ForeignKey(
        "VisitPart",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="expenses"
    )


    
