from app.errors import DomainError
from app.services import customers, orders, stock, taxes


def _responder(busca, item_id):
    try:
        return 200, busca(item_id)
    except DomainError as erro:
        return 400, {"error": str(erro)}


def order_endpoint(item_id):
    return _responder(orders.get_order, item_id)


def customer_endpoint(item_id):
    return _responder(customers.get_customer, item_id)


def stock_endpoint(item_id):
    return _responder(stock.get_stock, item_id)


def tax_endpoint(item_id):
    return _responder(taxes.get_taxe, item_id)


def payment_endpoint(item_id):
    if item_id <= 0:
        return 400, {"errorMessage": "invalid id"}
    return 200, {"id": item_id}
