import assert from 'node:assert/strict';
import test from 'node:test';
import { assignmentForVehicle, findDriverLicense, findVehicleByOption, unitOptionLabel } from './serviceAssignment.js';

test('formats and finds the selected unit from its dropdown option', () => {
  const vehicles = [
    { id: 4, name: 'Minivan', owner: 'Propia', delegate: 'Ana Torres', delegate_license_number: 'Q123456' },
  ];

  assert.equal(unitOptionLabel(vehicles[0]), 'Minivan · Propia');
  assert.equal(findVehicleByOption(vehicles, 'Minivan · Propia'), vehicles[0]);
  assert.equal(findVehicleByOption(vehicles, ''), null);
  assert.deepEqual(assignmentForVehicle(vehicles, 'Minivan · Propia'), {
    vehicle: vehicles[0], driver: 'Ana Torres', license: 'Q123456',
  });
  assert.deepEqual(assignmentForVehicle(vehicles, ''), { vehicle: null, driver: '', license: '' });
});

test('uses the selected unit driver license, ignoring case and surrounding spaces', () => {
  const vehicles = [{ delegate: '  Ana Torres ', delegate_license_number: 'Q123456' }];

  assert.equal(findDriverLicense('ana torres', vehicles, []), 'Q123456');
});

test('falls back to a previously saved service when the unit has no license yet', () => {
  const services = [{ driver: 'Ana Torres', driver_license_number: 'Q654321' }];

  assert.equal(findDriverLicense('Ana Torres', [{ delegate: 'Ana Torres' }], services), 'Q654321');
});

test('returns an empty license for an unknown driver', () => {
  assert.equal(findDriverLicense('Nuevo conductor', [], []), '');
  assert.equal(findDriverLicense('', [], []), '');
});
