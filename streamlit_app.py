import streamlit as st
import pandas as pd
import requests
import base64
import re
import time
from datetime import datetime

# --- 1. KONFIGURÁCIA A SECRETS ---
st.set_page_config(
    page_title="TEPUJEM Portál", 
    page_icon="💰", 
    layout="centered"
)

# Načítanie citlivých údajov zo Streamlit Secrets
try:
    SCRIPT_URL = st.secrets["SCRIPT_URL"]
    API_TOKEN = st.secrets["API_TOKEN"]
except Exception:
    st.error("Chýba konfigurácia (SCRIPT_URL alebo API_TOKEN) v Secrets!")
    st.stop()

# --- 2. POMOCNÉ FUNKCIE ---
def get_base64_of_bin_file(bin_file):
    """Načítanie obrázka pre pozadie."""
    try:
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except FileNotFoundError:
        return None

def call_script(action, params=None):
    """Univerzálne volanie Google skriptu s API Tokenom."""
    if params is None:
        params = {}
    params['action'] = action
    params['token'] = API_TOKEN
    
    try:
        response = requests.get(SCRIPT_URL, params=params, timeout=45)
        return response.json()
    except Exception as e:
        st.error(f"⚠️ Chyba komunikácie: {e}")
        return {"status": "error", "message": str(e)}

def validate_mobile(mob):
    """Validácia formátu mobilu 09XXXXXXXX."""
    return re.match(r'^09\d{8}$', mob) is not None

# --- 3. DÁTOVÉ FUNKCIE (ŽIVÉ DÁTA BEZ CACHE) ---

def get_regions():
    """Načíta pobočky z Google Sheets."""
    res = call_script("getRegions")
    return res.get("regions", ["Bratislava", "Liptov", "Malacky", "Levice", "Banovce", "Zilina", "Orava", "Vranov"])

def get_data():
    """Načíta transakcie s overením tokenu."""
    try:
        url = f"{SCRIPT_URL}?action=getZakazky&token={API_TOKEN}"
        response = requests.get(url, timeout=35)
        return pd.DataFrame(response.json())
    except:
        return pd.DataFrame()

def get_users():
    """Načíta užívateľov s overením tokenu."""
    try:
        url = f"{SCRIPT_URL}?action=getUsers&token={API_TOKEN}"
        response = requests.get(url, timeout=35)
        return pd.DataFrame(response.json())
    except:
        return pd.DataFrame()

# --- 4. CSS VIZUÁLNY ŠTÝL ---
img_base64 = get_base64_of_bin_file("image5.png")

if img_base64:
    st.markdown(f"""
    <style>
    [data-testid="stAppViewContainer"] {{
        background-image: url("data:image/png;base64,{img_base64}");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }}
    [data-testid="stAppViewContainer"]::before {{
        content: "";
        position: absolute;
        top: 0; left: 0; width: 100%; height: 100%;
        background: rgba(0, 0, 0, 0.78); 
        pointer-events: none;
    }}
    [data-testid="stMainBlockContainer"] {{
        max-width: 850px !important; 
        background-color: #1a1a1a !important; 
        padding: 3rem !important;
        border-radius: 25px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.6);
        margin-top: 30px;
        color: white !important;
    }}
    h1, h2, h3, label, p, span, div {{ color: white !important; font-family: 'Segoe UI', sans-serif; }}
    .stButton>button {{ width: 100%; border-radius: 10px; height: 3em; background-color: #333; border: 1px solid #555; }}
    input {{ background-color: #262626 !important; color: white !important; border-radius: 8px !important; border: 1px solid #444 !important; }}
    .stMetric {{ background-color: #262626; padding: 15px; border-radius: 15px; border: 1px solid #333; }}
    </style>
    """, unsafe_allow_html=True)

# --- 5. LOGIKA PRIHLÁSENIA A SESSION ---
if 'user' not in st.session_state:
    st.session_state['user'] = None

if st.session_state['user'] is None:
    st.title("💰 Zarob si s TEPUJEM.SK")
    t1, t2 = st.tabs(["Prihlásenie", "Registrácia partnera"])
    
    with t1:
        with st.form("login_form"):
            m = st.text_input("Mobil (09XXXXXXXX)")
            h = st.text_input("Heslo", type="password")
            if st.form_submit_button("Vstúpiť do portálu"):
                res = call_script("login", {"mobil": m, "heslo": h})
                if res.get("status") == "success":
                    st.session_state['user'] = res
                    st.rerun()
                else:
                    st.error("Nesprávne údaje alebo chyba zabezpečenia.")

    with t2:
        with st.form("reg_form"):
            pob = st.selectbox("Najbližšia pobočka", get_regions())
            meno = st.text_input("Meno")
            priezvisko = st.text_input("Priezvisko")
            adresa = st.text_input("Adresa")
            mob = st.text_input("Mobilné číslo (09XXXXXXXX)")
            hes = st.text_input("Heslo (min. 6 znakov)", type="password")
            kod = st.text_input("Váš unikátny kód (referral)")
            
            if st.form_submit_button("Založiť účet"):
                if not validate_mobile(mob):
                    st.error("Mobil musí byť v tvare 09XXXXXXXX.")
                elif not all([meno, priezvisko, adresa, mob, hes, kod]):
                    st.warning("Vyplňte všetky polia.")
                else:
                    # Fix pre nulu na začiatku
                    fixed_mob = f"'{mob}"
                    res = call_script("register", {
                        "pobocka": pob, "meno": meno, "priezvisko": priezvisko,
                        "adresa": adresa, "mobil": fixed_mob, "heslo": hes, "kod": kod
                    })
                    if res.get("status") == "success":
                        st.success("Registrácia úspešná! Teraz sa prihláste.")
                    else:
                        st.error("Tento mobil alebo kód sa už používa.")

# --- 6. DASHBOARD (PO PRIHLÁSENÍ) ---
else:
    u = st.session_state['user']
    st.sidebar.markdown(f"### Vitajte, **{u.get('meno')}**")
    st.sidebar.write(f"Rola: `{u.get('rola', 'partner')}`")
    if st.sidebar.button("Odhlásiť sa"):
        st.session_state['user'] = None
        st.rerun()

    # Načítanie čerstvých dát
    df = get_data()
    users = get_users()

    if df.empty:
        st.info("Zatiaľ žiadne zákazky.")
    else:
        # Čistenie dát
        df['suma_zakazky'] = pd.to_numeric(df['suma_zakazky'], errors='coerce').fillna(0)
        df['provizia_odporucatel'] = pd.to_numeric(df['provizia_odporucatel'], errors='coerce').fillna(0)
        df['vyplatene_bool'] = df['vyplatene'].astype(str).str.strip().str.upper() == "TRUE"

        # Merge s užívateľmi pre admina
        if not users.empty:
            u_clean = users.rename(columns={'referral_code': 'kod_pouzity', 'mobil': 'tel_P', 'pobocka': 'mesto_P'})
            df = df.merge(u_clean[['kod_pouzity', 'meno', 'priezvisko', 'tel_P', 'mesto_P', 'adresa']], on='kod_pouzity', how='left')

        # --- ADMIN / SUPERADMIN SEKCOIA ---
        if u['rola'] in ['admin', 'superadmin']:
            st.title("📊 Administrácia")
            active_df = df if u['rola'] == 'superadmin' else df[(df['pobocka_id'] == u['pobocka']) | (df['mesto_P'] == u['pobocka'])]

            t1, t2 = st.tabs(["📩 Čaká na nacenenie", "💳 Čaká na výplatu"])

            with t1:
                nac = active_df[active_df['suma_zakazky'] <= 0]
                if nac.empty: st.success("Všetko je nacenené.")
                for i, row in nac.iterrows():
                    with st.expander(f"Zákazník: {row['poznamka']} | Partner: {row.get('meno', '---')}"):
                        st.write(f"Kontakt: {row.get('tel_P', '---')} | Adresa: {row.get('adresa', '---')}")
                        s = st.number_input("Suma zákazky (€)", key=f"sum_{i}", min_value=0.0)
                        if st.button("Uložiť sumu", key=f"btn_{i}"):
                            call_script("updateSuma", {"row_index": row['row_index'], "suma": s})
                            time.sleep(1)
                            st.rerun()

            with t2:
                vyp = active_df[(active_df['suma_zakazky'] > 0) & (~active_df['vyplatene_bool'])]
                if vyp.empty: st.info("Žiadne provízie k výplate.")
                else:
                    for kod in vyp['kod_pouzity'].unique():
                        p_rows = vyp[vyp['kod_pouzity'] == kod]
                        with st.expander(f"Partner: {kod} | Suma: {p_rows['provizia_odporucatel'].sum():.2f} €"):
                            st.dataframe(p_rows[['poznamka', 'suma_zakazky', 'provizia_odporucatel']])
                            if st.button(f"Označiť ako vyplatené ({kod})", key=f"p_{kod}"):
                                for idx in p_rows['row_index']:
                                    call_script("markAsPaid", {"row_index": idx})
                                st.rerun()

        # --- PARTNER SEKCOIA ---
        else:
            st.title("💰 Moje provízie")
            my_df = df[df['kod_pouzity'] == u['kod']]
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Zákazky", len(my_df))
            c2.metric("Zárobok", f"{my_df['provizia_odporucatel'].sum():.2f} €")
            c3.metric("K výplate", f"{my_df[~my_df['vyplatene_bool']]['provizia_odporucatel'].sum():.2f} €")
            
            st.divider()
            st.write("### História vašich odporúčaní")
            if my_df.empty:
                st.info("Zatiaľ ste neodporučili žiadnu zákazku.")
            else:
                res_df = my_df[['poznamka', 'suma_zakazky', 'provizia_odporucatel', 'vyplatene']].copy()
                res_df.columns = ['Zákazník', 'Suma (€)', 'Moja provízia', 'Stav']
                st.table(res_df)
