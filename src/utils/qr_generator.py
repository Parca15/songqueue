"""
Generador de códigos QR para los locales.
"""
import io
import base64

import qrcode
from qrcode.image.pil import PilImage


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
