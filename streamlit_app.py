import streamlit as st
import pandas as pd
import requests
import time

# --- 1. KONFIGURÁCIA ---
SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzLxqt5QwUvu2zha5NEOg97-7NtPLTbhMd2YQ3ORV6YRny7SvMZwBSgVQ6Zyd3u9v-IKw/exec"

st.set_page_config(page_title="TEPUJEM Portál", page_icon="💰", layout="wide")

if 'user' not in st.session_state:
    st.session_state['user'] = None

# --- STABILNÉ FUNKCIE ---

@st.cache_data(ttl=600)
def get_regions_cached():
    """ Načíta pobočky iba raz za 10 minút - bleskové UI """
    try:
        res = requests.get(f"{SCRIPT_URL}?action=getRegions", timeout=15).json()
        return res.get("regions", ["Liptov", "Bratislava"])
    except:
        return ["Liptov", "Bratislava", "Iné"]

def call_script(action, params):
    """ Robustné volanie s retry logikou pre zápis aj čítanie """
    for i in range(3):
        try:
            url = f"{SCRIPT_URL}?action={action}"
            res = requests.get(url, params=params, timeout=35).json()
            return res if action in ["login", "register", "getRegions"] else (res.get("status") == "success")
        except:
            time.sleep(2)
    return None

def get_data_stable():
    """ Načítanie tabuľky zákaziek """
    for _ in range(3):
        try:
            resp = requests.get(f"{SCRIPT_URL}?action=getZakazky", timeout=30)
            return pd.DataFrame(resp.json())
        except:
            time.sleep(2)
    return pd.DataFrame()

# --- 2. VSTUPNÁ OBRAZOVKA ---
if st.session_state['user'] is None:
    st.title("💰 Provízny systém TEPUJEM")
    tab1, tab2 = st.tabs(["Prihlásenie", "Registrácia nového partnera"])

    with tab1:
        with st.form("login_form"):
            m = st.text_input("Mobil (login)").strip()
            h = st.text_input("Heslo", type="password").strip()
            if st.form_submit_button("Prihlásiť sa", use_container_width=True):
                res = call_script("login", {"mobil": m, "heslo": h})
                if res and res.get("status") == "success":
                    st.session_state['user'] = res
                    st.rerun()
                else:
                    st.error("Nesprávne údaje.")

    with tab2:
        st.subheader("Registrácia")
        available_regions = get_regions_cached()
        
        with st.form("reg_form"):
            reg_pob = st.selectbox("Pobočka (Priradenie k adminovi)", available_regions)
            reg_men = st.text_input("Celé meno")
            reg_mob = st.text_input("Mobil (Login)")
            reg_hes = st.text_input("Heslo (min. 6 znakov)", type="password")
            reg_kod = st.text_input("Váš unikátny kód")
            
            if st.form_submit_button("Zaregistrovať sa", use_container_width=True):
                if len(reg_hes) < 6:
                    st.warning("Krátke heslo.")
                else:
                    with st.status("Zapisujem do Google Tabuľky..."):
                        res = call_script("register", {
                            "meno": reg_men, "mobil": reg_mob, 
                            "heslo": reg_hes, "kod": reg_kod, "pobocka": reg_pob
                        })
                        if res and res.get("status") == "success":
                            st.success("Úspešné! Teraz sa môžete prihlásiť.")
                        else:
                            st.error("Chyba zápisu alebo duplicita.")

# --- 3. DASHBOARD ---
else:
    u = st.session_state['user']
    st.sidebar.title(f"👤 {u.get('meno')}")
    st.sidebar.info(f"Pobočka: {u.get('pobocka_id')}")
    if st.sidebar.button("Odhlásiť sa"):
        st.session_state['user'] = None
        st.rerun()

    df = get_data_stable()
    if df.empty:
        st.warning("Dáta sa načítavajú alebo sú nedostupné (F5).")
        st.stop()

    # Prevod dát a statusov
    df['suma_zakazky'] = pd.to_numeric(df['suma_zakazky'], errors='coerce').fillna(0.0)
    df['provizia_odporucatel'] = pd.to_numeric(df['provizia_odporucatel'], errors='coerce').fillna(0.0)
    df['vyplatene_bool'] = df['vyplatene'].astype(str).str.upper() == 'TRUE'
    df['Stav'] = df['vyplatene_bool'].apply(lambda x: "Vyplatené ✅" if x else "Čaká ⏳")

    if u['rola'] in ['admin', 'superadmin']:
        st.title(f"📊 Správa - {u.get('pobocka_id')}")
        active_df = df if u['rola'] == 'superadmin' else df[df['pobocka_id'] == u['pobocka_id']]

        st.subheader("📩 Na nacenenie")
        k_naceneniu = active_df[active_df['suma_zakazky'] <= 0]
        for i, row in k_naceneniu.iterrows():
            with st.expander(f"📌 {row['poznamka']}"):
                nova_suma = st.number_input(f"Suma (€)", key=f"s_{i}")
                if st.button("Uložiť", key=f"b_{i}"):
                    if call_script("updateSuma", {"row_index": row['row_index'], "suma": nova_suma}):
                        time.sleep(1.2)
                        st.rerun()

        st.divider()
        st.subheader("💳 K výplate")
        k_vyplate = active_df[(active_df['suma_zakazky'] > 0) & (~active_df['vyplatene_bool'])]
        for p_kod in k_vyplate['kod_pouzity'].unique():
            p_data = k_vyplate[k_vyplate['kod_pouzity'] == p_kod]
            with st.expander(f"👤 {p_data['partner_meno'].iloc[0]} | Spolu: **{p_data['provizia_odporucatel'].sum():.2f} €**"):
                st.table(p_data[['poznamka', 'provizia_odporucatel', 'Stav']])
                if st.button(f"Vyplatené {p_kod}", key=f"p_{p_kod}"):
                    for idx in p_data['row_index']: call_script("markAsPaid", {"row_index": idx})
                    st.rerun()
    else:
        # PARTNER PREHĽAD
        st.title(f"💰 Váš prehľad ({u.get('kod')})")
        my_df = df[df['kod_pouzity'] == u['kod']].copy()
        c1, c2 = st.columns(2)
        c1.metric("Celkovo zarobené", f"{my_df['provizia_odporucatel'].sum():.2f} €")
        c2.metric("K výplate", f"{my_df[~my_df['vyplatene_bool']]['provizia_odporucatel'].sum():.2f} €")
        st.table(my_df[['poznamka', 'provizia_odporucatel', 'Stav']].rename(columns={'poznamka':'Zákazka'}))
