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
    delegate_license_number = models.CharField(max_length=40, blank=True)
    status = models.CharField(max_length=40, default='Disponible')
    maintenance_start = models.DateField(null=True, blank=True)
    maintenance_end = models.DateField(null=True, blank=True)
    maintenance_notes = models.TextField(blank=True)
    unavailable_start = models.DateTimeField(null=True, blank=True)
    unavailable_end = models.DateTimeField(null=True, blank=True)
    availability_notes = models.TextField(blank=True)
    technical_review_due = models.DateField(null=True, blank=True)
    insurance_due = models.DateField(null=True, blank=True)
    provider = models.ForeignKey(Contact, null=True, blank=True, on_delete=models.SET_NULL, related_name='vehicles')
    def __str__(self): return f'{self.name} ({self.plate})'

class TouristGuide(Timestamped):
    STATUSES = [('Disponible', 'Disponible'), ('No disponible', 'No disponible')]
    full_name = models.CharField(max_length=180)
    dni = models.CharField(max_length=40, blank=True)
    carnet = models.CharField(max_length=60, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    status = models.CharField(max_length=30, choices=STATUSES, default='Disponible')
    unavailable_start = models.DateField(null=True, blank=True)
    unavailable_end = models.DateField(null=True, blank=True)
    unavailable_reason = models.TextField(blank=True)

    def __str__(self): return self.full_name

class Service(Timestamped):
    TYPES = [(v,v) for v in ['Tour privado','Tour público','Expreso','Taxi huésped','Traslado de personal','Logística']]
    STATUSES = [(v,v) for v in ['Pendiente','Confirmado','Completado','Cancelado']]
    JOURNEY_STATUSES = [(v,v) for v in ['Pendiente','En curso','En retorno','Completado']]
    name = models.CharField(max_length=180)
    type = models.CharField(max_length=50, choices=TYPES)
    trip_mode = models.CharField(max_length=30, blank=True, help_text='Solo ida o ida y vuelta para expreso')
    return_required = models.BooleanField(default=True)
    journey_status = models.CharField(max_length=20, choices=JOURNEY_STATUSES, default='Pendiente')
    journey_leg = models.CharField(max_length=12, blank=True, default='')
    journey_step = models.PositiveSmallIntegerField(default=0)
    journey_events = models.JSONField(default=list, blank=True)
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
    manifest_code = models.CharField(max_length=60, blank=True)
    transport_company = models.CharField(max_length=180, blank=True)
    manifest_responsible = models.CharField(max_length=180, blank=True)
    guide_name = models.CharField(max_length=180, blank=True)
    guide_document_number = models.CharField(max_length=40, blank=True)
    guide_card_number = models.CharField(max_length=40, blank=True)
    tour_guide = models.ForeignKey(TouristGuide, null=True, blank=True, on_delete=models.SET_NULL, related_name='services')
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


class ServiceBooking(Timestamped):
    PAYMENT_STATUSES = [('Pendiente', 'Pendiente'), ('Pagado', 'Pagado')]
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='bookings')
    client = models.ForeignKey(Client, null=True, blank=True, on_delete=models.SET_NULL, related_name='service_bookings')
    contact_name = models.CharField(max_length=180)
    contact_phone = models.CharField(max_length=40, blank=True)
    passenger_count = models.PositiveSmallIntegerField(default=1)
    drone_passengers = models.PositiveSmallIntegerField(default=0)
    ticket_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    drone_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUSES, default='Pendiente')

    def __str__(self): return f'{self.contact_name} · Servicio {self.service_id}'


class ServicePassenger(Timestamped):
    DOCUMENT_TYPES = [('DNI', 'DNI'), ('Pasaporte', 'Pasaporte'), ('Carné de extranjería', 'Carné de extranjería'), ('Otro', 'Otro')]
    PAYMENT_STATUSES = [('Pendiente', 'Pendiente'), ('Pagado', 'Pagado')]
    PAYMENT_METHODS = [('', 'Sin registrar'), ('Efectivo', 'Efectivo'), ('Yape', 'Yape'), ('Plin', 'Plin'), ('Transferencia', 'Transferencia'), ('Tarjeta', 'Tarjeta'), ('Otro', 'Otro')]
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='passengers')
    booking = models.ForeignKey('ServiceBooking', null=True, blank=True, on_delete=models.CASCADE, related_name='passengers')
    position = models.PositiveSmallIntegerField(default=0)
    full_name = models.CharField(max_length=180)
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPES, default='DNI')
    document_number = models.CharField(max_length=40, blank=True)
    age = models.PositiveSmallIntegerField(null=True, blank=True)
    country = models.CharField(max_length=100, blank=True, default='Perú')
    sale_code = models.CharField(max_length=60, blank=True)
    tour_name = models.CharField(max_length=180, blank=True)
    passenger_type = models.CharField(max_length=100, blank=True)
    agency = models.CharField(max_length=180, blank=True)
    booked_by = models.CharField(max_length=180, blank=True)
    btc = models.CharField(max_length=40, blank=True)
    bter = models.CharField(max_length=40, blank=True)
    food = models.CharField(max_length=80, blank=True)
    passenger_origin = models.CharField(max_length=180, blank=True)
    passenger_destination = models.CharField(max_length=180, blank=True)
    accommodation = models.CharField(max_length=180, blank=True)
    manifest_notes = models.TextField(blank=True)
    manifest_description = models.TextField(blank=True)
    seat_number = models.PositiveSmallIntegerField(null=True, blank=True)
    drone = models.BooleanField(default=False)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUSES, default='Pendiente')
    payment_method = models.CharField(max_length=30, choices=PAYMENT_METHODS, blank=True, default='')
    phone = models.CharField(max_length=40, blank=True)
    guardian_name = models.CharField(max_length=180, blank=True)
    guardian_document_number = models.CharField(max_length=40, blank=True)
    guardian_seat_number = models.PositiveSmallIntegerField(null=True, blank=True)
    guardian_relationship = models.CharField(max_length=80, blank=True)
    guardian_drone = models.BooleanField(default=False)
    guardian_payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUSES, default='Pendiente')
    guardian_payment_method = models.CharField(max_length=30, choices=PAYMENT_METHODS, blank=True, default='')
    authorization_reference = models.CharField(max_length=180, blank=True)

    class Meta:
        ordering = ['position', 'seat_number', 'full_name']

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.sale_code:
            self.sale_code = f'VTA-{self.pk:06d}'
            type(self).objects.filter(pk=self.pk, sale_code='').update(sale_code=self.sale_code)

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
    STATUSES = [('Programado', 'Programado'), ('En camino', 'En camino'), ('Llegó al destino', 'Llegó al destino'), ('Cancelado', 'Cancelado')]
    title = models.CharField(max_length=180)
    datetime = models.DateTimeField()
    place = models.CharField(max_length=240)
    responsible = models.CharField(max_length=180, blank=True)
    reminders = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=40, choices=STATUSES, default='Programado')
    departed_at = models.DateTimeField(null=True, blank=True)
    arrived_at = models.DateTimeField(null=True, blank=True)
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
