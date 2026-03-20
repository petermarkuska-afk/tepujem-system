import streamlit as st
import pandas as pd
import requests

# --- NASTAVENIA ---
# Sem vložte tú URL, ktorú ste práve získali v kroku 1 (z Apps Scriptu)
SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyjAB40A4smgumuldfN34harY1TkudIYTTglikbci9PvC1XLxKCUftvQulqtW65Y8-4Bg/exec"

# Sem vložte CSV link (Súbor -> Zdieľať -> Publikovať na webe -> CSV)
# Tento link slúži na čítanie provízií z tabuľky "Zakazky a provizie"
ZAKAZKY_CSV = "https://docs.google.com/spreadsheets/d/1DHUfPU56bqQJbzVjqIGgvpTbDtGQcD_TjVFaLZjXUAA/edit?usp=sharing"

st.set_page_config(page_title="TEPUJEM Portál")

if 'user' not in st.session_state:
    st.title("💰 Provízny systém TEPUJEM")
    tab1, tab2 = st.tabs(["Prihlásenie", "Registrácia"])

    with tab1:
        mob = st.text_input("Mobilné číslo")
        hes = st.text_input("Heslo", type="password")
        if st.button("Vstúpiť"):
            # Pýtame sa "vrátnika" v tabuľke
            r = requests.get(f"{SCRIPT_URL}?action=login&mobil={mob}&heslo={hes}").json()
            if r["status"] == "success":
                st.session_state['user'] = r
                st.rerun()
            else:
                st.error("Nesprávne údaje.")

    with tab2:
        with st.form("reg"):
            st.write("Vytvorte si profil")
            m = st.text_input("Meno")
            p = st.text_input("Priezvisko")
            mob_reg = st.text_input("Mobil")
            hes_reg = st.text_input("Heslo", type="password")
            kod = st.text_input("Váš unikátny kód (napr. LUKAS10)")
            if st.form_submit_button("Registrovať"):
                data = {"meno":m, "priezvisko":p, "mobil":mob_reg, "heslo":hes_reg, "referral_code":kod}
                res = requests.post(SCRIPT_URL, json=data).json()
                st.success("Hotovo! Teraz sa môžete prihlásiť.")

else:
    u = st.session_state['user']
    st.title(f"Ahoj, {u['meno']}!")
    st.info(f"Tvoj kód: **{u['kod']}**")
    
    # Načítanie provízií
    try:
        df = pd.read_csv(ZAKAZKY_CSV)
        moje = df[df['kod_pouzity'] == u['kod']]
        st.metric("Zárobok celkom", f"{moje['provizia_odporucatel'].sum()} €")
        st.dataframe(moje[['pobocka_id', 'suma_zakazky', 'provizia_odporucatel']])
    except:
        st.write("Zatiaľ tu nemáš žiadne provízie.")
    
    if st.sidebar.button("Odhlásiť sa"):
        del st.session_state['user']
        st.rerun()
