import streamlit as st
import pandas as pd
import requests
import time

# --- 1. KONFIGURÁCIA (MASTER URL) ---
SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzLxqt5QwUvu2zha5NEOg97-7NtPLTbhMd2YQ3ORV6YRny7SvMZwBSgVQ6Zyd3u9v-IKw/exec"

st.set_page_config(page_title="TEPUJEM Portál", page_icon="💰", layout="wide")

if 'user' not in st.session_state:
    st.session_state['user'] = None

# --- FUNKCIE S CACHE ---

@st.cache_data(ttl=600)
def get_regions_cached():
    for i in range(3):
        try:
            url = f"{SCRIPT_URL}?action=getRegions"
            res = requests.get(url, timeout=15).json()
            if res and "regions" in res:
                return res["regions"]
        except:
            time.sleep(1.5)
    return ["Liptov", "Bratislava", "Malacky", "Levice", "Banovce", "Zilina", "Orava", "Vranov"]

def call_script(action, params):
    """ Posilnené volanie pre dôležité zápisy (Registrácia, Login) """
    # Skúsime to až 4-krát s narastajúcim oneskorením
    for i in range(4):
        try:
            url = f"{SCRIPT_URL}?action={action}"
            for k, v in params.items(): url += f"&{k}={v}"
            # Zvýšený timeout na 30 sekúnd pre istotu pri zápise
            response = requests.get(url, timeout=30)
            res = response.json()
            return res if action in ["login", "register"] else (res.get("status") == "success")
        except Exception as e:
            if i < 3:
                time.sleep(2 * (i + 1)) # Čakaj 2s, potom 4s, potom 6s
                continue
    return {"status": "timeout", "message": "Server neodpovedá. Skontrolujte pripojenie alebo tabuľku."}

def get_data_stable():
    """ Robustné načítanie dát tabuľky """
    for _ in range(3):
        try:
            resp = requests.get(f"{SCRIPT_URL}?action=getZakazky", timeout=25)
            return pd.DataFrame(resp.json())
        except:
            time.sleep(2)
    return pd.DataFrame()

# --- 2. VSTUPNÁ OBRAZOVKA ---
if st.session_state['user'] is None:
    st.title("💰 Provízny systém TEPUJEM")
    tab1, tab2 = st.tabs(["Prihlásenie", "Registrácia nového partnera"])

    with tab1:
        m = st.text_input("Mobil (login)", key="L_MOB").strip()
        h = st.text_input("Heslo", type="password", key="L_HES").strip()
        if st.button("Prihlásiť sa", key="btn_login", use_container_width=True):
            with st.spinner("Pripájanie k databáze..."):
                res = call_script("login", {"mobil": m, "heslo": h})
                if res and res.get("status") == "success":
                    st.session_state['user'] = res
                    st.rerun()
                elif res and res.get("status") == "error":
                    st.error(f"Chyba: {res.get('message', 'Nesprávne údaje.')}")
                else:
                    st.warning("Pripojenie trvá dlhšie, skúste to znova o pár sekúnd.")

    with tab2:
        st.subheader("Registrácia")
        available_regions = get_regions_cached()

        reg_pobocka = st.selectbox("Pobočka (Región)", available_regions, key="reg_pob")
        reg_meno = st.text_input("Meno a priezvisko", key="reg_men")
        reg_mobil = st.text_input("Mobil (Login)", key="reg_mob")
        reg_heslo = st.text_input("Heslo (min. 6 znakov)", type="password", key="reg_hes")
        reg_kod = st.text_input("Váš unikátny kód (napr. PETO10)", key="reg_kod")

        if st.button("Zaregistrovať sa", key="btn_reg", use_container_width=True):
            if not all([reg_meno, reg_mobil, reg_heslo, reg_kod]):
                st.warning("Prosím, vyplňte všetky polia.")
            elif len(reg_heslo) < 6:
                st.warning("Heslo musí mať aspoň 6 znakov.")
            else:
                placeholder = st.empty()
                with placeholder.container():
                    st.info("Odosielam registráciu do Google Tabuľky... Čakajte prosím.")
                    res = call_script("register", {
                        "meno": reg_meno, "mobil": reg_mobil, 
                        "heslo": reg_heslo, "kod": reg_kod, "pobocka": reg_pobocka
                    })
                
                if res and res.get("status") == "success":
                    st.success("✅ Registrácia úspešná! Teraz sa môžete vľavo prepnúť na Prihlásenie.")
                    st.balloons()
                elif res and res.get("status") == "error":
                    st.error(f"❌ Chyba: {res.get('message', 'Mobil alebo Kód už existuje.')}")
                else:
                    st.error("⚠️ Systém nestihol potvrdiť zápis. Skontrolujte tabuľku, či sa dáta zapísali, alebo skúste znova.")

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
        st.warning("Dáta sú momentálne nedostupné. Skúste F5.")
        st.stop()

    df['suma_zakazky'] = pd.to_numeric(df['suma_zakazky'], errors='coerce').fillna(0.0)
    df['provizia_odporucatel'] = pd.to_numeric(df['provizia_odporucatel'], errors='coerce').fillna(0.0)
    df['vyplatene_bool'] = df['vyplatene'].astype(str).str.upper() == 'TRUE'
    df['Stav'] = df['vyplatene_bool'].apply(lambda x: "Vyplatené ✅" if x else "Čaká ⏳")

    if u['rola'] in ['admin', 'superadmin']:
        active_df = df if u['rola'] == 'superadmin' else df[df['pobocka_id'] == u['pobocka_id']]
        
        st.subheader("📩 Zákazky na nacenenie")
        k_naceneniu = active_df[active_df['suma_zakazky'] <= 0]
        if k_naceneniu.empty: st.write("Všetko je nacenené.")
        for i, row in k_naceneniu.iterrows():
            with st.expander(f"📌 {row['poznamka']}"):
                nova_suma = st.number_input(f"Suma (€)", key=f"s_{i}")
                if st.button("Uložiť", key=f"b_{i}"):
                    if call_script("updateSuma", {"row_index": row['row_index'], "suma": nova_suma}):
                        time.sleep(1.2)
                        st.rerun()

        st.divider()
        st.subheader("💳 Prehľad k výplate")
        k_vyplate = active_df[(active_df['suma_zakazky'] > 0) & (~active_df['vyplatene_bool'])]
        for p_kod in k_vyplate['kod_pouzity'].unique():
            p_data = k_vyplate[k_vyplate['kod_pouzity'] == p_kod]
            with st.expander(f"👤 {p_data['partner_meno'].iloc[0]} | **{p_data['provizia_odporucatel'].sum():.2f} €**"):
                st.table(p_data[['poznamka', 'provizia_odporucatel', 'Stav']])
                if st.button(f"Vyplatené {p_kod}", key=f"pay_{p_kod}"):
                    for idx in p_data['row_index']: call_script("markAsPaid", {"row_index": idx})
                    st.rerun()
    else:
        # PARTNER VIEW
        my_df = df[df['kod_pouzity'] == u['kod']].copy()
        st.metric("Na vyplatenie", f"{my_df[~my_df['vyplatene_bool']]['provizia_odporucatel'].sum():.2f} €")
        st.table(my_df[['poznamka', 'provizia_odporucatel', 'Stav']])
