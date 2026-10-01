import re
from datetime import datetime

def parse_qr_scheda(qr_string: str):
    """
    Parsifica codici scheda nel formato:
    - SE.0192765.G-1-TSSAA00000 (con -T)
    - SE.0192765.G-1-SSAA00000   (senza -T)
    """
    if not qr_string:
        return None

    qr_cleaned = qr_string.strip()
    if not qr_cleaned:
        return None

    pattern = r"^(?P<codice>.+?)(?:-T)?-(?P<wwyy>\d{4})(?P<prog>\d{5})$"
    
    match = re.match(pattern, qr_cleaned)
    if match:
        raw_prog = match.group("prog")
        prog_4_cifre = raw_prog[-4:]
        
        return {
            "qr_raw": qr_cleaned,
            "codice": match.group("codice").upper(),
            "wwyy": match.group("wwyy"),
            "prog": prog_4_cifre
        }
    else:
        # Fallback pulito se il formato differisce leggermente
        parti = qr_cleaned.split("-")
        codice_approx = parti[0].upper() if len(parti) > 0 else qr_cleaned.upper()
        
        return {
            "qr_raw": qr_cleaned,
            "codice": codice_approx,
            "wwyy": "0000",
            "prog": qr_cleaned[-4:] if len(qr_cleaned) >= 4 else "0000"
        }

def genera_seriale_centralina(commessa: str, modello: str) -> str:
    """Genera un seriale univoco per la centralina con timestamp."""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"CTRL-{commessa.upper()}-{modello.upper()}-{timestamp}"