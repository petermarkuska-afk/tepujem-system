import streamlit as st
import pandas as pd
import requests

# --- KONFIGURÁCIA (Doplň svoje údaje) ---
# 1. URL z Google Apps Script (končí na /exec)
SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyjAB40A4smgumuldfN34harY1TkudIYTTglikbci9PvC1XLxKCUftvQulqtW65Y8-4Bg/exec"

# 2. CSV link z tabuľky Zakazky (Súbor -> Zdieľať -> Publikovať na webe -> CSV)
ZAKAZKY_CSV = "https://docs.google.com/spreadsheets/d/1DHUfPU56bqQJbzVjqIGgvpTbDtGQcD_TjVFaLZjXUAA/edit?usp=sharingK"

st.set_page_config(page_title="TEPUJEM Portál", page_icon="💰", layout="wide")

# Inicializácia session state
if 'user' not in st.session_state:
    st.session_state['user'] = None

# --- ODHLÁSENIE ---
def logout():
    st.session_state['user'] = None
    st.rerun()

# --- HLAVNÁ LOGIKA ---
if st.session_state['user'] is None:
    st.title("💰 Provízny systém TEPUJEM")
    tab1, tab2 = st.tabs(["Prihlásenie", "Registrácia"])

    with tab1:
        st.subheader("Vstup pre partnerov")
        mob = st.text_input("Mobilné číslo (napr. 0915...)").strip()
        hes = st.text_input("Heslo", type="password").strip()
        
        if st.button("Prihlásiť sa"):
            if mob and hes:
                with st.spinner("Overujem..."):
                    try:
                        url = f"{SCRIPT_URL}?action=login&mobil={mob}&heslo={hes}"
                        r = requests.get(url, timeout=10).json()
                        if r["status"] == "success":
                            st.session_state['user'] = r
                            st.rerun()
                        else:
                            st.error("Nesprávne údaje. Skontrolujte mobil a heslo.")
                    except Exception as e:
                        st.error(f"Chyba pripojenia: {e}")
            else:
                st.warning("Prosím, vyplňte mobil aj heslo.")

    with tab2:
        with st.form("registration_form"):
            st.subheader("Registrácia nového partnera")
            m = st.text_input("Meno")
            p = st.text_input("Priezvisko")
            a = st.text_input("Adresa (pre Superadmina)")
            mob_reg = st.text_input("Mobil (bude slúžiť ako login)")
            hes_reg = st.text_input("Heslo")
            kod = st.text_input("Váš unikátny kód (napr. PETO10)")
            
            if st.form_submit_button("Vytvoriť profil"):
                if all([m, p, mob_reg, hes_reg, kod]):
                    payload = {
                        "meno": m, "priezvisko": p, "adresa": a, 
                        "mobil": mob_reg, "heslo": hes_reg, "referral_code": kod
                    }
                    try:
                        res = requests.post(SCRIPT_URL, json=payload, timeout=10).json()
                        if res["status"] == "success":
                            st.success("Profil vytvorený! Teraz sa môžete prihlásiť.")
                        else:
                            st.error("Chyba pri registrácii. Kód možno už existuje.")
                    except:
                        st.error("Chyba spojenia s Google tabuľkou.")
                else:
                    st.warning("Všetky polia sú povinné.")

else:
    # --- PRIHLÁSENÝ POUŽÍVATEĽ ---
    u = st.session_state['user']
    
    # Sidebar menu
    st.sidebar.title(f"👤 {u['meno']}")
    st.sidebar.write(f"Rola: **{u['rola'].upper()}**")
    if st.sidebar.button("Odhlásiť sa"):
        logout()

    st.title(f"Vitajte v portáli, {u['meno']}")

    try:
        # Načítanie dát zo zdieľaného CSV (Tabuľka Zakazky)
        df = pd.read_csv(ZAKAZKY_CSV)
        
        # 1. LOGIKA PRE SUPERADMINA
        if u['rola'] == 'superadmin':
            st.header("🌍 Celkový prehľad (SUPERADMIN)")
            st.info("Vidíte všetky objednávky. Regióny priraďujte v stĺpci 'pobocka_id' v Google Tabuľke.")
            st.dataframe(df, use_container_width=True)
            
            col1, col2 = st.columns(2)
            col1.metric("Celkový obrat", f"{df['suma_zakazky'].sum()} €")
            col2.metric("Počet objednávok", len(df))

        # 2. LOGIKA PRE ADMINA (Regionálneho)
        elif u['rola'] == 'admin':
            # Admin má svoj región priradený v poli 'kod' (napr. Nitra)
            moj_region = u['kod']
            st.header(f"📍 Región: {moj_region}")
            
            # Filtrujeme dáta len pre tento región
            region_data = df[df['pobocka_id'] == moj_region]
            
            if region_data.empty:
                st.warning(f"Pre región {moj_region} zatiaľ neboli priradené žiadne objednávky.")
            else:
                st.dataframe(region_data, use_container_width=True)
                st.metric(f"Obrat v regióne {moj_region}", f"{region_data['suma_zakazky'].sum()} €")

        # 3. LOGIKA PRE ZÁKAZNÍKA (Referral)
        else:
            st.header("💰 Vaše provízie")
            st.success(f"Váš odporúčací kód: **{u['kod']}**")
            
            # Filtrujeme len objednávky, kde bol použitý kód zákazníka
            moje_data = df[df['kod_pouzity'] == u['kod']]
            
            if moje_data.empty:
                st.write("Zatiaľ nemáte žiadne úspešné odporúčania.")
            else:
                total_provizia = moje_data['provizia_odporucatel'].sum()
                st.metric("Zárobok celkom", f"{total_provizia} €")
                st.write("Zoznam vašich odporúčaní:")
                st.dataframe(moje_data[['pobocka_id', 'suma_zakazky', 'provizia_odporucatel']], use_container_width=True)

    except Exception as e:
        st.error("Nepodarilo sa načítať dáta zo zákaziek. Skontrolujte, či je tabuľka publikovaná na webe ako CSV.")
