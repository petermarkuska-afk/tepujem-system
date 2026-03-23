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
    st.error("🚨 KRITICKÁ CHYBA: Chýba konfigurácia (Secrets). Skontrolujte .streamlit/secrets.toml")
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

def validate_mobile(mob):
    """Validácia mobilného čísla 09XXXXXXXX."""
    return re.match(r'^09\d{8}$', str(mob)) is not None

def format_currency(val):
    try:
        return f"{float(val):.2f} €"
    except (ValueError, TypeError):
        return "0.00 €"

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
# 3. DATA ENGINE (S VYNUCOVANÍM REFRESHU)
# =================================================================
@st.cache_data(ttl=600)
def get_full_data():
    try:
        # Načítanie zákaziek
        z_res = requests.get(f"{SCRIPT_URL}?action=getZakazky&token={API_TOKEN}").json()
        df_z = pd.DataFrame(z_res)
        
        # Načítanie užívateľov (adminov/partnerov)
        u_res = requests.get(f"{SCRIPT_URL}?action=getUsers&token={API_TOKEN}").json()
        df_u = pd.DataFrame(u_res)
        
        if df_z.empty:
            return pd.DataFrame(), df_u
            
        df_z.columns = [str(c).strip() for c in df_z.columns]

        # Konverzia číselných stĺpcov pre výpočty
        for col in ['suma_zakazky', 'provizia_odporucatel']:
            if col in df_z.columns:
                df_z[col] = pd.to_numeric(df_z[col], errors='coerce').fillna(0)
        
        # Logika pre stav 'vyplatene' (stĺpec G v Google Sheets)
        if 'vyplatene' in df_z.columns:
            df_z['vyplatene_bool'] = df_z['vyplatene'].astype(str).str.strip().str.upper().isin(["TRUE", "1", "YES"])
        else:
            df_z['vyplatene_bool'] = False
        
        # Indexovanie riadkov pre spätný zápis (začíname od 2 kvôli hlavičke v Sheets)
        if 'row_index' not in df_z.columns:
            df_z['row_index'] = range(2, len(df_z) + 2)

        # Prepojenie zákaziek s menami partnerov podľa kódu
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
        st.error(f"⚠️ Chyba synchronizácie dát: {str(e)}")
        return pd.DataFrame(), pd.DataFrame()

# =================================================================
# 4. PRÉMIOVÝ VIZUÁL (CSS)
# =================================================================
img_b64 = get_base64_of_bin_file("image5.png")
st.markdown(f"""
<style>
    .stApp {{
        background: linear-gradient(rgba(0,0,0,0.9), rgba(0,0,0,0.9)), 
                    url("data:image/png;base64,{img_b64}");
        background-size: cover; background-attachment: fixed;
    }}
    [data-testid="stMainBlockContainer"] {{
        background-color: rgba(28, 28, 28, 0.98) !important;
        padding: 50px !important; border-radius: 25px; border: 1px solid #444;
        box-shadow: 0 20px 60px rgba(0,0,0,0.9); max-width: 1100px !important; margin: auto;
    }}
    h1, h2, h3, p, label {{ color: white !important; font-family: 'Inter', sans-serif; }}
    
    .stButton > button {{
        width: 100%; border-radius: 12px; height: 3.5rem;
        background: linear-gradient(135deg, #FFD700 0%, #B8860B 100%) !important;
        color: black !important; font-weight: 800 !important; border: none !important;
        text-transform: uppercase; letter-spacing: 1.5px; transition: 0.3s;
    }}
    .stButton > button:hover {{ transform: scale(1.02); box-shadow: 0 10px 20px rgba(255,215,0,0.3); }}
    
    .stTextInput input, .stSelectbox div {{ background-color: #222 !important; color: white !important; border-radius: 10px !important; }}
    .stDataFrame {{ background-color: #1a1a1a !important; border-radius: 15px; border: 1px solid #333; }}
    
    .stTabs [data-baseweb="tab-list"] {{ gap: 10px; }}
    .stTabs [data-baseweb="tab"] {{
        background-color: #222 !important; border-radius: 10px 10px 0 0 !important;
        padding: 10px 20px !important; color: #888 !important;
    }}
    .stTabs [aria-selected="true"] {{ color: #FFD700 !important; border-bottom: 2px solid #FFD700 !important; }}
</style>
""", unsafe_allow_html=True)

# =================================================================
# 5. AUTHENTIKÁCIA (LOGIN & REGISTRÁCIA)
# =================================================================
if 'user' not in st.session_state:
    st.session_state['user'] = None

# Načítame dáta pre dynamický zoznam pobočiek v registrácii
df_main, df_users_db = get_full_data()

if st.session_state['user'] is None:
    _, col_login, _ = st.columns([1, 2, 1])
    with col_login:
        st.markdown("<h1 style='text-align: center; font-size: 3rem; margin-bottom: 0;'>💰 Zarob si s</h1>", unsafe_allow_html=True)
        st.markdown("<h1 style='text-align: center; color: #FFD700 !important; margin-top: -10px; margin-bottom: 30px;'>TEPUJEM.SK</h1>", unsafe_allow_html=True)
        
        t_log, t_reg = st.tabs(["🔐 Prihlásenie", "📝 Registrácia"])
        
        with t_log:
            with st.form("auth_login"):
                m_login = st.text_input("Mobil (09XXXXXXXX)")
                h_login = st.text_input("Heslo", type="password")
                if st.form_submit_button("VSTÚPIŤ DO PORTÁLU"):
                    res = call_script("login", {"mobil": m_login, "heslo": h_login})
                    if res.get("status") == "success":
                        st.session_state['user'] = res
                        st.cache_data.clear()
                        st.rerun()
                    else: 
                        st.error("❌ Nesprávne mobilné číslo alebo heslo.")

        with t_reg:
            with st.form("auth_reg"):
                # DYNAMICKÝ VÝBER POBOČKY (Ťahá unikátne pobočky z databázy užívateľov)
                if not df_users_db.empty and 'pobocka' in df_users_db.columns:
                    list_branches = sorted(df_users_db['pobocka'].unique().tolist())
                else:
                    list_branches = ["celý Liptov", "Malacky", "Levice", "Bratislava, Trnava, Senec", "Vranov a Košice"]
                
                pob_reg = st.selectbox("Pobočka", list_branches)
                
                c1, c2 = st.columns(2)
                men_reg = c1.text_input("Meno")
                pri_reg = c2.text_input("Priezvisko")
                mes_reg = st.text_input("Mesto / Obec")
                mob_reg = st.text_input("Mobil (09XXXXXXXX)")
                hes_reg = st.text_input("Heslo", type="password")
                kod_reg = st.text_input("Vlastný referral kód (napr. MOJKOD10)")
                
                if st.form_submit_button("ZAREGISTROVAŤ SA"):
                    if all([men_reg, pri_reg, mes_reg, mob_reg, hes_reg, kod_reg]) and validate_mobile(mob_reg):
                        res = call_script("register", {
                            "pobocka": pob_reg, 
                            "meno": men_reg, 
                            "priezvisko": pri_reg, 
                            "mesto": mes_reg, 
                            "mobil": mob_reg, 
                            "heslo": hes_reg, 
                            "kod": kod_reg
                        })
                        if res.get("status") == "success": 
                            st.success("🎉 Úspešne ste sa zaregistrovali! Teraz sa môžete prihlásiť.")
                        else: 
                            st.error(f"❌ Chyba: {res.get('message')}")
                    else: 
                        st.warning("⚠️ Vyplňte všetky polia správne a skontrolujte formát mobilu.")

# =================================================================
# 6. HLAVNÝ DASHBOARD (ADMIN A PARTNER)
# =================================================================
else:
    u = st.session_state['user']
    with st.sidebar:
        st.markdown(f"### 👤 {u['meno']} {u['priezvisko']}")
        st.info(f"📍 {u['pobocka']}\n🔑 {u.get('rola', 'partner').upper()}")
        st.divider()
        if st.button("🔄 OBNOVIŤ DÁTA"):
            st.cache_data.clear()
            st.rerun()
        if st.button("🚪 ODHLÁSIŤ SA"):
            st.cache_data.clear()
            st.session_state['user'] = None
            st.rerun()

    # Použijeme už načítané dáta (df_main)
    if not df_main.empty:
        # --- ROZHRANIE PRE ADMINA / SUPERADMINA ---
        if u.get('rola') in ['admin', 'superadmin']:
            st.title("📊 Administrácia systému")
            # Filtrovanie dát podľa pobočky admina (superadmin vidí všetko)
            view_df = df_main if u['rola'] == 'superadmin' else df_main[df_main['p_pobocka'] == u['pobocka']]

            # Metriky
            m1, m2, m3 = st.columns(3)
            m1.metric("Obrat Celkom", format_currency(view_df['suma_zakazky'].sum()))
            k_vyplate = view_df[(view_df['suma_zakazky'] > 0) & (~view_df['vyplatene_bool'])]['provizia_odporucatel'].sum()
            m2.metric("Provízie k úhrade", format_currency(k_vyplate))
            m3.metric("Počet zákaziek", len(view_df))

            st.divider()
            t1, t2, t3 = st.tabs(["🆕 NACENIŤ", "💸 VÝPLATY", "📜 ARCHÍV"])

            with t1:
                # Zákazky, ktoré ešte nemajú sumu (suma_zakazky <= 0)
                to_price = view_df[view_df['suma_zakazky'] <= 0]
                if to_price.empty: 
                    st.success("✅ Všetky doručené zákazky sú už nacenené.")
                else:
                    for i, r in to_price.iterrows():
                        with st.container(border=True):
                            cl, cr = st.columns([3, 1])
                            cl.write(f"**📍 {r.get('mesto', 'N/A')}** | {r.get('poznamka', '')}")
                            cl.caption(f"Partner: {r.get('p_meno', 'Neznámy')} (`{r['kod_pouzity']}`)")
                            n_sum = cr.number_input("Zadajte sumu (€)", key=f"s_{i}", min_value=0.0, step=1.0)
                            if cr.button("ULOŽIŤ SUMU", key=f"b_{i}"):
                                p_calc = n_sum * 0.05
                                admin_tag = "superadmin" if u['rola'] == 'superadmin' else u['pobocka']
                                res = call_script("updateSuma", {
                                    "row_index": r['row_index'], 
                                    "suma": n_sum, 
                                    "provizia": p_calc, 
                                    "admin_pobocka": admin_tag
                                })
                                if res.get("status") == "success":
                                    st.cache_data.clear()
                                    st.success("Suma bola úspešne zapísaná!")
                                    time.sleep(0.5)
                                    st.rerun()

            with t2:
                # Zákazky so sumou, ktoré ešte neboli vyplatené
                to_pay = view_df[(view_df['suma_zakazky'] > 0) & (~view_df['vyplatene_bool'])]
                if to_pay.empty: 
                    st.info("Momentálne nie sú žiadne otvorené provízie na vyplatenie.")
                else:
                    for k in to_pay['kod_pouzity'].unique():
                        sub = to_pay[to_pay['kod_pouzity'] == k]
                        sum_to_pay = sub['provizia_odporucatel'].sum()
                        with st.expander(f"💰 {k} | K úhrade: {format_currency(sum_to_pay)}"):
                            if st.button(f"Označiť kód {k} ako vyplatený", key=f"pay_{k}"):
                                for _, pr in sub.iterrows():
                                    call_script("markAsPaid", {"row_index": pr['row_index']})
                                st.cache_data.clear()
                                st.success(f"Kód {k} bol spracovaný.")
                                time.sleep(0.5)
                                st.rerun()
                            # Dynamická kontrola stĺpcov pre zobrazenie
                            cols_to_disp = [c for c in ['mesto', 'suma_zakazky', 'provizia_odporucatel'] if c in sub.columns]
                            st.dataframe(sub[cols_to_disp], use_container_width=True, hide_index=True)

            with t3:
                # Všetky zákazky pre prehľad (Archív)
                all_cols = ['mesto', 'kod_pouzity', 'poznamka', 'suma_zakazky', 'provizia_odporucatel', 'vyplatene']
                available_cols = [c for c in all_cols if c in view_df.columns]
                st.dataframe(view_df[available_cols], use_container_width=True, hide_index=True)

        # --- ROZHRANIE PRE PARTNERA ---
        else:
            st.title("💰 Moje Provízie")
            # Používame kód 'kod', ktorý sme dostali pri prihlásení
            my_code = u.get('kod')
            my_df = df_main[df_main['kod_pouzity'] == my_code]
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Zarobené celkom", format_currency(my_df['provizia_odporucatel'].sum()))
            unpaid_val = my_df[~my_df['vyplatene_bool']]['provizia_odporucatel'].sum()
            c2.metric("Čaká na výplatu", format_currency(unpaid_val))
            c3.metric("Počet odporúčaní", len(my_df))
            
            st.divider()
            if my_df.empty:
                st.info("Zatiaľ tu nemáte žiadne zákazky. Keď niekto použije váš kód, uvidíte to tu.")
            else:
                p_cols = ['mesto', 'poznamka', 'suma_zakazky', 'provizia_odporucatel', 'vyplatene']
                available_p_cols = [c for c in p_cols if c in my_df.columns]
                st.dataframe(my_df[available_p_cols], use_container_width=True, hide_index=True)

    else:
        st.warning("Dáta sú prázdne alebo sa ich nepodarilo načítať.")

    st.caption(f"© {datetime.now().year} TEPUJEM.SK Enterprise System | v6.9.0")
