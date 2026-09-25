"""O lint do plano: o que o olho deixa passar e só apareceria durante a execução.

Por que um script e não só o self-review: "confira se não ficou placeholder" é exatamente o
tipo de checagem que o modelo diz ter feito e não fez. Aqui é regex, não boa vontade.

Biblioteca padrão (`python3 -m unittest discover -s tests`).
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SCRIPT = RAIZ / "scripts" / "plan_check.py"
sys.path.insert(0, str(RAIZ / "scripts"))

from plan_check import checar  # noqa: E402

PLANO_BOM = """# Plano de implementação — Cobrança

[spec.md](spec.md)

**Objetivo:** cobrar o cliente uma vez só.

**Restrições verificáveis (do spec):**
| Restrição | Como o plano checa |
|---|---|
| p95 < 200ms | Task 1, step 4 |

---

### Task 1: Idempotência da cobrança

**Arquivos:**
- Criar: `src/cobranca.py`
- Teste: `tests/test_cobranca.py`

**Depende de:** nada

- [ ] **Step 1: escrever o teste que falha**

```python
def test_cobra_uma_vez():
    assert cobrar("id-1") == cobrar("id-1")
```

- [ ] **Step 2: rodar o teste e confirmar que falha**

Rode: `pytest tests/test_cobranca.py -v`
Esperado: FALHA

### Task 2: Endpoint

**Arquivos:**
- Alterar: `{existente}`

**Depende de:** Task 1

- [ ] **Step 1: ligar o endpoint**

```python
app.post("/cobranca", cobrar)
```
"""


class Api(unittest.TestCase):
    def setUp(self):
        self.pasta = Path(tempfile.mkdtemp())
        self.existente = self.pasta / "src" / "app.py"
        self.existente.parent.mkdir(parents=True)
        self.existente.write_text("app = None\n", encoding="utf-8")

    def escrever(self, texto):
        p = self.pasta / "plan.md"
        p.write_text(texto.replace("{existente}", "src/app.py"), encoding="utf-8")
        return p

    def achados(self, texto, **kw):
        return [a["regra"] for a in checar(str(self.escrever(texto)), **kw)]

    def test_plano_bom_passa_limpo(self):
        self.assertEqual(self.achados(PLANO_BOM), [])

    def test_task_sem_arquivos(self):
        texto = PLANO_BOM.replace("**Arquivos:**\n- Criar: `src/cobranca.py`\n- Teste: `tests/test_cobranca.py`\n", "")

        self.assertIn("task-sem-arquivos", self.achados(texto))

    def test_placeholder_em_qualquer_forma(self):
        for marca in ["TODO", "TBD", "implementar depois", "adicionar validação",
                      "tratar os erros adequadamente", "igual à Task 1"]:
            with self.subTest(marca=marca):
                texto = PLANO_BOM.replace("- [ ] **Step 1: ligar o endpoint**",
                                          f"- [ ] **Step 1: {marca}**")

                self.assertIn("placeholder", self.achados(texto))

    def test_placeholder_dentro_de_bloco_de_codigo_nao_conta(self):
        """O plano pode ter 'TBD' como DADO do teste (fixture, valor esperado). O que não pode
        é o plano empurrar a decisão em texto."""
        texto = PLANO_BOM.replace('app.post("/cobranca", cobrar)',
                                  'assert resposta.status == "TBD"  # TODO do fixture, não do plano')

        self.assertNotIn("placeholder", self.achados(texto))

    def test_placeholder_no_texto_conta_mesmo_com_bloco_na_task(self):
        texto = PLANO_BOM.replace("### Task 2: Endpoint", "### Task 2: Endpoint (TODO)")

        self.assertIn("placeholder", self.achados(texto))

    def test_step_de_codigo_sem_bloco_de_codigo(self):
        texto = PLANO_BOM.replace('```python\napp.post("/cobranca", cobrar)\n```\n', "")

        self.assertIn("step-sem-codigo", self.achados(texto))

    def test_checkbox_malformado(self):
        texto = PLANO_BOM.replace("- [ ] **Step 1: ligar o endpoint**", "- [] **Step 1: ligar o endpoint**")

        self.assertIn("checkbox-torto", self.achados(texto))

    def test_dependencia_para_task_que_nao_existe(self):
        texto = PLANO_BOM.replace("**Depende de:** Task 1", "**Depende de:** Task 7")

        self.assertIn("dependencia-inexistente", self.achados(texto))

    def test_arquivo_a_alterar_que_nao_existe_no_projeto(self):
        texto = PLANO_BOM.replace("{existente}", "src/inexistente.py")

        achados = checar(str(self.escrever(texto)), projeto=str(self.pasta))

        self.assertIn("arquivo-inexistente", [a["regra"] for a in achados])

    def test_arquivo_a_criar_nao_precisa_existir(self):
        achados = checar(str(self.escrever(PLANO_BOM)), projeto=str(self.pasta))

        self.assertEqual([a["regra"] for a in achados], [])

    def test_sem_a_raiz_do_projeto_nao_inventa_achado_de_arquivo(self):
        texto = PLANO_BOM.replace("{existente}", "src/inexistente.py")

        self.assertNotIn("arquivo-inexistente", self.achados(texto))

    def test_cabecalho_sem_link_do_spec(self):
        texto = PLANO_BOM.replace("[spec.md](spec.md)\n", "")

        self.assertIn("sem-spec", self.achados(texto))

    def test_plano_sem_task_nenhuma(self):
        self.assertIn("sem-task", self.achados("# Plano\n\n[spec.md](spec.md)\n\ntexto solto\n"))

    def test_cada_achado_diz_a_linha_e_o_que_fazer(self):
        texto = PLANO_BOM.replace("- [ ] **Step 1: ligar o endpoint**", "- [ ] **Step 1: TODO**")

        achado = [a for a in checar(str(self.escrever(texto))) if a["regra"] == "placeholder"][0]

        self.assertGreater(achado["linha"], 0)
        self.assertTrue(achado["dica"])


@unittest.skipUnless(SCRIPT.is_file(), "script ausente")
class Cli(unittest.TestCase):
    def rodar(self, texto):
        pasta = Path(tempfile.mkdtemp())
        (pasta / "plan.md").write_text(texto.replace("{existente}", "src/app.py"), encoding="utf-8")
        return subprocess.run([sys.executable, str(SCRIPT), str(pasta / "plan.md")],
                              capture_output=True, text=True, timeout=30)

    def test_plano_limpo_sai_com_zero(self):
        r = self.rodar(PLANO_BOM)

        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("nada a corrigir", r.stdout)

    def test_plano_com_problema_sai_com_dois_e_lista(self):
        r = self.rodar(PLANO_BOM.replace("- [ ] **Step 1: ligar o endpoint**", "- [ ] **Step 1: TODO**"))

        self.assertEqual(r.returncode, 2)
        self.assertIn("placeholder", r.stdout)

    def test_arquivo_que_nao_existe_sai_com_um(self):
        pasta = Path(tempfile.mkdtemp())

        r = subprocess.run([sys.executable, str(SCRIPT), str(pasta / "nao-existe.md")],
                           capture_output=True, text=True, timeout=30)

        self.assertEqual(r.returncode, 1)


if __name__ == "__main__":
    unittest.main()
