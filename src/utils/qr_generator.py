"""
Generador de códigos QR para los locales.
"""
import io
import base64
import socket
import subprocess

import qrcode
from qrcode.image.pil import PilImage


def get_local_ip() -> str:
    """Retorna la IP local de la maquina en la red actual (no loopback)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # No envia trafico real: solo resuelve la interfaz de salida.
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def get_machine_hostname() -> str | None:
    """Retorna el nombre de host para mDNS (Bonjour/Avahi), o None."""
    # macOS: nombre Bonjour estable que resuelve como <nombre>.local
    try:
        out = subprocess.run(
            ["scutil", "--get", "LocalHostName"],
            capture_output=True, text=True, timeout=2,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    # Linux/otros: el hostname suele resolverse via Avahi como <host>.local
    try:
        name = socket.gethostname()
        if name and name.lower() != "localhost":
            return name
    except Exception:
        pass
    return None


def get_server_base_url() -> str:
    """URL base estable para el QR: nombre .local (mDNS) o IP LAN.

    El nombre .local se resuelve solo a la IP actual de la maquina en la red
    donde este, por lo que el QR no se rompe al cambiar de red.
    """
    name = get_machine_hostname()
    if name:
        return f"http://{name}.local"
    return f"http://{get_local_ip()}"


def generate_qr_code(url: str, box_size: int = 10, border: int = 4) -> PilImage:
    """Genera un código QR a partir de una URL."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=box_size,
        border=border,
    )
    qr.add_data(url)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white")


def qr_to_base64(url: str) -> str:
    """Genera un QR y lo retorna como string base64 para embed en HTML."""
    img = generate_qr_code(url)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    img_str = base64.b64encode(buffer.read()).decode("utf-8")
    return f"data:image/png;base64,{img_str}"


def generate_venue_qr_url(base_url: str, qr_token: str) -> str:
    """Genera la URL que apunta al QR de un local."""
    return f"{base_url}/join/{qr_token}"
