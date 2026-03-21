import streamlit as st
import pandas as pd
import requests
import base64
import re
import time
from datetime import datetime

# --- 1. KONFIGURÁCIA A SECRETS ---
st.set_page_config(
    page_title="TEPUJEM Portál", 
    page_icon="💰", 
    layout="centered"
)

# Načítanie citlivých údajov zo Streamlit Secrets
try:
    SCRIPT_URL = st.secrets["SCRIPT_URL"]
    API_TOKEN = st.secrets["API_TOKEN"]
except Exception:
    st.error("Chýba konfigurácia (SCRIPT_URL alebo API_TOKEN) v Secrets!")
    st.stop()

# --- 2. POMOCNÉ FUNKCIE ---
def get_base64_of_bin_file(bin_file):
    """Pomocná funkcia pre načítanie pozadia."""
    try:
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except FileNotFoundError:
        return None

def call_script(action, params=None):
    """Volanie Google Apps Scriptu s pridaným API Tokenom."""
    if params is None:
        params = {}
    params['action'] = action
    params['token'] = API_TOKEN
    
    try:
        response = requests.get(SCRIPT_URL, params=params, timeout=40)
        return response.json()
    except Exception as e:
        st.error(f"Chyba pripojenia k databáze: {e}")
        return {}

def validate_mobile(mob):
    """Validácia mobilného čísla (formát 09XXXXXXXX)."""
    pattern = r'^09\d{8}$'
    return re.match(pattern, mob) is not None

# --- 3. DÁTOVÉ FUNKCIE (LIVE SYNC) ---
def get_regions():
    """Načíta zoznam pobočiek pre registráciu."""
    res = call_script("getRegions")
    return res.get("regions", [])

def get_data():
    """Načíta transakcie/zákazky z Google Sheets."""
    try:
        response = requests.get(f"{SCRIPT_URL}?action=getZakazky&token={API_TOKEN}")
        return pd.DataFrame(response.json())
    except Exception:
        return pd.DataFrame()

def get_users():
    """Načíta užívateľov z users_data."""
    try:
        response = requests.get(f"{SCRIPT_URL}?action=getUsers&token={API_TOKEN}")
        return pd.DataFrame(response.json())
    except Exception:
        return pd.DataFrame()

# --- 4. CSS ŠTÝLY (TVOJ PÔVODNÝ MASTER VIZUÁL) ---
img_base64 = get_base64_of_bin_file("image5.png")

css_style = """
<style>
/* Pozadie celej stránky */
[data-testid="stAppViewContainer"] {
    background-image: url("data:image/png;base64,REPLACE_ME");
    background-size: cover;
    background-position: center;
    background-attachment: fixed;
}
/* Tmavá clona pre čitateľnosť */
[data-testid="stAppViewContainer"]::before {
    content: "";
    position: absolute;
    top: 0; left: 0; width: 100%; height: 100%;
    background: rgba(0, 0, 0, 0.78); 
    pointer-events: none;
}
/* Karta obsahu */
[data-testid="stMainBlockContainer"] {
    max-width: 850px !important; 
    background-color: rgba(30, 30, 30, 0.95) !important; 
    padding: 45px !important;
    border-radius: 25px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.8);
    margin-top: 40px;
    color: white !important;
    border: 1px solid #444;
}
/* Formátovanie textov */
[data-testid="stMainBlockContainer"] *, label, h1, h2, h3, p, div { color: white !important; }

/* Štýlovanie tlačidiel a vstupov */
.stButton > button {
    background: linear-gradient(135deg, #FFD700 0%, #B8860B 100%) !important;
    color: black !important;
    font-weight: bold !important;
    border-radius: 12px !important;
    border: none !important;
    padding: 10px 20px !important;
}
input { background-color: #2b2b2b !important; color: white !important; border: 1px solid #555 !important; border-radius: 10px !important; }

/* Tabuľky */
table { color: white !important; background-color: #1a1a1a !important; }
thead tr th { background-color: #333 !important; color: #FFD700 !important; }
</style>
"""

if img_base64:
    st.markdown(css_style.replace("REPLACE_ME", img_base64), unsafe_allow_html=True)

# --- 5. HLAVNÁ LOGIKA APLIKÁCIE ---
if 'user' not in st.session_state:
    st.session_state['user'] = None

# --- ČASŤ A: PRIHLÁSENIE A REGISTRÁCIA ---
if st.session_state['user'] is None:
    st.title("💰 Provízny Systém TEPUJEM.SK")
    
    tab1, tab2 = st.tabs(["Prihlásenie", "Nová registrácia"])
    
    with tab1:
        with st.form("login_form"):
            m = st.text_input("Mobilné číslo (09XXXXXXXX)")
            h = st.text_input("Heslo", type="password")
            if st.form_submit_button("Prihlásiť sa"):
                if not validate_mobile(m):
                    st.error("Mobil musí byť v tvare 09XXXXXXXX!")
                else:
                    res = call_script("login", {"mobil": m, "heslo": h})
                    if res.get("status") == "success":
                        st.session_state['user'] = res
                        st.rerun()
                    else:
                        st.error("Nesprávne údaje alebo účet neexistuje.")

    with tab2:
        with st.form("register_form"):
            st.subheader("Registrácia partnera")
            pob = st.selectbox("Priradiť k pobočke", get_regions())
            c1, c2 = st.columns(2)
            meno = c1.text_input("Meno")
            prie = c2.text_input("Priezvisko")
            adr = st.text_input("Adresa (pre fakturáciu)")
            mob = st.text_input("Mobilné číslo")
            hes = st.text_input("Heslo", type="password")
            kod = st.text_input("Váš unikátny Referral kód")
            
            if st.form_submit_button("Odoslať registráciu"):
                if not validate_mobile(mob):
                    st.error("Mobil musí byť v tvare 09XXXXXXXX!")
                elif not all([meno, prie, mob, hes, kod]):
                    st.warning("Prosím, vyplňte všetky povinné polia.")
                else:
                    res = call_script("register", {
                        "pobocka": pob, "meno": meno, "priezvisko": prie,
                        "adresa": adr, "mobil": mob, "heslo": hes, "kod": kod
                    })
                    if res.get("status") == "success":
                        st.success("Registrácia bola úspešná! Môžete sa prihlásiť.")
                    else:
                        st.error(f"Chyba: {res.get('message', 'Kód alebo mobil sa už používa.')}")

# --- ČASŤ B: DASHBOARD PO PRIHLÁSENÍ ---
else:
    u = st.session_state['user']
    
    # Sidebar menu
    st.sidebar.title(f"👤 {u.get('meno', 'Užívateľ')}")
    st.sidebar.write(f"📍 Pobočka: {u.get('pobocka', '---')}")
    st.sidebar.write(f"🔑 Rola: {u.get('rola', '---')}")
    st.sidebar.divider()
    
    if st.sidebar.button("🔄 Aktualizovať dáta"):
        st.rerun()
        
    if st.sidebar.button("Odhlásiť sa"):
        st.session_state['user'] = None
        st.rerun()

    # Načítanie a spracovanie dát
    df = get_data()
    users = get_users()

    if df.empty:
        st.warning("V databáze zákaziek momentálne nie sú žiadne dáta.")
        st.stop()

    # Pretypovanie a čistenie (FIX CHYBY .str.upper())
    df['suma_zakazky'] = pd.to_numeric(df['suma_zakazky'], errors='coerce').fillna(0)
    df['provizia_odporucatel'] = pd.to_numeric(df['provizia_odporucatel'], errors='coerce').fillna(0)
    # Oprava pre Series object has no attribute upper:
    df['vyplatene_bool'] = df['vyplatene'].astype(str).str.strip().str.upper() == "TRUE"

    # Merge s užívateľmi (Prepojenie cez referral_code)
    if not users.empty:
        users_clean = users.rename(columns={
            'referral_code': 'kod_pouzity', 
            'mobil': 'm_partnera', 
            'pobocka': 'p_partnera',
            'meno': 'meno_p',
            'priezvisko': 'priezvisko_p'
        })
        df = df.merge(users_clean[['kod_pouzity', 'meno_p', 'priezvisko_p', 'm_partnera', 'p_partnera']], 
                      on='kod_pouzity', how='left')
    else:
        for c in ['meno_p', 'priezvisko_p', 'm_partnera', 'p_partnera']: df[c] = "---"

    # --- ZOBRAZENIE PRE ADMINA / SUPERADMINA ---
    if u['rola'] in ['admin', 'superadmin']:
        st.title(f"📊 Manažment - {u.get('pobocka')}")
        
        # Superadmin vidí všetko, Admin len svoju pobočku
        if u['rola'] == 'superadmin':
            active_df = df
        else:
            active_df = df[(df['pobocka_id'] == u['pobocka']) | (df['p_partnera'] == u['pobocka'])]

        tab_new, tab_pay, tab_all = st.tabs(["Nové zákazky", "Na vyplatenie", "Všetky záznamy"])

        with tab_new:
            st.subheader("🆕 Čaká na nacenenie")
            nac = active_df[active_df['suma_zakazky'] <= 0]
            if nac.empty:
                st.success("Všetky zákazky majú priradenú sumu.")
            else:
                for idx, row in nac.iterrows():
                    p_name = f"{row.get('meno_p', '---')} {row.get('priezvisko_p', '')}"
                    with st.expander(f"Zákazník: {row.get('poznamka')} | Partner: {p_name}"):
                        st.write(f"Kontakt partnera: {row.get('m_partnera', '---')}")
                        nova_cena = st.number_input("Zadajte sumu (€)", key=f"sum_{idx}", min_value=0.0, step=1.0)
                        if st.button("Uložiť a naceniť", key=f"btn_{idx}"):
                            res = call_script("updateSuma", {
                                "row_index": row['row_index'], 
                                "suma": nova_cena,
                                "admin_pobocka": u.get('pobocka')
                            })
                            if res.get("status") == "success":
                                st.success("Uložené!")
                                time.sleep(0.5)
                                st.rerun()

        with tab_pay:
            st.subheader("💰 Provízie k výplate")
            to_pay = active_df[(active_df['suma_zakazky'] > 0) & (~active_df['vyplatene_bool'])]
            if to_pay.empty:
                st.info("Žiadne nevyplatené provízie.")
            else:
                for k in to_pay['kod_pouzity'].unique():
                    p_subset = to_pay[to_pay['kod_pouzity'] == k]
                    p_full = f"{p_subset['meno_p'].iloc[0]} {p_subset['priezvisko_p'].iloc[0]}"
                    suma_celkom = p_subset['provizia_odporucatel'].sum()
                    
                    with st.container(border=True):
                        c_a, c_b = st.columns([3, 1])
                        c_a.write(f"**Partner:** {p_full} (`{k}`) | **Spolu:** {suma_celkom:.2f} €")
                        if c_b.button(f"Vyplatiť", key=f"p_{k}"):
                            for _, r_pay in p_subset.iterrows():
                                call_script("markAsPaid", {"row_index": r_pay['row_index'], "admin_pobocka": u.get('pobocka')})
                            st.rerun()
                        st.table(p_subset[['poznamka', 'suma_zakazky', 'provizia_odporucatel']])

        with tab_all:
            st.subheader("📑 Kompletná história")
            st.dataframe(active_df[['datum', 'kod_pouzity', 'poznamka', 'suma_zakazky', 'provizia_odporucatel', 'vyplatene']], use_container_width=True)

    # --- ZOBRAZENIE PRE PARTNERA ---
    else:
        st.title("💰 Môj Provízny Portál")
        my_df = df[df['kod_pouzity'] == u['kod']]
        
        # Metriky partnera
        m1, m2, m3 = st.columns(3)
        m1.metric("Celkový zárobok", f"{my_df['provizia_odporucatel'].sum():.2f} €")
        m2.metric("K výplate", f"{my_df[~my_df['vyplatene_bool']]['provizia_odporucatel'].sum():.2f} €")
        m3.metric("Počet zákaziek", len(my_df))
        
        st.divider()
        st.subheader("Zoznam odporúčaní")
        if not my_df.empty:
            st.table(my_df[['datum', 'poznamka', 'provizia_odporucatel', 'vyplatene']])
        else:
            st.info("Zatiaľ nemáte žiadne evidované odporúčania.")

    st.sidebar.divider()
    st.sidebar.caption(f"© 2026 TEPUJEM.SK | {datetime.now().year}")
