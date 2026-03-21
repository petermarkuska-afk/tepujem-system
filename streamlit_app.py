import streamlit as st
import pandas as pd
import requests
import base64
import re
import time
from datetime import datetime
import io

# --- 1. KONFIGURÁCIA STRÁNKY ---
st.set_page_config(
    page_title="TEPUJEM.SK | Partner & Admin Portál", 
    page_icon="💰", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. BEZPEČNOSŤ A SECRETS ---
try:
    SCRIPT_URL = st.secrets["SCRIPT_URL"]
    API_TOKEN = st.secrets["API_TOKEN"]
except Exception:
    st.error("🚨 KRITICKÁ CHYBA: Chýba konfigurácia (Secrets). Aplikácia nemôže komunikovať s databázou.")
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
        /* Hlavné pozadie s blend módom */
        .stApp {{
            background: linear-gradient(rgba(0,0,0,0.85), rgba(0,0,0,0.85)), 
                        url("data:image/png;base64,{img_b64}");
            background-size: cover;
            background-attachment: fixed;
        }}
        
        /* Kontajner hlavného obsahu */
        [data-testid="stMainBlockContainer"] {{
            background-color: rgba(25, 25, 25, 0.9) !important;
            border-radius: 25px;
            padding: 50px !important;
            border: 1px solid #3d3d3d;
            box-shadow: 0 15px 35px rgba(0,0,0,0.6);
            margin-top: 30px;
        }}

        /* Nadpisy a texty */
        h1, h2, h3, label, p, span {{
            color: #ffffff !important;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }}

        /* Tlačidlá - Tepujem Gold Design */
        .stButton>button {{
            background: linear-gradient(135deg, #FFD700 0%, #B8860B 100%) !important;
            color: #000000 !important;
            font-weight: 800 !important;
            border: none !important;
            border-radius: 12px !important;
            padding: 12px 24px !important;
            transition: all 0.3s ease;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .stButton>button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(255, 215, 0, 0.4);
        }}

        /* Inputy a Selectboxy */
        .stTextInput>div>div>input, .stSelectbox>div>div {{
            background-color: #333333 !important;
            color: white !important;
            border: 1px solid #555 !important;
            border-radius: 10px !important;
        }}

        /* Tabuľky a DataFrame */
        [data-testid="stDataFrame"] {{
            background-color: #1a1a1a !important;
            border-radius: 15px;
            border: 1px solid #333;
        }}
        
        /* Sidebar */
        [data-testid="stSidebar"] {{
            background-color: #0f0f0f !important;
            border-right: 1px solid #333;
        }}
    </style>
    """
    st.markdown(style, unsafe_allow_html=True)

load_design()

# --- 4. FUNKCIE PRE KOMUNIKÁCIU ---
def call_api(action, params=None):
    """Robustné volanie Google Apps Script API."""
    if params is None: params = {}
    params['action'] = action
    params['token'] = API_TOKEN
    
    try:
        resp = requests.get(SCRIPT_URL, params=params, timeout=40)
        if resp.status_code == 200:
            return resp.json()
        return {"status": "error", "message": f"Server Error {resp.status_code}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def validate_mobile(mob):
    """Overenie slovenského formátu mobilu."""
    return bool(re.match(r'^09\d{8}$', str(mob)))

# --- 5. DÁTOVÝ ENGINE (MERGE & SYNC) ---
def get_master_data():
    """Získa transakcie a užívateľov a vykoná komplexné prepojenie."""
    try:
        # 1. Načítanie transakcií zo stĺpca 'referral_code' (G)
        z_raw = requests.get(f"{SCRIPT_URL}?action=getZakazky&token={API_TOKEN}").json()
        df_z = pd.DataFrame(z_raw)
        
        # 2. Načítanie databázy užívateľov
        u_raw = requests.get(f"{SCRIPT_URL}?action=getUsers&token={API_TOKEN}").json()
        df_u = pd.DataFrame(u_raw)
        
        if df_z.empty:
            return pd.DataFrame(), df_u

        # Čistenie a typovanie (dôležité pre výpočty)
        df_z['suma_zakazky'] = pd.to_numeric(df_z['suma_zakazky'], errors='coerce').fillna(0)
        df_z['provizia_odporucatel'] = pd.to_numeric(df_z['provizia_odporucatel'], errors='coerce').fillna(0)
        df_z['vyplatene_bool'] = df_z['vyplatene'].astype(str).str.strip().upper() == "TRUE"

        # Merge - Prepojenie transakcie s konkrétnym partnerom
        if not df_u.empty:
            # Pripravíme lookup tabuľku partnerov (stĺpec G v tabuľke = referral_code)
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
    # --- LOGIN / REGISTRATION SCREEN ---
    c_logo, c_main, c_spacer = st.columns([1, 2, 1])
    with c_main:
        st.title("💰 Provízny Portál TEPUJEM.SK")
        tab_log, tab_reg = st.tabs(["🔐 Prihlásenie", "📝 Registrácia partnera"])
        
        with tab_log:
            with st.form("login_form"):
                l_mob = st.text_input("Mobil (09XXXXXXXX)")
                l_hes = st.text_input("Heslo", type="password")
                if st.form_submit_button("Vstúpiť do portálu"):
                    if not validate_mobile(l_mob):
                        st.warning("Zadajte mobil v správnom tvare.")
                    else:
                        with st.spinner("Overujem..."):
                            res = call_api("login", {"mobil": l_mob, "heslo": l_hes})
                            if res.get("status") == "success":
                                st.session_state['user'] = res
                                st.rerun()
                            else: st.error("Nesprávne údaje.")

        with tab_reg:
            with st.form("reg_form"):
                st.subheader("Nový partner")
                r_pob = st.selectbox("Priradiť k pobočke", ["celý Liptov", "Malacky", "Levice", "Bratislava, Trnava, Senec"])
                c_r1, c_r2 = st.columns(2)
                r_meno = c_r1.text_input("Meno")
                r_priez = c_r2.text_input("Priezvisko")
                r_mob = st.text_input("Mobil (09XXXXXXXX)")
                r_hes = st.text_input("Heslo", type="password")
                r_kod = st.text_input("Váš unikátny Kód (Referral)")
                
                if st.form_submit_button("Odoslať registráciu"):
                    if not all([r_meno, r_priez, r_mob, r_hes, r_kod]):
                        st.warning("Všetky polia sú povinné!")
                    else:
                        res = call_api("register", {
                            "pobocka": r_pob, "meno": r_meno, "priezvisko": r_priez,
                            "mobil": r_mob, "heslo": r_hes, "kod": r_kod
                        })
                        st.success("Registrácia úspešná!") if res.get("status") == "success" else st.error("Chyba.")

# --- 7. DASHBOARD (LOGGED IN) ---
else:
    u = st.session_state['user']
    
    # Sidebar Navigation & User Info
    with st.sidebar:
        st.image("https://tepujem.sk/wp-content/uploads/2022/03/logo-tepujem-white.png", width=180)
        st.markdown(f"### 👤 {u['meno']} {u['priezvisko']}")
        st.info(f"📍 {u['pobocka']}\n\n🔑 Rola: {u['rola']}")
        st.divider()
        if st.button("🔄 Aktualizovať dáta"): st.rerun()
        if st.button("🚪 Odhlásiť sa"):
            st.session_state['user'] = None
            st.rerun()
        st.divider()
        st.caption(f"Posledná synchr.: {datetime.now().strftime('%H:%M:%S')}")

    # Load All Data
    df, users_all = get_master_data()

    if df.empty:
        st.info("Zatiaľ žiadne záznamy v databáze.")
    else:
        # --- ROZHRANIE PRE ADMINOV ---
        if u['rola'] in ['admin', 'superadmin']:
            st.title(f"📊 Administrácia - {u['pobocka']}")
            
            # Filter dát podľa právomoci
            if u['rola'] == 'superadmin':
                view_df = df
            else:
                # Admin vidí svoju pobočku + zákazky partnerov, ktorí patria pod jeho pobočku
                view_df = df[(df['pobocka_id'] == u['pobocka']) | (df['p_pobocka'] == u['pobocka'])]

            # KPI Metriky (Top panely)
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Celkový Obrat", f"{view_df['suma_zakazky'].sum():.2f} €")
            k2.metric("Provízie k výplate", f"{view_df[~view_df['vyplatene_bool']]['provizia_odporucatel'].sum():.2f} €")
            k3.metric("Nové zákazky", len(view_df[view_df['suma_zakazky'] <= 0]))
            k4.metric("Počet partnerov", view_df['kod_pouzity'].nunique())

            # Taby pre Admina
            t_price, t_pay, t_all, t_users = st.tabs(["🆕 Nacenenie", "💰 Výplaty", "📑 Všetky záznamy", "👥 Správa Partnerov"])

            with t_price:
                st.subheader("Zákazky čakajúce na sumu")
                to_price = view_df[view_df['suma_zakazky'] <= 0]
                if to_price.empty:
                    st.success("Všetko je nacenené.")
                else:
                    for i, r in to_price.iterrows():
                        with st.expander(f"Zákazník: {r['poznamka']} | Partner: {r['p_meno']} ({r['kod_pouzity']})"):
                            col_i, col_b = st.columns([3, 1])
                            val = col_i.number_input("Suma zákazky (€)", key=f"inp_{i}", min_value=0.0, step=5.0)
                            if col_b.button("Uložiť", key=f"btn_{i}"):
                                res = call_api("updateSuma", {"row_index": r['row_index'], "suma": val, "admin_pobocka": u['pobocka']})
                                if res.get("status") == "success":
                                    st.success("Suma uložená!")
                                    time.sleep(0.5)
                                    st.rerun()

            with t_pay:
                st.subheader("Nevyplatené provízie partnerom")
                to_pay = view_df[(view_df['suma_zakazky'] > 0) & (~view_df['vyplatene_bool'])]
                if to_pay.empty:
                    st.info("Žiadne provízie na vyplatenie.")
                else:
                    # Zoskupenie podľa partnerov pre lepšiu prehľadnosť
                    for partner in to_pay['kod_pouzity'].unique():
                        p_data = to_pay[to_pay['kod_pouzity'] == partner]
                        total = p_data['provizia_odporucatel'].sum()
                        with st.container(border=True):
                            c_p1, c_p2 = st.columns([3, 1])
                            c_p1.write(f"**Partner:** {partner} | **Spolu k výplate:** {total:.2f} €")
                            if c_p2.button(f"Označiť ako vyplatené", key=f"pay_{partner}"):
                                for _, row_p in p_data.iterrows():
                                    call_api("markAsPaid", {"row_index": row_p['row_index'], "admin_pobocka": u['pobocka']})
                                st.rerun()
                            st.dataframe(p_data[['datum', 'poznamka', 'suma_zakazky', 'provizia_odporucatel']], use_container_width=True)

            with t_all:
                st.subheader("Kompletná história transakcií")
                st.dataframe(view_df, use_container_width=True)

            with t_users:
                st.subheader("Registrovaní partneri")
                st.dataframe(users_all[['meno', 'priezvisko', 'mobil', 'referral_code', 'pobocka', 'rola']], use_container_width=True)

        # --- ROZHRANIE PRE PARTNEROV ---
        else:
            st.title(f"💰 Môj Provízny Prehľad")
            my_df = df[df['kod_pouzity'] == u['kod']]
            
            # Karty pre partnera
            c1, c2, c3 = st.columns(3)
            c1.metric("Zarobené celkovo", f"{my_df['provizia_odporucatel'].sum():.2f} €")
            c2.metric("Čaká na výplatu", f"{my_df[~my_df['vyplatene_bool']]['provizia_odporucatel'].sum():.2f} €")
            c3.metric("Počet odporúčaní", len(my_df))

            st.divider()
            st.subheader("História mojich odporúčaní")
            if my_df.empty:
                st.info("Zatiaľ žiadne záznamy.")
            else:
                st.dataframe(
                    my_df[['datum', 'poznamka', 'suma_zakazky', 'provizia_odporucatel', 'vyplatene', 'pobocka_id']],
                    column_config={
                        "datum": "Dátum",
                        "poznamka": "Popis zákazky",
                        "suma_zakazky": st.column_config.NumberColumn("Cena tepovania", format="%.2f €"),
                        "provizia_odporucatel": st.column_config.NumberColumn("Moja provízia", format="%.2f €"),
                        "vyplatene": "Stav výplaty",
                        "pobocka_id": "Mesto"
                    },
                    use_container_width=True,
                    hide_index=True
                )

    # --- 8. FOOTER ---
    st.markdown("---")
    st.caption(f"© 2026 TEPUJEM.SK Enterprise System | Verzia 4.0.0-GOLD")
