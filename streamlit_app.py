import streamlit as st
import pandas as pd
import requests
import base64
import re
import time
from datetime import datetime
import plotly.express as px  # Pre vizualizáciu v Admin zóne

# --- 1. KONFIGURÁCIA STRÁNKY ---
st.set_page_config(
    page_title="TEPUJEM.SK | Partner Portál", 
    page_icon="💰", 
    layout="wide",  # Širšie rozloženie pre lepšiu prehľadnosť tabuliek
    initial_sidebar_state="expanded"
)

# --- 2. SECRETS & KONFIGURÁCIA ---
try:
    SCRIPT_URL = st.secrets["SCRIPT_URL"]
    API_TOKEN = st.secrets["API_TOKEN"]
except Exception:
    st.error("🚨 Kritická chyba: Chýba konfigurácia v Streamlit Secrets (SCRIPT_URL alebo API_TOKEN)!")
    st.stop()

# --- 3. POMOCNÉ FUNKCIE (Vizuál & Systém) ---
def get_base64_of_bin_file(bin_file):
    """Načítanie lokálneho obrázka pre CSS pozadie."""
    try:
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except FileNotFoundError:
        return None

def validate_mobile(mob):
    """Validácia slovenského mobilného formátu 09XXXXXXXX."""
    pattern = r'^09\d{8}$'
    return re.match(pattern, mob) is not None

def format_currency(val):
    """Formátovanie meny pre tabuľky."""
    return f"{val:.2f} €"

# --- 4. KOMUNIKÁCIA S BACKENDOM (API) ---
def call_script(action, params=None):
    """Univerzálny komunikačný bridge s Google Apps Scriptom."""
    if params is None:
        params = {}
    
    # Povinné bezpečnostné parametre
    params['action'] = action
    params['token'] = API_TOKEN
    
    try:
        # Používame POST pre zápis a GET pre čítanie (tu GET pre jednoduchosť, ale s tokenom)
        response = requests.get(SCRIPT_URL, params=params, timeout=45)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Chyba servera: {response.status_code}")
            return {"status": "error", "message": "Server communication failed"}
    except Exception as e:
        st.error(f"⚠️ Pripojenie zlyhalo: {str(e)}")
        return {"status": "error", "message": str(e)}

# --- 5. DATA FETCHING (Živé dáta) ---
@st.fragment
def refresh_data_logic():
    """Fragment pre rýchle obnovenie dát bez celého reloadu."""
    st.session_state['last_refresh'] = datetime.now().strftime("%H:%M:%S")

def get_full_data():
    """Načíta transakcie a užívateľov a vykoná komplexný merge."""
    try:
        # 1. Načítanie zákaziek
        raw_zakazky = requests.get(f"{SCRIPT_URL}?action=getZakazky&token={API_TOKEN}").json()
        df_z = pd.DataFrame(raw_zakazky)
        
        # 2. Načítanie užívateľov
        raw_users = requests.get(f"{SCRIPT_URL}?action=getUsers&token={API_TOKEN}").json()
        df_u = pd.DataFrame(raw_users)
        
        if df_z.empty:
            return pd.DataFrame(), df_u
            
        # Čistenie a typovanie dát
        df_z['suma_zakazky'] = pd.to_numeric(df_z['suma_zakazky'], errors='coerce').fillna(0)
        df_z['provizia_odporucatel'] = pd.to_numeric(df_z['provizia_odporucatel'], errors='coerce').fillna(0)
        df_z['vyplatene_bool'] = df_z['vyplatene'].astype(str).str.strip().upper() == "TRUE"
        
        # Komplexný Merge (v tabuľke je 'referral_code', v session je 'kod')
        if not df_u.empty:
            df_u_clean = df_u.rename(columns={
                'referral_code': 'kod_pouzity',
                'mobil': 'partner_mobil',
                'pobocka': 'partner_pobocka',
                'meno': 'partner_meno',
                'priezvisko': 'partner_priezvisko'
            })
            df_merged = df_z.merge(df_u_clean, on='kod_pouzity', how='left')
            return df_merged, df_u
        
        return df_z, df_u
    except Exception as e:
        st.error(f"Chyba pri spracovaní dát: {e}")
        return pd.DataFrame(), pd.DataFrame()

# --- 6. ADVANCED CSS CUSTOMIZATION ---
img_base64 = get_base64_of_bin_file("image5.png")
placeholder_img = "https://images.unsplash.com/photo-1628177142898-93e36e4e3a50?q=80&w=2070&auto=format&fit=crop"

background_url = f"data:image/png;base64,{img_base64}" if img_base64 else placeholder_img

st.markdown(f"""
<style>
    /* Hlavný kontajner */
    .stApp {{
        background: linear-gradient(rgba(0,0,0,0.8), rgba(0,0,0,0.8)), url("{background_url}");
        background-size: cover;
        background-attachment: fixed;
    }}
    
    /* Štýlovanie kariet a blokov */
    [data-testid="stMainBlockContainer"] {{
        background-color: rgba(20, 20, 20, 0.9) !important;
        padding: 50px !important;
        border-radius: 25px;
        border: 1px solid #333;
        box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    }}
    
    /* Vylepšenie inputov */
    input, .stSelectbox, .stTextInput {{
        background-color: #2b2b2b !important;
        color: white !important;
        border-radius: 10px !important;
    }}
    
    /* Metriky */
    [data-testid="stMetricValue"] {{
        color: #00ffcc !important;
        font-weight: bold;
    }}
    
    /* Sidebar */
    [data-testid="stSidebar"] {{
        background-color: #111 !important;
        border-right: 1px solid #333;
    }}

    /* Custom Button Style */
    .stButton > button {{
        width: 100%;
        border-radius: 12px;
        height: 3em;
        background-color: #FFD700 !important;
        color: black !important;
        font-weight: bold !important;
        border: none !important;
        transition: 0.3s;
    }}
    .stButton > button:hover {{
        background-color: #ffed80 !important;
        transform: scale(1.02);
    }}
</style>
""", unsafe_allow_html=True)

# --- 7. SESSION STATE MANAGEMENT ---
if 'user' not in st.session_state:
    st.session_state['user'] = None
if 'last_refresh' not in st.session_state:
    st.session_state['last_refresh'] = datetime.now().strftime("%H:%M:%S")

# --- 8. ČASŤ: PRIHLÁSENIE A REGISTRÁCIA ---
if st.session_state['user'] is None:
    cols = st.columns([1, 2, 1])
    with cols[1]:
        st.image("https://tepujem.sk/wp-content/uploads/2022/03/logo-tepujem-white.png", width=250)
        st.title("💰 Provízny Portál")
        st.write("Vitajte v systéme pre správu vašich odporúčaní.")
        
        choice = st.radio("Vyberte si akciu:", ["Prihlásenie", "Nová registrácia"], horizontal=True)
        
        if choice == "Prihlásenie":
            with st.container(border=True):
                login_mob = st.text_input("Mobil (09XXXXXXXX)", placeholder="Zadajte telefón")
                login_psw = st.text_input("Heslo", type="password")
                if st.button("Vstúpiť do portálu"):
                    if not validate_mobile(login_mob):
                        st.warning("⚠️ Mobilné číslo musí mať formát 09XXXXXXXX.")
                    else:
                        with st.spinner("Overujem údaje..."):
                            res = call_script("login", {"mobil": login_mob, "heslo": login_psw})
                            if res.get("status") == "success":
                                st.session_state['user'] = res
                                st.toast("✅ Prihlásenie úspešné!")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("❌ Nesprávne meno alebo heslo.")
        
        else:
            with st.container(border=True):
                st.subheader("Registračný formulár")
                reg_regions = call_script("getRegions").get("regions", ["Bratislava", "Košice", "Žilina"])
                
                col_a, col_b = st.columns(2)
                with col_a:
                    r_pob = st.selectbox("Pobočka", reg_regions)
                    r_meno = st.text_input("Meno")
                    r_mob = st.text_input("Mobil (09XXXXXXXX)")
                with col_b:
                    r_priez = st.text_input("Priezvisko")
                    r_heslo = st.text_input("Heslo", type="password")
                    r_kod = st.text_input("Vlastný kód (napr. FERI10)")
                
                r_adr = st.text_area("Fakturačná adresa / Sídlo")
                
                if st.button("Odoslať registráciu"):
                    if not all([r_meno, r_priez, r_mob, r_heslo, r_kod]):
                        st.error("❗ Vyplňte všetky povinné polia.")
                    elif not validate_mobile(r_mob):
                        st.error("❗ Mobil musí byť v tvare 09XXXXXXXX.")
                    else:
                        with st.spinner("Vytváram účet..."):
                            res = call_script("register", {
                                "pobocka": r_pob, "meno": r_meno, "priezvisko": r_priez,
                                "adresa": r_adr, "mobil": r_mob, "heslo": r_heslo, "kod": r_kod
                            })
                            if res.get("status") == "success":
                                st.success("🎉 Registrácia úspešná! Teraz sa môžete prihlásiť.")
                            else:
                                st.error(f"Chyba: {res.get('message', 'Kód už existuje')}")

# --- 9. ČASŤ: DASHBOARD PO PRIHLÁSENÍ ---
else:
    user = st.session_state['user']
    
    # Sidebar detaily
    with st.sidebar:
        st.image("https://tepujem.sk/wp-content/uploads/2022/03/logo-tepujem-white.png", width=150)
        st.markdown(f"### 👤 {user['meno']} {user['priezvisko']}")
        st.info(f"📍 **Pobočka:** {user['pobocka']}\n\n🔑 **Rola:** {user['rola']}")
        st.write(f"⏱️ Naposledy aktualizované: {st.session_state['last_refresh']}")
        
        if st.button("🔄 Okamžitá aktualizácia"):
            st.rerun()
        
        st.divider()
        if st.button("🚪 Odhlásiť sa"):
            st.session_state['user'] = None
            st.rerun()

    # Načítanie dát
    df, users_df = get_full_data()

    if df.empty:
        st.warning("⚠️ V databáze sa nenachádzajú žiadne záznamy.")
    else:
        # --- ADMIN / SUPERADMIN SEKICA ---
        if user['rola'] in ['admin', 'superadmin']:
            st.title(f"📊 Manažérsky Dashboard - {user['pobocka']}")
            
            # Filtrovanie dát podľa pobočky
            if user['rola'] == 'superadmin':
                admin_df = df
            else:
                # Admin vidí zákazky svojej pobočky ALEBO tie, kde je jeho pobočka priradená partnerovi
                admin_df = df[(df['pobocka_id'] == user['pobocka']) | (df['partner_pobocka'] == user['pobocka'])]

            # KPI Metriky
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Celkový obrat", format_currency(admin_df['suma_zakazky'].sum()))
            m2.metric("Provízie na výplatu", format_currency(admin_df[~admin_df['vyplatene_bool']]['provizia_odporucatel'].sum()))
            m3.metric("Počet zákaziek", len(admin_df))
            m4.metric("Aktívni partneri", admin_df['kod_pouzity'].nunique())

            # Rozdelenie do tabov
            t_nac, t_vyp, t_stat = st.tabs(["🆕 Čaká na nacenenie", "💰 Výplatná listina", "📈 Štatistiky"])

            with t_nac:
                st.subheader("Nové zákazky (Suma 0 €)")
                to_price = admin_df[admin_df['suma_zakazky'] <= 0]
                if to_price.empty:
                    st.success("Všetko je nacenené. Dobrá práca!")
                else:
                    for idx, row in to_price.iterrows():
                        with st.expander(f"📍 {row['poznamka']} | Partner: {row.get('partner_meno', 'Neznámy')}"):
                            c_info, c_input = st.columns([2, 1])
                            with c_info:
                                st.write(f"**Dátum vytvorenia:** {row.get('datum', '---')}")
                                st.write(f"**Mobil partnera:** {row.get('partner_mobil', '---')}")
                            with c_input:
                                n_suma = st.number_input("Zadajte sumu zákazky", key=f"inp_{idx}", min_value=0.0, step=10.0)
                                if st.button("Potvrdiť cenu", key=f"btn_{idx}"):
                                    res = call_script("updateSuma", {
                                        "row_index": row['row_index'],
                                        "suma": n_suma,
                                        "admin_pobocka": user['pobocka']
                                    })
                                    if res.get("status") == "success":
                                        st.success("Suma bola úspešne aktualizovaná!")
                                        time.sleep(1)
                                        st.rerun()

            with t_vyp:
                st.subheader("Prehľad nevyplatených provízií")
                to_pay = admin_df[(admin_df['suma_zakazky'] > 0) & (~admin_df['vyplatene_bool'])]
                if to_pay.empty:
                    st.info("Momentálne nie sú žiadne provízie na vyplatenie.")
                else:
                    # Grupovanie podľa partnerov pre hromadnú výplatu
                    for partner_kod in to_pay['kod_pouzity'].unique():
                        p_subset = to_pay[to_pay['kod_pouzity'] == partner_kod]
                        p_meno = f"{p_subset['partner_meno'].iloc[0]} {p_subset['partner_priezvisko'].iloc[0]}"
                        total_p = p_subset['provizia_odporucatel'].sum()
                        
                        with st.container(border=True):
                            c_p1, c_p2 = st.columns([3, 1])
                            c_p1.markdown(f"**Partner:** {p_meno} (`{partner_kod}`)  \n**K výplate:** {format_currency(total_p)}")
                            if c_p2.button(f"Vyplatiť všetko", key=f"pay_{partner_kod}"):
                                with st.spinner("Zapisujem platby..."):
                                    for _, r in p_subset.iterrows():
                                        call_script("markAsPaid", {"row_index": r['row_index'], "admin_pobocka": user['pobocka']})
                                    st.success(f"Provízie pre {p_meno} boli vyrovnané.")
                                    time.sleep(1)
                                    st.rerun()
                            st.dataframe(p_subset[['datum', 'poznamka', 'suma_zakazky', 'provizia_odporucatel']], use_container_width=True)

            with t_stat:
                st.subheader("Analýza výkonu pobočky")
                fig = px.bar(admin_df, x='kod_pouzity', y='suma_zakazky', color='pobocka_id', 
                             title="Obrat podľa partnerov a miest", template="plotly_dark")
                st.plotly_chart(fig, use_container_width=True)

        # --- PARTNER SEKICA ---
        else:
            st.title(f"💰 Môj Provízny Prehľad")
            my_df = df[df['kod_pouzity'] == user['kod']]
            
            # Karty so štatistikami partnera
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Celkový zárobok", format_currency(my_df['provizia_odporucatel'].sum()))
            with c2:
                cakajuce = my_df[~my_df['vyplatene_bool']]['provizia_odporucatel'].sum()
                st.metric("Čaká na výplatu", format_currency(cakajuce), delta="K výplate", delta_color="normal")
            with c3:
                st.metric("Počet odporúčaní", len(my_df))

            st.divider()
            
            # Detailná tabuľka pre partnera
            st.subheader("História mojich odporúčaní")
            if my_df.empty:
                st.info("Zatiaľ ste neodoslali žiadne odporúčania. Keď niekoho odporučíte, uvidíte ho tu.")
            else:
                # Formátovanie tabuľky pre krásny výstup
                st.dataframe(
                    my_df[['datum', 'poznamka', 'suma_zakazky', 'provizia_odporucatel', 'vyplatene', 'pobocka_id']],
                    column_config={
                        "datum": "Dátum",
                        "poznamka": "Zákazník / Poznámka",
                        "suma_zakazky": st.column_config.NumberColumn("Suma zákazky", format="%.2f €"),
                        "provizia_odporucatel": st.column_config.NumberColumn("Moja Provízia", format="%.2f €"),
                        "vyplatene": st.column_config.CheckboxColumn("Vyplatené"),
                        "pobocka_id": "Miesto servisu"
                    },
                    use_container_width=True,
                    hide_index=True
                )

    # --- 10. FOOTER ---
    st.markdown("---")
    st.caption(f"© {datetime.now().year} TEPUJEM.SK Portál | Verzia 3.2.1-MASTER | Systém beží v cloude")
