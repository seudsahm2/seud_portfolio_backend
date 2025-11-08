from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ("portfolio", "0007_skill_expansion"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="stars",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="project",
            name="forks",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="project",
            name="language",
            field=models.CharField(blank=True, max_length=60),
        ),
        migrations.AddField(
            model_name="project",
            name="topics",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="project",
            name="last_pushed",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
