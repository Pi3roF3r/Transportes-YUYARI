from django.conf import settings
from django.db import models

class Timestamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True

class Client(Timestamped):
    name = models.CharField(max_length=180)
    kind = models.CharField(max_length=40, default='Turista')
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    contact_person = models.CharField(max_length=180, blank=True)
    contact_phone = models.CharField(max_length=40, blank=True)
    whatsapp = models.CharField(max_length=40, blank=True)
    social_media = models.CharField(max_length=240, blank=True)
    origin = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    def __str__(self): return self.name

class Contact(Timestamped):
    name = models.CharField(max_length=180)
    kind = models.CharField(max_length=60)
    person = models.CharField(max_length=180, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    notes = models.TextField(blank=True)
    def __str__(self): return self.name

class Vehicle(Timestamped):
    name = models.CharField(max_length=120)
    plate = models.CharField(max_length=20, unique=True)
    owner = models.CharField(max_length=100, default='Propia')
    capacity = models.PositiveSmallIntegerField(default=1)
    delegate = models.CharField(max_length=160, blank=True)
    status = models.CharField(max_length=40, default='Disponible')
    maintenance_start = models.DateField(null=True, blank=True)
    maintenance_end = models.DateField(null=True, blank=True)
    maintenance_notes = models.TextField(blank=True)
    technical_review_due = models.DateField(null=True, blank=True)
    insurance_due = models.DateField(null=True, blank=True)
    provider = models.ForeignKey(Contact, null=True, blank=True, on_delete=models.SET_NULL, related_name='vehicles')
    def __str__(self): return f'{self.name} ({self.plate})'

class Service(Timestamped):
    TYPES = [(v,v) for v in ['Tour privado','Tour público','Expreso','Taxi huésped','Traslado de personal','Logística']]
    STATUSES = [(v,v) for v in ['Pendiente','Confirmado','Completado','Cancelado']]
    name = models.CharField(max_length=180)
    type = models.CharField(max_length=50, choices=TYPES)
    trip_mode = models.CharField(max_length=30, blank=True, help_text='Solo ida o ida y vuelta para expreso')
    date = models.DateField()
    time = models.TimeField()
    status = models.CharField(max_length=30, choices=STATUSES, default='Pendiente')
    client = models.ForeignKey(Client, null=True, blank=True, on_delete=models.SET_NULL, related_name='services')
    client_name = models.CharField(max_length=180, blank=True)
    people = models.PositiveSmallIntegerField(default=1)
    origin = models.CharField(max_length=200)
    destination = models.CharField(max_length=200)
    origin_latitude = models.FloatField(null=True, blank=True)
    origin_longitude = models.FloatField(null=True, blank=True)
    destination_latitude = models.FloatField(null=True, blank=True)
    destination_longitude = models.FloatField(null=True, blank=True)
    duration_minutes = models.PositiveSmallIntegerField(default=120)
    passenger_names = models.TextField(blank=True)
    pickup_instructions = models.TextField(blank=True)
    emergency_contact = models.CharField(max_length=180, blank=True)
    driver = models.CharField(max_length=180, blank=True)
    driver_license_number = models.CharField(max_length=40, blank=True)
    vehicle = models.ForeignKey(Vehicle, null=True, blank=True, on_delete=models.SET_NULL, related_name='services')
    vehicle_name = models.CharField(max_length=180, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    drone = models.BooleanField(default=False)
    drone_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    drone_passengers = models.PositiveSmallIntegerField(default=0)
    notes = models.TextField(blank=True)
    incident_log = models.TextField(blank=True)
    checklist = models.JSONField(default=dict, blank=True)
    def __str__(self): return f'{self.name} · {self.date}'


class ServicePassenger(Timestamped):
    DOCUMENT_TYPES = [('DNI', 'DNI'), ('Pasaporte', 'Pasaporte'), ('Carné de extranjería', 'Carné de extranjería'), ('Otro', 'Otro')]
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='passengers')
    position = models.PositiveSmallIntegerField(default=0)
    full_name = models.CharField(max_length=180)
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPES, default='DNI')
    document_number = models.CharField(max_length=40, blank=True)
    age = models.PositiveSmallIntegerField(null=True, blank=True)
    seat_number = models.PositiveSmallIntegerField(null=True, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    guardian_name = models.CharField(max_length=180, blank=True)
    guardian_relationship = models.CharField(max_length=80, blank=True)
    authorization_reference = models.CharField(max_length=180, blank=True)

    class Meta:
        ordering = ['position', 'seat_number', 'full_name']

    def __str__(self): return f'{self.full_name} · Servicio {self.service_id}'

class Stop(Timestamped):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='stops')
    position = models.PositiveSmallIntegerField(default=0)
    name = models.CharField(max_length=180)
    arrival_time = models.TimeField(null=True, blank=True)
    duration_minutes = models.PositiveSmallIntegerField(default=0)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    notes = models.TextField(blank=True)
    class Meta: ordering = ['position']

class Transfer(Timestamped):
    title = models.CharField(max_length=180)
    datetime = models.DateTimeField()
    place = models.CharField(max_length=240)
    responsible = models.CharField(max_length=180, blank=True)
    reminders = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=40, default='Programado')
    service = models.ForeignKey(Service, null=True, blank=True, on_delete=models.SET_NULL, related_name='transfers')
    def __str__(self): return self.title

class Expense(Timestamped):
    EXPENSE_KINDS = [('Gasto', 'Gasto'), ('Compra', 'Compra')]
    COST_TYPES = [('Variable', 'Variable'), ('Fijo', 'Fijo')]
    concept = models.CharField(max_length=180)
    category = models.CharField(max_length=60)
    expense_kind = models.CharField(max_length=20, choices=EXPENSE_KINDS, default='Gasto')
    cost_type = models.CharField(max_length=20, choices=COST_TYPES, default='Variable')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField()
    service = models.ForeignKey(Service, null=True, blank=True, on_delete=models.SET_NULL, related_name='expenses')
    service_name = models.CharField(max_length=180, blank=True)
    receipt = models.FileField(upload_to='receipts/%Y/%m/', blank=True)
    notes = models.TextField(blank=True)
    def __str__(self): return self.concept


class UserAccess(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='access_profile')
    permissions = models.JSONField(default=dict, blank=True)

    def __str__(self): return f'Permisos de {self.user.get_username()}'


class SystemSettings(models.Model):
    key = models.CharField(max_length=32, unique=True, default='main')
    values = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self): return 'Configuración de Yuyari'
