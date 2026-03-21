import streamlit as st
import pandas as pd
import requests
import base64
import re
import time
from datetime import datetime

# --- 1. KONFIGURÁCIA STRÁNKY ---
st.set_page_config(
    page_title="TEPUJEM.SK | Enterprise Provízny Portál", 
    page_icon="💰", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. BEZPEČNOSŤ A SECRETS ---
try:
    SCRIPT_URL = st.secrets["SCRIPT_URL"]
    API_TOKEN = st.secrets["API_TOKEN"]
except Exception:
    st.error("🚨 KRITICKÁ CHYBA: Chýba konfigurácia (Secrets). Skontrolujte SCRIPT_URL a API_TOKEN.")
    st.stop()

# --- 3. POMOCNÉ FUNKCIE PRE VIZUÁL A VALIDÁCIU ---
def get_base64_of_bin_file(bin_file):
    """Načíta obrázok a skonvertuje ho do base64 pre CSS pozadie."""
    try:
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except FileNotFoundError:
        return None

def validate_mobile(mob):
    """Validuje slovenský formát mobilu 09XXXXXXXX."""
    return re.match(r'^09\d{8}$', str(mob)) is not None

def format_currency(val):
    """Formátuje číslo na menu Euro."""
    try:
        return f"{float(val):.2f} €"
    except (ValueError, TypeError):
        return "0.00 €"

# --- 4. KOMUNIKÁCIA S BACKENDOM (API) ---
def call_script(action, params=None):
    """Univerzálna funkcia na volanie Google Apps Scriptu."""
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
    """Načíta transakcie a užívateľov a vykoná precízny merge."""
    try:
        # 1. Načítanie transakcií (Sheet: transakcie)
        z_res = requests.get(f"{SCRIPT_URL}?action=getZakazky&token={API_TOKEN}").json()
        df_z = pd.DataFrame(z_res)
        
        # 2. Načítanie užívateľov (Sheet: users_data)
        u_res = requests.get(f"{SCRIPT_URL}?action=getUsers&token={API_TOKEN}").json()
        df_u = pd.DataFrame(u_res)
        
        if df_z.empty:
            return pd.DataFrame(), df_u
            
        # Ošetrenie číselných formátov
        df_z['suma_zakazky'] = pd.to_numeric(df_z['suma_zakazky'], errors='coerce').fillna(0)
        df_z['provizia_odporucatel'] = pd.to_numeric(df_z['provizia_odporucatel'], errors='coerce').fillna(0)
        
        # --- FIX: Series .str accessor pre 'upper' ---
        # Toto rieši chybu, ktorú si poslal na screenshote
        df_z['vyplatene_bool'] = df_z['vyplatene'].astype(str).str.strip().str.upper() == "TRUE"
        
        # Zabezpečenie row_index pre neskoršie aktualizácie
        if 'row_index' not in df_z.columns:
            df_z['row_index'] = range(2, len(df_z) + 2)

        # Merge cez referral_code (V tvojom Exceli stĺpec G)
        if not df_u.empty:
            df_u_lookup = df_u.rename(columns={
                'referral_code': 'kod_pouzity',
                'mobil': 'p_mobil',
                'meno': 'p_meno',
                'priezvisko': 'p_priezvisko',
                'pobocka': 'p_pobocka'
            })
            # Prepojíme dáta tak, aby sme mali info o partnerovi pri každej zákazke
            df_merged = df_z.merge(df_u_lookup[['kod_pouzity', 'p_meno', 'p_priezvisko', 'p_mobil', 'p_pobocka']], 
                                   on='kod_pouzity', how='left')
            return df_merged, df_u
        
        return df_z, df_u
    except Exception as e:
        st.error(f"⚠️ Chyba synchronizácie dát: {str(e)}")
        return pd.DataFrame(), pd.DataFrame()

# --- 6. PRÉMIOVÝ VIZUÁLNY SYSTÉM (CSS) ---
img_base64 = get_base64_of_bin_file("image5.png")
background_css = f"""
<style>
    /* Hlavné pozadie aplikácie */
    .stApp {{
        background: linear-gradient(rgba(0,0,0,0.86), rgba(0,0,0,0.86)), 
                    url("data:image/png;base64,{img_base64 if img_base64 else ""}");
        background-size: cover;
        background-attachment: fixed;
    }}
    /* Kontajner s obsahom */
    [data-testid="stMainBlockContainer"] {{
        background-color: rgba(30, 30, 30, 0.96) !important;
        padding: 60px !important;
        border-radius: 30px;
        border: 1px solid #444;
        box-shadow: 0 20px 50px rgba(0,0,0,0.8);
        max-width: 1000px !important;
        margin: auto;
    }}
    /* Texty a nadpisy */
    h1, h2, h3, p, label, span, div {{ color: #ffffff !important; font-family: 'Inter', sans-serif; }}
    
    /* Zlaté tlačidlá v štýle Tepujem.sk */
    .stButton > button {{
        width: 100%;
        border-radius: 15px;
        background: linear-gradient(135deg, #FFD700 0%, #B8860B 100%) !important;
        color: #000000 !important;
        font-weight: 900 !important;
        border: none !important;
        padding: 15px;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        transition: all 0.3s ease;
    }}
    .stButton > button:hover {{ transform: scale(1.02); box-shadow: 0 8px 20px rgba(255,215,0,0.4); }}
    
    /* Vstupné polia a tabuľky */
    .stTextInput input, .stSelectbox div {{ background-color: #222 !important; color: white !important; border-radius: 10px !important; }}
    .stDataFrame {{ background-color: #1a1a1a !important; border-radius: 15px; overflow: hidden; }}
</style>
"""
st.markdown(background_css, unsafe_allow_html=True)

# --- 7. SESSION MANAGEMENT ---
if 'user' not in st.session_state:
    st.session_state['user'] = None

# --- 8. AUTENTIFIKÁCIA (LOGIN & REGISTRÁCIA) ---
if st.session_state['user'] is None:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.image("https://tepujem.sk/wp-content/uploads/2022/03/logo-tepujem-white.png", width=300)
        st.title("💰 Provízny Portál")
        
        t1, t2 = st.tabs(["🔐 Prihlásenie", "📝 Registrácia partnera"])
        
        with t1:
            with st.form("login_form"):
                m_log = st.text_input("Mobil (09XXXXXXXX)")
                h_log = st.text_input("Heslo", type="password")
                if st.form_submit_button("PRIHLÁSIŤ SA"):
                    if validate_mobile(m_log):
                        res = call_script("login", {"mobil": m_log, "heslo": h_log})
                        if res.get("status") == "success":
                            st.session_state['user'] = res
                            st.rerun()
                        else: st.error("❌ Nesprávne prihlasovacie údaje.")
                    else: st.warning("⚠️ Zadajte správny formát mobilu.")

        with t2:
            with st.form("reg_form"):
                r_pob = st.selectbox("Priradiť k pobočke", ["celý Liptov", "Malacky", "Levice", "Bratislava, Trnava, Senec"])
                col_m, col_p = st.columns(2)
                r_meno = col_m.text_input("Meno")
                r_priez = col_p.text_input("Priezvisko")
                r_mob = st.text_input("Mobil (09XXXXXXXX)")
                r_hes = st.text_input("Heslo", type="password")
                r_kod = st.text_input("Váš unikátny referral kód")
                
                if st.form_submit_button("DOKONČIŤ REGISTRÁCIU"):
                    if all([r_meno, r_priez, r_mob, r_hes, r_kod]) and validate_mobile(r_mob):
                        res = call_script("register", {
                            "pobocka": r_pob, "meno": r_meno, "priezvisko": r_priez,
                            "mobil": r_mob, "heslo": r_hes, "kod": r_kod
                        })
                        if res.get("status") == "success": st.success("🎉 Registrácia úspešná! Môžete sa prihlásiť.")
                        else: st.error(f"❌ Chyba: {res.get('message')}")
                    else: st.error("❗ Skontrolujte, či sú všetky polia správne vyplnené.")

# --- 9. HLAVNÝ DASHBOARD SYSTÉMU ---
else:
    u = st.session_state['user']
    
    with st.sidebar:
        st.markdown(f"### 👤 {u['meno']} {u['priezvisko']}")
        st.info(f"📍 {u['pobocka']}\n\n🔑 Rola: {u['rola'].upper()}")
        st.divider()
        if st.button("🔄 AKTUALIZOVAŤ DÁTA"): st.rerun()
        if st.button("🚪 ODHLÁSIŤ SA"):
            st.session_state['user'] = None
            st.rerun()

    # Načítanie aktuálnych dát
    df, users_raw = get_full_data()

    if df.empty:
        st.info("ℹ️ V systéme momentálne nie sú žiadne zákazky.")
    else:
        # --- ROZHRANIE PRE ADMINA / SUPERADMINA ---
        if u['rola'] in ['admin', 'superadmin']:
            st.title(f"📊 Manažérsky Prehľad")
            
            # Filtrovanie prístupu k pobočkám
            if u['rola'] == 'superadmin':
                view_df = df
            else:
                view_df = df[(df['pobocka_id'] == u['pobocka']) | (df['p_pobocka'] == u['pobocka'])]

            # KPI Panely
            k1, k2, k3 = st.columns(3)
            k1.metric("Celkový obrat", format_currency(view_df['suma_zakazky'].sum()))
            k2.metric("Provízie k výplate", format_currency(view_df[~view_df['vyplatene_bool']]['provizia_odporucatel'].sum()))
            k3.metric("Počet zákaziek", len(view_df))

            st.divider()
            
            t_price, t_pay, t_hist = st.tabs(["🆕 NACENENIE", "💰 VÝPLATY", "📑 ARCHÍV"])

            with t_price:
                st.subheader("Nové zákazky bez sumy")
                to_price = view_df[view_df['suma_zakazky'] <= 0]
                if to_price.empty:
                    st.success("✅ Všetky zákazky sú nacenené.")
                else:
                    for i, r in to_price.iterrows():
                        p_full = f"{r.get('p_meno', '---')} {r.get('p_priezvisko', '')}"
                        with st.expander(f"📍 {r['poznamka']} | Partner: {p_full}"):
                            st.write(f"**Kontakt partnera:** {r.get('p_mobil', '---')}")
                            n_suma = st.number_input(f"Suma zákazky (€)", key=f"s_{i}", min_value=0.0, step=5.0)
                            if st.button("ULOŽIŤ SUMU", key=f"btn_s_{i}"):
                                # FIX: Superadmin posiela ID pobočky priamo zo zákazky, aby skript nehlásil "Unauthorized"
                                branch_fix = r['pobocka_id'] if u['rola'] == 'superadmin' else u['pobocka']
                                res = call_script("updateSuma", {
                                    "row_index": r['row_index'], 
                                    "suma": n_suma, 
                                    "admin_pobocka": branch_fix
                                })
                                if res.get("status") == "success":
                                    st.success("Zápis bol úspešný!")
                                    time.sleep(1)
                                    st.rerun()
                                else: st.error(f"❌ Chyba zápisu: {res.get('message')}")

            with t_pay:
                st.subheader("Provízie pripravené na úhradu")
                to_pay = view_df[(view_df['suma_zakazky'] > 0) & (~view_df['vyplatene_bool'])]
                if to_pay.empty:
                    st.info("Žiadne nevyplatené provízie.")
                else:
                    for kod in to_pay['kod_pouzity'].unique():
                        sub = to_pay[to_pay['kod_pouzity'] == kod]
                        p_name = f"{sub['p_meno'].iloc[0]} {sub['p_priezvisko'].iloc[0]}"
                        with st.container(border=True):
                            ca, cb = st.columns([3, 1])
                            ca.write(f"**Partner:** {p_name} (`{kod}`) | Spolu k výplate: **{format_currency(sub['provizia_odporucatel'].sum())}**")
                            if cb.button(f"VYPLATIŤ {kod}", key=f"pay_{kod}"):
                                for _, row in sub.iterrows():
                                    call_script("markAsPaid", {"row_index": row['row_index'], "admin_pobocka": u['pobocka']})
                                st.success(f"Provízia pre {kod} bola označená ako vyplatená.")
                                time.sleep(1)
                                st.rerun()
                            st.dataframe(sub[['datum', 'poznamka', 'suma_zakazky', 'provizia_odporucatel']], use_container_width=True)

            with t_hist:
                st.subheader("Kompletná história transakcií")
                h_cols = ['datum', 'kod_pouzity', 'poznamka', 'suma_zakazky', 'provizia_odporucatel', 'vyplatene']
                st.dataframe(view_df[[c for c in h_cols if c in view_df.columns]], use_container_width=True, hide_index=True)

        # --- ROZHRANIE PRE PARTNERA ---
        else:
            st.title("💰 Môj Provízny Portál")
            my_df = df[df['kod_pouzity'] == u['kod']]
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Zarobené celkovo", format_currency(my_df['provizia_odporucatel'].sum()))
            c2.metric("Nezaplatené provízie", format_currency(my_df[~my_df['vyplatene_bool']]['provizia_odporucatel'].sum()))
            c3.metric("Počet odporúčaní", len(my_df))

            st.divider()
            st.subheader("Zoznam mojich odporúčaní")
            if my_df.empty:
                st.info("Zatiaľ nemáte žiadne evidované zákazky.")
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
    st.caption(f"© {datetime.now().year} TEPUJEM.SK Enterprise System | Verzia 5.3.1-PLATINUM")
