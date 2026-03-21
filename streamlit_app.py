import streamlit as st
import pandas as pd
import requests
import base64
import re
import time
from datetime import datetime

# =================================================================
# 1. KONFIGURÁCIA STRÁNKY A PRÍSTUPY
# =================================================================
st.set_page_config(
    page_title="TEPUJEM.SK | Enterprise Provízny Systém", 
    page_icon="💰", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ZABEZPEČENIE (SECRETS) ---
try:
    SCRIPT_URL = st.secrets["SCRIPT_URL"]
    API_TOKEN = st.secrets["API_TOKEN"]
except Exception:
    st.error("🚨 KRITICKÁ CHYBA: Chýba konfigurácia v Streamlit Secrets (SCRIPT_URL alebo API_TOKEN).")
    st.stop()

# =================================================================
# 2. POMOCNÉ FUNKCIE (UI, VALIDÁCIA, FORMÁTOVANIE)
# =================================================================
def get_base64_of_bin_file(bin_file):
    """Konverzia obrázka na pozadie."""
    try:
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except Exception:
        return ""

def validate_mobile(mob):
    """Validácia slovenského čísla 09XXXXXXXX."""
    return re.match(r'^09\d{8}$', str(mob)) is not None

def format_currency(val):
    """Formátovanie na Euro."""
    try:
        return f"{float(val):.2f} €"
    except (ValueError, TypeError):
        return "0.00 €"

# =================================================================
# 3. KOMUNIKÁCIA S API (GOOGLE APPS SCRIPT)
# =================================================================
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

# =================================================================
# 4. DATA ENGINE (FIX PRE ŠTRUKTÚRU TABUĽKY)
# =================================================================
def get_full_data():
    """Načíta dáta a vyčistí názvy stĺpcov podľa tvojej štruktúry."""
    try:
        # 1. Načítanie transakcií
        z_res = requests.get(f"{SCRIPT_URL}?action=getZakazky&token={API_TOKEN}").json()
        df_z = pd.DataFrame(z_res)
        
        # 2. Načítanie partnerov
        u_res = requests.get(f"{SCRIPT_URL}?action=getUsers&token={API_TOKEN}").json()
        df_u = pd.DataFrame(u_res)
        
        if df_z.empty:
            return pd.DataFrame(), df_u
            
        # OČISTA STĹPCOV (Prevencia KeyError)
        df_z.columns = [str(c).strip() for c in df_z.columns]

        # Konverzia čísel
        for col in ['suma_zakazky', 'provizia_odporucatel']:
            if col in df_z.columns:
                df_z[col] = pd.to_numeric(df_z[col], errors='coerce').fillna(0)
        
        # FIX: Logika pre stĺpec 'vyplatene' (Stĺpec G)
        if 'vyplatene' in df_z.columns:
            df_z['vyplatene_bool'] = df_z['vyplatene'].astype(str).str.strip().str.upper() == "TRUE"
        else:
            df_z['vyplatene_bool'] = False
        
        # Generovanie indexu pre Google Sheets (riadok v hárku)
        if 'row_index' not in df_z.columns:
            df_z['row_index'] = range(2, len(df_z) + 2)

        # Merge s užívateľmi pre získanie detailov o partnerovi
        if not df_u.empty:
            df_u.columns = [str(c).strip() for c in df_u.columns]
            df_u_lookup = df_u.rename(columns={
                'referral_code': 'kod_pouzity',
                'pobocka': 'p_pobocka',
                'meno': 'p_meno',
                'priezvisko': 'p_priezvisko'
            })
            df_merged = df_z.merge(
                df_u_lookup[['kod_pouzity', 'p_meno', 'p_priezvisko', 'p_pobocka']], 
                on='kod_pouzity', 
                how='left'
            )
            return df_merged, df_u
        
        return df_z, df_u
    except Exception as e:
        st.error(f"⚠️ Chyba synchronizácie: {str(e)}")
        return pd.DataFrame(), pd.DataFrame()

# =================================================================
# 5. PRÉMIOVÝ VIZUÁL (CSS)
# =================================================================
img_base64 = get_base64_of_bin_file("image5.png")
st.markdown(f"""
<style>
    .stApp {{
        background: linear-gradient(rgba(0,0,0,0.88), rgba(0,0,0,0.88)), 
                    url("data:image/png;base64,{img_base64}");
        background-size: cover; background-attachment: fixed;
    }}
    [data-testid="stMainBlockContainer"] {{
        background-color: rgba(28, 28, 28, 0.98) !important;
        padding: 50px !important; border-radius: 30px; border: 1px solid #444;
        box-shadow: 0 20px 60px rgba(0,0,0,0.9); max-width: 1150px !important; margin: auto;
    }}
    h1, h2, h3, p, label, span, div, .stMetric {{ color: #ffffff !important; font-family: 'Inter', sans-serif; }}
    
    .stButton > button {{
        width: 100%; border-radius: 15px; height: 3.5rem;
        background: linear-gradient(135deg, #FFD700 0%, #B8860B 100%) !important;
        color: #000 !important; font-weight: 900 !important; border: none !important;
        text-transform: uppercase; letter-spacing: 1.8px; transition: 0.3s ease;
    }}
    .stButton > button:hover {{ transform: scale(1.03); box-shadow: 0 10px 25px rgba(255, 215, 0, 0.45); }}
    
    .stTextInput input, .stSelectbox div {{ background-color: #222 !important; color: white !important; border-radius: 12px !important; }}
    .stDataFrame {{ background-color: #1a1a1a !important; border-radius: 15px; border: 1px solid #333; }}
    
    .stTabs [data-baseweb="tab-list"] {{ gap: 10px; }}
    .stTabs [data-baseweb="tab"] {{
        background-color: #262626 !important; border-radius: 10px 10px 0 0 !important;
        padding: 12px 24px !important; color: #999 !important;
    }}
    .stTabs [aria-selected="true"] {{ color: #FFD700 !important; border-bottom: 2px solid #FFD700 !important; }}
</style>
""", unsafe_allow_html=True)

# =================================================================
# 6. AUTH & SESSION
# =================================================================
if 'user' not in st.session_state:
    st.session_state['user'] = None

if st.session_state['user'] is None:
    _, col_login, _ = st.columns([1, 2, 1])
    with col_login:
        st.image("https://tepujem.sk/wp-content/uploads/2022/03/logo-tepujem-white.png", width=320)
        st.title("💰 Partner Portal")
        t1, t2 = st.tabs(["🔐 Vstup", "📝 Registrácia"])
        
        with t1:
            with st.form("login_form"):
                m_log = st.text_input("Mobil (09XXXXXXXX)")
                h_log = st.text_input("Heslo", type="password")
                if st.form_submit_button("PRIHLÁSIŤ SE"):
                    res = call_script("login", {"mobil": m_log, "heslo": h_log})
                    if res.get("status") == "success":
                        st.session_state['user'] = res
                        st.rerun()
                    else: st.error("❌ Prístup zamietnutý. Skontrolujte údaje.")

        with t2:
            with st.form("reg_form"):
                r_pob = st.selectbox("Pobočka", [
                    "celý Liptov", "Malacky", "Levice", "Bratislava, Trnava, Senec",
                    "Banovce, Topoľčany, Trenčín, Prievidza", "Vranov a Košice"
                ])
                rm, rp = st.columns(2)
                r_meno = rm.text_input("Meno")
                r_prie = rp.text_input("Priezvisko")
                r_mob = st.text_input("Mobil")
                r_hes = st.text_input("Heslo", type="password")
                r_kod = st.text_input("Referral kód (napr. ZLAVA10)")
                if st.form_submit_button("DOKONČIŤ REGISTRÁCIU"):
                    if all([r_meno, r_prie, r_mob, r_hes, r_kod]) and validate_mobile(r_mob):
                        res = call_script("register", {
                            "pobocka": r_pob, "meno": r_meno, "priezvisko": r_prie, 
                            "mobil": r_mob, "heslo": r_hes, "kod": r_kod
                        })
                        if res.get("status") == "success": st.success("🎉 Registrácia úspešná!")
                    else: st.error("⚠️ Vyplňte polia správne (mobil v tvare 09XXXXXXXX).")

# =================================================================
# 7. HLAVNÝ SYSTÉM (ADMIN / PARTNER)
# =================================================================
else:
    u = st.session_state['user']
    with st.sidebar:
        st.markdown(f"### 👤 {u['meno']} {u['priezvisko']}")
        st.info(f"📍 {u['pobocka']}\n🔑 {u['rola'].upper()}")
        st.divider()
        if st.button("🔄 OBNOVIŤ DÁTA"): st.rerun()
        if st.button("🚪 ODHLÁSIŤ SA"):
            st.session_state['user'] = None
            st.rerun()

    df, _ = get_full_data()

    if df.empty:
        st.info("ℹ️ Žiadne zákazky v systéme.")
    else:
        # --- LOGIKA PRE ADMINOV ---
        if u['rola'] in ['admin', 'superadmin']:
            st.title("📊 Administrácia systému")
            
            # Filtrovanie: Superadmin vidí všetko, Admin svoju pobočku
            view_df = df if u['rola'] == 'superadmin' else df[df['p_pobocka'] == u['pobocka']]

            k1, k2, k3 = st.columns(3)
            k1.metric("Obrat", format_currency(view_df['suma_zakazky'].sum()))
            k2.metric("K výplate", format_currency(view_df[~view_df['vyplatene_bool']]['provizia_odporucatel'].sum()))
            k3.metric("Zákazky", len(view_df))

            st.divider()
            t_nac, t_vyp, t_arc = st.tabs(["🆕 NACENIŤ", "💰 VÝPLATY", "📜 ARCHÍV"])

            # 1. TAB: NACENENIE
            with t_nac:
                to_price = view_df[view_df['suma_zakazky'] <= 0]
                if to_price.empty: st.success("✅ Všetky zákazky sú nacenené.")
                else:
                    for i, r in to_price.iterrows():
                        with st.container(border=True):
                            c_left, c_right = st.columns([3, 1])
                            c_left.write(f"**📍 {r.get('mesto', 'Neznáme')}** | {r.get('poznamka', '')}")
                            c_left.write(f"Partner: {r.get('p_meno', '---')} (`{r['kod_pouzity']}`)")
                            
                            n_sum = c_right.number_input("Suma (€)", key=f"s_{i}", min_value=0.0)
                            if c_right.button("ULOŽIŤ", key=f"b_{i}"):
                                # VÝPOČET PROVÍZIE 5%
                                p_calc = n_sum * 0.05
                                auth_tag = "superadmin" if u['rola'] == 'superadmin' else u['pobocka']
                                res = call_script("updateSuma", {
                                    "row_index": r['row_index'], 
                                    "suma": n_sum, 
                                    "provizia": p_calc,
                                    "admin_pobocka": auth_tag
                                })
                                if res.get("status") == "success": 
                                    st.success("Zapísané!"); time.sleep(0.5); st.rerun()

            # 2. TAB: VÝPLATY
            with t_vyp:
                to_pay = view_df[(view_df['suma_zakazky'] > 0) & (~view_df['vyplatene_bool'])]
                if to_pay.empty: st.info("Žiadne otvorené provízie.")
                else:
                    for kod in to_pay['kod_pouzity'].unique():
                        sub = to_pay[to_pay['kod_pouzity'] == kod]
                        with st.expander(f"💰 {kod} | Spolu: {format_currency(sub['provizia_odporucatel'].sum())}"):
                            if st.button(f"Vyplatiť {kod}", key=f"pay_{kod}"):
                                for _, prow in sub.iterrows():
                                    call_script("markAsPaid", {"row_index": prow['row_index']})
                                st.rerun()
                            st.dataframe(sub[['mesto', 'poznamka', 'suma_zakazky', 'provizia_odporucatel']], use_container_width=True)

            # 3. TAB: ARCHÍV
            with t_arc:
                cols = [c for c in ['mesto', 'kod_pouzity', 'poznamka', 'suma_zakazky', 'provizia_odporucatel', 'vyplatene'] if c in view_df.columns]
                st.dataframe(view_df[cols], use_container_width=True, hide_index=True)

        # --- LOGIKA PRE PARTNERA ---
        else:
            st.title("💰 Moje Provízie")
            my_df = df[df['kod_pouzity'] == u['referral_code']]
            c1, c2, c3 = st.columns(3)
            c1.metric("Zarobené", format_currency(my_df['provizia_odporucatel'].sum()))
            c2.metric("K výplate", format_currency(my_df[~my_df['vyplatene_bool']]['provizia_odporucatel'].sum()))
            c3.metric("Zákazky", len(my_df))
            st.divider()
            p_cols = [c for c in ['mesto', 'poznamka', 'suma_zakazky', 'provizia_odporucatel', 'vyplatene'] if c in my_df.columns]
            st.dataframe(my_df[p_cols], use_container_width=True, hide_index=True)

    st.markdown("---")
    st.caption(f"© {datetime.now().year} TEPUJEM.SK Enterprise | v6.0.0-ULTIMATE")
