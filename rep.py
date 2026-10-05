import base64
import io
import pandas as pd
import streamlit as st

# 1. PRIMO COMANDO STREAMLIT IN CIMA ALLO SCRIPT
st.set_page_config(
    page_title="Assemblaggio Centraline", page_icon="⚙️", layout="wide"
)

from src.db import (
    aggiorna_fase_centralina,
    autentica_utente,
    cambia_stato_utente,
    crea_commessa_centralina,
    crea_utente,
    elimina_bom_modello,
    elimina_commessa_centralina,
    elimina_commessa_schede,
    elimina_scheda_singola,
    elimina_utente,
    genera_prossimo_seriale_modello,
    get_bom_modello,
    get_connection,
    get_lista_codici_schede_noti,
    init_db,
    inserisci_scheda,
    registra_assemblaggio,
    reset_password_utente,
    ripristina_scheda_riparata,
    salva_bom_modello,
    sostituisci_scheda_centralina,
)
from src.label import (
    genera_immagine_etichetta,
    genera_zpl_centralina,
    invia_zpl_a_stampante,
)
from src.utils import parse_qr_scheda


def get_base64_of_bin_file(bin_file):
  try:
    with open(bin_file, "rb") as f:
      data = f.read()
    return base64.b64encode(data).decode()
  except Exception:
    return ""


img_base64 = get_base64_of_bin_file("img/cs.jpg")

if img_base64:
  st.markdown(
      f"""
        <style>
        header[data-testid="stHeader"], footer {{
            display: none !important;
        }}

        .stApp {{
            background-repeat: no-repeat;
            background-position: center center;
            background-attachment: fixed;
            background-size: cover;
        }}

        @media (prefers-color-scheme: light) {{
            .stApp {{
                background-image: 
                    linear-gradient(rgba(255, 255, 255, 0.88), rgba(255, 255, 255, 0.88)), 
                    url("data:image/jpg;base64,{img_base64}");
            }}
        }}

        @media (prefers-color-scheme: dark) {{
            .stApp {{
                background-image: 
                    linear-gradient(rgba(14, 17, 23, 0.85), rgba(14, 17, 23, 0.85)), 
                    url("data:image/jpg;base64,{img_base64}");
            }}
        }}
        </style>
    """,
      unsafe_allow_html=True,
  )

# Inizializzazione DB con WAL mode attiva
init_db()

if "utente_loggato" not in st.session_state:
  st.session_state["utente_loggato"] = None

if "ip_zebra" not in st.session_state:
  st.session_state["ip_zebra"] = "192.168.1.150"

# SCHERMATA DI LOGIN
if st.session_state["utente_loggato"] is None:
  st.markdown("<br><br><br>", unsafe_allow_html=True)
  c_left, c_login, c_right = st.columns([1, 1.5, 1])

  with c_login:
    with st.container(border=True):
      st.markdown(
          "<h3 style='text-align: center;'>🔐 Accesso Sistema</h3>",
          unsafe_allow_html=True,
      )
      st.markdown(
          "<p style='text-align: center; color: gray;'>Inserisci le tue"
          " credenziali per accedere</p>",
          unsafe_allow_html=True,
      )
      st.markdown("---")

      with st.form("form_login"):
        username = st.text_input("Username").strip()
        password = st.text_input("Password", type="password")
        st.markdown("<br>", unsafe_allow_html=True)
        btn_login = st.form_submit_button(
            "Accedi al Sistema", type="primary", use_container_width=True
        )

        if btn_login:
          ok, user_data = autentica_utente(username, password)
          if ok:
            st.session_state["utente_loggato"] = user_data
            st.success(f"Benvenuto {user_data['nome']}!")
            st.rerun()
          else:
            st.error("❌ Credenziali errate o utente disattivato.")

      st.caption("💡 Credenziali predefinite: **admin** / **admin123**")
  st.stop()


# MODALI (POPUP)
@st.dialog("⚙️ Gestione Sistema & Utenti (Admin)", width="large")
def modal_admin_settings():
  tab_usr, tab_ip = st.tabs(["👤 Gestione Utenti", "🖨️ Stampante Zebra"])

  with tab_usr:
    st.subheader("➕ Crea Nuovo Utente")
    with st.form("form_crea_usr"):
      c_f1, c_f2 = st.columns(2)
      with c_f1:
        nu_user = st.text_input("Username").strip().lower()
        nu_nome = st.text_input("Nome Completo")
      with c_f2:
        nu_pwd = st.text_input("Password", type="password")
        nu_ruolo = st.selectbox("Ruolo", ["OPERATORE", "QUALITA", "ADMIN"])
      if st.form_submit_button("Crea Utente", type="primary"):
        if nu_user and nu_nome and nu_pwd:
          ok, msg = crea_utente(nu_user, nu_pwd, nu_nome, nu_ruolo)
          if ok:
            st.success(msg)
            st.rerun()
          else:
            st.error(msg)
        else:
          st.warning("Compilare tutti i campi.")

    st.markdown("---")
    st.subheader("📋 Gestione Account Esistenti")

    conn = get_connection()
    utenti_list = conn.execute(
        "SELECT username, nome_completo, ruolo, attivo FROM utenti"
    ).fetchall()
    conn.close()

    usr_corrente = st.session_state["utente_loggato"]["username"]

    c_u1, c_u2, c_u3, c_u4, c_u5, c_u6 = st.columns([1.5, 2, 1.2, 1, 1.2, 1.2])
    c_u1.markdown("**Username**")
    c_u2.markdown("**Nome**")
    c_u3.markdown("**Ruolo**")
    c_u4.markdown("**Stato**")
    c_u5.markdown("**Sospensione**")
    c_u6.markdown("**Elimina**")
    st.markdown("---")

    for u_row in utenti_list:
      u_name = u_row["username"]
      u_fullname = u_row["nome_completo"]
      u_role = u_row["ruolo"]
      u_active = bool(u_row["attivo"])

      col1, col2, col3, col4, col5, col6 = st.columns(
          [1.5, 2, 1.2, 1, 1.2, 1.2]
      )
      col1.write(f"`{u_name}`")
      col2.write(u_fullname)
      col3.write(u_role)

      if u_active:
        col4.markdown("🟢 **Attivo**")
      else:
        col4.markdown("🔴 **Sospeso**")

      is_self = u_name == usr_corrente
      is_main_admin = u_name == "admin"

      btn_label = "🔒 Sospendi" if u_active else "🔓 Attiva"
      if col5.button(
          btn_label, key=f"btn_susp_{u_name}", disabled=(is_self or is_main_admin)
      ):
        ok, msg = cambia_stato_utente(u_name, not u_active)
        if ok:
          st.success(msg)
          st.rerun()
        else:
          st.error(msg)

      if col6.button(
          "🗑️ Elimina",
          key=f"btn_del_{u_name}",
          type="secondary",
          disabled=(is_self or is_main_admin),
      ):
        ok, msg = elimina_utente(u_name, usr_corrente)
        if ok:
          st.success(msg)
          st.rerun()
        else:
          st.error(msg)

    st.markdown("---")
    st.subheader("🔑 Reset Password Utente")
    c_r1, c_r2, c_r3 = st.columns([2, 2, 1])
    usr_options = [u["username"] for u in utenti_list]
    usr_reset = c_r1.selectbox("Seleziona Utente:", usr_options)
    pwd_nuova = c_r2.text_input("Nuova Password:", type="password")
    if c_r3.button("Aggiorna Password", use_container_width=True):
      if pwd_nuova:
        ok, msg = reset_password_utente(usr_reset, pwd_nuova)
        if ok:
          st.success(msg)
        else:
          st.error(msg)

  with tab_ip:
    st.subheader("🖨️ IP Stampante Zebra")
    ip_in = st.text_input(
        "IP Stampante:", value=st.session_state.get("ip_zebra", "192.168.1.150")
    )
    if st.button("Salva IP Stampante", type="primary"):
      st.session_state["ip_zebra"] = ip_in.strip()
      st.success("✅ IP aggiornato!")


# MODALE CREA COMMESSA SCHEDE
@st.dialog("➕ Crea Nuova Commessa Schede", width="large")
def modal_crea_commessa_schede():
  nuova_commessa = st.text_input(
      "Codice Commessa Schede (es. LOTTO-SCHEDE-01)"
  ).upper()

  codici_noti = get_lista_codici_schede_noti()
  opzioni_codice = codici_noti + ["➕ Inserisci nuovo codice..."]

  scelta_cod = st.selectbox(
      "Codice Scheda Previsto per questa Commessa:", options=opzioni_codice
  )

  if scelta_cod == "➕ Inserisci nuovo codice...":
    codice_scheda_atteso = (
        st.text_input("Digitare Nuovo Codice Scheda (es. SE.0176965.F-1-T):")
        .strip()
        .upper()
    )
  else:
    codice_scheda_atteso = scelta_cod

  cliente_commessa = st.text_input("Fornitore / Note")
  qta_commessa = st.number_input(
      "Quantità Schede Previste", min_value=1, value=1, step=1
  )
  note_commessa = st.text_area("Note", height=68)

  if st.button(
      "Salva Commessa Schede", type="primary", use_container_width=True
  ):
    if nuova_commessa and codice_scheda_atteso:
      conn = get_connection()
      try:
        conn.execute(
            "INSERT INTO commesse (codice_commessa, cliente, quantita,"
            " codice_scheda_atteso, note) VALUES (?, ?, ?, ?, ?)",
            (
                nuova_commessa,
                cliente_commessa,
                qta_commessa,
                codice_scheda_atteso,
                note_commessa,
            ),
        )
        conn.commit()
        st.success(
            f"Commessa {nuova_commessa} creata con successo! (Codice Vincolato:"
            f" {codice_scheda_atteso})"
        )
        st.cache_data.clear()
        st.rerun()
      except Exception as e:
        st.error(f"Errore nella creazione: {e}")
      finally:
        conn.close()
    else:
      st.warning(
          "Inserire il codice della commessa e specificare il codice scheda"
          " atteso."
      )


@st.dialog("🗑 Elimina Commessa Schede", width="large")
def modal_elimina_commessa_schede(commesse_df):
  if commesse_df.empty:
    st.info("Nessuna commessa presente.")
  else:
    comm_da_del = st.selectbox(
        "Seleziona da eliminare:",
        options=commesse_df["codice_commessa"].tolist(),
        key="del_comm_schede",
    )
    if st.button(
        "Conferma Eliminazione", type="secondary", use_container_width=True
    ):
      ok, msg = elimina_commessa_schede(comm_da_del)
      if ok:
        st.success(msg)
        st.rerun()
      else:
        st.error(msg)


# MODALI BOM
@st.dialog("📥 Importa File BOM (CSV / Excel)", width="large")
def modal_importa_bom():
  if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

  file_caricato = st.file_uploader(
      "Carica file BOM (.csv, .xlsx, .xls)",
      type=["csv", "xlsx", "xls"],
      key=f"file_uploader_{st.session_state.uploader_key}",
  )

  if file_caricato is not None:
    try:
      if file_caricato.name.endswith(".csv"):
        df_raw = pd.read_csv(
            file_caricato, sep=None, engine="python", header=None
        )
      else:
        df_raw = pd.read_excel(file_caricato, header=None)

      st.write("Anteprima dati rilevati:")
      st.dataframe(df_raw.head(10), use_container_width=True, hide_index=True)

      if st.button(
          "🚀 Importa / Aggiorna tutte le BOM",
          type="primary",
          use_container_width=True,
      ):
        success_count = 0
        for idx, row in df_raw.iterrows():
          celle = [
              str(val).strip().upper()
              for val in row
              if pd.notna(val) and str(val).strip() != ""
          ]
          if len(celle) >= 2:
            modello = celle[0]
            schede = celle[1:]
            ok, _ = salva_bom_modello(modello, schede)
            if ok:
              success_count += 1
        st.session_state.uploader_key += 1
        st.success(f"✅ Configurate/aggiornate {success_count} BOM.")
        st.rerun()
    except Exception as e:
      st.error(f"Errore nella lettura del file: {e}")


@st.dialog("➕ Inserisci/Modifica Singolo Modello BOM", width="large")
def modal_singola_bom():
  modello_bom = st.text_input(
      "Nome Modello Centralina", placeholder="es. VCU_480"
  ).upper()
  num_componenti = st.number_input(
      "Numero schede richieste (1-8)", min_value=1, max_value=8, value=2
  )

  codici_attesi = []
  c1, c2 = st.columns(2)
  for i in range(num_componenti):
    target_col = c1 if i % 2 == 0 else c2
    code = target_col.text_input(
        f"Codice Scheda #{i+1} richiesto", key=f"bom_code_{i}"
    ).upper()
    if code:
      codici_attesi.append(code)

  if st.button("Salva Singola BOM", type="primary", use_container_width=True):
    if modello_bom and len(codici_attesi) == num_componenti:
      ok, msg = salva_bom_modello(modello_bom, codici_attesi)
      if ok:
        st.success(msg)
        st.rerun()
      else:
        st.error(msg)
    else:
      st.warning("Compilare il modello e tutti i codici scheda attesi.")


@st.dialog("🗑️ Elimina BOM Modello", width="large")
def modal_elimina_bom():
  conn = get_connection()
  modelli_esistenti = [
      row[0]
      for row in conn.execute(
          "SELECT DISTINCT modello FROM bom ORDER BY modello"
      ).fetchall()
  ]
  conn.close()

  if modelli_esistenti:
    modello_da_eliminare = st.selectbox(
        "Seleziona Modello da rimuovere:", options=modelli_esistenti
    )
    if st.button(
        "Conferma Eliminazione BOM", type="secondary", use_container_width=True
    ):
      ok, msg = elimina_bom_modello(modello_da_eliminare)
      if ok:
        st.success(msg)
        st.rerun()
      else:
        st.error(msg)
  else:
    st.info("Nessuna BOM presente.")


# MODALI COMMESSE CENTRALINE
@st.dialog("➕ Nuova Commessa Centralina", width="large")
def modal_crea_commessa_centralina(df_modelli_bom):
  cod_comm_cent = st.text_input("Codice Commessa (es. ORD-2026-VCU01)").upper()
  modello_cent = st.selectbox(
      "Modello Centralina:",
      options=(
          df_modelli_bom["modello"].tolist()
          if not df_modelli_bom.empty
          else []
      ),
      key="select_mod_nuova_comm",
  )

  c_qta, c_mat = st.columns([1, 1])
  with c_qta:
    qta_cent = st.number_input("Quantità Pezzi", min_value=1, value=10, step=1)
  with c_mat:
    _, prog_suggerito = (
        genera_prossimo_seriale_modello(modello_cent)
        if modello_cent
        else ("", 1)
    )
    usa_mat_custom = st.checkbox(
        "Personalizza matricola di partenza", value=False
    )
    if usa_mat_custom:
      mat_inizio = st.number_input(
          "Matricola da cui iniziare",
          min_value=1,
          value=int(prog_suggerito),
          step=1,
      )
    else:
      mat_inizio = None

  cliente_cent = st.text_input("Cliente / Note")

  if st.button(
      "Salva Nuova Commessa Centralina",
      type="primary",
      use_container_width=True,
  ):
    if cod_comm_cent and modello_cent:
      ok, msg = crea_commessa_centralina(
          cod_comm_cent,
          modello_cent,
          qta_cent,
          cliente_cent,
          "",
          matricola_inizio=mat_inizio,
      )
      if ok:
        st.success(msg)
        st.rerun()
      else:
        st.error(msg)
    else:
      st.warning("Compilare il codice commessa e selezionare il modello.")


@st.dialog("🗑️ Elimina Commessa Centralina", width="large")
def modal_elimina_commessa_centralina(df_comm_cent):
  if df_comm_cent.empty:
    st.info("Nessuna commessa centralina presente.")
  else:
    comm_cent_del = st.selectbox(
        "Seleziona da eliminare:",
        options=df_comm_cent["codice_commessa"].tolist(),
        key="del_comm_cent",
    )
    if st.button(
        "Conferma Eliminazione", type="secondary", use_container_width=True
    ):
      ok, msg = elimina_commessa_centralina(comm_cent_del)
      if ok:
        st.success(msg)
        st.rerun()
      else:
        st.error(msg)


# MODALI AVANZAMENTO & REWORK
@st.dialog("⚡ Avanzamento Fase Centralina", width="large")
def modal_avanzamento_fase(fasi_disponibili, utente_act):
  seriale_inserito = st.text_input(
      "Seriale Centralina:",
      key="campo_seriale_fase",
      placeholder="Inserisci o spara il seriale...",
  ).strip()

  fase_destinazione = st.selectbox(
      "Seleziona Nuova Fase:", options=fasi_disponibili
  )

  obbligo_nota = fase_destinazione == "IN_RIPARAZIONE"
  label_nota = (
      "Note / Descrizione Anomalia (OBBLIGATORIA per IN_RIPARAZIONE):"
      if obbligo_nota
      else "Note (Opzionale):"
  )

  note_fase = st.text_input(
      label_nota,
      key="note_cambio_fase",
      placeholder=(
          "Descrivi il motivo..." if obbligo_nota else "Es. Esito OK, note"
          " collaudo..."
      ),
  )

  if st.button(
      "🔄 Conferma Cambio Fase", type="primary", use_container_width=True
  ):
    if not seriale_inserito:
      st.warning("⚠️ Inserire un seriale valido prima di confermare.")
    elif obbligo_nota and not note_fase.strip():
      st.error(
          "❌ La descrizione dell'anomalia è OBBLIGATORIA per spostare la"
          " centralina 'IN_RIPARAZIONE'!"
      )
    else:
      ok, msg = aggiorna_fase_centralina(
          seriale_inserito, fase_destinazione, note=note_fase, utente=utente_act
      )
      if ok:
        st.success(msg)
        st.rerun()
      else:
        st.error(msg)


@st.dialog("🛠️ Sostituzione Scheda KO su Centralina", width="large")
def modal_sostituzione_scheda(utente_act):
  seriale_ko = st.text_input(
      "Seriale Centralina da Riparare:", key="seriale_rework"
  ).strip()

  conn = get_connection()
  schede_mag = pd.read_sql(
      "SELECT qr_raw, codice_scheda FROM schede WHERE stato = 'MAGAZZINO'", conn
  )
  conn.close()

  if seriale_ko:
    conn = get_connection()
    schede_montate = pd.read_sql(
        """
            SELECT cs.posiz_scheda, cs.qr_scheda, s.codice_scheda 
            FROM centralina_schede cs
            JOIN schede s ON cs.qr_scheda = s.qr_raw
            WHERE cs.seriale_centralina = ?
        """,
        conn,
        params=(seriale_ko,),
    )
    conn.close()

    if not schede_montate.empty:
      opp = [
          f"Pos {r['posiz_scheda']}: {r['codice_scheda']} ({r['qr_scheda']})"
          for _, r in schede_montate.iterrows()
      ]
      scelta_pos = st.selectbox(
          "Seleziona Scheda KO da Rimuovere:", options=opp
      )
      pos_num = int(scelta_pos.split(":")[0].replace("Pos ", ""))

      motivo_ko_input = st.text_input(
          "Motivo / Difetto Rilevato (OBBLIGATORIO):",
          key="motivo_ko_txt",
          placeholder="Es. Componente U3 bruciato",
      )
      nuovo_qr_sost = st.text_input(
          "Spara QR Nuova Scheda Sostitutiva (da Magazzino):",
          key="qr_sost_input",
      ).strip()

      if st.button(
          "🔄 Sostituisci Scheda KO", type="primary", use_container_width=True
      ):
        if not motivo_ko_input.strip():
          st.error("❌ Inserire obbligatoriamente il motivo del guasto.")
        elif not nuovo_qr_sost:
          st.warning("⚠ Inserire o sparare il QR della nuova scheda.")
        else:
          parsed_in = parse_qr_scheda(nuovo_qr_sost)
          valore_da_cercare = (
              parsed_in["qr_raw"] if parsed_in else nuovo_qr_sost
          ).strip().upper()

          qr_effettivo = None
          for _, row_mag in schede_mag.iterrows():
            qr_raw_db = str(row_mag["qr_raw"]).strip().upper()
            cod_db = str(row_mag["codice_scheda"]).strip().upper()
            if (
                valore_da_cercare == qr_raw_db
                or valore_da_cercare == cod_db
                or valore_da_cercare in qr_raw_db
            ):
              qr_effettivo = row_mag["qr_raw"]
              break

          if qr_effettivo:
            ok, msg = sostituisci_scheda_centralina(
                seriale_ko, pos_num, qr_effettivo, utente=utente_act
            )
            if ok:
              conn_rip = get_connection()
              conn_rip.execute(
                  """
                                INSERT INTO riparazioni_schede (qr_scheda, seriale_centralina, motivo_ko, esito, utente)
                                VALUES (?, ?, ?, 'IN_RIPARAZIONE', ?)
                            """,
                  (
                      scelta_pos.split("(")[1].replace(")", ""),
                      seriale_ko,
                      motivo_ko_input,
                      utente_act,
                  ),
              )
              conn_rip.commit()
              conn_rip.close()

              st.success(f"{msg} | Nota Guasto Registrata.")
              st.rerun()
            else:
              st.error(msg)
          else:
            st.error(
                f"❌ La scheda '{nuovo_qr_sost}' non risulta disponibile in"
                " Magazzino."
            )
    else:
      st.warning("Nessuna centralina trovata con questo seriale.")


@st.dialog("🔄 Rientro Scheda Riparata dal Laboratorio", width="large")
def modal_rientro_riparazione(utente_act):
  conn = get_connection()
  schede_in_rip = pd.read_sql(
      "SELECT qr_raw, codice_scheda FROM schede WHERE stato = 'IN_RIPARAZIONE'",
      conn,
  )
  conn.close()

  if not schede_in_rip.empty:
    scheda_rip_sel = st.selectbox(
        "Scheda In Riparazione:", options=schede_in_rip["qr_raw"].tolist()
    )
    desc_intervento = st.text_input(
        "Descrizione Intervento Svolta (OBBLIGATORIO):",
        placeholder="Es. Sostituito C12 e ripassate saldature",
    )
    esito_rip = st.radio(
        "Esito Intervento:", ["MAGAZZINO", "SCARTO_DEFINITIVO"], horizontal=True
    )

    if st.button(
        "Conferma Rientro Riparazione",
        type="primary",
        use_container_width=True,
    ):
      if not desc_intervento.strip():
        st.error("❌ La descrizione dell'intervento è obbligatoria.")
      else:
        ok, msg = ripristina_scheda_riparata(scheda_rip_sel, esito_rip)
        if ok:
          conn_rip = get_connection()
          conn_rip.execute(
              """
                        UPDATE riparazioni_schede 
                        SET intervento_riparazione = ?, esito = ?, utente = ?
                        WHERE qr_scheda = ? AND esito = 'IN_RIPARAZIONE'
                    """,
              (desc_intervento, esito_rip, utente_act, scheda_rip_sel),
          )
          conn_rip.commit()
          conn_rip.close()

          st.success(msg)
          st.rerun()
        else:
          st.error(msg)
  else:
    st.info("Nessuna scheda attualmente in riparazione.")


# INTESTAZIONE
col_titolo, col_utente = st.columns([2.3, 1.2])

with col_titolo:
  st.title("⚙️ Gestionale MMRM")

with col_utente:
  u = st.session_state["utente_loggato"]
  c_info, c_admin, c_out = st.columns([1.5, 1, 1])

  with c_info:
    st.markdown(f"👤 **{u['nome']}**\n`{u['ruolo']}`")

  with c_admin:
    if u["ruolo"] == "ADMIN":
      if st.button("⚙️ Impostazioni", use_container_width=True):
        modal_admin_settings()

  with c_out:
    if st.button("🚪 Esci", use_container_width=True):
      st.session_state["utente_loggato"] = None
      st.rerun()

st.markdown("---")


# DEFINIZIONE DINAMICA TAB
ruolo = u["ruolo"]

if ruolo == "OPERATORE":
  mappa_tabs = {
      "📦 1. Commesse Schede": "tab_commesse",
      "🏭 2. Magazzino": "tab_magazzino",
      "🛠 3. Assemblaggio": "tab_assemblaggio",
      "🔍 4. Tracciabilità": "tab_tracciabilita",
  }
elif ruolo == "QUALITA":
  mappa_tabs = {
      "🔍 1. Tracciabilità": "tab_tracciabilita",
      "📊 2. Avanzamento & Rework": "tab_avanzamento",
      "📈 3. Dashboard & Report PDF": "tab_dashboard",
  }
else:  # ADMIN
  mappa_tabs = {
      "📦 1. Commesse Schede": "tab_commesse",
      "🏭 2. Magazzino": "tab_magazzino",
      "📋 3. Configurazione BOM": "tab_bom",
      "🛠 4. Assemblaggio": "tab_assemblaggio",
      "📊 5. Avanzamento & Rework": "tab_avanzamento",
      "📈 6. Dashboard & Report PDF": "tab_dashboard",
      "🔍 7. Tracciabilità": "tab_tracciabilita",
  }

lista_nomi_tab = list(mappa_tabs.keys())
tabs_oggetti = st.tabs(lista_nomi_tab)
tab_dict = {
    mappa_tabs[nome]: tabs_oggetti[i] for i, nome in enumerate(lista_nomi_tab)
}


# TAB: COMMESSE SCHEDE
if "tab_commesse" in tab_dict:
  with tab_dict["tab_commesse"]:
    st.header("📦 Gestione Commesse Schede e Ingresso")

    conn = get_connection()
    commesse_df = pd.read_sql(
        "SELECT codice_commessa, cliente, quantita, codice_scheda_atteso FROM"
        " commesse ORDER BY data_creazione DESC",
        conn,
    )
    conn.close()

    st.subheader("1. Gestione & Selezione Commessa Schede")
    btn_c1, btn_c2, _ = st.columns([1, 1, 2])
    with btn_c1:
      if st.button(
          "➕ Crea Nuova Commessa Schede",
          use_container_width=True,
          type="primary",
      ):
        modal_crea_commessa_schede()
    with btn_c2:
      if st.button("🗑️ Elimina Commessa Schede", use_container_width=True):
        modal_elimina_commessa_schede(commesse_df)

    st.markdown("<br>", unsafe_allow_html=True)

    if not commesse_df.empty:
      commesse_df["label"] = commesse_df.apply(
          lambda r: (
              f"{r['codice_commessa']} (Q.tà Max: {r['quantita']} | Codice:"
              f" {r['codice_scheda_atteso'] if pd.notna(r['codice_scheda_atteso']) else 'LIBERO'})"
          ),
          axis=1,
      )
      mappa_commesse = dict(
          zip(commesse_df["label"], commesse_df["codice_commessa"])
      )
      scelta_label = st.selectbox(
          "🎯 Seleziona Commessa Schede Operativa:",
          options=list(mappa_commesse.keys()),
      )
      commessa_selezionata = mappa_commesse[scelta_label]
    else:
      commessa_selezionata = None
      st.info(
          "Nessuna commessa schede a sistema. Creane una prima di proseguire."
      )

    st.markdown("---")

    if commessa_selezionata:
      conn = get_connection()
      row_comm = conn.execute(
          "SELECT quantita, codice_scheda_atteso FROM commesse WHERE"
          " codice_commessa = ?",
          (commessa_selezionata,),
      ).fetchone()
      qta_max_schede = row_comm[0]
      codice_atteso_commessa = row_comm[1]
      count_schede = conn.execute(
          "SELECT COUNT(*) FROM schede WHERE commessa = ?",
          (commessa_selezionata,),
      ).fetchone()[0]
      conn.close()

      col_ing, col_tab = st.columns([1, 2])

      with col_ing:
        st.subheader(f"2. Scansione Rapida Schede ({commessa_selezionata})")
        st.caption(
            f"📊 Schede Inserite: **{count_schede} / {qta_max_schede}**"
        )
        if codice_atteso_commessa:
          st.info(f"🎯 Codice Atteso: **{codice_atteso_commessa}**")

        if "last_msg_tab1" not in st.session_state:
          st.session_state["last_msg_tab1"] = None

        def registra_qr_automatico():
          qr_scansionato = st.session_state.campo_qr_raffica.strip()
          if qr_scansionato:
            conn_check = get_connection()
            c_inserite = conn_check.execute(
                "SELECT COUNT(*) FROM schede WHERE commessa = ?",
                (commessa_selezionata,),
            ).fetchone()[0]
            conn_check.close()

            if c_inserite >= qta_max_schede:
              st.session_state["last_msg_tab1"] = (
                  "error",
                  "❌ Limite commessa raggiunto!"
                  f" ({c_inserite}/{qta_max_schede} schede).",
              )
            else:
              parsed = parse_qr_scheda(qr_scansionato)
              if parsed:
                if (
                    codice_atteso_commessa
                    and parsed["codice"] != codice_atteso_commessa
                ):
                  st.session_state["last_msg_tab1"] = (
                      "error",
                      "❌ Codice non conforme! L'etichetta sparata è"
                      f" '{parsed['codice']}', la commessa richiede"
                      f" '{codice_atteso_commessa}'.",
                  )
                else:
                  ok, msg = inserisci_scheda(
                      parsed["qr_raw"],
                      commessa_selezionata,
                      parsed["codice"],
                      parsed["wwyy"],
                      parsed["prog"],
                  )
                  if ok:
                    st.session_state["last_msg_tab1"] = (
                        "success",
                        f"✅ Registrata: {parsed['codice']} (#{parsed['prog']})",
                    )
                  else:
                    st.session_state["last_msg_tab1"] = ("warning", f"⚠️ {msg}")
              else:
                st.session_state["last_msg_tab1"] = (
                    "error",
                    "❌ QR Code non valido!",
                )
          st.session_state.campo_qr_raffica = ""

        bloccato_ing = count_schede >= qta_max_schede
        if bloccato_ing:
          st.error(
              f"⚠️ Limite massimo raggiunto ({count_schede}/{qta_max_schede})."
          )

        st.text_input(
            "Spara il QR Code qui:",
            key="campo_qr_raffica",
            on_change=registra_qr_automatico,
            placeholder=(
                "In attesa della pistola QR..."
                if not bloccato_ing
                else "Lotto completo."
            ),
            disabled=bloccato_ing,
        )

        if st.session_state["last_msg_tab1"]:
          tipo, testo = st.session_state["last_msg_tab1"]
          if tipo == "success":
            st.success(testo)
          elif tipo == "warning":
            st.warning(testo)
          else:
            st.error(testo)

      with col_tab:
        st.subheader(
            f"📋 Schede Inserite in Commessa: {commessa_selezionata}"
        )
        conn = get_connection()
        query_schede = """
                    SELECT 
                        qr_raw,
                        codice_scheda AS "Codice Scheda", 
                        anno_settimana AS "Anno/Sett (WWYY)", 
                        progressivo AS "Progressivo", 
                        stato AS "Stato", 
                        data_ingresso AS "Data Ingresso" 
                    FROM schede 
                    WHERE commessa = ? 
                    ORDER BY data_ingresso DESC
                """
        df_schede = pd.read_sql(
            query_schede, conn, params=(commessa_selezionata,)
        )
        conn.close()

        st.metric("Totale Schede Inserite", len(df_schede))
        if not df_schede.empty:
          st.dataframe(
              df_schede.drop(columns=["qr_raw"]),
              use_container_width=True,
              height=280,
              hide_index=True,
          )

          st.markdown("---")
          with st.expander("🗑️ Rimuovi/Elimina una scheda inserita per errore"):
            opzioni_rimozione = df_schede.apply(
                lambda r: (
                    f"{r['Codice Scheda']} | Prog: {r['Progressivo']} | WWYY:"
                    f" {r['Anno/Sett (WWYY)']}"
                ),
                axis=1,
            ).tolist()

            scheda_sel_label = st.selectbox(
                "Seleziona la scheda da eliminare dalla commessa:",
                options=opzioni_rimozione,
            )
            if st.button(
                "🗑️ Elimina Scheda Selezionata",
                type="secondary",
                use_container_width=True,
            ):
              idx = opzioni_rimozione.index(scheda_sel_label)
              qr_da_del = df_schede.iloc[idx]["qr_raw"]

              ok, msg = elimina_scheda_singola(qr_da_del)
              if ok:
                st.success(msg)
                st.rerun()
              else:
                st.error(msg)
        else:
          st.info("Nessuna scheda ancora letta per questa commessa.")


# TAB MAGAZZINO
if "tab_magazzino" in tab_dict:
  with tab_dict["tab_magazzino"]:
    st.header("🏭 Giacenze Schede in Magazzino")
    conn = get_connection()
    tutte_commesse = [
        row[0]
        for row in conn.execute(
            "SELECT codice_commessa FROM commesse"
        ).fetchall()
    ]
    tutti_codici = [
        row[0]
        for row in conn.execute(
            "SELECT DISTINCT codice_scheda FROM schede"
        ).fetchall()
    ]

    query_giacenze = """
            SELECT 
                commessa AS "Commessa Schede", 
                codice_scheda AS "Codice Scheda", 
                data_ingresso AS "Data Ingresso" 
            FROM schede 
            WHERE stato = 'MAGAZZINO' 
            ORDER BY commessa, codice_scheda, data_ingresso DESC
        """
    df_giacenze = pd.read_sql(query_giacenze, conn)
    conn.close()

    c_f1, c_f2 = st.columns(2)
    with c_f1:
      f_commessa = st.multiselect(
          "Filtra per Commessa Schede", options=tutte_commesse
      )
    with c_f2:
      f_codice = st.multiselect(
          "Filtra per Codice Scheda", options=tutti_codici
      )

    df_filtrato = df_giacenze.copy()
    if f_commessa:
      df_filtrato = df_filtrato[
          df_filtrato["Commessa Schede"].isin(f_commessa)
      ]
    if f_codice:
      df_filtrato = df_filtrato[df_filtrato["Codice Scheda"].isin(f_codice)]

    st.metric("Totale Schede Disponibili a Magazzino", len(df_filtrato))
    if not df_filtrato.empty:
      st.dataframe(df_filtrato, use_container_width=True, hide_index=True)
    else:
      st.info("ℹ️ Nessuna scheda presente in magazzino.")


# TAB CONFIGURAZIONE BOM
if "tab_bom" in tab_dict:
  with tab_dict["tab_bom"]:
    st.header("📋 Configurazione Distinta Base (BOM Modelli)")

    btn_b1, btn_b2, btn_b3, _ = st.columns([1, 1, 1, 1])
    with btn_b1:
      if st.button(
          "📥 Importa File BOM", use_container_width=True, type="primary"
      ):
        modal_importa_bom()
    with btn_b2:
      if st.button(
          "➕ Inserisci/Modifica Singolo Modello", use_container_width=True
      ):
        modal_singola_bom()
    with btn_b3:
      if st.button("🗑️ Elimina BOM Modello", use_container_width=True):
        modal_elimina_bom()

    st.markdown("---")
    st.subheader("📋 BOM Attualmente Configurate a Sistema")

    conn = get_connection()
    df_bom_raw = pd.read_sql(
        "SELECT modello, posiz_scheda, codice_scheda_atteso FROM bom ORDER BY"
        " modello, posiz_scheda",
        conn,
    )
    conn.close()

    if not df_bom_raw.empty:
      pivoted = df_bom_raw.pivot(
          index="modello",
          columns="posiz_scheda",
          values="codice_scheda_atteso",
      )
      pivoted.columns = [f"Scheda {col}" for col in pivoted.columns]
      pivoted.reset_index(inplace=True)
      pivoted.rename(columns={"modello": "Modello Centralina"}, inplace=True)
      pivoted.fillna("", inplace=True)
      st.dataframe(pivoted, use_container_width=True, hide_index=True)
    else:
      st.info("ℹ️ Nessuna BOM ancora configurata.")


# TAB ASSEMBLAGGIO CENTRALINE
if "tab_assemblaggio" in tab_dict:
  with tab_dict["tab_assemblaggio"]:
    st.header("🛠️ Postazione Operativa Assemblaggio")

    conn = get_connection()
    df_modelli_bom = pd.read_sql(
        "SELECT DISTINCT modello FROM bom ORDER BY modello", conn
    )
    df_comm_cent = pd.read_sql(
        """
            SELECT codice_commessa, modello, quantita, matricola_inizio 
            FROM commesse_centraline 
            ORDER BY data_creazione DESC
        """,
        conn,
    )
    conn.close()

    btn_ac1, btn_ac2, _ = st.columns([1, 1, 2])
    with btn_ac1:
      if st.button(
          "➕ Nuova Commessa Centralina",
          use_container_width=True,
          type="primary",
      ):
        modal_crea_commessa_centralina(df_modelli_bom)
    with btn_ac2:
      if st.button("🗑️ Elimina Commessa Centralina", use_container_width=True):
        modal_elimina_commessa_centralina(df_comm_cent)

    st.markdown("<br>", unsafe_allow_html=True)

    if df_modelli_bom.empty:
      st.warning(
          "⚠ Per poter creare commesse ed assemblare, configura prima le BOM."
      )
    else:
      if not df_comm_cent.empty:
        df_comm_cent["label"] = df_comm_cent.apply(
            lambda r: (
                f"{r['codice_commessa']} | Modello: {r['modello']} (Tot:"
                f" {r['quantita']} pz)"
            ),
            axis=1,
        )
        mappa_comm_cent = dict(
            zip(df_comm_cent["label"], df_comm_cent["codice_commessa"])
        )

        scelta_comm_label = st.selectbox(
            "🎯 Seleziona Commessa:", options=list(mappa_comm_cent.keys())
        )
        commessa_cent_selezionata = mappa_comm_cent[scelta_comm_label]

        # Reset session buffer se viene cambiata la commessa selezionata
        if (
            st.session_state.get("commessa_attiva_last")
            != commessa_cent_selezionata
        ):
          st.session_state["schede_scansionate_correnti"] = []
          st.session_state["commessa_attiva_last"] = commessa_cent_selezionata

        info_comm = df_comm_cent[
            df_comm_cent["codice_commessa"] == commessa_cent_selezionata
        ].iloc[0]
        modello_ass = info_comm["modello"]
        qta_totale = info_comm["quantita"]
        matricola_custom = info_comm["matricola_inizio"]
      else:
        commessa_cent_selezionata = None
        st.info("Nessuna commessa di produzione attiva.")

      st.markdown("---")

      if commessa_cent_selezionata:
        bom_attesa = get_bom_modello(modello_ass)

        if not bom_attesa:
          st.error(f"❌ BOM per il modello '{modello_ass}' non trovata.")
        else:
          conn = get_connection()
          assemblate_count = conn.execute(
              "SELECT COUNT(*) FROM centraline WHERE commessa = ?",
              (commessa_cent_selezionata,),
          ).fetchone()[0]
          conn.close()

          limite_raggiunto = assemblate_count >= qta_totale
          pezzo_attuale = min(assemblate_count + 1, qta_totale)

          if pd.notna(matricola_custom) and matricola_custom is not None:
            prog_num = int(matricola_custom) + assemblate_count
          else:
            _, prog_num = genera_prossimo_seriale_modello(modello_ass)

          prossimo_seriale = f"{modello_ass}-{prog_num:05d}"

          m1, m2, m3 = st.columns([1, 1, 1])
          m1.metric("📦 Pezzo Corrente", f"{assemblate_count} di {qta_totale}")
          m2.metric(
              "🏷️ Seriale In Assegnazione",
              f"{prog_num:05d}" if not limite_raggiunto else "COMPLETATO",
          )
          m3.metric("🧩 Schede per Centralina", f"{len(bom_attesa)} Componenti")

          st.progress(min(assemblate_count / qta_totale, 1.0))

          if limite_raggiunto:
            st.error(
                "⚠️ Quantità massima prevista per questa commessa raggiunta"
                f" ({assemblate_count}/{qta_totale})."
            )
          else:
            st.subheader("⚡ Scansione Componenti")

            if "schede_scansionate_correnti" not in st.session_state:
              st.session_state["schede_scansionate_correnti"] = []

            conn = get_connection()
            df_disponibili = pd.read_sql(
                "SELECT qr_raw, codice_scheda FROM schede WHERE stato ="
                " 'MAGAZZINO'",
                conn,
            )
            conn.close()
            dict_magazzino = dict(
                zip(df_disponibili["qr_raw"], df_disponibili["codice_scheda"])
            )

            def processa_scansione_singola():
              qr_scanned = st.session_state.campo_scansione_unica.strip()
              if qr_scanned:
                attuali_qr = [
                    item["qr"]
                    for item in st.session_state["schede_scansionate_correnti"]
                ]

                if qr_scanned in attuali_qr:
                  st.toast(
                      "⚠️ Scheda già scansionata per questa centralina!",
                      icon="⚠️",
                  )
                elif qr_scanned not in dict_magazzino:
                  st.toast("❌ Scheda non presente in magazzino!", icon="❌")
                else:
                  codice_magazzino = dict_magazzino[qr_scanned]
                  codici_gia_presenti = [
                      item["codice"]
                      for item in st.session_state[
                          "schede_scansionate_correnti"
                      ]
                  ]
                  codici_bom_rimanenti = list(bom_attesa)

                  for c_pres in codici_gia_presenti:
                    for c_req in list(codici_bom_rimanenti):
                      if c_pres == c_req or c_pres.startswith(c_req):
                        codici_bom_rimanenti.remove(c_req)
                        break

                  trovato = False
                  for cod_req in codici_bom_rimanenti:
                    if codice_magazzino == cod_req or codice_magazzino.startswith(
                        cod_req
                    ):
                      trovato = True
                      break

                  if trovato:
                    st.session_state["schede_scansionate_correnti"].append({
                        "qr": qr_scanned,
                        "codice": codice_magazzino,
                    })
                    st.toast(f"✅ Acquisita: {codice_magazzino}", icon="✅")
                  else:
                    st.toast(
                        "❌ Componente non previsto nella BOM"
                        f" ({codice_magazzino})",
                        icon="❌",
                    )

              st.session_state.campo_scansione_unica = ""

            col_input, col_status = st.columns([1.2, 1])

            with col_input:
              st.text_input(
                  "Spara QR Code Scheda:",
                  key="campo_scansione_unica",
                  on_change=processa_scansione_singola,
                  placeholder="Posiziona il cursore qui e spara...",
                  disabled=(
                      len(st.session_state["schede_scansionate_correnti"])
                      == len(bom_attesa)
                  ),
              )
              st.caption(
                  "⚡ Mantiene il focus: puoi sparare tutte le schede in"
                  " sequenza."
              )

              if st.session_state["schede_scansionate_correnti"]:
                if st.button(
                    "🔄 Annulla scansioni pezzo corrente", type="secondary"
                ):
                  st.session_state["schede_scansionate_correnti"] = []
                  st.rerun()

            with col_status:
              st.markdown("##### 📋 Stato Schede BOM")
              codici_inseriti = [
                  item["codice"]
                  for item in st.session_state["schede_scansionate_correnti"]
              ]
              temp_inseriti = list(codici_inseriti)

              for cod_req in bom_attesa:
                mancante = True
                for c_ins in list(temp_inseriti):
                  if c_ins == cod_req or c_ins.startswith(cod_req):
                    mancante = False
                    temp_inseriti.remove(c_ins)
                    break

                if not mancante:
                  st.success(f"✅ {cod_req}")
                else:
                  st.info(f"⏳ In attesa: {cod_req}")

            st.markdown("---")

            qr_scansionati = [
                item["qr"]
                for item in st.session_state["schede_scansionate_correnti"]
            ]
            if len(qr_scansionati) == len(bom_attesa):
              st.success(
                  "🎉 **Centralina Completata!** Pronta per la registrazione e"
                  " la stampa."
              )

              c_act1, c_act2 = st.columns([1, 1])

              with c_act1:
                png_bytes = genera_immagine_etichetta(
                    prossimo_seriale, modello_ass, commessa_cent_selezionata
                )
                zpl_code = genera_zpl_centralina(
                    prossimo_seriale, modello_ass, commessa_cent_selezionata
                )
                st.image(
                    png_bytes, caption="Anteprima Etichetta Stampa", width=280
                )

              with c_act2:
                if st.button(
                    "💾 Conferma & Stampa Subito",
                    type="primary",
                    use_container_width=True,
                ):
                  ok, msg = registra_assemblaggio(
                      prossimo_seriale,
                      modello_ass,
                      commessa_cent_selezionata,
                      prog_num,
                      qr_scansionati,
                      utente=u["username"],
                  )
                  if ok:
                    invia_zpl_a_stampante(
                        zpl_code, st.session_state["ip_zebra"]
                    )
                    st.session_state["schede_scansionate_correnti"] = []
                    st.success("✅ Centralina salvata con successo!")
                    st.rerun()
                  else:
                    st.error(msg)


# TAB AVANZAMENTO & REWORK
if "tab_avanzamento" in tab_dict:
  with tab_dict["tab_avanzamento"]:
    st.header("📊 Monitoraggio, Avanzamento Fasi & Rework")

    FASI_DISPONIBILI = [
        "Assemblaggio",
        "I collaudo",
        "Resinatura",
        "Calibrazione",
        "Burn-In",
        "II collaudo",
        "Spedita",
        "IN_RIPARAZIONE",
    ]

    btn_f1, btn_f2, btn_f3, _ = st.columns([1, 1, 1, 1])
    with btn_f1:
      if st.button(
          "⚡ Avanzamento Fase", use_container_width=True, type="primary"
      ):
        modal_avanzamento_fase(FASI_DISPONIBILI, u["username"])
    with btn_f2:
      if st.button("🛠️ Sostituisci Scheda KO", use_container_width=True):
        modal_sostituzione_scheda(u["username"])
    with btn_f3:
      if st.button("🔄 Rientro da Laboratorio", use_container_width=True):
        modal_rientro_riparazione(u["username"])

    st.markdown("---")
    st.subheader("📋 Registro Avanzamento Centraline")

    conn = get_connection()
    df_avanzamento = pd.read_sql(
        """
            SELECT 
                c.seriale_centralina AS "Seriale Centralina",
                c.modello AS "Modello",
                c.commessa AS "Commessa",
                c.fase_attuale AS "Fase Attuale",
                c.utente_assemblaggio AS "Operatore",
                c.data_assemblaggio AS "Data Creazione"
            FROM centraline c
            ORDER BY c.data_assemblaggio DESC
        """,
        conn,
    )
    conn.close()

    if not df_avanzamento.empty:
      mostra_spedite = st.checkbox(
          "Mostra anche centraline già Spedite", value=False
      )
      df_display = df_avanzamento.copy()
      if not mostra_spedite:
        df_display = df_display[df_display["Fase Attuale"] != "Spedita"]

      f_col1, f_col2 = st.columns(2)
      with f_col1:
        filtro_fase = st.multiselect(
            "Filtra per Fase:", options=FASI_DISPONIBILI
        )
      with f_col2:
        filtro_comm = st.multiselect(
            "Filtra per Commessa:", options=df_display["Commessa"].unique()
        )

      if filtro_fase:
        df_display = df_display[df_display["Fase Attuale"].isin(filtro_fase)]
      if filtro_comm:
        df_display = df_display[df_display["Commessa"].isin(filtro_comm)]

      st.metric("Centraline Visualizzate", len(df_display))
      st.dataframe(
          df_display, use_container_width=True, height=350, hide_index=True
      )
    else:
      st.info("ℹ️ Nessuna centralina a sistema.")


# TAB DASHBOARD & REPORT PDF
if "tab_dashboard" in tab_dict:
  with tab_dict["tab_dashboard"]:
    st.header("📈 Dashboard Analytics & Reportistica Tracciabilità")

    tab_dash, tab_pdf = st.tabs([
        "📊 KPI & Statistiche Produzione",
        "📄 Generazione Report PDF Centralina",
    ])

    with tab_dash:
      conn = get_connection()
      tot_comm_cent = conn.execute(
          "SELECT COUNT(*) FROM commesse_centraline"
      ).fetchone()[0]
      tot_centraline = conn.execute(
          "SELECT COUNT(*) FROM centraline"
      ).fetchone()[0]
      tot_spedite = conn.execute(
          "SELECT COUNT(*) FROM centraline WHERE fase_attuale = 'Spedita'"
      ).fetchone()[0]
      tot_in_rip = conn.execute(
          "SELECT COUNT(*) FROM centraline WHERE fase_attuale ='IN_RIPARAZIONE'"
      ).fetchone()[0]
      conn.close()

      k1, k2, k3, k4 = st.columns(4)
      k1.metric("Commesse Centraline", tot_comm_cent)
      k2.metric("Centraline Prodotte", tot_centraline)
      k3.metric("Centraline Spedite", tot_spedite)
      k4.metric("In Riparazione ⚠", tot_in_rip)

      st.markdown("---")
      st.subheader("📊 Distribuzione Fasi Centraline")

      conn = get_connection()
      df_fasi_chart = pd.read_sql(
          "SELECT fase_attuale, COUNT(*) as quantita FROM centraline GROUP BY"
          " fase_attuale",
          conn,
      )
      conn.close()

      if not df_fasi_chart.empty:
        st.bar_chart(df_fasi_chart.set_index("fase_attuale"))
      else:
        st.info("Nessun dato disponibile per il grafico.")

    with tab_pdf:
      st.subheader("📄 Certificato e Report Completo Storico Centralina")

      conn = get_connection()
      lista_seriali = [
          r[0]
          for r in conn.execute(
              "SELECT seriale_centralina FROM centraline ORDER BY"
              " seriale_centralina DESC"
          ).fetchall()
      ]
      conn.close()

      if lista_seriali:
        seriale_pdf_sel = st.selectbox(
            "Seleziona Centralina per la Generazione Report:",
            options=lista_seriali,
        )

        conn = get_connection()
        info_c = pd.read_sql(
            "SELECT * FROM centraline WHERE seriale_centralina = ?",
            conn,
            params=(seriale_pdf_sel,),
        ).iloc[0]
        info_schede = pd.read_sql(
            """
                    SELECT cs.posiz_scheda, s.qr_raw, s.codice_scheda, s.anno_settimana, s.progressivo 
                    FROM centralina_schede cs JOIN schede s ON cs.qr_scheda = s.qr_raw 
                    WHERE cs.seriale_centralina = ? ORDER BY cs.posiz_scheda
                """,
            conn,
            params=(seriale_pdf_sel,),
        )
        info_storico = pd.read_sql(
            """
                    SELECT 
                        COALESCE(data_cambio, data_ora) AS data_cambio, 
                        COALESCE(fase_precedente, fase_da) AS fase_precedente, 
                        COALESCE(fase_successiva, fase_a) AS fase_successiva, 
                        note,
                        utente
                    FROM storico_fasi WHERE seriale_centralina = ? 
                    ORDER BY COALESCE(data_cambio, data_ora) ASC
                """,
            conn,
            params=(seriale_pdf_sel,),
        )
        conn.close()

        st.markdown("#### Anteprima Dati Report")
        st.write(
            f"**Seriale:** {info_c['seriale_centralina']} | **Modello:**"
            f" {info_c['modello']} | **Commessa:** {info_c['commessa']} | **Fase"
            f" Attuale:** {info_c['fase_attuale']}"
        )

        c_preview1, c_preview2 = st.columns(2)
        with c_preview1:
          st.markdown("**Schede Installate:**")
          st.dataframe(info_schede, use_container_width=True, hide_index=True)
        with c_preview2:
          st.markdown("**Storico Fasi & Anomalie:**")
          st.dataframe(info_storico, use_container_width=True, hide_index=True)

        try:
          from reportlab.lib.pagesizes import letter
          from reportlab.pdfgen import canvas

          def genera_pdf_bytes():
            buffer = io.BytesIO()
            p = canvas.Canvas(buffer, pagesize=letter)
            p.setFont("Helvetica-Bold", 16)
            p.drawString(
                50, 750, "CERTIFICATO DI TRACCIABILITÀ CENTRALINA"
            )

            p.setFont("Helvetica", 10)
            p.drawString(
                50, 730, f"Seriale Centralina: {info_c['seriale_centralina']}"
            )
            p.drawString(50, 715, f"Modello: {info_c['modello']}")
            p.drawString(50, 700, f"Commessa: {info_c['commessa']}")
            p.drawString(50, 685, f"Fase Attuale: {info_c['fase_attuale']}")
            p.drawString(
                50, 670, f"Data Assemblaggio: {info_c['data_assemblaggio']}"
            )

            p.setFont("Helvetica-Bold", 12)
            p.drawString(50, 640, "Componenti Schede Installati:")
            p.setFont("Helvetica", 9)
            y = 620
            for _, r in info_schede.iterrows():
              p.drawString(
                  60,
                  y,
                  f"Pos {r['posiz_scheda']}: {r['codice_scheda']} | QR:"
                  f" {r['qr_raw']} | (WWYY: {r['anno_settimana']})",
              )
              y -= 15

            y -= 15
            p.setFont("Helvetica-Bold", 12)
            p.drawString(50, y, "Storico Avanzamento Fasi & Note:")
            p.setFont("Helvetica", 9)
            y -= 20
            for _, r in info_storico.iterrows():
              usr_str = (
                  f" [{r['utente']}]"
                  if pd.notna(r["utente"]) and r["utente"]
                  else ""
              )
              p.drawString(
                  60,
                  y,
                  f"[{r['data_cambio']}]{usr_str} {r['fase_precedente']} ➔"
                  f" {r['fase_successiva']} | Note: {r['note']}",
              )
              y -= 15

            p.showPage()
            p.save()
            pdf_out = buffer.getvalue()
            buffer.close()
            return pdf_out

          pdf_data = genera_pdf_bytes()
          st.download_button(
              label="📄 Scarica Report PDF Tracciabilità",
              data=pdf_data,
              file_name=f"Report_Centralina_{seriale_pdf_sel}.pdf",
              mime="application/pdf",
              type="primary",
          )
        except ImportError:
          st.info("ℹ️ Libreria `reportlab` non installata.")
      else:
        st.info("Nessuna centralina disponibile per generare report.")


# TAB TRACCIABILITÀ
if "tab_tracciabilita" in tab_dict:
  with tab_dict["tab_tracciabilita"]:
    st.header("🔍 Ricerca & Tracciabilità Biunivoca")
    tipo_search = st.radio(
        "Cerca per:", ["Seriale Centralina", "QR Code Scheda"], horizontal=True
    )
    val = st.text_input("Codice da cercare:").strip()

    if val:
      conn = get_connection()
      if tipo_search == "Seriale Centralina":
        df_c = pd.read_sql(
            "SELECT * FROM centraline WHERE seriale_centralina = ?",
            conn,
            params=(val,),
        )
        if not df_c.empty:
          st.dataframe(df_c, use_container_width=True, hide_index=True)
          df_s = pd.read_sql(
              """
                        SELECT cs.posiz_scheda, s.qr_raw, s.codice_scheda, s.anno_settimana, s.progressivo 
                        FROM centralina_schede cs JOIN schede s ON cs.qr_scheda = s.qr_raw 
                        WHERE cs.seriale_centralina = ? ORDER BY cs.posiz_scheda
                    """,
              conn,
              params=(val,),
          )
          st.subheader("Schede Componenti")
          st.dataframe(df_s, use_container_width=True, hide_index=True)
        else:
          st.warning("Nessuna centralina trovata.")
      else:
        df_s = pd.read_sql(
            "SELECT * FROM schede WHERE qr_raw = ?", conn, params=(val,)
        )
        if not df_s.empty:
          st.dataframe(df_s, use_container_width=True, hide_index=True)
          df_c = pd.read_sql(
              """
                        SELECT c.seriale_centralina, c.modello, c.commessa, c.data_assemblaggio 
                        FROM centralina_schede cs JOIN centraline c ON cs.seriale_centralina = c.seriale_centralina 
                        WHERE cs.qr_scheda = ?
                    """,
              conn,
              params=(val,),
          )
          st.subheader("Centralina di Destinazione")
          st.dataframe(df_c, use_container_width=True, hide_index=True)
        else:
          st.warning("Nessuna scheda trovata.")
      conn.close()