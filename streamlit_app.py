import streamlit as st
import pandas as pd
import requests
import base64
import os

# --- KONFIGURÁCIA ---
SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzLxqt5QwUvu2zha5NEOg97-7NtPLTbhMd2YQ3ORV6YRny7SvMZwBSgVQ6Zyd3u9v-IKw/exec"

st.set_page_config(page_title="TEPUJEM Portál", page_icon="💰", layout="wide")

# --- FUNKCIA NA NAČÍTANIE OBRÁZKA PRE POZADIE ---
def get_base64_of_bin_file(bin_file):
    try:
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except FileNotFoundError:
        return None

# --- APLIKÁCIA CSS POZADIA ---
img_base64 = get_base64_of_bin_file("image5.png")

if img_base64:
    page_bg_img = f'''
    <style>
    [data-testid="stAppViewContainer"] {{
        background-image: url("data:image/png;base64,{img_base64}");
        background-size: cover;
        background-position: center;
        background-repeat: no-repeat;
        background-attachment: fixed;
    }}
    /* Biele priesvitné pozadie pre obsah */
    [data-testid="stMainBlockContainer"] {{
        background-color: rgba(255, 255, 255, 0.85);
        padding: 2rem;
        border-radius: 15px;
    }}
    </style>
    '''
    st.markdown(page_bg_img, unsafe_allow_html=True)

# --- INICIALIZÁCIA ---
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
        df['pobocka_odporucatela'] = None
        df['meno_user'] = None
        df['mobil_user'] = None

    df['pridelena_pobocka'] = df['pobocka_odporucatela'].fillna(df['pobocka_id'])

    # --- ADMIN ---
    if u['rola'] in ['admin', 'superadmin']:
        st.title(f"📊 Správa - {u.get('pobocka_id')}")

        if u['rola'] == 'superadmin':
            active_df = df 
        else:
            active_df = df[df['pridelena_pobocka'] == u['pobocka_id']]

        t1, t2 = st.tabs(["Na nacenenie", "Na vyplatenie"])

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
            display_df = my_df.copy()
            display_df['Zárobok'] = display_df['provizia_odporucatel'].apply(lambda x: f"{x:.2f} €")
            display_df['Vyplatené'] = display_df['vyplatene_bool'].apply(lambda x: "áno" if x else "čaká sa")
            display_df.rename(columns={'poznamka': 'Poznámka'}, inplace=True)
            st.table(display_df[['Poznámka', 'Zárobok', 'Vyplatené']])
