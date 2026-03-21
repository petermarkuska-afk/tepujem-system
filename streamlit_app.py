import streamlit as st
import pandas as pd
import requests
import base64
import re
import time
from datetime import datetime

# =================================================================
# 1. KONFIGURÁCIA STRÁNKY
# =================================================================
st.set_page_config(
    page_title="TEPUJEM.SK | Enterprise Portál", 
    page_icon="💰", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ZABEZPEČENIE ---
try:
    SCRIPT_URL = st.secrets["SCRIPT_URL"]
    API_TOKEN = st.secrets["API_TOKEN"]
except Exception:
    st.error("🚨 KRITICKÁ CHYBA: Chýba SCRIPT_URL alebo API_TOKEN v Streamlit Secrets.")
    st.stop()

# =================================================================
# 2. POMOCNÉ FUNKCIE
# =================================================================
def get_base64_of_bin_file(bin_file):
    try:
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except Exception:
        return ""

def format_currency(val):
    try:
        return f"{float(val):.2f} €"
    except (ValueError, TypeError):
        return "0.00 €"

def call_script(action, params=None):
    if params is None: params = {}
    params['action'] = action
    params['token'] = API_TOKEN
    try:
        response = requests.get(SCRIPT_URL, params=params, timeout=45)
        return response.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

# =================================================================
# 3. DATA ENGINE (FIX PODĽA TVOJEJ ŠTRUKTÚRY)
# =================================================================
def get_full_data():
    try:
        # Načítanie dát z Apps Scriptu
        z_res = requests.get(f"{SCRIPT_URL}?action=getZakazky&token={API_TOKEN}").json()
        df_z = pd.DataFrame(z_res)
        
        u_res = requests.get(f"{SCRIPT_URL}?action=getUsers&token={API_TOKEN}").json()
        df_u = pd.DataFrame(u_res)
        
        if df_z.empty:
            return pd.DataFrame(), df_u
            
        # --- OČISTA A MAPOVANIE PODĽA TVOJHO SCREENSHOTU ---
        df_z.columns = [str(c).strip() for c in df_z.columns]

        # Pretypovanie čísel (suma_zakazky, provizia_odporucatel)
        for col in ['suma_zakazky', 'provizia_odporucatel']:
            if col in df_z.columns:
                df_z[col] = pd.to_numeric(df_z[col], errors='coerce').fillna(0)
        
        # Logika pre stav vyplatené (Stĺpec G v Google Sheets)
        if 'vyplatene' in df_z.columns:
            df_z['vyplatene_bool'] = df_z['vyplatene'].astype(str).str.strip().str.upper() == "TRUE"
        else:
            df_z['vyplatene_bool'] = False
        
        # Pridanie row_index ak chýba
        if 'row_index' not in df_z.columns:
            df_z['row_index'] = range(2, len(df_z) + 2)

        # --- MERGE S POUŽÍVATEĽMI (Prepojenie cez kod_pouzity vs referral_code) ---
        if not df_u.empty:
            df_u.columns = [str(c).strip() for c in df_u.columns]
            # Premenujeme stĺpce užívateľov pre prehľadnosť v merge
            df_u_lookup = df_u.rename(columns={
                'referral_code': 'kod_pouzity',
                'mobil': 'p_mobil',
                'meno': 'p_meno',
                'priezvisko': 'p_priezvisko',
                'pobocka': 'p_pobocka'
            })
            
            # Merge podľa kódu
            df_merged = df_z.merge(
                df_u_lookup[['kod_pouzity', 'p_meno', 'p_priezvisko', 'p_mobil', 'p_pobocka']], 
                on='kod_pouzity', 
                how='left'
            )
            return df_merged, df_u
        
        return df_z, df_u
    except Exception as e:
        st.error(f"⚠️ Synchronizácia zlyhala: {str(e)}")
        return pd.DataFrame(), pd.DataFrame()

# =================================================================
# 4. PRÉMIOVÝ VIZUÁL (CSS)
# =================================================================
img_b64 = get_base64_of_bin_file("image5.png")
st.markdown(f"""
<style>
    .stApp {{
        background: linear-gradient(rgba(0,0,0,0.88), rgba(0,0,0,0.88)), 
                    url("data:image/png;base64,{img_b64}");
        background-size: cover; background-attachment: fixed;
    }}
    [data-testid="stMainBlockContainer"] {{
        background-color: rgba(28, 28, 28, 0.98) !important;
        padding: 45px !important; border-radius: 25px; border: 1px solid #444;
        box-shadow: 0 20px 60px rgba(0,0,0,0.9); max-width: 1150px !important; margin: auto;
    }}
    h1, h2, h3, p, label, span, .stMetric {{ color: #ffffff !important; font-family: 'Inter', sans-serif; }}
    
    .stButton > button {{
        width: 100%; border-radius: 12px; height: 3.5rem;
        background: linear-gradient(135deg, #FFD700 0%, #B8860B 100%) !important;
        color: #000 !important; font-weight: 800 !important; border: none !important;
        text-transform: uppercase; letter-spacing: 1.5px; transition: 0.3s ease;
    }}
    .stButton > button:hover {{ transform: scale(1.02); box-shadow: 0 10px 25px rgba(255, 215, 0, 0.4); }}
    
    .stTextInput input, .stSelectbox div {{ background-color: #222 !important; color: white !important; border-radius: 10px !important; }}
    .stDataFrame {{ background-color: #1a1a1a !important; border-radius: 15px; border: 1px solid #333; }}
    
    /* Úprava tabov */
    .stTabs [data-baseweb="tab-list"] {{ gap: 8px; }}
    .stTabs [data-baseweb="tab"] {{
        background-color: #262626 !important; border-radius: 10px 10px 0 0 !important;
        padding: 12px 24px !important; color: #999 !important;
    }}
    .stTabs [aria-selected="true"] {{ color: #FFD700 !important; border-bottom: 2px solid #FFD700 !important; }}
</style>
""", unsafe_allow_html=True)

# =================================================================
# 5. SYSTÉM PRIHLASOVANIA
# =================================================================
if 'user' not in st.session_state:
    st.session_state['user'] = None

if st.session_state['user'] is None:
    c1, col_login, c3 = st.columns([1, 2, 1])
    with col_login:
        st.image("https://tepujem.sk/wp-content/uploads/2022/03/logo-tepujem-white.png", width=320)
        st.title("💰 Partner Portal")
        
        t_login, t_reg = st.tabs(["🔐 Prihlásenie", "📝 Registrácia"])
        
        with t_login:
            with st.form("login_form"):
                m_log = st.text_input("Mobil (napr. 0901234567)")
                h_log = st.text_input("Heslo", type="password")
                if st.form_submit_button("VSTÚPIŤ DO SYSTÉMU"):
                    res = call_script("login", {"mobil": m_log, "heslo": h_log})
                    if res.get("status") == "success":
                        st.session_state['user'] = res
                        st.rerun()
                    else: st.error("❌ Neplatné prihlasovacie údaje.")

        with t_reg:
            with st.form("register_form"):
                r_pob = st.selectbox("Pobočka", [
                    "celý Liptov", "Malacky", "Levice", 
                    "Bratislava, Trnava, Senec", "Banovce, Topoľčany, Trenčín, Prievidza",
                    "Žilina, Martin, Púchov, PB, KNM, Bytča, Čadca", "Dolný Kubín a Orava", "Vranov a Košice"
                ])
                rm, rp = st.columns(2)
                r_meno = rm.text_input("Meno")
                r_priez = rp.text_input("Priezvisko")
                r_mob = st.text_input("Mobil")
                r_heslo = st.text_input("Heslo (min. 6 znakov)", type="password")
                r_kod = st.text_input("Váš Referral Kód (napr. Zlava10)")
                
                if st.form_submit_button("VYTVORIŤ ÚČET"):
                    if all([r_meno, r_priez, r_mob, r_heslo, r_kod]):
                        res = call_script("register", {
                            "pobocka": r_pob, "meno": r_meno, "priezvisko": r_priez, 
                            "mobil": r_mob, "heslo": r_heslo, "kod": r_kod
                        })
                        if res.get("status") == "success":
                            st.success("🎉 Registrácia bola úspešná! Teraz sa môžete prihlásiť.")
                        else: st.error(f"Chyba: {res.get('message')}")
                    else: st.warning("⚠️ Prosím, vyplňte všetky polia.")

# =================================================================
# 6. HLAVNÝ DASHBOARD (PO PRIHLÁSENÍ)
# =================================================================
else:
    u = st.session_state['user']
    
    # Bočný panel
    with st.sidebar:
        st.markdown(f"### 👤 {u['meno']} {u['priezvisko']}")
        st.info(f"📍 {u['pobocka']}\n\n🔑 Rola: {u['rola'].upper()}")
        st.divider()
        if st.button("🔄 AKTUALIZOVAŤ DÁTA"): st.rerun()
        if st.button("🚪 ODHLÁSIŤ SA"):
            st.session_state['user'] = None
            st.rerun()

    # Načítanie dát
    df, users_all = get_full_data()

    if df.empty:
        st.info("ℹ️ V systéme zatiaľ nie sú žiadne zákazky.")
    else:
        # --- ROZHRANIE PRE ADMIN / SUPERADMIN ---
        if u['rola'] in ['admin', 'superadmin']:
            st.title("🛡️ Administrácia")
            
            # Filtrovanie dát podľa pobočky (Superadmin vidí všetko)
            if u['rola'] == 'superadmin':
                view_df = df
            else:
                view_df = df[(df['pobocka_id'] == u['pobocka']) | (df['p_pobocka'] == u['pobocka'])]

            # Metriky na vrchu
            m1, m2, m3 = st.columns(3)
            m1.metric("Obrat Celkom", format_currency(view_df['suma_zakazky'].sum()))
            m2.metric("Provízie k výplate", format_currency(view_df[~view_df['vyplatene_bool']]['provizia_odporucatel'].sum()))
            m3.metric("Počet Transakcií", len(view_df))

            st.divider()
            
            # Taby pre správu
            tab_price, tab_pay, tab_arch = st.tabs(["🆕 NACENENIE", "💰 VÝPLATY", "📜 ARCHÍV"])

            # 1. TAB: NACENENIE (Zákazky kde suma_zakazky == 0)
            with tab_price:
                to_price = view_df[view_df['suma_zakazky'] <= 0]
                if to_price.empty:
                    st.success("✅ Všetky zákazky sú aktuálne nacenené.")
                else:
                    for i, row in to_price.iterrows():
                        with st.container(border=True):
                            c_info, c_action = st.columns([3, 1])
                            # Podľa tvojho hárka: 'mesto' a 'poznamka'
                            loc = row.get('mesto', 'Neznáme')
                            note = row.get('poznamka', 'Bez poznámky')
                            partner = f"{row.get('p_meno', '---')} {row.get('p_priezvisko', '')}"
                            
                            c_info.write(f"**📍 {loc}** | {note}")
                            c_info.write(f"Partner: {partner} (`{row['kod_pouzity']}`)")
                            
                            val = c_action.number_input("Suma (€)", key=f"v_{i}", min_value=0.0, step=10.0)
                            if c_action.button("ULOŽIŤ SUMU", key=f"b_{i}"):
                                # Superadmin bypass pre ukladanie
                                a_branch = "superadmin" if u['rola'] == 'superadmin' else u['pobocka']
                                res = call_script("updateSuma", {
                                    "row_index": row['row_index'], 
                                    "suma": val, 
                                    "admin_pobocka": a_branch
                                })
                                if res.get("status") == "success":
                                    st.success("Zapísané!"); time.sleep(0.5); st.rerun()
                                else: st.error(res.get("message"))

            # 2. TAB: VÝPLATY (Zákazky nacenené ale nevyplatené)
            with tab_pay:
                to_pay = view_df[(view_df['suma_zakazky'] > 0) & (~view_df['vyplatene_bool'])]
                if to_pay.empty:
                    st.info("Žiadne provízie nečakajú na vyplatenie.")
                else:
                    for kod in to_pay['kod_pouzity'].unique():
                        sub = to_pay[to_pay['kod_pouzity'] == kod]
                        total_p = sub['provizia_odporucatel'].sum()
                        with st.expander(f"💰 {kod} | Spolu: {format_currency(total_p)}"):
                            if st.button(f"Označiť {kod} ako VYPLATENÉ", key=f"pay_{kod}"):
                                for _, r_pay in sub.iterrows():
                                    call_script("markAsPaid", {"row_index": r_pay['row_index']})
                                st.success("Hotovo!"); time.sleep(0.5); st.rerun()
                            # Zobrazenie stĺpcov ktoré máš: mesto, poznamka, suma_zakazky
                            st.dataframe(sub[['mesto', 'poznamka', 'suma_zakazky', 'provizia_odporucatel']], use_container_width=True)

            # 3. TAB: ARCHÍV (Kompletná história)
            with tab_arch:
                # OCHRANA PROTI KEYERROR: Dynamický výber stĺpcov podľa toho čo v tabuľke skutočne je
                cols_to_show = ['mesto', 'kod_pouzity', 'poznamka', 'suma_zakazky', 'provizia_odporucatel', 'vyplatene']
                final_cols = [c for c in cols_to_show if c in view_df.columns]
                st.dataframe(view_df[final_cols], use_container_width=True, hide_index=True)

        # --- ROZHRANIE PRE PARTNERA ---
        else:
            st.title("💰 Môj Provízny Prehľad")
            my_df = df[df['kod_pouzity'] == u['kod']]
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Zarobené celkovo", format_currency(my_df['provizia_odporucatel'].sum()))
            c2.metric("Nezaplatené", format_currency(my_df[~my_df['vyplatene_bool']]['provizia_odporucatel'].sum()))
            c3.metric("Počet odporúčaní", len(my_df))
            
            st.divider()
            st.subheader("Moje zákazky")
            # Podľa tvojich stĺpcov
            p_cols = ['mesto', 'poznamka', 'suma_zakazky', 'provizia_odporucatel', 'vyplatene']
            p_final = [c for c in p_cols if c in my_df.columns]
            st.dataframe(my_df[p_final], use_container_width=True, hide_index=True)

    st.markdown("---")
    st.caption(f"© {datetime.now().year} TEPUJEM.SK Enterprise System | v5.8.0-PLATINUM")
