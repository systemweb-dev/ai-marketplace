"""O dossiê: a pasta do trabalho, o estado e o índice.

Por que testar um script pequeno: ele existe justamente para o índice e o estado nunca
mentirem. Se o `estado` não gravar, ou o índice for regenerado por fora dos marcadores, a
skill inteira passa a informar errado — e ninguém percebe, porque nada quebra na hora.

Biblioteca padrão (`python3 -m unittest discover -s tests`): a skill roda na máquina de quem
a instala, sem dependência nova.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SCRIPT = RAIZ / "scripts" / "dossie.py"
sys.path.insert(0, str(RAIZ / "scripts"))

from dossie import ESTADOS, ler_frontmatter, slugify  # noqa: E402

HOJE = date.today().isoformat()


class Slug(unittest.TestCase):
    def test_tira_acento_pontuacao_e_caixa(self):
        self.assertEqual(slugify("Relatório de Cobrança: v2"), "relatorio-de-cobranca-v2")

    def test_titulo_sem_nada_aproveitavel_ainda_vira_pasta(self):
        self.assertEqual(slugify("··· !!! ···"), "sem-titulo")


class Cli(unittest.TestCase):
    def setUp(self):
        self.raiz = Path(tempfile.mkdtemp()) / "specs"

    def rodar(self, *args, raiz_antes=True):
        cmd = [sys.executable, str(SCRIPT)]
        cmd += (["--raiz", str(self.raiz), *args] if raiz_antes else [*args, "--raiz", str(self.raiz)])
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30)

    def novo(self, titulo="Auditoria de cluster"):
        r = self.rodar("novo", "--titulo", titulo)
        self.assertEqual(r.returncode, 0, r.stderr)
        return Path(r.stdout.strip())

    def test_novo_cria_a_pasta_com_spec_frontmatter_e_referencias(self):
        pasta = self.novo()

        fm = ler_frontmatter(str(pasta / "spec.md"))
        self.assertEqual(pasta.name, f"{HOJE}-auditoria-de-cluster")
        self.assertEqual(fm["titulo"], "Auditoria de cluster")
        self.assertEqual(fm["estado"], "rascunho")
        self.assertEqual(fm["criado"], HOJE)
        self.assertTrue((pasta / "referencias" / ".gitkeep").is_file())

    def test_raiz_funciona_depois_do_subcomando(self):
        """`novo --titulo X --raiz Y` é a ordem natural de quem digita, e é a que o SKILL.md
        sugere logo depois do exemplo. Antes ela morria em 'unrecognized arguments'."""
        r = self.rodar("novo", "--titulo", "Ordem natural", raiz_antes=False)

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.raiz / f"{HOJE}-ordem-natural" / "spec.md").is_file())

    def test_titulo_repetido_no_mesmo_dia_e_recusado_com_saida(self):
        self.novo()

        r = self.rodar("novo", "--titulo", "Auditoria de cluster")

        self.assertNotEqual(r.returncode, 0)
        self.assertIn("já existe", r.stderr)
        self.assertIn("listar", r.stderr, "o erro precisa dizer como continuar o existente")

    def test_estado_grava_no_frontmatter_e_no_indice(self):
        pasta = self.novo()

        r = self.rodar("estado", pasta.name, "em-execucao")

        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(ler_frontmatter(str(pasta / "spec.md"))["estado"], "em-execucao")
        self.assertIn("em execução", (self.raiz / "README.md").read_text(encoding="utf-8"))

    def test_estado_desconhecido_e_recusado_dizendo_os_validos(self):
        pasta = self.novo()

        r = self.rodar("estado", pasta.name, "publicado")

        self.assertNotEqual(r.returncode, 0)
        for estado in ESTADOS:
            self.assertIn(estado, r.stderr)
        self.assertEqual(ler_frontmatter(str(pasta / "spec.md"))["estado"], "rascunho")

    def test_slug_parcial_sugere_o_dossie_certo(self):
        """Esquecer o prefixo de data é o erro natural: o script precisa dizer qual era o slug."""
        pasta = self.novo("Auditoria de cluster")

        r = self.rodar("estado", "auditoria-de-cluster", "aprovado")

        self.assertNotEqual(r.returncode, 0)
        self.assertIn(pasta.name, r.stderr, "sem a sugestão, o agente fica adivinhando")
        self.assertEqual(ler_frontmatter(str(pasta / "spec.md"))["estado"], "rascunho")

    def test_slug_que_nao_existe_de_jeito_nenhum_falha_sem_sugestao_falsa(self):
        self.novo("Auditoria de cluster")

        r = self.rodar("estado", "coisa-que-nao-existe", "aprovado")

        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("auditoria-de-cluster", r.stderr)

    def test_listar_em_json_traz_o_que_o_agente_precisa(self):
        self.novo()

        r = self.rodar("listar", "--json")

        item = json.loads(r.stdout)[0]
        self.assertEqual(item["estado"], "rascunho")
        self.assertEqual(item["titulo"], "Auditoria de cluster")
        self.assertFalse(item["tem_plano"])
        self.assertEqual(item["referencias"], [], ".gitkeep não conta como referência")

    def test_listar_sem_dossie_nao_finge_que_existe(self):
        r = self.rodar("listar")

        self.assertIn("nenhum dossiê", r.stdout)

    def test_listar_nao_deixa_espaco_sobrando_no_fim_da_linha(self):
        self.novo()

        r = self.rodar("listar")

        self.assertTrue(r.stdout.strip(), "a listagem não pode vir vazia")
        for linha in r.stdout.splitlines():
            self.assertEqual(linha, linha.rstrip(), "linha com espaço sobrando no fim")

    def test_indice_e_regenerado_entre_os_marcadores_preservando_o_resto(self):
        pasta = self.novo()
        readme = self.raiz / "README.md"
        texto = readme.read_text(encoding="utf-8").replace(
            "# Specs", "# Specs\n\nAnotação minha que não pode sumir.")
        readme.write_text(texto, encoding="utf-8")

        (pasta / "plan.md").write_text("plano", encoding="utf-8")
        self.rodar("indice")

        final = readme.read_text(encoding="utf-8")
        self.assertIn("Anotação minha que não pode sumir.", final)
        self.assertIn("plano", final.split("<!-- DOSSIES:START -->")[1])
        self.assertEqual(final.count("<!-- DOSSIES:START -->"), 1)

    def test_indice_aponta_para_o_spec_de_cada_dossie(self):
        pasta = self.novo()

        self.rodar("indice")

        self.assertIn(f"]({pasta.name}/spec.md)", (self.raiz / "README.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
