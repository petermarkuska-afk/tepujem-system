import streamlit as st
import pandas as pd
import requests
import base64
import re
import time
from datetime import datetime

# --- 1. KONFIGURÁCIA STRÁNKY ---
st.set_page_config(
    page_title="TEPUJEM.SK | Enterprise Portál", 
    page_icon="💰", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. BEZPEČNOSŤ A SECRETS ---
try:
    SCRIPT_URL = st.secrets["SCRIPT_URL"]
    API_TOKEN = st.secrets["API_TOKEN"]
except Exception:
    st.error("🚨 KRITICKÁ CHYBA: Chýba konfigurácia (Secrets).")
    st.stop()

# --- 3. PRÉMIOVÝ VIZUÁLNY SYSTÉM (CSS) ---
def load_design():
    """Načíta kompletný vizuálny štýl portálu."""
    img_path = "image5.png"
    img_b64 = ""
    try:
        with open(img_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()
    except:
        pass

    style = f"""
    <style>
        .stApp {{
            background: linear-gradient(rgba(0,0,0,0.85), rgba(0,0,0,0.85)), 
                        url("data:image/png;base64,{img_b64}");
            background-size: cover;
            background-attachment: fixed;
        }}
        [data-testid="stMainBlockContainer"] {{
            background-color: rgba(25, 25, 25, 0.9) !important;
            border-radius: 25px;
            padding: 50px !important;
            border: 1px solid #3d3d3d;
            box-shadow: 0 15px 35px rgba(0,0,0,0.6);
        }}
        h1, h2, h3, label, p, span {{ color: #ffffff !important; }}
        .stButton>button {{
            background: linear-gradient(135deg, #FFD700 0%, #B8860B 100%) !important;
            color: #000000 !important;
            font-weight: 800 !important;
            border-radius: 12px !important;
            width: 100%;
        }}
        [data-testid="stDataFrame"] {{ background-color: #1a1a1a !important; }}
    </style>
    """
    st.markdown(style, unsafe_allow_html=True)

load_design()

# --- 4. FUNKCIE PRE KOMUNIKÁCIU ---
def call_api(action, params=None):
    if params is None: params = {}
    params['action'] = action
    params['token'] = API_TOKEN
    try:
        resp = requests.get(SCRIPT_URL, params=params, timeout=40)
        return resp.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

def validate_mobile(mob):
    return bool(re.match(r'^09\d{8}$', str(mob)))

# --- 5. DÁTOVÝ ENGINE (FIXED MERGE & SYNC) ---
def get_master_data():
    """Získa transakcie a užívateľov s opravou chyby .upper()."""
    try:
        # 1. Načítanie transakcií
        z_raw = requests.get(f"{SCRIPT_URL}?action=getZakazky&token={API_TOKEN}").json()
        df_z = pd.DataFrame(z_raw)
        
        # 2. Načítanie užívateľov
        u_raw = requests.get(f"{SCRIPT_URL}?action=getUsers&token={API_TOKEN}").json()
        df_u = pd.DataFrame(u_raw)
        
        if df_z.empty:
            return pd.DataFrame(), df_u

        # --- OPRAVA CHYBY 'Series' has no attribute 'upper' ---
        # Musíme použiť .str.upper() namiesto .upper()
        df_z['suma_zakazky'] = pd.to_numeric(df_z['suma_zakazky'], errors='coerce').fillna(0)
        df_z['provizia_odporucatel'] = pd.to_numeric(df_z['provizia_odporucatel'], errors='coerce').fillna(0)
        df_z['vyplatene_bool'] = df_z['vyplatene'].astype(str).str.strip().str.upper() == "TRUE"

        # Merge prepojenie
        if not df_u.empty:
            u_map = df_u.rename(columns={
                'referral_code': 'kod_pouzity',
                'meno': 'p_meno', 'priezvisko': 'p_priez',
                'mobil': 'p_mobil', 'pobocka': 'p_pobocka'
            })
            df_final = df_z.merge(u_map[['kod_pouzity', 'p_meno', 'p_priez', 'p_mobil', 'p_pobocka']], 
                                 on='kod_pouzity', how='left')
            return df_final, df_u
            
        return df_z, df_u
    except Exception as e:
        st.error(f"Chyba synchronizácie: {e}")
        return pd.DataFrame(), pd.DataFrame()

# --- 6. AUTENTIFIKÁCIA ---
if 'user' not in st.session_state:
    st.session_state['user'] = None

if st.session_state['user'] is None:
    c_logo, c_main, c_spacer = st.columns([1, 2, 1])
    with c_main:
        st.title("💰 Provízny Portál TEPUJEM.SK")
        tab_log, tab_reg = st.tabs(["🔐 Prihlásenie", "📝 Registrácia"])
        
        with tab_log:
            with st.form("login_form"):
                l_mob = st.text_input("Mobil (09XXXXXXXX)")
                l_hes = st.text_input("Heslo", type="password")
                if st.form_submit_button("Vstúpiť"):
                    res = call_api("login", {"mobil": l_mob, "heslo": l_hes})
                    if res.get("status") == "success":
                        st.session_state['user'] = res
                        st.rerun()
                    else: st.error("Nesprávne údaje.")

        with tab_reg:
            with st.form("reg_form"):
                r_pob = st.selectbox("Pobočka", ["celý Liptov", "Malacky", "Levice", "Bratislava, Trnava, Senec"])
                r_meno = st.text_input("Meno")
                r_priez = st.text_input("Priezvisko")
                r_mob = st.text_input("Mobil (09XXXXXXXX)")
                r_hes = st.text_input("Heslo", type="password")
                r_kod = st.text_input("Vlastný Kód")
                if st.form_submit_button("Registrovať"):
                    res = call_api("register", {"pobocka": r_pob, "meno": r_meno, "priezvisko": r_priez, "mobil": r_mob, "heslo": r_hes, "kod": r_kod})
                    st.success("Hotovo!") if res.get("status") == "success" else st.error("Chyba.")

# --- 7. DASHBOARD ---
else:
    u = st.session_state['user']
    
    with st.sidebar:
        st.markdown(f"### 👤 {u['meno']} {u['priezvisko']}")
        st.info(f"📍 {u['pobocka']}\n\n🔑 Rola: {u['rola']}")
        if st.button("🔄 Aktualizovať"): st.rerun()
        if st.button("🚪 Odhlásiť"):
            st.session_state['user'] = None
            st.rerun()

    df, users_all = get_master_data()

    if df.empty:
        st.info("Žiadne záznamy.")
    else:
        # --- ADMIN / SUPERADMIN SEKICA ---
        if u['rola'] in ['admin', 'superadmin']:
            st.title(f"📊 Administrácia")
            
            # Filtrovanie pre admina
            if u['rola'] == 'superadmin':
                view_df = df
            else:
                view_df = df[(df['pobocka_id'] == u['pobocka']) | (df['p_pobocka'] == u['pobocka'])]

            m1, m2, m3 = st.columns(3)
            m1.metric("Obrat", f"{view_df['suma_zakazky'].sum():.2f} €")
            m2.metric("K výplate", f"{view_df[~view_df['vyplatene_bool']]['provizia_odporucatel'].sum():.2f} €")
            m3.metric("Počet", len(view_df))

            t1, t2, t3 = st.tabs(["🆕 Nacenenie", "💰 Výplaty", "👥 Partneri"])

            with t1:
                to_price = view_df[view_df['suma_zakazky'] <= 0]
                if to_price.empty: st.success("Všetko nacenené.")
                else:
                    for i, r in to_price.iterrows():
                        with st.expander(f"Zákazník: {r['poznamka']} | Partner: {r.get('p_meno', '---')}"):
                            val = st.number_input("Suma (€)", key=f"n_{i}", min_value=0.0)
                            if st.button("Uložiť", key=f"b_{i}"):
                                call_api("updateSuma", {"row_index": r['row_index'], "suma": val, "admin_pobocka": u['pobocka']})
                                st.rerun()

            with t2:
                to_pay = view_df[(view_df['suma_zakazky'] > 0) & (~view_df['vyplatene_bool'])]
                for partner in to_pay['kod_pouzity'].unique():
                    p_data = to_pay[to_pay['kod_pouzity'] == partner]
                    with st.container(border=True):
                        st.write(f"**Partner:** {partner} | **K výplate:** {p_data['provizia_odporucatel'].sum():.2f} €")
                        if st.button(f"Vyplatiť {partner}", key=f"p_{partner}"):
                            for _, rp in p_data.iterrows():
                                call_api("markAsPaid", {"row_index": rp['row_index'], "admin_pobocka": u['pobocka']})
                            st.rerun()
                        st.dataframe(p_data[['datum', 'poznamka', 'provizia_odporucatel']], use_container_width=True)

            with t3:
                st.dataframe(users_all[['meno', 'priezvisko', 'referral_code', 'pobocka']], use_container_width=True)

        # --- PARTNER SEKICA ---
        else:
            st.title("💰 Môj Prehľad")
            my_df = df[df['kod_pouzity'] == u['kod']]
            c1, c2 = st.columns(2)
            c1.metric("Zarobené celkovo", f"{my_df['provizia_odporucatel'].sum():.2f} €")
            c2.metric("Čaká na výplatu", f"{my_df[~my_df['vyplatene_bool']]['provizia_odporucatel'].sum():.2f} €")
            
            st.dataframe(
                my_df[['datum', 'poznamka', 'suma_zakazky', 'provizia_odporucatel', 'vyplatene']],
                column_config={"suma_zakazky": "Cena (€)", "provizia_odporucatel": "Moja provízia (€)"},
                use_container_width=True
            )

    st.markdown("---")
    st.caption("© 2026 TEPUJEM.SK Enterprise | v4.1.0")
