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
    st.error("🚨 Kritická chyba: Chýba konfigurácia v Streamlit Secrets!")
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
    return re.match(r'^09\d{8}$', str(mob)) is not None

def format_currency(val):
    try:
        return f"{float(val):.2f} €"
    except:
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
        return {"status": "error", "message": "Server Error"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- 5. DATA ENGINE (ZÍSKAVANIE A MERGE) ---
def get_full_data():
    try:
        # Načítanie transakcií
        z_res = requests.get(f"{SCRIPT_URL}?action=getZakazky&token={API_TOKEN}").json()
        df_z = pd.DataFrame(z_res)
        
        # Načítanie užívateľov
        u_res = requests.get(f"{SCRIPT_URL}?action=getUsers&token={API_TOKEN}").json()
        df_u = pd.DataFrame(u_res)
        
        if df_z.empty:
            return pd.DataFrame(), df_u
            
        # Ošetrenie typov dát
        df_z['suma_zakazky'] = pd.to_numeric(df_z['suma_zakazky'], errors='coerce').fillna(0)
        df_z['provizia_odporucatel'] = pd.to_numeric(df_z['provizia_odporucatel'], errors='coerce').fillna(0)
        
        # OPRAVA: Series object has no attribute 'upper'
        # Používame .str.upper() na celú sériu
        df_z['vyplatene_bool'] = df_z['vyplatene'].astype(str).str.strip().str.upper() == "TRUE"
        
        # Komplexný Merge (prepojenie zákazky s partnerom cez kód)
        if not df_u.empty:
            df_u_clean = df_u.rename(columns={
                'referral_code': 'kod_pouzity',
                'mobil': 'partner_mobil',
                'meno': 'partner_meno',
                'priezvisko': 'partner_priezvisko',
                'pobocka': 'partner_pobocka'
            })
            df_merged = df_z.merge(df_u_clean, on='kod_pouzity', how='left')
            return df_merged, df_u
        
        return df_z, df_u
    except Exception as e:
        st.error(f"⚠️ Chyba synchronizácie dát: {e}")
        return pd.DataFrame(), pd.DataFrame()

# --- 6. PRÉMIOVÝ VIZUÁL (CSS) ---
img_base64 = get_base64_of_bin_file("image5.png")
background_css = f"""
<style>
    .stApp {{
        background: linear-gradient(rgba(0,0,0,0.8), rgba(0,0,0,0.8)), url("data:image/png;base64,{img_base64 if img_base64 else ""}");
        background-size: cover;
        background-attachment: fixed;
    }}
    [data-testid="stMainBlockContainer"] {{
        background-color: rgba(20, 20, 20, 0.92) !important;
        padding: 50px !important;
        border-radius: 25px;
        border: 1px solid #333;
        box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    }}
    h1, h2, h3, p, label {{ color: white !important; font-family: 'Inter', sans-serif; }}
    .stButton > button {{
        width: 100%;
        border-radius: 12px;
        background: linear-gradient(135deg, #FFD700 0%, #B8860B 100%) !important;
        color: black !important;
        font-weight: bold !important;
        border: none !important;
        transition: 0.3s;
    }}
    .stButton > button:hover {{ transform: scale(1.02); }}
</style>
"""
st.markdown(background_css, unsafe_allow_html=True)

# --- 7. SESSION MANAGEMENT ---
if 'user' not in st.session_state:
    st.session_state['user'] = None

# --- 8. PRIHLÁSENIE A REGISTRÁCIA ---
if st.session_state['user'] is None:
    cols = st.columns([1, 2, 1])
    with cols[1]:
        st.image("https://tepujem.sk/wp-content/uploads/2022/03/logo-tepujem-white.png", width=250)
        st.title("💰 Provízny Portál")
        
        auth_tab1, auth_tab2 = st.tabs(["🔐 Prihlásenie", "📝 Registrácia"])
        
        with auth_tab1:
            with st.form("login_form"):
                l_mob = st.text_input("Mobil (09XXXXXXXX)")
                l_hes = st.text_input("Heslo", type="password")
                if st.form_submit_button("Vstúpiť do portálu"):
                    if not validate_mobile(l_mob):
                        st.warning("⚠️ Neplatný formát mobilu.")
                    else:
                        res = call_script("login", {"mobil": l_mob, "heslo": l_hes})
                        if res.get("status") == "success":
                            st.session_state['user'] = res
                            st.rerun()
                        else:
                            st.error("❌ Nesprávne meno alebo heslo.")

        with auth_tab2:
            with st.form("reg_form"):
                r_pob = st.selectbox("Pobočka", ["Bratislava", "Košice", "Žilina", "Liptov", "Malacky", "Levice"])
                col_m, col_p = st.columns(2)
                r_meno = col_m.text_input("Meno")
                r_priez = col_p.text_input("Priezvisko")
                r_mob = st.text_input("Mobil (09XXXXXXXX)")
                r_hes = st.text_input("Heslo", type="password")
                r_kod = st.text_input("Vlastný referral kód (napr. FERI10)")
                
                if st.form_submit_button("Dokončiť registráciu"):
                    if not all([r_meno, r_priez, r_mob, r_hes, r_kod]):
                        st.error("❗ Vyplňte všetky polia.")
                    elif not validate_mobile(r_mob):
                        st.error("❗ Nesprávny formát mobilu.")
                    else:
                        res = call_script("register", {
                            "pobocka": r_pob, "meno": r_meno, "priezvisko": r_priez,
                            "mobil": r_mob, "heslo": r_hes, "kod": r_kod
                        })
                        if res.get("status") == "success":
                            st.success("🎉 Registrácia úspešná! Teraz sa môžete prihlásiť.")
                        else:
                            st.error(f"Chyba: {res.get('message', 'Kód sa už používa')}")

# --- 9. DASHBOARD ---
else:
    u = st.session_state['user']
    
    with st.sidebar:
        st.markdown(f"### 👤 {u['meno']} {u['priezvisko']}")
        st.info(f"📍 {u['pobocka']}\n\n🔑 Rola: {u['rola']}")
        st.divider()
        if st.button("🔄 Aktualizovať dáta"): st.rerun()
        if st.button("🚪 Odhlásiť sa"):
            st.session_state['user'] = None
            st.rerun()

    df, users_raw = get_full_data()

    if df.empty:
        st.warning("⚠️ Žiadne záznamy v databáze.")
    else:
        # --- ROZHRANIE ADMIN / SUPERADMIN ---
        if u['rola'] in ['admin', 'superadmin']:
            st.title(f"📊 Správa - {u['pobocka']}")
            
            # Filter dát podľa právomocí
            if u['rola'] == 'superadmin':
                admin_df = df
            else:
                admin_df = df[(df['pobocka_id'] == u['pobocka']) | (df['partner_pobocka'] == u['pobocka'])]

            # KPI Panely
            m1, m2, m3 = st.columns(3)
            m1.metric("Celkový obrat", format_currency(admin_df['suma_zakazky'].sum()))
            m2.metric("K výplate partnerom", format_currency(admin_df[~admin_df['vyplatene_bool']]['provizia_odporucatel'].sum()))
            m3.metric("Počet zákaziek", len(admin_df))

            t_new, t_pay, t_all = st.tabs(["🆕 Na nacenenie", "💰 Na vyplatenie", "📑 História"])

            with t_new:
                st.subheader("Zákazky bez sumy")
                to_price = admin_df[admin_df['suma_zakazky'] <= 0]
                if to_price.empty:
                    st.success("Všetko je nacenené.")
                else:
                    for i, r in to_price.iterrows():
                        p_label = f"{r.get('partner_meno', 'Neznámy')} {r.get('partner_priezvisko', '')}"
                        with st.expander(f"📍 {r['poznamka']} | Partner: {p_label}"):
                            st.write(f"**Kontakt partnera:** {r.get('partner_mobil', '---')}")
                            n_suma = st.number_input("Zadajte sumu (€)", key=f"s_{i}", min_value=0.0)
                            if st.button("Uložiť nacenenie", key=f"b_{i}"):
                                res = call_script("updateSuma", {"row_index": r['row_index'], "suma": n_suma, "admin_pobocka": u['pobocka']})
                                if res.get("status") == "success":
                                    st.success("Suma bola uložená!")
                                    time.sleep(0.5)
                                    st.rerun()

            with t_pay:
                st.subheader("Nevyplatené provízie")
                to_pay = admin_df[(admin_df['suma_zakazky'] > 0) & (~admin_df['vyplatene_bool'])]
                if to_pay.empty:
                    st.info("Žiadne provízie na vyplatenie.")
                else:
                    for kod in to_pay['kod_pouzity'].unique():
                        p_subset = to_pay[to_pay['kod_pouzity'] == kod]
                        p_name = f"{p_subset['partner_meno'].iloc[0]} {p_subset['partner_priezvisko'].iloc[0]}"
                        with st.container(border=True):
                            c_p1, c_p2 = st.columns([3, 1])
                            c_p1.write(f"**Partner:** {p_name} (`{kod}`)  \n**Suma k výplate:** {format_currency(p_subset['provizia_odporucatel'].sum())}")
                            if c_p2.button(f"Označiť ako vyplatené", key=f"pay_{kod}"):
                                for _, row in p_subset.iterrows():
                                    call_script("markAsPaid", {"row_index": row['row_index'], "admin_pobocka": u['pobocka']})
                                st.rerun()
                            st.dataframe(p_subset[['datum', 'poznamka', 'suma_zakazky', 'provizia_odporucatel']], use_container_width=True)

            with t_all:
                st.subheader("Kompletná databáza")
                # OPRAVA KeyError: Zobrazujeme len stĺpce, ktoré reálne existujú
                available_cols = ['datum', 'kod_pouzity', 'poznamka', 'suma_zakazky', 'provizia_odporucatel', 'vyplatene']
                cols_to_show = [c for c in available_cols if c in admin_df.columns]
                st.dataframe(admin_df[cols_to_show], use_container_width=True)

        # --- ROZHRANIE PARTNER ---
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
                st.info("Zatiaľ ste neodoslali žiadne odporúčania.")
            else:
                st.dataframe(
                    my_df[['datum', 'poznamka', 'suma_zakazky', 'provizia_odporucatel', 'vyplatene']],
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
    st.caption(f"© {datetime.now().year} TEPUJEM.SK Portál | Verzia 5.0.0-STABLE")
