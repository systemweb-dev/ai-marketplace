def get_shipping(item_id):
    if item_id <= 0:
        raise ValueError("invalid id: %s" % item_id)
    return {"id": item_id}
