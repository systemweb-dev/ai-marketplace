"""As três camadas de configuração: default (skill) < alvos (do projeto, ignorado) < projeto (versionado).

A camada do projeto é versionada e chega por clone ou pull request. Ela tem uma **lista positiva**
do que pode definir — qualquer outra coisa é erro. Lista de proibidos não serve aqui: basta um
jeito novo de escrever a mesma coisa (`[alvo.x]`, chave no topo, tabela com outro nome) para o
arquivo voltar a entregar conexão.
"""
import tomllib
from pathlib import PurePosixPath, Path

from lib import ignorado as ignorado_mod

# o arquivo de alvos mora junto do relatório, dentro do projeto — e a pasta dos dois é a que
# o .gitignore protege. Guardar conexão no home separava os alvos do projeto que os usa.
ARQUIVO_DOS_ALVOS = "alvos.toml"
ARQUIVO_DO_PROJETO = "config.toml"
LEGADO_DO_PROJETO = ".sw-infra-audit.toml"      # onde ele ficava antes, na raiz
PASTA_PADRAO = "docs/infra"

# o que o arquivo do projeto pode definir — nada além disto
PROJETO_PERMITE = ("alvos", "aceite", "relatorio", "severidade", "insights")
RELATORIO_PERMITE = ("pasta", "formato", "ignorar_em", "ip_completo")
INSIGHTS_PERMITE = ("janela", "limite_de_lista")
# o aceite é o único bloco do arquivo que APAGA achado: um erro de digitação aqui
# (`compomente`) viraria aceite do alvo inteiro, silenciosamente mais amplo que o pedido
ACEITE_PERMITE = ("alvo", "componente", "regra", "objeto", "motivo", "desde", "revisar_em")
# defesa em profundidade: nenhum nome de conexão, em qualquer profundidade
CHAVES_DE_CONEXAO = ("tipo", "host", "porta", "usuario", "senha", "senha_env", "metricas_url",
                     "context", "url", "password", "token")


class ConfigInvalida(Exception):
    """Configuração que a skill se recusa a interpretar."""


def _ler(caminho):
    if caminho is None:
        return {}
    caminho = Path(caminho)
    if not caminho.exists():
        return {}
    try:
        with caminho.open("rb") as arquivo:
            return tomllib.load(arquivo)
    except tomllib.TOMLDecodeError as erro:
        raise ConfigInvalida(f"{caminho.name}: TOML inválido — {erro}") from erro
    except OSError as erro:
        raise ConfigInvalida(f"{caminho.name}: não consegui ler — {erro}") from erro


def _achatar(dados, prefixo=""):
    """{'a': {'b': 1}} -> {'a.b': 1}.

    Lista de tabelas (`[[alvo]]`, `[[aceite]]`) fica de fora: tem tratamento próprio. Lista de
    valores entra — senão `alvos = [...]` sumiria do efetivo e do `--explicar` sem uma palavra.
    """
    saida = {}
    for chave, valor in dados.items():
        nome = f"{prefixo}{chave}"
        if isinstance(valor, dict):
            saida.update(_achatar(valor, f"{nome}."))
        elif isinstance(valor, list) and valor and all(isinstance(i, dict) for i in valor):
            continue
        else:
            saida[nome] = valor
    return saida


def _validar_projeto(dados, nome_arquivo):
    """O arquivo versionado do projeto: só o que está na lista positiva, e nunca conexão."""
    for chave in dados:
        if chave not in PROJETO_PERMITE:
            raise ConfigInvalida(
                f"{nome_arquivo}: o arquivo do projeto não define {chave!r}. Aqui entram apenas "
                f"{', '.join(PROJETO_PERMITE)} — conexão (host, porta, usuário, credencial) mora "
                f"no alvos.toml da sua máquina, fora do repositório.")

    for chave in _achatar(dados):
        folha = chave.split(".")[-1].casefold()
        if folha in CHAVES_DE_CONEXAO:
            raise ConfigInvalida(
                f"{nome_arquivo}: a chave {chave!r} descreve conexão, e o arquivo do projeto é "
                f"versionado. Declare o alvo no alvos.toml da sua máquina.")

    alvos = dados.get("alvos", [])
    if not isinstance(alvos, list) or not all(isinstance(n, str) for n in alvos):
        raise ConfigInvalida(f"{nome_arquivo}: `alvos` precisa ser uma lista de NOMES de alvos "
                             f"declarados no alvos.toml, por exemplo alvos = [\"cluster\"].")

    relatorio = dados.get("relatorio", {})
    if not isinstance(relatorio, dict):
        raise ConfigInvalida(f"{nome_arquivo}: `relatorio` precisa ser uma tabela")
    for chave in relatorio:
        if chave not in RELATORIO_PERMITE:
            raise ConfigInvalida(f"{nome_arquivo}: relatorio.{chave} não existe; disponíveis: "
                                 f"{', '.join(RELATORIO_PERMITE)}")
    insights = dados.get("insights", {})
    if not isinstance(insights, dict):
        raise ConfigInvalida(f"{nome_arquivo}: `insights` precisa ser uma tabela")
    for chave in insights:
        if chave not in INSIGHTS_PERMITE:
            raise ConfigInvalida(f"{nome_arquivo}: insights.{chave} não existe; disponíveis: "
                                 f"{', '.join(INSIGHTS_PERMITE)}")

    for aceite in dados.get("aceite", []):
        if not isinstance(aceite, dict):
            raise ConfigInvalida(f"{nome_arquivo}: cada aceite é um bloco [[aceite]]")
        for chave in aceite:
            if chave not in ACEITE_PERMITE:
                raise ConfigInvalida(f"{nome_arquivo}: aceite.{chave} não existe; disponíveis: "
                                     f"{', '.join(ACEITE_PERMITE)}")

    pasta = relatorio.get("pasta")
    if pasta is not None:
        caminho = PurePosixPath(str(pasta))
        if caminho.is_absolute() or ".." in caminho.parts:
            raise ConfigInvalida(f"{nome_arquivo}: relatorio.pasta precisa ser relativa e dentro do "
                                 f"projeto — {pasta!r} não é.")


class Config:
    def __init__(self, camadas, alvos_escolhidos, aceites):
        self._valores, self._origens = {}, {}
        for origem, dados in camadas:                  # ordem: default, infra, projeto
            for chave, valor in _achatar(dados).items():
                self._valores[chave] = valor
                self._origens[chave] = origem
        self._alvos = alvos_escolhidos
        self._aceites = aceites

    def valor(self, chave):
        return self._valores.get(chave)

    def origem(self, chave):
        return self._origens.get(chave)

    def alvos_escolhidos(self):
        return list(self._alvos)

    def aceites(self):
        return list(self._aceites)

    def explicar(self):
        """[(chave, valor, origem)] em ordem estável — saída que o usuário compara entre rodadas."""
        return sorted(((chave, self._valores[chave], self._origens[chave])
                       for chave in self._valores), key=lambda linha: linha[0])


def carregar(padrao, infra, projeto):
    dados_padrao, dados_infra, dados_projeto = _ler(padrao), _ler(infra), _ler(projeto)
    _validar_projeto(dados_projeto, Path(projeto).name if projeto else ".sw-infra-audit.toml")

    aceites = [dict(a, origem="infra") for a in dados_infra.get("aceite", [])]
    aceites += [dict(a, origem="projeto") for a in dados_projeto.get("aceite", [])]

    return Config(
        camadas=[("default", dados_padrao), ("infra", dados_infra), ("projeto", dados_projeto)],
        alvos_escolhidos=dados_projeto.get("alvos", []),
        aceites=aceites)


def caminho_dos_alvos(padrao, projeto, explicito=None):
    """Onde moram os alvos: `<pasta do relatório>/alvos.toml`, dentro do projeto.

    A pasta sai da configuração efetiva sem a camada de alvos (ela ainda não foi lida) — quem
    muda `relatorio.pasta` move o relatório E os alvos, porque duas pastas seriam duas verdades.
    """
    if explicito:
        return Path(explicito)
    efetiva = carregar(padrao=padrao, infra=None, projeto=projeto)
    return Path(str(efetiva.valor("relatorio.pasta") or PASTA_PADRAO)) / ARQUIVO_DOS_ALVOS


def exigir_pasta_protegida(caminho, raiz="."):
    """Recusa usar um arquivo de conexão que o git NÃO esteja ignorando.

    Fora de repositório não há o que proteger. Dentro, a pasta precisa estar no `.gitignore`:
    conexão versionada é conexão publicada, e o aviso tem que vir antes do primeiro commit.
    """
    caminho = Path(caminho)
    if not ignorado_mod.em_repositorio(raiz):
        return
    pasta = caminho.parent
    if ignorado_mod.ignorado(caminho, raiz) or ignorado_mod.ignorado(f"{pasta}/", raiz):
        return
    raise ConfigInvalida(
        f"{pasta}/ não está no .gitignore deste repositório, e {caminho.name} guarda conexão "
        f"(host, context, credencial). Rode `configurar.py ignorar --pasta {pasta}` antes de "
        f"declarar alvos — arquivo de conexão versionado é conexão publicada.")


def caminho_do_projeto(explicito=None, raiz="."):
    """O arquivo versionado do projeto: `docs/infra/config.toml`.

    Ponto de entrada da configuração, por isso o caminho é fixo — é ele que pode mover o resto
    (`relatorio.pasta`). Enquanto existir só o antigo `.sw-infra-audit.toml` na raiz, ele
    continua valendo: ninguém fica sem configuração de um dia para o outro.
    """
    if explicito:
        return Path(explicito)
    novo = Path(raiz) / PASTA_PADRAO / ARQUIVO_DO_PROJETO
    antigo = Path(raiz) / LEGADO_DO_PROJETO
    return antigo if not novo.exists() and antigo.exists() else novo
