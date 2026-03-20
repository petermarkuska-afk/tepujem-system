import streamlit as st
import pandas as pd
import requests
import time

# --- KONFIGURÁCIA ---
# Vymeň za svoje aktuálne URL z "Nasadit > Nová verze"
SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzLxqt5QwUvu2zha5NEOg97-7NtPLTbhMd2YQ3ORV6YRny7SvMZwBSgVQ6Zyd3u9v-IKw/exec"

st.set_page_config(page_title="TEPUJEM Portál", page_icon="💰", layout="wide")

if 'user' not in st.session_state:
    st.session_state['user'] = None

# --- FUNKCIE PRE RÝCHLOSŤ A STABILITU ---

def call_script(action, params=None):
    """ Volanie skriptu s predĺženým timeoutom a ošetrením chýb """
    if params is None:
        params = {}
    params['action'] = action
    try:
        # Zvýšený timeout na 60s pre pomalé Google Sheets
        response = requests.get(SCRIPT_URL, params=params, timeout=60)
        return response.json()
    except Exception as e:
        return {"status": "error", "message": "Google Tabuľka neodpovedá včas. Skúste znova."}

@st.cache_data(ttl=300) # Cache na 5 minút pre bleskové načítanie pobočiek
def get_regions():
    res = call_script("getRegions")
    if isinstance(res, dict) and "regions" in res:
        return res["regions"]
    return ["Bratislava", "Liptov", "Malacky", "Levice", "Banovce", "Zilina", "Orava", "Vranov"]

# --- UI LOGIKA ---

if st.session_state['user'] is None:
    st.title("💰 Provízny systém TEPUJEM")
    tab1, tab2 = st.tabs(["Prihlásenie", "Registrácia"])

    with tab1:
        with st.form("login_form"):
            m = st.text_input("Mobil (prihlasovacie meno)")
            h = st.text_input("Heslo", type="password")
            if st.form_submit_button("Prihlásiť sa", use_container_width=True):
                with st.spinner("Overujem..."):
                    res = call_script("login", {"mobil": m, "heslo": h})
                    if res.get("status") == "success":
                        st.session_state['user'] = res
                        st.rerun()
                    else:
                        st.error(res.get("message", "Nesprávne údaje."))

    with tab2:
        st.subheader("Nový partner")
        with st.form("reg_form"):
            reg_pob = st.selectbox("Pobočka", get_regions())
            reg_men = st.text_input("Meno")
            reg_priez = st.text_input("Priezvisko")
            reg_mob = st.text_input("Mobil (Login)")
            reg_hes = st.text_input("Heslo", type="password")
            reg_kod = st.text_input("Unikátny kód (napr. JOZO5)")
            
            if st.form_submit_button("Zaregistrovať sa", use_container_width=True):
                with st.spinner("Zapisujem do tabuľky..."):
                    res = call_script("register", {
                        "pobocka": reg_pob, "meno": reg_men, "priezvisko": reg_priez,
                        "mobil": reg_mob, "heslo": reg_hes, "kod": reg_kod
                    })
                    if res.get("status") == "success":
                        st.success("Registrácia úspešná! Môžete sa prihlásiť.")
                    else:
                        st.error(res.get("message", "Chyba pri zápise."))

else:
    # --- DASHBOARD ---
    u = st.session_state['user']
    st.sidebar.title(f"👤 {u['meno']}")
    if st.sidebar.button("Odhlásiť sa"):
        st.session_state['user'] = None
        st.rerun()

    st.header(f"Vitajte, {u['meno']}!")
    
    with st.spinner("Načítavam dáta..."):
        data_res = call_script("getZakazky")
        
    if isinstance(data_res, list) and len(data_res) > 0:
        df = pd.DataFrame(data_res)
        
        # Ošetrenie stĺpcov (aby nepadalo na chýbajúcich dátach)
        cols = df.columns
        if 'suma_zakazky' in cols:
            df['suma_zakazky'] = pd.to_numeric(df['suma_zakazky'], errors='coerce').fillna(0)
        if 'provizia_odporucatel' in cols:
            df['provizia_odporucatel'] = pd.to_numeric(df['provizia_odporucatel'], errors='coerce').fillna(0)
        
        # Filtrovanie pre partnera
        if u['rola'] == 'zakaznik':
            my_df = df[df['kod_pouzity'] == u['kod']]
            st.metric("Zárobok celkovo", f"{my_df['provizia_odporucatel'].sum():.2f} €")
            st.dataframe(my_df[['poznamka', 'provizia_odporucatel', 'vyplatene']], use_container_width=True)
        
        # Filtrovanie pre admina
        else:
            admin_df = df if u['rola'] == 'superadmin' else df[df['pobocka_id'] == u['pobocka_id']]
            st.subheader("Správa zákaziek")
            st.dataframe(admin_df, use_container_width=True)
    else:
        st.info("Zatiaľ tu nie sú žiadne dáta o zákazkách.")
