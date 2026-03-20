import streamlit as st
import pandas as pd
import requests
import json

# --- 1. KONFIGURÁCIA ---
# SEM VLOŽ SVOJU NAJNOVŠIU URL Z GOOGLE APPS SCRIPTU (Z nového Deploymentu)
SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzLxqt5QwUvu2zha5NEOg97-7NtPLTbhMd2YQ3ORV6YRny7SvMZwBSgVQ6Zyd3u9v-IKw/exec"

st.set_page_config(page_title="TEPUJEM Portál", page_icon="💰", layout="wide")

if 'user' not in st.session_state:
    st.session_state['user'] = None

# --- 2. POMOCNÉ FUNKCIE ---
def update_suma(row_index, nova_suma):
    """Odošle novú sumu - Google Script automaticky dopočíta 5% províziu"""
    try:
        url = f"{SCRIPT_URL}?action=updateSuma&row_index={row_index}&suma={nova_suma}"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            return res.json().get("status") == "success"
        else:
            st.error(f"Chyba pri zápise: Google vrátil kód {res.status_code}")
            return False
    except Exception as e:
        st.error(f"Chyba pripojenia pri zápise: {e}")
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
                # --- TESTOVACIA DIAGNOSTIKA ---
                login_url = f"{SCRIPT_URL}?action=login&mobil={m}&heslo={h}"
                res = requests.get(login_url, timeout=15)
                
                if res.status_code != 200:
                    st.error(f"❌ KRITICKÁ CHYBA: Google Script vrátil kód {res.status_code}")
                    with st.expander("Zobraziť technický detail chyby"):
                        st.code(res.text)
                        st.write("Skontrolujte, či je v Deployment nastavené 'Anyone' a nie 'Only myself'.")
                else:
                    try:
                        r = res.json()
                        if r.get("status") == "success":
                            st.session_state['user'] = r
                            st.success("✅ Prihlásenie úspešné!")
                            st.rerun()
                        else: 
                            st.error("❌ Nesprávne telefónne číslo alebo heslo.")
                    except json.JSONDecodeError:
                        st.error("❌ Google Script nevrátil JSON formát. Pravdepodobne chyba v Apps Scripte.")
                        st.code(res.text)
            
            except Exception as e: 
                st.error(f"❌ Nepodarilo sa vôbec spojiť s URL. Skontrolujte internet a SCRIPT_URL.")
                st.info(f"Detail chyby: {e}")
            
    with tab2:
        st.subheader("Nový partnerský účet")
        with st.form("reg_form"):
            meno = st.text_input("Meno")
            prie = st.text_input("Priezvisko")
            mob = st.text_input("Mobil")
            hes = st.text_input("Heslo")
            kod = st.text_input("Váš unikátny kód (napr. JOZO5)")
            if st.form_submit_button("Vytvoriť účet", use_container_width=True):
                payload = {"target": "user", "meno": meno, "priezvisko": prie, "adresa": "", "mobil": mob, "heslo": hes, "referral_code": kod}
                try:
                    res_reg = requests.post(SCRIPT_URL, json=payload, timeout=10)
                    if res_reg.status_code == 200:
                        st.success("✅ Registrácia úspešná! Teraz sa môžete prihlásiť.")
                    else:
                        st.error(f"Chyba pri registrácii (Kód {res_reg.status_code})")
                except:
                    st.error("Chyba spojenia pri registrácii.")

# --- 4. DASHBOARD (Po prihlásení) ---
else:
    u = st.session_state['user']
    st.sidebar.title(f"👤 {u.get('meno', 'Užívateľ')}")
    st.sidebar.info(f"Rola: {u['rola'].upper()}")
    
    if st.sidebar.button("Odhlásiť sa", use_container_width=True):
        st.session_state['user'] = None
        st.rerun()

    try:
        # Načítanie dát so zahrnutím mena a mobilu partnera
        res = requests.get(f"{SCRIPT_URL}?action=getZakazky", timeout=15)
        raw_data = res.json()
        
        if not raw_data:
            df = pd.DataFrame(columns=['pobocka_id', 'kod_pouzity', 'partner_meno', 'partner_mobil', 'suma_zakazky', 'provizia_odporucatel', 'row_index'])
        else:
            df = pd.DataFrame(raw_data)
            # Konverzia na čísla
            for col in ['suma_zakazky', 'provizia_odporucatel']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

        # --- SEKCIA A: SUPERADMIN ---
        if u['rola'] == 'superadmin':
            st.title("🌍 Globálny prehľad")
            st.write("### 📋 Všetky transakcie")
            st.dataframe(df[['pobocka_id', 'kod_pouzity', 'partner_meno', 'partner_mobil', 'suma_zakazky', 'provizia_odporucatel', 'poznamka']], use_container_width=True)
            
            st.divider()
            st.subheader("📊 Mesačné podklady pre výplaty")
            if not df.empty and 'partner_meno' in df.columns:
                sum_df = df.groupby(['partner_meno', 'partner_mobil', 'kod_pouzity']).agg({'provizia_odporucatel': 'sum', 'pobocka_id': 'count'}).reset_index()
                sum_df.columns = ['Partner', 'Mobil', 'Kód', 'Suma na výplatu (€)', 'Zákaziek']
                st.dataframe(sum_df.sort_values(by='Suma na výplatu (€)', ascending=False), use_container_width=True)
                
                csv = sum_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 Stiahnuť výplatnú listinu (CSV)", data=csv, file_name="vyplaty.csv", mime="text/csv")

        # --- SEKCIA B: ADMIN ---
        elif u['rola'] == 'admin':
            moje_mesto = str(u.get('pobocka_id', ''))
            st.title(f"📍 Pobočka: {moje_mesto}")
            f_df = df[df['pobocka_id'].astype(str) == moje_mesto].copy()
            
            nove = f_df[f_df['suma_zakazky'] == 0]
            vybavene = f_df[f_df['suma_zakazky'] > 0]
            
            st.subheader("📩 Objednávky na nacenenie")
            for i, row in nove.iterrows():
                with st.expander(f"Kód: {row['kod_pouzity']} | Partner: {row.get('partner_meno', 'Neznámy')}"):
                    s_val = st.number_input(f"Zadaj sumu (€)", key=f"s_{i}", min_value=0.0, step=1.0)
                    if st.button("Uložiť sumu", key=f"b_{i}"):
                        if update_suma(row['row_index'], s_val):
                            st.success("✅ Úspešne uložené!")
                            st.rerun()

            st.subheader("✅ História")
            st.dataframe(vybavene[['kod_pouzity', 'partner_meno', 'suma_zakazky', 'provizia_odporucatel', 'poznamka']], use_container_width=True)

        # --- SEKCIA C: PARTNER ---
        else:
            st.title(f"💰 Váš partnerský účet ({u.get('kod', '---')})")
            my_df = df[df['kod_pouzity'].astype(str) == str(u.get('kod', ''))].copy()
            st.metric("Váš doterajší zárobok", f"{my_df['provizia_odporucatel'].sum():.2f} €")
            st.subheader("Prehľad provízií")
            st.table(my_df[['pobocka_id', 'suma_zakazky', 'provizia_odporucatel']])

    except Exception as e:
        st.error(f"Chyba pri spracovaní dát: {e}")
