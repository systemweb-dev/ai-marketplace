"""O contrato do flow.json: o que o editor aceita gravar e o que ele recusa.

Biblioteca padrão apenas (`python3 -m unittest discover -s tests`): a skill é distribuída pelo
marketplace e não pode exigir que a máquina de quem usa tenha pytest instalado.
"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from flow_contract import assert_valid_flow, validate_flow  # noqa: E402


def valid_flow():
    return {
        "title": "Request HTTP",
        "layout": "flow",
        "accent": "#2f6bf0",
        "animation": {"mode": "packet", "speed": 1},
        "groups": [{"id": "edge", "label": "Edge", "color": "#e8743b"}],
        "nodes": [
            {"id": "user", "label": "Usuário", "group": "edge"},
            {"id": "api", "label": "API", "group": "edge"},
        ],
        "edges": [{"from": "user", "to": "api"}],
    }


class Contrato(unittest.TestCase):
    def codigos(self, flow):
        return {erro["code"] for erro in validate_flow(flow)}

    def test_aceita_documento_valido(self):
        self.assertEqual(validate_flow(valid_flow()), [])

    def test_recusa_id_repetido_dizendo_onde(self):
        flow = valid_flow()
        flow["nodes"].append({"id": "user", "label": "Outro"})

        erros = validate_flow(flow)

        self.assertEqual({e["code"] for e in erros}, {"duplicate_id"})
        self.assertEqual(erros[0]["path"], "nodes[2].id")

    def test_recusa_ponta_de_aresta_inexistente_e_grupo_desconhecido(self):
        flow = valid_flow()
        flow["nodes"][0]["group"] = "missing-group"
        flow["edges"] = [{"from": "missing", "to": "user"}]

        self.assertEqual(self.codigos(flow), {"unknown_group", "unknown_edge_endpoint"})

    def test_aceita_aresta_de_volta_mas_recusa_a_repetida(self):
        flow = valid_flow()
        flow["edges"] += [{"from": "api", "to": "user"}]
        self.assertEqual(validate_flow(flow), [])

        flow["edges"].append({"from": "user", "to": "api"})

        self.assertIn("duplicate_edge", self.codigos(flow))

    def test_recusa_valor_invalido_em_campo_conhecido(self):
        for campo, valor in [("accent", "blue"), ("direction", "diagonal")]:
            with self.subTest(campo=campo):
                flow = valid_flow()
                flow[campo] = valor

                self.assertTrue(self.codigos(flow) & {"invalid_color", "invalid_enum"})

    def test_validar_nao_altera_o_documento(self):
        flow = valid_flow()
        original = copy.deepcopy(flow)

        validate_flow(flow)

        self.assertEqual(flow, original)

    def test_assert_valid_flow_aponta_o_campo(self):
        flow = valid_flow()
        flow["nodes"][0]["pos"] = ["x", 2]

        with self.assertRaisesRegex(ValueError, r"nodes\[0\]\.pos"):
            assert_valid_flow(flow)

    def test_recusa_campo_invalido_de_aresta(self):
        for campo, valor, codigo in [("label", 42, "invalid_label"),
                                     ("animated", "yes", "invalid_boolean"),
                                     ("dir", "sideways", "invalid_enum")]:
            with self.subTest(campo=campo):
                flow = valid_flow()
                flow["edges"][0][campo] = valor

                self.assertIn(codigo, self.codigos(flow))

    def test_recusa_titulo_e_icone_invalidos(self):
        flow = valid_flow()
        flow["title"] = 7
        flow["nodes"][0]["icon"] = "unknown"

        self.assertEqual(self.codigos(flow), {"invalid_title", "invalid_enum"})

    def test_recusa_valor_nulo_ou_nao_hashavel_em_campo_conhecido(self):
        for campo, valor in [("layout", []), ("direction", {}), ("animation", None)]:
            with self.subTest(campo=campo):
                flow = valid_flow()
                flow[campo] = valor

                self.assertTrue(validate_flow(flow))

    def test_recusa_ponta_de_aresta_nao_hashavel(self):
        flow = valid_flow()
        flow["edges"][0]["from"] = []

        self.assertIn("unknown_edge_endpoint", self.codigos(flow))


if __name__ == "__main__":
    unittest.main()
