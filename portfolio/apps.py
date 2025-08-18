from django.apps import AppConfig


class PortfolioConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "portfolio"

    def ready(self):  # pragma: no cover - side-effect setup
        # Wire a post_migrate hook to create the daily beat schedule once DB is ready
        try:
            from django.db.models.signals import post_migrate

            def _ensure_daily_task(sender, **kwargs):
                try:
                    from django.conf import settings
                    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
                        return
                    from django_celery_beat.models import PeriodicTask, CrontabSchedule

                    schedule, _ = CrontabSchedule.objects.get_or_create(
                        minute="0",
                        hour="3",
                        day_of_week="*",
                        day_of_month="*",
                        month_of_year="*",
                        timezone=settings.TIME_ZONE,
                    )
                    PeriodicTask.objects.get_or_create(
                        name="Daily knowledge refresh",
                        task="portfolio.tasks.refresh_knowledge",
                        crontab=schedule,
                        defaults={"enabled": True},
                    )
                except Exception:
                    # Beat not installed/migrated yet or DB not ready; safe to ignore
                    pass

            post_migrate.connect(_ensure_daily_task, dispatch_uid="portfolio_daily_task")
        except Exception:
            pass
