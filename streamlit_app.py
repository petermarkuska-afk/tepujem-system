import streamlit as st
import pandas as pd
import requests

# --- 1. KONFIGURÁCIA ---
# SEM VLOŽ SVOJU AKTUÁLNU URL Z GOOGLE APPS SCRIPTU
SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzLxqt5QwUvu2zha5NEOg97-7NtPLTbhMd2YQ3ORV6YRny7SvMZwBSgVQ6Zyd3u9v-IKw/exec"

st.set_page_config(page_title="TEPUJEM Portál", page_icon="💰", layout="wide")

# Inicializácia session state
if 'user' not in st.session_state:
    st.session_state['user'] = None

# --- 2. POMOCNÉ FUNKCIE ---
def update_suma(row_index, nova_suma):
    """Odošle novú sumu do Google Scriptu"""
    try:
        url = f"{SCRIPT_URL}?action=updateSuma&row_index={row_index}&suma={nova_suma}"
        r = requests.get(url, timeout=10).json()
        return r.get("status") == "success"
    except Exception as e:
        st.error(f"Chyba pripojenia: {e}")
        return False

# --- 3. PRIHLASOVANIE A REGISTRÁCIA ---
if st.session_state['user'] is None:
    st.title("💰 Provízny systém TEPUJEM")
    tab1, tab2 = st.tabs(["Prihlásenie", "Registrácia"])
    
    with tab1:
        m = st.text_input("Mobil (login)").strip()
        h = st.text_input("Heslo", type="password").strip()
        if st.button("Prihlásiť sa", use_container_width=True):
            try:
                r = requests.get(f"{SCRIPT_URL}?action=login&mobil={m}&heslo={h}", timeout=10).json()
                if r["status"] == "success":
                    st.session_state['user'] = r
                    st.success("Prihlásenie úspešné!")
                    st.rerun()
                else: 
                    st.error("Nesprávne údaje.")
            except: 
                st.error("Nepodarilo sa pripojiť k databáze. Skontroluj SCRIPT_URL.")
            
    with tab2:
        st.subheader("Nový partnerský účet")
        with st.form("reg"):
            meno = st.text_input("Meno")
            prie = st.text_input("Priezvisko")
            mob = st.text_input("Mobil (napr. 905111222)")
            hes = st.text_input("Heslo")
            kod = st.text_input("Váš kód (napr. JOZO5)")
            if st.form_submit_button("Vytvoriť účet", use_container_width=True):
                payload = {"target": "user", "meno": meno, "priezvisko": prie, "adresa": "", "mobil": mob, "heslo": hes, "referral_code": kod}
                try:
                    requests.post(SCRIPT_URL, json=payload, timeout=10)
                    st.success("Registrácia úspešná! Teraz sa prihláste.")
                except:
                    st.error("Chyba pri registrácii.")

# --- 4. DASHBOARD (Po prihlásení) ---
else:
    u = st.session_state['user']
    st.sidebar.title(f"👤 {u.get('meno', 'Užívateľ')}")
    st.sidebar.info(f"Rola: {u['rola'].upper()}")
    
    if st.sidebar.button("Odhlásiť sa", use_container_width=True):
        st.session_state['user'] = None
        st.rerun()

    try:
        # Načítanie dát
        res = requests.get(f"{SCRIPT_URL}?action=getZakazky", timeout=10)
        raw_data = res.json()
        
        # Ošetrenie prázdnej databázy
        if not raw_data or len(raw_data) == 0:
            df = pd.DataFrame(columns=['pobocka_id', 'kod_pouzity', 'suma_zakazky', 'provizia_odporucatel', 'zlava_novy', 'poznamka', 'row_index'])
        else:
            df = pd.DataFrame(raw_data)
            # Prevod stĺpcov na čísla pre výpočty
            for col in ['suma_zakazky', 'provizia_odporucatel', 'zlava_novy']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

        # --- SEKCIA A: SUPERADMIN ---
        if u['rola'] == 'superadmin':
            st.title("🌍 Globálny prehľad (Superadmin)")
            c1, c2, c3 = st.columns(3)
            c1.metric("Celkový obrat", f"{df['suma_zakazky'].sum():.2f} €")
            c2.metric("Počet zákaziek", len(df))
            c3.metric("Provízie spolu", f"{df['provizia_odporucatel'].sum():.2f} €")
            
            st.write("### Detailná tabuľka")
            st.dataframe(df, use_container_width=True)

            st.divider()
            st.subheader("📊 Provízie podľa partnerov")
            if not df.empty:
                sum_df = df.groupby('kod_pouzity').agg({'suma_zakazky':'sum', 'provizia_odporucatel':'sum', 'pobocka_id':'count'}).reset_index()
                sum_df.columns = ['Kód partnera', 'Obrat (€)', 'Provízia (€)', 'Počet zakázok']
                st.dataframe(sum_df, use_container_width=True)

        # --- SEKCIA B: ADMIN (Pobočky) ---
        elif u['rola'] == 'admin':
            moje_mesto = str(u.get('pobocka_id', ''))
            st.title(f"📍 Regionálna pobočka: {moje_mesto}")
            
            f_df = df[df['pobocka_id'].astype(str) == moje_mesto].copy()
            
            if f_df.empty:
                st.info("Momentálne nemáte žiadne pridelené zakázky.")
            else:
                nove = f_df[f_df['suma_zakazky'] == 0]
                vybavene = f_df[f_df['suma_zakazky'] > 0]
                
                st.subheader("📩 Nové objednávky na spracovanie")
                if nove.empty:
                    st.success("Všetko je vybavené!")
                else:
                    for i, row in nove.iterrows():
                        with st.expander(f"Kód: {row['kod_pouzity']} | Info: {row['poznamka']}"):
                            col1, col2 = st.columns([3, 1])
                            s_val = col1.number_input(f"Zadaj sumu za tepovanie (€)", key=f"s_{i}", min_value=0.0, step=5.0)
                            if col2.button("Uložiť", key=f"b_{i}"):
                                if s_val > 0:
                                    if update_suma(row['row_index'], s_val):
                                        st.success("Suma bola uložená!")
                                        st.rerun()
                                    else: st.error("Chyba pri zápise.")
                                else: st.warning("Zadaj platnú sumu.")

                st.subheader("✅ História vybavených zakázok")
                st.dataframe(vybavene[['kod_pouzity', 'suma_zakazky', 'provizia_odporucatel', 'poznamka']], use_container_width=True)

        # --- SEKCIA C: PARTNER / ZÁKAZNÍK ---
        else:
            st.title(f"💰 Váš partnerský účet ({u.get('kod', '---')})")
            my_df = df[df['kod_pouzity'].astype(str) == str(u.get('kod', ''))].copy()
            
            c1, c2 = st.columns(2)
            c1.metric("Váš zárobok", f"{my_df['provizia_odporucatel'].sum():.2f} €")
            c2.metric("Počet odporúčaní", len(my_df))
            
            st.subheader("Prehľad vašich provízií")
            if not my_df.empty:
                st.table(my_df[['pobocka_id', 'suma_zakazky', 'provizia_odporucatel']])
            else:
                st.info("Zatiaľ nemáte žiadne odporúčania. Zdieľajte svoj kód!")

    except Exception as e:
        st.error(f"Dáta nie sú dostupné alebo tabuľka neexistuje. (Chyba: {e})")
