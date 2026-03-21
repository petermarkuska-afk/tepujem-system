import streamlit as st
import pandas as pd
import requests
import base64
import re
import time
from datetime import datetime

# =================================================================
# 1. GLOBÁLNA KONFIGURÁCIA A NASTAVENIA STRÁNKY
# =================================================================
st.set_page_config(
    page_title="TEPUJEM.SK | Enterprise Provízny Systém", 
    page_icon="💰", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ZABEZPEČENIE (SECRETS) ---
try:
    # URL tvojho nasadeného Google Apps Scriptu
    SCRIPT_URL = st.secrets["SCRIPT_URL"]
    # Token, ktorý sa musí zhodovať s REQUIRED_TOKEN v .gs skripte
    API_TOKEN = st.secrets["API_TOKEN"]
except Exception:
    st.error("🚨 KRITICKÁ CHYBA: Chýba konfigurácia v Streamlit Secrets (SCRIPT_URL alebo API_TOKEN).")
    st.stop()

# =================================================================
# 2. POMOCNÉ FUNKCIE (UI, VALIDÁCIA, FORMÁTOVANIE)
# =================================================================
def get_base64_of_bin_file(bin_file):
    """Skonvertuje lokálny obrázok do Base64 pre použitie v CSS pozadí."""
    try:
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except FileNotFoundError:
        return None
    except Exception as e:
        return None

def validate_mobile(mob):
    """Overí, či telefónne číslo spĺňa slovenský formát 09XXXXXXXX."""
    return re.match(r'^09\d{8}$', str(mob)) is not None

def format_currency(val):
    """Formátuje číselnú hodnotu na menu Euro s dvomi desatinnými miestami."""
    try:
        return f"{float(val):.2f} €"
    except (ValueError, TypeError):
        return "0.00 €"

# =================================================================
# 3. KOMUNIKÁCIA S BACKENDOM (GOOGLE APPS SCRIPT API)
# =================================================================
def call_script(action, params=None):
    """Univerzálna funkcia na vykonávanie GET požiadaviek na Google Script API."""
    if params is None:
        params = {}
    params['action'] = action
    params['token'] = API_TOKEN
    try:
        # Timeout nastavený na 45s kvôli pomalším reakciám Google tabuliek
        response = requests.get(SCRIPT_URL, params=params, timeout=45)
        if response.status_code == 200:
            return response.json()
        return {"status": "error", "message": f"Server Error {response.status_code}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# =================================================================
# 4. DATA ENGINE (SYNCHRONIZÁCIA A SPÁJANIE TABULIEK)
# =================================================================
def get_full_data():
    """Načíta transakcie a partnerov a vykoná precízny Data Merge."""
    try:
        # 1. Načítanie všetkých zákaziek (Sheet: transactions_data)
        z_res = requests.get(f"{SCRIPT_URL}?action=getZakazky&token={API_TOKEN}").json()
        df_z = pd.DataFrame(z_res)
        
        # 2. Načítanie všetkých registrovaných užívateľov (Sheet: users_data)
        u_res = requests.get(f"{SCRIPT_URL}?action=getUsers&token={API_TOKEN}").json()
        df_u = pd.DataFrame(u_res)
        
        if df_z.empty:
            return pd.DataFrame(), df_u
            
        # Čistenie a pretypovanie dát pre výpočty
        df_z['suma_zakazky'] = pd.to_numeric(df_z['suma_zakazky'], errors='coerce').fillna(0)
        df_z['provizia_odporucatel'] = pd.to_numeric(df_z['provizia_odporucatel'], errors='coerce').fillna(0)
        
        # FIX: Použitie .str.upper() na Series, aby sme predišli AttributeError
        df_z['vyplatene_bool'] = df_z['vyplatene'].astype(str).str.strip().str.upper() == "TRUE"
        
        # Interný index pre presné smerovanie zápisu do Google Sheets (Row 1 sú hlavičky)
        if 'row_index' not in df_z.columns:
            df_z['row_index'] = range(2, len(df_z) + 2)

        # Merge dát: Priradíme informácie o partnerovi ku každej transakcii cez 'kod_pouzity'
        if not df_u.empty:
            # G stĺpec v Exceli je 'referral_code'
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
        st.error(f"⚠️ KRITICKÁ CHYBA SYNCHRONIZÁCIE: {str(e)}")
        return pd.DataFrame(), pd.DataFrame()

# =================================================================
# 5. PRÉMIOVÝ VIZUÁLNY SYSTÉM (ADVANCED CSS)
# =================================================================
img_base64 = get_base64_of_bin_file("image5.png")
background_css = f"""
<style>
    /* Hlavný kontajner aplikácie s dynamickým pozadím */
    .stApp {{
        background: linear-gradient(rgba(0,0,0,0.88), rgba(0,0,0,0.88)), 
                    url("data:image/png;base64,{img_base64 if img_base64 else ""}");
        background-size: cover;
        background-attachment: fixed;
    }}

    /* Štylizácia hlavného bloku s obsahom */
    [data-testid="stMainBlockContainer"] {{
        background-color: rgba(28, 28, 28, 0.97) !important;
        padding: 50px !important;
        border-radius: 30px;
        border: 1px solid #444;
        box-shadow: 0 20px 60px rgba(0,0,0,0.9);
        margin-top: 30px;
        max-width: 1150px !important;
        margin-left: auto;
        margin-right: auto;
    }}

    /* Globálne nastavenie farieb textu */
    h1, h2, h3, p, label, span, div {{
        color: #ffffff !important;
        font-family: 'Inter', sans-serif;
    }}
    
    /* Zlaté Enterprise tlačidlá */
    .stButton > button {{
        width: 100%;
        border-radius: 15px;
        background: linear-gradient(135deg, #FFD700 0%, #B8860B 100%) !important;
        color: #000000 !important;
        font-weight: 900 !important;
        border: none !important;
        padding: 16px;
        text-transform: uppercase;
        letter-spacing: 1.8px;
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    }}
    
    .stButton > button:hover {{
        transform: scale(1.03);
        box-shadow: 0 10px 25px rgba(255, 215, 0, 0.45);
        color: #000 !important;
    }}

    /* Vstupné polia (Inputs) */
    .stTextInput input, .stSelectbox div, .stNumberInput input {{
        background-color: #222 !important;
        color: white !important;
        border-radius: 12px !important;
        border: 1px solid #444 !important;
    }}

    /* Tabuľky (DataFrames) */
    .stDataFrame {{
        background-color: #1a1a1a !important;
        border-radius: 15px;
        border: 1px solid #333;
    }}
    
    /* Odstránenie Streamlit loga v pätičke */
    footer {{visibility: hidden;}}
    #MainMenu {{visibility: hidden;}}
</style>
"""
st.markdown(background_css, unsafe_allow_html=True)

# =================================================================
# 6. SESSION STATE MANAGEMENT
# =================================================================
if 'user' not in st.session_state:
    st.session_state['user'] = None

# =================================================================
# 7. VSTUPNÁ BRÁNA (LOGIN / REGISTRÁCIA)
# =================================================================
if st.session_state['user'] is None:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.image("https://tepujem.sk/wp-content/uploads/2022/03/logo-tepujem-white.png", width=320)
        st.title("💰 Partner Portál")
        
        tab1, tab2 = st.tabs(["🔐 Prihlásenie", "📝 Registrácia partnera"])
        
        with tab1:
            with st.form("login_form"):
                m_log = st.text_input("Mobil (09XXXXXXXX)")
                h_log = st.text_input("Heslo", type="password")
                if st.form_submit_button("PRIHLÁSIŤ SA"):
                    if validate_mobile(m_log):
                        res = call_script("login", {"mobil": m_log, "heslo": h_log})
                        if res.get("status") == "success":
                            st.session_state['user'] = res
                            st.success("✅ Vitajte späť!")
                            time.sleep(1)
                            st.rerun()
                        else: st.error("❌ Nesprávne prihlasovacie údaje.")
                    else: st.warning("⚠️ Zadajte správny formát mobilného čísla.")

        with tab2:
            with st.form("reg_form"):
                r_pob = st.selectbox("Pobočka", ["celý Liptov", "Malacky", "Levice", "Bratislava, Trnava, Senec"])
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
                        if res.get("status") == "success": 
                            st.success("🎉 Úspešne ste sa registrovali! Môžete sa prihlásiť.")
                        else: st.error(f"❌ {res.get('message')}")
                    else: st.error("❗ Skontrolujte, či sú vyplnené všetky polia správne.")

# =================================================================
# 8. HLAVNÝ SYSTÉM (DASHBOARD)
# =================================================================
else:
    u = st.session_state['user']
    
    # --- BOČNÝ PANEL ---
    with st.sidebar:
        st.markdown(f"### 👤 {u['meno']} {u['priezvisko']}")
        st.info(f"📍 Pobočka: {u['pobocka']}\n\n🔑 Rola: {u['rola'].upper()}")
        st.divider()
        if st.button("🔄 AKTUALIZOVAŤ DÁTA"): st.rerun()
        if st.button("🚪 ODHLÁSIŤ SA"):
            st.session_state['user'] = None
            st.rerun()

    # Načítanie a spracovanie dát
    df, users_raw = get_full_data()

    if df.empty:
        st.info("ℹ️ V databáze momentálne nie sú žiadne evidované zákazky.")
    else:
        # --- SEKICA PRE ADMINA A SUPERADMINA ---
        if u['rola'] in ['admin', 'superadmin']:
            st.title(f"📊 Manažérsky Prehľad")
            
            # Filtrovanie dát podľa pobočky (Superadmin vidí všetko)
            if u['rola'] == 'superadmin':
                view_df = df
            else:
                view_df = df[(df['pobocka_id'] == u['pobocka']) | (df['p_pobocka'] == u['pobocka'])]

            # KPI Panely
            m1, m2, m3 = st.columns(3)
            with m1: st.metric("Obrat Celkom", format_currency(view_df['suma_zakazky'].sum()))
            with m2: st.metric("Provízie k výplate", format_currency(view_df[~view_df['vyplatene_bool']]['provizia_odporucatel'].sum()))
            with m3: st.metric("Počet Transakcií", len(view_df))

            st.divider()
            
            tab_price, tab_pay, tab_history = st.tabs(["🆕 NACENENIE", "💰 VÝPLATY", "📑 ARCHÍV"])

            # --- TAB 1: NACENENIE ---
            with tab_price:
                st.subheader("Nové požiadavky (bez zadanej ceny)")
                to_price = view_df[view_df['suma_zakazky'] <= 0]
                if to_price.empty:
                    st.success("✅ Všetky zákazky sú aktuálne nacenené.")
                else:
                    for idx, row in to_price.iterrows():
                        p_name = f"{row.get('p_meno', '---')} {row.get('p_priezvisko', '')}"
                        with st.container(border=True):
                            st.write(f"**📍 Adresa/Poznámka:** {row['poznamka']}")
                            st.write(f"**Partner:** {p_name} ({row.get('p_mobil', '---')})")
                            n_val = st.number_input(f"Suma za tepovanie (€)", key=f"inp_{idx}", min_value=0.0, step=5.0)
                            
                            if st.button("ULOŽIŤ SUMU", key=f"btn_{idx}"):
                                # KRITICKÝ FIX: Pre Superadmina posielame bypass reťazec
                                auth_branch = "superadmin" if u['rola'] == 'superadmin' else u['pobocka']
                                res = call_script("updateSuma", {
                                    "row_index": row['row_index'], 
                                    "suma": n_val, 
                                    "admin_pobocka": auth_branch
                                })
                                if res.get("status") == "success":
                                    st.success("🎉 Suma úspešne zapísaná!"); time.sleep(1); st.rerun()
                                else: 
                                    st.error(f"❌ Chyba zápisu: {res.get('message')}")

            # --- TAB 2: VÝPLATY ---
            with tab_pay:
                st.subheader("Provízie čakajúce na vyplatenie")
                to_pay = view_df[(view_df['suma_zakazky'] > 0) & (~view_df['vyplatene_bool'])]
                if to_pay.empty:
                    st.info("Žiadne otvorené provízie na úhradu.")
                else:
                    for kod in to_pay['kod_pouzity'].unique():
                        sub = to_pay[to_pay['kod_pouzity'] == kod]
                        partner_full = f"{sub['p_meno'].iloc[0]} {sub['p_priezvisko'].iloc[0]}"
                        with st.expander(f"💰 {partner_full} | Celkom: {format_currency(sub['provizia_odporucatel'].sum())}"):
                            if st.button(f"Označiť {kod} ako VYPLATENÉ", key=f"pay_{kod}"):
                                auth_branch = "superadmin" if u['rola'] == 'superadmin' else u['pobocka']
                                for _, p_row in sub.iterrows():
                                    call_script("markAsPaid", {"row_index": p_row['row_index'], "admin_pobocka": auth_branch})
                                st.success("Platba bola úspešne zaznamenaná."); time.sleep(1); st.rerun()
                            st.dataframe(sub[['datum', 'poznamka', 'suma_zakazky', 'provizia_odporucatel']], use_container_width=True)

            # --- TAB 3: ARCHÍV ---
            with tab_history:
                st.subheader("Kompletná história záznamov")
                st.dataframe(view_df[['datum', 'kod_pouzity', 'poznamka', 'suma_zakazky', 'provizia_odporucatel', 'vyplatene']], use_container_width=True, hide_index=True)

        # --- SEKICA PRE PARTNERA ---
        else:
            st.title("💰 Môj Provízny Prehľad")
            my_df = df[df['kod_pouzity'] == u['kod']]
            
            c1, c2, c3 = st.columns(3)
            with c1: st.metric("Zarobené celkovo", format_currency(my_df['provizia_odporucatel'].sum()))
            with c2: st.metric("K výplate", format_currency(my_df[~my_df['vyplatene_bool']]['provizia_odporucatel'].sum()))
            with c3: st.metric("Počet zákaziek", len(my_df))

            st.divider()
            st.subheader("Zoznam mojich odporúčaní")
            if my_df.empty:
                st.info("Zatiaľ ste neposlali žiadne odporúčania.")
            else:
                st.dataframe(
                    my_df[['datum', 'poznamka', 'suma_zakazky', 'provizia_odporucatel', 'vyplatene']],
                    column_config={
                        "suma_zakazky": st.column_config.NumberColumn("Cena (€)", format="%.2f"),
                        "provizia_odporucatel": st.column_config.NumberColumn("Provízia (€)", format="%.2f"),
                        "vyplatene": "Stav úhrady"
                    },
                    use_container_width=True,
                    hide_index=True
                )

    # --- FOOTER ---
    st.markdown("---")
    st.caption(f"© {datetime.now().year} TEPUJEM.SK Enterprise Backend | Verzia 5.5.0-MASTER-FULL")
