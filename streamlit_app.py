import streamlit as st
import pandas as pd
import requests
import base64
import re
import time
from datetime import datetime

# --- 1. KONFIGURÁCIA ---
st.set_page_config(
    page_title="TEPUJEM Portál", 
    page_icon="💰", 
    layout="centered"
)

# URL tvojho Google Apps Scriptu
SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzLxqt5QwUvu2zha5NEOg97-7NtPLTbhMd2YQ3ORV6YRny7SvMZwBSgVQ6Zyd3u9v-IKw/exec"

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
    """Univerzálne volanie Google skriptu."""
    if params is None: params = {}
    params['action'] = action
    try:
        response = requests.get(SCRIPT_URL, params=params, timeout=45)
        return response.json()
    except Exception as e:
        st.error(f"⚠️ Problém s databázou: {e}")
        return {"status": "error", "message": str(e)}

def validate_mobile(mob):
    """Kontrola správneho formátu mobilu 09XXXXXXXX."""
    return re.match(r'^09\d{8}$', mob) is not None

# --- 3. DÁTOVÉ FUNKCIE (VŽDY NAŽIVO BEZ CACHE) ---

def get_regions():
    res = call_script("getRegions")
    return res.get("regions", ["Bratislava", "Liptov", "Malacky", "Levice", "Banovce", "Zilina", "Orava", "Vranov"])

def get_data():
    try:
        response = requests.get(f"{SCRIPT_URL}?action=getZakazky", timeout=35)
        return pd.DataFrame(response.json())
    except:
        return pd.DataFrame()

def get_users():
    try:
        response = requests.get(f"{SCRIPT_URL}?action=getUsers", timeout=35)
        return pd.DataFrame(response.json())
    except:
        return pd.DataFrame()

# --- 4. CSS ŠTÝLY (VIZUÁL) ---
img_base64 = get_base64_of_bin_file("image5.png")
if img_base64:
    st.markdown(f"""
    <style>
    [data-testid="stAppViewContainer"] {{
        background-image: url("data:image/png;base64,{img_base64}");
        background-size: cover; background-position: center; background-attachment: fixed;
    }}
    [data-testid="stAppViewContainer"]::before {{
        content: ""; position: absolute; top: 0; left: 0; width: 100%; height: 100%;
        background: rgba(0, 0, 0, 0.82); pointer-events: none;
    }}
    [data-testid="stMainBlockContainer"] {{
        max-width: 850px !important; background-color: #121212 !important; 
        padding: 3rem !important; border-radius: 30px; border: 1px solid #333;
        margin-top: 30px; color: white !important;
    }}
    .stMetric {{ background-color: #1e1e1e; padding: 15px; border-radius: 15px; border: 1px solid #333; }}
    h1, h2, h3, label, p, span {{ color: white !important; font-family: 'Segoe UI', sans-serif; }}
    input {{ background-color: #222 !important; color: white !important; border: 1px solid #444 !important; }}
    .stButton>button {{ background-color: #444; color: white; border-radius: 10px; border: 1px solid #666; }}
    </style>
    """, unsafe_allow_html=True)

# --- 5. SESSION STATE ---
if 'user' not in st.session_state:
    st.session_state['user'] = None

# --- 6. VSTUPNÁ BRÁNA (LOGIN / REGISTRÁCIA) ---
if st.session_state['user'] is None:
    st.title("💰 Provízny portál TEPUJEM")
    t_log, t_reg = st.tabs(["🔒 Prihlásenie", "📝 Registrácia partnera"])
    
    with t_log:
        with st.form("login_form"):
            login_mob = st.text_input("Mobil (09XXXXXXXX)").strip()
            login_hes = st.text_input("Heslo", type="password").strip()
            if st.form_submit_button("Vstúpiť do systému", use_container_width=True):
                # Pri prihlásení posielame čisté číslo, Script si ho nájde
                res = call_script("login", {"mobil": login_mob, "heslo": login_hes})
                if res.get("status") == "success":
                    st.session_state['user'] = res
                    st.rerun()
                else:
                    st.error("Nesprávne prihlasovacie údaje.")

    with t_reg:
        with st.form("register_form"):
            st.subheader("Nový partner")
            c1, c2 = st.columns(2)
            r_meno = c1.text_input("Meno")
            r_priez = c2.text_input("Priezvisko")
            r_mob = st.text_input("Mobil (09XXXXXXXX)")
            r_pob = st.selectbox("Pobočka", get_regions())
            r_kod = st.text_input("Váš kód (napr. FERKO10)")
            r_hes = st.text_input("Heslo (min. 6 znakov)", type="password")
            
            if st.form_submit_button("Vytvoriť účet", use_container_width=True):
                if not validate_mobile(r_mob):
                    st.error("Chybný formát mobilu! Musí začínať 09...")
                elif len(r_hes) < 6:
                    st.warning("Heslo je príliš krátke.")
                elif not all([r_meno, r_priez, r_mob, r_kod]):
                    st.warning("Vyplňte všetky povinné polia.")
                else:
                    # --- KĽÚČOVÁ OPRAVA: PRIDÁVAME APOSTROF PRED ČÍSLO ---
                    # Toto prinúti Google Sheets nechať nulu na začiatku
                    fixed_mob = f"'{r_mob}"
                    
                    res = call_script("register", {
                        "pobocka": r_pob, "meno": r_meno, "priezvisko": r_priez,
                        "mobil": fixed_mob, "heslo": r_hes, "kod": r_kod
                    })
                    if res.get("status") == "success":
                        st.success("Registrácia úspešná! Teraz sa môžete prihlásiť.")
                    else:
                        st.error(f"Chyba: {res.get('message', 'Mobil alebo kód už existuje.')}")

# --- 7. HLAVNÝ DASHBOARD ---
else:
    u = st.session_state['user']
    st.sidebar.markdown(f"### 👤 {u['meno']} {u.get('priezvisko', '')}")
    st.sidebar.write(f"ID: `{u.get('kod')}`")
    if st.sidebar.button("Odhlásiť sa", use_container_width=True):
        st.session_state['user'] = None
        st.rerun()

    # Načítanie čerstvých dát
    with st.spinner("Aktualizujem dáta z tabuľky..."):
        df = get_data()
        users = get_users()

    if df.empty:
        st.info("Momentálne nie sú evidované žiadne zákazky.")
    else:
        # Čistenie číselných dát
        df['suma_zakazky'] = pd.to_numeric(df['suma_zakazky'], errors='coerce').fillna(0)
        df['provizia_odporucatel'] = pd.to_numeric(df['provizia_odporucatel'], errors='coerce').fillna(0)
        df['vyplatene_bool'] = df['vyplatene'].astype(str).str.upper() == "TRUE"

        # --- ADMIN / SUPERADMIN ZOBRAZENIE ---
        if u['rola'] in ['admin', 'superadmin']:
            st.title("📊 Administrácia")
            
            if not users.empty:
                u_cl = users.rename(columns={'referral_code': 'kod_pouzity', 'pobocka': 'pob_P'})
                df = df.merge(u_cl[['kod_pouzity', 'pob_P']], on='kod_pouzity', how='left')

            active_df = df if u['rola'] == 'superadmin' else df[(df['pobocka_id'] == u['pobocka']) | (df['pob_P'] == u['pobocka'])]

            col_a, col_b = st.columns(2)
            col_a.metric("Obrat pobočky", f"{active_df['suma_zakazky'].sum():.2f} €")
            col_b.metric("Nezaplatené provízie", f"{active_df[~active_df['vyplatene_bool']]['provizia_odporucatel'].sum():.2f} €")

            t_nace, t_vyplat = st.tabs(["📝 Čaká na nacenenie", "💳 Výplaty partnerom"])

            with t_nace:
                nac = active_df[active_df['suma_zakazky'] <= 0]
                if nac.empty: st.success("Všetko nacenené.")
                for i, row in nac.iterrows():
                    with st.expander(f"Zákazka: {row['poznamka']} (Kód: {row['kod_pouzity']})"):
                        ns = st.number_input("Suma zákazky (€)", key=f"inp_{i}", step=5.0)
                        if st.button("Uložiť a vypočítať", key=f"save_{i}"):
                            call_script("updateSuma", {"row_index": row['row_index'], "suma": ns})
                            time.sleep(1.2) # Čas na spracovanie v Sheets
                            st.rerun()

            with t_vyplat:
                vyp = active_df[(active_df['suma_zakazky'] > 0) & (~active_df['vyplatene_bool'])]
                if vyp.empty: st.info("Žiadne provízie k výplate.")
                else:
                    for k in vyp['kod_pouzity'].unique():
                        p_rows = vyp[vyp['kod_pouzity'] == k]
                        with st.expander(f"Partner: {k} | Suma: {p_rows['provizia_odporucatel'].sum():.2f} €"):
                            st.table(p_rows[['poznamka', 'provizia_odporucatel']])
                            if st.button(f"Označiť ako vyplatené ({k})", key=f"pay_{k}"):
                                for idx in p_rows['row_index']:
                                    call_script("markAsPaid", {"row_index": idx})
                                st.rerun()

        # --- PARTNER ZOBRAZENIE ---
        else:
            st.title("💰 Moje provízie")
            my_df = df[df['kod_pouzity'] == u['kod']]
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Počet odporúčaní", len(my_df))
            m2.metric("Zarobené celkovo", f"{my_df['provizia_odporucatel'].sum():.2f} €")
            m3.metric("K výplate", f"{my_df[~my_df['vyplatene_bool']]['provizia_odporucatel'].sum():.2f} €")
            
            st.subheader("História")
            if my_df.empty:
                st.info("Zatiaľ ste neodporučili žiadneho zákazníka.")
            else:
                out_df = my_df[['poznamka', 'suma_zakazky', 'provizia_odporucatel', 'vyplatene']].copy()
                out_df.columns = ['Poznámka', 'Suma (€)', 'Provízia (€)', 'Stav']
                st.dataframe(out_df, use_container_width=True, hide_index=True)
