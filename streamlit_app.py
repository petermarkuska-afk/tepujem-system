import streamlit as st
import pandas as pd
import requests

# --- KONFIGURÁCIA ---
# SEM VLOŽ SVOJU NOVÚ URL Z GOOGLE APPS SCRIPTU (Po novom Deployi)
SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzLxqt5QwUvu2zha5NEOg97-7NtPLTbhMd2YQ3ORV6YRny7SvMZwBSgVQ6Zyd3u9v-IKw/exec"

st.set_page_config(page_title="TEPUJEM Portál", page_icon="💰", layout="wide")

# Inicializácia session state
if 'user' not in st.session_state:
    st.session_state['user'] = None

# --- POMOCNÉ FUNKCIE ---
def update_suma(row_index, nova_suma):
    """Odošle novú sumu do Google Scriptu cez GET parameter"""
    try:
        url = f"{SCRIPT_URL}?action=updateSuma&row_index={row_index}&suma={nova_suma}"
        r = requests.get(url, timeout=10).json()
        return r.get("status") == "success"
    except Exception as e:
        st.error(f"Chyba komunikácie: {e}")
        return False

# --- PRIHLASOVANIE A REGISTRÁCIA ---
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
                    st.success(f"Vitajte, {r.get('meno', 'používateľ')}!")
                    st.rerun()
                else: 
                    st.error("Nesprávne telefónne číslo alebo heslo.")
            except: 
                st.error("Nepodarilo sa pripojiť k databáze. Skontrolujte SCRIPT_URL.")
            
    with tab2:
        st.subheader("Vytvoriť nový partnerský účet")
        with st.form("reg_form"):
            meno = st.text_input("Meno")
            prie = st.text_input("Priezvisko")
            mob = st.text_input("Mobil (bez úvodnej nuly, napr. 905123456)")
            hes = st.text_input("Heslo (vyberte si bezpečné heslo)")
            kod = st.text_input("Váš unikátny kód (napr. JOZO5)")
            
            submit = st.form_submit_button("Vytvoriť účet", use_container_width=True)
            if submit:
                if meno and prie and mob and hes and kod:
                    payload = {
                        "target": "user", # Toto povie skriptu, aby zapisoval do users_data
                        "meno": meno,
                        "priezvisko": prie,
                        "adresa": "",
                        "mobil": mob,
                        "heslo": hes,
                        "referral_code": kod
                    }
                    try:
                        r = requests.post(SCRIPT_URL, json=payload, timeout=10)
                        st.success("Registrácia úspešná! Teraz sa môžete prihlásiť v prvej karte.")
                    except:
                        st.error("Chyba pri registrácii.")
                else:
                    st.warning("Prosím, vyplňte všetky polia.")

# --- DASHBOARD (Po prihlásení) ---
else:
    u = st.session_state['user']
    # Sidebar s informáciami
    st.sidebar.title(f"👤 {u.get('meno', 'Užívateľ')}")
    st.sidebar.info(f"Rola: {u['rola'].upper()}\n\nKód: {u.get('kod', '---')}")
    
    if st.sidebar.button("Odhlásiť sa", use_container_width=True):
        st.session_state['user'] = None
        st.rerun()

    try:
        # Načítanie všetkých zakázok
        res = requests.get(f"{SCRIPT_URL}?action=getZakazky", timeout=10)
        df = pd.DataFrame(res.json())
        
        if not df.empty:
            # Oprava dátových typov na čísla, aby fungovali výpočty
            for col in ['suma_zakazky', 'provizia_odporucatel', 'zlava_novy']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # --- SEKCIA PODĽA ROLY ---

        # 1. SUPERADMIN (Peter - vidí všetko, spravuje zadeľovanie)
        if u['rola'] == 'superadmin':
            st.title("🌍 Administrátorská konzola (Všetky pobočky)")
            
            # Celkové štatistiky
            c1, c2, c3 = st.columns(3)
            c1.metric("Celkový obrat", f"{df['suma_zakazky'].sum():.2f} €")
            c2.metric("Počet zákaziek", len(df))
            c3.metric("Provízie spolu", f"{df['provizia_odporucatel'].sum():.2f} €")
            
            st.write("### Všetky transakcie")
            st.dataframe(df, use_container_width=True)

            # Prehľad podľa odporúčateľov (Zrátavanie provízií)
            st.divider()
            st.subheader("📊 Provízie podľa partnerov")
            if not df.empty:
                summary_df = df.groupby('kod_pouzity').agg({
                    'suma_zakazky': 'sum',
                    'provizia_odporucatel': 'sum',
                    'pobocka_id': 'count'
                }).reset_index()
                summary_df.columns = ['Kód partnera', 'Obrat (€)', 'Provízia (€)', 'Počet zakázok']
                st.dataframe(summary_df, use_container_width=True)

        # 2. ADMIN (Napr. NITRA, LIPTOV - dopĺňa sumy)
        elif u['rola'] == 'admin':
            moje_mesto = u.get('pobocka_id', '') # Meno admina v users_data musí sedieť s pobocka_id
            st.title(f"📍 Regionálny prehľad: {moje_mesto}")
            
            # Filtrujeme zakázky priradené tejto pobočke
            f_df = df[df['pobocka_id'].astype(str) == str(moje_mesto)].copy()
            
            if f_df.empty:
                st.info("Zatiaľ nemáte priradené žiadne nové objednávky.")
            else:
                # Rozdelenie na nové (suma 0) a vybavené
                nove = f_df[f_df['suma_zakazky'] == 0]
                vybavene = f_df[f_df['suma_zakazky'] > 0]
                
                st.subheader("📩 Nové objednávky (Zadajte sumu)")
                if nove.empty:
                    st.success("Všetky objednávky sú spracované.")
                else:
                    for i, row in nove.iterrows():
                        with st.expander(f"Kód: {row['kod_pouzity']} | Info: {row['poznamka']}"):
                            col1, col2 = st.columns([3, 1])
                            nova_suma_val = col1.number_input(f"Suma za tepovanie (€)", key=f"val_{i}", min_value=0.0, step=5.0)
                            if col2.button("Potvrdiť", key=f"btn_{i}"):
                                if nova_suma_val > 0:
                                    if update_suma(row['row_index'], nova_suma_val):
                                        st.success("Suma zapísaná!")
                                        st.rerun()
                                    else: st.error("Chyba zápisu.")
                                else: st.warning("Zadajte sumu.")

                st.subheader("✅ História vašich zakázok")
                st.dataframe(vybavene[['kod_pouzity', 'suma_zakazky', 'provizia_odporucatel', 'poznamka']], use_container_width=True)

        # 3. ZÁKAZNÍK / PARTNER (Vidí len svoje provízie)
        else:
            st.title(f"💰 Váš partnerský účet")
            my_kod = u.get('kod', '')
            my_df = df[df['kod_pouzity'].astype(str) == str(my_kod)].copy()
            
            c1, c2 = st.columns(2)
            c1.metric("Váš doterajší zárobok", f"{my_df['provizia_odporucatel'].sum():.2f} €")
            c2.metric("Počet odporúčaní", len(my_df))
            
            st.subheader("Zoznam vašich odporúčaní")
            if not my_df.empty:
                # Zobrazíme len dôležité stĺpce pre partnera
                st.table(my_df[['pobocka_id', 'suma_zakazky', 'provizia_odporucatel']])
            else:
                st.info(f"Zatiaľ ste nikoho neodporučili. Váš kód na zdieľanie je: **{my_kod}**")

    except Exception as e:
        st.error(f"Nepodarilo sa načítať dáta z tabuľky. (Chyba: {e})")
