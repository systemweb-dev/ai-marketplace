#!/usr/bin/env python3
"""Detector anti-slop: varre o HTML de um mockup atrás dos "tells" de IA.

Determinístico: sem LLM, sem rede, só a biblioteca padrão. Lê um arquivo local e diz, com
linha, trecho e dica, onde o mockup caiu num padrão de categoria — texto em gradiente, preto
puro, borda colorida lateral, emoji no lugar de ícone, dados "Jane Doe", travessão na
interface, rótulo numerado de seção, knob que não faz nada...

Uso:
    python3 detectar.py <index.html> [--json]

Saída: 0 = sem falha (avisos, se houver, aparecem); 2 = pelo menos uma falha; 1 = erro
(arquivo ilegível, ou `detector: ignorar` citando regra que não existe).

O que é analisado — o DESIGN, nunca a casca do harness:
- a marcação dentro de qualquer elemento com a classe `variation`;
- o CSS de todos os `<style>`, menos a região `harness:inicio` … `harness:fim`;
- os `style=""` e as classes utilitárias (Tailwind) dentro das variações;
- os atributos de texto de interface: `placeholder`, `aria-label`, `title`, `alt` e o `value`
  de botão.

Exceção que o pedido justifica é declarada no próprio HTML e vale para o arquivo inteiro:
    <!-- detector: ignorar sombra-dura, tres-colunas-iguais (mundo neobrutalista) -->
A justificativa vai depois da lista, entre parênteses ou após um travessão. O que foi
suprimido continua aparecendo, com linha, sob IGNORADAS — nunca some.

O catálogo e o porquê de cada regra estão em `references/piso-e-recusas.md`.
"""
import json
import re
import sys
from html.parser import HTMLParser

REGRAS = {
    "nenhuma-variacao": {
        "severidade": "falha",
        "dica": "nenhum elemento com a classe `variation` — nada de design foi analisado"},
    "texto-em-gradiente": {
        "severidade": "falha",
        "dica": "ênfase vem de peso ou tamanho; tire o background-clip: text"},
    "preto-puro": {
        "severidade": "falha",
        "dica": "use um quase-preto tingido (ex.: #16181d) — preto puro achata a profundidade"},
    "borda-lateral-colorida": {
        "severidade": "falha",
        "dica": "borda lateral acima de 1px é o enfeite padrão de card e aviso; "
                "use fundo tingido, ícone ou peso"},
    "sombra-dura": {
        "severidade": "aviso",
        "dica": "sombra sem desfoque é fantasia neobrutalista; dê desfoque, ou declare a exceção "
                "se o mundo escolhido é esse"},
    "halo-decorativo": {
        "severidade": "aviso",
        "dica": "brilho colorido sem deslocamento é enfeite; sombra de verdade tem deslocamento"},
    "easing-elastico": {
        "severidade": "falha",
        "dica": "quique soa datado; use saída exponencial, ex.: cubic-bezier(0.16, 1, 0.3, 1)"},
    "cursor-personalizado": {
        "severidade": "falha",
        "dica": "cursor em imagem é hostil à acessibilidade e ao desempenho"},
    "tres-colunas-iguais": {
        "severidade": "aviso",
        "dica": "três colunas iguais é a linha de recursos padrão; tente zigue-zague ou grade "
                "assimétrica — se é dado tabular, declare a exceção"},
    "sem-reducao-de-movimento": {
        "severidade": "falha",
        "dica": "há animação e nenhum @media (prefers-reduced-motion) no CSS — o harness traz "
                "uma guarda global; não a apague"},
    "travessao-na-interface": {
        "severidade": "falha",
        "dica": "no texto de interface, troque o travessão por ponto, vírgula, dois-pontos ou "
                "quebra de linha (meia-risca de intervalo, como 08h–18h, está certa)"},
    "rotulo-numerado": {
        "severidade": "falha",
        "dica": "numeração de seção só enfeita; deixe o título falar sozinho"},
    "emoji-como-icone": {
        "severidade": "falha",
        "dica": "ícone vem de biblioteca real ou SVG autoral, com traço consistente"},
    "dados-genericos": {
        "severidade": "falha",
        "dica": "invente nomes, empresas, e-mails e telefones críveis, do lugar e do setor"},
    "numero-perfeito-demais": {
        "severidade": "aviso",
        "dica": "dado real é bagunçado: 47,2%, R$ 1.847,30"},
    "verbo-de-enchimento": {
        "severidade": "aviso",
        "dica": "troque por um verbo concreto: o que a pessoa faz"},
    "knob-sem-efeito": {
        "severidade": "aviso",
        "dica": "o knob foi declarado mas nenhum CSS usa --k-<id> nem data-k-<id>: o controle "
                "aparece e não faz nada"},
}

# --- fronteiras e limpeza ---------------------------------------------------------------------

_CASCA = [
    # a forma atual do harness
    re.compile(r"/\*\s*harness:inicio.*?harness:fim\s*\*/", re.S),
    # mockups gerados antes dos marcadores
    re.compile(r"/\*\s*-+\s*harness chrome.*?(?=/\*\s*=+\s*\n\s*Component styles go here)", re.S),
]
_IGNORAR = re.compile(r"<!--\s*detector:\s*ignorar\s+(.*?)-->", re.I | re.S)
_ESTILO = re.compile(r"(<style\b[^>]*>)(.*?)</style>", re.S | re.I)
_COMENTARIO_CSS = re.compile(r"/\*.*?\*/", re.S)
_STRING_CSS = re.compile(r"'[^'\n]*'|\"[^\"\n]*\"")
_ID_DE_REGRA = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)+$")


def _em_branco(trecho):
    """Apaga o conteúdo preservando as quebras de linha — as linhas do resto não se mexem."""
    return re.sub(r"[^\n]", " ", trecho)


def _limpar_css(css):
    """Comentário e string saem antes da análise: `/* color: #000 */` não é CSS, e
    `content: 'color: #000'` é texto."""
    css = _COMENTARIO_CSS.sub(lambda m: _em_branco(m.group(0)), css)
    return _STRING_CSS.sub(lambda m: _em_branco(m.group(0)), css)


def _blocos_de_estilo(html, sem_casca=True):
    """[(linha_inicial, css)] dos `<style>`, limpos e, por padrão, sem a casca do harness."""
    blocos = []
    for casado in _ESTILO.finditer(html):
        css = casado.group(2)
        # A casca sai ANTES dos comentários: os marcadores harness:inicio/fim SÃO comentários,
        # e limpá-los primeiro apagaria a própria fronteira.
        if sem_casca:
            for casca in _CASCA:
                css = casca.sub(lambda m: _em_branco(m.group(0)), css)
        css = _limpar_css(css)
        blocos.append((html.count("\n", 0, casado.start(2)) + 1, css))
    return blocos


# --- cores e medidas --------------------------------------------------------------------------

_NUMERO = r"-?\d*\.?\d+"
_FUNCAO_DE_COR = re.compile(r"\b(rgba?|hsla?|oklch|oklab|lch|lab|color)\(([^()]*)\)", re.I)
_HEX = re.compile(r"#([0-9a-fA-F]{3,8})\b")
_COR_NOMEADA = re.compile(r"\b(black|white|gray|grey|silver|red|purple|violet|blue|green|lime|"
                          r"orange|yellow|pink|magenta|fuchsia|cyan|aqua|teal|indigo|gold|"
                          r"transparent|currentcolor)\b", re.I)
_NEUTRAS = {"black", "white", "gray", "grey", "silver", "transparent", "currentcolor"}


def _alfa(texto):
    """O alfa de uma cor funcional: `rgb(0 0 0 / .4)` ou `rgba(0,0,0,.4)`; 1 quando ausente."""
    if "/" in texto:
        bruto = texto.split("/")[-1].strip()
    elif len([p for p in texto.split(",") if p.strip()]) == 4:
        bruto = texto.split(",")[-1].strip()
    else:
        return 1.0
    try:
        return float(bruto[:-1]) / 100 if bruto.endswith("%") else float(bruto)
    except ValueError:
        return 1.0


def _cores(valor):
    """[(tipo, canais_rgb_ou_None, alfa, texto)] de cada cor dentro de um valor de CSS."""
    achadas = []
    for m in _FUNCAO_DE_COR.finditer(valor):
        funcao, dentro = m.group(1).lower(), m.group(2)
        numeros = [float(n) for n in re.findall(_NUMERO, dentro)]
        canais = None
        if funcao.startswith("rgb") and len(numeros) >= 3:
            canais = tuple(numeros[:3])
        elif funcao.startswith("hsl") and len(numeros) >= 3:
            canais = ("hsl", numeros[2])                   # luminosidade basta para "preto"
        elif funcao in ("oklch", "oklab", "lch", "lab") and numeros:
            canais = ("lum", numeros[0])
        achadas.append(("funcao", canais, _alfa(dentro), m.group(0)))
    sem_funcoes = _FUNCAO_DE_COR.sub(" ", valor)
    for m in _HEX.finditer(sem_funcoes):
        h = m.group(1)
        if len(h) in (3, 4):
            rgb, a = tuple(int(c * 2, 16) for c in h[:3]), (int(h[3] * 2, 16) / 255 if len(h) == 4 else 1)
        elif len(h) in (6, 8):
            rgb = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
            a = int(h[6:8], 16) / 255 if len(h) == 8 else 1
        else:
            continue
        achadas.append(("hex", rgb, a, m.group(0)))
    for m in _COR_NOMEADA.finditer(sem_funcoes):
        nome = m.group(1).lower()
        rgb = (0, 0, 0) if nome == "black" else None
        achadas.append(("nome", rgb, 0 if nome == "transparent" else 1, nome))
    return achadas


def _e_preto_opaco(cor):
    tipo, canais, alfa, _ = cor
    if alfa < 1 or canais is None:
        return False
    if canais[0] == "hsl":
        return canais[1] == 0
    if canais[0] == "lum":
        return canais[1] == 0
    return all(c == 0 for c in canais)


def _e_colorida(cor):
    """Tem matiz de verdade? Cinza, preto, branco e translúcido quase invisível não têm."""
    tipo, canais, alfa, texto = cor
    if tipo == "nome":
        return texto not in _NEUTRAS
    if alfa < 0.25 or canais is None or canais[0] in ("hsl", "lum"):
        return False
    return max(canais) - min(canais) >= 40


def _px(medida):
    """`1.5rem` → 24.0; `4px` → 4.0; `0` → 0.0; outra unidade → None."""
    m = re.fullmatch(r"(-?\d*\.?\d+)(px|rem|em)?", medida.strip(), re.I)
    if not m:
        return None
    valor = float(m.group(1))
    return valor * 16 if (m.group(2) or "").lower() in ("rem", "em") else valor


def _medidas(valor):
    """As medidas de comprimento de um valor, com as cores tiradas antes (senão os números de
    dentro de `rgb(124 58 237)` virariam deslocamento)."""
    limpo = _HEX.sub(" ", _FUNCAO_DE_COR.sub(" ", valor))
    return [x for x in (_px(t) for t in re.findall(r"-?\d*\.?\d+(?:px|rem|em)?(?![\w%(])", limpo))
            if x is not None]


def _camadas(valor):
    return [c for c in re.split(r",(?![^(]*\))", valor) if c.strip()]


# --- regras de CSS ----------------------------------------------------------------------------

_DECLARACAO = re.compile(r"(?<![\w-])(--[\w-]+|[a-zA-Z-]+)\s*:\s*([^;{}]+)")
_PROPRIEDADES_DE_COR = {"color", "background", "background-color", "border", "border-color",
                        "border-top", "border-bottom", "border-left", "border-right", "outline",
                        "outline-color", "fill", "stroke", "caret-color", "text-decoration-color",
                        "column-rule", "column-rule-color"}
_LATERAIS = {"border-left", "border-right", "border-inline-start", "border-inline-end"}


def _regras_de_css(css, linha_base, achar):
    def linha_de(posicao):
        return linha_base + css.count("\n", 0, posicao)

    def trecho(posicao):
        inicio = css.rfind("\n", 0, posicao) + 1
        fim = css.find("\n", posicao)
        return css[inicio:fim if fim != -1 else None].strip()

    for m in re.finditer(r"(?:-webkit-)?background-clip\s*:\s*text", css, re.I):
        achar("texto-em-gradiente", linha_de(m.start()), trecho(m.start()))

    for m in _DECLARACAO.finditer(css):
        propriedade, valor = m.group(1).lower(), m.group(2)
        onde = linha_de(m.start()), trecho(m.start())

        if (propriedade in _PROPRIEDADES_DE_COR or propriedade.startswith("--")) \
                and any(_e_preto_opaco(c) for c in _cores(valor)):
            achar("preto-puro", *onde)

        if propriedade in _LATERAIS or propriedade in {p + "-width" for p in _LATERAIS}:
            larguras = _medidas(valor)
            if larguras and max(larguras) > 1 and "transparent" not in valor.lower():
                achar("borda-lateral-colorida", *onde)
        elif propriedade == "border-width":
            larguras = _medidas(valor)
            if len(larguras) == 4 and larguras[0] == 0 and larguras[2] == 0 \
                    and max(larguras[1], larguras[3]) > 1:
                achar("borda-lateral-colorida", *onde)

        if propriedade == "box-shadow":
            for camada in _camadas(valor):
                if re.search(r"\binset\b", camada, re.I):
                    continue
                medidas = _medidas(camada)
                if len(medidas) < 3:
                    continue
                x, y, desfoque = medidas[:3]
                if desfoque == 0 and abs(x) + abs(y) >= 2:
                    achar("sombra-dura", *onde)
                elif x == 0 and y == 0 and desfoque >= 8 \
                        and any(_e_colorida(c) for c in _cores(camada)):
                    achar("halo-decorativo", *onde)

        if propriedade == "cursor" and re.search(r"url\(", valor, re.I):
            achar("cursor-personalizado", *onde)

        if propriedade == "grid-template-columns" and re.fullmatch(
                r"\s*(?:repeat\(\s*3\s*,\s*(?:1fr|minmax\(\s*0(?:px)?\s*,\s*1fr\s*\))\s*\)"
                r"|1fr\s+1fr\s+1fr)\s*(?:!important)?\s*", valor, re.I):
            achar("tres-colunas-iguais", *onde)

    for m in re.finditer(r"cubic-bezier\(\s*([^)]*)\)", css, re.I):
        valores = [v.strip() for v in m.group(1).split(",")]
        try:
            y1, y2 = float(valores[1]), float(valores[3])
        except (IndexError, ValueError):
            continue
        if not (0 <= y1 <= 1 and 0 <= y2 <= 1):
            achar("easing-elastico", linha_de(m.start()), trecho(m.start()))


# Classes utilitárias (Tailwind e afins) que carregam o mesmo clichê que a regra de CSS
_UTILITARIAS = [
    (re.compile(r"(?:^|:)grid-cols-3$"), "tres-colunas-iguais"),
    (re.compile(r"(?:^|:)(?:bg|text|border|fill|stroke)-black$"), "preto-puro"),
    (re.compile(r"(?:^|:)bg-clip-text$"), "texto-em-gradiente"),
    (re.compile(r"(?:^|:)border-[lrse]-(?:[2-9]|\d{2,}|\[.+\])$"), "borda-lateral-colorida"),
]

# --- regras de texto --------------------------------------------------------------------------

# Controle: o texto dentro dele é SEMPRE interface, mesmo embrulhado num <p> ou <span>.
_CONTROLES = {"button", "a", "label", "summary", "option", "select", "legend"}
_PAPEIS_DE_CONTROLE = {"button", "tab", "menuitem", "link", "option", "switch"}
# Interface por natureza, decidida pelo ancestral mais próximo.
_INTERFACE = {"h1", "h2", "h3", "h4", "h5", "h6", "th", "figcaption", "caption", "dt", "title"}
_CLASSE_DE_INTERFACE = re.compile(r"(?:^|[\s_-])(badge|pill|tag|chip|eyebrow|label|kicker|btn|"
                                  r"button|tab|menu|icone?|icon|title|titulo|heading|"
                                  r"cabecalho)(?:$|[\s_-])", re.I)
_NAVEGACAO = {"nav", "menu"}
_PAPEIS_DE_NAVEGACAO = {"navigation", "menubar", "menu", "tablist"}
_CONTEUDO = {"p", "blockquote", "td", "li", "dd"}
_VAZIOS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
           "source", "track", "wbr"}
_ATRIBUTOS_DE_TEXTO = ("placeholder", "aria-label", "title", "alt")

# Número de seção: sozinho ("03") ou seguido de separador e PALAVRA ("01 / Recursos"). Sem
# separador é contagem ("02 animais"); separador seguido de dígito é hora ou data ("09:30").
_ROTULO = re.compile(r"^\s*(?:0\d{1,2}|№\s*\d+)\s*(?:$|[/·.|:—–-]\s*[A-Za-zÀ-ÿ])")
_EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF]")
_GENERICOS = re.compile(
    r"\b(john doe|jane doe|fulano(?: de tal)?|beltrano|sicrano|lorem ipsum)\b"
    r"|@ex[ae]mpl[oe]\.(?:com|org)(?:\.br)?\b"
    r"|\(\d{2}\)\s*9?9{4}-?9{4}"
    r"|\b000\.000\.000-00\b|\b123\.456\.789-\d{2}\b", re.I)
_ACME = re.compile(r"\bacme\b", re.I)
_LOGRADOURO = re.compile(r"(rua|avenida|av\.|travessa|alameda|praça|estrada)\s+$", re.I)
_PERFEITOS = re.compile(r"\b99[.,]99\s*%|\b1234567\b|\b123[.,]?456\b")
_ENCHIMENTO = re.compile(r"\b(revolucion\w*|seamless\w*|unleash\w*|next-gen|supercharg\w*|"
                         r"sem esforço|próxima geração|eleve (?:o|a|os|as|seu|sua|seus|suas)|"
                         r"elevate your|potencialize)\b", re.I)


def _travessao_proibido(texto):
    """Travessão sempre; meia-risca só quando NÃO está num intervalo (08h–18h, R$ 50–80)."""
    for m in re.finditer(r"[—–]", texto):
        if m.group(0) == "—":
            return True
        antes = texto[:m.start()].rstrip()[-1:]
        depois = texto[m.end():].lstrip()[:1]
        if not (antes and depois and (antes.isdigit() or antes == "h") and depois.isdigit()):
            return True
    return False


def _genericos(texto):
    if _GENERICOS.search(texto):
        return True
    return any(not _LOGRADOURO.search(texto[:m.start()]) for m in _ACME.finditer(texto))


class _Marcacao(HTMLParser):
    def __init__(self, achar, analisar_css):
        super().__init__(convert_charrefs=True)
        self.achar = achar
        self.analisar_css = analisar_css
        self.pilha = []          # [(tag, attrs, e_variacao)]
        self.variacoes = 0       # profundidade dentro de .variation
        self.total_de_variacoes = 0
        self.knobs = []          # [(linha, lista_de_knobs)]

    # --- contexto ---
    def _controle_acima(self):
        return any(tag in _CONTROLES or attrs.get("role") in _PAPEIS_DE_CONTROLE
                   for tag, attrs, _ in self.pilha)

    def _em_navegacao(self):
        return any(tag in _NAVEGACAO or attrs.get("role") in _PAPEIS_DE_NAVEGACAO
                   for tag, attrs, _ in self.pilha)

    def _de_interface(self):
        """O texto atual é de interface (e não de conteúdo)?

        Dentro de um controle (botão, link, rótulo), é sempre interface, mesmo embrulhado num
        `<p>`. Fora dele, decide o ancestral MAIS PRÓXIMO: `<h2>` é interface, `<p>` é conteúdo
        — e `<li>` dentro de `<nav>` é item de navegação, portanto interface.
        """
        if self._controle_acima():
            return True
        for tag, attrs, _ in reversed(self.pilha):
            if tag == "li" and self._em_navegacao():
                return True
            if tag in _CONTEUDO:
                return False
            if tag in _INTERFACE or tag in _NAVEGACAO \
                    or _CLASSE_DE_INTERFACE.search(attrs.get("class") or ""):
                return True
        return False

    def _em_conteudo(self):
        return any(tag in _CONTEUDO or tag == "time" for tag, _, _ in self.pilha)

    # --- árvore ---
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = (attrs.get("class") or "").split()
        e_variacao = "variation" in classes
        if e_variacao:
            self.total_de_variacoes += 1
            if attrs.get("data-knobs"):
                try:
                    lista = json.loads(attrs["data-knobs"])
                except ValueError:
                    lista = []
                self.knobs.append((self.getpos()[0], lista if isinstance(lista, list) else []))
        if self.variacoes or e_variacao:
            linha = self.getpos()[0]
            if attrs.get("style"):
                self.analisar_css(_limpar_css(attrs["style"]), linha)
            for classe in classes:
                for padrao, regra in _UTILITARIAS:
                    if padrao.search(classe):
                        self.achar(regra, linha, f'class="{attrs.get("class")}"')
            self._atributos(tag, attrs, linha)
        if tag in _VAZIOS:
            return
        self.pilha.append((tag, attrs, e_variacao))
        if e_variacao:
            self.variacoes += 1

    def _atributos(self, tag, attrs, linha):
        """Placeholder, rótulo acessível, título e o value de botão também são texto que a
        pessoa lê — e é justamente num formulário que "Jane Doe" mais aparece."""
        textos = [attrs.get(nome) for nome in _ATRIBUTOS_DE_TEXTO]
        botao = tag == "input" and (attrs.get("type") or "").lower() in ("submit", "button", "reset")
        if botao:
            textos.append(attrs.get("value"))
        for texto in filter(None, textos):
            if _travessao_proibido(texto):
                self.achar("travessao-na-interface", linha, f'{tag}: "{texto}"')
        for texto in filter(None, [attrs.get("placeholder"), attrs.get("value")]):
            if _genericos(texto):
                self.achar("dados-genericos", linha, f'{tag}: "{texto}"')

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in _VAZIOS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.pilha) - 1, -1, -1):
            if self.pilha[i][0] == tag:
                for _, _, e_variacao in self.pilha[i:]:
                    if e_variacao:
                        self.variacoes -= 1
                del self.pilha[i:]
                return

    # --- texto ---
    def handle_data(self, dado):
        if not self.variacoes or not dado.strip():
            return
        if self.pilha and self.pilha[-1][0] in ("script", "style"):
            return
        linha = self.getpos()[0] + dado[:len(dado) - len(dado.lstrip())].count("\n")
        texto = dado.strip()
        interface = self._de_interface()
        if interface and _travessao_proibido(texto):
            self.achar("travessao-na-interface", linha, texto)
        # Em célula, item de lista ou parágrafo, "07" é dado (dia, quantidade), não rótulo.
        if len(texto) <= 40 and not self._em_conteudo() and _ROTULO.search(texto):
            self.achar("rotulo-numerado", linha, texto)
        so_emoji = not _EMOJI.sub("", texto).strip(" ️")
        if _EMOJI.search(texto) and (interface or so_emoji):
            self.achar("emoji-como-icone", linha, texto)
        if _genericos(texto):
            self.achar("dados-genericos", linha, texto)
        if _PERFEITOS.search(texto):
            self.achar("numero-perfeito-demais", linha, texto)
        if _ENCHIMENTO.search(texto):
            self.achar("verbo-de-enchimento", linha, texto)


# --- orquestração -----------------------------------------------------------------------------

def _regras_ignoradas(html):
    """As regras de `detector: ignorar ...`. A lista acaba no primeiro termo que não tem forma
    de regra — é o começo da justificativa: "(mundo neobrutalista)", "— o brief pede". Termo
    com forma de regra que não existe é erro: um erro de digitação calaria a regra errada."""
    ignoradas = []
    for bloco in _IGNORAR.findall(html):
        for termo in re.split(r"[,;\s]+", bloco.strip()):
            if not termo:
                continue
            if not _ID_DE_REGRA.match(termo):
                break
            if termo not in REGRAS:
                raise ValueError(f"'detector: ignorar' cita a regra {termo!r}, que não existe; "
                                 f"as regras são: {', '.join(sorted(REGRAS))}")
            ignoradas.append(termo)
    return ignoradas


def analisar(html):
    """{"variacoes": n, "achados": [...], "ignoradas": [...], "suprimidos": [...]}."""
    ignoradas = _regras_ignoradas(html)
    achados, suprimidos, vistos = [], [], set()

    def achar(regra, linha, trecho):
        if (regra, linha) in vistos:
            return
        vistos.add((regra, linha))
        item = {"regra": regra, "severidade": REGRAS[regra]["severidade"],
                "linha": linha, "trecho": trecho[:120], "dica": REGRAS[regra]["dica"]}
        (suprimidos if regra in ignoradas else achados).append(item)

    design = _blocos_de_estilo(html)
    for linha_base, css in design:
        _regras_de_css(css, linha_base, achar)

    marcacao = _Marcacao(achar, lambda css, linha: _regras_de_css(css, linha, achar))
    marcacao.feed(html)
    marcacao.close()

    if marcacao.total_de_variacoes == 0:
        achar("nenhuma-variacao", 1, "nenhum elemento com class=\"variation\"")

    # A guarda de movimento é procurada no CSS (casca incluída, que é onde o harness a põe) —
    # nunca no texto: a palavra num parágrafo não protege ninguém.
    css_inteiro = " ".join(css for _, css in _blocos_de_estilo(html, sem_casca=False))
    anima = any(re.search(r"@keyframes|\banimation\s*:|\btransition\s*:", css, re.I)
                for _, css in design)
    if anima and "prefers-reduced-motion" not in css_inteiro:
        achar("sem-reducao-de-movimento", 1, "animação sem @media (prefers-reduced-motion)")

    # Knob declarado que nenhum CSS usa: o controle aparece e não faz nada.
    css_do_design = " ".join(css for _, css in design) + " " + " ".join(
        re.findall(r'style="([^"]*)"', html))
    for linha, lista in marcacao.knobs:
        for knob in lista:
            if not isinstance(knob, dict) or not knob.get("id"):
                continue
            id_ = str(knob["id"])
            if f"--k-{id_}" not in css_do_design and f"data-k-{id_}" not in css_do_design:
                achar("knob-sem-efeito", linha, f'knob "{id_}"')

    for lista in (achados, suprimidos):
        lista.sort(key=lambda a: (a["linha"], a["regra"]))
    return {"variacoes": marcacao.total_de_variacoes, "achados": achados,
            "ignoradas": sorted(set(ignoradas)), "suprimidos": suprimidos}


def _texto(resultado):
    linhas = [f"{resultado['variacoes']} variação(ões) analisada(s)."]
    for severidade in ("falha", "aviso"):
        grupo = [a for a in resultado["achados"] if a["severidade"] == severidade]
        if grupo:
            linhas.append(f"{severidade.upper()} ({len(grupo)})")
            for a in grupo:
                linhas.append(f"  linha {a['linha']:>4} · {a['regra']}: {a['trecho']}")
                linhas.append(f"             → {a['dica']}")
    if resultado["ignoradas"]:
        linhas.append(f"IGNORADAS por declaração no HTML: {', '.join(resultado['ignoradas'])}")
        for a in resultado["suprimidos"]:
            linhas.append(f"  linha {a['linha']:>4} · {a['regra']}: {a['trecho']}")
        if not resultado["suprimidos"]:
            linhas.append("  (nenhum achado dessas regras nesta rodada)")
    if not resultado["achados"]:
        linhas.append("nenhum tell encontrado.")
    return "\n".join(linhas)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    caminhos = [a for a in argv if not a.startswith("--")]
    if len(caminhos) != 1:
        print("uso: detectar.py <index.html> [--json]", file=sys.stderr)
        return 1
    try:
        with open(caminhos[0], encoding="utf-8") as arquivo:
            resultado = analisar(arquivo.read())
    except (OSError, ValueError) as erro:
        print(f"detectar: {erro}", file=sys.stderr)
        return 1
    print(json.dumps(resultado, ensure_ascii=False, indent=2) if "--json" in argv
          else _texto(resultado))
    return 2 if any(a["severidade"] == "falha" for a in resultado["achados"]) else 0


if __name__ == "__main__":
    sys.exit(main())
