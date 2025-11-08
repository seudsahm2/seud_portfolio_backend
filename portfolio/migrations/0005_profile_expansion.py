from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('portfolio', '0004_chatlog_answer_json'),  # corrected parent migration name
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Remove redundant fields
        migrations.RemoveField(
            model_name='profile',
            name='full_name',
        ),
        migrations.RemoveField(
            model_name='profile',
            name='email',
        ),
        # Add linkage to user (staff)
        migrations.AddField(
            model_name='profile',
            name='user',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='portfolio_profile', to=settings.AUTH_USER_MODEL),
        ),
        # New profile fields
        migrations.AddField(
            model_name='profile',
            name='tagline',
            field=models.CharField(blank=True, max_length=180),
        ),
        migrations.AddField(
            model_name='profile',
            name='primary_stack',
            field=models.CharField(blank=True, help_text='Short comma-separated primary stack', max_length=200),
        ),
        migrations.AddField(
            model_name='profile',
            name='years_experience',
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='profile',
            name='open_to_opportunities',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='profile',
            name='avatar',
            # Use default migration serialization (runtime model supplies custom Supabase storage)
            field=models.ImageField(blank=True, null=True, upload_to='profile/'),
        ),
        migrations.AddField(
            model_name='profile',
            name='avatar_url',
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name='profile',
            name='socials',
            field=models.JSONField(blank=True, default=dict, help_text='e.g. {github, linkedin, twitter, website}'),
        ),
        migrations.AddField(
            model_name='profile',
            name='highlights',
            field=models.JSONField(blank=True, default=list, help_text='List of short bullet points to showcase'),
        ),
    ]
