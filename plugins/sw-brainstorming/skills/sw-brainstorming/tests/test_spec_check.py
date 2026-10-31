"""O lint do spec: citação que não existe tem de reprovar antes do gate do usuário.

Biblioteca padrão (`python3 -m unittest discover -s tests`).
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SCRIPT = RAIZ / "scripts" / "spec_check.py"
sys.path.insert(0, str(RAIZ / "scripts"))

from spec_check import checar  # noqa: E402

SPEC_BOM = """# Cobrança

## Objetivo & outcome
Cobrar uma vez só. O pedido fecha em `app/Pedido.php:2`. [visto: app/Pedido.php:2]

## Não-objetivos
Estorno fica de fora. [usuário]

## Decisões
Usar o gateway atual. [doc: https://exemplo.dev/api · v2 · 2026-10-31]

## Suposições
| Suposição | Risco se for falsa | Como validar |
|---|---|---|
| O saldo é em tempo real | vira assíncrono | chamar a homologação |
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)
        (self.raiz / "app").mkdir()
        (self.raiz / "app/Pedido.php").write_text("<?php\n$x = 1;\n", encoding="utf-8")
        self.dossie = self.raiz / "docs/specs/x"
        self.dossie.mkdir(parents=True)

    def rodar(self, texto):
        spec = self.dossie / "spec.md"
        spec.write_text(texto, encoding="utf-8")
        achados, avisos = checar(str(spec), str(self.raiz))
        return [a["regra"] for a in achados], [a["regra"] for a in avisos]


class TestEvidencia(Base):
    def test_spec_com_evidencia_real_passa_limpo(self):
        self.assertEqual(self.rodar(SPEC_BOM), ([], []))

    def test_arquivo_inventado_reprova(self):
        regras, _ = self.rodar(SPEC_BOM + "\nO hook fica aqui. [visto: app/Hook.php:3]\n")
        self.assertEqual(regras, ["evidência inexistente"])

    def test_linha_alem_do_fim_do_arquivo_reprova(self):
        regras, _ = self.rodar(SPEC_BOM + "\nFecha aqui. [visto: app/Pedido.php:90]\n")
        self.assertEqual(regras, ["linha inexistente"])

    def test_doc_sem_fonte_reprova(self):
        regras, _ = self.rodar(SPEC_BOM + "\nA API aceita lote. [doc: versão 2]\n")
        self.assertEqual(regras, ["documentação sem fonte"])

    def test_referencia_do_dossie_faltando_reprova(self):
        regras, _ = self.rodar(SPEC_BOM + "\nVer `referencias/tela.png`.\n")
        self.assertEqual(regras, ["referência faltando"])

    def test_arquivo_novo_citado_so_gera_aviso(self):
        """Spec cita o que VAI ser criado: isso não pode reprovar."""
        regras, avisos = self.rodar(SPEC_BOM + "\nCriar `app/Novo.php`.\n")
        self.assertEqual((regras, avisos), ([], ["caminho não encontrado"]))

    def test_citacao_dentro_de_bloco_de_codigo_e_ignorada(self):
        regras, _ = self.rodar(SPEC_BOM + "\n```\n[visto: nao/existe.py:1]\n```\n")
        self.assertEqual(regras, [])


class TestEstrutura(Base):
    def test_esqueleto_do_dossie_reprova(self):
        regras, _ = self.rodar("# X\n\n*(a skill sw-brainstorming preenche as seções)*\n")
        self.assertEqual(regras.count("seção faltando"), 4)
        self.assertIn("placeholder", regras)

    def test_fora_de_escopo_vale_como_nao_objetivos(self):
        regras, _ = self.rodar(SPEC_BOM.replace("## Não-objetivos", "## Fora de escopo"))
        self.assertEqual(regras, [])

    def test_placeholder_reprova_mas_nome_entre_crases_nao(self):
        regras, _ = self.rodar(SPEC_BOM + "\nRetry a definir.\n")
        self.assertEqual(regras, ["placeholder"])
        regras, _ = self.rodar(SPEC_BOM + "\nO campo `TODO` vem da API.\n")
        self.assertEqual(regras, [])


class TestPortugues(Base):
    def test_a_palavra_todo_nao_e_pendencia(self):
        """Num spec real, "todo o repositório" era acusado como TODO."""
        regras, _ = self.rodar(SPEC_BOM + "\nProcura em todo o repositório.\n")
        self.assertEqual(regras, [])


class TestSuposicoes(Base):
    def test_suposicao_sem_como_validar_reprova(self):
        regras, _ = self.rodar(SPEC_BOM.replace("chamar a homologação", " "))
        self.assertEqual(regras, ["suposição sem validação"])

    def test_tabela_sem_a_coluna_reprova(self):
        regras, _ = self.rodar(SPEC_BOM.replace("Como validar", "Observação"))
        self.assertEqual(regras, ["suposições sem 'Como validar'"])

    def test_suposicao_marcada_sem_linha_na_tabela_reprova(self):
        sem_tabela = SPEC_BOM.split("| Suposição")[0] + "Nenhuma.\n\nO saldo é real. [suposição]\n"
        regras, _ = self.rodar(sem_tabela)
        self.assertEqual(regras, ["suposição fora da tabela"])


class TestSaida(Base):
    def executar(self, texto):
        spec = self.dossie / "spec.md"
        spec.write_text(texto, encoding="utf-8")
        return subprocess.run([sys.executable, str(SCRIPT), str(spec), "--projeto", str(self.raiz)],
                              capture_output=True, text=True, check=False)

    def test_limpo_sai_zero(self):
        self.assertEqual(self.executar(SPEC_BOM).returncode, 0)

    def test_achado_sai_dois(self):
        self.assertEqual(self.executar("# X\n").returncode, 2)

    def test_spec_ilegivel_sai_um(self):
        saida = subprocess.run([sys.executable, str(SCRIPT), str(self.raiz / "nada.md")],
                               capture_output=True, text=True, check=False)
        self.assertEqual(saida.returncode, 1)


if __name__ == "__main__":
    unittest.main()
