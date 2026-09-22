"""Arranjo em faixas (`layout: tiers`): cada nó tem o seu lugar.

O que estes testes protegem: dois nós da mesma faixa que caem na mesma coluna precisam empilhar
dentro dela — antes, o `y` dependia só da faixa e eles eram desenhados exatamente um sobre o
outro, escondendo nós do diagrama sem nenhum aviso.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from build_flow import LANE_PAD, NODE_H, layout_tiers  # noqa: E402


def montar(nodes, edges):
    nodes_by_id = {n["id"]: n for n in nodes}
    grupos = []
    for n in nodes:
        g = n.get("group")
        if g and g not in [x["id"] for x in grupos]:
            grupos.append({"id": g, "label": g})
    return layout_tiers([n["id"] for n in nodes], edges, nodes_by_id, grupos)


class Faixas(unittest.TestCase):
    def test_nos_da_mesma_faixa_e_coluna_nao_se_sobrepoem(self):
        nodes = [{"id": "web", "group": "cliente"}, {"id": "app", "group": "cliente"},
                 {"id": "api", "group": "backend"}]
        edges = [{"from": "web", "to": "api"}, {"from": "app", "to": "api"}]

        pos, _, _, _ = montar(nodes, edges)

        self.assertEqual(len(set(pos.values())), 3, "cada nó precisa de um ponto próprio")
        self.assertEqual(pos["web"][0], pos["app"][0], "mesma coluna: ambos entram no fluxo")
        self.assertNotEqual(pos["web"][1], pos["app"][1], "mas em alturas diferentes")

    def test_a_faixa_cresce_para_caber_a_maior_pilha(self):
        um = [{"id": "a", "group": "g"}, {"id": "b", "group": "g2"}]
        tres = [{"id": "a", "group": "g"}, {"id": "a2", "group": "g"}, {"id": "a3", "group": "g"},
                {"id": "b", "group": "g2"}]

        _, _, altura_um, faixas_um = montar(um, [])
        _, _, altura_tres, faixas_tres = montar(tres, [])

        self.assertGreater(altura_tres, altura_um)
        self.assertGreaterEqual(faixas_tres[0][2], 3 * NODE_H, "a faixa cabe os três")
        self.assertEqual(faixas_um[0][2], NODE_H + 2 * LANE_PAD, "faixa de um nó não incha")

    def test_faixa_de_baixo_comeca_depois_da_de_cima(self):
        nodes = [{"id": "a", "group": "topo"}, {"id": "a2", "group": "topo"},
                 {"id": "b", "group": "meio"}]

        pos, _, _, faixas = montar(nodes, [])

        topo, meio = faixas[0], faixas[1]
        self.assertGreaterEqual(meio[1], topo[1] + topo[2], "as faixas não podem se invadir")
        self.assertTrue(all(pos[n][1] >= topo[1] for n in ("a", "a2")))
        self.assertGreaterEqual(pos["b"][1], meio[1])

    def test_no_sem_grupo_cai_na_ultima_faixa_sem_virar_faixa_desenhada(self):
        nodes = [{"id": "a", "group": "g"}, {"id": "solto"}]

        pos, _, _, faixas = montar(nodes, [])

        self.assertEqual([f[0] for f in faixas], ["g"], "a faixa '_' não é desenhada")
        self.assertNotEqual(pos["solto"][1], pos["a"][1])

    def test_ordem_das_faixas_segue_a_ordem_dos_grupos(self):
        nodes = [{"id": "b", "group": "segundo"}, {"id": "a", "group": "primeiro"}]

        pos, _, _, faixas = montar(nodes, [])

        self.assertEqual([f[0] for f in faixas], ["segundo", "primeiro"])
        self.assertLess(pos["b"][1], pos["a"][1])


if __name__ == "__main__":
    unittest.main()
