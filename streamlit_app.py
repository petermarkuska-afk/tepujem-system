import streamlit as st
import pandas as pd
import requests
import time

# --- 1. KONFIGURÁCIA ---
# Tu vlož svoje URL z Google Scriptu (Nasadit > Nová verze)
SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzLxqt5QwUvu2zha5NEOg97-7NtPLTbhMd2YQ3ORV6YRny7SvMZwBSgVQ6Zyd3u9v-IKw/exec"

st.set_page_config(page_title="TEPUJEM Portál", page_icon="💰", layout="wide")

# Inicializácia session state
if 'user' not in st.session_state:
    st.session_state['user'] = None

# --- 2. STABILNÉ FUNKCIE ---

@st.cache_data(ttl=600)
def get_regions_cached():
    """ Načíta pobočky (adminov) a zapamätá si ich na 10 minút pre rýchle UI """
    try:
        res = requests.get(f"{SCRIPT_URL}?action=getRegions", timeout=15).json()
        return res.get("regions", ["Bratislava", "Liptov"])
    except:
        return ["Bratislava", "Liptov", "Malacky", "Levice", "Banovce", "Zilina", "Orava", "Vranov"]

def call_script(action, params):
    """ Univerzálne volanie Google Scriptu s ochranou proti timeoutu """
    for i in range(3):
        try:
            url = f"{SCRIPT_URL}?action={action}"
            # Používame 45s timeout, pretože zápis do Google Sheets je pomalý
            res = requests.get(url, params=params, timeout=45).json()
            return res if action in ["login", "register", "getRegions"] else (res.get("status") == "success")
        except:
            if i < 2: time.sleep(2)
    return {"status": "error", "message": "Server neodpovedá. Skúste znova."}

def get_data_stable():
    """ Načítanie všetkých zákaziek z transactions_data """
    for _ in range(3):
        try:
            resp = requests.get(f"{SCRIPT_URL}?action=getZakazky", timeout=30)
            return pd.DataFrame(resp.json())
        except:
            time.sleep(2)
    return pd.DataFrame()

# --- 3. VSTUPNÁ OBRAZOVKA (LOGIN / REGISTRÁCIA) ---
if st.session_state['user'] is None:
    st.title("💰 Provízny systém TEPUJEM")
    tab1, tab2 = st.tabs(["Prihlásenie", "Registrácia nového partnera"])

    with tab1:
        with st.form("login_form"):
            m = st.text_input("Mobil (login)").strip()
            h = st.text_input("Heslo", type="password").strip()
            if st.form_submit_button("Prihlásiť sa", use_container_width=True):
                with st.spinner("Overujem údaje..."):
                    res = call_script("login", {"mobil": m, "heslo": h})
                    if res.get("status") == "success":
                        st.session_state['user'] = res
                        st.rerun()
                    else:
                        st.error(res.get("message", "Nesprávne údaje."))

    with tab2:
        st.subheader("Registrácia")
        available_regions = get_regions_cached()
        
        with st.form("reg_form"):
            reg_pob = st.selectbox("Pobočka (Priradenie k adminovi)", available_regions)
            reg_men = st.text_input("Meno a priezvisko")
            reg_mob = st.text_input("Mobil (slúži ako Login)")
            reg_hes = st.text_input("Heslo (min. 6 znakov)", type="password")
            reg_kod = st.text_input("Váš unikátny kód (referral)")
            
            if st.form_submit_button("Zaregistrovať sa", use_container_width=True):
                if not all([reg_men, reg_mob, reg_hes, reg_kod]):
                    st.warning("Prosím, vyplňte všetky polia.")
                elif len(reg_hes) < 6:
                    st.warning("Heslo musí mať aspoň 6 znakov.")
                else:
                    with st.status("Zapisujem do users_data..."):
                        res = call_script("register", {
                            "pobocka": reg_pob, "priezvisko": reg_men, 
                            "mobil": reg_mob, "heslo": reg_hes, "kod": reg_kod
                        })
                        if res.get("status") == "success":
                            st.success("✅ Úspešne zaregistrované! Teraz sa môžete prihlásiť.")
                            st.balloons()
                        else:
                            st.error(f"❌ Chyba: {res.get('message', 'Skúste iný mobil/kód.')}")

# --- 4. DASHBOARD (PO PRIHLÁSENÍ) ---
else:
    u = st.session_state['user']
    st.sidebar.title(f"👤 {u.get('meno')}")
    st.sidebar.info(f"Pobočka: {u.get('pobocka_id')}")
    
    if st.sidebar.button("Odhlásiť sa", use_container_width=True):
        st.session_state['user'] = None
        st.rerun()

    # Načítanie dát
    df = get_data_stable()
    
    if df.empty:
        st.warning("Zatiaľ tu nie sú žiadne dáta o zákazkách.")
    else:
        # Formátovanie stĺpcov
        df['suma_zakazky'] = pd.to_numeric(df['suma_zakazky'], errors='coerce').fillna(0.0)
        df['provizia_odporucatel'] = pd.to_numeric(df['provizia_odporucatel'], errors='coerce').fillna(0.0)
        df['vyplatene_bool'] = df['vyplatene'].astype(str).str.upper() == 'TRUE'
        df['Stav'] = df['vyplatene_bool'].apply(lambda x: "Vyplatené ✅" if x else "Čaká ⏳")

        # --- ADMIN / SUPERADMIN ZOBRAZENIE ---
        if u['rola'] in ['admin', 'superadmin']:
            st.title(f"📊 Správa - {u.get('pobocka_id')}")
            
            # Filter: Admin vidí len tie, kde sa pobocka_id zhoduje s jeho menom
            active_df = df if u['rola'] == 'superadmin' else df[df['pobocka_id'] == u['pobocka_id']]

            # Sekcia 1: Nacenenie
            st.subheader("📩 Nové zákazky na nacenenie")
            k_naceneniu = active_df[active_df['suma_zakazky'] <= 0]
            if k_naceneniu.empty:
                st.info("Všetky zákazky sú nacenené.")
            else:
                for i, row in k_naceneniu.iterrows():
                    with st.expander(f"📍 {row['pobocka_id']} | {row['poznamka']}"):
                        nova_suma = st.number_input(f"Suma zákazky (€)", key=f"s_{i}", min_value=0.0)
                        if st.button("Uložiť a vypočítať", key=f"b_{i}"):
                            if call_script("updateSuma", {"row_index": row['row_index'], "suma": nova_suma}):
                                st.success("Uložené!")
                                time.sleep(1.2) # Pauza pre Google prepočet
                                st.rerun()

            st.divider()

            # Sekcia 2: Výplaty
            st.subheader("💳 Prehľad provízií k výplate")
            k_vyplate = active_df[(active_df['suma_zakazky'] > 0) & (~active_df['vyplatene_bool'])]
            if not k_vyplate.empty:
                for p_kod in k_vyplate['kod_pouzity'].unique():
                    p_data = k_vyplate[k_vyplate['kod_pouzity'] == p_kod]
                    p_meno = p_data['partner_meno'].iloc[0] if 'partner_meno' in p_data else p_kod
                    
                    with st.expander(f"👤 {p_meno} ({p_kod}) | Spolu: **{p_data['provizia_odporucatel'].sum():.2f} €**"):
                        st.table(p_data[['poznamka', 'provizia_odporucatel', 'Stav']])
                        if st.button(f"Označiť ako vyplatené ({p_kod})", key=f"pay_{p_kod}"):
                            for idx in p_data['row_index']:
                                call_script("markAsPaid", {"row_index": idx})
                            st.success("Označené!")
                            time.sleep(1)
                            st.rerun()
            else:
                st.success("Všetky provízie sú vyplatené.")

        # --- PARTNER ZOBRAZENIE ---
        else:
            st.title(f"💰 Váš prehľad ({u.get('kod')})")
            my_df = df[df['kod_pouzity'] == u['kod']].copy()
            
            c1, c2 = st.columns(2)
            c1.metric("Celkovo zarobené", f"{my_df['provizia_odporucatel'].sum():.2f} €")
            c2.metric("Na vyplatenie", f"{my_df[~my_df['vyplatene_bool']]['provizia_odporucatel'].sum():.2f} €")
            
            st.subheader("Moje odporúčané zákazky")
            if my_df.empty:
                st.info("Zatiaľ ste neodporučili žiadnu zákazku.")
            else:
                st.table(my_df[['poznamka', 'provizia_odporucatel', 'Stav']].rename(columns={'poznamka': 'Zákazník'}))
