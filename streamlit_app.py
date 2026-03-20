import streamlit as st
import pandas as pd
import requests
import time

# --- 1. KONFIGURÁCIA (MASTER URL) ---
SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzLxqt5QwUvu2zha5NEOg97-7NtPLTbhMd2YQ3ORV6YRny7SvMZwBSgVQ6Zyd3u9v-IKw/exec"

st.set_page_config(page_title="TEPUJEM Portál", page_icon="💰", layout="wide")

if 'user' not in st.session_state:
    st.session_state['user'] = None

def call_script(action, params):
    """ Stabilné volanie s automatickým opakovaním (Retry) """
    for i in range(3):
        try:
            url = f"{SCRIPT_URL}?action={action}"
            for k, v in params.items(): url += f"&{k}={v}"
            res = requests.get(url, timeout=25).json()
            return res if action in ["login", "register", "getRegions"] else (res.get("status") == "success")
        except:
            time.sleep(1.8)
    return None

def get_data_stable():
    """ Robustné načítanie dát tabuľky """
    for _ in range(3):
        try:
            resp = requests.get(f"{SCRIPT_URL}?action=getZakazky", timeout=25)
            return pd.DataFrame(resp.json())
        except:
            time.sleep(2)
    return pd.DataFrame()

# --- 2. VSTUPNÁ OBRAZOVKA (Prihlásenie / Registrácia) ---
if st.session_state['user'] is None:
    st.title("💰 Provízny systém TEPUJEM")
    tab1, tab2 = st.tabs(["Prihlásenie", "Registrácia nového partnera"])

    with tab1:
        m = st.text_input("Mobil (prihlasovacie meno)", key="L_MOB").strip()
        h = st.text_input("Heslo", type="password", key="L_HES").strip()
        if st.button("Prihlásiť sa", use_container_width=True):
            with st.spinner("Overujem údaje..."):
                res = call_script("login", {"mobil": m, "heslo": h})
                if res and res.get("status") == "success":
                    st.session_state['user'] = res
                    st.success("Prihlásenie úspešné!")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("Nesprávne údaje alebo chyba servera.")

    with tab2:
        st.subheader("Registrácia")
        
        # Dynamické načítanie regiónov od Adminov z tabuľky
        with st.spinner("Načítavam dostupné pobočky..."):
            regions_res = call_script("getRegions", {})
            available_regions = regions_res.get("regions", ["Liptov", "Bratislava"]) if regions_res else ["Liptov", "Bratislava"]

        reg_pobocka = st.selectbox("Vyberte vašu pobočku (región)", available_regions)
        reg_meno = st.text_input("Meno a priezvisko")
        reg_mobil = st.text_input("Mobil (slúži ako login)")
        reg_heslo = st.text_input("Heslo (min. 6 znakov)", type="password")
        reg_kod = st.text_input("Váš unikátny kód (napr. PETO10)")

        if st.button("Zaregistrovať sa", use_container_width=True):
            if len(reg_heslo) < 6:
                st.warning("Heslo musí mať aspoň 6 znakov.")
            else:
                with st.spinner("Registrujem..."):
                    res = call_script("register", {
                        "meno": reg_meno, "mobil": reg_mobil, 
                        "heslo": reg_heslo, "kod": reg_kod, "pobocka": reg_pobocka
                    })
                    if res and res.get("status") == "success":
                        st.success("Registrácia úspešná! Teraz sa môžete prihlásiť.")
                    else:
                        st.error("Chyba. Skontrolujte údaje (mobil/kód už môže existovať).")

# --- 3. DASHBOARD ---
else:
    u = st.session_state['user']
    st.sidebar.title(f"👤 {u.get('meno')}")
    st.sidebar.info(f"Pobočka: {u.get('pobocka_id')}")
    
    if st.sidebar.button("Odhlásiť sa", use_container_width=True):
        st.session_state['user'] = None
        st.rerun()

    df = get_data_stable()
    
    if df.empty:
        st.warning("Dáta sa nepodarilo načítať. Skúste F5.")
        st.stop()

    # Formátovanie dát
    df['suma_zakazky'] = pd.to_numeric(df['suma_zakazky'], errors='coerce').fillna(0.0)
    df['provizia_odporucatel'] = pd.to_numeric(df['provizia_odporucatel'], errors='coerce').fillna(0.0)
    df['vyplatene_bool'] = df['vyplatene'].astype(str).str.upper() == 'TRUE'
    df['Stav'] = df['vyplatene_bool'].apply(lambda x: "Vyplatené ✅" if x else "Čaká ⏳")

    # --- ADMIN / SUPERADMIN ---
    if u['rola'] in ['admin', 'superadmin']:
        st.title(f"📊 Správa - {u.get('pobocka_id')}")
        
        # Filter: Admin vidí len partnerov registrovaných pod jeho pobočkou
        active_df = df if u['rola'] == 'superadmin' else df[df['pobocka_id'] == u['pobocka_id']]

        # 1. Nacenenie
        st.subheader("📩 Zákazky na nacenenie")
        k_naceneniu = active_df[active_df['suma_zakazky'] <= 0]
        if not k_naceneniu.empty:
            for i, row in k_naceneniu.iterrows():
                with st.expander(f"📌 {row['pobocka_id']} | {row['poznamka']}"):
                    nova_suma = st.number_input(f"Suma (€)", key=f"s_{i}", min_value=0.0)
                    if st.button("Uložiť", key=f"b_{i}"):
                        if call_script("updateSuma", {"row_index": row['row_index'], "suma": nova_suma}):
                            st.success("Uložené.")
                            time.sleep(1.2)
                            st.rerun()
        else: st.info("Žiadne nové dopyty.")

        st.divider()

        # 2. Výplaty
        st.subheader("💳 Prehľad k výplate")
        k_vyplate = active_df[(active_df['suma_zakazky'] > 0) & (~active_df['vyplatene_bool'])]
        if not k_vyplate.empty:
            for p_kod in k_vyplate['kod_pouzity'].unique():
                p_data = k_vyplate[k_vyplate['kod_pouzity'] == p_kod]
                with st.expander(f"👤 {p_data['partner_meno'].iloc[0]} ({p_kod}) | Spolu: **{p_data['provizia_odporucatel'].sum():.2f} €**"):
                    st.table(p_data[['poznamka', 'provizia_odporucatel', 'Stav']].rename(columns={'poznamka': 'Zákazník'}))
                    if st.button(f"Označiť za vyplatené {p_kod}", key=f"pay_{p_kod}"):
                        for idx in p_data['row_index']: call_script("markAsPaid", {"row_index": idx})
                        st.rerun()
        else: st.success("Všetko je vyplatené.")

    # --- PARTNER ---
    else:
        st.title(f"💰 Váš prehľad ({u.get('kod')})")
        my_df = df[df['kod_pouzity'] == u['kod']].copy()
        c1, c2 = st.columns(2)
        c1.metric("Zárobok celkovo", f"{my_df['provizia_odporucatel'].sum():.2f} €")
        c2.metric("Na vyplatenie", f"{my_df[~my_df['vyplatene_bool']]['provizia_odporucatel'].sum():.2f} €")
        st.table(my_df[['poznamka', 'provizia_odporucatel', 'Stav']].rename(columns={'poznamka': 'Zákazka'}))
