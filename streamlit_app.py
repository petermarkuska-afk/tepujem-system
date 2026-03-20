import streamlit as st
import pandas as pd
import requests

# --- 1. KONFIGURÁCIA ---
# SEM MUSÍŠ VLOŽIŤ SVOJU URL (končí sa na /exec)
SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzLxqt5QwUvu2zha5NEOg97-7NtPLTbhMd2YQ3ORV6YRny7SvMZwBSgVQ6Zyd3u9v-IKw/exec"

st.set_page_config(page_title="TEPUJEM Portál", page_icon="💰", layout="wide")

if 'user' not in st.session_state:
    st.session_state['user'] = None

# Pomocná funkcia na komunikáciu s databázou
def call_script(action, params):
    try:
        url = f"{SCRIPT_URL}?action={action}"
        for k, v in params.items(): url += f"&{k}={v}"
        res = requests.get(url, timeout=10)
        return res.json().get("status") == "success"
    except:
        return False

# --- 2. PRIHLASOVANIE A REGISTRÁCIA ---
if st.session_state['user'] is None:
    st.title("💰 Provízny systém TEPUJEM")
    tab1, tab2 = st.tabs(["Prihlásenie", "Registrácia"])
    
    with tab1:
        m = st.text_input("Mobil (prihlasovacie meno)").strip()
        h = st.text_input("Heslo", type="password").strip()
        if st.button("Prihlásiť sa", use_container_width=True):
            try:
                res = requests.get(f"{SCRIPT_URL}?action=login&mobil={m}&heslo={h}", timeout=10).json()
                if res.get("status") == "success":
                    st.session_state['user'] = res
                    st.rerun()
                else: 
                    st.error("Nesprávne údaje.")
            except: 
                st.error("Chyba pripojenia k databáze. Skontrolujte SCRIPT_URL.")
            
    with tab2:
        st.subheader("Nový partnerský účet")
        with st.form("reg_form"):
            meno = st.text_input("Meno")
            prie = st.text_input("Priezvisko")
            mob = st.text_input("Mobil")
            hes = st.text_input("Heslo", type="password")
            kod = st.text_input("Váš unikátny kód (napr. JOZO5)")
            if st.form_submit_button("Vytvoriť účet", use_container_width=True):
                payload = {"target": "user", "meno": meno, "priezvisko": prie, "mobil": mob, "heslo": hes, "referral_code": kod}
                try:
                    requests.post(SCRIPT_URL, json=payload, timeout=10)
                    st.success("Registrácia úspešná! Môžete sa prihlásiť.")
                except:
                    st.error("Chyba pri registrácii.")

# --- 3. DASHBOARD (Po prihlásení) ---
else:
    u = st.session_state['user']
    st.sidebar.title(f"👤 {u.get('meno', 'Užívateľ')}")
    if st.sidebar.button("Odhlásiť sa", use_container_width=True):
        st.session_state['user'] = None
        st.rerun()

    try:
        # Načítanie dát z Google Tabuľky
        res = requests.get(f"{SCRIPT_URL}?action=getZakazky", timeout=15).json()
        df = pd.DataFrame(res)
        
        if not df.empty:
            for col in ['suma_zakazky', 'provizia_odporucatel']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

        # Zobrazenie pre Partnera (Zakaznik)
        if u['rola'] not in ['superadmin', 'admin']:
            st.title(f"💰 Váš prehľad ({u.get('kod', '---')})")
            my_df = df[df['kod_pouzity'] == u['kod']].copy()
            
            c1, c2 = st.columns(2)
            c1.metric("Celkový zárobok", f"{my_df['provizia_odporucatel'].sum():.2f} €")
            c2.metric("Na vyplatenie", f"{my_df[my_df['vyplatene'] == False]['provizia_odporucatel'].sum():.2f} €")
            
            st.subheader("Zoznam odporúčaných zákaziek")
            if not my_df.empty:
                # Premenovanie podľa požiadavky
                display_df = my_df.copy()
                display_df = display_df.rename(columns={
                    'poznamka': 'Objednávka',
                    'provizia_odporucatel': 'Získaná provízia'
                })
                display_df['Stav'] = display_df['vyplatene'].apply(lambda x: "✅ Vyplatené" if x else "⏳ Čaká")
                
                # Skryjeme pobocka_id a suma_zakazky
                st.table(display_df[['Objednávka', 'Získaná provízia', 'Stav']])
            else:
                st.info("Zatiaľ žiadne záznamy.")

        # Zobrazenie pre Superadmina (Peter)
        elif u['rola'] == 'superadmin':
            st.title("🌍 Správa výplat")
            if not df.empty:
                df['Stav'] = df['vyplatene'].apply(lambda x: "✅ Vyplatené" if x else "⏳ Čaká")
                st.dataframe(df[['kod_pouzity', 'partner_meno', 'suma_zakazky', 'provizia_odporucatel', 'poznamka', 'Stav']], use_container_width=True)

    except Exception as e:
        st.error(f"Nepodarilo sa načítať dáta. (Chyba: {e})")
