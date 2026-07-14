#!/bin/sh
set -e

echo "Applying database migrations..."
python manage.py migrate --noinput

python manage.py shell -c "
from django.contrib.auth.models import User
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser('admin', 'admin@brigadir.local', 'admin123')
    print('=== Created admin user: login=admin password=admin123 (change if you expose this publicly) ===')
"

echo "Starting Brigadir.Pro on http://0.0.0.0:8000/"
exec python manage.py runserver 0.0.0.0:8000
