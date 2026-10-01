import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor

# ==========================================
# CONFIGURAZIONE DATABASE
# ==========================================
# Seleziona il tipo di DB: "POSTGRES" (per la rete) oppure "SQLITE" (per test locale)
# USE_DB = os.getenv("APP_DB_TYPE", "POSTGRES")

USE_DB = "SQLITE"

# DATI CONNESSIONE POSTGRESQL (RETE)
DB_HOST = os.getenv("DB_HOST", "192.168.1.50")  # Modifica con l'IP del tuo server DB
DB_NAME = os.getenv("DB_NAME", "gestionale_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "tuapassword")
DB_PORT = os.getenv("DB_PORT", "5432")

# PERCORSO SQLITE (LOCALE)
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "database.db")


def get_connection():
    """Restituisce una nuova connessione attiva al database impostato."""
    if USE_DB == "POSTGRES":
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            port=DB_PORT
        )
        return conn
    else:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn


def execute_query(conn, query, params=()):
    """
    Esegue una query convertendo automaticamente il segnaposto '?' in '%s'
    se si sta utilizzando PostgreSQL.
    """
    if USE_DB == "POSTGRES":
        query_pg = query.replace("?", "%s")
        cursor = conn.cursor()
        cursor.execute(query_pg, params)
        return cursor
    else:
        return conn.execute(query, params)


def init_db():
    """Inizializza le tabelle sia per PostgreSQL che per SQLite."""
    conn = get_connection()
    cursor = conn.cursor()
    
    is_pg = (USE_DB == "POSTGRES")
    pk_auto = "SERIAL PRIMARY KEY" if is_pg else "INTEGER PRIMARY KEY AUTOINCREMENT"
    dt_type = "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"

    # 1. Tabella Schede
    if is_pg:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS schede (
            qr_raw TEXT PRIMARY KEY,
            commessa TEXT NOT NULL,
            codice_scheda TEXT NOT NULL,
            anno_settimana TEXT NOT NULL,
            progressivo TEXT NOT NULL,
            stato TEXT DEFAULT 'MAGAZZINO',
            data_ingresso TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
    else:
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
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS bom (
        id {pk_auto},
        modello TEXT NOT NULL,
        posiz_scheda INTEGER NOT NULL,
        codice_scheda_atteso TEXT NOT NULL,
        UNIQUE(modello, posiz_scheda)
    );
    """)

    # 3. Tabella Centraline Finite
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS centraline (
        seriale_centralina TEXT PRIMARY KEY,
        modello TEXT NOT NULL,
        commessa TEXT NOT NULL,
        progressivo_modello INTEGER NOT NULL,
        fase_attuale TEXT DEFAULT 'Assemblaggio',
        data_assemblaggio {dt_type}
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
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS commesse (
        codice_commessa TEXT PRIMARY KEY,
        cliente TEXT,
        quantita INTEGER DEFAULT 0,
        note TEXT,
        data_creazione {dt_type}
    );
    """)

    # 6. Tabella Commesse Centraline
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS commesse_centraline (
        codice_commessa TEXT PRIMARY KEY,
        modello TEXT NOT NULL,
        quantita INTEGER NOT NULL,
        cliente TEXT,
        note TEXT,
        matricola_inizio INTEGER,
        data_creazione {dt_type}
    );
    """)

    # 7. Tabella Storico Fasi
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS storico_fasi (
        id {pk_auto},
        seriale_centralina TEXT,
        fase_da TEXT,
        fase_a TEXT,
        note TEXT,
        data_ora {dt_type}
    );
    """)

    conn.commit()
    conn.close()


def salva_bom_modello(modello: str, lista_codici_scheda: list):
    conn = get_connection()
    try:
        execute_query(conn, "DELETE FROM bom WHERE modello = ?", (modello.upper(),))
        for idx, codice in enumerate(lista_codici_scheda, start=1):
            execute_query(
                conn,
                "INSERT INTO bom (modello, posiz_scheda, codice_scheda_atteso) VALUES (?, ?, ?)",
                (modello.upper(), idx, codice.strip().upper())
            )
        conn.commit()
        return True, f"BOM per il modello {modello} salvata correttamente!"
    except Exception as e:
        conn.rollback()
        return False, f"Errore nel salvataggio BOM: {str(e)}"
    finally:
        conn.close()


def get_bom_modello(modello: str):
    conn = get_connection()
    cursor = execute_query(
        conn,
        "SELECT posiz_scheda, codice_scheda_atteso FROM bom WHERE modello = ? ORDER BY posiz_scheda ASC", 
        (modello.upper(),)
    )
    rows = cursor.fetchall()
    conn.close()
    return [r[1] for r in rows]


def inserisci_scheda(qr_raw, commessa, codice, wwyy, prog):
    conn = get_connection()
    try:
        execute_query(
            conn,
            "INSERT INTO schede (qr_raw, commessa, codice_scheda, anno_settimana, progressivo) VALUES (?, ?, ?, ?, ?)",
            (qr_raw, commessa, codice, wwyy, prog)
        )
        conn.commit()
        return True, "Scheda registrata con successo."
    except Exception as e:
        conn.rollback()
        if "unique" in str(e).lower() or "duplicate" in str(e).lower() or "primary key" in str(e).lower():
            return False, "QR Code già presente nel sistema!"
        return False, f"Errore inserimento: {str(e)}"
    finally:
        conn.close()


def genera_prossimo_seriale_modello(modello: str):
    conn = get_connection()
    cursor = execute_query(
        conn,
        "SELECT MAX(progressivo_modello) FROM centraline WHERE modello = ?", 
        (modello.upper(),)
    )
    row = cursor.fetchone()
    max_prog = row[0] if (row and row[0] is not None) else 0
    nuovo_prog = max_prog + 1
    conn.close()
    
    seriale = f"{modello.upper()}-{nuovo_prog:05d}"
    return seriale, nuovo_prog


def registra_assemblaggio(seriale_centr, modello, commessa, prog_modello, qr_schede):
    conn = get_connection()
    try:
        check_exist = execute_query(conn, "SELECT 1 FROM centraline WHERE seriale_centralina = ?", (seriale_centr,)).fetchone()
        if check_exist:
            return False, f"❌ Errore: Il seriale {seriale_centr} risulta già registrato a sistema!"

        execute_query(
            conn,
            "INSERT INTO centraline (seriale_centralina, modello, commessa, progressivo_modello, fase_attuale) VALUES (?, ?, ?, ?, 'Assemblaggio')",
            (seriale_centr, modello.upper(), commessa, prog_modello)
        )
        for idx, qr in enumerate(qr_schede, start=1):
            execute_query(
                conn,
                "INSERT INTO centralina_schede (seriale_centralina, qr_scheda, posiz_scheda) VALUES (?, ?, ?)",
                (seriale_centr, qr, idx)
            )
            execute_query(
                conn,
                "UPDATE schede SET stato = 'IN_USO' WHERE qr_raw = ?",
                (qr,)
            )
            
        execute_query(conn, """
            INSERT INTO storico_fasi (seriale_centralina, fase_da, fase_a, note)
            VALUES (?, 'N/A', 'Assemblaggio', 'Assemblaggio iniziale completato')
        """, (seriale_centr,))
        
        conn.commit()
        return True, "Assemblaggio salvato!"
    except Exception as e:
        conn.rollback()
        return False, f"Errore salvataggio: {str(e)}"
    finally:
        conn.close()


def elimina_bom_modello(modello):
    conn = get_connection()
    try:
        execute_query(conn, "DELETE FROM bom WHERE modello = ?", (modello.upper(),))
        conn.commit()
        return True, f"BOM per il modello '{modello}' eliminata con successo!"
    except Exception as e:
        conn.rollback()
        return False, f"Errore durante l'eliminazione: {e}"
    finally:
        conn.close()


def crea_commessa_centralina(codice_commessa, modello, quantita, cliente="", note="", matricola_inizio=None):
    conn = get_connection()
    try:
        execute_query(conn, """
            INSERT INTO commesse_centraline (codice_commessa, modello, quantita, cliente, note, matricola_inizio)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (codice_commessa.upper(), modello.upper(), quantita, cliente, note, matricola_inizio))
        conn.commit()
        return True, f"Commessa {codice_commessa} creata con successo!"
    except Exception as e:
        conn.rollback()
        return False, f"Errore durante la creazione: {e}"
    finally:
        conn.close()


def elimina_commessa_schede(codice_commessa):
    conn = get_connection()
    try:
        usate = execute_query(conn, """
            SELECT COUNT(*) FROM centralina_schede cs
            JOIN schede s ON cs.qr_scheda = s.qr_raw
            WHERE s.commessa = ?
        """, (codice_commessa,)).fetchone()[0]
        
        if usate > 0:
            return False, f"❌ Impossibile eliminare: {usate} schede di questa commessa sono già state usate in centraline assemblate!"

        execute_query(conn, "DELETE FROM schede WHERE commessa = ?", (codice_commessa,))
        execute_query(conn, "DELETE FROM commesse WHERE codice_commessa = ?", (codice_commessa,))
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
        cursor = execute_query(
            conn,
            "SELECT seriale_centralina FROM centraline WHERE commessa = ?", 
            (codice_commessa,)
        )
        centraline = cursor.fetchall()
        seriali = [c[0] for c in centraline]
        
        if seriali:
            placeholders = ','.join('?' for _ in seriali)
            cursor_qr = execute_query(
                conn,
                f"SELECT qr_scheda FROM centralina_schede WHERE seriale_centralina IN ({placeholders})", 
                seriali
            )
            qr_schede = [row[0] for row in cursor_qr.fetchall()]
            
            if qr_schede:
                ph_qr = ','.join('?' for _ in qr_schede)
                execute_query(conn, f"UPDATE schede SET stato = 'MAGAZZINO' WHERE qr_raw IN ({ph_qr})", qr_schede)
            
            execute_query(conn, f"DELETE FROM centralina_schede WHERE seriale_centralina IN ({placeholders})", seriali)
            execute_query(conn, f"DELETE FROM centraline WHERE commessa = ?", (codice_commessa,))

        execute_query(conn, "DELETE FROM commesse_centraline WHERE codice_commessa = ?", (codice_commessa,))
        conn.commit()
        return True, f"✅ Commessa Centralina '{codice_commessa}' eliminata e schede ripristinate in magazzino!"
    except Exception as e:
        conn.rollback()
        return False, f"❌ Errore durante l'eliminazione: {e}"
    finally:
        conn.close()


def aggiorna_fase_centralina(seriale_centralina, nuova_fase, note=""):
    conn = get_connection()
    try:
        row = execute_query(conn, "SELECT fase_attuale FROM centraline WHERE seriale_centralina = ?", (seriale_centralina,)).fetchone()
        if not row:
            return False, f"❌ Centralina '{seriale_centralina}' non trovata."
        
        fase_precedente = row[0]
        execute_query(conn, "UPDATE centraline SET fase_attuale = ? WHERE seriale_centralina = ?", (nuova_fase, seriale_centralina))
        
        execute_query(conn, """
            INSERT INTO storico_fasi (seriale_centralina, fase_da, fase_a, note)
            VALUES (?, ?, ?, ?)
        """, (seriale_centralina, fase_precedente, nuova_fase, note))
        
        conn.commit()
        return True, f"✅ Centralina {seriale_centralina} spostata in '{nuova_fase}'"
    except Exception as e:
        conn.rollback()
        return False, f"❌ Errore aggiornamento fase: {e}"
    finally:
        conn.close()


def sostituisci_scheda_centralina(seriale_centralina, posiz_scheda, nuovo_qr_scheda):
    """Sostituisce la scheda guasta in modo atomico, verificando prima la compatibilità BOM."""
    conn = get_connection()
    try:
        row_cent = execute_query(conn, "SELECT modello FROM centraline WHERE seriale_centralina = ?", (seriale_centralina,)).fetchone()
        if not row_cent:
            return False, f"❌ Centralina {seriale_centralina} non trovata."
        
        modello = row_cent[0]

        row_vecchia = execute_query(conn, """
            SELECT qr_scheda FROM centralina_schede 
            WHERE seriale_centralina = ? AND posiz_scheda = ?
        """, (seriale_centralina, posiz_scheda)).fetchone()
        
        if not row_vecchia:
            return False, "❌ Nessuna scheda trovata per la posizione indicata."
            
        vecchio_qr = row_vecchia[0]

        row_nuova = execute_query(conn, "SELECT codice_scheda, stato FROM schede WHERE qr_raw = ?", (nuovo_qr_scheda,)).fetchone()
        if not row_nuova:
            return False, f"❌ La nuova scheda ({nuovo_qr_scheda}) non esiste a sistema."
        
        codice_nuova, stato_nuova = row_nuova
        if stato_nuova != 'MAGAZZINO':
            return False, f"❌ La nuova scheda è nello stato '{stato_nuova}', non in 'MAGAZZINO'."

        row_bom = execute_query(conn, "SELECT codice_scheda_atteso FROM bom WHERE modello = ? AND posiz_scheda = ?", (modello, posiz_scheda)).fetchone()
        if row_bom:
            codice_atteso = row_bom[0]
            if codice_nuova != codice_atteso and not codice_nuova.startswith(codice_atteso):
                return False, f"❌ Incompatibilità BOM! Posizione {posiz_scheda} richiede codice '{codice_atteso}', la scheda inserita è '{codice_nuova}'."
        
        execute_query(conn, "UPDATE schede SET stato = 'IN_RIPARAZIONE' WHERE qr_raw = ?", (vecchio_qr,))
        
        execute_query(conn, """
            UPDATE centralina_schede SET qr_scheda = ? 
            WHERE seriale_centralina = ? AND posiz_scheda = ?
        """, (nuovo_qr_scheda, seriale_centralina, posiz_scheda))
        
        execute_query(conn, "UPDATE schede SET stato = 'IN_USO' WHERE qr_raw = ?", (nuovo_qr_scheda,))
        
        execute_query(conn, """
            INSERT INTO storico_fasi (seriale_centralina, fase_da, fase_a, note)
            VALUES (?, 'Riparazione', 'Riparazione', ?)
        """, (seriale_centralina, f"Sostituita scheda Pos {posiz_scheda}: KO ({vecchio_qr}) ➔ OK ({nuovo_qr_scheda})"))
        
        conn.commit()
        return True, "✅ Sostituzione completata con successo! La vecchia scheda è stata inviata IN_RIPARAZIONE."
    except Exception as e:
        conn.rollback()
        return False, f"❌ Errore durante la sostituzione: {e}"
    finally:
        conn.close()


def ripristina_scheda_riparata(qr_scheda, esito):
    conn = get_connection()
    try:
        if esito not in ['MAGAZZINO', 'SCARTO_DEFINITIVO']:
            return False, "Esito non valido."
            
        execute_query(conn, "UPDATE schede SET stato = ? WHERE qr_raw = ?", (esito, qr_scheda))
        conn.commit()
        msg = "ritornata in MAGAZZINO" if esito == 'MAGAZZINO' else "segnata come SCARTO DEFINITIVO"
        return True, f"✅ Scheda {qr_scheda} {msg}!"
    except Exception as e:
        conn.rollback()
        return False, f"❌ Errore ripristino scheda: {e}"
    finally:
        conn.close()