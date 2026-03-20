import streamlit as st
import pandas as pd
import requests
import json

# --- 1. KONFIGURÁCIA ---
# SEM VLOŽ SVOJU URL (Skontroluj, či neobsahuje medzery na začiatku/konci)
SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzLxqt5QwUvu2zha5NEOg97-7NtPLTbhMd2YQ3ORV6YRny7SvMZwBSgVQ6Zyd3u9v-IKw/exec"

st.set_page_config(page_title="Diagnostika TEPUJEM", page_icon="🔍", layout="wide")

if 'user' not in st.session_state:
    st.session_state['user'] = None

# --- DIAGNOSTICKÁ FUNKCIA ---
def debug_request(url):
    st.info(f"Odosielam požiadavku na: {url}")
    try:
        response = requests.get(url, timeout=15)
        st.write(f"Kód odpovede: {response.status_code}")
        
        # Pokus o zobrazenie surového textu odpovede
        try:
            data = response.json()
            st.success("Server vrátil platný JSON.")
            return data
        except json.JSONDecodeError:
            st.error("Server nevrátil JSON formát!")
            with st.expander("Zobraziť surovú odpoveď servera"):
                st.code(response.text)
            return None
    except requests.exceptions.MissingSchema:
        st.error("Chyba: SCRIPT_URL nemá platný formát (chýba https://).")
    except requests.exceptions.ConnectionError:
        st.error("Chyba: Nepodarilo sa nadviazať spojenie so serverom.")
    except Exception as e:
        st.error(f"Neočakávaná chyba: {e}")
    return None

# --- 2. PRIHLASOVANIE ---
if st.session_state['user'] is None:
    st.title("💰 Provízny systém (Režim ladenia)")
    
    m = st.text_input("Mobil").strip()
    h = st.text_input("Heslo", type="password").strip()
    
    if st.button("Prihlásiť sa a spustiť test", use_container_width=True):
        test_url = f"{SCRIPT_URL}?action=login&mobil={m}&heslo={h}"
        res = debug_request(test_url)
        
        if res and res.get("status") == "success":
            st.session_state['user'] = res
            st.success("Prihlásenie úspešné! Presmerúvam...")
            st.rerun()
        elif res:
            st.warning(f"Server odpovedal, ale prihlásenie zlyhalo: {res.get('message', 'Neznámy dôvod')}")

# --- 3. DASHBOARD ---
else:
    u = st.session_state['user']
    st.sidebar.title(f"👤 {u.get('meno', 'Užívateľ')}")
    if st.sidebar.button("Odhlásiť sa"):
        st.session_state['user'] = None
        st.rerun()

    st.title("Dáta z tabuľky")
    if st.button("Testovať načítanie zákaziek"):
        zakazky_url = f"{SCRIPT_URL}?action=getZakazky"
        data = debug_request(zakazky_url)
        if data:
            df = pd.DataFrame(data)
            
            # Premenovanie stĺpcov podľa požiadavky
            if not df.empty and 'poznamka' in df.columns:
                df = df.rename(columns={
                    'poznamka': 'Objednávka',
                    'provizia_odporucatel': 'Získaná provízia'
                })
            
            st.write("Výsledná tabuľka:")
            st.dataframe(df)
