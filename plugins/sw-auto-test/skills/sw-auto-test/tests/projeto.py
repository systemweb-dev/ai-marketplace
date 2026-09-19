"""Projetos de teste realistas o bastante para os detectores terem o que achar."""

PYTEST_BOM = '''\
def test_soma_dois_numeros():
    assert somar(2, 2) == 4
'''

PYTEST_RUIM = '''\
import time, random
from datetime import datetime


def test_sem_assercao():
    resultado = calcular(1)
    print(resultado)


@pytest.mark.skip(reason="quebrou")
def test_desligado():
    assert False


def test_espera_e_relogio():
    time.sleep(2)
    assert datetime.now().year > 2000


def test_aleatorio():
    assert random.randint(1, 10) > 0
'''

VITEST_RUIM = '''\
import { it, expect } from 'vitest';

it.skip('desligado', () => { expect(1).toBe(1); });

it('sem assercao', () => { montarCarrinho(); });

it('usa relogio real', async () => {
  await new Promise(r => setTimeout(r, 500));
  expect(new Date().getFullYear()).toBeGreaterThan(2000);
});

it('nome repetido', () => { expect(2).toBe(2); });

it('nome repetido', () => { expect(3).toBe(3); });
'''

PHPUNIT_RUIM = '''\
<?php
class CarrinhoTest extends TestCase
{
    public function test_sem_assercao(): void
    {
        $carrinho = new Carrinho();
        $carrinho->adicionar(1);
    }

    public function test_pulado(): void
    {
        $this->markTestSkipped('instavel');
    }

    public function test_rede(): void
    {
        $resposta = file_get_contents('http://api.exemplo/itens');
        $this->assertNotEmpty($resposta);
    }
}
'''


def projeto_pytest(repo):
    """pyproject + tests/unit com um teste bom e vários problemáticos."""
    repo.escrever({
        "pyproject.toml": "[tool.pytest.ini_options]\ntestpaths = ['tests']\n",
        "src/calculadora.py": "def somar(a, b):\n    return a + b\n",
        "tests/unit/test_calculadora.py": PYTEST_BOM,
        "tests/unit/test_problemas.py": PYTEST_RUIM,
    })
    repo.commit("chore: projeto python")
    return repo


def projeto_vitest(repo):
    repo.escrever({
        "package.json": '{"name": "app", "devDependencies": {"vitest": "^2.0.0"}}\n',
        "vitest.config.ts": "export default {};\n",
        "src/carrinho.ts": "export function montarCarrinho() { return []; }\n",
        "tests/unit/carrinho.test.ts": VITEST_RUIM,
    })
    repo.commit("chore: projeto js")
    return repo


def projeto_phpunit(repo):
    repo.escrever({
        "composer.json": '{"require-dev": {"phpunit/phpunit": "^11.0"}}\n',
        "phpunit.xml": "<phpunit><testsuites><testsuite name='Unit'>"
                       "<directory>tests/Unit</directory></testsuite></testsuites></phpunit>\n",
        "src/Carrinho.php": "<?php class Carrinho { public function adicionar($id) {} }\n",
        "tests/Unit/CarrinhoTest.php": PHPUNIT_RUIM,
    })
    repo.commit("chore: projeto php")
    return repo
