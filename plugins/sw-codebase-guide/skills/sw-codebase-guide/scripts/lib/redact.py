"""Impede que segredo e credencial saiam no documento ou no inventário.

Tudo que a varredura emite passa por aqui. A regra é: a CHAVE pode aparecer
(saber que existe `DB_PASSWORD` é informação útil); o VALOR nunca.

Duas decisões que o primeiro desenho errou, e por isso estão escritas:

1. **Não há âncora de início de linha.** A versão anterior usava `^`, e com isso
   `      - DB_PASSWORD=senha` (item de lista YAML) passava inteiro — justamente o
   formato de docker-compose e manifesto k8s, que são os arquivos mais densos em
   segredo de um projeto. Pelo mesmo motivo a varredura é por OCORRÊNCIA, não por
   linha: `{"api_key": "abc"}` tem o par no meio da linha, e testar só o primeiro
   par deixava passar tudo que é compacto.

2. **O nome da chave não é o único gatilho.** `X_SIGNATURE=9f8a...` e
   `GH_PAT=ghp_16C7...` não casam com nenhum nome conhecido. Por isso existe
   `FORMAS`: a forma do valor denuncia sozinha.

E o contrário também importa: mascarar `auth: true` ou `"author": "Jane"` não
protege nada e destrói informação legítima do manifesto. Daí `INOCENTE`.

**Limites conhecidos:** não cobre segredo construído em tempo de execução
(`'x' + 'y'`), nem valor dentro de chamada (`os.environ['K'] = f(...)`), nem
formato binário. É uma guarda de superfície, não um analisador.
"""
import re

MASCARA = '***'

# Nome de chave que denuncia segredo. Casado como SUBSTRING, porque o nome real
# varia muito: `STRIPE_SECRET_KEY`, `senha_banco`, `apiKey`.
# `auth(?!ors?\b)` exclui `author`/`authors` (campo de manifesto) mas MANTÉM
# `Authorization` — a primeira tentativa, `auth(?!or)`, matava os dois.
NOMES = re.compile(
    r'(?i)(senha|password|passwd|secret|token|api[_-]?key|apikey|private[_-]?key'
    r'|credential|auth(?!ors?\b)|access[_-]?key|client[_-]?secret|signature|bearer)'
)

# Forma que denuncia segredo pelo VALOR, mesmo com nome de chave inocente.
FORMAS = re.compile(
    r'(?:ghp_|gho_|ghs_|ghu_|github_pat_|sk-|rk_live|pk_live|xox[baprs]-|AKIA|ASIA)'
    r'[A-Za-z0-9_\-]{8,}'
    r'|eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.'          # JWT
)

# Valor que NUNCA é segredo: mascarar aqui só perde informação.
INOCENTE = re.compile(
    r'(?i)^(?:true|false|null|none|nil|undefined|-?\d+(?:\.\d+)?'
    r'|str|int|bool|float|string|number|boolean|any|object)$'
    r'|^(?:os\.environ|process\.env|getenv|env|config|Field|useMemo|useState)$'
    r'|^\$\{|^<%'
)

# Prefixo de declaração que fica ENTRE o começo e a chave.
# `export`, `ENV` e `ARG` entraram porque `.env`, `*.sh` e Dockerfile são input
# direto desta skill e passavam inteiros.
DECLARACAO = (r'(?:export|ENV|ARG|const|let|var|public|private|protected|static'
              r'|define\(|final|readonly)\s+')

# Um par `chave <sep> valor` em qualquer lugar do texto. O valor entre aspas pode
# atravessar linha — é o que faz valor multilinha ser mascarado inteiro.
PAR = re.compile(
    r'[\'"]?(?P<chave>[A-Za-z_][\w.\-]*)[\'"]?'
    r'(?P<sep>\s*(?:=>|:|=)\s*)'
    r'(?P<valor>"[^"]*"|\'[^\']*\'|[A-Za-z0-9_\-./+=:@~!$%^&*]+)'
)

# Valor que some inteiro, não importa a chave.
BLOCOS = [
    # Chave privada: até o END quando ele existe; senão, até a linha em branco ou o
    # fim do texto. Exigir o END deixava passar a chave TRUNCADA — e truncar arquivo
    # é exatamente o que uma skill de documentação faz.
    (re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----'
                r'(?:.*?-----END [A-Z ]*PRIVATE KEY-----|.*?(?=\n\s*\n)|.*)', re.S), MASCARA),
    # Credencial em URL de conexão. O usuário é OPCIONAL (`*`, não `+`):
    # `redis://:senha@host` não tem usuário e vazava.
    (re.compile(r'(?i)\b([a-z][a-z0-9+.-]*://)([^:/\s"\']*):([^@\s"\']+)@'),
     r'\1\2:' + MASCARA + '@'),
    # Esquema de autenticação: o valor tem ESPAÇO no meio (`Bearer ghp_...`), e o
    # padrão de par para no espaço — mascarava `Bearer` e deixava o token solto.
    (re.compile(r'(?i)\b(bearer|basic|token)\s+([A-Za-z0-9_\-./+=]{8,})'),
     r'\1 ' + MASCARA),
    # XML/HTML: <password>valor</password>
    (re.compile(r'(?i)<(\w*(?:senha|password|secret|token|key)\w*)>([^<]+)</\1>'),
     r'<\1>' + MASCARA + r'</\1>'),
]


def eh_chave_de_segredo(chave: str) -> bool:
    """O nome da chave denuncia que o valor é segredo?"""
    return bool(NOMES.search(chave))


def _mascarar_par(m, texto: str) -> str:
    chave, sep, valor = m.group('chave'), m.group('sep'), m.group('valor')
    nu = valor.strip('"\'')

    # chamada de função, não valor: `const secret = useMemo(() => ...)`
    if m.end() < len(texto) and texto[m.end()] == '(':
        return m.group(0)
    if INOCENTE.search(nu) or not nu:
        return m.group(0)
    if eh_chave_de_segredo(chave) or FORMAS.search(nu):
        return f'{chave}{sep}{MASCARA}'
    return m.group(0)


def redigir(texto: str) -> str:
    """Devolve o texto sem valor de segredo. A chave permanece; o valor vira ***."""
    for padrao, troca in BLOCOS:
        texto = padrao.sub(troca, texto)
    return PAR.sub(lambda m: _mascarar_par(m, texto), texto)


def linha_tem_segredo(linha: str) -> bool:
    """Esta linha não pode ser impressa como está?"""
    return linha != redigir(linha)


def chaves_de_env(texto: str) -> list:
    """Só os NOMES das variáveis de um arquivo de ambiente. Nunca os valores.

    Saber que o projeto usa `STRIPE_SECRET` é informação útil para quem chega; o
    valor nunca pode sair. Extrair a chave aqui, em vez de redigir o valor depois,
    é o que garante que não há caminho pelo qual o valor chegue ao inventário.
    """
    chaves = []
    for linha in texto.split('\n'):
        linha = linha.strip()
        if not linha or linha.startswith('#') or '=' not in linha:
            continue
        # `re.sub` de PREFIXO, não `lstrip`: `lstrip('export')` é strip de conjunto
        # de caracteres e devolvia `['ken']` para `token=abc` e `[]` para `port=5432`.
        chave = re.sub(r'^export\s+', '', linha).split('=', 1)[0].strip().strip('"\'')
        if re.fullmatch(r'[A-Za-z_][\w.]*', chave):
            chaves.append(chave)
    return sorted(set(chaves))
