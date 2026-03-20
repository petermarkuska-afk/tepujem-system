import streamlit as st
import pandas as pd
import requests
import time

# --- 1. KONFIGURÁCIA ---
# Vlož svoju overenú URL z Google Apps Scriptu
SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzLxqt5QwUvu2zha5NEOg97-7NtPLTbhMd2YQ3ORV6YRny7SvMZwBSgVQ6Zyd3u9v-IKw/exec"

st.set_page_config(page_title="TEPUJEM Portál", page_icon="💰", layout="wide")

# Inicializácia session stavov
if 'user' not in st.session_state:
    st.session_state['user'] = None

# Pomocná funkcia na volanie API (zápis dát)
def call_script(action, params):
    try:
        url = f"{SCRIPT_URL}?action={action}"
        for k, v in params.items(): url += f"&{k}={v}"
        res = requests.get(url, timeout=10).json()
        return res.get("status") == "success"
    except Exception:
        return False

# --- 2. PRIHLASOVANIE ---
if st.session_state['user'] is None:
    st.title("💰 Provízny systém TEPUJEM")
    
    with st.container():
        m = st.text_input("Mobil (prihlasovacie meno)", key="login_phone").strip()
        h = st.text_input("Heslo", type="password", key="login_pass").strip()
        
        if st.button("Prihlásiť sa", use_container_width=True):
            if not m or not h:
                st.warning("Prosím, vyplňte mobil a heslo.")
            else:
                try:
                    # Volanie prihlasovacieho skriptu
                    response = requests.get(f"{SCRIPT_URL}?action=login&mobil={m}&heslo={h}", timeout=15)
                    res = response.json()
                    
                    if res.get("status") == "success":
                        st.session_state['user'] = res
                        st.success("Prihlásenie úspešné! Pripravujem dashboard...")
                        time.sleep(1) # Krátka pauza pre stabilitu
                        st.rerun()
                    else:
                        st.error("Nesprávne údaje.")
                except Exception as e:
                    st.error("Chyba pripojenia. Skontrolujte SCRIPT_URL alebo internet.")

# --- 3. DASHBOARD (Po úspešnom prihlásení) ---
else:
    u = st.session_state['user']
    st.sidebar.title(f"👤 {u.get('meno', 'Užívateľ')}")
    if st.sidebar.button("Odhlásiť sa", use_container_width=True):
        st.session_state['user'] = None
        st.rerun()

    try:
        # Načítanie dát zákaziek
        resp = requests.get(f"{SCRIPT_URL}?action=getZakazky", timeout=15)
        df = pd.DataFrame(resp.json())
        
        if df.empty:
            df = pd.DataFrame(columns=['pobocka_id', 'kod_pouzity', 'suma_zakazky', 'provizia_odporucatel', 'poznamka', 'vyplatene', 'row_index'])

        for col in ['suma_zakazky', 'provizia_odporucatel']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

        # ROZHRANIE PRE ADMINA (Peter)
        if u['rola'] in ['superadmin', 'admin']:
            st.title("🌍 Správa systému")
            st.subheader("📋 Prehľad všetkých zákaziek")
            admin_df = df.copy()
            admin_df['Stav'] = admin_df['vyplatene'].apply(lambda x: "✅ Vyplatené" if str(x).upper() == 'TRUE' else "⏳ Čaká")
            st.dataframe(admin_df[['pobocka_id', 'kod_pouzity', 'suma_zakazky', 'provizia_odporucatel', 'poznamka', 'Stav']], use_container_width=True)

        # ROZHRANIE PRE PARTNERA (Zákazník)
        else:
            st.title(f"💰 Váš partnerský prehľad ({u.get('kod', '---')})")
            my_df = df[df['kod_pouzity'] == u['kod']].copy()
            
            c1, c2 = st.columns(2)
            c1.metric("Váš celkový zárobok", f"{my_df['provizia_odporucatel'].sum():.2f} €")
            # Výpočet sumy na vyplatenie
            cakajuce = my_df[my_df['vyplatene'].astype(str).str.upper() != 'TRUE']['provizia_odporucatel'].sum()
            c2.metric("Aktuálne na vyplatenie", f"{cakajuce:.2f} €")
            
            st.subheader("Zoznam odporúčaných zákaziek")
            if not my_df.empty:
                display_df = my_df.copy()
                # Premenovanie podľa zadania
                display_df = display_df.rename(columns={'poznamka': 'Objednávka', 'provizia_odporucatel': 'Získaná provízia'})
                display_df['Stav'] = display_df['vyplatene'].apply(lambda x: "✅ Vyplatené" if str(x).upper() == 'TRUE' else "⏳ Čaká")
                st.table(display_df[['Objednávka', 'Získaná provízia', 'Stav']])
            else:
                st.info("Zatiaľ žiadne záznamy.")

    except Exception:
        st.error("Chyba pri načítavaní dát z Google tabuľky.")
