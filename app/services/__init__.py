ROLE_SOLICITANTE = "Solicitante"
ROLE_ATENDENTE = "Atendente"
ROLE_ADMIN = "Admin"

# Legado: ainda usado no painel admin para distinguir perfis cadastrados.
STAFF_ROLES = (ROLE_ATENDENTE, ROLE_ADMIN)


def role_of(user):
    if user is None or user.cargo is None:
        return None
    return user.cargo.name


def is_admin(user):
    return role_of(user) == ROLE_ADMIN


def is_staff(user):
    """Legado — preferir ``can_manage_ticket`` para regras operacionais."""
    return role_of(user) in STAFF_ROLES


def belongs_to_ticket_area(user, ticket):
    """Usuário pertence à área de destino do chamado."""
    if user is None or user.area_id is None or ticket is None:
        return False
    return user.area_id == ticket.category_id


def can_manage_ticket(user, ticket):
    """Somente o administrador pode tratar chamados."""
    return is_admin(user)
