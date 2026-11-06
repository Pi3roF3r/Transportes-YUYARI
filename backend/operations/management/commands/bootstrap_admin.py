import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Crea o prepara el administrador principal.'

    def add_arguments(self, parser):
        parser.add_argument('--reset-password', action='store_true', help='Restablece la contraseña con DJANGO_ADMIN_PASSWORD.')

    def handle(self, *args, **options):
        User = get_user_model()
        reset_password = options['reset_password']
        exists = User.objects.filter(username='admin').exists()
        password = os.environ.get('DJANGO_ADMIN_PASSWORD')
        needs_password = reset_password or not exists
        if needs_password and not password and not settings.DEBUG:
            raise CommandError('Define DJANGO_ADMIN_PASSWORD para crear o restablecer el administrador en producción.')

        user, created = User.objects.get_or_create(username='admin')
        user.first_name = 'Administrador'
        user.last_name = 'principal'
        user.email = user.email or 'admin@yuyari.pe'
        user.is_active = True
        user.is_staff = True
        user.is_superuser = True
        if created or reset_password:
            user.set_password(password or 'admin123')
        user.save()
        action = 'creado' if created else ('contraseña restablecida' if reset_password else 'verificado; contraseña conservada')
        self.stdout.write(self.style.SUCCESS(f'Usuario administrador {action}: admin'))
