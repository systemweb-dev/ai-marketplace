"""A senha sai do ambiente, entra num header e não aparece em mais lugar nenhum.

O `alvos.toml` declara `senha_env = "NOME_DA_VARIAVEL"` — o NOME, nunca o valor. O arquivo vive
fora do git com permissão 600, mas "fora do git" não é o mesmo que "seguro de imprimir": basta
um traceback para o conteúdo dele virar log.

A credencial é amarrada a **(alvo, host, porta)**, e `para(url)` recusa qualquer outro destino.
Não existe credencial "da rodada": num alvo com dois componentes autenticados, a senha de um
não pode ir parar na requisição do outro por descuido de código.

Este é o único módulo da skill que lê variável de ambiente para obter SEGREDO (`lib/runner.py`
também lê `os.environ`, com lista positiva, para montar o ambiente do processo filho — e é
justamente por essa lista ser positiva que a senha não chega lá). Concentrar o segredo aqui é o
que torna verificável, na Task 13, que nenhum adaptador toca `os.environ`.
"""
import os

from lib import http_get

USUARIO_PADRAO = "guest"


class CredencialFaltando(Exception):
    """`senha_env` declarado, variável ausente no ambiente."""


class Credencial:
    """Amarrada a (alvo, host, porta). Não serializa e não se imprime."""

    __slots__ = ("alvo", "componente", "usuario", "_senha", "_destino")

    def __init__(self, alvo, componente, usuario, senha, destino):
        self.alvo = alvo
        self.componente = componente
        self.usuario = usuario
        self._senha = senha
        self._destino = destino

    def para(self, url, alvo):
        """O `(usuario, senha)`, e só se a URL E o alvo forem os desta credencial.

        É deliberadamente a ÚNICA forma de obter o par. A versão anterior expunha um `par()`
        público, e aí a amarração virava convenção: qualquer chamador que escrevesse `par()`
        em vez de `para(url)` mandava a senha para qualquer destino da allowlist, sem erro.

        O `alvo` entra na comparação porque (host, porta) não basta: dois alvos (prod e dr,
        blue e green) podem declarar o MESMO endereço com senhas diferentes, e aí a de um
        autenticaria no outro.
        """
        if None in self._destino:
            # Credencial sem destino resolvido casaria com toda URL que também não parseia,
            # porque a comparação é de tuplas. `de_componente` já recusa criar uma assim; esta
            # guarda é para quem construir a classe direto.
            return None
        if alvo != self.alvo or http_get.destino(url) != self._destino:
            return None
        return (self.usuario, self._senha)

    def __repr__(self):
        host, porta = self._destino
        return f"<Credencial {self.usuario}@{host}:{porta} alvo={self.alvo!r}>"

    __str__ = __repr__

    def __getstate__(self):
        """`__slots__` bloqueia `vars()`, mas não bloqueia pickle, `copy` nem
        `object.__getstate__` — todos os três devolviam a senha. Um `deepcopy` do grafo de
        componentes bastaria para gravá-la."""
        raise TypeError("Credencial não serializa: a senha não pode sair deste objeto por "
                        "pickle, copy ou __getstate__")


def de_componente(componente, alvo, ambiente=None):
    """A credencial de um componente, ou None quando ele não declara `senha_env`.

    Componente sem `senha_env` não é erro: a API pode ser aberta em rede interna, e o adaptador
    tenta sem credencial e lida com o 401.
    """
    nome_da_variavel = componente.get("senha_env")
    if not nome_da_variavel:
        return None
    ambiente = os.environ if ambiente is None else ambiente
    if nome_da_variavel not in ambiente:
        raise CredencialFaltando(
            f"o componente {componente.get('nome')!r} declara senha_env="
            f"{nome_da_variavel!r}, mas essa variável não está no ambiente — exporte-a antes "
            f"de rodar a auditoria")
    destino = http_get.destino(componente.get("admin_url"))
    if destino[0] is None or destino[1] is None:
        # Sem destino resolvido, `_destino` viraria (None, None) — e `para()` compara tuplas,
        # então a credencial casaria com TODA url que também não parseia. A função que existe
        # para amarrar a senha entregaria a senha.
        raise CredencialFaltando(
            f"o componente {componente.get('nome')!r} declara senha_env mas não tem "
            f"`admin_url` com host e porta — sem destino não há a que amarrar a credencial")
    return Credencial(alvo=alvo, componente=componente.get("nome"),
                      usuario=componente.get("usuario") or USUARIO_PADRAO,
                      senha=ambiente[nome_da_variavel], destino=destino)


class CredencialRecusada(Exception):
    """Credencial que não vira arquivo de opções do cliente sem mudar de sentido."""


def _escapar(texto):
    """Valor entre aspas duplas no arquivo de opções do MySQL/MariaDB: `\\` e `"` escapados.

    O `#` fica como está: dentro das aspas ele é literal (o leitor só corta comentário fora delas), e
    `\\#` deixaria a barra dentro da senha — conferido no spike, referencias/spike-mysql-stdin.md."""
    return texto.replace("\\", "\\\\").replace('"', '\\"')


class CredencialSsh:
    """Amarrada a (alvo, destino ssh, porta, componente). Sai só como o `[client]` do arquivo de
    opções, para o stdin do ssh, e só para a mesma amarração. Não serializa e não se imprime."""

    __slots__ = ("alvo", "destino", "porta", "componente", "usuario", "_senha")

    def __init__(self, alvo, destino, porta, componente, usuario, senha):
        self.alvo = alvo
        self.destino = destino
        self.porta = porta
        self.componente = componente
        self.usuario = usuario
        self._senha = senha

    def entrada(self, alvo, destino, porta, componente):
        """O arquivo de opções com usuário e senha — None fora da amarração."""
        if (alvo, destino, porta, componente) != (self.alvo, self.destino, self.porta, self.componente):
            return None
        return (f'[client]\nuser="{_escapar(self.usuario)}"\n'
                f'password="{_escapar(self._senha)}"\n')  # noscan: molde; a senha vem da variável

    def __repr__(self):
        return f"<CredencialSsh componente={self.componente!r} alvo={self.alvo!r}>"

    __str__ = __repr__

    def __getstate__(self):
        raise TypeError("CredencialSsh não serializa: a senha não pode sair deste objeto por "
                        "pickle, copy ou __getstate__")


def de_componente_ssh(componente, alvo, destino, porta, ambiente=None):
    """A credencial de leitura de um componente de host, ou None quando ele não lê com senha.

    Usuário é obrigatório: sem ele, o cliente usaria o usuário do SSH (root) com a senha de outro."""
    if componente.get("leitura") != "senha":
        return None
    nome_da_variavel, usuario = componente.get("senha_env"), componente.get("usuario")
    if not usuario or not nome_da_variavel:
        raise CredencialFaltando(f"o componente {componente.get('nome')!r} declara leitura = "
                                 f'"senha" sem usuario e senha_env')
    ambiente = os.environ if ambiente is None else ambiente
    if nome_da_variavel not in ambiente:
        raise CredencialFaltando(
            f"o componente {componente.get('nome')!r} declara senha_env={nome_da_variavel!r}, mas "
            f"essa variável não está no ambiente — exporte-a antes de rodar a auditoria")
    senha = ambiente[nome_da_variavel]
    for texto in (usuario, senha):
        if any(c in texto for c in "\n\r\0"):
            raise CredencialRecusada(
                f"o usuário ou a senha do componente {componente.get('nome')!r} tem quebra de "
                f"linha, que o arquivo de opções do cliente não representa")
    return CredencialSsh(alvo, destino, porta, componente.get("nome"), usuario, senha)
