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
    # Funkcia s automatickým opakovaním pri chybe (retry logic)
    for _ in range(2): 
        try:
            url = f"{SCRIPT_URL}?action={action}"
            for k, v in params.items(): url += f"&{k}={v}"
            res = requests.get(url, timeout=15).json()
            return res.get("status") == "success"
        except:
            time.sleep(1)
    return False

# --- 2. PRIHLASOVANIE ---
if st.session_state['user'] is None:
    st.title("💰 Provízny systém TEPUJEM")
    m = st.text_input("Mobil (prihlasovacie meno)", key="L_MOB").strip()
    h = st.text_input("Heslo", type="password", key="L_HES").strip()
    
    if st.button("Prihlásiť sa", use_container_width=True):
        try:
            # Väčší časový interval a ošetrenie pripojenia
            with st.spinner("Pripájanie k databáze..."):
                time.sleep(1.5) 
                res = requests.get(f"{SCRIPT_URL}?action=login&mobil={m}&heslo={h}", timeout=20).json()
                
            if res.get("status") == "success":
                st.session_state['user'] = res
                st.success("Overené. Vitajte!")
                time.sleep(1.5) 
                st.rerun()
            else:
                st.error("Nesprávne údaje.")
        except:
            st.error("Server je momentálne zaneprázdnený. Skúste prosím kliknúť znova.")

# --- 3. DASHBOARD ---
else:
    u = st.session_state['user']
    st.sidebar.title(f"👤 {u.get('meno', 'Užívateľ')}")
    st.sidebar.info(f"Rola: {u['rola'].upper()} | Región: {u.get('pobocka_id', 'LIPTOV')}")
    
    if st.sidebar.button("Odhlásiť sa", use_container_width=True):
        st.session_state['user'] = None
        st.rerun()

    try:
        # Načítanie dát s ošetrením chýb
        resp = requests.get(f"{SCRIPT_URL}?action=getZakazky", timeout=20)
        df = pd.DataFrame(resp.json())
        
        if df.empty:
            st.info("Databáza neobsahuje žiadne záznamy.")
            st.stop()

        # Prevod dát a formátovanie stavu
        df['suma_zakazky'] = pd.to_numeric(df['suma_zakazky'], errors='coerce').fillna(0.0)
        df['provizia_odporucatel'] = pd.to_numeric(df['provizia_odporucatel'], errors='coerce').fillna(0.0)
        df['vyplatene_bool'] = df['vyplatene'].astype(str).str.upper() == 'TRUE'
        df['Stav'] = df['vyplatene_bool'].apply(lambda x: "Vyplatené ✅" if x else "Čaká ⏳")

        # --- SEKCIA: ADMIN & SUPERADMIN ---
        if u['rola'] in ['admin', 'superadmin']:
            st.title(f"📊 Správa - {u.get('pobocka_id', 'LIPTOV')}")

            # Filter pre región
            active_df = df if u['rola'] == 'superadmin' else df[df['pobocka_id'] == u['pobocka_id']]

            # 1. BLOK: NACENENIE (Tu zadávaš sumu, ak zmizla alebo je 0)
            st.subheader("📩 Zákazky na nacenenie")
            k_naceneniu = active_df[active_df['suma_zakazky'] <= 0]
            if not k_naceneniu.empty:
                for i, row in k_naceneniu.iterrows():
                    with st.expander(f"📌 Potrebné naceniť: {row['poznamka']}"):
                        nova_suma = st.number_input(f"Zadaj sumu pre: {row['kod_pouzity']}", key=f"s_{i}", min_value=0.0)
                        if st.button("Uložiť cenu", key=f"b_{i}"):
                            if call_script("updateSuma", {"row_index": row['row_index'], "suma": nova_suma}):
                                st.success("Cena uložená.")
                                time.sleep(1)
                                st.rerun()
            else:
                st.write("Žiadne nové zákazky na nacenenie.")

            st.divider()

            # 2. BLOK: VÝPLATY (Zoskupené podľa získateľov)
            st.subheader("💳 Prehľad k výplate (podľa partnerov)")
            k_vyplate = active_df[(active_df['suma_zakazky'] > 0) & (~active_df['vyplatene_bool'])]
            
            if not k_vyplate.empty:
                for p_kod in k_vyplate['kod_pouzity'].unique():
                    p_data = k_vyplate[k_vyplate['kod_pouzity'] == p_kod]
                    suma_celkom = p_data['provizia_odporucatel'].sum()
                    
                    with st.expander(f"👤 {p_data['partner_meno'].iloc[0]} ({p_kod}) | Spolu: **{suma_celkom:.2f} €**"):
                        st.table(p_data[['poznamka', 'provizia_odporucatel', 'Stav']].rename(columns={
                            'poznamka': 'Zákazník / Poznámka',
                            'provizia_odporucatel': 'Provízia (€)'
                        }))
                        if st.button(f"Všetko vyplatené pre {p_kod}", key=f"all_{p_kod}"):
                            for idx in p_data['row_index']:
                                call_script("markAsPaid", {"row_index": idx})
                            st.rerun()
            else:
                st.info("Všetky provízie v tomto regióne sú spracované.")

        # --- SEKCIA: PARTNER (Zákazník) ---
        else:
            st.title(f"💰 Váš prehľad ({u.get('kod', '---')})")
            my_df = df[df['kod_pouzity'] == u['kod']].copy()
            
            c1, c2 = st.columns(2)
            c1.metric("Zárobok celkovo", f"{my_df['provizia_odporucatel'].sum():.2f} €")
            cakajuce = my_df[~my_df['vyplatene_bool']]['provizia_odporucatel'].sum()
            c2.metric("Na vyplatenie", f"{cakajuce:.2f} €")
            
            st.subheader("Zoznam odporúčaní")
            st.table(my_df[['poznamka', 'provizia_odporucatel', 'Stav']].rename(columns={
                'poznamka': 'Zákazka',
                'provizia_odporucatel': 'Provízia',
                'Stav': 'Status výplaty'
            }))

    except Exception:
        st.error("Chyba pri komunikácii s Google Tabuľkou. Prosím, obnovte stránku (F5).")
