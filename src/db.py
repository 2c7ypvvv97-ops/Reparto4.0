import os
import sqlite3
import hashlib

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "database.db")

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # 0. Tabella Utenti (Gestione RBAC)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS utenti (
        username TEXT PRIMARY KEY,
        password_hash TEXT NOT NULL,
        nome_completo TEXT NOT NULL,
        ruolo TEXT CHECK(ruolo IN ('OPERATORE', 'QUALITA', 'ADMIN')) NOT NULL,
        attivo INTEGER DEFAULT 1,
        data_creazione DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Utente ADMIN di default se la tabella è vuota (admin / admin123)
    check_users = cursor.execute("SELECT COUNT(*) FROM utenti").fetchone()[0]
    if check_users == 0:
        cursor.execute(
            "INSERT INTO utenti (username, password_hash, nome_completo, ruolo) VALUES (?, ?, ?, ?)",
            ("admin", hash_password("admin123"), "Amministratore Sistema", "ADMIN")
        )

    # 1. Tabella Schede
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS schede (
        qr_raw TEXT PRIMARY KEY,
        commessa TEXT NOT NULL,
        codice_scheda TEXT NOT NULL,
        anno_settimana TEXT NOT NULL,
        progressivo TEXT NOT NULL,
        stato TEXT CHECK(stato IN ('MAGAZZINO', 'IN_USO', 'IN_RIPARAZIONE', 'SCARTO_DEFINITIVO')) DEFAULT 'MAGAZZINO',
        data_ingresso DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. Tabella Modelli / BOM
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bom (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        modello TEXT NOT NULL,
        posiz_scheda INTEGER NOT NULL,
        codice_scheda_atteso TEXT NOT NULL,
        UNIQUE(modello, posiz_scheda)
    );
    """)

    # 3. Tabella Centraline Finite
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS centraline (
        seriale_centralina TEXT PRIMARY KEY,
        modello TEXT NOT NULL,
        commessa TEXT NOT NULL,
        progressivo_modello INTEGER NOT NULL,
        fase_attuale TEXT DEFAULT 'Assemblaggio',
        utente_assemblaggio TEXT,
        data_assemblaggio DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 4. Tabella Relazione Centralina <-> Schede
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS centralina_schede (
        seriale_centralina TEXT NOT NULL,
        qr_scheda TEXT NOT NULL,
        posiz_scheda INTEGER NOT NULL,
        PRIMARY KEY (seriale_centralina, posiz_scheda),
        FOREIGN KEY (seriale_centralina) REFERENCES centraline(seriale_centralina) ON DELETE CASCADE,
        FOREIGN KEY (qr_scheda) REFERENCES schede(qr_raw)
    );
    """)

    # 5. Tabella Commesse Schede
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS commesse (
        codice_commessa TEXT PRIMARY KEY,
        cliente TEXT,
        quantita INTEGER DEFAULT 0,
        note TEXT,
        data_creazione DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 6. Tabella Commesse Centraline
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS commesse_centraline (
        codice_commessa TEXT PRIMARY KEY,
        modello TEXT NOT NULL,
        quantita INTEGER NOT NULL,
        cliente TEXT,
        note TEXT,
        matricola_inizio INTEGER,
        data_creazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 7. Tabella Storico Fasi
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS storico_fasi (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        seriale_centralina TEXT,
        fase_da TEXT,
        fase_a TEXT,
        fase_precedente TEXT,
        fase_successiva TEXT,
        note TEXT,
        utente TEXT,
        data_ora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        data_cambio TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # 8. Tabella Riparazioni Schede
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS riparazioni_schede (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        qr_scheda TEXT NOT NULL,
        seriale_centralina TEXT,
        motivo_ko TEXT NOT NULL,
        intervento_riparazione TEXT,
        esito TEXT NOT NULL,
        utente TEXT,
        data_intervento TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()
    conn.close()


# --- GESTIONE UTENTI AGGIORNATA ---
def autentica_utente(username, password):
    conn = get_connection()
    res = conn.execute(
        "SELECT username, nome_completo, ruolo FROM utenti WHERE username = ? AND password_hash = ? AND attivo = 1",
        (username.strip().lower(), hash_password(password))
    ).fetchone()
    conn.close()
    if res:
        return True, {"username": res["username"], "nome": res["nome_completo"], "ruolo": res["ruolo"]}
    return False, None

def crea_utente(username, password, nome_completo, ruolo):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO utenti (username, password_hash, nome_completo, ruolo, attivo) VALUES (?, ?, ?, ?, 1)",
            (username.strip().lower(), hash_password(password), nome_completo.strip(), ruolo)
        )
        conn.commit()
        return True, f"✅ Utente '{username}' creato con successo!"
    except sqlite3.IntegrityError:
        return False, "❌ Username già esistente!"
    except Exception as e:
        return False, f"❌ Errore: {e}"
    finally:
        conn.close()

def reset_password_utente(username, nuova_password):
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE utenti SET password_hash = ? WHERE username = ?",
            (hash_password(nuova_password), username.strip().lower())
        )
        conn.commit()
        return True, f"✅ Password aggiornata per '{username}'!"
    except Exception as e:
        return False, f"❌ Errore: {e}"
    finally:
        conn.close()

def cambia_stato_utente(username, attivo):
    conn = get_connection()
    try:
        conn.execute("UPDATE utenti SET attivo = ? WHERE username = ?", (1 if attivo else 0, username.strip().lower()))
        conn.commit()
        stato_txt = "attivato" if attivo else "sospeso"
        return True, f"✅ Utente '{username}' {stato_txt} con successo!"
    except Exception as e:
        return False, f"❌ Errore: {e}"
    finally:
        conn.close()

def elimina_utente(username, admin_corrente):
    if username.strip().lower() == admin_corrente.strip().lower():
        return False, "❌ Non puoi eliminare l'account con cui sei attualmente collegato!"
    if username.strip().lower() == "admin":
        return False, "❌ Impossibile eliminare l'account 'admin' principale!"

    conn = get_connection()
    try:
        conn.execute("DELETE FROM utenti WHERE username = ?", (username.strip().lower(),))
        conn.commit()
        return True, f"🗑️ Utente '{username}' eliminato definitivamente!"
    except Exception as e:
        return False, f"❌ Errore durante l'eliminazione: {e}"
    finally:
        conn.close()

# --- FUNZIONI OPERATIVE ---
def salva_bom_modello(modello: str, lista_codici_scheda: list):
    conn = get_connection()
    try:
        with conn:
            conn.execute("DELETE FROM bom WHERE modello = ?", (modello.upper(),))
            for idx, codice in enumerate(lista_codici_scheda, start=1):
                conn.execute(
                    "INSERT INTO bom (modello, posiz_scheda, codice_scheda_atteso) VALUES (?, ?, ?)",
                    (modello.upper(), idx, codice.strip().upper())
                )
        return True, f"BOM per il modello {modello} salvata correttamente!"
    except Exception as e:
        return False, f"Errore nel salvataggio BOM: {str(e)}"
    finally:
        conn.close()

def get_bom_modello(modello: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT posiz_scheda, codice_scheda_atteso FROM bom WHERE modello = ? ORDER BY posiz_scheda ASC", 
        (modello.upper(),)
    )
    rows = cursor.fetchall()
    conn.close()
    return [r[1] for r in rows]

def inserisci_scheda(qr_raw, commessa, codice, wwyy, prog):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO schede (qr_raw, commessa, codice_scheda, anno_settimana, progressivo) VALUES (?, ?, ?, ?, ?)",
            (qr_raw, commessa, codice, wwyy, prog)
        )
        conn.commit()
        return True, "Scheda registrata con successo."
    except sqlite3.IntegrityError:
        return False, "QR Code già presente nel sistema!"
    finally:
        conn.close()

def genera_prossimo_seriale_modello(modello: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT MAX(progressivo_modello) FROM centraline WHERE modello = ?", 
        (modello.upper(),)
    )
    row = cursor.fetchone()
    max_prog = row[0] if (row and row[0] is not None) else 0
    nuovo_prog = max_prog + 1
    conn.close()
    seriale = f"{modello.upper()}-{nuovo_prog:05d}"
    return seriale, nuovo_prog

def registra_assemblaggio(seriale_centr, modello, commessa, prog_modello, qr_schede, utente=""):
    conn = get_connection()
    try:
        with conn:
            check_exist = conn.execute("SELECT 1 FROM centraline WHERE seriale_centralina = ?", (seriale_centr,)).fetchone()
            if check_exist:
                return False, f"❌ Errore: Il seriale {seriale_centr} risulta già registrato a sistema!"

            conn.execute(
                "INSERT INTO centraline (seriale_centralina, modello, commessa, progressivo_modello, fase_attuale, utente_assemblaggio) VALUES (?, ?, ?, ?, 'Assemblaggio', ?)",
                (seriale_centr, modello.upper(), commessa, prog_modello, utente)
            )
            for idx, qr in enumerate(qr_schede, start=1):
                conn.execute(
                    "INSERT INTO centralina_schede (seriale_centralina, qr_scheda, posiz_scheda) VALUES (?, ?, ?)",
                    (seriale_centr, qr, idx)
                )
                conn.execute("UPDATE schede SET stato = 'IN_USO' WHERE qr_raw = ?", (qr,))
                
            conn.execute("""
                INSERT INTO storico_fasi (seriale_centralina, fase_da, fase_a, fase_precedente, fase_successiva, note, utente)
                VALUES (?, 'N/A', 'Assemblaggio', 'N/A', 'Assemblaggio', 'Assemblaggio iniziale completato', ?)
            """, (seriale_centr, utente))
            
        return True, "Assemblaggio salvato!"
    except Exception as e:
        return False, f"Errore salvataggio: {str(e)}"
    finally:
        conn.close()

def elimina_bom_modello(modello):
    conn = get_connection()
    try:
        conn.execute("DELETE FROM bom WHERE modello = ?", (modello.upper(),))
        conn.commit()
        return True, f"BOM per il modello '{modello}' eliminata con successo!"
    except Exception as e:
        return False, f"Errore durante l'eliminazione: {e}"
    finally:
        conn.close()

def crea_commessa_centralina(codice_commessa, modello, quantita, cliente="", note="", matricola_inizio=None):
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO commesse_centraline (codice_commessa, modello, quantita, cliente, note, matricola_inizio)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (codice_commessa.upper(), modello.upper(), quantita, cliente, note, matricola_inizio))
        conn.commit()
        return True, f"Commessa {codice_commessa} creata con successo!"
    except Exception as e:
        return False, f"Errore durante la creazione: {e}"
    finally:
        conn.close()

def elimina_commessa_schede(codice_commessa):
    conn = get_connection()
    try:
        usate = conn.execute("""
            SELECT COUNT(*) FROM centralina_schede cs
            JOIN schede s ON cs.qr_scheda = s.qr_raw
            WHERE s.commessa = ?
        """, (codice_commessa,)).fetchone()[0]
        
        if usate > 0:
            return False, f"❌ Impossibile eliminare: {usate} schede usate in centraline assemblate!"

        conn.execute("DELETE FROM schede WHERE commessa = ?", (codice_commessa,))
        conn.execute("DELETE FROM commesse WHERE codice_commessa = ?", (codice_commessa,))
        conn.commit()
        return True, f"✅ Commessa Schede '{codice_commessa}' eliminata con successo!"
    except Exception as e:
        conn.rollback()
        return False, f"❌ Errore durante l'eliminazione: {e}"
    finally:
        conn.close()

def elimina_commessa_centralina(codice_commessa):
    conn = get_connection()
    try:
        centraline = conn.execute(
            "SELECT seriale_centralina FROM centraline WHERE commessa = ?", 
            (codice_commessa,)
        ).fetchall()
        seriali = [c[0] for c in centraline]
        
        if seriali:
            placeholders = ','.join('?' for _ in seriali)
            qr_schede = [row[0] for row in conn.execute(
                f"SELECT qr_scheda FROM centralina_schede WHERE seriale_centralina IN ({placeholders})", 
                seriali
            ).fetchall()]
            
            if qr_schede:
                ph_qr = ','.join('?' for _ in qr_schede)
                conn.execute(f"UPDATE schede SET stato = 'MAGAZZINO' WHERE qr_raw IN ({ph_qr})", qr_schede)
            
            conn.execute(f"DELETE FROM centralina_schede WHERE seriale_centralina IN ({placeholders})", seriali)
            conn.execute("DELETE FROM centraline WHERE commessa = ?", (codice_commessa,))

        conn.execute("DELETE FROM commesse_centraline WHERE codice_commessa = ?", (codice_commessa,))
        conn.commit()
        return True, f"✅ Commessa Centralina '{codice_commessa}' eliminata e schede ripristinate!"
    except Exception as e:
        conn.rollback()
        return False, f"❌ Errore durante l'eliminazione: {e}"
    finally:
        conn.close()

def aggiorna_fase_centralina(seriale_centralina, nuova_fase, note="", utente=""):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        res = cursor.execute(
            "SELECT fase_attuale FROM centraline WHERE seriale_centralina = ?", 
            (seriale_centralina,)
        ).fetchone()
        
        if not res:
            return False, f"❌ Centralina '{seriale_centralina}' non trovata."
            
        fase_attuale = res[0]
        cursor.execute("UPDATE centraline SET fase_attuale = ? WHERE seriale_centralina = ?", (nuova_fase, seriale_centralina))
        cursor.execute(
            """INSERT INTO storico_fasi 
               (seriale_centralina, fase_da, fase_a, fase_precedente, fase_successiva, note, utente) 
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (seriale_centralina, fase_attuale, nuova_fase, fase_attuale, nuova_fase, note, utente)
        )
        conn.commit()
        return True, f"✅ Centralina {seriale_centralina} spostata in '{nuova_fase}'."
    except Exception as e:
        conn.rollback()
        return False, f"❌ Errore durante l'aggiornamento della fase: {e}"
    finally:
        conn.close()

def sostituisci_scheda_centralina(seriale_centralina, posiz_scheda, nuovo_qr_scheda, utente=""):
    conn = get_connection()
    try:
        with conn:
            row_cent = conn.execute("SELECT modello FROM centraline WHERE seriale_centralina = ?", (seriale_centralina,)).fetchone()
            if not row_cent:
                return False, f"❌ Centralina {seriale_centralina} non trovata."
            modello = row_cent[0]

            row_vecchia = conn.execute("""
                SELECT qr_scheda FROM centralina_schede 
                WHERE seriale_centralina = ? AND posiz_scheda = ?
            """, (seriale_centralina, posiz_scheda)).fetchone()
            
            if not row_vecchia:
                return False, "❌ Nessuna scheda trovata per la posizione indicata."
            vecchio_qr = row_vecchia[0]

            row_nuova = conn.execute("SELECT codice_scheda, stato FROM schede WHERE qr_raw = ?", (nuovo_qr_scheda,)).fetchone()
            if not row_nuova:
                return False, f"❌ La nuova scheda ({nuovo_qr_scheda}) non esiste a sistema."
            
            codice_nuova, stato_nuova = row_nuova
            if stato_nuova != 'MAGAZZINO':
                return False, f"❌ La nuova scheda è nello stato '{stato_nuova}', non in 'MAGAZZINO'."

            row_bom = conn.execute("SELECT codice_scheda_atteso FROM bom WHERE modello = ? AND posiz_scheda = ?", (modello, posiz_scheda)).fetchone()
            if row_bom:
                codice_atteso = row_bom[0]
                if codice_nuova != codice_atteso and not codice_nuova.startswith(codice_atteso):
                    return False, f"❌ Incompatibilità BOM! Posizione {posiz_scheda} richiede codice '{codice_atteso}', la scheda inserita è '{codice_nuova}'."
            
            conn.execute("UPDATE schede SET stato = 'IN_RIPARAZIONE' WHERE qr_raw = ?", (vecchio_qr,))
            conn.execute("""
                UPDATE centralina_schede SET qr_scheda = ? 
                WHERE seriale_centralina = ? AND posiz_scheda = ?
            """, (nuovo_qr_scheda, seriale_centralina, posiz_scheda))
            conn.execute("UPDATE schede SET stato = 'IN_USO' WHERE qr_raw = ?", (nuovo_qr_scheda,))
            
            conn.execute("""
                INSERT INTO storico_fasi (seriale_centralina, fase_da, fase_a, fase_precedente, fase_successiva, note, utente)
                VALUES (?, 'Riparazione', 'Riparazione', 'Riparazione', 'Riparazione', ?, ?)
            """, (seriale_centralina, f"Sostituita scheda Pos {posiz_scheda}: KO ({vecchio_qr}) ➔ OK ({nuovo_qr_scheda})", utente))
            
        return True, "✅ Sostituzione completata! La vecchia scheda è stata inviata IN_RIPARAZIONE."
    except Exception as e:
        return False, f"❌ Errore durante la sostituzione: {e}"
    finally:
        conn.close()

def ripristina_scheda_riparata(qr_scheda, esito):
    conn = get_connection()
    try:
        if esito not in ['MAGAZZINO', 'SCARTO_DEFINITIVO']:
            return False, "Esito non valido."
            
        conn.execute("UPDATE schede SET stato = ? WHERE qr_raw = ?", (esito, qr_scheda))
        conn.commit()
        msg = "ritornata in MAGAZZINO" if esito == 'MAGAZZINO' else "segnata come SCARTO DEFINITIVO"
        return True, f"✅ Scheda {qr_scheda} {msg}!"
    except Exception as e:
        conn.rollback()
        return False, f"❌ Errore ripristino scheda: {e}"
    finally:
        conn.close()