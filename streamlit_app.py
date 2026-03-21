import streamlit as st
import pandas as pd
import requests
import base64
import re
import time
from datetime import datetime

# --- 1. GLOBÁLNA KONFIGURÁCIA ---
st.set_page_config(
    page_title="TEPUJEM.SK | Partner Portal", 
    page_icon="💰", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. BEZPEČNOSŤ (SECRETS) ---
try:
    SCRIPT_URL = st.secrets["SCRIPT_URL"]
    API_TOKEN = st.secrets["API_TOKEN"]
except Exception:
    st.error("🚨 CHYBA KONFIGURÁCIE: V Streamlit Cloud chýbajú 'Secrets' (SCRIPT_URL alebo API_TOKEN).")
    st.stop()

# --- 3. POMOCNÉ FUNKCIE (UI & LOGIKA) ---
def get_base64_of_bin_file(bin_file):
    """Konverzia obrázka na pozadie."""
    try:
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except Exception:
        return None

def validate_mobile(mob):
    """Validácia slovenského čísla."""
    return re.match(r'^09\d{8}$', str(mob)) is not None

def format_currency(val):
    """Formátovanie na Euro."""
    try:
        return f"{float(val):.2f} €"
    except (ValueError, TypeError):
        return "0.00 €"

# --- 4. KOMUNIKÁCIA S GOOGLE SCRIPT API ---
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

# --- 5. DATA ENGINE (MERGE & FIXY) ---
def get_full_data():
    """Získanie dát z Google Sheets a ich prepojenie."""
    try:
        # Načítanie transakcií
        z_res = requests.get(f"{SCRIPT_URL}?action=getZakazky&token={API_TOKEN}").json()
        df_z = pd.DataFrame(z_res)
        
        # Načítanie partnerov (Užívateľov)
        u_res = requests.get(f"{SCRIPT_URL}?action=getUsers&token={API_TOKEN}").json()
        df_u = pd.DataFrame(u_res)
        
        if df_z.empty:
            return pd.DataFrame(), df_u
            
        # Ošetrenie čísel a textov
        df_z['suma_zakazky'] = pd.to_numeric(df_z['suma_zakazky'], errors='coerce').fillna(0)
        df_z['provizia_odporucatel'] = pd.to_numeric(df_z['provizia_odporucatel'], errors='coerce').fillna(0)
        
        # FIX: 'Series' object has no attribute 'upper' (opravené cez .str)
        df_z['vyplatene_bool'] = df_z['vyplatene'].astype(str).str.strip().str.upper() == "TRUE"
        
        # Generovanie indexu pre Google Sheets (riadok 2 je začiatok dát)
        if 'row_index' not in df_z.columns:
            df_z['row_index'] = range(2, len(df_z) + 2)

        # Merge dát - párovanie transakcie na partnera cez kód (stĺpec G v Sheets)
        if not df_u.empty:
            df_u_lookup = df_u.rename(columns={
                'referral_code': 'kod_pouzity',
                'mobil': 'p_mobil',
                'meno': 'p_meno',
                'priezvisko': 'p_priezvisko',
                'pobocka': 'p_pobocka'
            })
            df_merged = df_z.merge(df_u_lookup[['kod_pouzity', 'p_meno', 'p_priezvisko', 'p_mobil', 'p_pobocka']], 
                                   on='kod_pouzity', how='left')
            return df_merged, df_u
        
        return df_z, df_u
    except Exception as e:
        st.error(f"⚠️ Chyba dát: {str(e)}")
        return pd.DataFrame(), pd.DataFrame()

# --- 6. DESIGN (CSS ŠTÝLY) ---
img_b64 = get_base64_of_bin_file("image5.png")
st.markdown(f"""
<style>
    .stApp {{
        background: linear-gradient(rgba(0,0,0,0.85), rgba(0,0,0,0.85)), 
                    url("data:image/png;base64,{img_b64 if img_b64 else ""}");
        background-size: cover; background-attachment: fixed;
    }}
    [data-testid="stMainBlockContainer"] {{
        background-color: rgba(26, 26, 26, 0.97) !important;
        padding: 50px !important; border-radius: 25px; border: 1px solid #333;
        box-shadow: 0 15px 40px rgba(0,0,0,0.7); margin-top: 20px;
    }}
    h1, h2, h3, span, label {{ color: white !important; font-family: 'Inter', sans-serif; }}
    
    .stButton > button {{
        width: 100%; border-radius: 12px;
        background: linear-gradient(135deg, #FFD700 0%, #B8860B 100%) !important;
        color: black !important; font-weight: 800 !important;
        border: none !important; padding: 12px; transition: 0.3s ease;
    }}
    .stButton > button:hover {{ transform: scale(1.02); box-shadow: 0 5px 15px rgba(218,165,32,0.4); }}
    .stDataFrame {{ background-color: #111 !important; border-radius: 10px; }}
</style>
""", unsafe_allow_html=True)

# --- 7. SESSION STATE ---
if 'user' not in st.session_state:
    st.session_state['user'] = None

# --- 8. VSTUPNÁ BRÁNA ---
if st.session_state['user'] is None:
    _, col_login, _ = st.columns([1, 2, 1])
    with col_login:
        st.image("https://tepujem.sk/wp-content/uploads/2022/03/logo-tepujem-white.png", width=280)
        st.title("💰 Partner Portál")
        
        tab_log, tab_reg = st.tabs(["🔐 Prihlásenie", "📝 Registrácia"])
        
        with tab_log:
            with st.form("login"):
                m = st.text_input("Mobil (09XXXXXXXX)")
                h = st.text_input("Heslo", type="password")
                if st.form_submit_button("VSTÚPIŤ"):
                    res = call_script("login", {"mobil": m, "heslo": h})
                    if res.get("status") == "success":
                        st.session_state['user'] = res
                        st.rerun()
                    else: st.error("❌ Nesprávny mobil alebo heslo.")

        with tab_reg:
            with st.form("registration"):
                r_pob = st.selectbox("Pobočka", ["celý Liptov", "Malacky", "Levice", "Bratislava, Trnava, Senec"])
                r_m = st.text_input("Meno")
                r_p = st.text_input("Priezvisko")
                r_mob = st.text_input("Mobil")
                r_hes = st.text_input("Heslo", type="password")
                r_kod = st.text_input("Váš unikátny kód")
                if st.form_submit_button("REGISTROVAŤ SA"):
                    if all([r_m, r_p, r_mob, r_hes, r_kod]):
                        res = call_script("register", {"pobocka": r_pob, "meno": r_m, "priezvisko": r_p, "mobil": r_mob, "heslo": r_hes, "kod": r_kod})
                        if res.get("status") == "success": st.success("✅ Hotovo! Môžete sa prihlásiť.")
                        else: st.error(f"❌ {res.get('message')}")
                    else: st.warning("❗ Vyplňte všetky polia.")

# --- 9. HLAVNÝ SYSTÉM (DASHBOARD) ---
else:
    u = st.session_state['user']
    
    with st.sidebar:
        st.markdown(f"### 👤 {u['meno']} {u['priezvisko']}")
        st.info(f"📍 Pob: {u['pobocka']}\n\n🔑 Rola: {u['rola']}")
        st.divider()
        if st.button("🔄 OBNOVIŤ DÁTA"): st.rerun()
        if st.button("🚪 ODHLÁSIŤ SA"):
            st.session_state['user'] = None
            st.rerun()

    df, users_raw = get_full_data()

    if df.empty:
        st.warning("⚠️ Databáza je prázdna.")
    else:
        # --- SEKICA ADMIN / SUPERADMIN ---
        if u['rola'] in ['admin', 'superadmin']:
            st.title(f"📊 Správa - {u['pobocka']}")
            
            # Filter podľa právomocí
            if u['rola'] == 'superadmin':
                view_df = df
            else:
                view_df = df[(df['pobocka_id'] == u['pobocka']) | (df['p_pobocka'] == u['pobocka'])]

            # Metriky navrchu
            c1, c2, c3 = st.columns(3)
            c1.metric("Obrat celkom", format_currency(view_df['suma_zakazky'].sum()))
            c2.metric("K výplate", format_currency(view_df[~view_df['vyplatene_bool']]['provizia_odporucatel'].sum()))
            c3.metric("Počet zákaziek", len(view_df))

            t1, t2, t3 = st.tabs(["🆕 NOVÉ (NACENIŤ)", "💰 VÝPLATY", "📑 ARCHÍV"])

            with t1:
                st.subheader("Zákazky čakajúce na cenu")
                to_price = view_df[view_df['suma_zakazky'] <= 0]
                if to_price.empty:
                    st.success("✅ Všetko je nacenené.")
                else:
                    for idx, row in to_price.iterrows():
                        p_name = f"{row.get('p_meno', '---')} {row.get('p_priezvisko', '')}"
                        with st.container(border=True):
                            st.write(f"**📍 Adresa:** {row['poznamka']}")
                            st.write(f"**Partner:** {p_name} ({row.get('p_mobil', '---')})")
                            new_val = st.number_input("Zadajte sumu (€)", key=f"inp_{idx}", min_value=0.0, step=10.0)
                            
                            if st.button("ULOŽIŤ SUMU", key=f"btn_{idx}"):
                                # FIX: Ak je Superadmin, musí poslať branch ID priamo zo zakazky, inak mu to Sheets nepovoli
                                b_to_send = row['pobocka_id'] if u['rola'] == 'superadmin' else u['pobocka']
                                res = call_script("updateSuma", {
                                    "row_index": row['row_index'], 
                                    "suma": new_val, 
                                    "admin_pobocka": b_to_send
                                })
                                if res.get("status") == "success":
                                    st.success("✅ Zapísané!")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error(f"❌ Chyba: {res.get('message')}")

            with t2:
                st.subheader("Pripravené na vyplatenie")
                to_pay = view_df[(view_df['suma_zakazky'] > 0) & (~view_df['vyplatene_bool'])]
                if to_pay.empty:
                    st.info("Žiadne provízie na vyplatenie.")
                else:
                    for kod in to_pay['kod_pouzity'].unique():
                        sub = to_pay[to_pay['kod_pouzity'] == kod]
                        name = f"{sub['p_meno'].iloc[0]} {sub['p_priezvisko'].iloc[0]}"
                        with st.expander(f"💰 {name} | K výplate: {format_currency(sub['provizia_odporucatel'].sum())}"):
                            if st.button(f"Označiť {kod} ako vyplatené", key=f"pay_{kod}"):
                                for _, r in sub.iterrows():
                                    call_script("markAsPaid", {"row_index": r['row_index'], "admin_pobocka": u['pobocka']})
                                st.rerun()
                            st.dataframe(sub[['datum', 'poznamka', 'suma_zakazky', 'provizia_odporucatel']], use_container_width=True)

            with t3:
                st.subheader("História všetkých záznamov")
                cols = ['datum', 'kod_pouzity', 'poznamka', 'suma_zakazky', 'provizia_odporucatel', 'vyplatene']
                st.dataframe(view_df[[c for c in cols if c in view_df.columns]], use_container_width=True)

        # --- SEKICA PARTNER ---
        else:
            st.title("💰 Môj Provízny Prehľad")
            my_df = df[df['kod_pouzity'] == u['kod']]
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Zarobené celkovo", format_currency(my_df['provizia_odporucatel'].sum()))
            c2.metric("Nezaplatené", format_currency(my_df[~my_df['vyplatene_bool']]['provizia_odporucatel'].sum()))
            c3.metric("Počet zákaziek", len(my_df))

            st.divider()
            st.subheader("Moje zákazky")
            if my_df.empty:
                st.info("Zatiaľ ste neodoslali žiadne zákazky.")
            else:
                st.dataframe(
                    my_df[['datum', 'poznamka', 'suma_zakazky', 'provizia_odporucatel', 'vyplatene']],
                    column_config={
                        "suma_zakazky": st.column_config.NumberColumn("Cena (€)", format="%.2f"),
                        "provizia_odporucatel": st.column_config.NumberColumn("Provízia (€)", format="%.2f")
                    },
                    use_container_width=True, hide_index=True
                )

    # --- 10. FOOTER ---
    st.markdown("---")
    st.caption(f"© {datetime.now().year} TEPUJEM.SK Enterprise | v5.4.0-STABLE")
