from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from datetime import datetime, timedelta
from rest_framework import serializers
from .models import Client, Contact, Expense, Service, ServiceBooking, ServicePassenger, Stop, TouristGuide, Transfer, UserAccess, Vehicle
from .roles import PERMISSION_ACTIONS, PERMISSION_SECTIONS, effective_permissions

class ClientSerializer(serializers.ModelSerializer):
    class Meta: model=Client; fields='__all__'; read_only_fields=('created_at','updated_at')
class ContactSerializer(serializers.ModelSerializer):
    class Meta: model=Contact; fields='__all__'; read_only_fields=('created_at','updated_at')
class VehicleSerializer(serializers.ModelSerializer):
    unavailable_start = serializers.DateTimeField(required=False, allow_null=True)
    unavailable_end = serializers.DateTimeField(required=False, allow_null=True)

    class Meta: model=Vehicle; fields='__all__'; read_only_fields=('created_at','updated_at')
    def to_internal_value(self, data):
        data = data.copy()
        for field in ('unavailable_start', 'unavailable_end'):
            if data.get(field) == '':
                data[field] = None
        return super().to_internal_value(data)

    def validate(self, attrs):
        start = attrs.get('maintenance_start', getattr(self.instance, 'maintenance_start', None))
        end = attrs.get('maintenance_end', getattr(self.instance, 'maintenance_end', None))
        delegate = (attrs.get('delegate', getattr(self.instance, 'delegate', '')) or '').strip()
        delegate_license = (attrs.get('delegate_license_number', getattr(self.instance, 'delegate_license_number', '')) or '').strip()
        if start and end and end < start:
            raise serializers.ValidationError({'maintenance_end': 'La fecha final del mantenimiento no puede ser anterior a la inicial.'})
        unavailable_start = attrs.get('unavailable_start', getattr(self.instance, 'unavailable_start', None))
        unavailable_end = attrs.get('unavailable_end', getattr(self.instance, 'unavailable_end', None))
        if bool(unavailable_start) != bool(unavailable_end):
            raise serializers.ValidationError({'unavailable_end': 'Completa tanto la fecha y hora de inicio como la de fin.'})
        if unavailable_start and unavailable_end and unavailable_end <= unavailable_start:
            raise serializers.ValidationError({'unavailable_end': 'La fecha y hora de fin deben ser posteriores al inicio de la indisponibilidad.'})
        if attrs.get('capacity', getattr(self.instance, 'capacity', 1)) < 1:
            raise serializers.ValidationError({'capacity': 'La unidad debe tener al menos un asiento de capacidad.'})
        driver_details_changed = self.instance is None or 'delegate' in attrs or 'delegate_license_number' in attrs
        if driver_details_changed and delegate and not delegate_license:
            raise serializers.ValidationError({'delegate_license_number': 'Registra la licencia del conductor delegado.'})
        return attrs
class TouristGuideSerializer(serializers.ModelSerializer):
    unavailable_start = serializers.DateField(required=False, allow_null=True)
    unavailable_end = serializers.DateField(required=False, allow_null=True)

    class Meta: model=TouristGuide; fields='__all__'; read_only_fields=('created_at','updated_at')

    def to_internal_value(self, data):
        data = data.copy()
        for field in ('unavailable_start', 'unavailable_end'):
            if data.get(field) == '':
                data[field] = None
        return super().to_internal_value(data)

    def validate(self, attrs):
        start = attrs.get('unavailable_start', getattr(self.instance, 'unavailable_start', None))
        end = attrs.get('unavailable_end', getattr(self.instance, 'unavailable_end', None))
        if bool(start) != bool(end):
            raise serializers.ValidationError({'unavailable_end': 'Indica tanto el primer como el último día de indisponibilidad.'})
        if start and end and end < start:
            raise serializers.ValidationError({'unavailable_end': 'El fin de la indisponibilidad no puede ser anterior al inicio.'})
        reason = attrs.get('unavailable_reason', getattr(self.instance, 'unavailable_reason', '')).strip()
        if start and not reason:
            raise serializers.ValidationError({'unavailable_reason': 'Indica el motivo de la indisponibilidad por fechas.'})
        if attrs.get('status', getattr(self.instance, 'status', 'Disponible')) == 'No disponible' and not reason:
            raise serializers.ValidationError({'unavailable_reason': 'Indica el motivo por el que el guía no estará disponible.'})
        return attrs

class StopSerializer(serializers.ModelSerializer):
    class Meta: model=Stop; fields=('id','position','name','arrival_time','duration_minutes','latitude','longitude','notes')

class ServicePassengerSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServicePassenger
        exclude = ('service', 'booking', 'created_at', 'updated_at')

    def validate(self, attrs):
        instance = self.instance
        for status_key, method_key in (('payment_status', 'payment_method'), ('guardian_payment_status', 'guardian_payment_method')):
            status = attrs.get(status_key, getattr(instance, status_key, 'Pendiente'))
            method = attrs.get(method_key, getattr(instance, method_key, ''))
            if status == 'Pagado' and not method:
                raise serializers.ValidationError({method_key: 'Selecciona el medio de pago para registrar un pago confirmado.'})
        return attrs

class ServiceBookingSerializer(serializers.ModelSerializer):
    passengers = ServicePassengerSerializer(many=True, read_only=True)
    total_amount = serializers.SerializerMethodField()
    class Meta:
        model = ServiceBooking
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at', 'ticket_price', 'drone_price', 'passenger_count', 'drone_passengers', 'total_amount')
    def get_total_amount(self, obj):
        return obj.passenger_count * obj.ticket_price + obj.drone_passengers * obj.drone_price

class ServiceSerializer(serializers.ModelSerializer):
    stops = StopSerializer(many=True, required=False)
    passengers = ServicePassengerSerializer(many=True, required=False)
    bookings = ServiceBookingSerializer(many=True, read_only=True)
    reminder_users = serializers.PrimaryKeyRelatedField(many=True, queryset=get_user_model().objects.filter(is_active=True), required=False)
    reminder_user_details = serializers.SerializerMethodField()
    client_display = serializers.SerializerMethodField()
    vehicle_display = serializers.SerializerMethodField()
    vehicle_capacity = serializers.SerializerMethodField()
    total_price = serializers.SerializerMethodField()
    class Meta: model=Service; fields='__all__'; read_only_fields=('created_at','updated_at','client_display','vehicle_display','reminder_user_details')
    def get_reminder_user_details(self, obj):
        return [{'id': u.id, 'username': u.username, 'name': u.get_full_name() or u.username} for u in obj.reminder_users.all()]
    def get_client_display(self,obj): return obj.client.name if obj.client_id else obj.client_name
    def get_vehicle_display(self,obj): return str(obj.vehicle) if obj.vehicle_id else obj.vehicle_name
    def get_vehicle_capacity(self,obj): return obj.vehicle.capacity if obj.vehicle_id else 0
    def get_total_price(self,obj):
        if obj.type == 'Tour público':
            return obj.people * obj.price + obj.drone_passengers * obj.drone_price
        return obj.price + (obj.drone_price if obj.drone else 0)
    def validate(self, attrs):
        instance = self.instance
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        can_manage_drone_price = bool(user and user.is_authenticated and (user.is_superuser or user.groups.filter(name='Administrador').exists() or effective_permissions(user).get('services', {}).get('edit', False)))
        passengers = attrs.get('passengers')
        service_type = attrs.get('type', getattr(instance, 'type', ''))
        is_public_departure = service_type == 'Tour público'
        if is_public_departure and not attrs.get('vehicle', getattr(instance, 'vehicle', None)):
            raise serializers.ValidationError({'vehicle': 'Asigna una unidad con capacidad para administrar los cupos de esta salida pública.'})
        selected_drone_passengers = sum(
            int(bool(passenger.get('drone'))) + int(bool(passenger.get('guardian_drone') and passenger.get('guardian_name')))
            for passenger in (passengers or [])
        )
        if passengers is not None:
            if 'drone_passengers' in attrs and attrs['drone_passengers'] != selected_drone_passengers:
                raise serializers.ValidationError({'passengers': 'El número de pasajeros con dron debe coincidir con las casillas marcadas en el manifiesto.'})
            if 'drone' in attrs and bool(attrs['drone']) != (selected_drone_passengers > 0):
                raise serializers.ValidationError({'passengers': 'Marca el dron en cada pasajero que solicite el servicio.'})
            attrs['drone_passengers'] = selected_drone_passengers
            attrs['drone'] = selected_drone_passengers > 0
        drone = attrs.get('drone', getattr(instance, 'drone', False))
        drone_details_touched = instance is None or any(key in attrs for key in ('drone', 'drone_price', 'drone_passengers', 'passengers'))
        if (drone or attrs.get('drone_price', 0) > 0 or attrs.get('drone_passengers', 0) > 0) and not can_manage_drone_price:
            raise serializers.ValidationError({'drone': 'Solo administración o usuarios con permiso para editar servicios pueden gestionar el precio del dron.'})
        if drone_details_touched:
            if drone:
                drone_price = attrs.get('drone_price', getattr(instance, 'drone_price', 0))
                drone_passengers = attrs.get('drone_passengers', getattr(instance, 'drone_passengers', 0))
                people = attrs.get('people', getattr(instance, 'people', 1))
                if drone_price < 0:
                    raise serializers.ValidationError({'drone_price': 'El precio del servicio de dron no puede ser negativo.'})
                if passengers is not None and drone_passengers != selected_drone_passengers:
                    raise serializers.ValidationError({'passengers': 'Marca el dron en cada pasajero que solicite el servicio.'})
                if drone_passengers < 1:
                    raise serializers.ValidationError({'drone_passengers': 'Marca qué pasajeros usarán el servicio de dron.'})
                if drone_passengers > people:
                    raise serializers.ValidationError({'drone_passengers': f'No puede superar la cantidad de pasajeros del servicio ({people}).'})
            elif not is_public_departure:
                attrs['drone_price'] = 0
                attrs['drone_passengers'] = 0
        service_date = attrs.get('date', getattr(instance, 'date', None))
        service_time = attrs.get('time', getattr(instance, 'time', None))
        duration = attrs.get('duration_minutes', getattr(instance, 'duration_minutes', 120))
        driver = (attrs.get('driver', getattr(instance, 'driver', '')) or '').strip().casefold()
        vehicle = attrs.get('vehicle', getattr(instance, 'vehicle', None))
        guide = attrs.get('tour_guide', getattr(instance, 'tour_guide', None))
        status = attrs.get('status', getattr(instance, 'status', 'Pendiente'))
        license_number = attrs.get('driver_license_number', getattr(instance, 'driver_license_number', ''))
        if 'driver' in attrs and driver and not license_number.strip():
            raise serializers.ValidationError({'driver_license_number': 'Registra el número de licencia del conductor asignado.'})
        if guide and status not in ('Cancelado', 'Completado'):
            if guide.status != 'Disponible':
                raise serializers.ValidationError({'tour_guide': f'{guide.full_name} está marcado como no disponible: {guide.unavailable_reason or "sin motivo registrado"}.'})
            if service_date and ((guide.unavailable_start and service_date >= guide.unavailable_start) or (guide.unavailable_end and service_date <= guide.unavailable_end)):
                raise serializers.ValidationError({'tour_guide': f'{guide.full_name} no está disponible ese día: {guide.unavailable_reason or "indisponibilidad registrada"}.'})
        vehicle_changed = any(key in attrs for key in ('vehicle', 'date', 'time', 'duration_minutes', 'people', 'driver')) or instance is None
        if vehicle_changed and vehicle:
            if vehicle.status in ('Mantenimiento', 'No disponible'):
                raise serializers.ValidationError({'vehicle': f'La unidad está marcada como {vehicle.status.lower()} y no puede asignarse a un servicio.'})
            if service_date:
                if not service_time:
                    return attrs
                service_start = datetime.combine(service_date, service_time)
                service_end = service_start + timedelta(minutes=duration)
                if vehicle.unavailable_start and vehicle.unavailable_end:
                    block_start = vehicle.unavailable_start
                    block_end = vehicle.unavailable_end
                    from django.utils import timezone
                    service_start = timezone.make_aware(service_start) if timezone.is_naive(service_start) else service_start
                    service_end = timezone.make_aware(service_end) if timezone.is_naive(service_end) else service_end
                    if service_start < block_end and service_end > block_start:
                        reason = vehicle.availability_notes or 'indisponibilidad programada'
                        if 'manten' in reason.casefold() or 'maten' in reason.casefold():
                            raise serializers.ValidationError({'vehicle': f'La unidad está en mantenimiento en ese horario: {reason}.'})
                        raise serializers.ValidationError({'vehicle': f'La unidad no está disponible en ese horario ({reason}).'})
                if vehicle.technical_review_due and service_date > vehicle.technical_review_due:
                    raise serializers.ValidationError({'vehicle': f'La revisión técnica vence el {vehicle.technical_review_due}; el servicio está programado después de esa fecha.'})
                if vehicle.insurance_due and service_date > vehicle.insurance_due:
                    raise serializers.ValidationError({'vehicle': f'El SOAT / seguro vence el {vehicle.insurance_due}; el servicio está programado después de esa fecha.'})
                after_start = not vehicle.maintenance_start or service_date >= vehicle.maintenance_start
                before_end = not vehicle.maintenance_end or service_date <= vehicle.maintenance_end
                if (vehicle.maintenance_start or vehicle.maintenance_end) and after_start and before_end:
                    raise serializers.ValidationError({'vehicle': f'La unidad está en mantenimiento ({vehicle.maintenance_start or "sin inicio"} al {vehicle.maintenance_end or "sin fin"}).'})
            people = attrs.get('people', getattr(instance, 'people', 1))
            if people > vehicle.capacity:
                raise serializers.ValidationError({'people': f'La unidad tiene capacidad para {vehicle.capacity} pasajeros.'})
        if passengers is not None:
            expected_people = attrs.get('people', getattr(instance, 'people', 1))
            companions = [passenger for passenger in passengers if (passenger.get('guardian_name') or '').strip()]
            attendee_count = len(passengers) + len(companions)
            if attendee_count != expected_people:
                raise serializers.ValidationError({'passengers': f'Registra los {expected_people} asientos de la reserva, incluyendo a los acompañantes.'})
            seats = [passenger.get('seat_number') for passenger in passengers]
            seats.extend(companion.get('guardian_seat_number') for companion in companions)
            if any(seat is None or seat < 1 for seat in seats):
                raise serializers.ValidationError({'passengers': 'Asigna un número de asiento válido al pasajero y a cada acompañante registrado.'})
            if len(seats) != len(set(seats)):
                raise serializers.ValidationError({'passengers': 'No puedes asignar el mismo asiento a más de un pasajero.'})
            for index, passenger in enumerate(passengers, start=1):
                if not passenger.get('document_number') or passenger.get('age') is None:
                    raise serializers.ValidationError({'passengers': f'Completa documento y edad del pasajero {index} para generar su manifiesto.'})
                if passenger.get('age', 0) < 18:
                    has_guardian = bool(passenger.get('guardian_name'))
                    if has_guardian and not (passenger.get('guardian_relationship') and passenger.get('guardian_document_number') and passenger.get('guardian_seat_number')):
                        raise serializers.ValidationError({'passengers': f'Completa documento, asiento y parentesco del acompañante del menor {index}.'})
                    if not has_guardian and not passenger.get('authorization_reference'):
                        raise serializers.ValidationError({'passengers': f'Registra un acompañante con asiento o la autorización si el menor {index} viaja solo.'})
            if vehicle and any(seat > vehicle.capacity for seat in seats):
                raise serializers.ValidationError({'passengers': f'Los asientos no pueden superar la capacidad de la unidad ({vehicle.capacity}).'})
            people = attrs.get('people', getattr(instance, 'people', 1))
            if len(passengers) > people:
                raise serializers.ValidationError({'passengers': 'El manifiesto tiene más pasajeros que los indicados en la reserva.'})
        if not service_date or not service_time or not duration or status in ('Cancelado', 'Completado'):
            return attrs

        start = datetime.combine(service_date, service_time)
        end = start + timedelta(minutes=duration)
        candidates = Service.objects.filter(date=service_date).exclude(status__in=('Cancelado', 'Completado'))
        if instance:
            candidates = candidates.exclude(pk=instance.pk)
        for other in candidates:
            other_start = datetime.combine(other.date, other.time)
            other_end = other_start + timedelta(minutes=other.duration_minutes or 120)
            if start >= other_end or end <= other_start:
                continue
            same_driver = bool(driver and other.driver and driver == other.driver.strip().casefold())
            same_vehicle = bool(vehicle and other.vehicle_id == vehicle.pk)
            same_guide = bool(guide and other.tour_guide_id == guide.pk)
            if same_driver or same_vehicle or same_guide:
                assigned = 'conductor, unidad y guía' if same_driver and same_vehicle and same_guide else 'conductor y unidad' if same_driver and same_vehicle else 'conductor y guía' if same_driver and same_guide else 'unidad y guía' if same_vehicle and same_guide else 'guía turístico' if same_guide else 'conductor' if same_driver else 'unidad'
                raise serializers.ValidationError({
                    'schedule': f"Se cruza con «{other.name}» ({other.time.strftime('%H:%M')}); ya tiene asignado el mismo {assigned}. Ajusta la hora, duración o asignación."
                })
        return attrs
    @transaction.atomic
    def create(self,validated_data):
        stops=validated_data.pop('stops',[]); passengers=validated_data.pop('passengers',[]); reminder_users=validated_data.pop('reminder_users',None)
        guide=validated_data.get('tour_guide')
        if guide:
            validated_data.update(guide_name=guide.full_name, guide_document_number=guide.dni, guide_card_number=guide.carnet)
        if passengers:
            validated_data['passenger_names']='\n'.join(name for passenger in passengers for name in (passenger['full_name'], passenger.get('guardian_name', '')) if name)
        obj=Service.objects.create(**validated_data)
        if reminder_users is not None:
            obj.reminder_users.set(reminder_users)
        for i,stop in enumerate(stops): Stop.objects.create(service=obj,position=stop.pop('position',i),**stop)
        for i,passenger in enumerate(passengers):
            position = passenger.pop('position', i)
            ServicePassenger.objects.create(service=obj,position=position,**passenger)
        return obj
    @transaction.atomic
    def update(self,instance,validated_data):
        stops=validated_data.pop('stops',None)
        passengers=validated_data.pop('passengers',None)
        reminder_users=validated_data.pop('reminder_users',None)
        if 'tour_guide' in validated_data:
            guide=validated_data['tour_guide']
            validated_data.update(guide_name=guide.full_name if guide else '', guide_document_number=guide.dni if guide else '', guide_card_number=guide.carnet if guide else '')
        for k,v in validated_data.items(): setattr(instance,k,v)
        instance.save()
        if reminder_users is not None:
            instance.reminder_users.set(reminder_users)
        if stops is not None:
            instance.stops.all().delete()
            for i,stop in enumerate(stops): Stop.objects.create(service=instance,position=stop.pop('position',i),**stop)
        if passengers is not None:
            instance.passengers.all().delete()
            for i,passenger in enumerate(passengers):
                position = passenger.pop('position', i)
                ServicePassenger.objects.create(service=instance,position=position,**passenger)
            instance.passenger_names='\n'.join(name for passenger in passengers for name in (passenger['full_name'], passenger.get('guardian_name', '')) if name)
            instance.save(update_fields=['passenger_names','updated_at'])
        return instance
class TransferSerializer(serializers.ModelSerializer):
    reminder_users = serializers.PrimaryKeyRelatedField(many=True, queryset=get_user_model().objects.filter(is_active=True), required=False)
    reminder_user_details = serializers.SerializerMethodField()
    class Meta: model=Transfer; fields='__all__'; read_only_fields=('created_at','updated_at','reminder_user_details')
    def get_reminder_user_details(self, obj):
        return [{'id': u.id, 'username': u.username, 'name': u.get_full_name() or u.username} for u in obj.reminder_users.all()]
class ExpenseSerializer(serializers.ModelSerializer):
    class Meta: model=Expense; fields='__all__'; read_only_fields=('created_at','updated_at')
class UserSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(choices=('Administrador', 'Jefe', 'Encargado', 'Operaciones'), write_only=True)
    full_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    name = serializers.SerializerMethodField()
    role_name = serializers.SerializerMethodField()
    password = serializers.CharField(write_only=True, required=False, min_length=8)
    permissions = serializers.JSONField(write_only=True, required=False)

    class Meta:
        model = get_user_model()
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'full_name', 'name', 'is_active', 'role', 'role_name', 'password', 'permissions')
        read_only_fields = ('id', 'name', 'role_name')

    def get_name(self, obj):
        return obj.get_full_name() or obj.username

    def get_role_name(self, obj):
        if obj.is_superuser or obj.groups.filter(name='Administrador').exists():
            return 'Administrador'
        return obj.groups.values_list('name', flat=True).first() or 'Operaciones'

    def validate_permissions(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError('Los permisos deben enviarse como un objeto por módulo.')
        clean = {}
        for section in PERMISSION_SECTIONS:
            section_permissions = value.get(section, {})
            if not isinstance(section_permissions, dict):
                raise serializers.ValidationError(f'Los permisos de {section} no tienen un formato válido.')
            clean[section] = {action: bool(section_permissions.get(action, False)) for action in PERMISSION_ACTIONS}
        clean['reports'] = {'view': clean['services']['view'] and clean['expenses']['view']}
        return clean

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['permissions'] = effective_permissions(instance)
        return data

    def _assign_role(self, user, role):
        group, _ = Group.objects.get_or_create(name=role)
        user.groups.set([group])
        user.is_staff = role == 'Administrador'
        user.save(update_fields=('is_staff',))

    def create(self, validated_data):
        User = get_user_model()
        role = validated_data.pop('role')
        password = validated_data.pop('password', None)
        permissions = validated_data.pop('permissions', None)
        if not password:
            raise serializers.ValidationError({'password': 'La contraseña es obligatoria.'})
        full_name = validated_data.pop('full_name', '').strip()
        if full_name:
            parts = full_name.split()
            validated_data.setdefault('first_name', parts[0])
            validated_data.setdefault('last_name', ' '.join(parts[1:]))
        user = User.objects.create_user(password=password, **validated_data)
        self._assign_role(user, role)
        if permissions is not None:
            UserAccess.objects.create(user=user, permissions=permissions)
        return user

    def update(self, instance, validated_data):
        role = validated_data.pop('role', None)
        password = validated_data.pop('password', None)
        permissions = validated_data.pop('permissions', None)
        full_name = validated_data.pop('full_name', '').strip()
        if full_name:
            parts = full_name.split()
            validated_data.setdefault('first_name', parts[0])
            validated_data.setdefault('last_name', ' '.join(parts[1:]))
        for key, value in validated_data.items():
            setattr(instance, key, value)
        if password:
            instance.set_password(password)
        instance.save()
        if role:
            self._assign_role(instance, role)
        if permissions is not None:
            UserAccess.objects.update_or_create(user=instance, defaults={'permissions': permissions})
        return instance
