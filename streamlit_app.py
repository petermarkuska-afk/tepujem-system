import streamlit as st
import pandas as pd
import requests

# --- KONFIGURÁCIA ---
# SEM VLOŽTE SVOJU URL Z APPS SCRIPTU (Web App URL)
SCRIPT_URL = "SEM_VLOZ_SVOJU_URL_Z_APPS_SCRIPTU"

st.set_page_config(page_title="TEPUJEM Portál", page_icon="💰", layout="wide")

# Inicializácia prihlásenia
if 'user' not in st.session_state:
    st.session_state['user'] = None

def logout():
    st.session_state['user'] = None
    st.rerun()

# --- 1. PRIHLASOVACIA OBRAZOVKA ---
if st.session_state['user'] is None:
    st.title("💰 Provízny systém TEPUJEM")
    
    tab1, tab2 = st.tabs(["Prihlásenie", "Registrácia partnera"])

    with tab1:
        st.subheader("Vstup do portálu")
        mob = st.text_input("Mobilné číslo (login)").strip()
        hes = st.text_input("Heslo", type="password").strip()
        
        if st.button("Prihlásiť sa"):
            if mob and hes:
                with st.spinner("Overujem údaje..."):
                    try:
                        res = requests.get(f"{SCRIPT_URL}?action=login&mobil={mob}&heslo={hes}", timeout=15).json()
                        if res["status"] == "success":
                            st.session_state['user'] = res
                            st.rerun()
                        else:
                            st.error("Nesprávne meno alebo heslo.")
                    except Exception as e:
                        st.error(f"Nepodarilo sa spojiť s databázou. Skontrolujte SCRIPT_URL. ({e})")
            else:
                st.warning("Vyplňte všetky údaje.")

    with tab2:
        st.subheader("Nový partnerský profil")
        with st.form("reg_form"):
            col1, col2 = st.columns(2)
            meno = col1.text_input("Meno")
            prie = col2.text_input("Priezvisko")
            adr = st.text_input("Adresa / Región")
            mob_reg = st.text_input("Mobil (bude slúžiť ako login)")
            hes_reg = st.text_input("Heslo (minimálne 6 znakov)")
            kod = st.text_input("Váš unikátny zľavový kód (napr. MAREK10)")
            
            if st.form_submit_button("Zaregistrovať sa"):
                if all([meno, prie, mob_reg, hes_reg, kod]):
                    payload = {
                        "meno": meno, "priezvisko": prie, "adresa": adr, 
                        "mobil": mob_reg, "heslo": hes_reg, "referral_code": kod
                    }
                    try:
                        resp = requests.post(SCRIPT_URL, json=payload, timeout=15).json()
                        st.success("Registrácia úspešná! Teraz sa môžete prihlásiť.")
                    except:
                        st.error("Chyba pri registrácii. Skúste to neskôr.")
                else:
                    st.warning("Prosím, vyplňte všetky polia.")

# --- 2. DASHBOARD PRE PRIHLÁSENÝCH ---
else:
    u = st.session_state['user']
    
    # Sidebar menu
    st.sidebar.title(f"👤 {u['meno']} {u['priezvisko']}")
    st.sidebar.info(f"Rola: **{u['rola'].upper()}**")
    st.sidebar.button("Odhlásiť sa", on_click=logout)

    st.title("Prehľad objednávok a provízií")

    try:
        # Sťahovanie dát zo súkromnej tabuľky
        with st.spinner("Načítavam dáta z cloudu..."):
            response = requests.get(f"{SCRIPT_URL}?action=getZakazky", timeout=15)
            # Prevod JSON na DataFrame
            df = pd.DataFrame(response.json())

        # --- FILTROVANIE PODĽA ROLY ---

        # A. SUPERADMIN (Vidí všetko)
        if u['rola'] == 'superadmin':
            st.header("🌍 Administrátorská konzola (Všetky regióny)")
            st.dataframe(df, use_container_width=True)
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Celkový obrat", f"{pd.to_numeric(df['suma_zakazky']).sum()} €")
            c2.metric("Počet zákaziek", len(df))
            c3.metric("Vyplatené provízie", f"{pd.to_numeric(df['provizia_odporucatel']).sum()} €")

        # B. ADMIN REGIÓNU (Vidí len svoju pobočku)
        elif u['rola'] == 'admin':
            moj_region = u['kod'] # Admin má región v poli 'kod'
            st.header(f"📍 Regionálny prehľad: {moj_region}")
            
            # Filter pre pobocka_id
            df_region = df[df['pobocka_id'].astype(str) == str(moj_region)]
            
            if df_region.empty:
                st.warning(f"V regióne {moj_region} zatiaľ nie sú žiadne priradené objednávky.")
            else:
                st.dataframe(df_region, use_container_width=True)
                st.metric(f"Obrat - {moj_region}", f"{pd.to_numeric(df_region['suma_zakazky']).sum()} €")

        # C. ZÁKAZNÍK / PARTNER (Vidí len svoje provízie)
        else:
            st.header(f"💰 Váš partnerský účet ({u['kod']})")
            
            # Filter pre kod_pouzity
            df_moje = df[df['kod_pouzity'].astype(str) == str(u['kod'])]
            
            if df_moje.empty:
                st.info("Zatiaľ neboli evidované žiadne objednávky s Vaším kódom.")
            else:
                total = pd.to_numeric(df_moje['provizia_odporucatel']).sum()
                st.metric("Váš doterajší zárobok", f"{total} €")
                st.write("Detailný zoznam odporúčaní:")
                # Zobrazíme len relevantné stĺpce pre zákazníka
                st.table(df_moje[['pobocka_id', 'suma_zakazky', 'provizia_odporucatel']])

    except Exception as e:
        st.error("Dáta momentálne nie sú k dispozícii. Skontrolujte, či v tabuľke 'Zakazky' nie sú prázdne riadky.")
        st.info("Technický detail: " + str(e))
