import streamlit as st
import pandas as pd
import requests
import time

# --- 1. KONFIGURÁCIA ---
SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzLxqt5QwUvu2zha5NEOg97-7NtPLTbhMd2YQ3ORV6YRny7SvMZwBSgVQ6Zyd3u9v-IKw/exec"

st.set_page_config(page_title="TEPUJEM Portál", page_icon="💰", layout="wide")

if 'user' not in st.session_state:
    st.session_state['user'] = None

# --- 2. FUNKCIE ---

def call_script(action, params=None):
    if params is None:
        params = {}
    params['action'] = action

    try:
        response = requests.get(SCRIPT_URL, params=params, timeout=50)
        return response.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}


@st.cache_data(ttl=300)
def get_regions_cached():
    try:
        res = call_script("getRegions")
        if isinstance(res, dict) and "regions" in res:
            return res["regions"]
    except:
        pass
    return ["Liptov", "Bratislava", "Malacky", "Levice", "Banovce", "Zilina", "Orava", "Vranov"]


def get_data_stable():
    try:
        resp = requests.get(f"{SCRIPT_URL}?action=getZakazky", timeout=40)
        data = resp.json()

        if isinstance(data, list) and len(data) > 0:
            return pd.DataFrame(data)
    except Exception as e:
        st.error(str(e))

    return pd.DataFrame()


# --- 3. LOGIN / REGISTRÁCIA ---

if st.session_state['user'] is None:
    st.title("💰 Provízny systém TEPUJEM")

    tab1, tab2 = st.tabs(["Prihlásenie", "Registrácia"])

    # --- LOGIN ---
    with tab1:
        with st.form("login_form"):
            m = st.text_input("Mobil (login)").strip()
            h = st.text_input("Heslo", type="password").strip()

            if st.form_submit_button("Prihlásiť sa", use_container_width=True):
                with st.spinner("Overujem..."):
                    res = call_script("login", {"mobil": m, "heslo": h})

                    if res.get("status") == "success":
                        st.session_state['user'] = res
                        st.rerun()
                    else:
                        st.error("Nesprávne údaje.")

    # --- REGISTRÁCIA ---
    with tab2:
        st.subheader("Nový partner")

        with st.form("reg_form"):
            reg_pob = st.selectbox("Pobočka", get_regions_cached())
            reg_men = st.text_input("Meno a priezvisko")
            reg_mob = st.text_input("Mobil (Login)")
            reg_hes = st.text_input("Heslo (min. 6 znakov)", type="password")
            reg_kod = st.text_input("Váš unikátny kód")

            if st.form_submit_button("Zaregistrovať sa", use_container_width=True):
                if not all([reg_men, reg_mob, reg_hes, reg_kod]):
                    st.warning("Vyplňte všetky polia.")
                else:
                    with st.spinner("Zapisujem..."):
                        res = call_script("register", {
                            "pobocka": reg_pob,
                            "priezvisko": reg_men,
                            "mobil": reg_mob,
                            "heslo": reg_hes,
                            "kod": reg_kod
                        })

                        if res.get("status") == "success":
                            st.success("Úspešné! Prihláste sa.")
                            st.balloons()
                        else:
                            st.error(res.get("message", "Chyba registrácie"))


# --- 4. DASHBOARD ---
else:
    u = st.session_state['user']

    st.sidebar.title(f"👤 {u.get('meno')}")
    st.sidebar.info(f"Pobočka: {u.get('pobocka_id')}")

    if st.sidebar.button("Odhlásiť sa", use_container_width=True):
        st.session_state['user'] = None
        st.rerun()

    with st.spinner("Načítavam zákazky..."):
        df = get_data_stable()

    if df.empty:
        st.info("Žiadne zákazky.")
    else:
        # --- ČÍSELNÉ STĹPCE ---
        for col in ['suma_zakazky', 'provizia_odporucatel']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

        # --- VYPLATENÉ ---
        if 'vyplatene' in df.columns:
            df['vyplatene_bool'] = df['vyplatene'].astype(str).str.strip().str.upper() == 'TRUE'
            df['Stav'] = df['vyplatene_bool'].apply(lambda x: "Vyplatené ✅" if x else "Čaká ⏳")
        else:
            df['vyplatene_bool'] = False
            df['Stav'] = "Čaká ⏳"

        # --- ADMIN / SUPERADMIN ---
        if u['rola'] in ['admin', 'superadmin']:
            st.title(f"📊 Správa - {u.get('pobocka_id')}")

            active_df = df if u['rola'] == 'superadmin' else df[df['pobocka_id'] == u['pobocka_id']]

            t1, t2 = st.tabs(["📩 Na nacenenie", "💳 Na vyplatenie"])

            # --- NACENENIE ---
            with t1:
                k_naceneniu = active_df[active_df['suma_zakazky'] <= 0]

                if k_naceneniu.empty:
                    st.success("Všetko nacenené.")
                else:
                    for i, row in k_naceneniu.iterrows():
                        with st.expander(f"{row['poznamka']} ({row['pobocka_id']})"):
                            nova_suma = st.number_input("Suma (€)", key=f"s_{i}", min_value=0.0)

                            if st.button("Uložiť", key=f"b_{i}"):
                                res = call_script("updateSuma", {
                                    "row_index": row['row_index'],
                                    "suma": nova_suma
                                })

                                if res.get("status") == "success":
                                    st.success("Uložené")
                                    time.sleep(1)
                                    st.rerun()

            # --- VYPLATENIE ---
            with t2:
                k_vyplate = active_df[
                    (active_df['suma_zakazky'] > 0) &
                    (~active_df['vyplatene_bool'])
                ]

                if k_vyplate.empty:
                    st.info("Nič na vyplatenie.")
                else:
                    for kod in k_vyplate['kod_pouzity'].unique():
                        p_data = k_vyplate[k_vyplate['kod_pouzity'] == kod]

                        with st.expander(f"Partner {kod} | {p_data['provizia_odporucatel'].sum():.2f} €"):
                            st.table(p_data[['poznamka', 'provizia_odporucatel', 'Stav']])

                            if st.button("Vyplatiť", key=f"pay_{kod}"):
                                for _, r in p_data.iterrows():
                                    call_script("markAsPaid", {
                                        "row_index": r['row_index']
                                    })
                                st.rerun()

        # --- PARTNER ---
        else:
            st.title(f"💰 Váš prehľad ({u.get('kod')})")

            my_df = df[df['kod_pouzity'] == u['kod']].copy()

            c1, c2 = st.columns(2)
            c1.metric("Zarobené", f"{my_df['provizia_odporucatel'].sum():.2f} €")
            c2.metric("K výplate", f"{my_df[~my_df['vyplatene_bool']]['provizia_odporucatel'].sum():.2f} €")

            st.subheader("Prehľad")

            if my_df.empty:
                st.write("Žiadne záznamy.")
            else:
                st.table(my_df[['poznamka', 'provizia_odporucatel', 'Stav']])
