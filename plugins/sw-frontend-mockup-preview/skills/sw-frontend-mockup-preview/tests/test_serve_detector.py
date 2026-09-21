"""O servidor de preview expõe o resultado do detector em `/__detector`.

É o que deixa a tela do harness mostrar o selo "limpo / N achados" sem o terminal: a cada
recarga (o live-reload já recarrega a cada edição), a tela pede o resultado de novo.
"""
import json
import sys
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import serve  # noqa: E402


class Detector(unittest.TestCase):
    def setUp(self):
        self.pasta = Path(tempfile.mkdtemp())
        self.servidor = serve.ThreadingServer(("127.0.0.1", 0), serve.make_handler(self.pasta))
        threading.Thread(target=self.servidor.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.servidor.server_address[1]}"

    def tearDown(self):
        self.servidor.shutdown()
        self.servidor.server_close()

    def pedir(self, caminho):
        with urllib.request.urlopen(self.base + caminho, timeout=5) as resposta:
            return resposta.status, resposta.headers.get("Content-Type"), resposta.read()

    def test_devolve_o_resultado_do_index_em_json(self):
        (self.pasta / "index.html").write_text(
            '<section class="variation"><button>Salvar — agora</button></section>',
            encoding="utf-8")

        status, tipo, corpo = self.pedir("/__detector")
        dados = json.loads(corpo)

        self.assertEqual(status, 200)
        self.assertIn("application/json", tipo)
        self.assertEqual(dados["variacoes"], 1)
        self.assertIn("travessao-na-interface", [a["regra"] for a in dados["achados"]])

    def test_sem_index_devolve_erro_legivel_e_nao_derruba_o_servidor(self):
        status, _, corpo = self.pedir("/__detector")

        self.assertEqual(status, 200)
        self.assertIn("erro", json.loads(corpo))
        self.assertEqual(self.pedir("/__detector")[0], 200)

    def test_declaracao_invalida_vira_erro_legivel(self):
        (self.pasta / "index.html").write_text(
            '<!-- detector: ignorar regra-que-nao-existe --><section class="variation"></section>',
            encoding="utf-8")

        self.assertIn("não existe", json.loads(self.pedir("/__detector")[2])["erro"])

    def test_o_resto_continua_sendo_servido(self):
        (self.pasta / "index.html").write_text("<p>oi</p>", encoding="utf-8")

        status, _, corpo = self.pedir("/")

        self.assertEqual(status, 200)
        self.assertIn(b"oi", corpo)


if __name__ == "__main__":
    unittest.main()
