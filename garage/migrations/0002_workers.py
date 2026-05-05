from django.db import migrations, models
import django.db.models.deletion


def forwards(apps, schema_editor):
    Visit = apps.get_model("garage", "Visit")
    Worker = apps.get_model("garage", "Worker")
    db_alias = schema_editor.connection.alias

    cache = {}
    for visit in Visit.objects.using(db_alias).all():
        name = (visit.worker_name or "").strip()
        if not name:
            name = "غير محدد"
        worker = cache.get(name)
        if worker is None:
            worker, _ = Worker.objects.using(db_alias).get_or_create(name=name)
            cache[name] = worker
        visit.worker_id = worker.id
        visit.save(update_fields=["worker"])


class Migration(migrations.Migration):
    dependencies = [
        ("garage", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Worker",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True, verbose_name="اسم الفني")),
                ("phone", models.CharField(blank=True, max_length=30, verbose_name="رقم الهاتف")),
            ],
        ),
        migrations.AddField(
            model_name="visit",
            name="worker",
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="visits",
                to="garage.worker",
            ),
        ),
        migrations.RunPython(forwards, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="visit",
            name="worker_name",
        ),
        migrations.AlterField(
            model_name="visit",
            name="worker",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="visits",
                to="garage.worker",
            ),
        ),
    ]
