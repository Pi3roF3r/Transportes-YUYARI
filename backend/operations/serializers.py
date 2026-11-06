from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from datetime import datetime, timedelta
from rest_framework import serializers
from .models import Client, Contact, Expense, Service, ServicePassenger, Stop, Transfer, UserAccess, Vehicle
from .roles import PERMISSION_ACTIONS, PERMISSION_SECTIONS, effective_permissions

class ClientSerializer(serializers.ModelSerializer):
    class Meta: model=Client; fields='__all__'; read_only_fields=('created_at','updated_at')
class ContactSerializer(serializers.ModelSerializer):
    class Meta: model=Contact; fields='__all__'; read_only_fields=('created_at','updated_at')
class VehicleSerializer(serializers.ModelSerializer):
    class Meta: model=Vehicle; fields='__all__'; read_only_fields=('created_at','updated_at')
    def validate(self, attrs):
        start = attrs.get('maintenance_start', getattr(self.instance, 'maintenance_start', None))
        end = attrs.get('maintenance_end', getattr(self.instance, 'maintenance_end', None))
        delegate = (attrs.get('delegate', getattr(self.instance, 'delegate', '')) or '').strip()
        delegate_license = (attrs.get('delegate_license_number', getattr(self.instance, 'delegate_license_number', '')) or '').strip()
        if start and end and end < start:
            raise serializers.ValidationError({'maintenance_end': 'La fecha final del mantenimiento no puede ser anterior a la inicial.'})
        if attrs.get('capacity', getattr(self.instance, 'capacity', 1)) < 1:
            raise serializers.ValidationError({'capacity': 'La unidad debe tener al menos un asiento de capacidad.'})
        driver_details_changed = self.instance is None or 'delegate' in attrs or 'delegate_license_number' in attrs
        if driver_details_changed and delegate and not delegate_license:
            raise serializers.ValidationError({'delegate_license_number': 'Registra la licencia del conductor delegado.'})
        return attrs
class StopSerializer(serializers.ModelSerializer):
    class Meta: model=Stop; fields=('id','position','name','arrival_time','duration_minutes','latitude','longitude','notes')

class ServicePassengerSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServicePassenger
        exclude = ('service', 'created_at', 'updated_at')

class ServiceSerializer(serializers.ModelSerializer):
    stops = StopSerializer(many=True, required=False)
    passengers = ServicePassengerSerializer(many=True, required=False)
    client_display = serializers.SerializerMethodField()
    vehicle_display = serializers.SerializerMethodField()
    total_price = serializers.SerializerMethodField()
    class Meta: model=Service; fields='__all__'; read_only_fields=('created_at','updated_at','client_display','vehicle_display')
    def get_client_display(self,obj): return obj.client.name if obj.client_id else obj.client_name
    def get_vehicle_display(self,obj): return str(obj.vehicle) if obj.vehicle_id else obj.vehicle_name
    def get_total_price(self,obj): return obj.price + (obj.drone_price if obj.drone else 0)
    def validate(self, attrs):
        instance = self.instance
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        can_manage_drone_price = bool(user and user.is_authenticated and (user.is_superuser or user.groups.filter(name='Administrador').exists() or effective_permissions(user).get('services', {}).get('edit', False)))
        drone = attrs.get('drone', getattr(instance, 'drone', False))
        drone_details_touched = instance is None or any(key in attrs for key in ('drone', 'drone_price', 'drone_passengers'))
        if (drone or 'drone_price' in attrs or 'drone_passengers' in attrs) and not can_manage_drone_price:
            raise serializers.ValidationError({'drone': 'Solo administración o usuarios con permiso para editar servicios pueden gestionar el precio del dron.'})
        if drone_details_touched:
            if drone:
                drone_price = attrs.get('drone_price', getattr(instance, 'drone_price', 0))
                drone_passengers = attrs.get('drone_passengers', getattr(instance, 'drone_passengers', 0))
                people = attrs.get('people', getattr(instance, 'people', 1))
                if drone_price < 0:
                    raise serializers.ValidationError({'drone_price': 'El precio del servicio de dron no puede ser negativo.'})
                if drone_passengers < 1:
                    raise serializers.ValidationError({'drone_passengers': 'Indica cuántos pasajeros usarán el servicio de dron.'})
                if drone_passengers > people:
                    raise serializers.ValidationError({'drone_passengers': f'No puede superar la cantidad de pasajeros del servicio ({people}).'})
            else:
                attrs['drone_price'] = 0
                attrs['drone_passengers'] = 0
        service_date = attrs.get('date', getattr(instance, 'date', None))
        service_time = attrs.get('time', getattr(instance, 'time', None))
        duration = attrs.get('duration_minutes', getattr(instance, 'duration_minutes', 120))
        driver = (attrs.get('driver', getattr(instance, 'driver', '')) or '').strip().casefold()
        vehicle = attrs.get('vehicle', getattr(instance, 'vehicle', None))
        status = attrs.get('status', getattr(instance, 'status', 'Pendiente'))
        license_number = attrs.get('driver_license_number', getattr(instance, 'driver_license_number', ''))
        if 'driver' in attrs and driver and not license_number.strip():
            raise serializers.ValidationError({'driver_license_number': 'Registra el número de licencia del conductor asignado.'})
        passengers = attrs.get('passengers')
        vehicle_changed = 'vehicle' in attrs or 'date' in attrs or 'people' in attrs or instance is None
        if vehicle_changed and vehicle:
            if vehicle.status == 'Mantenimiento':
                raise serializers.ValidationError({'vehicle': 'La unidad está marcada como En mantenimiento y no puede asignarse a un servicio.'})
            if service_date:
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
            if len(passengers) != expected_people:
                raise serializers.ValidationError({'passengers': f'Registra exactamente los {expected_people} pasajeros indicados en la reserva.'})
            seats = [passenger.get('seat_number') for passenger in passengers]
            if any(seat is None for seat in seats):
                raise serializers.ValidationError({'passengers': 'Asigna un número de asiento a cada pasajero del manifiesto.'})
            if len(seats) != len(set(seats)):
                raise serializers.ValidationError({'passengers': 'No puedes asignar el mismo asiento a más de un pasajero.'})
            for index, passenger in enumerate(passengers, start=1):
                if not passenger.get('document_number') or passenger.get('age') is None:
                    raise serializers.ValidationError({'passengers': f'Completa documento y edad del pasajero {index} para generar su manifiesto.'})
                if passenger.get('age', 0) < 18 and not ((passenger.get('guardian_name') and passenger.get('guardian_relationship')) or passenger.get('authorization_reference')):
                    raise serializers.ValidationError({'passengers': f'Registra acompañante y parentesco, o referencia de autorización si viaja solo, para el pasajero menor de edad {index}.'})
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
            if same_driver or same_vehicle:
                assigned = 'conductor y unidad' if same_driver and same_vehicle else 'conductor' if same_driver else 'unidad'
                raise serializers.ValidationError({
                    'schedule': f"Se cruza con «{other.name}» ({other.time.strftime('%H:%M')}); ya tiene asignado el mismo {assigned}. Ajusta la hora, duración o asignación."
                })
        return attrs
    @transaction.atomic
    def create(self,validated_data):
        stops=validated_data.pop('stops',[]); passengers=validated_data.pop('passengers',[])
        if passengers:
            validated_data['passenger_names']='\n'.join(passenger['full_name'] for passenger in passengers)
        obj=Service.objects.create(**validated_data)
        for i,stop in enumerate(stops): Stop.objects.create(service=obj,position=stop.pop('position',i),**stop)
        for i,passenger in enumerate(passengers): ServicePassenger.objects.create(service=obj,position=i,**passenger)
        return obj
    @transaction.atomic
    def update(self,instance,validated_data):
        stops=validated_data.pop('stops',None)
        passengers=validated_data.pop('passengers',None)
        for k,v in validated_data.items(): setattr(instance,k,v)
        instance.save()
        if stops is not None:
            instance.stops.all().delete()
            for i,stop in enumerate(stops): Stop.objects.create(service=instance,position=stop.pop('position',i),**stop)
        if passengers is not None:
            instance.passengers.all().delete()
            for i,passenger in enumerate(passengers): ServicePassenger.objects.create(service=instance,position=i,**passenger)
            instance.passenger_names='\n'.join(passenger['full_name'] for passenger in passengers)
            instance.save(update_fields=['passenger_names','updated_at'])
        return instance
class TransferSerializer(serializers.ModelSerializer):
    class Meta: model=Transfer; fields='__all__'; read_only_fields=('created_at','updated_at')
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
