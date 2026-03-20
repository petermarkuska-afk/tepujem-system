import streamlit as st
import pandas as pd
import requests

# --- KONFIGURÁCIA ---
SCRIPT_URL = "TVOJA_URL_Z_APPS_SCRIPTU"

st.set_page_config(page_title="TEPUJEM Portál", page_icon="💰", layout="wide")

if 'user' not in st.session_state:
    st.session_state['user'] = None

# Funkcia na odhlásenie
def logout():
    st.session_state['user'] = None
    st.rerun()

# --- A. PRIHLASOVACIA OBRAZOVKA ---
if st.session_state['user'] is None:
    st.title("💰 Provízny systém TEPUJEM")
    t1, t2 = st.tabs(["Prihlásenie", "Registrácia partnera"])

    with t1:
        with st.container():
            m_log = st.text_input("Mobilné číslo (login)").strip()
            h_log = st.text_input("Heslo", type="password").strip()
            if st.button("Vstúpiť do portálu", use_container_width=True):
                try:
                    r = requests.get(f"{SCRIPT_URL}?action=login&mobil={m_log}&heslo={h_log}", timeout=15).json()
                    if r["status"] == "success":
                        st.session_state['user'] = r
                        st.rerun()
                    else:
                        st.error("Nesprávne meno alebo heslo.")
                except:
                    st.error("Chyba spojenia s databázou.")

    with t2:
        with st.form("reg_form"):
            st.subheader("Nový partnerský profil")
            c1, c2 = st.columns(2)
            meno = c1.text_input("Meno")
            prie = c2.text_input("Priezvisko")
            adr = st.text_input("Adresa (ulica, mesto)")
            mob = st.text_input("Mobil (slúži ako login)")
            hes = st.text_input("Heslo", type="password")
            kod = st.text_input("Váš zľavový kód (napr. PETO10)")
            if st.form_submit_button("Zaregistrovať sa", use_container_width=True):
                if all([meno, prie, mob, hes, kod]):
                    payload = {"meno": meno, "priezvisko": prie, "adresa": adr, "mobil": mob, "heslo": hes, "referral_code": kod}
                    requests.post(SCRIPT_URL, json=payload, timeout=15)
                    st.success("Registrácia úspešná! Teraz sa môžete prihlásiť.")
                else:
                    st.warning("Vyplňte všetky polia.")

# --- B. DASHBOARD (PRIHLÁSENÝ) ---
else:
    u = st.session_state['user']
    st.sidebar.title(f"👤 {u['meno']} {u['priezvisko']}")
    st.sidebar.info(f"Rola: **{u['rola'].upper()}**")
    st.sidebar.button("Odhlásiť sa", on_click=logout, use_container_width=True)

    try:
        # Sťahovanie súkromných dát
        res = requests.get(f"{SCRIPT_URL}?action=getZakazky", timeout=15)
        raw_data = res.json()
        df = pd.DataFrame(raw_data) if raw_data else pd.DataFrame(columns=['pobocka_id', 'kod_pouzity', 'suma_zakazky', 'provizia_odporucatel'])
        
        # Prevod stĺpcov na čísla
        df['suma_zakazky'] = pd.to_numeric(df['suma_zakazky'], errors='coerce').fillna(0)
        df['provizia_odporucatel'] = pd.to_numeric(df['provizia_odporucatel'], errors='coerce').fillna(0)

        # 1. SUPERADMIN - Vidí všetko
        if u['rola'] == 'superadmin':
            st.title("🌍 Administrátorská konzola")
            st.dataframe(df, use_container_width=True)
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Celkový obrat", f"{df['suma_zakazky'].sum():.2f} €")
            m2.metric("Počet zákaziek", len(df))
            m3.metric("Provízie spolu", f"{df['provizia_odporucatel'].sum():.2f} €")

        # 2. ADMIN - Vidí len svoj región (napr. Nitra)
        elif u['rola'] == 'admin':
            moj_reg = str(u['kod'])
            st.title(f"📍 Región: {moj_reg}")
            f_df = df[df['pobocka_id'].astype(str) == moj_reg]
            
            if f_df.empty:
                st.warning(f"V regióne {moj_reg} nie sú žiadne zákazky.")
            else:
                st.dataframe(f_df, use_container_width=True)
                st.metric("Obrat regiónu", f"{f_df['suma_zakazky'].sum():.2f} €")

        # 3. ZÁKAZNÍK - Vidí svoje provízie
        else:
            st.title(f"💰 Váš účet ({u['kod']})")
            m_df = df[df['kod_pouzity'].astype(str) == str(u['kod'])]
            
            st.metric("Váš doterajší zárobok", f"{m_df['provizia_odporucatel'].sum():.2f} €")
            if not m_df.empty:
                st.write("Zoznam odporúčaní:")
                st.table(m_df[['pobocka_id', 'suma_zakazky', 'provizia_odporucatel']])
            else:
                st.info("Zatiaľ nemáte žiadne provízie.")

    except Exception as e:
        st.error(f"Nepodarilo sa načítať dáta: {e}")
