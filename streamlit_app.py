import streamlit as st
import pandas as pd
import requests

# --- KONFIGURÁCIA ---
# SEM VLOŽTE SVOJU NOVÚ URL Z GOOGLE APPS SCRIPTU
SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyjAB40A4smgumuldfN34harY1TkudIYTTglikbci9PvC1XLxKCUftvQulqtW65Y8-4Bg/exec"

st.set_page_config(page_title="TEPUJEM Portál", page_icon="💰", layout="wide")

if 'user' not in st.session_state:
    st.session_state['user'] = None

# --- PRIHLASOVANIE ---
if st.session_state['user'] is None:
    st.title("💰 Provízny systém TEPUJEM")
    tab1, tab2 = st.tabs(["Prihlásenie", "Registrácia"])
    
    with tab1:
        m = st.text_input("Mobil (login)").strip()
        h = st.text_input("Heslo", type="password").strip()
        if st.button("Prihlásiť sa"):
            try:
                r = requests.get(f"{SCRIPT_URL}?action=login&mobil={m}&heslo={h}", timeout=10).json()
                if r["status"] == "success":
                    st.session_state['user'] = r
                    st.rerun()
                else: st.error("Nesprávne údaje.")
            except: st.error("Nepodarilo sa pripojiť k databáze.")
            
    with tab2:
        with st.form("reg"):
            meno = st.text_input("Meno"); prie = st.text_input("Priezvisko")
            mob = st.text_input("Mobil"); hes = st.text_input("Heslo")
            kod = st.text_input("Váš kód (napr. JOZO10)")
            if st.form_submit_button("Vytvoriť účet"):
                requests.post(SCRIPT_URL, json={"meno": meno, "priezvisko": prie, "adresa": "", "mobil": mob, "heslo": hes, "referral_code": kod})
                st.success("Registrácia úspešná, teraz sa prihláste.")

# --- DASHBOARD ---
else:
    u = st.session_state['user']
    st.sidebar.title(f"👤 {u['meno']}")
    if st.sidebar.button("Odhlásiť sa"):
        st.session_state['user'] = None
        st.rerun()

    try:
        res = requests.get(f"{SCRIPT_URL}?action=getZakazky", timeout=10)
        df = pd.DataFrame(res.json())
        
        if not df.empty:
            # Vynútenie číselných formátov pre stĺpce
            for col in ['suma_zakazky', 'provizia_odporucatel', 'zlava_novy']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # A. SUPERADMIN
        if u['rola'] == 'superadmin':
            st.title("🌍 Administrátorská konzola")
            st.dataframe(df, use_container_width=True)
            c1, c2, c3 = st.columns(3)
            c1.metric("Celkový obrat", f"{df['suma_zakazky'].sum() if not df.empty else 0} €")
            c2.metric("Počet zákaziek", len(df))
            c3.metric("Provízie spolu", f"{df['provizia_odporucatel'].sum() if not df.empty else 0} €")

        # B. ADMIN (napr. Jozef Mako - Nitra)
        elif u['rola'] == 'admin':
            st.title(f"📍 Regionálny prehľad: {u['kod']}")
            f_df = df[df['pobocka_id'].astype(str) == str(u['kod'])]
            st.dataframe(f_df, use_container_width=True)
            st.metric("Obrat v regióne", f"{f_df['suma_zakazky'].sum() if not f_df.empty else 0} €")

        # C. ZÁKAZNÍK (Partner)
        else:
            st.title(f"💰 Váš partnerský účet ({u['kod']})")
            my_df = df[df['kod_pouzity'].astype(str) == str(u['kod'])]
            st.metric("Váš doterajší zárobok", f"{my_df['provizia_odporucatel'].sum() if not my_df.empty else 0} €")
            st.table(my_df[['pobocka_id', 'suma_zakazky', 'provizia_odporucatel']])

    except Exception as e:
        st.error(f"Dáta nie sú dostupné. (Chyba: {e})")
