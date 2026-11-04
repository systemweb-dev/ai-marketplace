import unittest

from app.errors import DomainError
from app.services.orders import get_order


class OrdersTest(unittest.TestCase):
    def test_recusa_id_invalido_com_erro_de_dominio(self):
        with self.assertRaises(DomainError):
            get_order(0)

    def test_devolve_o_pedido(self):
        self.assertEqual(get_order(7), {"id": 7})
