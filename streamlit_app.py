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
    page_title="TEPUJEM.SK | Enterprise Portál", 
    page_icon="💰", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ZABEZPEČENIE (SECRETS) ---
try:
    SCRIPT_URL = st.secrets["SCRIPT_URL"]
    API_TOKEN = st.secrets["API_TOKEN"]
except Exception:
    st.error("🚨 KRITICKÁ CHYBA: Chýba konfigurácia (Secrets). Skontrolujte SCRIPT_URL a API_TOKEN.")
    st.stop()

# =================================================================
# 2. POMOCNÉ FUNKCIE (DESIGN & LOGIKA)
# =================================================================
def get_base64_of_bin_file(bin_file):
    """Načíta obrázok a vráti ho v base64 pre CSS."""
    try:
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except Exception:
        return None

def validate_mobile(mob):
    """Validácia mobilného čísla 09XXXXXXXX."""
    return re.match(r'^09\d{8}$', str(mob)) is not None

def format_currency(val):
    """Formátovanie čísla na menu Euro."""
    try:
        return f"{float(val):.2f} €"
    except (ValueError, TypeError):
        return "0.00 €"

# =================================================================
# 3. API KOMUNIKÁCIA
# =================================================================
def call_script(action, params=None):
    """Hlavná funkcia pre volanie Google Apps Scriptu."""
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
# 4. DATA ENGINE (FIX PRE KEYERROR A STĹPCE)
# =================================================================
def get_full_data():
    """Načíta transakcie, užívateľov a prepojí ich do jedného DataFrame."""
    try:
        # Načítanie dát z backendu
        z_res = requests.get(f"{SCRIPT_URL}?action=getZakazky&token={API_TOKEN}").json()
        df_z = pd.DataFrame(z_res)
        
        u_res = requests.get(f"{SCRIPT_URL}?action=getUsers&token={API_TOKEN}").json()
        df_u = pd.DataFrame(u_res)
        
        if df_z.empty:
            return pd.DataFrame(), df_u
            
        # OČISTA NÁZVOV STĹPCOV (Prevencia KeyError)
        df_z.columns = [str(c).strip() for c in df_z.columns]

        # Konverzia číselných stĺpcov
        num_cols = ['suma_zakazky', 'provizia_odporucatel']
        for col in num_cols:
            if col in df_z.columns:
                df_z[col] = pd.to_numeric(df_z[col], errors='coerce').fillna(0)
        
        # Logika pre stav 'vyplatene'
        if 'vyplatene' in df_z.columns:
            df_z['vyplatene_bool'] = df_z['vyplatene'].astype(str).str.strip().str.upper() == "TRUE"
        else:
            df_z['vyplatene_bool'] = False
        
        # Indexácia riadkov pre Google Sheets (začína od 2)
        if 'row_index' not in df_z.columns:
            df_z['row_index'] = range(2, len(df_z) + 2)

        # Merge s tabuľkou užívateľov
        if not df_u.empty:
            df_u.columns = [str(c).strip() for c in df_u.columns]
            df_u_lookup = df_u.rename(columns={
                'referral_code': 'kod_pouzity',
                'mobil': 'p_mobil',
                'meno': 'p_meno',
                'priezvisko': 'p_priezvisko',
                'pobocka': 'p_pobocka'
            })
            df_merged = df_z.merge(
                df_u_lookup[['kod_pouzity', 'p_meno', 'p_priezvisko', 'p_mobil', 'p_pobocka']], 
                on='kod_pouzity', 
                how='left'
            )
            return df_merged, df_u
        
        return df_z, df_u
    except Exception as e:
        st.error(f"⚠️ Chyba dát: {str(e)}")
        return pd.DataFrame(), pd.DataFrame()

# =================================================================
# 5. ROZŠÍRENÉ CSS (DESIGN SYSTÉM)
# =================================================================
img_b64 = get_base64_of_bin_file("image5.png")
st.markdown(f"""
<style>
    .stApp {{
        background: linear-gradient(rgba(0,0,0,0.88), rgba(0,0,0,0.88)), 
                    url("data:image/png;base64,{img_b64 if img_b64 else ""}");
        background-size: cover; background-attachment: fixed;
    }}
    [data-testid="stMainBlockContainer"] {{
        background-color: rgba(30, 30, 30, 0.97) !important;
        padding: 50px !important; border-radius: 25px; border: 1px solid #444;
        box-shadow: 0 25px 50px rgba(0,0,0,0.8); max-width: 1100px !important; margin: auto;
    }}
    h1, h2, h3, p, label, span {{ color: white !important; font-family: 'Inter', sans-serif; }}
    
    .stButton > button {{
        width: 100%; border-radius: 12px;
        background: linear-gradient(135deg, #FFD700 0%, #B8860B 100%) !important;
        color: black !important; font-weight: 800 !important; border: none !important;
        padding: 15px; text-transform: uppercase; letter-spacing: 1.2px; transition: 0.3s;
    }}
    .stButton > button:hover {{ transform: scale(1.02); box-shadow: 0 10px 20px rgba(255,215,0,0.3); }}
    
    .stTextInput input, .stSelectbox div {{ background-color: #222 !important; color: white !important; border-radius: 10px !important; }}
    .stDataFrame {{ background-color: #1a1a1a !important; border-radius: 15px; overflow: hidden; border: 1px solid #333; }}
    
    .stTabs [data-baseweb="tab-list"] {{ gap: 10px; }}
    .stTabs [data-baseweb="tab"] {{
        background-color: #222 !important; border-radius: 10px 10px 0 0 !important;
        padding: 10px 20px !important; color: #888 !important;
    }}
    .stTabs [aria-selected="true"] {{ color: #FFD700 !important; border-bottom: 2px solid #FFD700 !important; }}
</style>
""", unsafe_allow_html=True)

# =================================================================
# 6. AUTHENTIKÁCIA
# =================================================================
if 'user' not in st.session_state:
    st.session_state['user'] = None

if st.session_state['user'] is None:
    _, col_login, _ = st.columns([1, 2, 1])
    with col_login:
        st.image("https://tepujem.sk/wp-content/uploads/2022/03/logo-tepujem-white.png", width=300)
        st.title("💰 Partner Portal")
        
        tab_log, tab_reg = st.tabs(["🔐 Prihlásenie", "📝 Registrácia"])
        
        with tab_log:
            with st.form("auth_login"):
                m = st.text_input("Mobil (09XXXXXXXX)")
                h = st.text_input("Heslo", type="password")
                if st.form_submit_button("VSTÚPIŤ"):
                    res = call_script("login", {"mobil": m, "heslo": h})
                    if res.get("status") == "success":
                        st.session_state['user'] = res
                        st.rerun()
                    else: st.error("❌ Nesprávne údaje")

        with tab_reg:
            with st.form("auth_reg"):
                pob = st.selectbox("Pobočka", ["celý Liptov", "Malacky", "Levice", "Bratislava, Trnava, Senec"])
                c1, c2 = st.columns(2)
                men = c1.text_input("Meno")
                pri = c2.text_input("Priezvisko")
                mob = st.text_input("Mobil")
                hes = st.text_input("Heslo", type="password")
                kod = st.text_input("Vlastný referral kód")
                if st.form_submit_button("ZAREGISTROVAŤ SA"):
                    if all([men, pri, mob, hes, kod]):
                        res = call_script("register", {"pobocka": pob, "meno": men, "priezvisko": pri, "mobil": mob, "heslo": hes, "kod": kod})
                        if res.get("status") == "success": st.success("🎉 Úspešne registrovaný!")
                    else: st.warning("⚠️ Vyplňte všetky polia.")

# =================================================================
# 7. DASHBOARD LOGIKA
# =================================================================
else:
    u = st.session_state['user']
    
    with st.sidebar:
        st.markdown(f"### 👤 {u['meno']} {u['priezvisko']}")
        st.info(f"📍 {u['pobocka']}\n\n🔑 Rola: {u['rola'].upper()}")
        st.divider()
        if st.button("🔄 OBNOVIŤ DÁTA"): st.rerun()
        if st.button("🚪 ODHLÁSIŤ SA"):
            st.session_state['user'] = None
            st.rerun()

    df, users_raw = get_full_data()

    if df.empty:
        st.info("ℹ️ Žiadne zákazky na zobrazenie.")
    else:
        # --- ROZHRANIE PRE ADMINOV ---
        if u['rola'] in ['admin', 'superadmin']:
            st.title("📊 Administrácia")
            
            # Filter dát: Superadmin vidí všetko, Admin len svoju pobočku
            if u['rola'] == 'superadmin':
                view_df = df
            else:
                view_df = df[(df['pobocka_id'] == u['pobocka']) | (df['p_pobocka'] == u['pobocka'])]

            # Metriky
            k1, k2, k3 = st.columns(3)
            k1.metric("Celkový obrat", format_currency(view_df['suma_zakazky'].sum()))
            k2.metric("Provízie k úhrade", format_currency(view_df[~view_df['vyplatene_bool']]['provizia_odporucatel'].sum()))
            k3.metric("Počet zákaziek", len(view_df))

            st.divider()
            
            t1, t2, t3 = st.tabs(["🆕 NOVÉ (NACENIŤ)", "💸 VÝPLATY", "📜 HISTÓRIA"])

            with t1:
                to_price = view_df[view_df['suma_zakazky'] <= 0]
                if to_price.empty:
                    st.success("✅ Všetky zákazky sú nacenené.")
                else:
                    for idx, row in to_price.iterrows():
                        with st.container(border=True):
                            col_a, col_b = st.columns([3, 1])
                            col_a.write(f"**📍 Adresa/Poznámka:** {row['poznamka']}")
                            col_a.write(f"**Partner:** {row.get('p_meno', '')} {row.get('p_priezvisko', '')} (`{row['kod_pouzity']}`)")
                            
                            new_suma = col_b.number_input("Suma (€)", key=f"n_{idx}", min_value=0.0, step=5.0)
                            if col_b.button("ULOŽIŤ", key=f"b_{idx}"):
                                # FIX: Superadmin bypass
                                auth_branch = "superadmin" if u['rola'] == 'superadmin' else u['pobocka']
                                res = call_script("updateSuma", {"row_index": row['row_index'], "suma": new_suma, "admin_pobocka": auth_branch})
                                if res.get("status") == "success":
                                    st.success("✅ Zapísané!")
                                    time.sleep(1)
                                    st.rerun()
                                else: st.error(res.get("message"))

            with t2:
                to_pay = view_df[(view_df['suma_zakazky'] > 0) & (~view_df['vyplatene_bool'])]
                if to_pay.empty:
                    st.info("Žiadne otvorené provízie.")
                else:
                    for kod in to_pay['kod_pouzity'].unique():
                        sub = to_pay[to_pay['kod_pouzity'] == kod]
                        p_name = f"{sub['p_meno'].iloc[0]} {sub['p_priezvisko'].iloc[0]}"
                        with st.expander(f"💰 {p_name} ({kod}) - Spolu: {format_currency(sub['provizia_odporucatel'].sum())}"):
                            if st.button(f"Označiť {kod} ako VYPLATENÉ", key=f"pay_{kod}"):
                                auth_branch = "superadmin" if u['rola'] == 'superadmin' else u['pobocka']
                                for _, r in sub.iterrows():
                                    call_script("markAsPaid", {"row_index": r['row_index'], "admin_pobocka": auth_branch})
                                st.rerun()
                            st.dataframe(sub[['datum', 'poznamka', 'suma_zakazky', 'provizia_odporucatel']], use_container_width=True)

            with t3:
                # Dynamická ochrana stĺpcov pre zobrazenie
                cols = ['datum', 'kod_pouzity', 'poznamka', 'suma_zakazky', 'provizia_odporucatel', 'vyplatene']
                existing = [c for c in cols if c in view_df.columns]
                st.dataframe(view_df[existing], use_container_width=True, hide_index=True)

        # --- ROZHRANIE PRE PARTNERA ---
        else:
            st.title("💰 Moje Provízie")
            my_df = df[df['kod_pouzity'] == u['kod']]
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Zarobené spolu", format_currency(my_df['provizia_odporucatel'].sum()))
            c2.metric("K výplate", format_currency(my_df[~my_df['vyplatene_bool']]['provizia_odporucatel'].sum()))
            c3.metric("Počet odporúčaní", len(my_df))
            
            st.divider()
            st.subheader("Prehľad mojich zákaziek")
            st.dataframe(
                my_df[['datum', 'poznamka', 'suma_zakazky', 'provizia_odporucatel', 'vyplatene']],
                use_container_width=True,
                hide_index=True
            )

    st.markdown("---")
    st.caption(f"© {datetime.now().year} TEPUJEM.SK Enterprise System | v5.6.0-PLATINUM")
