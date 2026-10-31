# tests/test_comentarios.py
"""Remover comentário é a única parte desta skill que apaga conhecimento.

Código deletado por engano volta do git, dos testes e do comportamento do sistema. O
comentário que registrava POR QUE a linha é daquele jeito não volta de lugar nenhum — ele
é a única cópia. Então as travas aqui são de dois tipos, e o segundo é o que importa:

  que o analisador ACHE o comentário certo — `//` dentro de `url(http://x)`, `#` dentro de
  `${#lista}` e `#` dentro de `\"\"\"docstring\"\"\"` não são comentários, e cortá-los corta
  código vivo;

  que ele NÃO proponha o que não pode sair — diretiva (`# type: ignore`, `//go:build`,
  `@ORM\\Column`) é código escrito em forma de comentário, e o "por quê" é informação que
  não existe em nenhum outro lugar do repositório.

A última trava é a mais forte: remover todos os candidatos de alta confiança de um arquivo
Python e o arquivo continuar sendo Python válido.
"""
import ast
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / 'scripts'))

import comentarios as com  # noqa: E402


def classes(texto, familia, **kw):
    """As classes atribuídas aos comentários de um trecho, em ordem."""
    spans = com.extrair(texto, familia)
    saida = []
    for inicio, fim, forma in spans:
        bruto = texto[inicio:fim]
        alvo, adiante, _ = com._alvo_de(texto, inicio, fim)
        c = {'corpo': com.corpo_de(bruto), 'forma': forma, 'texto': bruto}
        saida.append(com.classificar(c, familia, alvo, adiante,
                                     kw.get('vocabulario', set())))
    return saida


# ------------------------------------------------- o que NÃO é comentário
def test_barra_dupla_dentro_de_url_nao_e_comentario():
    """`url(http://cdn/x.png)` não é citado em CSS: o `//` ficaria exposto ao grep."""
    assert com.extrair('a{background:url(http://cdn/x.png)}', 'css') == []


def test_barra_dupla_dentro_de_string_nao_e_comentario():
    assert com.extrair('const u = "http://x/y";\n', 'c') == []


def test_cerquilha_dentro_de_expansao_do_shell_nao_e_comentario():
    """`${#lista}` é o tamanho do array. Cortar dali quebra o script."""
    assert com.extrair('echo ${#lista}\n', 'hash') == []


def test_cerquilha_dentro_de_cor_nao_e_comentario():
    assert com.extrair("cor = '#fff'\n", 'py') == []


def test_cerquilha_dentro_de_docstring_nao_e_comentario():
    fonte = 'def f():\n    """usa # como separador"""\n    return 1\n'
    assert com.extrair(fonte, 'py') == []


def test_comentario_depois_de_codigo_na_mesma_linha_e_achado():
    spans = com.extrair('contador += 1  # incrementa\n', 'py')
    assert len(spans) == 1


def test_barra_asterisco_dentro_de_classe_de_regex_nao_abre_bloco():
    """`/[/*]/` é um literal de regex. Abrir bloco ali engole o resto do arquivo."""
    assert com.extrair('const re = /[/*]/;\nconst x = 1;\n', 'c') == []


def test_texto_fora_da_tag_php_nao_e_codigo_php():
    """Num `.php`, o que está fora de `<?php` é HTML — `//` ali é texto da página."""
    assert com.extrair('<div>a // b</div>\n', 'php') == []


def test_dentro_da_tag_php_a_barra_dupla_e_comentario():
    spans = com.extrair('<?php\n// nota\n$x = 1;\n', 'php')
    assert len(spans) == 1


# ------------------------------------------------- protegido: diretiva
def test_shebang_nunca_e_candidato():
    assert classes('#!/usr/bin/env python3\n', 'py')[0]['classe'] == 'diretiva'


def test_type_ignore_e_diretiva():
    c = classes('x = f()  # type: ignore\n', 'py')[0]
    assert c['classe'] == 'diretiva' and c['acao'] == 'manter'


def test_eslint_disable_e_diretiva():
    assert classes('// eslint-disable-next-line no-unused-vars\n', 'c')[0]['classe'] \
        == 'diretiva'


def test_go_build_e_diretiva():
    assert classes('//go:build linux\n', 'c')[0]['classe'] == 'diretiva'


def test_docblock_do_doctrine_e_diretiva_porque_e_o_schema():
    """`@ORM\\Column` num docblock define a coluna do banco. Remover apaga o schema."""
    fonte = '<?php\n/**\n * @ORM\\Column(type="string")\n */\nprivate $nome;\n'
    assert classes(fonte, 'php')[0]['classe'] == 'diretiva'


def test_data_provider_do_phpunit_e_diretiva():
    fonte = '<?php\n/**\n * @dataProvider casos\n */\npublic function testX() {}\n'
    assert classes(fonte, 'php')[0]['classe'] == 'diretiva'


def test_frozen_string_literal_e_diretiva():
    assert classes('# frozen_string_literal: true\n', 'hash')[0]['classe'] == 'diretiva'


def test_prettier_ignore_e_diretiva():
    assert classes('// prettier-ignore\n', 'c')[0]['classe'] == 'diretiva'


def test_spdx_e_licenca():
    assert classes('// SPDX-License-Identifier: MIT\n', 'c')[0]['classe'] == 'licenca'


# ------------------------------------------------- protegido: o porquê
def test_o_comentario_que_diz_o_motivo_fica():
    c = classes('// usa laço porque o map quebrava com array esparso\n'
                'for (const x of xs) {}\n', 'c')[0]
    assert c['classe'] == 'porque' and c['acao'] == 'manter'


def test_o_comentario_que_cita_issue_fica():
    assert classes('// ver #4312\nx();\n', 'c')[0]['classe'] == 'porque'


def test_o_aviso_fica():
    assert classes('// nunca chame isto dentro da transação\nx();\n',
                   'c')[0]['classe'] == 'porque'


def test_a_medida_fica():
    assert classes('// 40ms mais rápido que o regex\nx();\n',
                   'c')[0]['classe'] == 'porque'


def test_a_dependencia_de_ordem_fica():
    assert classes('// a ordem importa: o token expira antes do refresh\nx();\n',
                   'c')[0]['classe'] == 'porque'


def test_codigo_comentado_com_motivo_declarado_nao_e_remocao_cega():
    """`// desativado porque o cliente não aprovou — #88` termina parecendo código.

    O motivo vence: o par (código morto + razão) é um registro de decisão, e quem decide
    é o humano.
    """
    c = classes('<?php\n// $x = 1; desativado porque o cliente não aprovou — #88\n',
                'php')[0]
    assert c['classe'] == 'porque'


def test_todo_com_conteudo_e_divida_registrada():
    c = classes('// TODO: tratar o caso de CPF duplicado\n', 'c')[0]
    assert c['classe'] == 'pendencia' and c['acao'] == 'manter'


# ------------------------------------------------- candidato
def test_todo_vazio_e_scaffold():
    assert classes('// TODO\n', 'c')[0]['classe'] == 'scaffold'


def test_stub_gerado_pela_ide_e_scaffold():
    assert classes('// TODO Auto-generated method stub\n', 'c')[0]['classe'] == 'scaffold'


def test_cabecalho_de_ide_e_scaffold_e_carrega_nome_de_usuario():
    c = classes('// Created by IntelliJ IDEA.\n', 'c')[0]
    assert c['classe'] == 'scaffold' and 'usuário' in c['sinal']


def test_divisoria_e_candidato():
    assert classes('// ==============================\n', 'c')[0]['classe'] == 'divisoria'


def test_docblock_vazio_e_candidato():
    assert classes('/**\n *\n */\nfunction f() {}\n', 'c')[0]['classe'] == 'divisoria'


def test_codigo_comentado_e_candidato():
    c = classes('// return nil;\n', 'c')[0]
    assert c['classe'] == 'codigo_comentado' and 'git' in c['sinal']


def test_chamada_comentada_e_candidato():
    assert classes('// console.log(x);\n', 'c')[0]['classe'] == 'codigo_comentado'


def test_bloco_de_codigo_comentado_e_candidato():
    fonte = '/*\nif (x) {\n  y();\n}\n*/\n'
    assert classes(fonte, 'c')[0]['classe'] == 'codigo_comentado'


def test_comentario_que_repete_a_linha_e_candidato():
    """`// incrementa o contador` sobre `contador++`: o `++` já diz "incrementa"."""
    c = classes('// incrementa o contador\ncontador++;\n', 'c')[0]
    assert c['classe'] == 'redundante'


def test_comentario_no_rabo_que_repete_a_linha_e_candidato():
    c = classes('contador++;  // incrementa o contador\n', 'c')[0]
    assert c['classe'] == 'redundante'


def test_construtor_sobre_o_construtor_e_scaffold():
    c = classes('<?php\n/** Construtor */\npublic function __construct() {}\n', 'php')[0]
    assert c['classe'] in ('scaffold', 'redundante')


def test_comentario_que_acrescenta_uma_palavra_nao_e_repeticao():
    """Uma palavra que o código não tem pode ser justamente a informação que falta."""
    c = classes('// incrementa o contador de tentativas falhas\ncontador++;\n', 'c')[0]
    assert c['classe'] != 'redundante'


def test_comentario_longo_nunca_e_julgado_por_repeticao():
    fonte = ('// soma o contador do total de itens do carrinho do cliente ativo\n'
             'contador++;\n')
    assert classes(fonte, 'c')[0]['classe'] != 'redundante'


def test_docblock_que_mente_sai_para_corrigir_nao_para_remover():
    fonte = '<?php\n/**\n * @param string $b\n */\nfunction f($c) {}\n'
    c = classes(fonte, 'php')[0]
    assert c['classe'] == 'contradiz' and c['acao'] == 'corrigir'


def test_docblock_que_bate_com_a_assinatura_nao_contradiz():
    fonte = '<?php\n/**\n * @param string $c\n */\nfunction f($c) {}\n'
    assert classes(fonte, 'php')[0]['classe'] != 'contradiz'


def test_comentario_que_cita_simbolo_inexistente_e_orfao():
    c = classes('// ver AuthLegacyService\nx();\n', 'c',
                vocabulario={'x', 'pagamento'})[0]
    assert c['classe'] == 'orfao' and 'AuthLegacyService' in c['sinal']


def test_comentario_que_cita_simbolo_existente_nao_e_orfao():
    c = classes('// ver AuthLegacyService\nx();\n', 'c',
                vocabulario={'authlegacyservice'})[0]
    assert c['classe'] != 'orfao'


def test_prosa_nao_provada_desnecessaria_fica_para_o_humano():
    c = classes('// o cálculo segue a tabela do contador anexa\nz();\n', 'c',
                vocabulario={'contador', 'z', 'tabela', 'calculo'})[0]
    assert c['confianca'] == 'baixa' and c['acao'] == 'decidir'


def test_docblock_de_api_sai_como_baixa_e_nao_como_remover():
    fonte = '/**\n * @param {string} nome\n * @returns {boolean}\n */\n' \
            'export function v(nome) {}\n'
    c = classes(fonte, 'c')[0]
    assert c['classe'] == 'doc' and c['acao'] == 'decidir'


# ------------------------------------------------- a remoção
def test_a_linha_so_de_comentario_sai_inteira(tmp_path):
    arq = tmp_path / 'a.py'
    arq.write_text('x = 1\n# nota\ny = 2\n', encoding='utf-8')
    dados = com.apurar(tmp_path)
    com.aplicar(tmp_path, [a for a in dados['achados']])
    assert arq.read_text(encoding='utf-8') == 'x = 1\ny = 2\n'


def test_o_comentario_de_rabo_sai_sem_deixar_espaco(tmp_path):
    arq = tmp_path / 'a.py'
    arq.write_text('x = 1  # nota\n', encoding='utf-8')
    dados = com.apurar(tmp_path)
    com.aplicar(tmp_path, dados['achados'])
    assert arq.read_text(encoding='utf-8') == 'x = 1\n'


def test_remocao_recusa_quando_o_arquivo_mudou(tmp_path):
    """Offset velho corta no lugar errado — é assim que uma limpeza corrompe código."""
    arq = tmp_path / 'a.py'
    arq.write_text('x = 1\n# nota\n', encoding='utf-8')
    dados = com.apurar(tmp_path)
    arq.write_text('y = 9\nz = 8\n', encoding='utf-8')

    r = com.aplicar(tmp_path, dados['achados'])

    assert r['removidos'] == []
    assert 'mudou' in r['recusados'][0]['motivo']
    assert arq.read_text(encoding='utf-8') == 'y = 9\nz = 8\n'


def test_remocao_toca_so_o_que_foi_aprovado(tmp_path):
    arq = tmp_path / 'a.py'
    arq.write_text('# fica\n\n# sai\nx = 1\n', encoding='utf-8')
    dados = com.apurar(tmp_path)
    escolhido = [a for a in dados['achados'] if a['corpo'] == 'sai']

    com.aplicar(tmp_path, escolhido)

    assert arq.read_text(encoding='utf-8') == '# fica\n\nx = 1\n'


def test_o_arquivo_continua_valido_depois_de_tirar_os_candidatos(tmp_path):
    """A trava mais forte: cortar tudo que a skill chamaria de alta e o Python ainda parsear."""
    fonte = (
        '#!/usr/bin/env python3\n'
        '# -*- coding: utf-8 -*-\n'
        '"""Módulo de exemplo."""\n'
        '# ====================\n'
        'import os  # noqa\n'
        '\n'
        '\n'
        'def soma(a, b):\n'
        '    # retorna a soma\n'
        '    total = a + b  # soma\n'
        '    # print(total)\n'
        '    return total  # type: ignore\n'
    )
    arq = tmp_path / 'm.py'
    arq.write_text(fonte, encoding='utf-8')
    dados = com.apurar(tmp_path)
    altos = [a for a in dados['achados'] if a['confianca'] == 'alta']

    assert altos, 'o fixture precisa ter candidatos, senão o teste não prova nada'
    com.aplicar(tmp_path, altos)
    depois = arq.read_text(encoding='utf-8')

    ast.parse(depois)
    assert '#!/usr/bin/env python3' in depois        # shebang intacto
    assert 'coding: utf-8' in depois                 # diretiva de encoding intacta
    assert '# noqa' in depois                        # diretiva de linter intacta
    assert 'type: ignore' in depois                  # diretiva de tipo intacta
    assert '====' not in depois                      # a divisória saiu
    assert '# print(total)' not in depois            # o código comentado saiu


def test_a_apuracao_e_estavel_entre_duas_rodadas(tmp_path):
    (tmp_path / 'a.py').write_text('# nota\nx = 1\n', encoding='utf-8')
    (tmp_path / 'b.js').write_text('// nota\nconst y = 2;\n', encoding='utf-8')
    um = json.dumps(com.apurar(tmp_path), sort_keys=True, ensure_ascii=False)
    dois = json.dumps(com.apurar(tmp_path), sort_keys=True, ensure_ascii=False)
    assert um == dois


def test_extensao_sem_familia_vira_lacuna_com_motivo(tmp_path):
    """Não apurado ≠ não existe: o que não deu para ler aparece dito."""
    (tmp_path / 'a.erl').write_text('% nota\n', encoding='utf-8')
    dados = com.apurar(tmp_path)
    assert dados['nao_lidos'] == {'.erl': 1}
    assert 'sem família de sintaxe' in com.resumir(dados)


def test_arquivo_gerado_fica_fora():
    """Comentário de gerador não é de pessoa, e inflaria a lista com centenas de itens."""
    assert com.familia_de(pathlib.Path('x.min.js')) == 'c'   # a família existe
    # mas a varredura o descarta pelo sufixo de gerado
    assert 'x.min.js'.endswith(com.GERADOS)


def test_markdown_fica_fora_da_varredura(tmp_path):
    (tmp_path / 'LEIAME.md').write_text('<!-- nota -->\n', encoding='utf-8')
    assert com.apurar(tmp_path)['comentarios'] == 0


# ------------------------------------------------- achados de uma rodada real
# As três travas abaixo nasceram de rodar o analisador em três projetos de verdade e LER
# os candidatos, um a um. A suíte acima estava inteira verde enquanto ele propunha apagar
# a estrutura dos testes de outra skill desta casa.
def test_o_marcador_aaa_nao_e_repeticao_da_linha():
    """`# Assert` sobre `assert x == 1` repete a palavra — e é a estrutura do teste.

    Eram 200 dos 317 candidatos a `redundante` num projeto de 76 arquivos. O marcador não
    descreve a linha seguinte; ele marca onde um bloco começa.
    """
    c = classes('# Assert\nassert caminhos == [\'src\']\n', 'py')[0]
    assert c['classe'] == 'marcador' and c['acao'] == 'manter'


def test_os_marcadores_de_bdd_tambem_ficam():
    for marca in ('Arrange', 'Act', 'Given', 'When', 'Then', 'Ação', 'Verificação'):
        c = classes(f'# {marca}\nx = 1\n', 'py')[0]
        assert c['classe'] == 'marcador', marca


def test_a_prosa_que_a_linha_imprime_nao_torna_o_comentario_repetido():
    """O comentário casava com o TEXTO que a linha imprime, não com o que ela faz."""
    fonte = ("# importa nada fora de si\n"
             "corpo += '<p>O núcleo não importa nada fora de si.</p>'\n")
    assert classes(fonte, 'py')[0]['classe'] != 'redundante'


def test_a_legenda_de_um_regex_nao_e_repeticao():
    """Regex é o caso canônico de código que pede legenda: ela repete os literais do
    padrão por necessidade, e sem ela o padrão fica nu."""
    fonte = ('const PADRAO = /(?:^|\\n)\\s*export\\s+[^;]*?from/;'
             '  // export … from\n')
    assert classes(fonte, 'c')[0]['classe'] != 'redundante'


def test_linhas_de_comentario_seguidas_sao_um_comentario_so():
    """Um bloco `//` de três linhas entrava como três comentários.

    Medido em projeto real: o "porque" da primeira linha não protegia as duas seguintes, e
    as continuações saíam como candidatas — o conserto deixaria no arquivo uma explicação
    decapitada.
    """
    fonte = ('// avalia a data de nascimento porque a conta ainda não existe\n'
             '// quando isto roda, e o menor sem responsável confirmado é o\n'
             '// único caso em que o fluxo de ativação não fecha\n'
             'avaliar();\n')
    spans = com.agrupar(fonte, com.extrair(fonte, 'c'))

    assert len(spans) == 1
    assert classes(fonte, 'c')[0]['classe'] == 'porque'


def test_linha_em_branco_separa_dois_comentarios():
    fonte = '// um\n\n// dois\n'
    assert len(com.agrupar(fonte, com.extrair(fonte, 'c'))) == 2


def test_comentario_no_rabo_nao_se_junta_ao_de_cima():
    fonte = '// nota\nx();  // outra\n'
    assert len(com.agrupar(fonte, com.extrair(fonte, 'c'))) == 2


def test_diretiva_condicional_do_mysql_e_protegida():
    """`/*!40101 SET … */` num dump não é comentário: o servidor executa a linha."""
    fonte = '/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;\n'
    c = classes(fonte, 'dash')[0]
    assert c['classe'] == 'diretiva' and c['acao'] == 'manter'


def test_o_contrafactual_em_portugues_e_um_porque():
    """"sem a contrabarra, /robots-txt também cairia aqui" explica a razão sem a palavra."""
    fonte = ("<?php\n// sem a contrabarra, /robots-txt e /robotsXtxt também cairiam aqui\n"
             "Rota::get('robots\\.txt');\n")
    assert classes(fonte, 'php')[0]['classe'] != 'orfao'


def test_nome_inventado_pelo_comentario_nao_e_orfao():
    """Palavra de aparência técnica dentro de prosa não é referência a símbolo."""
    c = classes('// aqui um ValorQualquer nunca existiu de verdade\nx();\n', 'c',
                vocabulario={'x'})[0]
    assert c['classe'] != 'orfao'


def test_referencia_explicita_a_simbolo_inexistente_continua_sendo_orfao():
    c = classes('// ver AuthLegacyService\nx();\n', 'c', vocabulario={'x'})[0]
    assert c['classe'] == 'orfao'


def test_banner_de_gerador_nao_e_remocao_segura():
    """"Generated by IcoMoon" num asset pode ser a atribuição que a licença exige."""
    c = classes('/* Generated by IcoMoon.io */\n', 'css')[0]
    assert c['classe'] == 'gerador' and c['confianca'] == 'media'


def test_prosa_que_comeca_com_palavra_chave_nao_e_codigo():
    """`If done with making changes, start watching…` começa com `if` e é inglês."""
    c = classes('// If done with making changes, start watching for changes\nx();\n',
                'c')[0]
    assert c['classe'] != 'codigo_comentado'


def test_palavra_acentuada_nao_vira_palavra_chave():
    """`Função helper…` cortava no `ç` e deixava o token `fun`, que é palavra-chave."""
    c = classes('// Função helper para obter label de enum\nf();\n', 'c')[0]
    assert c['classe'] != 'codigo_comentado'


def test_prosa_com_parenteses_nao_e_chamada_de_funcao():
    c = classes('<!-- Arquivos (apenas criação) -->\n', 'html')[0]
    assert c['classe'] != 'codigo_comentado'


def test_documentacao_com_exemplo_de_uso_nao_e_codigo_desativado():
    """O bloco que ENSINA a usar o módulo tem código dentro; apagá-lo apaga o manual."""
    fonte = ('/*\n * Flags de ambiente centralizadas.\n *\n * Uso:\n'
             " *   import { isDev } from '@/utils/env';\n */\nexport const isDev = 1;\n")
    assert classes(fonte, 'c')[0]['classe'] != 'codigo_comentado'


def test_bloco_majoritariamente_codigo_continua_sendo_codigo_desativado():
    fonte = '/*\nif (x) {\n  y();\n}\n*/\n'
    assert classes(fonte, 'c')[0]['classe'] == 'codigo_comentado'


def test_faixa_de_secao_rotula_o_bloco_e_nao_a_linha():
    c = classes('// === RADIUS ===\n--radius-sm: 2px;\n', 'c')[0]
    assert c['classe'] == 'marcador'


def test_divisoria_pura_continua_candidata():
    assert classes('// ==============================\n', 'c')[0]['classe'] == 'divisoria'


def test_comentario_que_rotula_um_bloco_nao_e_repeticao():
    """`// Status de API` acima de `API_STATUS = {` é o título do objeto, não da linha."""
    c = classes('// Status de API\nconst API_STATUS = {\n', 'c')[0]
    assert c['classe'] != 'redundante'


def test_exemplo_dentro_do_comentario_nao_e_simbolo_orfao():
    """`funil/page.tsx → (funil, page)` ensina o formato; não cita arquivo real."""
    c = classes('# 2. o nome É o papel: funil/page.tsx → (funil, page)\nx = 1\n', 'py',
                vocabulario={'x'})[0]
    assert c['classe'] != 'orfao'


def test_comentario_no_rabo_nao_engole_a_linha_de_baixo():
    """`total = a + b  # soma` juntava com `# print(total)` da linha seguinte.

    O código desativado desaparecia dentro de um comentário de outra natureza: deixava de
    ser proposto, e a comparação de repetição passava a usar o alvo errado.
    """
    fonte = 'total = a + b  # soma\n# print(total)\n'
    spans = com.agrupar(fonte, com.extrair(fonte, 'py'))

    assert len(spans) == 2
    assert classes(fonte, 'py')[1]['classe'] == 'codigo_comentado'


def test_comentario_de_uma_palavra_e_rotulo_nao_repeticao():
    """`# RabbitMQ` acima de `RABBITMQ_HOST=...` nomeia o grupo, não descreve a linha."""
    c = classes('# RabbitMQ\nRABBITMQ_HOST=fila\n', 'hash')[0]
    assert c['classe'] != 'redundante'


def test_prosa_com_igual_dentro_nao_e_atribuicao():
    """`status=OPEN nulifica delivery`: duas palavras soltas lado a lado não são expressão."""
    fonte = '<?php\n// status=OPEN nulifica delivery\n$x = 1;\n'
    assert classes(fonte, 'php')[0]['classe'] != 'codigo_comentado'


def test_atribuicao_de_verdade_continua_sendo_codigo():
    fonte = "<?php\n// $this->mail->SMTPSecure = PHPMailer::ENCRYPTION_SMTPS;\n"
    assert classes(fonte, 'php')[0]['classe'] == 'codigo_comentado'


def test_variavel_de_ambiente_comentada_e_codigo():
    assert classes('# REDIS_PORT=6379\n', 'hash')[0]['classe'] == 'codigo_comentado'


def test_a_legenda_de_uma_alternativa_de_regex_e_protegida():
    """Removida de verdade num ensaio de ponta a ponta: o padrão ficou nu.

    `# import 'x' (efeito)` começa com palavra-chave e tem parêntese, então a regra de
    código desativado a acusava; e ela repete os literais do padrão, então a regra de
    repetição também. A legenda de um regex é o guard "explica o incompreensível".
    """
    fonte = ('''FORMAS = re.compile(\n'''
             '''    r"""|(?:^|\\n)\\s*import\\s*['"]([^'"]+)['"]"""  # import 'x' (efeito)\n''')
    c = classes(fonte, 'py')[-1]
    assert c['classe'] == 'legenda' and c['acao'] == 'manter'


def test_a_legenda_de_operacao_de_bits_e_protegida():
    c = classes('flags = valor & 0xFF  // só o byte baixo\n', 'c')[0]
    assert c['classe'] == 'legenda'


def test_arquivo_com_crlf_mantem_as_quebras_de_linha(tmp_path):
    """Remover um comentário não converte o arquivo.

    Medido em projeto real: `read_text`/`write_text` traduzem a quebra de linha, e tirar um
    comentário de uma linha num arquivo CRLF de 280 linhas trazia as 280 no diff. Diff
    inflado é revisão impossível — e é onde um erro de verdade passa sem ser visto.
    """
    arq = tmp_path / 'a.php'
    arq.write_bytes(b"<?php\r\n$x = 1;\r\n// sai\r\n$y = 2;  // fica porque ainda falta\r\n")

    dados = com.apurar(tmp_path)
    com.aplicar(tmp_path, [a for a in dados['achados'] if a['corpo'] == 'sai'])

    bruto = arq.read_bytes()
    assert bruto == b"<?php\r\n$x = 1;\r\n$y = 2;  // fica porque ainda falta\r\n"
    assert b'\n' not in bruto.replace(b'\r\n', b'')


def test_aplicar_recusa_protegido_mesmo_se_mandado(tmp_path):
    """Passar a apuração inteira em vez da lista aprovada é o erro barato de cometer."""
    arq = tmp_path / 'a.py'
    arq.write_text('# type: ignore\nx = 1\n', encoding='utf-8')
    dados = com.apurar(tmp_path)

    r = com.aplicar(tmp_path, dados['achados'])

    assert r['removidos'] == []
    assert 'protegido' in r['recusados'][0]['motivo']
    assert arq.read_text(encoding='utf-8') == '# type: ignore\nx = 1\n'


def test_toda_classe_emitida_tem_rotulo_no_resumo():
    """Classe nova sem rótulo derruba o resumo com KeyError na hora de imprimir."""
    import re as _re
    fonte = (RAIZ / 'scripts' / 'comentarios.py').read_text(encoding='utf-8')
    emitidas = set(_re.findall(r"'classe': '(\w+)'", fonte))
    assert emitidas <= set(com.ROTULO), emitidas - set(com.ROTULO)
