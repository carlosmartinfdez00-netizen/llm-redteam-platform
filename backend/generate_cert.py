"""
Genera un certificado TLS autofirmado para servir el panel web en HTTPS
en local (https://localhost:8000 en vez de http://localhost:8000).

Uso:
    python generate_cert.py

Crea la carpeta certs/ con cert.pem y key.pem. Luego arranca el backend
con:
    python -m uvicorn app.main:app --port 8000 --ssl-keyfile certs/key.pem --ssl-certfile certs/cert.pem

El navegador mostrará un aviso de "certificado no seguro" la primera vez
(es normal con un certificado autofirmado): acepta continuar / añade una
excepción para localhost. Esto no afecta a la conexión con Ollama, que
sigue siendo interna al servidor (Python -> Ollama por HTTP), no algo que
el navegador vea directamente.
"""
import datetime
import ipaddress
import os

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def main() -> None:
    out_dir = "certs"
    os.makedirs(out_dir, exist_ok=True)
    key_path = os.path.join(out_dir, "key.pem")
    cert_path = os.path.join(out_dir, "cert.pem")

    if os.path.exists(key_path) and os.path.exists(cert_path):
        print(f"Ya existen {key_path} y {cert_path}; no se regeneran.")
        return

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "localhost")]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=825))
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                ]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    with open(key_path, "wb") as f:
        f.write(
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    print(f"Certificado generado: {cert_path}")
    print(f"Clave privada generada: {key_path}")
    print(
        "\nArranca el backend con:\n"
        "  python -m uvicorn app.main:app --port 8000 "
        "--ssl-keyfile certs/key.pem --ssl-certfile certs/cert.pem\n"
        "y abre https://localhost:8000 en el navegador "
        "(acepta el aviso de certificado autofirmado)."
    )


if __name__ == "__main__":
    main()
