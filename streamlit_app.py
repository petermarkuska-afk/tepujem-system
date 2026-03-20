import streamlit as st
import pandas as pd
import requests

# --- 1. KONFIGURÁCIA ---
# SEM VLOŽ SVOJU AKTUALNU URL Z GOOGLE APPS SCRIPTU
SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzLxqt5QwUvu2zha5NEOg97-7NtPLTbhMd2YQ3ORV6YRny7SvMZwBSgVQ6Zyd3u9v-IKw/exec"

st.set_page_config(page_title="TEPUJEM Portál", page_icon="💰", layout="wide")

if 'user' not in st.session_state:
    st.session_state['user'] = None

# Pomocná funkcia na volanie skriptu
def call_script(action, params):
    try:
        url = f"{SCRIPT_URL}?action={action}"
        for k, v in params.items(): url += f"&{k}={v}"
        return requests.get(url, timeout=10).json().get("status") == "success"
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
                # Voláme Google Script pre overenie login-u
                res = requests.get(f"{SCRIPT_URL}?action=login&mobil={m}&heslo={h}", timeout=10).json()
                if res.get("status") == "success":
                    st.session_state['user'] = res
                    st.rerun()
                else: 
                    st.error("Nesprávne telefónne číslo alebo heslo.")
            except Exception as e: 
                st.error(f"Chyba pripojenia. Skontrolujte deployment a SCRIPT_URL.")
            
    with tab2:
        st.subheader("Nový partnerský účet")
        with st.form("reg_form"):
            c1, c2 = st.columns(2)
            meno = c1.text_input("Meno")
            prie = c2.text_input("Priezvisko")
            mob = c1.text_input("Mobil (napr. 0915...)")
            hes = c2.text_input("Heslo", type="password")
            kod = st.text_input("Váš unikátny kód (napr. JOZO5)")
            st.info("IBAN nie je vyžadovaný. Výplaty prebiehajú po vzájomnej dohode.")
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
        # Načítanie všetkých zakázok (Google Script vracia JSON)
        res = requests.get(f"{SCRIPT_URL}?action=getZakazky", timeout=15).json()
        df = pd.DataFrame(res)
        
        # Ošetrenie prázdnej tabuľky
        if df.empty:
            df = pd.DataFrame(columns=['pobocka_id', 'kod_pouzity', 'suma_zakazky', 'provizia_odporucatel', 'poznamka', 'vyplatene'])
        else:
            # Konverzia na čísla pre výpočty
            for col in ['suma_zakazky', 'provizia_odporucatel']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

        # A: SUPERADMIN (PETER)
        if u['rola'] == 'superadmin':
            st.title("🌍 Globálny prehľad (Superadmin)")
            # ... tu by bol kód pre admina na správu výplat ...
            # Zobrazíme len tabuľku, partnera Peter nepýtal
            hist_df = df.copy()
            hist_df['Stav'] = hist_df['vyplatene'].apply(lambda x: "✅ Vyplatené" if x else "⏳ Čaká")
            st.dataframe(hist_df[['pobocka_id', 'kod_pouzity', 'partner_meno', 'suma_zakazky', 'provizia_odporucatel', 'poznamka', 'Stav']], use_container_width=True)

        # B: ADMIN (POBOČKY)
        elif u['rola'] == 'admin':
            # Zobrazíme rozhranie pre Admina (mesto) z u['pobocka_id']
            st.title(f"📍 Pobočka: {u['pobocka_id']}")
            # ... tu by bol kód na zadávanie sumy zakázky ...

        # C: PARTNER (ZÁKAZNÍK)
        else:
            st.title(f"💰 Váš partnerský prehľad ({u.get('kod', '---')})")
            
            # Filtrujeme len zakázky daného partnera
            my_df = df[df['kod_pouzity'] == u['kod']].copy()
            
            # Výpočet metrík
            celkovo = my_df['provizia_odporucatel'].sum()
            na_vyplatenie = my_df[my_df['vyplatene'] == False]['provizia_odporucatel'].sum()
            
            c1, c2 = st.columns(2)
            c1.metric("Celkový zárobok", f"{celkovo:.2f} €")
            c2.metric("Na vyplatenie", f"{na_vyplatenie:.2f} €")
            
            st.subheader("Zoznam odporúčaných zákaziek")
            if not my_df.empty:
                # Príprava tabuľky pre zobrazenie
                display_df = my_df.copy()
                
                # --- PREMENOVANIE STĹPCOV (POŽADAVKA) ---
                display_df = display_df.rename(columns={
                    'poznamka': 'Objednávka',
                    'provizia_odporucatel': 'Získaná provízia'
                })
                
                # Prevod logickej hodnoty na ikonky
                display_df['Stav'] = display_df['vyplatene'].apply(lambda x: "✅ Vyplatené" if x else "⏳ Čaká")
                
                # Zobrazenie len požadovaných stĺpcov pre partnera (bez pobocka_id a suma_zakazky)
                # Tieto stĺpce sa "ťahajú" zo stĺpcov F a D Google tabuľky
                st.table(display_df[['Objednávka', 'Získaná provízia', 'Stav']])
            else:
                st.info("Zatiaľ nemáte žiadne odporúčania.")

    exceptException as e:
        st.error(f"Nepodarilo sa načítať dáta z Google tabuľky. (Detaily: {e})")
