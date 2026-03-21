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

# --- 2. BEZPEČNOSŤ A KONFIGURÁCIA ---
try:
    SCRIPT_URL = st.secrets["SCRIPT_URL"]
    API_TOKEN = st.secrets["API_TOKEN"]
except Exception:
    st.error("🚨 KRITICKÁ CHYBA: Chýba konfigurácia (Secrets).")
    st.stop()

# --- 3. POMOCNÉ FUNKCIE ---
def get_base64_of_bin_file(bin_file):
    try:
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except FileNotFoundError:
        return None

def validate_mobile(mob):
    return re.match(r'^09\d{8}$', str(mob)) is not None

def format_currency(val):
    try:
        return f"{float(val):.2f} €"
    except (ValueError, TypeError):
        return "0.00 €"

# --- 4. KOMUNIKÁCIA S BACKENDOM (API) ---
def call_script(action, params=None):
    if params is None:
        params = {}
    params['action'] = action
    params['token'] = API_TOKEN
    try:
        response = requests.get(SCRIPT_URL, params=params, timeout=45)
        if response.status_code == 200:
            return response.json()
        return {"status": "error", "message": f"Server Error {response.status_code}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- 5. DATA ENGINE (ZÍSKAVANIE A SYNCHRONIZÁCIA) ---
def get_full_data():
    """Načíta transakcie a užívateľov a vykoná bezpečný merge."""
    try:
        # 1. Načítanie transakcií
        z_res = requests.get(f"{SCRIPT_URL}?action=getZakazky&token={API_TOKEN}").json()
        df_z = pd.DataFrame(z_res)
        
        # 2. Načítanie užívateľov
        u_res = requests.get(f"{SCRIPT_URL}?action=getUsers&token={API_TOKEN}").json()
        df_u = pd.DataFrame(u_res)
        
        if df_z.empty:
            return pd.DataFrame(), df_u
            
        # Ošetrenie typov dát pre výpočty
        df_z['suma_zakazky'] = pd.to_numeric(df_z['suma_zakazky'], errors='coerce').fillna(0)
        df_z['provizia_odporucatel'] = pd.to_numeric(df_z['provizia_odporucatel'], errors='coerce').fillna(0)
        
        # FIX: 'Series' object has no attribute 'upper'
        df_z['vyplatene_bool'] = df_z['vyplatene'].astype(str).str.strip().str.upper() == "TRUE"
        
        # Zabezpečenie row_index (musíme ho mať pre zápis!)
        if 'row_index' not in df_z.columns:
            df_z['row_index'] = df_z.index + 2 # Google Sheets indexovanie

        # Bezpečné prepojenie cez referral_code (stĺpec G v Sheets)
        if not df_u.empty:
            df_u_lookup = df_u.rename(columns={
                'referral_code': 'kod_pouzity',
                'mobil': 'p_mobil',
                'meno': 'p_meno',
                'priezvisko': 'p_priezvisko',
                'pobocka': 'p_pobocka'
            })
            # Merge zachováva row_index transakcie
            df_merged = df_z.merge(df_u_lookup[['kod_pouzity', 'p_meno', 'p_priezvisko', 'p_mobil', 'p_pobocka']], 
                                   on='kod_pouzity', how='left')
            return df_merged, df_u
        
        return df_z, df_u
    except Exception as e:
        st.error(f"⚠️ Chyba synchronizácie: {str(e)}")
        return pd.DataFrame(), pd.DataFrame()

# --- 6. PRÉMIOVÝ VIZUÁL (CSS) ---
img_base64 = get_base64_of_bin_file("image5.png")
background_css = f"""
<style>
    .stApp {{
        background: linear-gradient(rgba(0,0,0,0.85), rgba(0,0,0,0.85)), 
                    url("data:image/png;base64,{img_base64 if img_base64 else ""}");
        background-size: cover;
        background-attachment: fixed;
    }}
    [data-testid="stMainBlockContainer"] {{
        background-color: rgba(25, 25, 25, 0.95) !important;
        padding: 50px !important;
        border-radius: 25px;
        border: 1px solid #444;
        box-shadow: 0 15px 45px rgba(0,0,0,0.7);
    }}
    h1, h2, h3, p, label, span {{ color: #ffffff !important; font-family: 'Inter', sans-serif; }}
    
    .stButton > button {{
        width: 100%;
        border-radius: 12px;
        background: linear-gradient(135deg, #FFD700 0%, #B8860B 100%) !important;
        color: black !important;
        font-weight: 800 !important;
        border: none !important;
        padding: 12px;
        transition: 0.3s;
    }}
    .stButton > button:hover {{ transform: translateY(-2px); box-shadow: 0 5px 15px rgba(255,215,0,0.3); }}
    .stDataFrame {{ background-color: #1a1a1a !important; border-radius: 10px; }}
</style>
"""
st.markdown(background_css, unsafe_allow_html=True)

# --- 7. SESSION MANAGEMENT ---
if 'user' not in st.session_state:
    st.session_state['user'] = None

# --- 8. AUTH GATE ---
if st.session_state['user'] is None:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.image("https://tepujem.sk/wp-content/uploads/2022/03/logo-tepujem-white.png", width=280)
        st.title("💰 Partner Portál")
        
        t1, t2 = st.tabs(["🔐 Prihlásenie", "📝 Registrácia"])
        
        with t1:
            with st.form("login_form"):
                m = st.text_input("Mobil (09XXXXXXXX)")
                h = st.text_input("Heslo", type="password")
                if st.form_submit_button("VSTÚPIŤ"):
                    if validate_mobile(m):
                        res = call_script("login", {"mobil": m, "heslo": h})
                        if res.get("status") == "success":
                            st.session_state['user'] = res
                            st.rerun()
                        else: st.error("❌ Nesprávne prihlasovacie údaje.")
                    else: st.warning("⚠️ Formát mobilu musí byť 09XXXXXXXX.")

        with t2:
            with st.form("reg_form"):
                r_pob = st.selectbox("Pobočka", ["celý Liptov", "Malacky", "Levice", "Bratislava, Trnava, Senec"])
                rm, rp = st.columns(2)
                r_meno = rm.text_input("Meno")
                r_priez = rp.text_input("Priezvisko")
                r_mob = st.text_input("Mobil (09XXXXXXXX)")
                r_hes = st.text_input("Heslo", type="password")
                r_kod = st.text_input("Referral kód")
                
                if st.form_submit_button("REGISTROVAŤ SA"):
                    if all([r_meno, r_priez, r_mob, r_hes, r_kod]):
                        res = call_script("register", {
                            "pobocka": r_pob, "meno": r_meno, "priezvisko": r_priez,
                            "mobil": r_mob, "heslo": r_hes, "kod": r_kod
                        })
                        if res.get("status") == "success": st.success("🎉 Registrácia úspešná!")
                        else: st.error(f"❌ Chyba: {res.get('message')}")
                    else: st.error("❗ Vyplňte všetky polia.")

# --- 9. DASHBOARD ---
else:
    u = st.session_state['user']
    
    with st.sidebar:
        st.markdown(f"### 👤 {u['meno']} {u['priezvisko']}")
        st.info(f"📍 {u['pobocka']}\n\n🔑 Rola: {u['rola']}")
        st.divider()
        if st.button("🔄 OBNOVIŤ DÁTA"): st.rerun()
        if st.button("🚪 ODHLÁSIŤ SA"):
            st.session_state['user'] = None
            st.rerun()

    df, users_raw = get_full_data()

    if df.empty:
        st.info("ℹ️ Žiadne záznamy v systéme.")
    else:
        # --- ROZHRANIE ADMIN / SUPERADMIN ---
        if u['rola'] in ['admin', 'superadmin']:
            st.title(f"📊 Správa - {u['pobocka']}")
            
            view_df = df if u['rola'] == 'superadmin' else df[(df['pobocka_id'] == u['pobocka']) | (df['p_pobocka'] == u['pobocka'])]

            # Metriky (Streamlit Native)
            k1, k2, k3 = st.columns(3)
            k1.metric("Obrat celkom", format_currency(view_df['suma_zakazky'].sum()))
            k2.metric("K výplate", format_currency(view_df[~view_df['vyplatene_bool']]['provizia_odporucatel'].sum()))
            k3.metric("Zákazky", len(view_df))

            tab_n, tab_v, tab_h = st.tabs(["🆕 Na nacenenie", "💰 Na vyplatenie", "📑 História"])

            with tab_n:
                st.subheader("Nové požiadavky")
                to_price = view_df[view_df['suma_zakazky'] <= 0]
                if to_price.empty:
                    st.success("✅ Všetko nacenené.")
                else:
                    for i, r in to_price.iterrows():
                        p_full = f"{r.get('p_meno', 'Neznámy')} {r.get('p_priezvisko', '')}"
                        with st.expander(f"📍 {r['poznamka']} | Partner: {p_full}"):
                            st.write(f"**Kontakt partnera:** {r.get('p_mobil', '---')}")
                            # FIX: Uložiť sumu vyžaduje row_index
                            n_val = st.number_input("Suma zákazky (€)", key=f"s_{i}", min_value=0.0, step=5.0)
                            if st.button("ULOŽIŤ", key=f"btn_save_{i}"):
                                # DÔLEŽITÉ: Posielame row_index z transakčnej tabuľky
                                res = call_script("updateSuma", {
                                    "row_index": r['row_index'], 
                                    "suma": n_val, 
                                    "admin_pobocka": u['pobocka']
                                })
                                if res.get("status") == "success":
                                    st.success("Zápis úspešný!")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error(f"Chyba zápisu: {res.get('message')}")

            with tab_v:
                st.subheader("Provízie partnerov")
                to_pay = view_df[(view_df['suma_zakazky'] > 0) & (~view_df['vyplatene_bool'])]
                if to_pay.empty:
                    st.info("Žiadne čakajúce platby.")
                else:
                    for kod in to_pay['kod_pouzity'].unique():
                        sub = to_pay[to_pay['kod_pouzity'] == kod]
                        name = f"{sub['p_meno'].iloc[0]} {sub['p_priezvisko'].iloc[0]}"
                        with st.container(border=True):
                            ca, cb = st.columns([3, 1])
                            ca.write(f"**{name}** (`{kod}`) | Spolu: **{format_currency(sub['provizia_odporucatel'].sum())}**")
                            if cb.button(f"VYPLATIŤ {kod}", key=f"pay_{kod}"):
                                for _, row in sub.iterrows():
                                    call_script("markAsPaid", {"row_index": row['row_index'], "admin_pobocka": u['pobocka']})
                                st.rerun()
                            st.dataframe(sub[['datum', 'poznamka', 'suma_zakazky', 'provizia_odporucatel']], use_container_width=True)

            with tab_h:
                st.subheader("Archív záznamov")
                hist_cols = ['datum', 'kod_pouzity', 'poznamka', 'suma_zakazky', 'provizia_odporucatel', 'vyplatene']
                st.dataframe(view_df[[c for c in hist_cols if c in view_df.columns]], use_container_width=True)

        # --- ROZHRANIE PARTNER ---
        else:
            st.title("💰 Môj Provízny Prehľad")
            my_df = df[df['kod_pouzity'] == u['kod']]
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Zarobené celkovo", format_currency(my_df['provizia_odporucatel'].sum()))
            c2.metric("Čaká na výplatu", format_currency(my_df[~my_df['vyplatene_bool']]['provizia_odporucatel'].sum()))
            c3.metric("Počet odporúčaní", len(my_df))

            st.divider()
            st.subheader("História mojich zákaziek")
            if my_df.empty:
                st.info("Zatiaľ ste nepriviedli žiadneho zákazníka.")
            else:
                st.dataframe(
                    my_df[['datum', 'poznamka', 'suma_zakazky', 'provizia_odporucatel', 'vyplatene']],
                    column_config={
                        "suma_zakazky": st.column_config.NumberColumn("Cena tepovania", format="%.2f €"),
                        "provizia_odporucatel": st.column_config.NumberColumn("Moja provízia", format="%.2f €"),
                        "vyplatene": "Stav úhrady"
                    },
                    use_container_width=True,
                    hide_index=True
                )

    # --- 10. FOOTER ---
    st.markdown("---")
    st.caption(f"© {datetime.now().year} TEPUJEM.SK Enterprise System | v5.2.0-STABLE")
