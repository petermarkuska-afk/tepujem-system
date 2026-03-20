import streamlit as st
import pandas as pd
import requests

# --- 1. KONFIGURÁCIA ---
# SEM VLOŽ SVOJU NAJNOVŠIU URL Z GOOGLE APPS SCRIPTU
SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzLxqt5QwUvu2zha5NEOg97-7NtPLTbhMd2YQ3ORV6YRny7SvMZwBSgVQ6Zyd3u9v-IKw/exec"

st.set_page_config(page_title="TEPUJEM Portál", page_icon="💰", layout="wide")

# Inicializácia session state
if 'user' not in st.session_state:
    st.session_state['user'] = None

# --- 2. POMOCNÉ FUNKCIE ---
def update_suma(row_index, nova_suma):
    """Odošle novú sumu do Google Scriptu - ten automaticky dopočíta 5% províziu"""
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
        m = st.text_input("Mobil (prihlasovacie meno)").strip()
        h = st.text_input("Heslo", type="password").strip()
        if st.button("Prihlásiť sa", use_container_width=True):
            try:
                r = requests.get(f"{SCRIPT_URL}?action=login&mobil={m}&heslo={h}", timeout=10).json()
                if r["status"] == "success":
                    st.session_state['user'] = r
                    st.success("Prihlásenie úspešné!")
                    st.rerun()
                else: 
                    st.error("Nesprávne telefónne číslo alebo heslo.")
            except: 
                st.error("Chyba pripojenia k databáze. Skontrolujte SCRIPT_URL.")
            
    with tab2:
        st.subheader("Nový partnerský účet")
        with st.form("reg_form"):
            meno = st.text_input("Meno")
            prie = st.text_input("Priezvisko")
            mob = st.text_input("Mobil (napr. 905123456)")
            hes = st.text_input("Heslo")
            kod = st.text_input("Váš unikátny kód (napr. JOZO5)")
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
        
        if not raw_data or len(raw_data) == 0:
            df = pd.DataFrame(columns=['pobocka_id', 'kod_pouzity', 'partner_meno', 'partner_mobil', 'suma_zakazky', 'provizia_odporucatel', 'zlava_novy', 'poznamka', 'row_index'])
        else:
            df = pd.DataFrame(raw_data)
            # Konverzia na čísla pre výpočty a metriky
            for col in ['suma_zakazky', 'provizia_odporucatel', 'zlava_novy']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

        # --- SEKCIA A: SUPERADMIN (PETER) ---
        if u['rola'] == 'superadmin':
            st.title("🌍 Globálny prehľad (Superadmin)")
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Celkový obrat", f"{df['suma_zakazky'].sum():.2f} €")
            c2.metric("Počet zákaziek", len(df))
            c3.metric("Provízie na výplatu", f"{df['provizia_odporucatel'].sum():.2f} €")
            
            st.write("### 📋 Detailný zoznam všetkých transakcií")
            # Zobrazenie s menom partnera a mobilom
            st.dataframe(df[['pobocka_id', 'kod_pouzity', 'partner_meno', 'partner_mobil', 'suma_zakazky', 'provizia_odporucatel', 'poznamka']], use_container_width=True)

            st.divider()
            st.subheader("📊 Mesačné vyúčtovanie pre partnerov")
            if not df.empty:
                # Zoskupenie podľa partnera pre výplaty
                sum_df = df.groupby(['partner_meno', 'partner_mobil', 'kod_pouzity']).agg({
                    'provizia_odporucatel': 'sum',
                    'pobocka_id': 'count'
                }).reset_index()
                sum_df.columns = ['Meno partnera', 'Mobil', 'Kód', 'Suma na výplatu (€)', 'Počet zakázok']
                st.dataframe(sum_df.sort_values(by='Suma na výplatu (€)', ascending=False), use_container_width=True)
                
                # Tlačidlo na stiahnutie (CSV)
                csv = sum_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 Stiahnuť podklady pre výplaty (CSV)", data=csv, file_name="vyplatny_list.csv", mime="text/csv")

        # --- SEKCIA B: ADMIN (POBOČKY) ---
        elif u['rola'] == 'admin':
            moje_mesto = str(u.get('pobocka_id', ''))
            st.title(f"📍 Pobočka: {moje_mesto}")
            
            f_df = df[df['pobocka_id'].astype(str) == moje_mesto].copy()
            
            if f_df.empty:
                st.info("Zatiaľ žiadne pridelené zakázky.")
            else:
                nove = f_df[f_df['suma_zakazky'] == 0]
                vybavene = f_df[f_df['suma_zakazky'] > 0]
                
                st.subheader("📩 Nové objednávky (Zadajte sumu)")
                for i, row in nove.iterrows():
                    with st.expander(f"Kód: {row['kod_pouzity']} | Partner: {row['partner_meno']} | Info: {row['poznamka']}"):
                        col1, col2 = st.columns([3, 1])
                        s_val = col1.number_input(f"Suma za tepovanie (€)", key=f"s_{i}", min_value=0.0, step=5.0)
                        if col2.button("Potvrdiť a uložiť", key=f"b_{i}"):
                            if s_val > 0:
                                if update_suma(row['row_index'], s_val):
                                    st.success("Suma a provízia zapísaná!")
                                    st.rerun()
                                else: st.error("Chyba pri zápise.")
                            else: st.warning("Zadajte platnú sumu.")

                st.subheader("✅ História pobočky")
                st.dataframe(vybavene[['kod_pouzity', 'partner_meno', 'suma_zakazky', 'provizia_odporucatel', 'poznamka']], use_container_width=True)

        # --- SEKCIA C: PARTNER / ZÁKAZNÍK ---
        else:
            st.title(f"💰 Váš partnerský účet ({u.get('kod', '---')})")
            my_df = df[df['kod_pouzity'].astype(str) == str(u.get('kod', ''))].copy()
            
            c1, c2 = st.columns(2)
            c1.metric("Váš doterajší zárobok", f"{my_df['provizia_odporucatel'].sum():.2f} €")
            c2.metric("Počet úspešných odporúčaní", len(my_df))
            
            st.subheader("Zoznam vašich provízií")
            if not my_df.empty:
                st.table(my_df[['pobocka_id', 'suma_zakazky', 'provizia_odporucatel']])
            else:
                st.info("Zatiaľ žiadne odporúčania.")

    except Exception as e:
        st.error(f"Nepodarilo sa spracovať dáta: {e}")
