"""Salvar do editor: ou grava tudo, ou não mexe em nada.

O que cada teste protege: o hash detecta que o arquivo mudou por fora (conflito), o build roda
antes de qualquer troca, e a substituição do flow.json e do flow.html é atômica — falha no meio
volta os dois ao que eram. Biblioteca padrão apenas
(`python3 -m unittest discover -s tests`), porque a skill roda na máquina de quem instala.
"""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import serve_flow  # noqa: E402
from serve_flow import BuildError, file_sha256, save_candidate  # noqa: E402


def successful_build(directory):
    (Path(directory) / "flow.html").write_text("<html></html>", encoding="utf-8")


class Salvar(unittest.TestCase):
    def setUp(self):
        self.pasta = Path(tempfile.mkdtemp())
        self.flow = self.pasta / "flow.json"
        self.html = self.pasta / "flow.html"

    def escrever(self, valor, path=None):
        (path or self.flow).write_text(valor, encoding="utf-8")

    def ler(self, path=None):
        return (path or self.flow).read_text(encoding="utf-8")

    def replace_que_falha_na_segunda_vez(self):
        """Simula o HTML falhando depois que o JSON já foi trocado."""
        original = serve_flow.os.replace
        chamadas = {"n": 0}

        def replace(origem, destino):
            chamadas["n"] += 1
            if chamadas["n"] == 2:
                raise OSError("falha simulada no HTML")
            return original(origem, destino)

        return replace

    def test_hash_muda_quando_o_arquivo_muda(self):
        self.escrever("{}")
        primeiro = file_sha256(self.flow)

        self.escrever('{"title":"novo"}')

        self.assertEqual(primeiro, hashlib.sha256(b"{}").hexdigest())
        self.assertNotEqual(file_sha256(self.flow), primeiro)

    def test_conflito_e_detectado_antes_de_preparar_a_troca(self):
        self.escrever('{"title":"atual"}')

        r = save_candidate(self.pasta, {"title": "candidato"}, "hash-incorreto", successful_build)

        self.assertEqual(r["status"], 409)
        self.assertEqual(self.ler(), '{"title":"atual"}')

    def test_build_que_falha_mantem_o_documento_original(self):
        self.escrever('{"title":"funcional"}')

        def build_que_falha(_):
            raise BuildError("falhou")

        r = save_candidate(self.pasta, {"title": "invalido"}, file_sha256(self.flow), build_que_falha)

        self.assertEqual(r["status"], 500)
        self.assertEqual(self.ler(), '{"title":"funcional"}')

    def test_sucesso_troca_json_e_html_de_uma_vez(self):
        self.escrever('{"title":"antigo"}')
        self.escrever("old", self.html)

        r = save_candidate(self.pasta, {"title": "novo"}, file_sha256(self.flow), successful_build)

        self.assertEqual(r["status"], 200)
        self.assertIn('"title": "novo"', self.ler())
        self.assertEqual(self.ler(self.html), "<html></html>")
        self.assertEqual(list(self.pasta.glob(".flow-save-*")), [], "arquivo temporário ficou para trás")

    def test_mudanca_externa_durante_o_build_vira_conflito(self):
        self.escrever('{"title":"atual"}')
        hash_original = file_sha256(self.flow)

        def build_que_ve_mudanca_externa(_):
            self.escrever('{"title":"externo"}')
            successful_build(_)

        r = save_candidate(self.pasta, {"title": "candidato"}, hash_original, build_que_ve_mudanca_externa)

        self.assertEqual(r["status"], 409)
        self.assertEqual(self.ler(), '{"title":"externo"}')

    def test_falha_ao_trocar_o_html_restaura_json_e_html(self):
        self.escrever('{"title":"antigo"}')
        self.escrever("old", self.html)

        with mock.patch.object(serve_flow.os, "replace", self.replace_que_falha_na_segunda_vez()):
            r = save_candidate(self.pasta, {"title": "novo"}, file_sha256(self.flow), successful_build)

        self.assertEqual(r["status"], 500)
        self.assertEqual(self.ler(), '{"title":"antigo"}')
        self.assertEqual(self.ler(self.html), "old")

    def test_falha_ao_trocar_o_html_apaga_o_novo_quando_nao_havia_html(self):
        self.escrever('{"title":"antigo"}')

        with mock.patch.object(serve_flow.os, "replace", self.replace_que_falha_na_segunda_vez()):
            r = save_candidate(self.pasta, {"title": "novo"}, file_sha256(self.flow), successful_build)

        self.assertEqual(r["status"], 500)
        self.assertEqual(self.ler(), '{"title":"antigo"}')
        self.assertFalse(self.html.exists())

    def test_candidato_invalido_nao_troca_o_documento(self):
        for dado in [None, [], "texto"]:
            with self.subTest(dado=dado):
                self.escrever('{"title":"funcional"}')

                def build_que_falha(_):
                    raise BuildError("flow.json inválido")

                r = save_candidate(self.pasta, dado, file_sha256(self.flow), build_que_falha)

                self.assertEqual(r["status"], 400)
                self.assertEqual(self.ler(), '{"title":"funcional"}')


if __name__ == "__main__":
    unittest.main()
