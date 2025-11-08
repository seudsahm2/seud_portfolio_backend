from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ("portfolio", "0006_alter_blogpost_options_alter_experience_options_and_more"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="skill",
            name="level",
        ),
        migrations.AddField(
            model_name="skill",
            name="category",
            field=models.CharField(blank=True, help_text="e.g. frontend, backend, devops, cloud, data, testing", max_length=40),
        ),
        migrations.AddField(
            model_name="skill",
            name="description",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="skill",
            name="docs_url",
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name="skill",
            name="icon",
            field=models.CharField(blank=True, help_text="icon key or url", max_length=80),
        ),
        migrations.AddField(
            model_name="skill",
            name="highlights",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="skill",
            name="since_year",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="skill",
            name="primary",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="skill",
            name="accent",
            field=models.CharField(blank=True, help_text="CSS color or hex, e.g. #10b981", max_length=20),
        ),
        migrations.AddField(
            model_name="skill",
            name="order",
            field=models.SmallIntegerField(default=0),
        ),
        migrations.AlterModelOptions(
            name="skill",
            options={"ordering": ["order", "name", "id"]},
        ),
    ]
