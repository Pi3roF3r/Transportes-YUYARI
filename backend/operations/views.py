from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.decorators import api_view, permission_classes
from django.shortcuts import get_object_or_404
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from .models import Client, Contact, Expense, Service, ServiceBooking, ServicePassenger, SystemSettings, TouristGuide, Transfer, UserAccess, Vehicle
from .roles import ROLE_WRITES, effective_permissions, user_can_access, user_role
from .serializers import ClientSerializer, ContactSerializer, ExpenseSerializer, ServiceBookingSerializer, ServicePassengerSerializer, ServiceSerializer, TouristGuideSerializer, TransferSerializer, UserSerializer, VehicleSerializer


class RolePermission(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        section = view.section
        if not user_can_access(user, section):
            return False
        if request.method in permissions.SAFE_METHODS or user.is_superuser:
            if user.is_superuser:
                return True
        try:
            custom_permissions = user.access_profile.permissions
        except UserAccess.DoesNotExist:
            custom_permissions = None
        if custom_permissions is not None:
            action_name = getattr(view, 'action', '')
            action = {
                'list': 'view', 'retrieve': 'view', 'create': 'create',
                'update': 'edit', 'partial_update': 'edit', 'destroy': 'delete',
                'journey': 'edit',
                'booking_payment': 'edit',
                'movement': 'edit',
            }.get(action_name, 'view')
            if action_name == 'bookings':
                action = 'create' if request.method == 'POST' else 'view'
            return bool(effective_permissions(user).get(section, {}).get(action, False))
        if request.method in permissions.SAFE_METHODS:
            return True
        allowed = ROLE_WRITES.get(section, set()) | {'Administrador'}
        return user.groups.filter(name__in=allowed).exists()


class BaseViewSet(viewsets.ModelViewSet):
    permission_classes = [RolePermission]


class ClientViewSet(BaseViewSet):
    queryset=Client.objects.all().order_by('-created_at'); serializer_class=ClientSerializer; search_fields=['name','email','phone','origin']; ordering_fields=['created_at','name']; section='clients'
class ContactViewSet(BaseViewSet):
    queryset=Contact.objects.all().order_by('-created_at'); serializer_class=ContactSerializer; search_fields=['name','kind','person','phone']; section='contacts'
class VehicleViewSet(BaseViewSet):
    queryset=Vehicle.objects.select_related('provider').all().order_by('name'); serializer_class=VehicleSerializer; search_fields=['name','plate','owner','delegate']; section='vehicles'
class TouristGuideViewSet(BaseViewSet):
    queryset=TouristGuide.objects.all().order_by('full_name'); serializer_class=TouristGuideSerializer; search_fields=['full_name','dni','carnet','phone']; section='guides'
class ServiceViewSet(BaseViewSet):
    queryset=Service.objects.select_related('client','vehicle').prefetch_related('stops','passengers','bookings__passengers','reminder_users').all().order_by('date','time'); serializer_class=ServiceSerializer; search_fields=['name','client_name','origin','destination','driver','type']; section='services'

    @action(detail=True, methods=['get', 'post'])
    @transaction.atomic
    def bookings(self, request, pk=None):
        service = self.get_object()
        if request.method == 'GET':
            bookings = service.bookings.select_related('client').prefetch_related('passengers').order_by('-created_at')
            return Response(ServiceBookingSerializer(bookings, many=True).data)
        if service.type != 'Tour público':
            return Response({'detail': 'Las reservas individuales solo están disponibles en salidas de Tour público.'}, status=400)
        service = Service.objects.select_for_update().select_related('vehicle').get(pk=service.pk)
        if service.status in ('Cancelado', 'Completado') or service.journey_status != 'Pendiente':
            return Response({'detail': 'Esta salida ya no acepta nuevas reservas.'}, status=400)
        contact_name = str(request.data.get('contact_name', '')).strip()
        contact_phone = str(request.data.get('contact_phone', '')).strip()
        passenger_rows = request.data.get('passengers')
        if not contact_name:
            return Response({'contact_name': 'Indica quién realiza la reserva.'}, status=400)
        if not isinstance(passenger_rows, list) or not passenger_rows:
            return Response({'passengers': 'Agrega al menos un pasajero a la reserva.'}, status=400)
        if not service.vehicle_id:
            return Response({'vehicle': 'La salida no tiene una unidad con capacidad registrada.'}, status=400)

        cleaned = []
        used_seats = set()
        default_payment_status = request.data.get('payment_status') if request.data.get('payment_status') in ('Pagado', 'Pendiente') else 'Pendiente'
        default_payment_method = request.data.get('payment_method', '')
        for index, row in enumerate(passenger_rows, start=1):
            row = {**row}
            row.setdefault('payment_status', default_payment_status)
            row.setdefault('payment_method', default_payment_method)
            if (row.get('guardian_name') or '').strip():
                row.setdefault('guardian_payment_status', default_payment_status)
                row.setdefault('guardian_payment_method', default_payment_method)
            serializer = ServicePassengerSerializer(data=row)
            if not serializer.is_valid():
                return Response({'passengers': f'Pasajero {index}: {serializer.errors}'}, status=400)
            passenger = dict(serializer.validated_data)
            if not passenger.get('document_number') or passenger.get('age') is None:
                return Response({'passengers': f'Completa documento y edad del pasajero {index}.'}, status=400)
            has_guardian = bool((passenger.get('guardian_name') or '').strip())
            if passenger['age'] < 18:
                if has_guardian and not (passenger.get('guardian_document_number') and passenger.get('guardian_relationship')):
                    return Response({'passengers': f'Completa documento y parentesco del acompañante del menor {index}.'}, status=400)
                if not has_guardian and not passenger.get('authorization_reference'):
                    return Response({'passengers': f'Registra un acompañante o la autorización si el menor {index} viaja solo.'}, status=400)
            cleaned.append((passenger, has_guardian))

        passenger_count = sum(1 + int(has_guardian) for _, has_guardian in cleaned)
        occupied = service.passengers.all()
        occupied_seats = {seat for passenger in occupied for seat in (passenger.seat_number, passenger.guardian_seat_number) if seat is not None}
        if len(occupied_seats) + passenger_count > service.vehicle.capacity:
            return Response({'passengers': f'Solo quedan {max(0, service.vehicle.capacity - len(occupied_seats))} asientos disponibles.'}, status=400)

        def allocate(requested):
            if requested is not None:
                seat = int(requested)
                if seat < 1 or seat > service.vehicle.capacity or seat in used_seats or seat in occupied_seats:
                    raise ValueError(f'El asiento {seat} no está disponible en esta salida.')
            else:
                seat = next((number for number in range(1, service.vehicle.capacity + 1) if number not in occupied_seats and number not in used_seats), None)
                if seat is None:
                    raise ValueError('No quedan asientos disponibles en esta unidad.')
            used_seats.add(seat)
            return seat

        try:
            for passenger, has_guardian in cleaned:
                passenger['seat_number'] = allocate(passenger.get('seat_number'))
                if has_guardian:
                    passenger['guardian_seat_number'] = allocate(passenger.get('guardian_seat_number'))
                else:
                    passenger['guardian_seat_number'] = None
                    passenger['guardian_drone'] = False
        except (TypeError, ValueError) as error:
            return Response({'passengers': str(error)}, status=400)

        drone_count = sum(int(bool(passenger.get('drone'))) + int(bool(passenger.get('guardian_drone') and has_guardian)) for passenger, has_guardian in cleaned)
        if drone_count and service.drone_price <= 0:
            return Response({'passengers': 'Esta salida aún no tiene una tarifa de dron configurada por administración.'}, status=400)
        client_id = request.data.get('client')
        client = get_object_or_404(Client, pk=client_id) if client_id else None
        with transaction.atomic():
            booking = ServiceBooking.objects.create(
                service=service,
                client=client,
                contact_name=contact_name,
                contact_phone=contact_phone,
                passenger_count=passenger_count,
                drone_passengers=drone_count,
                ticket_price=service.price,
                drone_price=service.drone_price,
                payment_status='Pagado' if request.data.get('payment_status') == 'Pagado' else 'Pendiente',
            )
            position = service.passengers.count()
            for offset, (passenger, _) in enumerate(cleaned):
                ServicePassenger.objects.create(service=service, booking=booking, position=position + offset, **passenger)
            attendees = [status for passenger, has_guardian in cleaned for status in (
                [passenger.get('payment_status', 'Pendiente')]
                + ([passenger.get('guardian_payment_status', 'Pendiente')] if has_guardian else [])
            )]
            booking.payment_status = 'Pagado' if attendees and all(status == 'Pagado' for status in attendees) else 'Pendiente'
            booking.save(update_fields=['payment_status', 'updated_at'])
            service.people += passenger_count
            service.drone_passengers += drone_count
            service.drone = service.drone_passengers > 0
            service.save(update_fields=['people', 'drone_passengers', 'drone', 'updated_at'])
        service.refresh_from_db()
        return Response(self.get_serializer(service).data, status=201)

    @action(detail=True, methods=['patch'], url_path=r'bookings/(?P<booking_id>[^/.]+)/payment')
    def booking_payment(self, request, pk=None, booking_id=None):
        service = self.get_object()
        booking = get_object_or_404(ServiceBooking, pk=booking_id, service=service)
        payment_status = request.data.get('payment_status')
        if payment_status not in ('Pendiente', 'Pagado'):
            return Response({'payment_status': 'El estado debe ser Pendiente o Pagado.'}, status=400)
        payment_method = request.data.get('payment_method')
        if payment_status == 'Pagado' and payment_method not in ('Efectivo', 'Yape', 'Plin', 'Transferencia', 'Tarjeta', 'Otro'):
            return Response({'payment_method': 'Selecciona cómo se recibió el pago.'}, status=400)
        with transaction.atomic():
            passengers = list(booking.passengers.all())
            for passenger in passengers:
                passenger.payment_status = payment_status
                passenger.payment_method = payment_method if payment_status == 'Pagado' else ''
                if passenger.guardian_name:
                    passenger.guardian_payment_status = payment_status
                    passenger.guardian_payment_method = payment_method if payment_status == 'Pagado' else ''
                passenger.save(update_fields=['payment_status', 'payment_method', 'guardian_payment_status', 'guardian_payment_method', 'updated_at'])
            booking.payment_status = payment_status
            booking.save(update_fields=['payment_status', 'updated_at'])
        return Response(ServiceBookingSerializer(booking).data)

    def _route_points(self, service):
        return [service.origin, *service.stops.order_by('position').values_list('name', flat=True), service.destination]

    def _record_journey_event(self, service, event, point):
        service.journey_events = [*service.journey_events, {
            'event': event,
            'point': point,
            'timestamp': timezone.now().isoformat(),
            'user': self.request.user.get_username(),
        }]

    @action(detail=True, methods=['post'])
    def journey(self, request, pk=None):
        service = self.get_object()
        action_name = request.data.get('action')
        if service.status == 'Cancelado':
            return Response({'detail': 'No se puede avanzar un servicio cancelado.'}, status=400)
        points = self._route_points(service)
        last_step = len(points) - 1

        if action_name == 'start':
            if service.journey_status != 'Pendiente':
                return Response({'detail': 'El viaje ya fue iniciado o finalizado.'}, status=400)
            service.journey_status = 'En curso'
            service.journey_leg = 'ida'
            service.journey_step = 0
            self._record_journey_event(service, 'Salida', points[0])
        elif action_name == 'arrive':
            if service.journey_status == 'En curso' and service.journey_leg == 'ida':
                if service.journey_step >= last_step:
                    return Response({'detail': 'Ya se registró la llegada al destino.'}, status=400)
                service.journey_step += 1
            elif service.journey_status == 'En retorno' and service.journey_leg == 'retorno':
                if service.journey_step <= 0:
                    return Response({'detail': 'Ya se registró la llegada al punto de origen.'}, status=400)
                service.journey_step -= 1
            else:
                return Response({'detail': 'Inicia el viaje antes de registrar una llegada.'}, status=400)
            self._record_journey_event(service, 'Llegada', points[service.journey_step])
        elif action_name == 'return':
            if not service.return_required:
                return Response({'detail': 'Este servicio fue registrado como solo ida.'}, status=400)
            if service.journey_status != 'En curso' or service.journey_step != last_step:
                return Response({'detail': 'Registra primero la llegada al destino para iniciar el retorno.'}, status=400)
            service.journey_status = 'En retorno'
            service.journey_leg = 'retorno'
            self._record_journey_event(service, 'Inicio de retorno', points[-1])
        elif action_name == 'finish':
            can_finish_one_way = not service.return_required and service.journey_status == 'En curso' and service.journey_step == last_step
            can_finish_return = service.return_required and service.journey_status == 'En retorno' and service.journey_step == 0
            if not (can_finish_one_way or can_finish_return):
                return Response({'detail': 'Completa la ruta de ida y el retorno requerido antes de finalizar.'}, status=400)
            service.journey_status = 'Completado'
            service.status = 'Completado'
            service.journey_leg = ''
            self._record_journey_event(service, 'Servicio finalizado', points[service.journey_step])
        else:
            return Response({'detail': 'Acción de viaje desconocida.'}, status=400)

        service.save(update_fields=['journey_status', 'journey_leg', 'journey_step', 'journey_events', 'status', 'updated_at'])
        return Response(self.get_serializer(service).data)
class TransferViewSet(BaseViewSet):
    queryset=Transfer.objects.select_related('service').prefetch_related('reminder_users').all().order_by('datetime'); serializer_class=TransferSerializer; search_fields=['title','place','responsible']; section='transfers'

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def movement(self, request, pk=None):
        transfer = Transfer.objects.select_for_update().get(pk=pk)
        action_name = request.data.get('action')
        if action_name == 'depart' and transfer.status == 'Programado':
            transfer.status = 'En camino'
            transfer.departed_at = timezone.now()
            transfer.save(update_fields=['status', 'departed_at', 'updated_at'])
        elif action_name == 'arrive' and transfer.status == 'En camino':
            transfer.status = 'Llegó al destino'
            transfer.arrived_at = timezone.now()
            transfer.save(update_fields=['status', 'arrived_at', 'updated_at'])
        else:
            return Response({'detail': 'Marca primero la salida del carro y luego su llegada al destino.'}, status=400)
        return Response(self.get_serializer(transfer).data)

class ExpenseViewSet(BaseViewSet):
    queryset=Expense.objects.select_related('service').all().order_by('-date'); serializer_class=ExpenseSerializer; search_fields=['concept','category','service_name']; section='expenses'


class IsPrimaryAdministrator(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)


class UserViewSet(viewsets.ModelViewSet):
    queryset = get_user_model().objects.filter(is_superuser=False).order_by('username')
    serializer_class = UserSerializer
    permission_classes = [IsPrimaryAdministrator]
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def perform_destroy(self, instance):
        if instance.is_superuser or instance.pk == self.request.user.pk:
            raise PermissionDenied('No puedes eliminar esta cuenta administradora.')
        instance.delete()


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def reminder_user_choices(request):
    users = get_user_model().objects.filter(is_active=True).order_by('username')
    return Response([
        {
            'id': u.id,
            'username': u.username,
            'name': u.get_full_name() or u.username,
            'role': user_role(u),
            'is_admin': u.is_superuser or user_role(u) == 'Administrador',
        }
        for u in users
    ])


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def current_user(request):
    user = request.user
    return Response({
        'id': user.id,
        'username': user.username,
        'name': user.get_full_name() or user.username,
        'email': user.email,
        'role': user_role(user),
        'is_active': user.is_active,
        'is_primary_admin': user.is_superuser,
        'permissions': effective_permissions(user),
    })


@api_view(['GET', 'PATCH'])
@permission_classes([AllowAny])
def system_settings(request):
    record, _ = SystemSettings.objects.get_or_create(key='main')
    if request.method == 'GET':
        return Response(record.values)
    user = request.user
    if not user or not user.is_authenticated:
        raise PermissionDenied('Inicia sesión con una cuenta autorizada para cambiar la configuración.')
    if not user.is_superuser and not effective_permissions(user).get('settings', {}).get('edit', False):
        raise PermissionDenied('Tu cuenta no tiene permiso para editar la configuración.')
    allowed = {
        'brand_name', 'tagline', 'logo', 'hero_image', 'experience_private', 'experience_shared', 'experience_transfer', 'about_image',
        'nav_experiences', 'nav_about', 'nav_contact', 'hero_badge', 'hero_title_accent', 'hero_title_rest', 'hero_location',
        'hero_side_label', 'hero_description', 'hero_cta', 'hero_assurance_one', 'hero_assurance_two', 'hero_team_title',
        'hero_team_note', 'hero_featured_badge', 'hero_featured_title', 'hero_featured_note', 'experiences_badge',
        'experiences_title_first', 'experiences_title_second', 'experiences_intro', 'private_badge', 'private_title',
        'private_description', 'private_action', 'shared_badge', 'shared_title', 'shared_description', 'shared_action',
        'express_badge', 'express_title', 'express_description', 'express_action', 'drone_badge', 'drone_title_first',
        'drone_title_second', 'drone_description', 'drone_detail_title', 'drone_detail_note', 'about_badge',
        'about_title_first', 'about_title_second', 'about_description', 'about_value_one', 'about_value_two',
        'about_value_three', 'about_cta', 'contact_badge', 'contact_title_first', 'contact_title_second',
        'contact_description', 'contact_location', 'contact_whatsapp_heading', 'contact_whatsapp_number',
        'contact_whatsapp_note', 'contact_email_heading', 'contact_email', 'contact_email_note', 'social_facebook',
        'social_instagram', 'social_x', 'footer_copyright', 'footer_nav_heading',
    }
    image_keys = {'logo', 'hero_image', 'experience_private', 'experience_shared', 'experience_transfer', 'about_image'}
    values = {key: value for key, value in request.data.items() if key in allowed}
    for key, value in values.items():
        if key in image_keys:
            if value and (not isinstance(value, str) or not value.startswith('data:image/')):
                raise PermissionDenied('Las imágenes deben ser archivos de imagen válidos.')
            if value and len(value) > 2_500_000:
                raise PermissionDenied('Cada imagen debe pesar menos de 1.8 MB después de optimizarla.')
        elif isinstance(value, str) and len(value) > 3000:
            raise PermissionDenied('Cada texto de la landing debe tener como máximo 3000 caracteres.')
    for key in ('social_facebook', 'social_instagram', 'social_x'):
        if key in values and values[key] and (not isinstance(values[key], str) or not values[key].startswith('https://')):
            raise PermissionDenied('Los enlaces de redes sociales deben comenzar con https://.')
    if 'contact_whatsapp_number' in values and values['contact_whatsapp_number'] and (not isinstance(values['contact_whatsapp_number'], str) or not (values['contact_whatsapp_number'].isdigit() and 8 <= len(values['contact_whatsapp_number']) <= 15)):
        raise PermissionDenied('El número de WhatsApp debe contener solo números e incluir el código de país.')
    if 'contact_email' in values and values['contact_email'] and (not isinstance(values['contact_email'], str) or '@' not in values['contact_email'] or any(char.isspace() for char in values['contact_email'])):
        raise PermissionDenied('Ingresa un correo de contacto válido.')
    record.values = {**record.values, **values}
    record.save(update_fields=['values', 'updated_at'])
    return Response(record.values)
