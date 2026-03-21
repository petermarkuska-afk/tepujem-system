import streamlit as st
import pandas as pd
import requests
import base64
import re
import time
from datetime import datetime

# --- 1. KONFIGURÁCIA ---
st.set_page_config(
    page_title="TEPUJEM Portál", 
    page_icon="💰", 
    layout="centered"
)

# URL na tvoj Google Apps Script
SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzLxqt5QwUvu2zha5NEOg97-7NtPLTbhMd2YQ3ORV6YRny7SvMZwBSgVQ6Zyd3u9v-IKw/exec"

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
    """Volanie Google Apps Scriptu s ošetrením chýb."""
    if params is None:
        params = {}
    params['action'] = action
    
    try:
        response = requests.get(SCRIPT_URL, params=params, timeout=45)
        return response.json()
    except Exception as e:
        st.error(f"Chyba pripojenia k databáze: {e}")
        return {}

def validate_mobile(mob):
    """Validácia mobilného čísla (formát 09XXXXXXXX)."""
    pattern = r'^09\d{8}$'
    return re.match(pattern, mob) is not None

# --- 3. DÁTOVÉ FUNKCIE (BEZ CACHE) ---
def get_regions():
    """Načíta zoznam pobočiek."""
    res = call_script("getRegions")
    return res.get("regions", [])

def get_data():
    """Načíta transakcie/zákazky z Google Sheets."""
    try:
        response = requests.get(f"{SCRIPT_URL}?action=getZakazky", timeout=35)
        return pd.DataFrame(response.json())
    except Exception:
        return pd.DataFrame()

def get_users():
    """Načíta užívateľov z users_data."""
    try:
        response = requests.get(f"{SCRIPT_URL}?action=getUsers", timeout=35)
        return pd.DataFrame(response.json())
    except Exception:
        return pd.DataFrame()

# --- 4. CSS ŠTÝLY ---
img_base64 = get_base64_of_bin_file("image5.png")

css_style = """
<style>
[data-testid="stAppViewContainer"] {
    background-image: url("data:image/png;base64,REPLACE_ME");
    background-size: cover;
    background-position: center;
    background-attachment: fixed;
}
[data-testid="stAppViewContainer"]::before {
    content: "";
    position: absolute;
    top: 0; left: 0; width: 100%; height: 100%;
    background: rgba(0, 0, 0, 0.75); 
    pointer-events: none;
}
[data-testid="stMainBlockContainer"] {
    max-width: 800px !important; 
    background-color: #1e1e1e !important; 
    padding: 40px !important;
    border-radius: 20px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.8);
    margin-top: 50px;
    color: white !important;
}
[data-testid="stMainBlockContainer"] *, label, h1, p, div { color: white !important; }
input { background-color: #333333 !important; color: white !important; border: 1px solid #555 !important; }
button { background-color: #444 !important; color: white !important; border: 1px solid #666 !important; }
</style>
"""

if img_base64:
    st.markdown(css_style.replace("REPLACE_ME", img_base64), unsafe_allow_html=True)

# --- 5. HLAVNÁ APLIKÁCIA ---
if 'user' not in st.session_state:
    st.session_state['user'] = None

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
            kod = st.text_input("Vlastný kód")
            
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
                        st.success("Registrácia úspešná! Prihláste sa.")
                    else:
                        st.error("Chyba pri registrácii.")

else:
    u = st.session_state['user']
    st.sidebar.title(f"👤 {u.get('meno', 'Užívateľ')}")
    if st.sidebar.button("Odhlásiť"):
        st.session_state['user'] = None
        st.rerun()

    df = get_data()
    users = get_users()

    if df.empty:
        st.warning("Žiadne dáta v tabuľke zákaziek.")
        st.stop()

    df['suma_zakazky'] = pd.to_numeric(df['suma_zakazky'], errors='coerce').fillna(0)
    df['provizia_odporucatel'] = pd.to_numeric(df['provizia_odporucatel'], errors='coerce').fillna(0)
    df['vyplatene_bool'] = df['vyplatene'].astype(str).str.strip().str.upper() == "TRUE"

    if not users.empty:
        users_clean = users.rename(columns={'referral_code': 'kod_pouzity', 'mobil': 'mobil_partnera', 'pobocka': 'pob_partnera'})
        df = df.merge(users_clean[['kod_pouzity', 'meno', 'priezvisko', 'adresa', 'mobil_partnera', 'pob_partnera']], on='kod_pouzity', how='left')

    # --- ADMIN VIEW ---
    if u['rola'] in ['admin', 'superadmin']:
        st.title(f"📊 Správa - {u.get('pobocka', 'Neznáma')}")
        active_df = df if u['rola'] == 'superadmin' else df[(df['pobocka_id'] == u['pobocka']) | (df['pob_partnera'] == u['pobocka'])]

        t1, t2 = st.tabs(["Na nacenenie", "Na vyplatenie"])

        with t1:
            nac = active_df[active_df['suma_zakazky'] <= 0]
            if nac.empty:
                st.success("Všetko nacenené! 👍")
            else:
                for i, row in nac.iterrows():
                    with st.expander(f"Zákazník: {row.get('poznamka')} | Partner: {row.get('meno', '---')}"):
                        suma_val = st.number_input("Suma €", key=f"s_{i}", min_value=0.0, step=1.0)
                        if st.button("Uložiť", key=f"b_{i}"):
                            with st.spinner("Zapisujem..."):
                                # OPRAVA: Posielame sumu ako string, aby ju Google Sheets nezdeformoval
                                call_script("updateSuma", {"row_index": str(row['row_index']), "suma": str(suma_val)})
                                time.sleep(1.5)
                                st.rerun()

        with t2:
            pay = active_df[(active_df['suma_zakazky'] > 0) & (~active_df['vyplatene_bool'])]
            if not pay.empty:
                for kod in pay['kod_pouzity'].dropna().unique():
                    p_data = pay[pay['kod_pouzity'] == kod]
                    with st.expander(f"Partner: {kod} | Spolu: {p_data['provizia_odporucatel'].sum():.2f} €"):
                        st.table(p_data[['poznamka', 'provizia_odporucatel']])
                        if st.button("Označiť ako vyplatené", key=f"pay_{kod}"):
                            for _, r in p_data.iterrows():
                                call_script("markAsPaid", {"row_index": str(r['row_index'])})
                            st.rerun()

    # --- PARTNER VIEW ---
    else:
        st.title("💰 Môj prehľad")
        my_df = df[df['kod_pouzity'] == u['kod']]
        st.metric("Zarobené celkovo", f"{my_df['provizia_odporucatel'].sum():.2f} €")
        st.metric("Čaká na výplatu", f"{my_df[~my_df['vyplatene_bool']]['provizia_odporucatel'].sum():.2f} €")
        if not my_df.empty:
            st.table(my_df[['poznamka', 'provizia_odporucatel', 'vyplatene']])
