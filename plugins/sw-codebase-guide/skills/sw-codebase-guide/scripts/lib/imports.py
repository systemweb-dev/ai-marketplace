"""Grafo de dependências por import, resolvido pela EVIDÊNCIA.

Resolver a string do import em arquivo exigiria, em tese, ler o `paths` do tsconfig,
o PSR-4 do composer e o apelido do bundler. Num projeto real medido o apelido mora
num `vue.config.js` — JavaScript executando, não dado. Então a resolução é feita
contra os arquivos que EXISTEM, e a configuração entra só como atalho conferido.

Este módulo orquestra: despacha por extensão, chama o extrator da linguagem e o
resolvedor, conta os sete baldes e ordena. Quem conhece sintaxe é `lib/linguagens/`;
quem conhece o sistema de arquivos é `lib/resolucao.py`.
"""
from collections import defaultdict
from pathlib import Path

from lib import resolucao, stacks as mod_stacks
from lib.arvore import linguagem_de
from lib.linguagens import js, php, python

# O despacho é por EXTENSÃO, não por stack detectada. A regra por stack já deixou
# 210 arquivos Python nem parseados nem declarados como lacuna, e a detecção por
# extensão do `stacks.py` tem piso de MIN_ARQUIVOS = 5: dois arquivos `.ts` num
# projeto PHP sumiriam em silêncio. Além disso `node` é uma stack só para cinco
# extensões, então o nome dela não identificaria o extrator de qualquer forma.
MODULOS = {'python': python, 'js': js, 'php': php}

# Linguagem que TEM sistema de módulos e que esta versão ainda não resolve. A lista
# é fechada de propósito: sem ela, o documento declarava lacuna para `.log`, `.css`,
# `.txt` e `.sql` — vinte linhas de "não medi" antes de qualquer conteúdo, que é
# exatamente o ruído que a v0.1.1 custou. Ninguém lê "não há grafo de import para
# arquivo de log" como informação.
COM_IMPORT = frozenset({'go', 'java', 'kotlin', 'swift', 'rust', 'ruby', 'csharp',
                        'scala', 'elixir', 'dart', 'c', 'cpp', 'objc'})
POR_EXTENSAO = {ext: nome for nome, mod in MODULOS.items() for ext in mod.EXTENSOES}

TETO_EXEMPLOS = 5   # com teto e ordem, porque o inventory.json tem que dar diff

VAZIO = {'relativos': 0, 'externos': 0, 'sufixo_unico': 0, 'base_provada': 0,
         'config_conferida': 0, 'ambiguos': 0, 'pendurados': 0, 'nao_resolvidos': 0}


def _declarados_de(caminho: str, por_manifesto: dict) -> set:
    """As dependências do manifesto ANCESTRAL MAIS PRÓXIMO do arquivo.

    Não a união de todos: num monorepo, a união torna o falso-externo mais provável
    — e falso-externo infla a taxa escondendo aresta interna.
    """
    melhor, nomes = -1, set()
    for manifesto, declarados in por_manifesto.items():
        pasta = str(Path(manifesto).parent)
        pasta = '' if pasta == '.' else pasta + '/'
        if caminho.startswith(pasta) and len(pasta) > melhor:
            melhor, nomes = len(pasta), declarados
    return nomes


def _por_configuracao(alvo, prefixos, indice, extensoes, arquivo_de_pasta):
    """O atalho declarado: `App\\X\\Y` -> `app/X/Y.php` por substituição de prefixo.

    Já vem conferido contra o disco pelo `ler_vocabulario` — o que apontava para
    pasta inexistente foi descartado lá. É o que leva o PHP perto de 100%.
    """
    for declarado, base in prefixos:
        if alvo == declarado or alvo.startswith(declarado + '/'):
            resto = alvo[len(declarado):].lstrip('/')
            destino = resolucao.resolver_relativo(
                f'{base}/x', f'./{resto}', indice, extensoes, arquivo_de_pasta)
            if destino:
                return destino
    return None


def _de_fora(alvo, prefixo, indice, vocab, modulo, classe) -> bool:
    r"""Nada casou no índice. O alvo vem de FORA do projeto, ou a medição falhou?

    A pergunta é sobre o primeiro segmento: se nem ele existe no projeto e ele não é
    um prefixo que o projeto declara possuir, o alvo inteiro é de outra gente.
    Contá-lo como "não resolvido" confunde dependência externa com falha de medição,
    e a diferença é enorme na taxa — medido: isso levava o Python a **33%** e o PHP
    a **57%**, os dois abaixo do piso de 70%, com as arestas todas certas.

    Os dois casos reais que a regra cobre:

    - **Python:** `from collections import Counter` gera o candidato
      `collections/Counter`. A base é stdlib e sai como externa, mas o derivado
      caía em não-resolvido — eram 588 numa varredura só.
    - **PHP:** `use SysWeb\Controller` é o framework, que mora em `vendor/` e foi
      podado. O `composer.json` declara o pacote como `systemweb/framework`, e o
      namespace é `SysWeb\` — **nome de pacote e namespace são coisas diferentes**,
      então a checagem por dependência declarada não alcança isso.
    """
    if prefixo.startswith(('@', '~')):
        # prefixo de APELIDO nunca existe como arquivo — é essa a natureza dele. Sem
        # esta linha, todo import apelidado que não resolveu de primeira virava
        # "externo", inflando o balde e matando a segunda passada: num projeto cujos
        # apelidos são planos, era o caminho fraco inteiro desaparecendo. Pacote
        # escopado com `@` já foi tratado antes, pela dependência declarada.
        return False
    if classe == 'nome_puro' and modulo.NOME_PURO_PODE_SER_INTERNO:
        return True     # `import json` sem `json.py` no projeto: é a stdlib
    if any(prefixo == declarado or prefixo.startswith(declarado + '/')
           for declarado, _ in vocab['prefixos']):
        return False    # o projeto DECLARA possuir este prefixo: falha de medição
    achados, _ = resolucao.candidatos(prefixo, indice, modulo.EXTENSOES,
                                      modulo.ARQUIVO_DE_PASTA, min_segmentos=1)
    return not achados


def grafo(raiz, stacks: list, arvore: list, recorte=None) -> dict:
    """Arestas de import do que deu para resolver, e a contagem do que não deu.

    `stacks` continua na assinatura para não quebrar quem chama, e não é usado: o
    despacho é por extensão.

    A árvore recebida é a do projeto INTEIRO, mesmo numa rodada com `--area`: um
    import que sai da área não pode virar `nao_resolvidos` e derrubar a taxa sem
    nada estar errado. O recorte é aplicado só no fim, sobre as arestas.
    """
    raiz = Path(raiz)
    por_manifesto = mod_stacks.dependencias_declaradas(raiz)
    caminhos = [i['caminho'] for i in arvore if not i['gerado']]

    # agrupado por LINGUAGEM, não por extensão: um projeto Vue tem `.ts`, `.js` e
    # `.vue`, e três blocos no documento seriam três pisos de 70% sobre um terço
    # dos dados cada
    por_linguagem, sem_extrator = defaultdict(list), defaultdict(list)
    for caminho in caminhos:
        extensao = Path(caminho).suffix.lower()
        nome = POR_EXTENSAO.get(extensao)
        if nome:
            por_linguagem[nome].append(caminho)
        elif linguagem_de(Path(caminho)) in COM_IMPORT:
            sem_extrator[extensao].append(caminho)

    arestas, indisponivel, contagem, barris = [], [], {}, []

    for extensao, arquivos in sorted(sem_extrator.items()):
        indisponivel.append({
            'stack': extensao,
            'motivo': f'{len(arquivos)} arquivo(s) {extensao}, e esta versão não tem '
                      f'resolvedor de import para eles; isto NÃO significa que nada '
                      f'depende de nada'})

    for nome, arquivos in sorted(por_linguagem.items()):
        modulo = MODULOS[nome]
        # o índice cobre TODOS os arquivos do projeto, não só os da linguagem: um
        # `import logo from '@/assets/logo.png'` é dependência real, e o `.png`
        # jamais estaria num índice feito só de `.ts`
        indice = resolucao.indexar(caminhos)
        vocab = resolucao.ler_vocabulario(raiz, modulo.CONFIGS)
        cont = dict(VAZIO)
        resolvidos, pendentes, nao_resolvidos = [], [], []

        for caminho in arquivos:
            try:
                texto = (raiz / caminho).read_text('utf-8', 'replace')
            except OSError:
                continue
            if resolucao.eh_barril(texto):
                barris.append(caminho)
            declarados = _declarados_de(caminho, por_manifesto)
            for alvo in modulo.extrair(texto):
                classe = modulo.classificar(alvo)
                if classe == 'relativo':
                    destino = resolucao.resolver_relativo(
                        caminho, alvo, indice, modulo.EXTENSOES, modulo.ARQUIVO_DE_PASTA)
                    if destino and destino != caminho:
                        cont['relativos'] += 1
                        arestas.append({'de': caminho, 'para': destino,
                                        'origem': 'relativo'})
                    elif resolucao.aponta_para_podado(caminho, alvo):
                        # aponta para dentro de `vendor/` ou `node_modules/`: é
                        # dependência externa, não falha de medição
                        cont['externos'] += 1
                    else:
                        cont['pendurados'] += 1
                    continue
                if resolucao.eh_externo(alvo, classe, modulo.BUILTINS, declarados,
                                        vocab['raizes'],
                                        modulo.NOME_PURO_PODE_SER_INTERNO):
                    cont['externos'] += 1
                    continue
                destino = _por_configuracao(alvo, vocab['prefixos'], indice,
                                            modulo.EXTENSOES, modulo.ARQUIVO_DE_PASTA)
                if destino:
                    if destino != caminho:
                        cont['config_conferida'] += 1
                        arestas.append({'de': caminho, 'para': destino,
                                        'origem': 'config_conferida'})
                    continue
                prefixo, _, resto = alvo.partition('/')
                # a string INTEIRA antes da string sem o primeiro segmento: em Python
                # `lib/config` casa inteiro, e em PHP `App/Dominio/X` só casa sem o
                # `App`, porque a pasta é `app` minúscula
                achados, sufixo = [], ''
                # nome puro não tem prefixo para tirar: a string é o caminho inteiro
                # do módulo, e o piso de dois segmentos (que existe para o RESTO de
                # um apelido) o barraria à toa — `from pedido import X` com
                # `pedido.py` no projeto é aresta de verdade
                piso = 1 if classe == 'nome_puro' else resolucao.MIN_SEGMENTOS
                for tentativa in (alvo, resto):
                    if not tentativa:
                        continue
                    achados, sufixo = resolucao.candidatos(
                        tentativa, indice, modulo.EXTENSOES, modulo.ARQUIVO_DE_PASTA,
                        min_segmentos=piso)
                    if achados:
                        break
                if len(achados) == 1:
                    if achados[0] != caminho:
                        cont['sufixo_unico'] += 1
                        arestas.append({'de': caminho, 'para': achados[0],
                                        'origem': 'sufixo_unico'})
                        resolvidos.append((prefixo, sufixo, achados[0]))
                elif not achados and _de_fora(alvo, prefixo, indice, vocab,
                                              modulo, classe):
                    cont['externos'] += 1
                else:
                    pendentes.append((caminho, prefixo, resto or alvo, achados, sufixo))

        provadas = resolucao.bases_provadas(resolvidos)
        for caminho, prefixo, resto, achados, sufixo in pendentes:
            destino = resolucao.desempatar(prefixo, resto, achados, sufixo, provadas,
                                           indice, modulo.EXTENSOES,
                                           modulo.ARQUIVO_DE_PASTA)
            if destino and destino != caminho:
                cont['base_provada'] += 1
                arestas.append({'de': caminho, 'para': destino, 'origem': 'base_provada'})
            elif destino:
                continue
            elif achados:
                cont['ambiguos'] += 1
                nao_resolvidos.append(f'{caminho}: {prefixo}/{resto}')
            else:
                cont['nao_resolvidos'] += 1
                nao_resolvidos.append(f'{caminho}: {prefixo}/{resto}')

        cont['exemplos_nao_resolvidos'] = sorted(nao_resolvidos)[:TETO_EXEMPLOS]
        contagem[nome] = cont

    if recorte is not None and recorte.parcial:
        # UMA ponta dentro, não as duas: a aresta que cruza a fronteira é o valor
        # da seção — "para mexer aqui você mexe lá fora".
        arestas = [a for a in arestas
                   if a['de'] in recorte or a['para'] in recorte]

    if not arestas and not indisponivel and not contagem:
        indisponivel.append({
            'stack': '(nenhuma)',
            'motivo': 'nenhum arquivo de linguagem reconhecida foi encontrado, então '
                      'não houve o que resolver; isto NÃO significa que nada depende '
                      'de nada'})

    # Ordenação GLOBAL no fim, uma vez só: o laço por linguagem insere intercalado, e
    # sem isto o `inventory.json` sairia diferente a cada rodada.
    return {'arestas': sorted(arestas, key=lambda a: (a['de'], a['para'], a['origem'])),
            'indisponivel': sorted(indisponivel, key=lambda i: i['stack']),
            'resolucao': contagem,
            'barris': sorted(barris)}
