"""Grava uma resposta humana no `knowledge.toml`.

É o quarto escritor da skill, e o único que grava o que uma pessoa disse. Existe
como script, e não como edição direta do TOML, pelo mesmo motivo dos outros três:
formato fechado não deriva. Aqui isso importa mais que nos outros, porque este é o
único arquivo que NÃO se regenera — formato quebrado aqui é informação perdida.
"""
import argparse
import sys
import tomllib
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import conhecimento  # noqa: E402


def _escapar(texto: str) -> str:
    return texto.replace('\\', '\\\\').replace('"', '\\"')


def gravar(base: Path, sobre: str, pergunta: str, resposta: str, quem: str,
           quando: str | None = None) -> Path:
    for nome, valor in (('sobre', sobre), ('pergunta', pergunta),
                        ('resposta', resposta), ('quem', quem)):
        if not str(valor).strip():
            raise ValueError(f'`{nome}` não pode ser vazio')
    quando = quando or date.today().isoformat()

    caminho = base / conhecimento.ARQUIVO
    cabecalho = ''
    if not caminho.exists():
        cabecalho = (
            '# O que gente sabe e o código não diz.\n'
            '#\n'
            '# Este é o ÚNICO arquivo da skill que não se regenera: o inventário se\n'
            '# refaz, a interpretação se reescreve e o documento se monta de novo, mas\n'
            '# o que está aqui só existe porque alguém respondeu. Apagá-lo perde\n'
            '# informação que o repositório não tem.\n'
            '#\n'
            '# Responder de novo ACRESCENTA um bloco; quem lê fica com o mais recente\n'
            '# de cada par (sobre, pergunta). O histórico fica, para dar para ver o que\n'
            '# mudou de ideia e quando.\n')

    # ESCRITA ATÔMICA, e é por causa do que este arquivo é: ele não se regenera.
    # Anexar e validar depois deixa um bloco quebrado dentro dele quando a validação
    # falha — e aí a informação de todo mundo fica inacessível por causa de uma
    # resposta malformada. O texto novo é montado, conferido em memória, e só então
    # substitui o arquivo.
    atual = caminho.read_text('utf-8') if caminho.exists() else ''
    novo = (cabecalho + atual
            + f'\n[[resposta]]\n'
              f'sobre = "{_escapar(sobre)}"\n'
              f'pergunta = "{_escapar(pergunta)}"\n'
              f'resposta = "{_escapar(resposta)}"\n'
              f'quem = "{_escapar(quem)}"\n'
              f'quando = "{quando}"\n')
    try:
        tomllib.loads(novo)
    except tomllib.TOMLDecodeError as erro:
        raise ValueError(f'a resposta não produziu TOML válido: {erro}') from erro
    caminho.write_text(novo, encoding='utf-8')
    return caminho


def main() -> int:
    p = argparse.ArgumentParser(description='Grava uma resposta humana.')
    p.add_argument('--dir', required=True, help='o diretório do documento')
    p.add_argument('--sobre', required=True,
                   help='o caminho do arquivo, ou o texto da pergunta em aberto')
    p.add_argument('--pergunta', required=True)
    p.add_argument('--resposta', required=True)
    p.add_argument('--quem', required=True, help='quem respondeu — vai no documento')
    p.add_argument('--quando', help='AAAA-MM-DD; o padrão é hoje')
    args = p.parse_args()
    try:
        caminho = gravar(Path(args.dir).resolve(), args.sobre, args.pergunta,
                         args.resposta, args.quem, args.quando)
    except (ValueError, OSError) as erro:
        print(erro, file=sys.stderr)
        return 2
    print(caminho)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
