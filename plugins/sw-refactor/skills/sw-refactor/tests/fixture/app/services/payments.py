def get_payment(item_id):
    if item_id <= 0:
        return None
    return {"id": item_id}
