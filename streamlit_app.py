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

# Pomocná funkcia na komunikáciu so skriptom
def call_script(action, params):
    try:
        url = f"{SCRIPT_URL}?action={action}"
        for k, v in params.items():
            url += f"&{k}={v}"
        res = requests.get(url, timeout=10).json()
        return res.get("status") == "success"
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
                st.error("Chyba pripojenia. Skontrolujte Deployment a SCRIPT_URL.")
            
    with tab2:
        st.subheader("Nový partnerský účet")
        with st.form("reg_form"):
            meno = st.text_input("Meno")
            prie = st.text_input("Priezvisko")
            mob = st.text_input("Mobil")
            hes = st.text_input("Heslo", type="password")
            kod = st.text_input("Váš unikátny kód (napr. JOZO5)")
            st.info("IBAN nie je vyžadovaný. Výplaty prebiehajú po dohode.")
            if st.form_submit_button("Vytvoriť účet", use_container_width=True):
                payload = {"target": "user", "meno": meno, "priezvisko": prie, "adresa": "", "mobil": mob, "heslo": hes, "referral_code": kod}
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
        # Načítanie dát
        res = requests.get(f"{SCRIPT_URL}?action=getZakazky", timeout=15).json()
        df = pd.DataFrame(res)
        
        if not df.empty:
            for col in ['suma_zakazky', 'provizia_odporucatel']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

        # --- A: SUPERADMIN (PETER) ---
        if u['rola'] == 'superadmin':
            st.title("🌍 Správa celého systému")
            
            # Sekcia pre výplaty
            k_vyplate = df[(df['suma_zakazky'] > 0) & (df['vyplatene'] == False)]
            st.subheader("⏳ Provízie na vyplatenie")
            if k_vyplate.empty:
                st.success("Všetko je vyplatené.")
            else:
                for i, row in k_vyplate.iterrows():
                    c1, c2, c3 = st.columns([3, 2, 1])
                    c1.write(f"**{row['partner_meno']}** ({row['partner_mobil']})")
                    c2.write(f"Provízia: **{row['provizia_odporucatel']:.2f} €**")
                    if c3.button("Označiť ako vyplatené", key=f"pay_{i}"):
                        if call_script("markAsPaid", {"row_index": row['row_index']}):
                            st.rerun()

            st.divider()
            st.subheader("📋 Kompletná história zákaziek")
            if not df.empty:
                view_df = df.copy()
                view_df['Stav'] = view_df['vyplatene'].apply(lambda x: "✅ Vyplatené" if x else "⏳ Čaká")
                st.dataframe(view_df[['pobocka_id', 'kod_pouzity', 'partner_meno', 'suma_zakazky', 'provizia_odporucatel', 'Stav']], use_container_width=True)

        # --- B: ADMIN (POBOČKY) ---
        elif u['rola'] == 'admin':
            moje_mesto = str(u.get('pobocka_id', ''))
            st.title(f"📍 Pobočka: {moje_mesto}")
            
            f_df = df[df['pobocka_id'].astype(str) == moje_mesto].copy()
            nove = f_df[f_df['suma_zakazky'] == 0]
            
            st.subheader("📩 Nové zakázky na nacenenie")
            if nove.empty:
                st.info("Žiadne nové zakázky.")
            else:
                for i, row in nove.iterrows():
                    with st.expander(f"Kód: {row['kod_pouzity']} | Partner: {row.get('partner_meno', 'Neznámy')}"):
                        val = st.number_input("Suma za prácu (€)", key=f"v_{i}", min_value=0.0, step=1.0)
                        if st.button("Uložiť cenu", key=f"s_{i}"):
                            if call_script("updateSuma", {"row_index": row['row_index'], "suma": val}):
                                st.success("Uložené!")
                                st.rerun()

            st.subheader("✅ História pobočky")
            st.dataframe(f_df[f_df['suma_zakazky'] > 0][['kod_pouzity', 'partner_meno', 'suma_zakazky', 'provizia_odporucatel']], use_container_width=True)

        # --- C: PARTNER (USER) ---
        else:
            st.title(f"💰 Váš prehľad provízií ({u.get('kod', '---')})")
            my_df = df[df['kod_pouzity'] == u['kod']].copy()
            
            col1, col2 = st.columns(2)
            col1.metric("Celkový zárobok", f"{my_df['provizia_odporucatel'].sum():.2f} €")
            col2.metric("Na vyplatenie", f"{my_df[my_df['vyplatene'] == False]['provizia_odporucatel'].sum():.2f} €")
            
            st.subheader("Zoznam odporúčaných zákaziek")
            if not my_df.empty:
                my_df['Stav'] = my_df['vyplatene'].apply(lambda x: "✅ Vyplatené" if x else "⏳ Čaká")
                st.table(my_df[['pobocka_id', 'suma_zakazky', 'provizia_odporucatel', 'Stav']])
            else:
                st.info("Zatiaľ žiadne odporúčania.")

    except Exception as e:
        st.error("Nepodarilo sa načítať dáta z Google tabuľky.")
