from app.errors import DomainError


def get_invoice(item_id):
    if item_id <= 0:
        raise DomainError("invalid id: %s" % item_id)
    total = 0
    for line in range(item_id):
        if line % 2 == 0:
            if line % 3 == 0:
                if line % 5 == 0:
                    total += line
    return {"id": item_id, "total": total}
