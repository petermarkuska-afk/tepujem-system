import streamlit as st
import pandas as pd
import requests
import base64
import re

# --- KONFIGURÁCIA ---
st.set_page_config(page_title="TEPUJEM Portál", page_icon="💰", layout="centered")

SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzLxqt5QwUvu2zha5NEOg97-7NtPLTbhMd2YQ3ORV6YRny7SvMZwBSgVQ6Zyd3u9v-IKw/exec"

# --- FUNKCIE PRE PRÁCU S DÁTAMI ---
def get_base64_of_bin_file(bin_file):
    try:
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except FileNotFoundError:
        return None

def call_script(action, params=None):
    if params is None: params = {}
    params['action'] = action
    try:
        response = requests.get(SCRIPT_URL, params=params, timeout=40)
        return response.json()
    except Exception as e:
        st.error(f"Chyba pripojenia: {e}")
        return {}

@st.cache_data(ttl=300)
def get_regions():
    res = call_script("getRegions")
    return res.get("regions", [])

@st.cache_data(ttl=300)
def get_data():
    try:
        data = requests.get(f"{SCRIPT_URL}?action=getZakazky").json()
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

@st.cache_data(ttl=300)
def get_users():
    try:
        data = requests.get(f"{SCRIPT_URL}?action=getUsers").json()
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

def validate_mobile(mob):
    pattern = r'^09\d{8}$'
    return re.match(pattern, mob) is not None

# --- CSS ŠTÝLY ---
img_base64 = get_base64_of_bin_file("image5.png")
css = """
<style>
[data-testid="stAppViewContainer"] { background-image: url("data:image/png;base64,REPLACE_ME"); background-size: cover; background-position: center; background-attachment: fixed; }
[data-testid="stAppViewContainer"]::before { content: ""; position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0, 0, 0, 0.7); pointer-events: none; }
[data-testid="stMainBlockContainer"] { max-width: 800px !important; background-color: #1e1e1e !important; padding: 40px !important; border-radius: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.8); margin-top: 50px; color: white !important; }
[data-testid="stMainBlockContainer"] *, label, h1, p { color: white !important; }
input { background-color: #333333 !important; color: white !important; border: 1px solid #555 !important; }
button { background-color: #444 !important; color: white !important; border: 1px solid #666 !important; }
</style>
"""
if img_base64: st.markdown(css.replace("REPLACE_ME", img_base64), unsafe_allow_html=True)

# --- HLAVNÝ PROGRAM ---
if 'user' not in st.session_state: st.session_state['user'] = None

if st.session_state['user'] is None:
    st.title("💰 Zarob si s TEPUJEM.SK")
    tab1, tab2 = st.tabs(["Prihlásenie", "Registrácia"])
    
    with tab1:
        with st.form("login_form"):
            m = st.text_input("Mobilné číslo (09XXXXXXXX)")
            h = st.text_input("Heslo", type="password")
            if st.form_submit_button("Prihlásiť"):
                if not validate_mobile(m): st.error("Mobil musí byť v tvare 09XXXXXXXX!")
                else:
                    res = call_script("login", {"mobil": m, "heslo": h})
                    if res.get("status") == "success":
                        st.session_state['user'] = res
                        st.rerun()
                    else: st.error("Zlé údaje.")

    with tab2:
        with st.form("register_form"):
            pob = st.selectbox("Vyber si svoj región", get_regions())
            meno = st.text_input("Meno")
            priezvisko = st.text_input("Priezvisko")
            adresa = st.text_input("Adresa")
            mob = st.text_input("Mobilné číslo (09XXXXXXXX)")
            hes = st.text_input("Heslo", type="password")
            kod = st.text_input("Kód (vlastný unikátny kód)")
            
            if st.form_submit_button("Registrovať"):
                if not validate_mobile(mob): st.error("Mobil musí byť v tvare 09XXXXXXXX!")
                elif not all([meno, priezvisko, adresa, mob, hes, kod]): st.warning("Vyplň všetky polia!")
                else:
                    res = call_script("register", {
                        "pobocka": pob, "meno": meno, "priezvisko": priezvisko,
                        "adresa": adresa, "mobil": mob, "heslo": hes, "kod": kod
                    })
                    if res.get("status") == "success":
                        get_users.clear()
                        st.success("Registrácia úspešná!")
                    else: st.error("Chyba pri registrácii.")

else:
    u = st.session_state['user']
    st.sidebar.title(f"👤 {u.get('meno')}")
    if st.sidebar.button("Odhlásiť"): st.session_state['user'] = None; st.rerun()

    df = get_data()
    users = get_users()
    if df.empty: st.warning("Žiadne dáta v systéme."); st.stop()

    # Čistenie dát
    df['suma_zakazky'] = pd.to_numeric(df['suma_zakazky'], errors='coerce').fillna(0)
    df['provizia_odporucatel'] = pd.to_numeric(df['provizia_odporucatel'], errors='coerce').fillna(0)
    df['vyplatene_bool'] = df['vyplatene'].astype(str).str.strip().str.upper() == "TRUE"

    # BEZPEČNÝ JOIN
    if not users.empty:
        # Preusporiadanie pre bezpečný merge
        # Predpokladáme názvy stĺpcov z Google Sheet: meno, priezvisko, adresa, mobil, referral_code, pobocka (A)
        users_clean = users.rename(columns={
            'referral_code': 'kod_pouzity',
            'meno': 'meno_partnera',
            'priezvisko': 'priezvisko_partnera',
            'adresa': 'adresa_partnera',
            'mobil': 'mobil_partnera'
        })
        
        # Merge - spájame stĺpce, ak existujú
        df = df.merge(
            users_clean[['kod_pouzity', 'meno_partnera', 'priezvisko_partnera', 'adresa_partnera', 'mobil_partnera']], 
            on='kod_pouzity', 
            how='left'
        )

    # --- ADMIN VIEW ---
    if u['rola'] in ['admin', 'superadmin']:
        st.title(f"📊 Správa - {u.get('pobocka_id')}")
        
        # Admin vidí všetko pre danú pobočku (alebo všetko ak superadmin)
        if u['rola'] == 'superadmin': active_df = df
        else: active_df = df[df['pobocka_id'] == u['pobocka_id']]

        t1, t2 = st.tabs(["Na nacenenie", "Na vyplatenie"])

        with t1:
            nac = active_df[active_df['suma_zakazky'] <= 0]
            if nac.empty: st.success("Všetko nacenené! 👍")
            else:
                for i, row in nac.iterrows():
                    m = row.get('meno_partnera', 'Priama')
                    p = row.get('priezvisko_partnera', '')
                    a = row.get('adresa_partnera', '---')
                    tel = row.get('mobil_partnera', '---')
                    
                    with st.expander(f"Zákazník: {row.get('poznamka')} | Partner: {m} {p}"):
                        st.write(f"Údaje partnera: {m} {p}, {a}, Tel: {tel}")
                        suma = st.number_input("Suma €", key=f"s_{i}", min_value=0.0, step=1.0)
                        if st.button("Uložiť", key=f"b_{i}"):
                            call_script("updateSuma", {"row_index": row['row_index'], "suma": suma})
                            get_data.clear(); st.rerun()

        with t2:
            pay = active_df[(active_df['suma_zakazky'] > 0) & (~active_df['vyplatene_bool'])]
            if pay.empty: st.info("Nič na vyplatenie.")
            else:
                # Zoskupíme podľa kódu
                for kod in pay['kod_pouzity'].dropna().unique():
                    p_data = pay[pay['kod_pouzity'] == kod]
                    m = p_data['meno_partnera'].iloc[0]
                    p = p_data['priezvisko_partnera'].iloc[0]
                    tel = p_data['mobil_partnera'].iloc[0]
                    adr = p_data['adresa_partnera'].iloc[0]
                    
                    with st.expander(f"Partner: {m} {p} (Tel: {tel}) | Spolu: {p_data['provizia_odporucatel'].sum():.2f} €"):
                        st.write(f"Adresa: {adr}")
                        disp = p_data[['poznamka', 'provizia_odporucatel', 'pobocka_id']].copy()
                        disp.columns = ['Poznámka', 'Provízia', 'Mesto']
                        st.table(disp)
                        
                        if st.button("Označiť všetko ako vyplatené", key=f"pay_{kod}"):
                            for _, r in p_data.iterrows():
                                call_script("markAsPaid", {"row_index": r['row_index']})
                            get_data.clear(); st.rerun()

    # --- PARTNER VIEW ---
    else:
        st.title("💰 Môj prehľad")
        my_df = df[df['kod_pouzity'] == u['kod']]
        st.metric("Zarobené celkovo", f"{my_df['provizia_odporucatel'].sum():.2f} €")
        
        if not my_df.empty:
            display_df = my_df[['poznamka', 'provizia_odporucatel', 'vyplatene', 'pobocka_id']].copy()
            display_df.columns = ['Poznámka', 'Zárobok', 'Vyplatené', 'Mesto']
            st.table(display_df)
