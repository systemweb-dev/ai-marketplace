"""Detectores textuais de problema em teste. Id estável por regra; nenhum parser de verdade.

O que a regex não consegue decidir com segurança sai como confiança **media** — e confiança média
nunca entra em lote de correção automática. Comentário e literal de texto são **mascarados** antes
da busca: `sleep(` citado num comentário não é espera fixa.
"""
import re

# id -> (descrição, dimensão, confiança)
REGRAS = {
    "sem_assercao_aparente": ("teste sem asserção aparente", "confiabilidade", "media"),
    "marcado_para_pular": ("teste desligado (skip/xfail/only)", "confiabilidade", "alta"),
    "espera_fixa": ("espera fixa dentro do teste", "isolamento", "alta"),
    "relogio_real": ("relógio real sem congelar", "isolamento", "media"),
    "aleatorio_sem_semente": ("aleatório sem semente", "isolamento", "media"),
    "rede_em_unit": ("chamada de rede em teste unitário", "isolamento", "alta"),
    "nome_duplicado": ("nome de teste repetido no arquivo", "legibilidade", "alta"),
}

_DECLARACAO = re.compile(
    r"^[ \t]*(?:async[ \t]+)?def[ \t]+(?P<py>test_\w+)"
    r"|^[ \t]*(?:it|test)(?:\.\w+)?[ \t]*\([ \t]*['\"`](?P<js>[^'\"`]+)"
    r"|^[ \t]*(?:public[ \t]+)?function[ \t]+(?P<php>test\w+)"
    r"|^[ \t]*func[ \t]+(?P<go>Test\w+)[ \t]*\("
    r"|^[ \t]*it[ \t]+['\"](?P<rb>[^'\"]+)['\"][ \t]*do",
    re.M)
# Java, C# e Rust marcam o teste por anotação; é o suficiente para CONTAR sem virar parser.
_ANOTACAO = re.compile(r"^[ \t]*(?:@Test\b|\[Fact\]|\[Test\]|#\[test\])", re.M)
_DECORADOR = re.compile(r"^[ \t]*(?:@|#\[)")

_ASSERCAO = re.compile(r"\bassert\w*\s*[\(\s]|\bexpect\s*\(|->assert|\$this->assert|\.should\b|t\.Error")
_PULAR = re.compile(r"@pytest\.mark\.(skip|xfail)|pytest\.skip\(|@unittest\.skip|"
                    r"\b(?:it|test|describe)\.(?:skip|only)\(|@Ignore\b|"
                    r"markTestSkipped|markTestIncomplete|t\.Skip\(")
_ESPERA = re.compile(r"time\.sleep\(|(?<![\w.])sleep\(|Thread\.sleep\(|usleep\(|"
                     r"setTimeout\(|waitForTimeout\(")
# `setTimeout(r, 0)` drena promessas pendentes; é idioma, não espera — validado em projeto real
_ATRASO_ZERO = re.compile(r"(setTimeout|waitForTimeout)\([^;\n]*?,\s*0\s*\)")
_RELOGIO = re.compile(r"datetime\.now\(|date\.today\(|time\.time\(|new Date\(\)|Date\.now\(\)|"
                      r"new DateTime\(|Carbon::now\(")
_CONGELA = re.compile(r"freezegun|freeze_time|time_machine|setSystemTime|Carbon::setTestNow|"
                      r"useFakeTimers")
_ALEATORIO = re.compile(r"\brandom\.\w|Math\.random\(|mt_rand\(|(?<![\w.])rand\(|\bfaker\b|\bFaker\b")
_SEMENTE = re.compile(r"\.seed\(|seed\s*=|Faker::seed|faker\.seed")
_REDE = re.compile(r"requests\.(get|post|put|delete)\(|httpx\.|urlopen\(|(?<![\w.])fetch\(|"
                   r"axios\.\w+\(|curl_exec\(|file_get_contents\(\s*['\"]http")
# rede mockada no arquivo não é rede de verdade — o falso positivo aqui custaria caro
_MOCK = re.compile(r"vi\.mock\(|jest\.mock\(|jest\.spyOn\(|nock\(|\bmsw\b|requests_mock|"
                   r"responses\.|Http::fake\(|mock_open\(|monkeypatch\.setattr\(|patch\(")


def _mascarar(texto: str, literais: bool = True) -> str:
    """Troca comentário (e, se `literais`, texto entre aspas) por espaço, mantendo as posições.

    A busca por rede precisa das aspas preservadas — a URL mora dentro delas.
    """
    saida = list(texto)
    tamanho = len(texto)
    posicao = 0
    while posicao < tamanho:
        letra = texto[posicao]
        if literais and letra in "'\"`":
            fim = posicao + 1
            while fim < tamanho and texto[fim] != letra:
                fim += 2 if texto[fim] == "\\" else 1
            for indice in range(posicao, min(fim + 1, tamanho)):
                if saida[indice] != "\n":
                    saida[indice] = " "
            posicao = fim + 1
            continue
        if letra == "#" or texto.startswith("//", posicao):
            fim = texto.find("\n", posicao)
            fim = tamanho if fim == -1 else fim
            for indice in range(posicao, fim):
                saida[indice] = " "
            posicao = fim
            continue
        if texto.startswith("/*", posicao):
            fim = texto.find("*/", posicao)
            fim = tamanho if fim == -1 else fim + 2
            for indice in range(posicao, fim):
                if saida[indice] != "\n":
                    saida[indice] = " "
            posicao = fim
            continue
        posicao += 1
    return "".join(saida)


def blocos(texto: str):
    """Fatia em (nome, linha da declaração, linha inicial do bloco, trecho até o próximo teste).

    O trecho começa nos decoradores/atributos imediatamente acima da declaração — é onde vivem
    `@pytest.mark.skip` e `#[Test]`. Sem declaração reconhecida, cai nas anotações (Java, C#, Rust).
    """
    linhas = texto.splitlines()
    marcas = []
    for achado in _DECLARACAO.finditer(texto):
        nome = next(valor for valor in achado.groupdict().values() if valor)
        linha = texto.count("\n", 0, achado.start()) + 1
        inicio = linha
        while inicio > 1 and _DECORADOR.match(linhas[inicio - 2]):
            inicio -= 1
        marcas.append((nome, linha, inicio))
    if not marcas:
        for posicao, achado in enumerate(_ANOTACAO.finditer(texto), start=1):
            linha = texto.count("\n", 0, achado.start()) + 1
            marcas.append((f"teste {posicao}", linha, linha))
    saida = []
    for posicao, (nome, linha, inicio) in enumerate(marcas):
        fim = marcas[posicao + 1][2] - 1 if posicao + 1 < len(marcas) else len(linhas)
        saida.append((nome, linha, inicio, "\n".join(linhas[inicio - 1:fim])))
    return saida


def _sinal(regra, caminho, linha, evidencia, teste):
    return {"regra": regra, "caminho": str(caminho), "linha": linha,
            "evidencia": evidencia.strip()[:120], "teste": teste}


def _linha_de(trecho_inicio, trecho, achado) -> int:
    return trecho_inicio + trecho.count("\n", 0, achado.start())


def varrer(caminho, texto: str, suite: str) -> list:
    """Devolve os sinais encontrados no arquivo, em ordem de linha."""
    achados = []
    mascarado = _mascarar(texto)
    linhas_mascaradas = mascarado.splitlines()
    linhas_com_texto = _mascarar(texto, literais=False).splitlines()
    congela_no_arquivo = bool(_CONGELA.search(mascarado))
    mock_no_arquivo = bool(_MOCK.search(mascarado))
    vistos = {}
    for nome, linha, inicio, trecho in blocos(texto):
        fatia = slice(inicio - 1, inicio - 1 + trecho.count("\n") + 1)
        limpo = "\n".join(linhas_mascaradas[fatia])
        com_texto = "\n".join(linhas_com_texto[fatia])
        if nome in vistos:
            achados.append(_sinal("nome_duplicado", caminho, linha,
                                  f"também na linha {vistos[nome]}", nome))
        else:
            vistos[nome] = linha
        pular = _PULAR.search(limpo)
        if pular:
            achados.append(_sinal("marcado_para_pular", caminho, _linha_de(inicio, limpo, pular),
                                  pular.group(0), nome))
            continue                      # teste desligado: os outros sinais não importam
        if not _ASSERCAO.search(limpo):
            achados.append(_sinal("sem_assercao_aparente", caminho, linha, trecho.splitlines()[0], nome))
        espera = _ESPERA.search(limpo)
        if espera and _ATRASO_ZERO.search(limpo[espera.start():]):
            espera = None
        if espera:
            achados.append(_sinal("espera_fixa", caminho, _linha_de(inicio, limpo, espera),
                                  espera.group(0), nome))
        relogio = _RELOGIO.search(limpo)
        if relogio and not congela_no_arquivo:
            achados.append(_sinal("relogio_real", caminho, _linha_de(inicio, limpo, relogio),
                                  relogio.group(0), nome))
        aleatorio = _ALEATORIO.search(limpo)
        if aleatorio and not _SEMENTE.search(mascarado):
            achados.append(_sinal("aleatorio_sem_semente", caminho,
                                  _linha_de(inicio, limpo, aleatorio), aleatorio.group(0), nome))
        rede = _REDE.search(com_texto)
        if rede and suite == "unit" and not mock_no_arquivo:
            achados.append(_sinal("rede_em_unit", caminho, _linha_de(inicio, com_texto, rede),
                                  rede.group(0), nome))
    return sorted(achados, key=lambda a: (a["linha"], a["regra"]))
