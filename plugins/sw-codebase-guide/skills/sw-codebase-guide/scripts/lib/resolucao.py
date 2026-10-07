"""Resolve a string de import no arquivo — pela EVIDÊNCIA, não pela configuração.

Resolver pelo que o projeto declara exige um leitor por formato, e num projeto real
medido os apelidos moram num `vue.config.js`: JavaScript executando, não dado.
Resolvendo pelos arquivos que EXISTEM, o mesmo projeto resolve 100% dos imports
internos — e os quatro apelidos inferidos batem exatamente com os declarados lá.

**A invariante deste arquivo: aresta errada é pior que aresta faltando.** A falta
aparece na taxa de resolução e o leitor a vê; a errada manda alguém mexer no arquivo
errado e não deixa rastro. Por isso ambíguo não resolve, por isso configuração só
vale conferida, e por isso um segmento só não basta.

Nada aqui conhece linguagem: as três categorias (`relativo`, `qualificado`,
`nome_puro`) e as constantes de forma chegam de fora, declaradas por cada módulo de
`lib/linguagens/`.
"""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

MIN_SEGMENTOS = 2   # candidato de um segmento é sorte, não evidência
MIN_PROVAS = 5      # `@Assets` tinha exatamente 5 provas no projeto medido

REEXPORT = re.compile(r"""^\s*export\s[^\n]*\sfrom\s*['"]""")


def indexar(caminhos) -> dict:
    """Todo sufixo de caminho -> os arquivos que terminam nele."""
    por_sufixo = {}
    for caminho in caminhos:
        partes = caminho.split('/')
        for i in range(len(partes)):
            por_sufixo.setdefault('/'.join(partes[i:]), set()).add(caminho)
    return por_sufixo


def _tentativas(alvo: str, extensoes: list, arquivo_de_pasta) -> list:
    """O alvo com cada extensão candidata, e depois como pasta.

    A ordem é a de `EXTENSOES` e é FIXA: com `x.ts` e `x/index.ts` existindo, vence
    o primeiro da lista, que é o que o Node faz. Ordem escrita não é o mesmo que
    'o primeiro candidato ganha' — lá são dois candidatos igualmente plausíveis.

    O nome do arquivo de pasta vem declarado: `index` no JS, `__init__` no Python,
    e `None` no PHP, onde um `use` aponta uma classe e não uma pasta.
    """
    saida = [alvo] + [alvo + e for e in extensoes]
    if arquivo_de_pasta:
        saida += [f'{alvo}/{arquivo_de_pasta}{e}' for e in extensoes]
    return saida


def _normalizar(caminho: str):
    """Resolve `.` e `..` sem tocar o disco. Subiu acima da raiz -> None.

    O `..` sobrando NÃO pode ser engolido em silêncio: `../../x` num arquivo de raiz
    viraria `x` e casaria com um `x.py` qualquer — aresta errada, que é a única
    coisa que este desenho declara pior que aresta faltando. O extrator não pode
    barrar isso sozinho porque não conhece o caminho de origem.
    """
    partes = []
    for parte in caminho.split('/'):
        if parte == '..':
            if not partes:
                return None
            partes.pop()
        elif parte not in ('.', ''):
            partes.append(parte)
    return '/'.join(partes)


def resolver_relativo(origem, alvo, indice, extensoes, arquivo_de_pasta):
    """`./x` e `../x` contra o arquivo de origem. Não existe -> None (pendurado)."""
    pasta = origem.rsplit('/', 1)[0] if '/' in origem else ''
    caminho = _normalizar(f'{pasta}/{alvo}' if pasta else alvo)
    if not caminho:
        return None         # subiu acima da raiz, ou o alvo era só `./`
    for tentativa in _tentativas(caminho, extensoes, arquivo_de_pasta):
        # a tentativa é um caminho a partir da raiz, e todo caminho é sufixo de si
        # mesmo no índice: se ele estiver no próprio conjunto, o arquivo existe
        if tentativa in indice.get(tentativa, ()):
            return tentativa
    return None


def candidatos(alvo: str, indice: dict, extensoes: list, arquivo_de_pasta,
               min_segmentos: int = MIN_SEGMENTOS) -> tuple:
    """Os arquivos cujo caminho termina no alvo, E o sufixo que casou.

    O sufixo volta junto porque quem chama precisa dele para calcular a base
    (destino menos sufixo): com `@Component/Box` casando em `Box.vue`, cortar pelo
    tamanho de `Box` deixaria `.vue` na base e ela nunca bateria com outra.

    Um candidato por si não é aresta: quem decide é quem chama. Devolver a lista
    inteira é o que permite o ambíguo ir para a segunda passada em vez de ser
    resolvido no chute.

    O piso de segmentos existe porque `@/utils` é o RESTO de um apelido, e casar um
    nome solto assim é sorte. Num NOME PURO não há prefixo para tirar — a string é o
    caminho inteiro do módulo —, e aí quem chama baixa o piso para 1: `from pedido
    import X` com `pedido.py` no projeto é aresta de verdade, e é como o resolvedor
    antigo de Python se comportava.
    """
    if alvo.count('/') + 1 < min_segmentos:
        return [], ''
    for tentativa in _tentativas(alvo, extensoes, arquivo_de_pasta):
        achados = indice.get(tentativa)
        if achados:
            return sorted(achados), tentativa
    return [], ''


def eh_externo(alvo, classe, builtins, declarados, raizes,
               nome_puro_pode_ser_interno) -> bool:
    """O import sai do projeto?

    É aqui que a aresta errada nasce quando nasce, então cada condição tem motivo
    medido:

    - **A dependência declarada vence para QUALQUER classe.** `@vue/test-utils` tem
      a forma de um apelido — medido, `@areas` é um apelido minúsculo com 45 imports
      num projeto real, então não dá para separar pela caixa. Sem esta linha o
      pacote escopado cairia no índice e sairia contado como não resolvido.
    - **`nome_puro` é externo nas linguagens que declaram isso.** Medido:
      `import 'server-only'` casaria com `tests/helpers/server-only.ts`, oito vezes.
      Mas em Python `from pedido import X` é módulo local, e aplicar a regra do JS
      lá apagava o grafo inteiro — por isso a linguagem declara.
    - **Builtin é externo sempre**, inclusive na linguagem que permite nome puro
      interno: ele nunca está em `dependencies`, então qualquer exceção escrita como
      "o que não é declarado" o deixaria passar.
    - **A exceção do `baseUrl` é estreita**: não declarado, não builtin, e dois ou
      mais segmentos.
    """
    primeiro = alvo.split('/', 1)[0]
    if alvo in declarados or primeiro in declarados:
        return True
    if classe != 'nome_puro':
        return False
    if alvo in builtins or primeiro in builtins:
        return True
    if nome_puro_pode_ser_interno:
        return False        # quem decide é o índice: o que não é arquivo é externo
    cabe_em_raiz = bool(raizes) and alvo.count('/') + 1 >= MIN_SEGMENTOS
    return not cabe_em_raiz


def _descer(dados, caminho_da_chave: str):
    """`compilerOptions.paths` -> dados['compilerOptions']['paths']."""
    for chave in caminho_da_chave.split('.'):
        if not isinstance(dados, dict) or chave not in dados:
            return None
        dados = dados[chave]
    return dados


def ler_vocabulario(raiz, configs: list) -> dict:
    """O mapeamento declarado pelo projeto, CONFERIDO contra o disco.

    O `configs` vem do módulo da linguagem e diz só ONDE as coisas moram. Sem essa
    indireção o resolvedor precisaria das strings `composer.json`, `tsconfig.json` e
    `psr-4`, e a restrição "nenhum nome de linguagem no resolvedor" cairia.

    Atalho, nunca verdade: o que aponta para pasta inexistente é descartado e o
    import volta a resolver pelos arquivos que existem.
    """
    raiz = Path(raiz)
    prefixos, raizes = [], []
    for config in configs:
        try:
            dados = json.loads((raiz / config['arquivo']).read_text('utf-8', 'replace'))
        except (json.JSONDecodeError, OSError):
            continue
        mapa = _descer(dados, config.get('prefixos', '')) or {}
        if isinstance(mapa, dict):
            for prefixo, destino in mapa.items():
                alvos = destino if isinstance(destino, list) else [destino]
                for alvo in alvos:
                    if not isinstance(alvo, str):
                        continue
                    base = alvo.rstrip('*').rstrip('/').replace('\\', '/')
                    if base and (raiz / base).is_dir():
                        prefixos.append((prefixo.rstrip('\\/*'), base))
        chave_raiz = config.get('raizes')
        base_url = _descer(dados, chave_raiz) if chave_raiz else None
        if isinstance(base_url, str) and (raiz / base_url).is_dir():
            raizes.append(base_url.rstrip('/'))
    return {'prefixos': sorted(set(prefixos)), 'raizes': sorted(set(raizes))}


def base_de(destino: str, sufixo: str) -> str:
    """O destino menos o sufixo que casou: `src/components/Box.vue` - `components/Box.vue`.

    O sufixo, não o alvo do import: a extensão pode ter completado o casamento, e
    cortar pelo tamanho do alvo deixaria `.vue` dentro da base.
    """
    return destino[:len(destino) - len(sufixo)].rstrip('/')


def bases_provadas(resolvidos) -> dict:
    """Por prefixo, as pastas onde ele já foi visto cair pelo menos MIN_PROVAS vezes.

    Isto é a configuração REDESCOBERTA pelos arquivos: num projeto real saiu
    `@ -> src`, `@Component -> src/components`, `@View -> src/views` e
    `@Assets -> src/assets`, que é exatamente o que o `vue.config.js` declara — e o
    arquivo nunca foi aberto.
    """
    contagem = defaultdict(Counter)
    for prefixo, sufixo, destino in resolvidos:
        contagem[prefixo][base_de(destino, sufixo)] += 1
    return {prefixo: {base for base, n in c.items() if n >= MIN_PROVAS}
            for prefixo, c in contagem.items()}


def desempatar(prefixo, resto, candidatos_, sufixo, provadas, indice, extensoes,
               arquivo_de_pasta):
    """A segunda passada, para os dois tipos de pendência que a etapa 3 deixou.

    Roda UMA vez e usa somente evidência da primeira passada: aresta criada aqui não
    realimenta prova, senão haveria iteração, com convergência e determinismo em
    aberto.

    - **ambíguo** (vários candidatos): resolve se EXATAMENTE UM tem a base provada.
      Comparar por base, e não por `startswith`, é o que separa
      `src/constants/index.ts` de `src/assets/js/constants/index.ts` — os dois
      começam com `src/`, e só a base distingue.
    - **fraco** (um segmento, sem candidato): monta `base + resto` e resolve se esse
      arquivo existe e é único.
    """
    bases = provadas.get(prefixo, set())
    if not bases:
        return None
    if candidatos_:
        sob = [c for c in candidatos_ if base_de(c, sufixo) in bases]
        return sob[0] if len(sob) == 1 else None
    achados = set()
    for base in bases:
        for tentativa in _tentativas(f'{base}/{resto}', extensoes, arquivo_de_pasta):
            encontrados = indice.get(tentativa)
            if encontrados:
                achados |= encontrados
                break
    return next(iter(achados)) if len(achados) == 1 else None


def eh_barril(texto: str) -> bool:
    """Arquivo que só re-exporta não é dependência de ninguém — é um corredor.

    Sem isto, o topo do ranking vira o `index.ts`, que é verdadeiro e não ajuda: o
    arquivo que a pessoa precisa abrir está do outro lado do corredor.

    O critério é estreito e escrito, senão dois critérios plausíveis dariam duas
    implementações: é barril o arquivo cujo conteúdo, fora comentário e linha em
    branco, é SÓ `export … from`.
    """
    uteis = [l for l in texto.split('\n')
             if l.strip() and not l.strip().startswith(('//', '/*', '*'))]
    return bool(uteis) and all(REEXPORT.match(l) for l in uteis)
