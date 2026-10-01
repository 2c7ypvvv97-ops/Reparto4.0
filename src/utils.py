import re
from datetime import datetime

def parse_qr_scheda(qr_string: str):
    """
    Parsifica codici scheda scansionati senza spazi.
    Esempio: SE.0176965.F-1-T382502077
    - Codice: SE.0176965.F-1-T
    - WWYY: 3825
    - Prog: 02077 (5 cifre complete)
    """
    if not qr_string:
        return None

    qr_cleaned = qr_string.strip()
    if not qr_cleaned:
        return None

    # Cerca la parte finale composta esattamente da 9 cifre (4 per WWYY + 5 per Progressivo)
    # E cattura tutto ciò che sta prima come codice scheda
    pattern = r"^(?P<codice>.+?)(?P<wwyy>\d{4})(?P<prog>\d{5})$"
    
    match = re.match(pattern, qr_cleaned)
    if match:
        return {
            "qr_raw": qr_cleaned,
            "codice": match.group("codice").upper(),
            "wwyy": match.group("wwyy"),
            "prog": match.group("prog")  # Mantiene tutte e 5 le cifre del progressivo
        }
    else:
        # Fallback se la stringa ha un formato non standard
        return {
            "qr_raw": qr_cleaned,
            "codice": qr_cleaned.upper(),
            "wwyy": "0000",
            "prog": qr_cleaned[-5:] if len(qr_cleaned) >= 5 else "00000"
        }

def genera_seriale_centralina(commessa: str, modello: str) -> str:
    """Genera un seriale univoco per la centralina con timestamp."""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"CTRL-{commessa.upper()}-{modello.upper()}-{timestamp}"