import streamlit as st
import pandas as pd
import requests

# --- 1. KONFIGURÁCIA ---
# Nezabudni sem vložiť svoju aktuálnu URL z Google Apps Scriptu
SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzLxqt5QwUvu2zha5NEOg97-7NtPLTbhMd2YQ3ORV6YRny7SvMZwBSgVQ6Zyd3u9v-IKw/exec"

st.set_page_config(page_title="TEPUJEM Portál", page_icon="💰", layout="wide")

if 'user' not in st.session_state:
    st.session_state['user'] = None

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
                st.error("Chyba pripojenia. Skontrolujte SCRIPT_URL.")
            
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
                    st.success("Registrácia úspešná! Teraz sa môžete prihlásiť.")
                except:
                    st.error("Chyba pri registrácii.")

# --- 3. DASHBOARD (Po prihlásení) ---
else:
    u = st.session_state['user']
    st.sidebar.title(f"👤 {u.get('meno', 'Užívateľ')}")
    st.sidebar.info(f"Rola: {u['rola'].upper()}")
    
    if st.sidebar.button("Odhlásiť sa", use_container_width=True):
        st.session_state['user'] = None
        st.rerun()

    try:
        res = requests.get(f"{SCRIPT_URL}?action=getZakazky", timeout=15).json()
        df = pd.DataFrame(res)
        
        # Ošetrenie prázdnej tabuľky
        if df.empty:
            df = pd.DataFrame(columns=['kod_pouzity', 'suma_zakazky', 'provizia_odporucatel', 'poznamka', 'vyplatene'])
        
        # Konverzia na čísla pre výpočty
        for col in ['suma_zakazky', 'provizia_odporucatel']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

        # --- A: SUPERADMIN ---
        if u['rola'] == 'superadmin':
            st.title("🌍 Globálny prehľad (Superadmin)")
            c1, c2, c3 = st.columns(3)
            c1.metric("Celkový obrat", f"{df['suma_zakazky'].sum():.2f} €")
            c2.metric("Počet zákaziek", len(df))
            c3.metric("Provízie spolu", f"{df['provizia_odporucatel'].sum():.2f} €")
            
            st.write("### Všetky transakcie")
            # Superadmin vidí všetko
            st.dataframe(df[['kod_pouzity', 'suma_zakazky', 'provizia_odporucatel', 'poznamka']], use_container_width=True)

        # --- B: ADMIN (Pobočky) ---
        elif u['rola'] == 'admin':
            moje_mesto = str(u.get('pobocka_id', ''))
            st.title(f"📍 Pobočka: {moje_mesto}")
            
            f_df = df[df['pobocka_id'].astype(str) == moje_mesto].copy()
            nove = f_df[f_df['suma_zakazky'] == 0]
            
            st.subheader("📩 Nové zakázky na nacenenie")
            for i, row in nove.iterrows():
                with st.expander(f"Kód: {row['kod_pouzity']} | Info: {row['poznamka']}"):
                    # Adminovi nechávame možnosť zadať sumu
                    st.number_input("Suma (€)", key=f"s_{i}", min_value=0.0)
                    if st.button("Uložiť", key=f"b_{i}"):
                        st.success("Uložené (simulácia)")

            st.subheader("✅ História")
            # Admin vidí sumu, aby mohol kontrolovať zadávanie
            st.dataframe(f_df[f_df['suma_zakazky'] > 0][['kod_pouzity', 'suma_zakazky', 'provizia_odporucatel', 'poznamka']], use_container_width=True)

        # --- C: PARTNER / ZÁKAZNÍK ---
        else:
            st.title(f"💰 Váš partnerský prehľad ({u.get('kod', '---')})")
            my_df = df[df['kod_pouzity'] == u['kod']].copy()
            
            col1, col2 = st.columns(2)
            col1.metric("Celkový zárobok", f"{my_df['provizia_odporucatel'].sum():.2f} €")
            col2.metric("Na vyplatenie", f"{my_df[my_df['vyplatene'] == False]['provizia_odporucatel'].sum():.2f} €")
            
            st.subheader("Zoznam odporúčaných zákaziek")
            if not my_df.empty:
                # Prevod logickej hodnoty na ikonky
                my_df['Stav'] = my_df['vyplatene'].apply(lambda x: "✅ Vyplatené" if x else "⏳ Čaká")
                
                # --- TU JE ZMENA PRENOSU STĹPCOV ---
                # Skryli sme pobocka_id a suma_zakazky.
                # Pridali sme 'poznamka', ktorá sa zvyčajne v Google Sheets importuje z Make.
                st.table(my_df[['poznamka', 'provizia_odporucatel', 'Stav']])
            else:
                st.info("Zatiaľ nemáte žiadne odporúčania.")

    except Exception as e:
        st.error(f"Nepodarilo sa načítať dáta z Google tabuľky. (Chyba: {e})")
