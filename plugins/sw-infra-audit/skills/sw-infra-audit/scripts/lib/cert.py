"""Validade dos certificados TLS do context Docker — dado do relatório + alerta proativo.

Lê **apenas os certificados públicos** (`ca.pem` e `cert.pem`) do diretório do context, e deles
apenas as datas de validade. NUNCA toca em `key.pem` (chave privada).

Checa a CA **e** o certificado de cliente: a CA costuma ter validade própria e, se ela vencer,
tudo para junto — mesmo que o certificado de cliente ainda esteja válido.

Context sem TLS (ex.: `ssh://`, socket local) não tem certificado → devolve None e a checagem
é ignorada em silêncio.
"""
import base64
import datetime
import hashlib
import os

CONTEXTS_DIR = os.path.expanduser("~/.docker/contexts")
PUBLIC_CERTS = ("ca.pem", "cert.pem")     # únicos arquivos que este módulo abre
WARN_DAYS = 30


def context_tls_dir(context_name, base_dir=None):
    """Diretório TLS do context (None se o context não usa TLS)."""
    base = base_dir or CONTEXTS_DIR
    cid = hashlib.sha256((context_name or "").encode()).hexdigest()
    d = os.path.join(base, "tls", cid, "docker")
    return d if os.path.isdir(d) else None


def _parse_asn1_time(tag, value):
    """UTCTime (YYMMDDHHMMSSZ) ou GeneralizedTime (YYYYMMDDHHMMSSZ) → datetime UTC."""
    v = value.strip().rstrip("Z")
    try:
        if tag == 0x17:                       # UTCTime: ano com 2 dígitos
            yy = int(v[:2])
            year = 1900 + yy if yy >= 50 else 2000 + yy
            rest = v[2:]
        else:                                  # GeneralizedTime
            year, rest = int(v[:4]), v[4:]
        mo, d, h = int(rest[0:2]), int(rest[2:4]), int(rest[4:6])
        mi = int(rest[6:8]) if len(rest) >= 8 else 0
        se = int(rest[8:10]) if len(rest) >= 10 else 0
        return datetime.datetime(year, mo, d, h, mi, se, tzinfo=datetime.timezone.utc)
    except (ValueError, IndexError):
        return None


def validity(path):
    """(notBefore, notAfter) do certificado PEM, em UTC. (None, None) se não der pra ler."""
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            pem = f.read()
    except OSError:
        return None, None
    body = "".join(l for l in pem.splitlines() if "-----" not in l)
    try:
        der = base64.b64decode(body)
    except Exception:
        return None, None

    # As duas primeiras horas ASN.1 do certificado são o par Validity (notBefore, notAfter).
    times, i = [], 0
    while i < len(der) - 2 and len(times) < 2:
        tag, ln = der[i], der[i + 1]
        if tag in (0x17, 0x18) and ln < 0x80 and i + 2 + ln <= len(der):
            dt = _parse_asn1_time(tag, der[i + 2:i + 2 + ln].decode("ascii", "ignore"))
            if dt:
                times.append(dt)
                i += 2 + ln
                continue
        i += 1
    return (times[0], times[1]) if len(times) == 2 else (None, None)


def _status(exp, now, warn_days):
    if exp <= now:
        return "expired"
    return "expiring" if (exp - now).days < warn_days else "ok"


def check(context_name, now=None, warn_days=WARN_DAYS, base_dir=None):
    """Dados dos certificados do context, ou None se o context não usa TLS.

    {
      "status": "expired|expiring|ok",     # o PIOR entre os certificados
      "days_left": 123,                    # do que vence primeiro
      "not_after": "...",                  # idem
      "certs": [ {"file","status","days_left","not_before","not_after"} ]
    }
    """
    d = context_tls_dir(context_name, base_dir)
    if not d:
        return None
    now = now or datetime.datetime.now(datetime.timezone.utc)

    certs = []
    for name in PUBLIC_CERTS:
        p = os.path.join(d, name)
        if not os.path.isfile(p):
            continue
        nb, na_ = validity(p)
        if not na_:
            continue
        certs.append({
            "file": name,
            "label": "autoridade (CA)" if name == "ca.pem" else "cliente",
            "status": _status(na_, now, warn_days),
            "days_left": (na_ - now).days,
            "not_before": nb.isoformat() if nb else None,
            "not_after": na_.isoformat(),
        })
    if not certs:
        return None

    pior = min(certs, key=lambda c: c["days_left"])     # o que vence primeiro manda
    return {"status": pior["status"], "days_left": pior["days_left"],
            "not_after": pior["not_after"], "certs": certs}
