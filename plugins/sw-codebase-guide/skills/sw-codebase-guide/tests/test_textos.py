from lib.textos import coletar, eh_fonte_textual, TETO_BYTES, TETO_TOTAL
from lib.arvore import varrer


def test_reconhece_as_fontes_textuais():
    # Act / Assert
    assert eh_fonte_textual('README.md')
    assert eh_fonte_textual('CLAUDE.md')
    assert eh_fonte_textual('docs/setup.md')
    assert eh_fonte_textual('docs/adr/0001-escolha-do-banco.md')   # recursivo
    assert eh_fonte_textual('locales/pt-BR.json')
    assert not eh_fonte_textual('src/app.py')
    assert not eh_fonte_textual('package.json')


def test_coleta_o_conteudo_das_fontes(tmp_path):
    # Arrange
    (tmp_path / 'README.md').write_text('# Loja\n\nSistema de pedidos para padarias.')
    (tmp_path / 'src').mkdir()
    (tmp_path / 'src' / 'app.py').write_text('x = 1')
    # Act
    achados = coletar(tmp_path, varrer(tmp_path))
    # Assert
    assert list(achados) == ['README.md']
    assert 'padarias' in achados['README.md']['conteudo']


def test_token_em_readme_nao_vaza(tmp_path):
    # Arrange — README de projeto recebido tem token de exemplo com frequência,
    # e o inventory.json é commitado. As linhas `# noscan` carregam um valor com
    # FORMA de token de propósito: a guarda só se prova com fixture que parece real.
    (tmp_path / 'README.md').write_text(
        'Configure o acesso:\n\nGITHUB_TOKEN=ghp_16C7e42F292c6912E7710c838347Ae178B4a\n')  # noscan: fixture
    # Act
    achados = coletar(tmp_path, varrer(tmp_path))
    # Assert
    conteudo = achados['README.md']['conteudo']
    assert 'ghp_16C7e42F292c6912E7710c838347Ae178B4a' not in conteudo  # noscan: fixture
    assert 'GITHUB_TOKEN' in conteudo          # a chave fica; o valor não


def test_arquivo_grande_e_cortado_e_marcado(tmp_path):
    # Arrange
    (tmp_path / 'README.md').write_text('a' * (TETO_BYTES + 500))
    # Act
    item = coletar(tmp_path, varrer(tmp_path))['README.md']
    # Assert
    assert len(item['conteudo']) <= TETO_BYTES
    assert item['cortado'] is True


def test_ordem_estavel(tmp_path):
    # Arrange
    for nome in ('README.md', 'CLAUDE.md', 'AGENTS.md'):
        (tmp_path / nome).write_text('texto')
    # Act
    primeira = list(coletar(tmp_path, varrer(tmp_path)))
    segunda = list(coletar(tmp_path, varrer(tmp_path)))
    # Assert — ordem instável quebraria a idempotência do documento
    assert primeira == segunda == sorted(primeira)


def test_fonte_textual_vale_em_qualquer_profundidade():
    """Monorepo por justaposição é o caso-âncora da skill, e nele o README de cada
    aplicação não está na raiz. Com os padrões ancorados em `^`, um projeto real com
    seis READMEs na árvore entregou ZERO fontes textuais — e como "propósito só com
    fonte textual" é regra, a frase mais valiosa do documento virava lacuna por causa
    de um acento circunflexo."""
    # Arrange / Act / Assert
    assert eh_fonte_textual('admin/README.md')
    assert eh_fonte_textual('api/CLAUDE.md')
    assert eh_fonte_textual('api/docs/arquitetura.md')
    assert eh_fonte_textual('packages/core/docs/adr/0001-banco.md')
    assert eh_fonte_textual('frontend/src/locales/pt-BR.json')


def test_pasta_que_so_TERMINA_em_docs_nao_e_fonte_textual():
    """A desancoragem não pode valer pedaço de nome: `mydocs/` e `oldreadme.md` não
    são fonte textual, e sem a barra no prefixo os dois entrariam."""
    # Arrange / Act / Assert
    assert not eh_fonte_textual('src/mydocs/notas.md')
    assert not eh_fonte_textual('src/oldreadme.md')
    assert not eh_fonte_textual('src/app.py')


def test_dossie_de_tarefa_nao_e_fonte_textual_do_SISTEMA():
    """Desancorar os padrões fez a seção varrer os dossiês de trabalho: num monorepo
    real foram 68 fontes e 1,4 MB — 60 delas `plan.md` e `spec.md` de tarefas já
    entregues, com os seis maiores arquivos sendo planos de implementação. Plano de
    tarefa descreve UM trabalho passado, não o sistema; e o `inventory.json` é
    commitado."""
    # Arrange / Act / Assert
    assert not eh_fonte_textual('admin/docs/specs/2026-09-13-creators/plan.md')
    assert not eh_fonte_textual('docs/plans/2026-08-24-onda2b-front.md')
    assert not eh_fonte_textual('api/docs/specs/x/referencias/colunas-antes.txt')
    # o que continua valendo
    assert eh_fonte_textual('docs/arquitetura.md')
    assert eh_fonte_textual('docs/adr/0001-escolha-do-banco.md')
    assert eh_fonte_textual('admin/README.md')


def test_secao_tem_teto_e_declara_o_que_deixou_de_fora(tmp_path):
    """Sem teto, um projeto com documentação grande leva 1,4 MB de conteúdo para um
    arquivo commitado — e enterra as três fontes que respondem a pergunta. O caminho
    continua na lista, com motivo: a lista completa é o que permite a quem lê abrir o
    arquivo à mão. Cortar em silêncio seria "não apurado" disfarçado de "não existe"."""
    # Arrange — oito arquivos grandes: cada um entra cortado em TETO_BYTES, e é a SOMA
    # que estoura o teto da seção. Com três arquivos o teste passaria sem teto algum,
    # porque 3 × 64 KB cabe — foi o que o primeiro fixture errou.
    (tmp_path / 'docs').mkdir()
    nomes = [f'd{i}.md' for i in range(8)]
    for nome in nomes:
        (tmp_path / 'docs' / nome).write_text('x' * (100 * 1024))
    # Act
    achados = coletar(tmp_path, varrer(tmp_path))
    # Assert
    assert len(achados) == len(nomes), 'o caminho de toda fonte textual continua na lista'
    omitidos = [c for c, v in achados.items() if v.get('omitido')]
    assert omitidos, 'nada foi omitido: o teto da seção não existe'
    assert all(achados[c]['conteudo'] == '' for c in omitidos)
    assert all(achados[c]['motivo'] for c in omitidos)
    total = sum(len(v['conteudo']) for v in achados.values())
    assert total <= TETO_TOTAL


def test_readme_passa_na_frente_da_documentacao_grande(tmp_path):
    """A prioridade é por CLASSE, não por ordem alfabética nem por tamanho: README,
    CLAUDE.md e ADR respondem "o que o produto faz"; um doc solto de 300 KB quase
    nunca. Em ordem alfabética o README deste fixture seria o último, e o teto da
    seção o deixaria de fora justamente no único arquivo que importava."""
    # Arrange — os concorrentes precisam ESTOURAR o orçamento, senão o README entra
    # de qualquer jeito e o teste passa com a prioridade desligada: cada arquivo entra
    # cortado em TETO_BYTES, então são oito, não dois. E vêm antes em ordem alfabética.
    (tmp_path / 'docs').mkdir()
    for i in range(8):
        (tmp_path / 'docs' / f'd{i}.md').write_text('x' * (100 * 1024))
    (tmp_path / 'z-app').mkdir()
    (tmp_path / 'z-app' / 'README.md').write_text('# Portal\n\nCadastro de creators.')
    # Act
    achados = coletar(tmp_path, varrer(tmp_path))
    # Assert
    assert 'creators' in achados['z-app/README.md']['conteudo']
    assert not achados['z-app/README.md'].get('omitido')


def test_documentacao_que_mora_em_pasta_de_ferramenta_e_lida(tmp_path):
    """Num projeto PHP real a ÚNICA documentação era `.claude/CLAUDE.md`, e a pasta é
    podada da árvore — então `textos` vinha vazio e a regra "propósito só com fonte
    textual" transformava num nada um projeto que tem documentação escrita.

    A pasta continua fora da árvore (ela não é código e não é área); o que muda é que
    o documento dela é procurado à parte."""
    # Arrange
    (tmp_path / '.claude').mkdir()
    (tmp_path / '.claude' / 'CLAUDE.md').write_text('# Sistema\n\nApuração fiscal.')
    (tmp_path / '.claude' / 'skills').mkdir()
    (tmp_path / '.claude' / 'skills' / 'alguma-skill.md').write_text('# Skill de outro assunto')
    (tmp_path / 'app.py').write_text('x = 1')
    # Act
    achados = coletar(tmp_path, varrer(tmp_path))
    # Assert
    assert '.claude/CLAUDE.md' in achados
    assert 'Apuração fiscal' in achados['.claude/CLAUDE.md']['conteudo']
    assert '.claude/skills/alguma-skill.md' not in achados, \
        'skill instalada é de outro assunto, não documentação deste projeto'


def test_pasta_de_ferramenta_continua_fora_da_arvore(tmp_path):
    """O par do teste acima: ler o documento não pode trazer a pasta de volta para a
    contagem de arquivos nem para o menu de áreas."""
    # Arrange
    (tmp_path / '.claude').mkdir()
    (tmp_path / '.claude' / 'CLAUDE.md').write_text('# Sistema')
    (tmp_path / 'app.py').write_text('x = 1')
    # Act
    caminhos = [a['caminho'] for a in varrer(tmp_path)]
    # Assert
    assert caminhos == ['app.py']
