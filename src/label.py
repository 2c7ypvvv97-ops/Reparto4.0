import io
import socket
import qrcode
from PIL import Image, ImageDraw, ImageFont

def invia_zpl_a_stampante(zpl_code: str, ip_stampante: str, porta: int = 9100) -> tuple[bool, str]:
    """
    Invia direttamente il codice ZPL alla stampante Zebra tramite socket TCP/IP.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(3.0)  # Timeout di 3 secondi
            s.connect((ip_stampante, porta))
            s.sendall(zpl_code.encode('utf-8'))
        return True, "Etichetta inviata alla stampante con successo!"
    except Exception as e:
        return False, f"Errore di connessione alla stampante ({ip_stampante}): {e}"


def _estrai_progressivo(seriale: str) -> str:
    """Estrae solo la parte finale del seriale per il testo in chiaro."""
    if "-" in seriale:
        return seriale.split("-")[-1]
    elif "_" in seriale:
        return seriale.split("_")[-1]
    return seriale


def genera_zpl_centralina(seriale: str, modello: str, commessa: str) -> str:
    """
    Genera il codice ZPL nativo per stampanti Zebra.
    QR Code = Seriale completo. Testo in chiaro = Solo progressivo con S/N:.
    """
    progressivo = _estrai_progressivo(seriale)
    
    zpl = f"""
    ^XA
    ^FO30,30^BQN,2,6^FDLA,{seriale}^FS
    ^FO220,30^A0N,28,28^FDMODELLO: {modello}^FS
    ^FO220,65^A0N,22,22^FDCOMMESSA: {commessa}^FS
    ^FO220,105^A0N,30,30^FDS/N:^FS
    ^FO220,145^A0N,55,55^FD{progressivo}^FS
    ^XZ
    """
    return zpl.strip()


def genera_immagine_etichetta(seriale: str, modello: str, commessa: str) -> bytes:
    """
    Genera la grafica PNG con solo il progressivo finale in chiaro.
    """
    width, height = 650, 240
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    # Bordo etichetta
    draw.rectangle([5, 5, width - 5, height - 5], outline=(0, 0, 0), width=3)
    
    # Generazione QR Code (seriale completo per lo scanner)
    qr = qrcode.QRCode(box_size=5, border=1)
    qr.add_data(seriale)
    qr.make(fit=True)
    
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    qr_img = qr_img.resize((180, 180))
    img.paste(qr_img, (20, 30))
    
    progressivo_finale = _estrai_progressivo(seriale)

    # Caricamento Font
    try:
        font_small = ImageFont.truetype("arial.ttf", 16)
        font_medium = ImageFont.truetype("arialbd.ttf", 18)
        font_large = ImageFont.truetype("arialbd.ttf", 36)
    except IOError:
        font_small = ImageFont.load_default()
        font_medium = font_small
        font_large = font_small

    x_testo = 215
    
    draw.text((x_testo, 20), f"Modello: {modello}", fill=(0, 0, 0), font=font_medium)
    draw.text((x_testo, 55), f"Commessa: {commessa}", fill=(90, 90, 90), font=font_small)
    
    draw.line([(x_testo, 88), (width - 20, 88)], fill=(0, 0, 0), width=2)
    
    draw.text((x_testo, 98), "S/N:", fill=(0, 0, 0), font=font_medium)
    draw.text((x_testo, 130), progressivo_finale, fill=(0, 0, 0), font=font_large)
    
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()