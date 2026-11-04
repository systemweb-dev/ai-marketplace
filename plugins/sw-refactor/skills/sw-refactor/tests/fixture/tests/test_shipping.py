import unittest

from app.services.shipping import get_shipping


class ShippingTest(unittest.TestCase):
    def test_id_invalido_levanta_value_error(self):
        with self.assertRaises(ValueError):
            get_shipping(0)
