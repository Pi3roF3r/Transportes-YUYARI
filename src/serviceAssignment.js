export function unitOptionLabel(unit) {
  return `${unit.name} · ${unit.owner}`;
}

export function findVehicleByOption(vehicles, option) {
  return vehicles.find((vehicle) => unitOptionLabel(vehicle) === option) || null;
}

export function assignmentForVehicle(vehicles, option) {
  const vehicle = findVehicleByOption(vehicles, option);
  return {
    vehicle,
    driver: vehicle?.delegate || '',
    license: vehicle?.delegate_license_number || '',
  };
}

export function findDriverLicense(name, vehicles, services) {
  const normalizedName = String(name || '').trim().toLowerCase();
  if (!normalizedName) return '';

  const unitLicense = vehicles.find(
    (vehicle) => vehicle.delegate?.trim().toLowerCase() === normalizedName && vehicle.delegate_license_number,
  )?.delegate_license_number;
  if (unitLicense) return unitLicense;

  return services.find(
    (service) => service.driver?.trim().toLowerCase() === normalizedName && service.driver_license_number,
  )?.driver_license_number || '';
}
