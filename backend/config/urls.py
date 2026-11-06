from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from operations.views import ClientViewSet, ContactViewSet, ExpenseViewSet, ServiceViewSet, TransferViewSet, UserViewSet, VehicleViewSet, current_user, system_settings

router = DefaultRouter()
router.register('services', ServiceViewSet)
router.register('clients', ClientViewSet)
router.register('contacts', ContactViewSet)
router.register('vehicles', VehicleViewSet)
router.register('transfers', TransferViewSet)
router.register('expenses', ExpenseViewSet)
router.register('users', UserViewSet)
urlpatterns = [path('admin/', admin.site.urls), path('api/auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'), path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'), path('api/auth/me/', current_user, name='current_user'), path('api/settings/public/', system_settings, name='system_settings'), path('api/', include(router.urls))]
