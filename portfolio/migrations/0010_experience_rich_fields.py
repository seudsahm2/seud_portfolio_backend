from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portfolio", "0009_project_github_rich_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="experience",
            name="location",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="experience",
            name="employment_type",
            field=models.CharField(blank=True, max_length=80, help_text="e.g., full-time, part-time, contract, internship"),
        ),
        migrations.AddField(
            model_name="experience",
            name="is_remote",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="experience",
            name="industry",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="experience",
            name="company_website",
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name="experience",
            name="company_logo",
            field=models.ImageField(blank=True, null=True, upload_to="experience/"),
        ),
        migrations.AddField(
            model_name="experience",
            name="company_logo_url",
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name="experience",
            name="technologies",
            field=models.JSONField(blank=True, default=list, help_text="List of key technologies used"),
        ),
        migrations.AddField(
            model_name="experience",
            name="achievements",
            field=models.JSONField(blank=True, default=list, help_text="List of bullet-point achievements"),
        ),
        migrations.AddField(
            model_name="experience",
            name="impact",
            field=models.TextField(blank=True, help_text="Short summary of measurable impact"),
        ),
        migrations.AddField(
            model_name="experience",
            name="order",
            field=models.SmallIntegerField(default=0),
        ),
        migrations.AlterModelOptions(
            name="experience",
            options={"ordering": ["order", "-start_date", "-end_date", "-id"]},
        ),
    ]
