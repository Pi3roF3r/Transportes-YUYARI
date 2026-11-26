from decimal import Decimal
from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import Service, TouristGuide, Transfer, UserAccess, Vehicle


class DriverAndVehicleAssignmentApiTests(APITestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username='test-admin',
            email='test-admin@example.com',
            password='test-password-123',
        )
        self.client.force_authenticate(self.admin)
        self.vehicle = Vehicle.objects.create(
            name='Minivan de prueba',
            plate='TEST-001',
            capacity=4,
            delegate='Ana Torres',
            delegate_license_number='Q123456',
        )
        self.guide = TouristGuide.objects.create(
            full_name='Guía de prueba',
            dni='12345678',
            carnet='GT-001',
        )

    def service_payload(self, **overrides):
        payload = {
            'name': 'Tour de prueba',
            'type': 'Tour privado',
            'date': '2027-02-10',
            'time': '08:00:00',
            'status': 'Pendiente',
            'people': 2,
            'origin': 'Chivay',
            'destination': 'Colca',
            'duration_minutes': 120,
            'driver': 'Ana Torres',
            'driver_license_number': 'Q123456',
            'vehicle': self.vehicle.pk,
            'vehicle_name': str(self.vehicle),
            'price': '125.00',
            'drone': False,
            'passengers': [
                {
                    'position': 0,
                    'full_name': 'Pasajera Uno',
                    'document_type': 'DNI',
                    'document_number': '11111111',
                    'age': 30,
                    'seat_number': 1,
                },
                {
                    'position': 1,
                    'full_name': 'Pasajero Dos',
                    'document_type': 'DNI',
                    'document_number': '22222222',
                    'age': 32,
                    'seat_number': 2,
                },
            ],
        }
        payload.update(overrides)
        return payload

    def drone_payload(self, **overrides):
        payload = self.service_payload(drone=True, drone_price='40.00', drone_passengers=1)
        payload.update(overrides)
        payload['passengers'][0]['drone'] = True
        return payload

    def test_unit_requires_license_when_a_delegate_is_registered(self):
        response = self.client.post(
            reverse('vehicle-list'),
            {
                'name': 'Unidad sin licencia',
                'plate': 'TEST-002',
                'capacity': 4,
                'delegate': 'Luis Paredes',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('delegate_license_number', response.data)

    def test_unit_saves_and_returns_delegate_license(self):
        response = self.client.get(reverse('vehicle-list'))
        saved_unit = next(row for row in response.data if row['id'] == self.vehicle.pk)
        self.assertEqual(saved_unit['delegate'], 'Ana Torres')
        self.assertEqual(saved_unit['delegate_license_number'], 'Q123456')

    def test_unit_driver_can_be_removed_by_clearing_name_and_license(self):
        response = self.client.patch(
            reverse('vehicle-detail', args=[self.vehicle.pk]),
            {'delegate': '', 'delegate_license_number': ''},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['delegate'], '')
        self.assertEqual(response.data['delegate_license_number'], '')

    def test_manifest_header_and_passenger_complementary_fields_are_saved(self):
        payload = self.service_payload(
            manifest_code='MF01-000123',
            transport_company='Transportes de prueba',
            manifest_responsible='Responsable Uno',
            guide_name='Guía Uno',
            guide_document_number='12345678',
            guide_card_number='CARNET-9',
        )
        payload['passengers'][0].update({
            'country': 'Perú',
            'sale_code': 'VTA-42',
            'tour_name': 'Ruta del Colca',
            'passenger_type': 'Turista',
            'agency': 'Agencia Uno',
            'booked_by': 'Operaciones',
            'btc': '0',
            'bter': '0',
            'food': 'Almuerzo',
            'passenger_origin': 'Chivay',
            'passenger_destination': 'Puno',
            'accommodation': 'Habitación 12',
            'manifest_notes': 'Recojo en recepción',
            'manifest_description': 'Se integra al grupo en la plaza principal.',
        })
        response = self.client.post(reverse('service-list'), payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        for key in ('manifest_code', 'transport_company', 'manifest_responsible', 'guide_name', 'guide_document_number', 'guide_card_number'):
            self.assertEqual(response.data[key], payload[key])
        passenger = response.data['passengers'][0]
        self.assertEqual(passenger['country'], 'Perú')
        self.assertEqual(passenger['sale_code'], 'VTA-42')
        self.assertEqual(passenger['manifest_notes'], 'Recojo en recepción')
        self.assertEqual(passenger['manifest_description'], 'Se integra al grupo en la plaza principal.')

    def test_service_guide_is_saved_and_guide_identity_is_snapshotted(self):
        response = self.client.post(
            reverse('service-list'),
            self.service_payload(tour_guide=self.guide.pk),
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['tour_guide'], self.guide.pk)
        self.assertEqual(response.data['guide_name'], self.guide.full_name)
        self.assertEqual(response.data['guide_document_number'], self.guide.dni)
        self.assertEqual(response.data['guide_card_number'], self.guide.carnet)

    def test_guide_can_be_saved_with_empty_optional_absence_dates(self):
        response = self.client.post(
            '/api/guides/',
            {
                'full_name': 'Guía disponible',
                'dni': '87654321',
                'carnet': 'GT-002',
                'status': 'Disponible',
                'unavailable_start': '',
                'unavailable_end': '',
                'unavailable_reason': '',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertIsNone(response.data['unavailable_start'])
        self.assertIsNone(response.data['unavailable_end'])

    def test_guide_cannot_be_assigned_during_a_registered_unavailability(self):
        self.guide.unavailable_start = date(2027, 2, 10)
        self.guide.unavailable_end = date(2027, 2, 10)
        self.guide.unavailable_reason = 'Enfermedad'
        self.guide.save()
        payload = self.service_payload(tour_guide=self.guide.pk)

        response = self.client.post(reverse('service-list'), payload, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('tour_guide', response.data)
        self.assertIn('Enfermedad', str(response.data['tour_guide']))

    def test_guide_cannot_be_double_booked_for_overlapping_services(self):
        first = self.service_payload(
            name='Primer servicio', tour_guide=self.guide.pk, vehicle=None,
            driver='', driver_license_number='', people=0, passengers=[], time='09:00:00',
        )
        created = self.client.post(reverse('service-list'), first, format='json')
        self.assertEqual(created.status_code, 201, created.data)
        second = self.service_payload(
            name='Segundo servicio', tour_guide=self.guide.pk, vehicle=None,
            driver='', driver_license_number='', people=0, passengers=[], time='10:00:00',
        )

        response = self.client.post(reverse('service-list'), second, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('schedule', response.data)
        self.assertIn('guía turístico', str(response.data['schedule']))

    def test_passenger_defaults_to_peru_and_receives_automatic_sale_code(self):
        payload = self.service_payload()
        payload['passengers'][0].pop('country', None)
        payload['passengers'][0].pop('sale_code', None)

        response = self.client.post(reverse('service-list'), payload, format='json')

        self.assertEqual(response.status_code, 201, response.data)
        passenger = response.data['passengers'][0]
        self.assertEqual(passenger['country'], 'Perú')
        self.assertRegex(passenger['sale_code'], r'^VTA-\d{6}$')

    def test_service_requires_license_when_driver_is_assigned(self):
        response = self.client.post(
            reverse('service-list'),
            self.service_payload(driver_license_number=''),
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('driver_license_number', response.data)

    def test_service_cannot_use_unit_during_manual_unavailability(self):
        self.vehicle.unavailable_start = timezone.make_aware(datetime(2027, 2, 10, 8, 30))
        self.vehicle.unavailable_end = timezone.make_aware(datetime(2027, 2, 10, 10, 30))
        self.vehicle.availability_notes = 'Reparación programada'
        self.vehicle.save()
        response = self.client.post(reverse('service-list'), self.service_payload(), format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('vehicle', response.data)
        self.assertIn('Reparación programada', str(response.data['vehicle']))

    def test_minor_companion_occupies_its_own_manifest_seat(self):
        payload = self.service_payload(people=3, drone=True, drone_price='30.00', drone_passengers=2)
        payload['passengers'][0].update({
            'age': 14,
            'drone': True,
            'guardian_name': 'Acompañante Adulto',
            'guardian_document_number': '33333333',
            'guardian_seat_number': 3,
            'guardian_relationship': 'Madre',
            'guardian_drone': True,
        })
        response = self.client.post(reverse('service-list'), payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertIn('Acompañante Adulto', response.data['passenger_names'])
        self.assertEqual(response.data['drone_passengers'], 2)

    def test_minor_companion_cannot_share_seat_or_skip_document(self):
        payload = self.service_payload(people=3)
        payload['passengers'][0].update({
            'age': 14,
            'guardian_name': 'Acompañante Adulto',
            'guardian_document_number': '33333333',
            'guardian_seat_number': 1,
            'guardian_relationship': 'Madre',
        })
        response = self.client.post(reverse('service-list'), payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('passengers', response.data)

        payload['passengers'][0]['guardian_document_number'] = '33333333'
        payload['passengers'][0]['guardian_seat_number'] = 0
        response = self.client.post(reverse('service-list'), payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('passengers', response.data)

        payload['passengers'][0]['guardian_seat_number'] = 3
        payload['passengers'][0]['guardian_document_number'] = ''
        response = self.client.post(reverse('service-list'), payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('passengers', response.data)

    def test_service_includes_drone_surcharge_in_total(self):
        response = self.client.post(
            reverse('service-list'),
            self.drone_payload(),
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['drone_passengers'], 1)
        self.assertTrue(response.data['passengers'][0]['drone'])
        self.assertEqual(response.data['driver_license_number'], 'Q123456')
        self.assertEqual(response.data['total_price'], Decimal('165.00'))

    def test_drone_passengers_cannot_exceed_reserved_passengers(self):
        response = self.client.post(
            reverse('service-list'),
            self.drone_payload(drone_passengers=3),
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('passengers', response.data)
        self.assertEqual(Service.objects.count(), 0)

    def test_drone_service_requires_a_drone_passenger_count(self):
        response = self.client.post(
            reverse('service-list'),
            self.service_payload(drone=True, drone_price='40.00', drone_passengers=0),
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('passengers', response.data)

    def test_regular_service_total_does_not_include_drone_charge(self):
        response = self.client.post(
            reverse('service-list'),
            self.service_payload(),
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['total_price'], Decimal('125.00'))
        self.assertEqual(response.data['drone_price'], '0.00')
        self.assertEqual(response.data['drone_passengers'], 0)

    def test_user_without_service_edit_permission_cannot_set_drone_price(self):
        operator = get_user_model().objects.create_user(
            username='test-operator',
            password='test-password-123',
        )
        UserAccess.objects.create(
            user=operator,
            permissions={
                'services': {'view': True, 'create': True, 'edit': False, 'delete': False},
            },
        )
        self.client.force_authenticate(operator)

        response = self.client.post(
            reverse('service-list'),
            self.drone_payload(),
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('drone', response.data)
        self.assertEqual(Service.objects.count(), 0)

    def test_journey_tracks_departure_stops_return_and_finish(self):
        created = self.client.post(reverse('service-list'), self.service_payload(), format='json')
        self.assertEqual(created.status_code, 201, created.data)
        service_id = created.data['id']
        # Store two named stops so outbound and return progress can be checked.
        service = Service.objects.get(pk=service_id)
        from .models import Stop
        Stop.objects.create(service=service, position=0, name='Mirador')
        Stop.objects.create(service=service, position=1, name='Baños')
        endpoint = reverse('service-journey', args=[service_id])

        started = self.client.post(endpoint, {'action': 'start'}, format='json')
        self.assertEqual(started.status_code, 200, started.data)
        self.assertEqual(started.data['journey_status'], 'En curso')
        self.assertEqual(started.data['journey_events'][-1]['point'], 'Chivay')

        for expected_point, expected_step in [('Mirador', 1), ('Baños', 2), ('Colca', 3)]:
            arrived = self.client.post(endpoint, {'action': 'arrive'}, format='json')
            self.assertEqual(arrived.status_code, 200, arrived.data)
            self.assertEqual(arrived.data['journey_events'][-1]['point'], expected_point)
            self.assertEqual(arrived.data['journey_step'], expected_step)

        returning = self.client.post(endpoint, {'action': 'return'}, format='json')
        self.assertEqual(returning.status_code, 200, returning.data)
        self.assertEqual(returning.data['journey_status'], 'En retorno')
        for expected_point in ['Baños', 'Mirador', 'Chivay']:
            arrived = self.client.post(endpoint, {'action': 'arrive'}, format='json')
            self.assertEqual(arrived.status_code, 200, arrived.data)
            self.assertEqual(arrived.data['journey_events'][-1]['point'], expected_point)

        finished = self.client.post(endpoint, {'action': 'finish'}, format='json')
        self.assertEqual(finished.status_code, 200, finished.data)
        self.assertEqual(finished.data['journey_status'], 'Completado')
        self.assertEqual(finished.data['status'], 'Completado')

    def test_public_departure_accepts_independent_bookings_and_per_person_drone(self):
        departure = self.service_payload(
            type='Tour público', people=0, passengers=[], price='50.00',
            drone=False, drone_price='8.00', drone_passengers=0,
        )
        created = self.client.post(reverse('service-list'), departure, format='json')
        self.assertEqual(created.status_code, 201, created.data)
        service_id = created.data['id']
        self.assertEqual(created.data['vehicle_capacity'], 4)
        self.assertEqual(created.data['people'], 0)
        self.assertEqual(created.data['total_price'], Decimal('0.00'))
        endpoint = reverse('service-bookings', args=[service_id])

        first = self.client.post(endpoint, {
            'contact_name': 'Cliente Uno',
            'contact_phone': '999111222',
            'passengers': [{
                'full_name': 'Pasajero Uno', 'document_type': 'DNI', 'document_number': '10101010',
                'age': 29, 'drone': True,
            }],
        }, format='json')
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(first.data['people'], 1)
        self.assertEqual(first.data['drone_passengers'], 1)
        self.assertEqual(first.data['total_price'], Decimal('58.00'))
        first_booking = first.data['bookings'][0]
        self.assertEqual(first_booking['contact_name'], 'Cliente Uno')
        self.assertEqual(first_booking['total_amount'], Decimal('58.00'))
        self.assertEqual(first_booking['passengers'][0]['seat_number'], 1)

        second = self.client.post(endpoint, {
            'contact_name': 'Cliente Dos',
            'contact_phone': '999333444',
            'payment_status': 'Pagado',
            'payment_method': 'Yape',
            'passengers': [
                {'full_name': 'Pasajero Dos', 'document_type': 'DNI', 'document_number': '20202020', 'age': 35},
                {'full_name': 'Pasajera Tres', 'document_type': 'DNI', 'document_number': '30303030', 'age': 32, 'drone': True},
            ],
        }, format='json')
        self.assertEqual(second.status_code, 201, second.data)
        self.assertEqual(second.data['people'], 3)
        second_booking = next(row for row in second.data['bookings'] if row['contact_name'] == 'Cliente Dos')
        self.assertEqual(second_booking['total_amount'], Decimal('108.00'))
        self.assertEqual(second_booking['payment_status'], 'Pagado')
        self.assertEqual([p['seat_number'] for p in second_booking['passengers']], [2, 3])
        self.assertEqual(second_booking['passengers'][0]['payment_status'], 'Pagado')
        self.assertEqual(second_booking['passengers'][0]['payment_method'], 'Yape')

        overflow = self.client.post(endpoint, {
            'contact_name': 'Cliente Tres',
            'passengers': [
                {'full_name': f'Extra {i}', 'document_type': 'DNI', 'document_number': str(40000000 + i), 'age': 20}
                for i in range(3)
            ],
        }, format='json')
        self.assertEqual(overflow.status_code, 400)
        self.assertIn('passengers', overflow.data)

        payment = self.client.patch(
            reverse('service-booking-payment', args=[service_id, first_booking['id']]),
            {'payment_status': 'Pagado', 'payment_method': 'Efectivo'}, format='json',
        )
        self.assertEqual(payment.status_code, 200, payment.data)
        self.assertEqual(payment.data['payment_status'], 'Pagado')

    def test_one_way_service_finishes_at_destination_and_cannot_finish_early(self):
        created = self.client.post(
            reverse('service-list'),
            self.service_payload(return_required=False),
            format='json',
        )
        self.assertEqual(created.status_code, 201, created.data)
        endpoint = reverse('service-journey', args=[created.data['id']])
        early_finish = self.client.post(endpoint, {'action': 'finish'}, format='json')
        self.assertEqual(early_finish.status_code, 400)
        self.client.post(endpoint, {'action': 'start'}, format='json')
        self.client.post(endpoint, {'action': 'arrive'}, format='json')
        finished = self.client.post(endpoint, {'action': 'finish'}, format='json')
        self.assertEqual(finished.status_code, 200, finished.data)
        self.assertEqual(finished.data['journey_status'], 'Completado')

    def test_vehicle_can_be_saved_with_empty_optional_unavailability_fields(self):
        response = self.client.patch(
            reverse('vehicle-detail', args=[self.vehicle.pk]),
            {'unavailable_start': '', 'unavailable_end': '', 'availability_notes': ''},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIsNone(response.data['unavailable_start'])
        self.assertIsNone(response.data['unavailable_end'])

    def test_user_created_with_permissions_can_only_use_granted_actions(self):
        permissions = {'services': {'view': True, 'create': True, 'edit': False, 'delete': False}}
        created = self.client.post(reverse('user-list'), {
            'username': 'service-operator',
            'email': 'operator@example.com',
            'full_name': 'Operador de prueba',
            'password': 'test-password-123',
            'role': 'Operaciones',
            'permissions': permissions,
        }, format='json')
        self.assertEqual(created.status_code, 201, created.data)
        self.assertTrue(created.data['permissions']['services']['create'])
        self.assertFalse(created.data['permissions']['services']['edit'])

        service = self.client.post(reverse('service-list'), self.service_payload(), format='json')
        self.assertEqual(service.status_code, 201, service.data)
        operator = get_user_model().objects.get(username='service-operator')
        self.client.force_authenticate(operator)
        self.assertEqual(self.client.get(reverse('service-list')).status_code, 200)
        created_service = self.client.post(reverse('service-list'), self.service_payload(name='Servicio autorizado', time='11:00:00'), format='json')
        self.assertEqual(created_service.status_code, 201, created_service.data)
        denied_edit = self.client.patch(reverse('service-detail', args=[service.data['id']]), {'name': 'Cambio no autorizado'}, format='json')
        self.assertEqual(denied_edit.status_code, 403)
        self.assertEqual(self.client.get(reverse('vehicle-list')).status_code, 403)

    def test_view_only_user_cannot_change_journey_progress(self):
        created = self.client.post(reverse('service-list'), self.service_payload(), format='json')
        operator = get_user_model().objects.create_user(username='journey-viewer', password='test-password-123')
        UserAccess.objects.create(user=operator, permissions={'services': {'view': True, 'create': False, 'edit': False, 'delete': False}})
        self.client.force_authenticate(operator)
        response = self.client.post(reverse('service-journey', args=[created.data['id']]), {'action': 'start'}, format='json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Service.objects.get(pk=created.data['id']).journey_status, 'Pendiente')


class TransferMovementApiTests(APITestCase):
    def setUp(self):
        admin = get_user_model().objects.create_superuser(
            username='transfer-admin', email='transfer-admin@example.com', password='test-password-123'
        )
        self.client.force_authenticate(admin)
        self.transfer = Transfer.objects.create(
            title='Trasbordo de prueba', datetime=timezone.now() + timezone.timedelta(hours=2), place='Chivay'
        )

    def test_transfer_must_depart_before_it_can_arrive(self):
        endpoint = reverse('transfer-movement', args=[self.transfer.pk])
        early_arrival = self.client.post(endpoint, {'action': 'arrive'}, format='json')
        self.assertEqual(early_arrival.status_code, 400)

        departure = self.client.post(endpoint, {'action': 'depart'}, format='json')
        self.assertEqual(departure.status_code, 200, departure.data)
        self.assertEqual(departure.data['status'], 'En camino')
        self.assertIsNotNone(departure.data['departed_at'])

        arrival = self.client.post(endpoint, {'action': 'arrive'}, format='json')
        self.assertEqual(arrival.status_code, 200, arrival.data)
        self.assertEqual(arrival.data['status'], 'Llegó al destino')
        self.assertIsNotNone(arrival.data['arrived_at'])

        duplicate_arrival = self.client.post(endpoint, {'action': 'arrive'}, format='json')
        self.assertEqual(duplicate_arrival.status_code, 400)

    def test_reminders_and_user_choices_on_service_and_transfer(self):
        worker = get_user_model().objects.create_user(
            username='worker-rem', email='worker-rem@example.com', password='test-password-123'
        )
        choices_res = self.client.get(reverse('reminder_user_choices'))
        self.assertEqual(choices_res.status_code, 200)
        self.assertTrue(any(u['id'] == worker.id for u in choices_res.data))

        transfer_res = self.client.post(reverse('transfer-list'), {
            'title': 'Trasbordo 15 min',
            'datetime': (timezone.now() + timezone.timedelta(minutes=15)).isoformat(),
            'place': 'Plaza de Armas',
            'reminders': ['2 h antes', '1 h antes', '30 min antes', '15 min antes'],
            'reminder_users': [worker.id],
        }, format='json')
        self.assertEqual(transfer_res.status_code, 201, transfer_res.data)
        self.assertIn('15 min antes', transfer_res.data['reminders'])
        self.assertEqual(transfer_res.data['reminder_users'], [worker.id])

        service_res = self.client.post(reverse('service-list'), {
            'name': 'Tour con recordatorio',
            'type': 'Tour público',
            'date': (timezone.localdate() + timezone.timedelta(days=1)).isoformat(),
            'time': '08:30:00',
            'origin': 'Arequipa',
            'destination': 'Colca',
            'vehicle': Vehicle.objects.create(name='Van R', plate='REM-001', capacity=10, delegate='Luis', delegate_license_number='LIC-99').pk,
            'price': 100,
            'reminders': ['1 h antes', '15 min antes'],
            'reminder_users': [worker.id],
        }, format='json')
        self.assertEqual(service_res.status_code, 201, service_res.data)
        self.assertEqual(service_res.data['reminders'], ['1 h antes', '15 min antes'])
        self.assertEqual(service_res.data['reminder_users'], [worker.id])
        self.assertEqual(service_res.data['reminder_user_details'][0]['username'], 'worker-rem')
