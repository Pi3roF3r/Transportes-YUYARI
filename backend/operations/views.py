from django.contrib.auth import get_user_model
from rest_framework import permissions, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from .models import Client, Contact, Expense, Service, SystemSettings, Transfer, UserAccess, Vehicle
from .roles import ROLE_WRITES, effective_permissions, user_can_access, user_role
from .serializers import ClientSerializer, ContactSerializer, ExpenseSerializer, ServiceSerializer, TransferSerializer, UserSerializer, VehicleSerializer


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
            action = {
                'list': 'view', 'retrieve': 'view', 'create': 'create',
                'update': 'edit', 'partial_update': 'edit', 'destroy': 'delete',
            }.get(getattr(view, 'action', ''), 'view')
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
class ServiceViewSet(BaseViewSet):
    queryset=Service.objects.select_related('client','vehicle').prefetch_related('stops').all().order_by('date','time'); serializer_class=ServiceSerializer; search_fields=['name','client_name','origin','destination','driver','type']; section='services'
class TransferViewSet(BaseViewSet):
    queryset=Transfer.objects.select_related('service').all().order_by('datetime'); serializer_class=TransferSerializer; search_fields=['title','place','responsible']; section='transfers'
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
