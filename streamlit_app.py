import streamlit as st
import pandas as pd
import requests
import time

SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzLxqt5QwUvu2zha5NEOg97-7NtPLTbhMd2YQ3ORV6YRny7SvMZwBSgVQ6Zyd3u9v-IKw/exec"

st.set_page_config(page_title="TEPUJEM Portál", page_icon="💰", layout="wide")

if 'user' not in st.session_state:
    st.session_state['user'] = None


# --- API ---
def call_script(action, params=None):
    if params is None:
        params = {}
    params['action'] = action

    try:
        return requests.get(SCRIPT_URL, params=params, timeout=40).json()
    except:
        return {}


@st.cache_data(ttl=300)
def get_regions():
    res = call_script("getRegions")
    return res.get("regions", [])


@st.cache_data(ttl=300)
def get_data():
    try:
        return pd.DataFrame(requests.get(f"{SCRIPT_URL}?action=getZakazky").json())
    except:
        return pd.DataFrame()


@st.cache_data(ttl=300)
def get_users():
    try:
        return pd.DataFrame(requests.get(f"{SCRIPT_URL}?action=getUsers").json())
    except:
        return pd.DataFrame()


# --- LOGIN / REGISTER ---
if st.session_state['user'] is None:
    # ZMENENÝ NÁZOV PROJEKTU
    st.title("💰 Zarob si s TEPUJEM.SK")

    tab1, tab2 = st.tabs(["Prihlásenie", "Registrácia"])

    with tab1:
        with st.form("login"):
            m = st.text_input("Mobil")
            h = st.text_input("Heslo", type="password")

            if st.form_submit_button("Login"):
                res = call_script("login", {"mobil": m, "heslo": h})
                if res.get("status") == "success":
                    st.session_state['user'] = res
                    st.rerun()
                else:
                    st.error("Zlé údaje")

    with tab2:
        with st.form("register"):
            pob = st.selectbox("Pobočka", get_regions())
            meno = st.text_input("Meno")
            mob = st.text_input("Mobil")
            hes = st.text_input("Heslo", type="password")
            kod = st.text_input("Kód")

            if st.form_submit_button("Registrovať"):
                if not all([meno, mob, hes, kod]):
                    st.warning("Vyplň všetko")
                else:
                    res = call_script("register", {
                        "pobocka": pob,
                        "priezvisko": meno,
                        "mobil": mob,
                        "heslo": hes,
                        "kod": kod
                    })
                    if res.get("status") == "success":
                        get_users.clear() 
                        st.success("Hotovo. Teraz sa môžete prihlásiť.")


# --- DASHBOARD ---
else:
    u = st.session_state['user']

    st.sidebar.title(f"👤 {u.get('meno')}")
    if st.sidebar.button("Odhlásiť"):
        st.session_state['user'] = None
        st.rerun()

    df = get_data()
    users = get_users()

    if df.empty:
        st.warning("Žiadne dáta v tabuľke zákaziek.")
        st.stop()

    # --- CLEAN ---
    df['suma_zakazky'] = pd.to_numeric(df['suma_zakazky'], errors='coerce').fillna(0)
    df['provizia_odporucatel'] = pd.to_numeric(df['provizia_odporucatel'], errors='coerce').fillna(0)
    df['vyplatene_bool'] = df['vyplatene'].astype(str).str.strip().str.upper() == "TRUE"

    # --- JOIN USERS ---
    if not users.empty:
        # Pripájame zľavový kód k používateľovi a ťaháme si aj jeho "pobočku"
        users_renamed = users.rename(columns={
            'referral_code': 'kod_pouzity',
            'priezvisko': 'meno_user',
            'mobil': 'mobil_user',
            'meno': 'pobocka_odporucatela'
        })

        df = df.merge(
            users_renamed[['kod_pouzity', 'meno_user', 'mobil_user', 'pobocka_odporucatela']],
            on='kod_pouzity',
            how='left'
        )
    else:
        # Poistka, ak by z nejakého dôvodu tabuľka users bola úplne prázdna
        df['pobocka_odporucatela'] = None
        df['meno_user'] = None
        df['mobil_user'] = None

    # Vytvorenie finálneho stĺpca pre priradenie pobočky 
    # (Ak je kód zadaný a spárovaný s users_data, dá pobočku odporúčateľa. Inak použije tú z tabuľky transactions_data)
    df['pridelena_pobocka'] = df['pobocka_odporucatela'].fillna(df['pobocka_id'])


    # --- ADMIN ---
    if u['rola'] in ['admin', 'superadmin']:
        st.title(f"📊 Správa - {u.get('pobocka_id')}")

        # Filtrujeme dáta podľa nášho "inteligentného" stĺpca 'pridelena_pobocka'
        if u['rola'] == 'superadmin':
            active_df = df 
        else:
            active_df = df[df['pridelena_pobocka'] == u['pobocka_id']]

        t1, t2 = st.tabs(["Na nacenenie", "Na vyplatenie"])

        # --- NACENENIE ---
        with t1:
            nac = active_df[active_df['suma_zakazky'] <= 0]

            if nac.empty:
                st.success("Máte všetko nacenené! 👍")
            else:
                for i, row in nac.iterrows():
                    meno = row.get('meno_user', 'Neznámy')
                    mobil = row.get('mobil_user', '')

                    with st.expander(f"{meno} ({mobil}) - {row['poznamka']}"):
                        suma = st.number_input("Suma €", key=f"s_{i}", min_value=0.0, step=1.0)

                        if st.button("Uložiť", key=f"b_{i}"):
                            call_script("updateSuma", {
                                "row_index": row['row_index'],
                                "suma": suma
                            })
                            get_data.clear()
                            st.rerun()

        # --- VYPLATENIE ---
        with t2:
            pay = active_df[(active_df['suma_zakazky'] > 0) & (~active_df['vyplatene_bool'])]

            if pay.empty:
                st.info("Nič na vyplatenie.")
            else:
                for kod in pay['kod_pouzity'].unique():
                    p_data = pay[pay['kod_pouzity'] == kod]

                    meno = p_data['meno_user'].iloc[0] if not p_data['meno_user'].isna().all() else "Neznámy"
                    mobil = p_data['mobil_user'].iloc[0] if not p_data['mobil_user'].isna().all() else ""

                    with st.expander(f"{meno} ({mobil}) | Spolu na výplatu: {p_data['provizia_odporucatel'].sum():.2f} €"):
                        
                        # Pekné zobrazenie v tabuľke pred vyplatením
                        disp_pay = p_data.copy()
                        disp_pay['Suma provízie'] = disp_pay['provizia_odporucatel'].apply(lambda x: f"{x:.2f} €")
                        disp_pay.rename(columns={'poznamka': 'Poznámka'}, inplace=True)
                        st.table(disp_pay[['Poznámka', 'Suma provízie']])

                        if st.button("Označiť ako vyplatené", key=f"pay_{kod}"):
                            for _, r in p_data.iterrows():
                                call_script("markAsPaid", {"row_index": r['row_index']})
                            get_data.clear()
                            st.rerun()

    # --- PARTNER (Odporúčateľ) ---
    else:
        st.title("💰 Môj prehľad")

        my_df = df[df['kod_pouzity'] == u['kod']]

        st.metric("Zarobené celkovo", f"{my_df['provizia_odporucatel'].sum():.2f} €")
        st.metric("Čaká na výplatu", f"{my_df[~my_df['vyplatene_bool']]['provizia_odporucatel'].sum():.2f} €")

        if my_df.empty:
            st.write("Zatiaľ nemáte žiadne odporúčania.")
        else:
            # Vytvoríme si kópiu dát na zobrazenie pre partnera
            display_df = my_df.copy()
            
            # Formátujeme zárobok na 2 desatinné miesta so znakom €
            display_df['Zárobok'] = display_df['provizia_odporucatel'].apply(lambda x: f"{x:.2f} €")
            
            # Vytvoríme stĺpec Vyplatené (áno / čaká sa) podľa hodnoty z vyplatene_bool
            display_df['Vyplatené'] = display_df['vyplatene_bool'].apply(lambda x: "áno" if x else "čaká sa")
            
            # Premenujeme stĺpec poznamka
            display_df.rename(columns={'poznamka': 'Poznámka'}, inplace=True)
            
            # Zobrazíme iba vybrané stĺpce v správnom poradí
            st.table(display_df[['Poznámka', 'Zárobok', 'Vyplatené']])
