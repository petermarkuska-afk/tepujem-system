import streamlit as st
import pandas as pd
import requests
import base64
import re

# --- KONFIGURÁCIA ---
st.set_page_config(page_title="TEPUJEM Portál", page_icon="💰", layout="centered")

SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzLxqt5QwUvu2zha5NEOg97-7NtPLTbhMd2YQ3ORV6YRny7SvMZwBSgVQ6Zyd3u9v-IKw/exec"

# --- FUNKCIA NA NAČÍTANIE OBRÁZKA ---
def get_base64_of_bin_file(bin_file):
    try:
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except FileNotFoundError:
        return None

# --- CSS PRE VZHĽAD (Dark mode karta + biele inputy) ---
img_base64 = get_base64_of_bin_file("image5.png")

css = """
<style>
/* Pozadie celej stránky */
[data-testid="stAppViewContainer"] {
    background-image: url("data:image/png;base64,REPLACE_ME");
    background-size: cover;
    background-position: center;
    background-attachment: fixed;
}
/* Tmavý filter */
[data-testid="stAppViewContainer"]::before {
    content: "";
    position: absolute;
    top: 0; left: 0; width: 100%; height: 100%;
    background: rgba(0, 0, 0, 0.7); 
    pointer-events: none;
}
/* Karta pre obsah */
[data-testid="stMainBlockContainer"] {
    max-width: 800px !important; 
    background-color: #1e1e1e !important; 
    padding: 30px !important;
    border-radius: 20px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.8);
    margin-top: 50px;
    color: white !important;
}
[data-testid="stMainBlockContainer"] *, label, h1, p { color: white !important; }
input { background-color: #333333 !important; color: white !important; border: 1px solid #555 !important; }
button { background-color: #444 !important; color: white !important; border: 1px solid #666 !important; }
</style>
"""
if img_base64: st.markdown(css.replace("REPLACE_ME", img_base64), unsafe_allow_html=True)

# --- API ---
def call_script(action, params=None):
    if params is None: params = {}
    params['action'] = action
    try: return requests.get(SCRIPT_URL, params=params, timeout=40).json()
    except: return {}

@st.cache_data(ttl=300)
def get_regions(): return call_script("getRegions").get("regions", [])

@st.cache_data(ttl=300)
def get_data():
    try: return pd.DataFrame(requests.get(f"{SCRIPT_URL}?action=getZakazky").json())
    except: return pd.DataFrame()

@st.cache_data(ttl=300)
def get_users():
    try: return pd.DataFrame(requests.get(f"{SCRIPT_URL}?action=getUsers").json())
    except: return pd.DataFrame()

# --- VALIDÁCIA MOBILU ---
def validate_mobile(mob):
    pattern = r'^09\d{8}$'
    return re.match(pattern, mob) is not None

# --- APP LOGIKA ---
if 'user' not in st.session_state: st.session_state['user'] = None

if st.session_state['user'] is None:
    st.title("💰 Zarob si s TEPUJEM.SK")
    tab1, tab2 = st.tabs(["Prihlásenie", "Registrácia"])
    
    with tab1:
        with st.form("login"):
            m = st.text_input("Mobilné číslo (napr. 0912345678)")
            h = st.text_input("Heslo", type="password")
            if st.form_submit_button("Login"):
                if not validate_mobile(m): st.error("Mobil musí byť v tvare 09XXXXXXXX!")
                else:
                    res = call_script("login", {"mobil": m, "heslo": h})
                    if res.get("status") == "success":
                        st.session_state['user'] = res
                        st.rerun()
                    else: st.error("Zlé údaje")
    with tab2:
        with st.form("register"):
            pob = st.selectbox("Vyber si svoj región", get_regions())
            meno = st.text_input("Meno")
            priezvisko = st.text_input("Priezvisko")
            adresa = st.text_input("Adresa")
            mob = st.text_input("Mobilné číslo (09XXXXXXXX)")
            hes = st.text_input("Heslo", type="password")
            kod = st.text_input("Kód (vlastný unikátny kód)")
            
            if st.form_submit_button("Registrovať"):
                if not validate_mobile(mob): st.error("Mobilné číslo musí byť v tvare 09XXXXXXXX!")
                elif not all([meno, priezvisko, adresa, mob, hes, kod]): st.warning("Vyplň všetky polia!")
                else:
                    res = call_script("register", {
                        "pobocka": pob, "meno": meno, "priezvisko": priezvisko,
                        "adresa": adresa, "mobil": mob, "heslo": hes, "kod": kod
                    })
                    if res.get("status") == "success":
                        get_users.clear() 
                        st.success("Registrácia úspešná! Teraz sa môžete prihlásiť.")

else:
    u = st.session_state['user']
    st.sidebar.title(f"👤 {u.get('meno')}")
    if st.sidebar.button("Odhlásiť"): st.session_state['user'] = None; st.rerun()

    df = get_data()
    users = get_users()
    if df.empty: st.warning("Žiadne dáta."); st.stop()

    df['suma_zakazky'] = pd.to_numeric(df['suma_zakazky'], errors='coerce').fillna(0)
    df['provizia_odporucatel'] = pd.to_numeric(df['provizia_odporucatel'], errors='coerce').fillna(0)
    df['vyplatene_bool'] = df['vyplatene'].astype(str).str.strip().str.upper() == "TRUE"

    if not users.empty:
        users_renamed = users.rename(columns={
            'referral_code': 'kod_pouzity', 
            'meno': 'meno_partnera',
            'priezvisko': 'priezvisko_partnera',
            'adresa': 'adresa_partnera',
            'mobil': 'mobil_partnera', 
            'pobocka': 'pobocka_partnera' 
        })
        df = df.merge(
            users_renamed[['kod_pouzity', 'meno_partnera', 'priezvisko_partnera', 'adresa_partnera', 'mobil_partnera', 'pobocka_partnera']], 
            on='kod_pouzity', how='left'
        )
    else:
        df['pobocka_partnera'] = None

    # --- ADMIN ---
    if u['rola'] in ['admin', 'superadmin']:
        st.title(f"📊 Správa - {u.get('pobocka_id')}")
        
        if u['rola'] == 'superadmin': active_df = df
        else: active_df = df[(df['pobocka_id'] == u['pobocka_id']) | (df['pobocka_partnera'] == u['pobocka_id'])]

        t1, t2 = st.tabs(["Na nacenenie", "Na vyplatenie"])
        with t1:
            nac = active_df[active_df['suma_zakazky'] <= 0]
            if nac.empty: st.success("Všetko nacenené! 👍")
            else:
                for i, row in nac.iterrows():
                    partner_info = f"{row.get('meno_partnera', 'Priama')} {row.get('priezvisko_partnera', '')}"
                    contact_info = f"Tel: {row.get('mobil_partnera', '-')}, Adresa: {row.get('adresa_partnera', '-')}"
                    with st.expander(f"Zákazník: {row.get('poznamka')} | Partner: {partner_info}"):
                        st.write(f"Kontaktné údaje: {contact_info}")
                        suma = st.number_input("Suma €", key=f"s_{i}", min_value=0.0, step=1.0)
                        if st.button("Uložiť", key=f"b_{i}"):
                            call_script("updateSuma", {"row_index": row['row_index'], "suma": suma})
                            get_data.clear(); st.rerun()
        with t2:
            pay = active_df[(active_df['suma_zakazky'] > 0) & (~active_df['vyplatene_bool'])]
            if pay.empty: st.info("Nič na vyplatenie.")
            else:
                for kod in pay['kod_pouzity'].dropna().unique():
                    p_data = pay[pay['kod_pouzity'] == kod]
                    meno = f"{p_data['meno_partnera'].iloc[0]} {p_data['priezvisko_partnera'].iloc[0]}"
                    mobil = p_data['mobil_partnera'].iloc[0]
                    adresa = p_data['adresa_partnera'].iloc[0]
                    with st.expander(f"Partner: {meno} (Tel: {mobil}, Adresa: {adresa}) | Spolu: {p_data['provizia_odporucatel'].sum():.2f} €"):
                        disp = p_data[['poznamka', 'provizia_odporucatel', 'pobocka_id']].copy()
                        disp.columns = ['Poznámka', 'Provízia', 'Mesto']
                        st.table(disp)
                        if st.button("Označiť všetko ako vyplatené", key=f"pay_{kod}"):
                            for _, r in p_data.iterrows(): call_script("markAsPaid", {"row_index": r['row_index']})
                            get_data.clear(); st.rerun()
    
    # --- PARTNER ---
    else:
        st.title("💰 Môj prehľad")
        my_df = df[df['kod_pouzity'] == u['kod']]
        st.metric("Zarobené celkovo", f"{my_df['provizia_odporucatel'].sum():.2f} €")
        st.metric("Čaká na výplatu", f"{my_df[~my_df['vyplatene_bool']]['provizia_odporucatel'].sum():.2f} €")
        
        if not my_df.empty:
            display_df = my_df[['poznamka', 'provizia_odporucatel', 'vyplatene', 'pobocka_id']].copy()
            display_df.columns = ['Poznámka', 'Zárobok', 'Vyplatené', 'Mesto']
            st.table(display_df)
