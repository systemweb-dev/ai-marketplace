"""Validade do certificado TLS do context Docker — checagem proativa.

Lê **apenas o certificado público** (`cert.pem`) do context, e dele apenas a data de expiração.
NUNCA toca em `key.pem` (chave privada). Se o context não usa TLS (ex.: ssh:// ou socket local),
não há certificado e a checagem é silenciosamente ignorada.
"""
import base64
import datetime
import hashlib
import os

CONTEXTS_DIR = os.path.expanduser("~/.docker/contexts")
PUBLIC_CERT = "cert.pem"          # único arquivo que este módulo abre


def cert_path(context_name, base_dir=None):
    """Caminho do certificado público do context (None se não existir/não usar TLS)."""
    base = base_dir or CONTEXTS_DIR
    cid = hashlib.sha256((context_name or "").encode()).hexdigest()
    p = os.path.join(base, "tls", cid, "docker", PUBLIC_CERT)
    return p if os.path.isfile(p) else None


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


def not_after(path):
    """Data de expiração do certificado PEM (datetime UTC) ou None se não der pra ler."""
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            pem = f.read()
    except OSError:
        return None
    body = "".join(l for l in pem.splitlines() if "-----" not in l)
    try:
        der = base64.b64decode(body)
    except Exception:
        return None

    # As duas primeiras horas ASN.1 do certificado são o par Validity (notBefore, notAfter).
    times, i = [], 0
    while i < len(der) - 2 and len(times) < 2:
        tag, ln = der[i], der[i + 1]
        if tag in (0x17, 0x18) and ln < 0x80 and i + 2 + ln <= len(der):
            val = der[i + 2:i + 2 + ln].decode("ascii", "ignore")
            dt = _parse_asn1_time(tag, val)
            if dt:
                times.append(dt)
                i += 2 + ln
                continue
        i += 1
    return times[1] if len(times) == 2 else None


def check(context_name, now=None, warn_days=30, base_dir=None):
    """Retorna {status, days_left, not_after} ou None quando não há certificado (ex.: ssh://).

    status: "expired" | "expiring" (< warn_days) | "ok"
    """
    p = cert_path(context_name, base_dir)
    if not p:
        return None
    exp = not_after(p)
    if not exp:
        return None
    now = now or datetime.datetime.now(datetime.timezone.utc)
    days = (exp - now).days
    status = "expired" if exp <= now else ("expiring" if days < warn_days else "ok")
    return {"status": status, "days_left": days, "not_after": exp.isoformat()}
