from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse

from config.settings import resource_path
from .models import Client, Car, Visit, Worker, VisitPart, Payment
from .forms import ClientForm, CarForm, VisitForm, WorkerForm, VisitPartFormSet, PaymentForm
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.db import transaction
from django.utils import timezone
from .models import InvoiceCounter
import reportlab
import os
from django.conf import settings
from django.db.models import Sum
from .models import Expense
from .forms import ExpenseForm, ReportFilterForm
from urllib.parse import quote
from decimal import Decimal, InvalidOperation
from django.views.decorators.http import require_POST


import arabic_reshaper
from bidi.algorithm import get_display

def rtl(text: str) -> str:
    if not text:
        return ""
    reshaped = arabic_reshaper.reshape(str(text))
    return get_display(reshaped)

def home(request):
    q = (request.GET.get("q") or "").strip()
    cars = []
    visits = []

    if q:
        cars = Car.objects.select_related("client").filter(
            Q(vin__icontains=q) |
            Q(plate_number__icontains=q) |
            Q(client__phone__icontains=q) |
            Q(client__name__icontains=q)
        )[:50]

        visits = Visit.objects.select_related("car", "car__client").filter(
            invoice_no__icontains=q
        )[:50]

    return render(request, "garage/home.html", {"q": q, "cars": cars, "visits": visits})


# ---------- Clients ----------
def client_list(request):
    q = (request.GET.get("q") or "").strip()

    clients = Client.objects.all().order_by("-id")

    if q:
        # search by phone (and optionally name)
        clients = clients.filter(
            Q(phone__icontains=q)
        )

    return render(request, "garage/client_list.html", {
        "clients": clients,
        "q": q,
    })
def client_create(request):
    
    form = ClientForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        client = form.save()
        return redirect("car_create_for_client", client_id=client.id)
    return render(request, "garage/form.html", {"title": "إضافة عميل", "form": form})


def client_edit(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    form = ClientForm(request.POST or None, instance=client)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("client_list")
    return render(request, "garage/form.html", {"title": "تعديل بيانات العميل", "form": form})


# ---------- Cars ----------
def car_list(request):
    cars = Car.objects.select_related("client").all().order_by("-created_at")[:300]
    return render(request, "garage/car_list.html", {"cars": cars})


def car_create(request):
    client_id = request.GET.get("client")

    if request.method == "POST":
        form = CarForm(request.POST)
        if form.is_valid():
            car = form.save()
            return redirect("car_detail", vin=car.vin)
    else:
        initial = {}
        if client_id:
            initial["client"] = client_id
        form = CarForm(initial=initial)

        # hide client field if client is predefined
        if client_id:
            form.fields["client"].disabled = True

    return render(
        request,
        "garage/form.html",
        {
            "title": "إضافة سيارة",
            "form": form,
        },
    )

def car_create_for_client(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    form = CarForm(request.POST or None, initial={"client": client})
    if request.method == "POST" and form.is_valid():
        car = form.save()
        return redirect("car_detail", vin=car.vin)
    return render(request, "garage/form.html", {"title": f"إضافة سيارة للعميل: {client.name}", "form": form})


def car_edit(request, vin):
    car = get_object_or_404(Car, vin=vin)
    form = CarForm(request.POST or None, instance=car)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("car_detail", vin=car.vin)
    return render(request, "garage/form.html", {"title": "تعديل بيانات السيارة", "form": form})


def car_detail(request, vin):
    car = get_object_or_404(Car.objects.select_related("client"), vin=vin)
    visits = car.visits.all()
    return render(request, "garage/car_detail.html", {"car": car, "visits": visits})


def visit_detail(request, visit_id):
    visit = get_object_or_404(
        Visit.objects.select_related("car", "car__client", "worker"),
        id=visit_id
    )

    parts = VisitPart.objects.filter(visit_id=visit_id).order_by("id")
    payments = Payment.objects.filter(visit_id=visit_id).order_by("id")

    cash = payments.aggregate(s=Sum("cash_amount"))["s"] or Decimal("0")
    insta = payments.aggregate(s=Sum("insta_amount"))["s"] or Decimal("0")
    parts_client_total = parts.aggregate(s=Sum("client_cost"))["s"] or Decimal("0")
    parts_workshop_total = parts.aggregate(s=Sum("workshop_cost"))["s"] or Decimal("0")
    labor_cost = getattr(visit, "labor_cost", None) or Decimal("0")
    grand_total = parts_client_total + labor_cost

    return render(request, "garage/visit_detail.html", {
        "visit": visit,
        "car": visit.car,
        "client": visit.car.client,
        "parts": parts,
        "parts_client_total": parts_client_total,
        "parts_workshop_total": parts_workshop_total,
        "cash": cash,
        "insta": insta,
        "labor_cost": labor_cost,
        "grand_total": grand_total,
    })

def visit_edit(request, visit_id):
    visit = get_object_or_404(Visit, id=visit_id)
    car = visit.car

    payment_obj, _ = Payment.objects.get_or_create(
        visit=visit,
        defaults={"cash_amount": 0, "insta_amount": 0}
    )

    if request.method == "POST":
        form = VisitForm(request.POST, instance=visit)
        formset = VisitPartFormSet(request.POST, instance=visit, prefix="parts")
        payment_form = PaymentForm(request.POST, instance=payment_obj)

        if form.is_valid() and formset.is_valid() and payment_form.is_valid():
            with transaction.atomic():
                visit_obj = form.save(commit=False)

                labor_raw = (request.POST.get("labor_cost") or "").strip()
                try:
                    visit_obj.labor_cost = Decimal(labor_raw) if labor_raw else Decimal("0")
                except InvalidOperation:
                    visit_obj.labor_cost = Decimal("0")

                visit_obj.save()
                formset.save()
                payment_form.save()

                parts_lines = []
                for p in VisitPart.objects.filter(visit=visit_obj).order_by("id"):
                    name = (p.part_name or "").strip()
                    if name:
                        parts_lines.append(f"{name} - {p.client_cost or 0}")
                visit_obj.parts_used = "\n".join(parts_lines)
                visit_obj.save(update_fields=["parts_used"])

                Expense.objects.filter(visit_part__visit=visit_obj, category__startswith="Visit part").delete()
                for part in VisitPart.objects.filter(visit=visit_obj):
                    if (part.workshop_cost or 0) > 0:
                        name = (part.part_name or "").strip()
                        visit_label = visit_obj.invoice_no or f"#{visit_obj.id}"
                        category = f"Visit part - {name}" if name else "Visit part"
                        Expense.objects.create(
                            date=visit_obj.visit_date.date(),
                            category=category,
                            amount=part.workshop_cost,
                            note=f"VIN {car.vin} | Visit {visit_label} | visit_id:{visit_obj.id}",
                            visit_part=part,
                        )

                if visit_obj.km_at_visit > car.current_km:
                    car.current_km = visit_obj.km_at_visit
                    car.save(update_fields=["current_km"])

            return redirect("visit_detail", visit_id=visit_obj.id)

    else:
        form = VisitForm(instance=visit)
        formset = VisitPartFormSet(instance=visit, prefix="parts")
        payment_form = PaymentForm(instance=payment_obj)

    return render(request, "garage/visit_form.html", {
        "car": car,
        "form": form,
        "formset": formset,
        "payment_form": payment_form,
        "edit_mode": True,
    })

def generate_invoice_no(for_date=None):
    year = (for_date or timezone.now()).year
    with transaction.atomic():
        counter, _ = InvoiceCounter.objects.select_for_update().get_or_create(year=year)
        counter.last_number += 1
        counter.save(update_fields=["last_number"])
        return f"INV-{year}-{counter.last_number:06d}"



# ---------- Visits ----------
def visit_create(request, vin):
    car = get_object_or_404(Car, vin=vin)

    form = VisitForm(request.POST or None)
    formset = VisitPartFormSet(request.POST or None, prefix="parts")

    if request.method == "POST":
        payment_form = PaymentForm(request.POST)

        if form.is_valid() and formset.is_valid() and payment_form.is_valid():
            with transaction.atomic():
                visit = form.save(commit=False)
                visit.car = car
                if not visit.invoice_no:
                    visit.invoice_no = generate_invoice_no(for_date=visit.visit_date)

                labor_raw = (request.POST.get("labor_cost") or "").strip()
                try:
                    visit.labor_cost = Decimal(labor_raw) if labor_raw else Decimal("0")
                except InvalidOperation:
                    visit.labor_cost = Decimal("0")

                visit.save()

                formset.instance = visit
                parts = formset.save()

                parts_lines = []
                for p in VisitPart.objects.filter(visit=visit).order_by("id"):
                    name = (p.part_name or "").strip()
                    if name:
                        parts_lines.append(f"{name} - {p.client_cost or 0}")
                visit.parts_used = "\n".join(parts_lines)
                visit.save(update_fields=["parts_used"])

                pay = payment_form.save(commit=False)
                pay.visit = visit
                pay.save()

                Expense.objects.filter(visit_part__visit=visit, category__startswith="Visit part").delete()
                for part in VisitPart.objects.filter(visit=visit):
                    if (part.workshop_cost or 0) > 0:
                        name = (part.part_name or "").strip()
                        visit_label = visit.invoice_no or f"#{visit.id}"
                        category = f"Visit part - {name}" if name else "Visit part"
                        Expense.objects.create(
                            date=visit.visit_date.date(),
                            category=category,
                            amount=part.workshop_cost,
                            note=f"VIN {car.vin} | Visit {visit_label} | visit_id:{visit.id}",
                            visit_part=part,
                        )

            if visit.km_at_visit > car.current_km:
                car.current_km = visit.km_at_visit
                car.save(update_fields=["current_km"])

            return redirect("car_detail", vin=car.vin)

    else:
        payment_form = PaymentForm()

    return render(request, "garage/visit_form.html", {
        "car": car,
        "form": form,
        "formset": formset,
        "payment_form": payment_form,
    })

# ---------- Workers ----------
def workers_list(request):
    warning = None

    if request.method == "POST":
        if request.POST.get("action") == "delete":
            worker = get_object_or_404(Worker, id=request.POST.get("worker_id"))
            default_worker, _ = Worker.objects.get_or_create(name="غير محدد")
            if worker.id == default_worker.id:
                warning = "لا يمكن حذف الفني الافتراضي."
            else:
                worker.visits.update(worker=default_worker)
                try:
                    worker.delete()
                except ProtectedError:
                    warning = "لا يمكن حذف الفني لأنه مرتبط بزيارات مسجلة."
            form = WorkerForm()
        else:
            form = WorkerForm(request.POST)
            if form.is_valid():
                form.save()
                return redirect("workers_list")
    else:
        form = WorkerForm()

    workers = Worker.objects.all().order_by("name").prefetch_related("visits", "visits__car", "visits__car__client")
    return render(request, "garage/workers_list.html", {"workers": workers, "form": form, "warning": warning})


from io import BytesIO
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from django.conf import settings
from reportlab.platypus import Image as RLImage
from PIL import Image as PILImage


def visit_invoice_pdf(request, visit_id):
    visit = get_object_or_404(
        Visit.objects.select_related("car", "car__client", "worker"),
        id=visit_id
    )

    if not visit.invoice_no:
        visit.invoice_no = generate_invoice_no(for_date=visit.visit_date)
        visit.save(update_fields=["invoice_no"])

    # ✅ EXE-safe font path (recommended)
    font_path = resource_path("garage/static/fonts/Amiri-Regular.ttf")
    try:
        pdfmetrics.registerFont(TTFont("Cairo", font_path))
    except Exception:
        pass

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=28,
        leftMargin=28,
        topMargin=28,
        bottomMargin=28,
        title=visit.invoice_no
    )

    styles = getSampleStyleSheet()

    # -----------------------------
    # 🎨 RED / WHITE / BLACK THEME
    # -----------------------------
    RED = colors.HexColor("#D90429")        # strong red
    RED_DARK = colors.HexColor("#9B001C")   # darker red
    WHITE = colors.white
    BLACK = colors.HexColor("#111111")
    MUTED_TXT = colors.HexColor("#444444")

    CARD_BG = WHITE
    GRID = colors.HexColor("#E5E7EB")
    HEAD_BG = RED
    HEAD_TEXT = WHITE

    # -----------------------------
    # Styles
    # -----------------------------
    base = ParagraphStyle(
        "ArabicBase",
        parent=styles["Normal"],
        fontName="Cairo",
        fontSize=11,
        leading=16,
        alignment=2,
        textColor=BLACK,
    )

    h_title = ParagraphStyle(
        "ArabicTitle",
        parent=base,
        fontSize=17,
        leading=22,
        spaceAfter=2,
        textColor=RED,
    )

    h_section = ParagraphStyle(
        "ArabicSection",
        parent=base,
        fontSize=13,
        leading=18,
        spaceBefore=6,
        spaceAfter=6,
        textColor=RED_DARK,
    )

    muted = ParagraphStyle(
        "ArabicMuted",
        parent=base,
        textColor=MUTED_TXT,
        fontSize=10,
        leading=14,
    )

    def card_table(rows, col_widths, header_row=None):
        data = []
        if header_row:
            data.append([rtl(x) for x in header_row])
        for r in rows:
            data.append([rtl(x) for x in r])

        t = Table(data, colWidths=col_widths, hAlign="RIGHT")

        style_cmds = [
            ("FONT", (0, 0), (-1, -1), "Cairo", 11),
            ("TEXTCOLOR", (0, 0), (-1, -1), BLACK),
            ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),

            ("BACKGROUND", (0, 0), (-1, -1), CARD_BG),

            ("BOX", (0, 0), (-1, -1), 0.8, GRID),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, GRID),

            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]

        if header_row:
            style_cmds += [
                ("BACKGROUND", (0, 0), (-1, 0), HEAD_BG),
                ("TEXTCOLOR", (0, 0), (-1, 0), HEAD_TEXT),
                ("FONT", (0, 0), (-1, 0), "Cairo", 12),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
                ("TOPPADDING", (0, 0), (-1, 0), 10),
            ]

        t.setStyle(TableStyle(style_cmds))
        return t

    story = []

    client = visit.car.client
    car = visit.car

    workshop_name = ""
    workshop_phone = ""
    workshop_address = ""

    try:
        workshop = WorkshopSettings.objects.first()
        if workshop:
            workshop_name = workshop.workshop_name or workshop_name
            workshop_phone = workshop.workshop_phone or ""
            workshop_address = workshop.workshop_address or ""
    except Exception:
        pass

    left_block = [
        Paragraph(rtl(workshop_name), h_title),
    ]
    if workshop_phone:
        left_block.append(Paragraph(rtl(f"هاتف: {workshop_phone}"), muted))
    if workshop_address:
        left_block.append(Paragraph(rtl(f"العنوان: {workshop_address}"), muted))

    # -----------------------------
    # Logo (original size but safe max)
    # -----------------------------
    logo_path = resource_path("garage/static/images/logo.jpeg")

    try:
        logo_img = RLImage(logo_path)

        w_pt = float(logo_img.imageWidth)
        h_pt = float(logo_img.imageHeight)

        MAX_W = 150
        MAX_H = 70

        scale = min(MAX_W / w_pt, MAX_H / h_pt, 1.0)

        logo_img.drawWidth = w_pt * scale
        logo_img.drawHeight = h_pt * scale

        logo_box = Table(
            [[logo_img]],
            colWidths=[MAX_W],
            rowHeights=[MAX_H],
            hAlign="RIGHT"
        )

        logo_box.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))

    except Exception:
        # fallback
        logo_box = Table(
            [[Paragraph(rtl("Logo"), muted)]],
            colWidths=[150],
            rowHeights=[70],
            hAlign="RIGHT"
        )
        logo_box.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.8, GRID),
            ("BACKGROUND", (0, 0), (-1, -1), WHITE),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))

    header = Table([[left_block, logo_box]], colWidths=[doc.width - 160, 160], hAlign="RIGHT")
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(header)
    story.append(Spacer(1, 12))

    inv_rows = [
        [visit.invoice_no, "رقم الفاتورة:"],
        [visit.visit_date.strftime("%d/%m/%Y"), "تاريخ الزيارة:"],
        [str(visit.km_at_visit), "قراءة العداد:"],
    ]
    inv_table = card_table(inv_rows, [doc.width * 0.65, doc.width * 0.35], header_row=["فاتورة صيانة", ""])
    inv_table.setStyle(TableStyle([("SPAN", (0, 0), (-1, 0))]))
    story.append(inv_table)
    story.append(Spacer(1, 12))

    story.append(Paragraph(rtl("بيانات العميل"), h_section))
    cust_rows = [
        [client.name or "", "الاسم:"],
        [client.phone or "", "رقم الهاتف:"],
    ]
    story.append(card_table(cust_rows, [doc.width * 0.65, doc.width * 0.35]))
    story.append(Spacer(1, 10))

    story.append(Paragraph(rtl("بيانات العربية"), h_section))
    car_rows = [
        [car.vin, "رقم الشاسيه (VIN):"],
    ]
    if getattr(car, "plate_number", None):
        if car.plate_number:
            car_rows.append([car.plate_number, "رقم اللوحة:"])
    if getattr(car, "important_detail", None):
        if car.important_detail:
            car_rows.append([car.important_detail, "معلومة مهمة:"])
    story.append(card_table(car_rows, [doc.width * 0.65, doc.width * 0.35]))
    story.append(Spacer(1, 12))

    story.append(Paragraph(rtl("تفاصيل الصيانة"), h_section))
    story.append(Paragraph(rtl(f"الفني: {visit.worker.name}"), base))
    story.append(Spacer(1, 6))

    if getattr(visit, "work_description", ""):
        story.append(Paragraph(rtl("وصف العمل:"), base))
        story.append(Paragraph(rtl(visit.work_description), base))
        story.append(Spacer(1, 8))

    parts_qs = visit.visit_parts.all()
    parts_total = parts_qs.aggregate(s=Sum("client_cost"))["s"] or Decimal("0")
    labor_cost = getattr(visit, "labor_cost", None) or Decimal("0")
    grand_total = parts_total + labor_cost

    part_rows = []
    if parts_qs.exists():
        for part in parts_qs:
            part_rows.append([
                f"{part.client_cost or 0} ج.م",
                (part.part_name or "").strip()
            ])
    else:
        part_rows.append(["", "لا توجد قطع غيار مسجلة"])

    story.append(Paragraph(rtl("قطع الغيار"), h_section))
    parts_table = card_table(
        part_rows,
        [doc.width * 0.30, doc.width * 0.70],
        header_row=["السعر (العميل)", "اسم القطعة"]
    )
    story.append(parts_table)
    story.append(Spacer(1, 10))

    totals_rows = [
        [f"{parts_total} ج.م", "إجمالي قطع الغيار:"],
        [f"{labor_cost} ج.م", "المصنعية:"],
        [f"{grand_total} ج.م", "الإجمالي النهائي:"],
    ]
    totals_table = card_table(totals_rows, [doc.width * 0.40, doc.width * 0.60])

    # Make totals last row stand out (red tint)
    totals_table.setStyle(TableStyle([
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#FFF1F2")),
        ("TEXTCOLOR", (0, -1), (-1, -1), RED_DARK),
        ("FONT", (0, -1), (-1, -1), "Cairo", 12),
    ]))

    story.append(totals_table)
    story.append(Spacer(1, 10))

    if getattr(visit, "notes", ""):
        story.append(Paragraph(rtl("ملاحظات:"), base))
        story.append(Paragraph(rtl(visit.notes), base))
        story.append(Spacer(1, 8))

    story.append(Spacer(1, 10))
    story.append(Paragraph(rtl("شكراً لتعاملكم معنا"), muted))

    doc.build(story)

    pdf = buffer.getvalue()
    buffer.close()

    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{visit.invoice_no}.pdf"'
    return response



def normalize_egypt_phone(phone: str) -> str:
    p = (phone or "").strip().replace(" ", "").replace("-", "")
    if p.startswith("+"):
        p = p[1:]
    # if stored as 01XXXXXXXXX (11 digits)
    if p.startswith("01") and len(p) == 11:
        return "20" + p[1:]
    # if already 20...
    if p.startswith("20"):
        return p
    return p  # fallback (as-is)

from urllib.parse import quote

def visit_whatsapp(request, visit_id):
    visit = get_object_or_404(
        Visit.objects.select_related("car", "car__client", "worker"),
        id=visit_id
    )

    client = visit.car.client
    car = visit.car
    phone = normalize_egypt_phone(client.phone)

    parts_qs = visit.visit_parts.all()
    parts_total = parts_qs.aggregate(s=Sum("client_cost"))["s"] or 0
    labor_cost = getattr(visit, "labor_cost", 0) or 0
    grand_total = parts_total + labor_cost

    lines = []

    lines.append(f"أهلاً بحضرتك {client.name}")
    lines.append("")
    lines.append("🧾 *فاتورة صيانة*")
    lines.append(f"رقم الفاتورة: {visit.invoice_no}")
    lines.append(f"تاريخ الزيارة: {visit.visit_date:%d/%m/%Y}")
    lines.append("")

    lines.append("🚗 *بيانات العربية*")
    lines.append(f"رقم الشاسيه (VIN): {car.vin}")
    if getattr(car, "plate_number", None):
        if car.plate_number:
            lines.append(f"رقم اللوحة: {car.plate_number}")
    lines.append("")

    if getattr(visit, "worker", None):
        lines.append(f"👨‍🔧 الفني: {visit.worker.name}")
        lines.append("")

    if visit.work_description:
        lines.append("🛠 *وصف العمل:*")
        lines.append(visit.work_description.strip())
        lines.append("")

    lines.append("🔩 *قطع الغيار :*")
    if parts_qs.exists():
        for part in parts_qs:
            name = (part.part_name or "").strip()
            price = part.client_cost or 0
            lines.append(f"- {name}: {price} ج.م")
    else:
        lines.append("لا توجد قطع غيار مسجلة.")
    lines.append("")

    lines.append("💰 *الملخص المالي:*")
    lines.append(f"إجمالي قطع الغيار: {parts_total} ج.م")
    lines.append(f"المصنعية: {labor_cost} ج.م")
    lines.append(f"*الإجمالي النهائي: {grand_total} ج.م*")
    lines.append("")

    if visit.notes:
        lines.append("📝 *ملاحظات:*")
        lines.append(visit.notes.strip())
        lines.append("")

    lines.append("شكراً لتعاملكم معنا 🙏")
    lines.append("لو محتاج أي استفسار إحنا تحت أمرك")

    msg = "\n".join(lines)
    url = f"https://wa.me/{phone}?text={quote(msg)}"
    return redirect(url)



def accounting_dashboard(request):
    form = ReportFilterForm(request.GET or None)

    visits_qs = Visit.objects.all()
    expenses_qs = Expense.objects.all()
    payments_qs = Payment.objects.all()

    if form.is_valid():
        sd = form.cleaned_data.get("start_date")
        ed = form.cleaned_data.get("end_date")
        if sd:
            visits_qs = visits_qs.filter(visit_date__gte=sd)
            expenses_qs = expenses_qs.filter(date__gte=sd)
            payments_qs = payments_qs.filter(visit__visit_date__gte=sd)
        if ed:
            visits_qs = visits_qs.filter(visit_date__lte=ed)
            expenses_qs = expenses_qs.filter(date__lte=ed)
            payments_qs = payments_qs.filter(visit__visit_date__lte=ed)

    visit_expenses = VisitPart.objects.filter(visit__in=visits_qs).aggregate(s=Sum("workshop_cost"))["s"] or 0
    other_expenses = expenses_qs.exclude(category__startswith="Visit part").aggregate(s=Sum("amount"))["s"] or 0
    expenses_total = visit_expenses + other_expenses

    cash_total = payments_qs.aggregate(s=Sum("cash_amount"))["s"] or 0
    bank_total = payments_qs.aggregate(s=Sum("insta_amount"))["s"] or 0

    net = (cash_total + bank_total) - expenses_total

    return render(request, "garage/accounting_dashboard.html", {
    "form": form,
    "cash_total": cash_total,
    "bank_total": bank_total,
    "expenses_total": expenses_total,
    "visit_expenses": visit_expenses,
    "other_expenses": other_expenses,
    "net": net,
    "visits_count": visits_qs.count(),
    "expenses_count": expenses_qs.exclude(category__startswith="Payment ").count(),
})


def expenses_list(request):
    form = ExpenseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("expenses_list")

    expenses = Expense.objects.filter(category__startswith="Visit part").order_by("-date", "-id")

    for e in expenses:
        e.visit_url = None
        e.visit_label = None
        e.vin_label = None
        if (e.category or "").startswith(("Visit part")) and e.note:
            parts = [p.strip() for p in e.note.split("|")]
            for p in parts:
                if p.startswith("VIN "):
                    e.vin_label = p[4:].strip()
                elif p.startswith("Visit "):
                    e.visit_label = p[6:].strip()
                elif p.startswith("visit_id:"):
                    visit_id = p[len("visit_id:"):].strip()
                    if visit_id.isdigit():
                        e.visit_url = reverse("visit_detail", args=[int(visit_id)])
    return render(request, "garage/expenses_list.html", {
        "form": form,
        "expenses": expenses
    })


@require_POST
def expense_delete(request, expense_id):
    exp = get_object_or_404(Expense, id=expense_id)

    part = exp.visit_part
    exp.delete()

    if part:
        part.delete()

    return redirect("expenses_list")


def car_report(request, vin):
    car = get_object_or_404(Car, vin=vin)
    form = ReportFilterForm(request.GET or None)

    qs = Visit.objects.filter(car=car).order_by("-visit_date", "-id")

    if form.is_valid():
        sd = form.cleaned_data.get("start_date")
        ed = form.cleaned_data.get("end_date")
        if sd:
            qs = qs.filter(visit_date__gte=sd)
        if ed:
            qs = qs.filter(visit_date__lte=ed)

    total = VisitPart.objects.filter(visit__in=qs).aggregate(s=Sum("client_cost"))["s"] or 0

    return render(request, "garage/car_report.html", {
        "car": car,
        "form": form,
        "visits": qs,
        "total": total,
    })

