import unittest

from app.api import payment_endpoint


class PaymentsTest(unittest.TestCase):
    def test_id_invalido_responde_400_com_errorMessage(self):
        self.assertEqual(payment_endpoint(0), (400, {"errorMessage": "invalid id"}))
