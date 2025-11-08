from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portfolio", "0008_project_github_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="readme_excerpt",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="project",
            name="license_spdx",
            field=models.CharField(max_length=40, blank=True),
        ),
        migrations.AddField(
            model_name="project",
            name="license_name",
            field=models.CharField(max_length=120, blank=True),
        ),
        migrations.AddField(
            model_name="project",
            name="open_issues",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="project",
            name="watchers",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="project",
            name="default_branch",
            field=models.CharField(max_length=80, blank=True),
        ),
        migrations.AddField(
            model_name="project",
            name="latest_release_tag",
            field=models.CharField(max_length=100, blank=True),
        ),
        migrations.AddField(
            model_name="project",
            name="latest_release_published",
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="project",
            name="is_archived",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="project",
            name="is_template",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="project",
            name="has_ci",
            field=models.BooleanField(default=False),
        ),
    ]
