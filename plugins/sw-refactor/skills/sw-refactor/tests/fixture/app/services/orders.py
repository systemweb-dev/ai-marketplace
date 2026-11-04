from app.errors import DomainError


def get_order(item_id):
    if item_id <= 0:
        raise DomainError("invalid id: %s" % item_id)
    return {"id": item_id}
