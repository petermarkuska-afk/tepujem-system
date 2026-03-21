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

# Tvoj overený URL skriptu
SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzLxqt5QwUvu2zha5NEOg97-7NtPLTbhMd2YQ3ORV6YRny7SvMZwBSgVQ6Zyd3u9v-IKw/exec"

# --- 2. POMOCNÉ FUNKCIE ---
def get_base64_of_bin_file(bin_file):
    """Načítanie pozadia."""
    try:
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except FileNotFoundError:
        return None

def call_script(action, params=None):
    """Volanie Google Apps Scriptu."""
    if params is None:
        params = {}
    params['action'] = action
    try:
        response = requests.get(SCRIPT_URL, params=params, timeout=45)
        return response.json()
    except Exception as e:
        st.error(f"Chyba pripojenia: {e}")
        return {}

def validate_mobile(mob):
    """Validácia formátu mobilu."""
    return re.match(r'^09\d{8}$', mob) is not None

# --- 3. DÁTOVÉ FUNKCIE (BEZ CACHE) ---

def get_regions():
    """Načíta pobočky vždy naživo."""
    res = call_script("getRegions")
    return res.get("regions", ["Bratislava", "Liptov", "Malacky", "Levice", "Banovce", "Zilina", "Orava", "Vranov"])

def get_data():
    """Načíta transakcie vždy naživo."""
    try:
        response = requests.get(f"{SCRIPT_URL}?action=getZakazky", timeout=35)
        return pd.DataFrame(response.json())
    except:
        return pd.DataFrame()

def get_users():
    """Načíta užívateľov vždy naživo."""
    try:
        response = requests.get(f"{SCRIPT_URL}?action=getUsers", timeout=35)
        return pd.DataFrame(response.json())
    except:
        return pd.DataFrame()

# --- 4. CSS A VIZUÁL ---
img_base64 = get_base64_of_bin_file("image5.png")
if img_base64:
    css_style = f"""
    <style>
    [data-testid="stAppViewContainer"] {{
        background-image: url("data:image/png;base64,{img_base64}");
        background-size: cover; background-position: center; background-attachment: fixed;
    }}
    [data-testid="stAppViewContainer"]::before {{
        content: ""; position: absolute; top: 0; left: 0; width: 100%; height: 100%;
        background: rgba(0, 0, 0, 0.78); pointer-events: none;
    }}
    [data-testid="stMainBlockContainer"] {{
        max-width: 850px !important; background-color: #1a1a1a !important; 
        padding: 3rem !important; border-radius: 25px; box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        margin-top: 30px; color: white !important;
    }}
    h1, h2, h3, label, p, span, div {{ color: white !important; font-family: 'Segoe UI', sans-serif; }}
    .stButton>button {{ width: 100%; border-radius: 10px; height: 3em; background-color: #333; border: 1px solid #555; }}
    input {{ background-color: #262626 !important; color: white !important; border-radius: 8px !important; }}
    </style>
    """
    st.markdown(css_style, unsafe_allow_html=True)

# --- 5. LOGIKA PRIHLÁSENIA ---
if 'user' not in st.session_state:
    st.session_state['user'] = None

if st.session_state['user'] is None:
    st.title("💰 Zarob si s TEPUJEM.SK")
    t1, t2 = st.tabs(["Prihlásenie", "Registrácia partnera"])
    
    with t1:
        with st.form("login_form"):
            m = st.text_input("Mobil (09XXXXXXXX)")
            h = st.text_input("Heslo", type="password")
            if st.form_submit_button("Vstúpiť do portálu"):
                res = call_script("login", {"mobil": m, "heslo": h})
                if res.get("status") == "success":
                    st.session_state['user'] = res
                    st.rerun()
                else: st.error("Nesprávne mobilné číslo alebo heslo.")

    with t2:
        with st.form("reg_form"):
            c1, c2 = st.columns(2)
            reg_meno = c1.text_input("Meno")
            reg_priez = c2.text_input("Priezvisko")
            reg_pob = st.selectbox("Najbližšia pobočka", get_regions())
            reg_mob = st.text_input("Mobilné číslo")
            reg_hes = st.text_input("Heslo (min. 6 znakov)", type="password")
            reg_kod = st.text_input("Váš unikátny kód (referral)")
            
            if st.form_submit_button("Založiť účet"):
                if not validate_mobile(reg_mob):
                    st.error("Formát mobilu musí byť 09XXXXXXXX.")
                elif not all([reg_meno, reg_priez, reg_mob, reg_hes, reg_kod]):
                    st.warning("Prosím, vyplňte všetky polia.")
                else:
                    res = call_script("register", {
                        "pobocka": reg_pob, "meno": reg_meno, "priezvisko": reg_priez,
                        "mobil": reg_mob, "heslo": reg_hes, "kod": reg_kod
                    })
                    if res.get("status") == "success":
                        st.success("Registrácia úspešná! Teraz sa môžete prihlásiť.")
                    else: st.error("Tento mobil alebo kód sa už používa.")

# --- 6. DASHBOARD ---
else:
    u = st.session_state['user']
    st.sidebar.markdown(f"### Vitajte, **{u.get('meno')}**")
    st.sidebar.write(f"Rola: `{u.get('rola')}`")
    st.sidebar.write(f"Pobočka: {u.get('pobocka')}")
    
    if st.sidebar.button("Odhlásiť sa"):
        st.session_state['user'] = None
        st.rerun()

    # Sťahujeme čerstvé dáta
    df = get_data()
    users = get_users()

    if df.empty:
        st.info("Momentálne neevidujeme žiadne zákazky.")
        st.stop()

    # Formátovanie
    df['suma_zakazky'] = pd.to_numeric(df['suma_zakazky'], errors='coerce').fillna(0)
    df['provizia_odporucatel'] = pd.to_numeric(df['provizia_odporucatel'], errors='coerce').fillna(0)
    df['vyplatene_bool'] = df['vyplatene'].astype(str).str.upper() == "TRUE"

    # Admin rozhranie
    if u['rola'] in ['admin', 'superadmin']:
        st.subheader("⚙️ Administrácia zákaziek")
        
        # Merge s užívateľmi pre lepšie info
        if not users.empty:
            u_clean = users.rename(columns={'referral_code': 'kod_pouzity', 'mobil': 'tel_P', 'pobocka': 'mesto_P'})
            df = df.merge(u_clean[['kod_pouzity', 'meno', 'priezvisko', 'tel_P', 'mesto_P']], on='kod_pouzity', how='left')

        # Filter podľa pobočky
        active_df = df if u['rola'] == 'superadmin' else df[(df['pobocka_id'] == u['pobocka']) | (df['mesto_P'] == u['pobocka'])]

        tab_n, tab_v = st.tabs(["📩 Čaká na nacenenie", "💳 Čaká na výplatu"])

        with tab_n:
            k_naceneniu = active_df[active_df['suma_zakazky'] <= 0]
            if k_naceneniu.empty: st.success("Všetko je nacenené.")
            for i, row in k_naceneniu.iterrows():
                with st.expander(f"Zákazka: {row['poznamka']} (Partner: {row.get('meno', '---')})"):
                    s = st.number_input("Suma zákazky (€)", key=f"sum_{i}", min_value=0.0)
                    if st.button("Uložiť sumu", key=f"btn_{i}"):
                        with st.spinner("Zapisujem..."):
                            call_script("updateSuma", {"row_index": row['row_index'], "suma": s})
                            time.sleep(1.5) # Krátka pauza pre Google
                            st.rerun()

        with tab_v:
            k_vyplate = active_df[(active_df['suma_zakazky'] > 0) & (~active_df['vyplatene_bool'])]
            if k_vyplate.empty: st.info("Žiadne provízie k výplate.")
            for kod in k_vyplate['kod_pouzity'].unique():
                p_rows = k_vyplate[k_vyplate['kod_pouzity'] == kod]
                with st.expander(f"Partner: {kod} | Suma: {p_rows['provizia_odporucatel'].sum():.2f} €"):
                    st.dataframe(p_rows[['poznamka', 'suma_zakazky', 'provizia_odporucatel']])
                    if st.button(f"Označiť ako vyplatené ({kod})", key=f"p_{kod}"):
                        for idx in p_rows['row_index']:
                            call_script("markAsPaid", {"row_index": idx})
                        st.rerun()

    # Užívateľské rozhranie
    else:
        st.title("💰 Moje provízie")
        my_df = df[df['kod_pouzity'] == u['kod']]
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Počet zákaziek", len(my_df))
        c2.metric("Celkový zárobok", f"{my_df['provizia_odporucatel'].sum():.2f} €")
        c3.metric("K výplate", f"{my_df[~my_df['vyplatene_bool']]['provizia_odporucatel'].sum():.2f} €")
        
        st.divider()
        st.write("### História vašich odporúčaní")
        if my_df.empty:
            st.info("Zatiaľ ste neodporučili žiadnu zákazku.")
        else:
            res_df = my_df[['poznamka', 'suma_zakazky', 'provizia_odporucatel', 'vyplatene']].copy()
            res_df.columns = ['Zákazník', 'Suma (€)', 'Moja provízia', 'Stav']
            st.dataframe(res_df, use_container_width=True)
