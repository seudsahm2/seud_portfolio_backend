web: gunicorn seud_portfolio_backend.wsgi:application --bind 0.0.0.0:$PORT --workers 3 --threads 2 --timeout 60
worker: celery -A seud_portfolio_backend worker -l info
beat: celery -A seud_portfolio_backend beat -l info
