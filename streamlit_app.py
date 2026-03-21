import streamlit as st
import pandas as pd
import requests
import base64
import re
import time
from datetime import datetime

# --- 1. KONFIGURÁCIA STRÁNKY ---
st.set_page_config(
    page_title="TEPUJEM.SK | Partner Portál", 
    page_icon="💰", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. BEZPEČNOSŤ A KONFIGURÁCIA ---
try:
    SCRIPT_URL = st.secrets["SCRIPT_URL"]
    API_TOKEN = st.secrets["API_TOKEN"]
except Exception:
    st.error("🚨 Kritická chyba: Chýba konfigurácia v Streamlit Secrets (SCRIPT_URL alebo API_TOKEN)!")
    st.stop()

# --- 3. POMOCNÉ FUNKCIE (DESIGN & VALIDÁCIA) ---
def get_base64_of_bin_file(bin_file):
    try:
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except FileNotFoundError:
        return None

def validate_mobile(mob):
    """Validácia slovenského formátu mobilu."""
    return re.match(r'^09\d{8}$', str(mob)) is not None

def format_currency(val):
    """Formátovanie čísel na menu Euro."""
    try:
        return f"{float(val):.2f} €"
    except (ValueError, TypeError):
        return "0.00 €"

# --- 4. KOMUNIKÁCIA S BACKENDOM (GOOGLE SCRIPT API) ---
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
        # Načítanie transakcií (Tab transactions_data)
        z_res = requests.get(f"{SCRIPT_URL}?action=getZakazky&token={API_TOKEN}").json()
        df_z = pd.DataFrame(z_res)
        
        # Načítanie užívateľov (Tab users_data)
        u_res = requests.get(f"{SCRIPT_URL}?action=getUsers&token={API_TOKEN}").json()
        df_u = pd.DataFrame(u_res)
        
        if df_z.empty:
            return pd.DataFrame(), df_u
            
        # Ošetrenie typov dát pre výpočty
        df_z['suma_zakazky'] = pd.to_numeric(df_z['suma_zakazky'], errors='coerce').fillna(0)
        df_z['provizia_odporucatel'] = pd.to_numeric(df_z['provizia_odporucatel'], errors='coerce').fillna(0)
        
        # FIX: 'Series' object has no attribute 'upper'
        # Musíme použiť .str accessor pre prácu s textom v stĺpci
        df_z['vyplatene_bool'] = df_z['vyplatene'].astype(str).str.strip().str.upper() == "TRUE"
        
        # Bezpečné prepojenie zákazky s partnerom (Merge cez Referral Code)
        if not df_u.empty:
            # Pripravíme lookup tabuľku (referral_code je v stĺpci G)
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
        st.error(f"⚠️ Chyba synchronizácie: {str(e)}")
        return pd.DataFrame(), pd.DataFrame()

# --- 6. PRÉMIOVÝ VIZUÁL (CSS) ---
img_base64 = get_base64_of_bin_file("image5.png")
background_css = f"""
<style>
    .stApp {{
        background: linear-gradient(rgba(0,0,0,0.82), rgba(0,0,0,0.82)), 
                    url("data:image/png;base64,{img_base64 if img_base64 else ""}");
        background-size: cover;
        background-attachment: fixed;
    }}
    [data-testid="stMainBlockContainer"] {{
        background-color: rgba(28, 28, 28, 0.94) !important;
        padding: 50px !important;
        border-radius: 25px;
        border: 1px solid #444;
        box-shadow: 0 12px 40px rgba(0,0,0,0.6);
    }}
    h1, h2, h3, p, label, span {{ color: white !important; font-family: 'Inter', sans-serif; }}
    
    /* Zlaté tlačidlá Tepujem.sk */
    .stButton > button {{
        width: 100%;
        border-radius: 12px;
        background: linear-gradient(135deg, #FFD700 0%, #B8860B 100%) !important;
        color: black !important;
        font-weight: 800 !important;
        border: none !important;
        padding: 12px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }}
    .stDataFrame {{ background-color: #1a1a1a !important; border-radius: 10px; }}
</style>
"""
st.markdown(background_css, unsafe_allow_html=True)

# --- 7. SESSION MANAGEMENT ---
if 'user' not in st.session_state:
    st.session_state['user'] = None

# --- 8. VSTUPNÁ BRÁNA (LOGIN / REG) ---
if st.session_state['user'] is None:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.image("https://tepujem.sk/wp-content/uploads/2022/03/logo-tepujem-white.png", width=280)
        st.title("💰 Partner Portál")
        
        t1, t2 = st.tabs(["🔐 Prihlásenie", "📝 Registrácia partnera"])
        
        with t1:
            with st.form("login_form"):
                m = st.text_input("Mobil (09XXXXXXXX)")
                h = st.text_input("Heslo", type="password")
                if st.form_submit_button("Vstúpiť"):
                    if validate_mobile(m):
                        res = call_script("login", {"mobil": m, "heslo": h})
                        if res.get("status") == "success":
                            st.session_state['user'] = res
                            st.rerun()
                        else: st.error("❌ Nesprávne údaje.")
                    else: st.warning("⚠️ Zadajte mobil v tvare 09XXXXXXXX.")

        with t2:
            with st.form("reg_form"):
                r_pob = st.selectbox("Domovská pobočka", ["celý Liptov", "Malacky", "Levice", "Bratislava, Trnava, Senec"])
                rm, rp = st.columns(2)
                r_meno = rm.text_input("Meno")
                r_priez = rp.text_input("Priezvisko")
                r_mob = st.text_input("Mobil (09XXXXXXXX)")
                r_hes = st.text_input("Heslo", type="password")
                r_kod = st.text_input("Váš unikátny referral kód")
                
                if st.form_submit_button("Registrovať sa"):
                    if all([r_meno, r_priez, r_mob, r_hes, r_kod]) and validate_mobile(r_mob):
                        res = call_script("register", {
                            "pobocka": r_pob, "meno": r_meno, "priezvisko": r_priez,
                            "mobil": r_mob, "heslo": r_hes, "kod": r_kod
                        })
                        if res.get("status") == "success": st.success("🎉 Úspešne registrované!")
                        else: st.error("❌ Registrácia zlyhala (Kód/Mobil už existuje).")
                    else: st.error("❗ Vyplňte všetky polia správne.")

# --- 9. HLAVNÝ DASHBOARD ---
else:
    u = st.session_state['user']
    
    with st.sidebar:
        st.markdown(f"### 👤 {u['meno']} {u['priezvisko']}")
        st.info(f"📍 {u['pobocka']}\n\n🔑 Rola: {u['rola']}")
        st.divider()
        if st.button("🔄 Obnoviť dáta"): st.rerun()
        if st.button("🚪 Odhlásiť sa"):
            st.session_state['user'] = None
            st.rerun()

    # Načítanie dát cez Data Engine
    df, users_raw = get_full_data()

    if df.empty:
        st.info("ℹ️ Zatiaľ žiadne záznamy v databáze.")
    else:
        # --- SEKICA ADMIN / SUPERADMIN ---
        if u['rola'] in ['admin', 'superadmin']:
            st.title(f"📊 Správa - {u['pobocka']}")
            
            # Filtrovanie prístupu
            if u['rola'] == 'superadmin':
                view_df = df
            else:
                view_df = df[(df['pobocka_id'] == u['pobocka']) | (df['p_pobocka'] == u['pobocka'])]

            # Metriky
            k1, k2, k3 = st.columns(3)
            k1.metric("Obrat celkom", format_currency(view_df['suma_zakazky'].sum()))
            k2.metric("Provízie k výplate", format_currency(view_df[~view_df['vyplatene_bool']]['provizia_odporucatel'].sum()))
            k3.metric("Počet zákaziek", len(view_df))

            tab_n, tab_v, tab_h = st.tabs(["🆕 Na nacenenie", "💰 Na vyplatenie", "📑 Kompletná história"])

            with tab_n:
                st.subheader("Nové zákazky (čakajú na sumu)")
                to_price = view_df[view_df['suma_zakazky'] <= 0]
                if to_price.empty:
                    st.success("✅ Všetko je nacenené.")
                else:
                    for i, r in to_price.iterrows():
                        p_name = f"{r.get('p_meno', '---')} {r.get('p_priezvisko', '')}"
                        with st.expander(f"📍 {r['poznamka']} | Partner: {p_name}"):
                            st.write(f"**Kontakt partnera:** {r.get('p_mobil', '---')}")
                            n_val = st.number_input("Suma zákazky (€)", key=f"s_{i}", min_value=0.0)
                            if st.button("Uložiť", key=f"b_{i}"):
                                res = call_script("updateSuma", {"row_index": r['row_index'], "suma": n_val, "admin_pobocka": u['pobocka']})
                                if res.get("status") == "success":
                                    st.success("Uložené!")
                                    time.sleep(0.5)
                                    st.rerun()

            with tab_v:
                st.subheader("Provízie pripravené na úhradu")
                to_pay = view_df[(view_df['suma_zakazky'] > 0) & (~view_df['vyplatene_bool'])]
                if to_pay.empty:
                    st.info("Žiadne provízie na vyplatenie.")
                else:
                    for kod in to_pay['kod_pouzity'].unique():
                        sub = to_pay[to_pay['kod_pouzity'] == kod]
                        name = f"{sub['p_meno'].iloc[0]} {sub['p_priezvisko'].iloc[0]}"
                        with st.container(border=True):
                            c_a, c_b = st.columns([3, 1])
                            c_a.write(f"**Partner:** {name} (`{kod}`) | **K výplate:** {format_currency(sub['provizia_odporucatel'].sum())}")
                            if c_b.button(f"Vyplatiť {kod}", key=f"pay_{kod}"):
                                for _, row in sub.iterrows():
                                    call_script("markAsPaid", {"row_index": row['row_index'], "admin_pobocka": u['pobocka']})
                                st.rerun()
                            st.dataframe(sub[['datum', 'poznamka', 'suma_zakazky', 'provizia_odporucatel']], use_container_width=True)

            with tab_h:
                st.subheader("Celý prehľad")
                # FIX KeyError: Výber stĺpcov robíme bezpečne
                cols = ['datum', 'kod_pouzity', 'poznamka', 'suma_zakazky', 'provizia_odporucatel', 'vyplatene']
                final_cols = [c for c in cols if c in view_df.columns]
                st.dataframe(view_df[final_cols], use_container_width=True)

        # --- SEKICA PARTNER ---
        else:
            st.title("💰 Môj Provízny Prehľad")
            my_df = df[df['kod_pouzity'] == u['kod']]
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Zarobené celkovo", format_currency(my_df['provizia_odporucatel'].sum()))
            c2.metric("Nezaplatené", format_currency(my_df[~my_df['vyplatene_bool']]['provizia_odporucatel'].sum()))
            c3.metric("Počet odporúčaní", len(my_df))

            st.divider()
            st.subheader("Moje zákazky")
            if my_df.empty:
                st.info("Zatiaľ žiadne odporúčania.")
            else:
                # FIX KeyError: Výber stĺpcov robíme bezpečne
                p_cols = ['datum', 'poznamka', 'suma_zakazky', 'provizia_odporucatel', 'vyplatene']
                final_p_cols = [c for c in p_cols if c in my_df.columns]
                
                st.dataframe(
                    my_df[final_p_cols],
                    column_config={
                        "suma_zakazky": st.column_config.NumberColumn("Cena tepovania", format="%.2f €"),
                        "provizia_odporucatel": st.column_config.NumberColumn("Moja provízia", format="%.2f €"),
                        "vyplatene": "Stav platby"
                    },
                    use_container_width=True,
                    hide_index=True
                )

    # --- 10. FOOTER ---
    st.markdown("---")
    st.caption(f"© {datetime.now().year} TEPUJEM.SK Enterprise System | v5.1.0-STABLE")
