import streamlit as st
import pandas as pd
import requests

# --- 1. KONFIGURÁCIA ---
# SEM VLOŽ SVOJU OVERENÚ URL Z GOOGLE APPS SCRIPTU
SCRIPT_URL = "import streamlit as st
import pandas as pd
import requests

# --- 1. KONFIGURÁCIA ---
# SEM VLOŽ SVOJU OVERENÚ URL Z GOOGLE APPS SCRIPTU
SCRIPT_URL = "import streamlit as st
import pandas as pd
import requests

# --- 1. KONFIGURÁCIA ---
# SEM VLOŽ SVOJU OVERENÚ URL Z GOOGLE APPS SCRIPTU
SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzLxqt5QwUvu2zha5NEOg97-7NtPLTbhMd2YQ3ORV6YRny7SvMZwBSgVQ6Zyd3u9v-IKw/exec"

st.set_page_config(page_title="TEPUJEM Portál", page_icon="💰", layout="wide")

if 'user' not in st.session_state:
    st.session_state['user'] = None

# Pomocná funkcia na volanie API (zápis dát)
def call_script(action, params):
    try:
        url = f"{SCRIPT_URL}?action={action}"
        for k, v in params.items(): url += f"&{k}={v}"
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
        # Načítanie dát
        response = requests.get(f"{SCRIPT_URL}?action=getZakazky", timeout=15)
        res_data = response.json()
        df = pd.DataFrame(res_data)
        
        if df.empty:
            df = pd.DataFrame(columns=['pobocka_id', 'kod_pouzity', 'suma_zakazky', 'provizia_odporucatel', 'poznamka', 'vyplatene', 'row_index'])

        # Prevod číselných hodnôt
        for col in ['suma_zakazky', 'provizia_odporucatel']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

        # --- A: SUPERADMIN (PETER) ---
        if u['rola'] == 'superadmin':
            st.title("🌍 Správa celého systému")
            
            k_vyplate = df[(df['suma_zakazky'] > 0) & (df['vyplatene'].astype(str).str.upper() != 'TRUE')]
            
            st.subheader("⏳ Čakajúce na vyplatenie")
            if k_vyplate.empty:
                st.success("Všetky provízie sú vyplatené.")
            else:
                for i, row in k_vyplate.iterrows():
                    c1, c2, c3 = st.columns([3, 2, 1])
                    c1.write(f"**{row.get('partner_meno', 'Partner')}** (Obj: {row['poznamka']})")
                    c2.write(f"Suma: **{row['provizia_odporucatel']:.2f} €**")
                    if c3.button("Označiť ako vyplatené", key=f"pay_{i}"):
                        if call_script("markAsPaid", {"row_index": row['row_index']}):
                            st.rerun()
            
            st.divider()
            st.subheader("📋 Kompletná história zákaziek")
            df_view = df.copy()
            df_view['Stav'] = df_view['vyplatene'].apply(lambda x: "✅ Vyplatené" if str(x).upper() == 'TRUE' else "⏳ Čaká")
            st.dataframe(df_view[['kod_pouzity', 'partner_meno', 'suma_zakazky', 'provizia_odporucatel', 'poznamka', 'Stav']], use_container_width=True)

        # --- B: ADMIN (POBOČKY) ---
        elif u['rola'] == 'admin':
            st.title(f"📍 Pobočka: {u.get('pobocka_id', '---')}")
            moje_df = df[df['pobocka_id'].astype(str) == str(u.get('pobocka_id', ''))]
            nove = moje_df[moje_df['suma_zakazky'] == 0]
            
            st.subheader("📩 Nové zákazky na nacenenie")
            if nove.empty:
                st.info("Žiadne nové zákazky.")
            else:
                for i, row in nove.iterrows():
                    with st.expander(f"Zákazka: {row['poznamka']} (Kód: {row['kod_pouzity']})"):
                        val = st.number_input("Celková suma za prácu (€)", key=f"v_{i}", min_value=0.0)
                        if st.button("Uložiť cenu", key=f"s_{i}"):
                            if call_script("updateSuma", {"row_index": row['row_index'], "suma": val}):
                                st.success("Uložené!")
                                st.rerun()

        # --- C: PARTNER (ZÁKAZNÍK) ---
        else:
            st.title(f"💰 Váš partnerský účet ({u.get('kod', '---')})")
            my_df = df[df['kod_pouzity'] == u['kod']].copy()
            
            c1, c2 = st.columns(2)
            c1.metric("Váš celkový zárobok", f"{my_df['provizia_odporucatel'].sum():.2f} €")
            cakajuce = my_df[my_df['vyplatene'].astype(str).str.upper() != 'TRUE']['provizia_odporucatel'].sum()
            c2.metric("Na vyplatenie", f"{cakajuce:.2f} €")
            
            st.subheader("Prehľad vašich provízií")
            if not my_df.empty:
                display_df = my_df.copy()
                # Premenovanie podľa požiadavky
                display_df = display_df.rename(columns={
                    'poznamka': 'Objednávka',
                    'provizia_odporucatel': 'Získaná provízia'
                })
                display_df['Stav'] = display_df['vyplatene'].apply(
                    lambda x: "✅ Vyplatené" if str(x).upper() == 'TRUE' else "⏳ Čaká"
                )
                # Skrytie citlivých stĺpcov
                st.table(display_df[['Objednávka', 'Získaná provízia', 'Stav']])
            else:
                st.info("Zatiaľ tu nemáte žiadne záznamy.")

    except Exception as e:
        st.error(f"Nepodarilo sa načítať dáta z tabuľky.")"

st.set_page_config(page_title="TEPUJEM Portál", page_icon="💰", layout="wide")

if 'user' not in st.session_state:
    st.session_state['user'] = None

# Pomocná funkcia na volanie API (zápis dát)
def call_script(action, params):
    try:
        url = f"{SCRIPT_URL}?action={action}"
        for k, v in params.items(): url += f"&{k}={v}"
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
        # Načítanie dát
        response = requests.get(f"{SCRIPT_URL}?action=getZakazky", timeout=15)
        res_data = response.json()
        df = pd.DataFrame(res_data)
        
        if df.empty:
            df = pd.DataFrame(columns=['pobocka_id', 'kod_pouzity', 'suma_zakazky', 'provizia_odporucatel', 'poznamka', 'vyplatene', 'row_index'])

        # Prevod číselných hodnôt
        for col in ['suma_zakazky', 'provizia_odporucatel']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

        # --- A: SUPERADMIN (PETER) ---
        if u['rola'] == 'superadmin':
            st.title("🌍 Správa celého systému")
            
            k_vyplate = df[(df['suma_zakazky'] > 0) & (df['vyplatene'].astype(str).str.upper() != 'TRUE')]
            
            st.subheader("⏳ Čakajúce na vyplatenie")
            if k_vyplate.empty:
                st.success("Všetky provízie sú vyplatené.")
            else:
                for i, row in k_vyplate.iterrows():
                    c1, c2, c3 = st.columns([3, 2, 1])
                    c1.write(f"**{row.get('partner_meno', 'Partner')}** (Obj: {row['poznamka']})")
                    c2.write(f"Suma: **{row['provizia_odporucatel']:.2f} €**")
                    if c3.button("Označiť ako vyplatené", key=f"pay_{i}"):
                        if call_script("markAsPaid", {"row_index": row['row_index']}):
                            st.rerun()
            
            st.divider()
            st.subheader("📋 Kompletná história zákaziek")
            df_view = df.copy()
            df_view['Stav'] = df_view['vyplatene'].apply(lambda x: "✅ Vyplatené" if str(x).upper() == 'TRUE' else "⏳ Čaká")
            st.dataframe(df_view[['kod_pouzity', 'partner_meno', 'suma_zakazky', 'provizia_odporucatel', 'poznamka', 'Stav']], use_container_width=True)

        # --- B: ADMIN (POBOČKY) ---
        elif u['rola'] == 'admin':
            st.title(f"📍 Pobočka: {u.get('pobocka_id', '---')}")
            moje_df = df[df['pobocka_id'].astype(str) == str(u.get('pobocka_id', ''))]
            nove = moje_df[moje_df['suma_zakazky'] == 0]
            
            st.subheader("📩 Nové zákazky na nacenenie")
            if nove.empty:
                st.info("Žiadne nové zákazky.")
            else:
                for i, row in nove.iterrows():
                    with st.expander(f"Zákazka: {row['poznamka']} (Kód: {row['kod_pouzity']})"):
                        val = st.number_input("Celková suma za prácu (€)", key=f"v_{i}", min_value=0.0)
                        if st.button("Uložiť cenu", key=f"s_{i}"):
                            if call_script("updateSuma", {"row_index": row['row_index'], "suma": val}):
                                st.success("Uložené!")
                                st.rerun()

        # --- C: PARTNER (ZÁKAZNÍK) ---
        else:
            st.title(f"💰 Váš partnerský účet ({u.get('kod', '---')})")
            my_df = df[df['kod_pouzity'] == u['kod']].copy()
            
            c1, c2 = st.columns(2)
            c1.metric("Váš celkový zárobok", f"{my_df['provizia_odporucatel'].sum():.2f} €")
            cakajuce = my_df[my_df['vyplatene'].astype(str).str.upper() != 'TRUE']['provizia_odporucatel'].sum()
            c2.metric("Na vyplatenie", f"{cakajuce:.2f} €")
            
            st.subheader("Prehľad vašich provízií")
            if not my_df.empty:
                display_df = my_df.copy()
                # Premenovanie podľa požiadavky
                display_df = display_df.rename(columns={
                    'poznamka': 'Objednávka',
                    'provizia_odporucatel': 'Získaná provízia'
                })
                display_df['Stav'] = display_df['vyplatene'].apply(
                    lambda x: "✅ Vyplatené" if str(x).upper() == 'TRUE' else "⏳ Čaká"
                )
                # Skrytie citlivých stĺpcov
                st.table(display_df[['Objednávka', 'Získaná provízia', 'Stav']])
            else:
                st.info("Zatiaľ tu nemáte žiadne záznamy.")

    except Exception as e:
        st.error(f"Nepodarilo sa načítať dáta z tabuľky.")"

st.set_page_config(page_title="TEPUJEM Portál", page_icon="💰", layout="wide")

if 'user' not in st.session_state:
    st.session_state['user'] = None

# Pomocná funkcia na volanie API (zápis dát)
def call_script(action, params):
    try:
        url = f"{SCRIPT_URL}?action={action}"
        for k, v in params.items(): url += f"&{k}={v}"
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
        # Načítanie dát
        response = requests.get(f"{SCRIPT_URL}?action=getZakazky", timeout=15)
        res_data = response.json()
        df = pd.DataFrame(res_data)
        
        if df.empty:
            df = pd.DataFrame(columns=['pobocka_id', 'kod_pouzity', 'suma_zakazky', 'provizia_odporucatel', 'poznamka', 'vyplatene', 'row_index'])

        # Prevod číselných hodnôt
        for col in ['suma_zakazky', 'provizia_odporucatel']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

        # --- A: SUPERADMIN (PETER) ---
        if u['rola'] == 'superadmin':
            st.title("🌍 Správa celého systému")
            
            k_vyplate = df[(df['suma_zakazky'] > 0) & (df['vyplatene'].astype(str).str.upper() != 'TRUE')]
            
            st.subheader("⏳ Čakajúce na vyplatenie")
            if k_vyplate.empty:
                st.success("Všetky provízie sú vyplatené.")
            else:
                for i, row in k_vyplate.iterrows():
                    c1, c2, c3 = st.columns([3, 2, 1])
                    c1.write(f"**{row.get('partner_meno', 'Partner')}** (Obj: {row['poznamka']})")
                    c2.write(f"Suma: **{row['provizia_odporucatel']:.2f} €**")
                    if c3.button("Označiť ako vyplatené", key=f"pay_{i}"):
                        if call_script("markAsPaid", {"row_index": row['row_index']}):
                            st.rerun()
            
            st.divider()
            st.subheader("📋 Kompletná história zákaziek")
            df_view = df.copy()
            df_view['Stav'] = df_view['vyplatene'].apply(lambda x: "✅ Vyplatené" if str(x).upper() == 'TRUE' else "⏳ Čaká")
            st.dataframe(df_view[['kod_pouzity', 'partner_meno', 'suma_zakazky', 'provizia_odporucatel', 'poznamka', 'Stav']], use_container_width=True)

        # --- B: ADMIN (POBOČKY) ---
        elif u['rola'] == 'admin':
            st.title(f"📍 Pobočka: {u.get('pobocka_id', '---')}")
            moje_df = df[df['pobocka_id'].astype(str) == str(u.get('pobocka_id', ''))]
            nove = moje_df[moje_df['suma_zakazky'] == 0]
            
            st.subheader("📩 Nové zákazky na nacenenie")
            if nove.empty:
                st.info("Žiadne nové zákazky.")
            else:
                for i, row in nove.iterrows():
                    with st.expander(f"Zákazka: {row['poznamka']} (Kód: {row['kod_pouzity']})"):
                        val = st.number_input("Celková suma za prácu (€)", key=f"v_{i}", min_value=0.0)
                        if st.button("Uložiť cenu", key=f"s_{i}"):
                            if call_script("updateSuma", {"row_index": row['row_index'], "suma": val}):
                                st.success("Uložené!")
                                st.rerun()

        # --- C: PARTNER (ZÁKAZNÍK) ---
        else:
            st.title(f"💰 Váš partnerský účet ({u.get('kod', '---')})")
            my_df = df[df['kod_pouzity'] == u['kod']].copy()
            
            c1, c2 = st.columns(2)
            c1.metric("Váš celkový zárobok", f"{my_df['provizia_odporucatel'].sum():.2f} €")
            cakajuce = my_df[my_df['vyplatene'].astype(str).str.upper() != 'TRUE']['provizia_odporucatel'].sum()
            c2.metric("Na vyplatenie", f"{cakajuce:.2f} €")
            
            st.subheader("Prehľad vašich provízií")
            if not my_df.empty:
                display_df = my_df.copy()
                # Premenovanie podľa požiadavky
                display_df = display_df.rename(columns={
                    'poznamka': 'Objednávka',
                    'provizia_odporucatel': 'Získaná provízia'
                })
                display_df['Stav'] = display_df['vyplatene'].apply(
                    lambda x: "✅ Vyplatené" if str(x).upper() == 'TRUE' else "⏳ Čaká"
                )
                # Skrytie citlivých stĺpcov
                st.table(display_df[['Objednávka', 'Získaná provízia', 'Stav']])
            else:
                st.info("Zatiaľ tu nemáte žiadne záznamy.")

    except Exception as e:
        st.error(f"Nepodarilo sa načítať dáta z tabuľky.")
