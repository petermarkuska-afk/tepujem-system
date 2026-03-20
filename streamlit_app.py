import streamlit as st
import pandas as pd
import requests
import time

# --- 1. KONFIGURÁCIA ---
SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzLxqt5QwUvu2zha5NEOg97-7NtPLTbhMd2YQ3ORV6YRny7SvMZwBSgVQ6Zyd3u9v-IKw/exec"

st.set_page_config(page_title="TEPUJEM Portál", page_icon="💰", layout="wide")

if 'user' not in st.session_state:
    st.session_state['user'] = None

# --- 2. STABILNÉ FUNKCIE (Oprava načítavania) ---

@st.cache_data(ttl=300)
def get_regions_cached():
    """ Rýchle načítanie pobočiek s fallbackom """
    try:
        res = requests.get(f"{SCRIPT_URL}?action=getRegions", timeout=15).json()
        if isinstance(res, dict) and "regions" in res:
            return res["regions"]
    except:
        pass
    return ["Liptov", "Bratislava", "Malacky", "Levice", "Banovce", "Zilina", "Orava", "Vranov"]

def call_script(action, params=None):
    """ Univerzálne volanie s ošetrením chýb """
    if params is None: params = {}
    params['action'] = action
    try:
        response = requests.get(SCRIPT_URL, params=params, timeout=45)
        return response.json()
    except Exception as e:
        return {"status": "error", "message": "Google Script neodpovedá."}

def get_data_stable():
    """ Načítanie dát s kontrolou prázdnych záznamov """
    try:
        resp = requests.get(f"{SCRIPT_URL}?action=getZakazky", timeout=30)
        data = resp.json()
        if isinstance(data, list) and len(data) > 0:
            return pd.DataFrame(data)
    except:
        pass
    return pd.DataFrame()

# --- 3. VSTUPNÁ OBRAZOVKA ---
if st.session_state['user'] is None:
    st.title("💰 Provízny systém TEPUJEM")
    tab1, tab2 = st.tabs(["Prihlásenie", "Registrácia"])

    with tab1:
        with st.form("login_form"):
            m = st.text_input("Mobil (login)").strip()
            h = st.text_input("Heslo", type="password").strip()
            if st.form_submit_button("Prihlásiť sa", use_container_width=True):
                res = call_script("login", {"mobil": m, "heslo": h})
                if res.get("status") == "success":
                    st.session_state['user'] = res
                    st.rerun()
                else:
                    st.error("Nesprávne údaje.")

    with tab2:
        st.subheader("Registrácia")
        available_regions = get_regions_cached()
        with st.form("reg_form"):
            reg_pob = st.selectbox("Pobočka", available_regions)
            reg_men = st.text_input("Meno a priezvisko")
            reg_mob = st.text_input("Mobil (Login)")
            reg_hes = st.text_input("Heslo", type="password")
            reg_kod = st.text_input("Váš unikátny kód")
            if st.form_submit_button("Zaregistrovať sa", use_container_width=True):
                with st.spinner("Zapisujem..."):
                    res = call_script("register", {
                        "pobocka": reg_pob, "priezvisko": reg_men, 
                        "mobil": reg_mob, "heslo": reg_hes, "kod": reg_kod
                    })
                    if res.get("status") == "success":
                        st.success("Úspešné! Prihláste sa vľavo.")
                    else:
                        st.error("Chyba zápisu.")

# --- 4. DASHBOARD (FIX: Ošetrenie prázdnych dát) ---
else:
    u = st.session_state['user']
    st.sidebar.title(f"👤 {u.get('meno')}")
    if st.sidebar.button("Odhlásiť sa"):
        st.session_state['user'] = None
        st.rerun()

    df = get_data_stable()
    
    if df.empty:
        st.info("Zatiaľ nie sú v systéme žiadne zákazky.")
    else:
        # Konverzia čísel
        for col in ['suma_zakazky', 'provizia_odporucatel']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        
        # Logika pre Admina vs Partnera
        if u['rola'] in ['admin', 'superadmin']:
            st.subheader(f"Správa - {u.get('pobocka_id')}")
            active_df = df if u['rola'] == 'superadmin' else df[df['pobocka_id'] == u['pobocka_id']]
            st.dataframe(active_df, use_container_width=True)
        else:
            st.subheader(f"Váš prehľad ({u.get('kod')})")
            my_df = df[df['kod_pouzity'] == u['kod']]
            st.metric("Na vyplatenie", f"{my_df['provizia_odporucatel'].sum():.2f} €")
            st.table(my_df[['poznamka', 'provizia_odporucatel']])
