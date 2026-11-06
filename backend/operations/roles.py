ROLE_ACCESS = {
    'Administrador': {'services', 'clients', 'contacts', 'vehicles', 'transfers', 'expenses', 'reports', 'users'},
    'Jefe': {'services', 'clients', 'contacts', 'vehicles', 'transfers', 'expenses', 'reports'},
    'Encargado': {'services', 'clients', 'contacts', 'vehicles', 'transfers'},
    'Operaciones': {'services', 'clients', 'transfers'},
}

ROLE_WRITES = {
    'services': {'Jefe', 'Encargado', 'Operaciones'},
    'clients': {'Jefe', 'Encargado', 'Operaciones'},
    'contacts': {'Jefe', 'Encargado'},
    'vehicles': {'Jefe', 'Encargado'},
    'transfers': {'Jefe', 'Encargado', 'Operaciones'},
    'expenses': {'Jefe'},
}

PERMISSION_SECTIONS = ('services', 'clients', 'contacts', 'vehicles', 'transfers', 'expenses', 'reports', 'settings')
PERMISSION_ACTIONS = ('view', 'create', 'edit', 'delete')


def user_role(user):
    if user.is_superuser or user.groups.filter(name='Administrador').exists():
        return 'Administrador'
    return user.groups.values_list('name', flat=True).first() or 'Operaciones'


def user_can_access(user, section):
    if user.is_superuser:
        return True
    return bool(effective_permissions(user).get(section, {}).get('view', False))


def effective_permissions(user):
    if user.is_superuser:
        return {section: {action: True for action in PERMISSION_ACTIONS} for section in PERMISSION_SECTIONS}
    try:
        custom = user.access_profile.permissions
    except Exception:
        custom = None
    if custom is not None:
        result = {
            section: {action: bool(custom.get(section, {}).get(action, False)) for action in PERMISSION_ACTIONS}
            for section in PERMISSION_SECTIONS
        }
        result['reports']['view'] = result['services']['view'] and result['expenses']['view']
        return result
    role = user_role(user)
    return {
        section: {
            'view': section in ROLE_ACCESS.get(role, set()),
            'create': role in ROLE_WRITES.get(section, set()),
            'edit': role in ROLE_WRITES.get(section, set()),
            'delete': False,
        }
        for section in PERMISSION_SECTIONS
    }
