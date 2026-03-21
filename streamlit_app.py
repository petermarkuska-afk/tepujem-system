import streamlit as st
import pandas as pd
import requests
import base64
import re
import time

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

# --- 3. DÁTOVÉ FUNKCIE (BEZ CACHE PRE NAŽIVO DÁTA) ---
def get_regions():
    """Načíta zoznam pobočiek pre registráciu."""
    res = call_script("getRegions")
    return res.get("regions", [])

def get_data():
    """Načíta transakcie/zákazky z Google Sheets (naživo)."""
    try:
        response = requests.get(f"{SCRIPT_URL}?action=getZakazky&token={API_TOKEN}")
        data = response.json()
        return pd.DataFrame(data)
    except Exception:
        return pd.DataFrame()

def get_users():
    """Načíta užívateľov z users_data (naživo)."""
    try:
        response = requests.get(f"{SCRIPT_URL}?action=getUsers&token={API_TOKEN}")
        data = response.json()
        return pd.DataFrame(data)
    except Exception:
        return pd.DataFrame()

# --- 4. CSS ŠTÝLY (TVOJ PÔVODNÝ VIZUÁL) ---
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
/* Tmavá clona */
[data-testid="stAppViewContainer"]::before {
    content: "";
    position: absolute;
    top: 0; left: 0; width: 100%; height: 100%;
    background: rgba(0, 0, 0, 0.75); 
    pointer-events: none;
}
/* Karta obsahu */
[data-testid="stMainBlockContainer"] {
    max-width: 800px !important; 
    background-color: #1e1e1e !important; 
    padding: 40px !important;
    border-radius: 20px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.8);
    margin-top: 50px;
    color: white !important;
}
/* Farby textov a prvkov */
[data-testid="stMainBlockContainer"] *, label, h1, p, div { color: white !important; }
input { background-color: #333333 !important; color: white !important; border: 1px solid #555 !important; }
button { background-color: #444 !important; color: white !important; border: 1px solid #666 !important; }

/* Štýlovanie tabuliek */
table { color: white !important; background-color: #222 !important; }
thead tr th { background-color: #333 !important; color: #FFD700 !important; }
</style>
"""

if img_base64:
    st.markdown(css_style.replace("REPLACE_ME", img_base64), unsafe_allow_html=True)

# --- 5. HLAVNÁ APLIKÁCIA ---
if 'user' not in st.session_state:
    st.session_state['user'] = None

# --- ČASŤ 1: LOGIN A REGISTRÁCIA ---
if st.session_state['user'] is None:
    st.title("💰 Zarob si s TEPUJEM.SK")
    
    tab1, tab2 = st.tabs(["Prihlásenie", "Registrácia"])
    
    with tab1:
        with st.form("login_form"):
            m = st.text_input("Mobilné číslo (formát 09XXXXXXXX)")
            h = st.text_input("Heslo", type="password")
            if st.form_submit_button("Prihlásiť"):
                if not validate_mobile(m):
                    st.error("Mobil musí byť v tvare 09XXXXXXXX!")
                else:
                    res = call_script("login", {"mobil": m, "heslo": h})
                    if res.get("status") == "success":
                        st.session_state['user'] = res
                        st.rerun()
                    else:
                        st.error("Zlé údaje alebo chybný mobil.")

    with tab2:
        with st.form("register_form"):
            pob = st.selectbox("Vyber najbližšiu pobočku", get_regions())
            meno = st.text_input("Meno")
            priezvisko = st.text_input("Priezvisko")
            adresa = st.text_input("Adresa")
            mob = st.text_input("Mobilné číslo (formát 09XXXXXXXX)")
            hes = st.text_input("Heslo", type="password")
            kod = st.text_input("Vlastný kód (Referral)")
            
            if st.form_submit_button("Registrovať"):
                if not validate_mobile(mob):
                    st.error("Mobilné číslo musí byť v tvare 09XXXXXXXX!")
                elif not all([meno, priezvisko, adresa, mob, hes, kod]):
                    st.warning("Vyplň všetky polia!")
                else:
                    res = call_script("register", {
                        "pobocka": pob, "meno": meno, "priezvisko": priezvisko,
                        "adresa": adresa, "mobil": mob, "heslo": hes, "kod": kod
                    })
                    if res.get("status") == "success":
                        st.success("Registrácia úspešná! Teraz sa môžete prihlásiť.")
                    else:
                        st.error("Chyba pri registrácii.")

# --- ČASŤ 2: DASHBOARD PO PRIHLÁSENÍ ---
else:
    u = st.session_state['user']
    
    # Bočný panel
    st.sidebar.title(f"👤 {u.get('meno', 'Užívateľ')}")
    st.sidebar.write(f"📍 Pobočka: {u.get('pobocka', '---')}")
    st.sidebar.write(f"🔑 Rola: {u.get('rola', '---')}")
    
    if st.sidebar.button("🔄 Aktualizovať dáta"):
        st.rerun()
        
    if st.sidebar.button("Odhlásiť"):
        st.session_state['user'] = None
        st.rerun()

    # Načítanie dát
    df = get_data()
    users = get_users()

    if df.empty:
        st.warning("Žiadne dáta v tabuľke zákaziek.")
        st.stop()

    # Čistenie dát transakcií
    df['suma_zakazky'] = pd.to_numeric(df['suma_zakazky'], errors='coerce').fillna(0)
    df['provizia_odporucatel'] = pd.to_numeric(df['provizia_odporucatel'], errors='coerce').fillna(0)
    df['vyplatene_bool'] = df['vyplatene'].astype(str).str.strip().str.upper() == "TRUE"

    # Merge s užívateľmi (FIX: 'referral_code' namiesto 'kod')
    if not users.empty:
        users_clean = users.rename(columns={
            'referral_code': 'kod_pouzity', 
            'mobil': 'mobil_partnera', 
            'pobocka': 'pobocka_partnera'
        })
        df = df.merge(users_clean[['kod_pouzity', 'meno', 'priezvisko', 'mobil_partnera', 'pobocka_partnera']], 
                      on='kod_pouzity', how='left')
    else:
        for col in ['meno', 'priezvisko', 'mobil_partnera', 'pobocka_partnera']:
            df[col] = "---"

    # --- ADMIN VIEW ---
    if u['rola'] in ['admin', 'superadmin']:
        st.title(f"📊 Správa - {u.get('pobocka', 'Neznáma')}")
        
        if u['rola'] == 'superadmin':
            active_df = df
        else:
            active_df = df[(df['pobocka_id'] == u['pobocka']) | (df['pobocka_partnera'] == u['pobocka'])]

        tab_nac, tab_vyp = st.tabs(["Na nacenenie", "Na vyplatenie"])

        with tab_nac:
            nac = active_df[active_df['suma_zakazky'] <= 0]
            if nac.empty:
                st.success("Všetko nacenené! 👍")
            else:
                for i, row in nac.iterrows():
                    m = row.get('meno', 'Priama')
                    p = row.get('priezvisko', '')
                    with st.expander(f"Zákazník: {row.get('poznamka')} | Partner: {m} {p}"):
                        st.write(f"Kontakt partnera: {row.get('mobil_partnera', '---')}")
                        suma = st.number_input("Suma €", key=f"s_{i}", min_value=0.0, step=1.0)
                        if st.button("Uložiť", key=f"b_{i}"):
                            call_script("updateSuma", {
                                "row_index": row['row_index'], 
                                "suma": suma,
                                "admin_pobocka": u.get('pobocka')
                            })
                            st.rerun()

        with tab_vyp:
            pay = active_df[(active_df['suma_zakazky'] > 0) & (~active_df['vyplatene_bool'])]
            if pay.empty:
                st.info("Nič na vyplatenie.")
            else:
                for kod in pay['kod_pouzity'].dropna().unique():
                    p_data = pay[pay['kod_pouzity'] == kod]
                    m_p = p_data['meno'].iloc[0] if not p_data.empty else "---"
                    p_p = p_data['priezvisko'].iloc[0] if not p_data.empty else ""
                    
                    with st.expander(f"Partner: {m_p} {p_p} ({kod}) | K výplate: {p_data['provizia_odporucatel'].sum():.2f} €"):
                        st.table(p_data[['poznamka', 'suma_zakazky', 'provizia_odporucatel']])
                        if st.button(f"Označiť ako vyplatené ({kod})", key=f"pay_{kod}"):
                            for _, r in p_data.iterrows():
                                call_script("markAsPaid", {
                                    "row_index": r['row_index'],
                                    "admin_pobocka": u.get('pobocka')
                                })
                            st.rerun()

    # --- PARTNER VIEW ---
    else:
        st.title("💰 Môj prehľad")
        my_df = df[df['kod_pouzity'] == u['kod']]
        
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Zarobené celkovo", f"{my_df['provizia_odporucatel'].sum():.2f} €")
        with c2:
            st.metric("Čaká na výplatu", f"{my_df[~my_df['vyplatene_bool']]['provizia_odporucatel'].sum():.2f} €")
        
        st.divider()
        if not my_df.empty:
            display_df = my_df[['poznamka', 'provizia_odporucatel', 'vyplatene', 'pobocka_id']].copy()
            display_df.columns = ['Poznámka', 'Zárobok', 'Vyplatené', 'Pobočka servisu']
            st.table(display_df)
        else:
            st.info("Zatiaľ tu nemáte žiadne záznamy.")

    st.sidebar.divider()
    st.sidebar.caption("© 2026 TEPUJEM.SK")
