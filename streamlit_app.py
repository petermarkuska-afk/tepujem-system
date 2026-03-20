import streamlit as st
import pandas as pd
import requests
import time

# --- 1. KONFIGURÁCIA ---
SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzLxqt5QwUvu2zha5NEOg97-7NtPLTbhMd2YQ3ORV6YRny7SvMZwBSgVQ6Zyd3u9v-IKw/exec"

st.set_page_config(page_title="TEPUJEM Portál", page_icon="💰", layout="wide")

if 'user' not in st.session_state:
    st.session_state['user'] = None

def call_script(action, params):
    try:
        url = f"{SCRIPT_URL}?action={action}"
        for k, v in params.items(): url += f"&{k}={v}"
        res = requests.get(url, timeout=10).json()
        return res.get("status") == "success"
    except: return False

# --- 2. PRIHLASOVANIE (s ošetrením stability) ---
if st.session_state['user'] is None:
    st.title("💰 Provízny systém TEPUJEM")
    m = st.text_input("Mobil (prihlasovacie meno)", key="L_MOB").strip()
    h = st.text_input("Heslo", type="password", key="L_HES").strip()
    
    if st.button("Prihlásiť sa", use_container_width=True):
        try:
            res = requests.get(f"{SCRIPT_URL}?action=login&mobil={m}&heslo={h}", timeout=15).json()
            if res.get("status") == "success":
                st.session_state['user'] = res
                st.success("Overujem údaje...")
                time.sleep(1.2) # Oneskorenie pre stabilitu prihlásenia
                st.rerun()
            else: st.error("Nesprávne údaje.")
        except: st.error("Chyba pripojenia. Skúste znova.")

# --- 3. DASHBOARD ---
else:
    u = st.session_state['user']
    st.sidebar.title(f"👤 {u.get('meno', 'Užívateľ')}")
    st.sidebar.info(f"Rola: {u['rola'].upper()} | Región: {u.get('pobocka_id', 'LIPTOV')}")
    
    if st.sidebar.button("Odhlásiť sa", use_container_width=True):
        st.session_state['user'] = None
        st.rerun()

    try:
        resp = requests.get(f"{SCRIPT_URL}?action=getZakazky", timeout=15)
        df = pd.DataFrame(resp.json())
        
        if df.empty:
            st.info("Zatiaľ žiadne záznamy v databáze.")
            st.stop()

        # Ošetrenie číselných formátov
        df['suma_zakazky'] = pd.to_numeric(df['suma_zakazky'], errors='coerce').fillna(0.0)
        df['provizia_odporucatel'] = pd.to_numeric(df['provizia_odporucatel'], errors='coerce').fillna(0.0)
        df['vyplatene_bool'] = df['vyplatene'].astype(str).str.upper() == 'TRUE'

        # --- SEKCIA: ADMIN & SUPERADMIN ---
        if u['rola'] in ['admin', 'superadmin']:
            mode = "ADMIN" if u['rola'] == 'admin' else "SUPERADMIN"
            st.title(f"📊 Správa výplat ({mode} - {u.get('pobocka_id', 'LIPTOV')})")

            # Filter dát podľa regiónu pre Admina
            if u['rola'] == 'admin':
                active_df = df[df['pobocka_id'] == u['pobocka_id']]
            else:
                active_df = df # Superadmin vidí všetko (Liptov)

            # 1. ČASŤ: NACENENIE (Tu Admin zadáva sumu)
            st.subheader("📩 Nové požiadavky na nacenenie")
            k_naceneniu = active_df[active_df['suma_zakazky'] <= 0]
            if not k_naceneniu.empty:
                for i, row in k_naceneniu.iterrows():
                    with st.expander(f"📍 {row['pobocka_id']} | Zákazka: {row['poznamka']}"):
                        nova_suma = st.number_input("Zadajte finálnu sumu zákazky (€)", key=f"s_{i}", min_value=1.0)
                        if st.button("Uložiť a vypočítať províziu", key=f"b_{i}"):
                            if call_script("updateSuma", {"row_index": row['row_index'], "suma": nova_suma}):
                                st.success("Suma uložená!")
                                time.sleep(1)
                                st.rerun()
            else: st.info("Žiadne nové zákazky na nacenenie.")

            st.divider()

            # 2. ČASŤ: VÝPLATY (Zobrazenie podľa získateľov)
            st.subheader("💳 Prehľad k výplate (podľa získateľov)")
            k_vyplate = active_df[(active_df['suma_zakazky'] > 0) & (~active_df['vyplatene_bool'])]
            
            if not k_vyplate.empty:
                partneri = k_vyplate['kod_pouzity'].unique()
                for p_kod in partneri:
                    p_data = k_vyplate[k_vyplate['kod_pouzity'] == p_kod]
                    p_meno = p_data['partner_meno'].iloc[0]
                    suma_celkom = p_data['provizia_odporucatel'].sum()
                    
                    with st.expander(f"👤 {p_meno} ({p_kod}) | Spolu na vyplatenie: **{suma_celkom:.2f} €**"):
                        st.table(p_data[['poznamka', 'provizia_odporucatel']].rename(columns={
                            'poznamka': 'Údaje zákazníka',
                            'provizia_odporucatel': 'Provízia (€)'
                        }))
                        if st.button(f"Označiť VŠETKO ako vyplatené pre {p_kod}", key=f"all_{p_kod}"):
                            for idx in p_data['row_index']:
                                call_script("markAsPaid", {"row_index": idx})
                            st.rerun()
            else: st.success("Všetko je vyplatené.")

        # --- SEKCIA: PARTNER (Zákazník) ---
        else:
            st.title(f"💰 Váš prehľad ({u.get('kod', '---')})")
            my_df = df[df['kod_pouzity'] == u['kod']].copy()
            c1, c2 = st.columns(2)
            c1.metric("Zárobok celkovo", f"{my_df['provizia_odporucatel'].sum():.2f} €")
            cakajuce = my_df[~my_df['vyplatene_bool']]['provizia_odporucatel'].sum()
            c2.metric("Na vyplatenie", f"{cakajuce:.2f} €")
            
            st.table(my_df[['poznamka', 'provizia_odporucatel', 'vyplatene_bool']].rename(columns={
                'poznamka': 'Zákazka',
                'provizia_odporucatel': 'Provízia',
                'vyplatene_bool': 'Vybavené'
            }))

    except Exception:
        st.error("Chyba pri spracovaní dát.")
