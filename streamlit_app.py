import streamlit as st
import pandas as pd
import requests
import base64
import re
import time
from datetime import datetime

# --- 1. KONFIGURÁCIA ---
st.set_page_config(
    page_title="TEPUJEM Portál", 
    page_icon="💰", 
    layout="centered"
)

# URL na tvoj Google Apps Script
SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzLxqt5QwUvu2zha5NEOg97-7NtPLTbhMd2YQ3ORV6YRny7SvMZwBSgVQ6Zyd3u9v-IKw/exec"

# --- 2. POMOCNÉ FUNKCIE ---
def get_base64_of_bin_file(bin_file):
    """Načítanie obrázka pre pozadie do base64."""
    try:
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except FileNotFoundError:
        return None

def call_script(action, params=None):
    """Robustné volanie API s ošetrením chýb."""
    if params is None:
        params = {}
    params['action'] = action
    
    try:
        params['t'] = str(int(time.time()))
        response = requests.get(SCRIPT_URL, params=params, timeout=45)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Chyba servera: {response.status_code}")
            return {}
    except Exception as e:
        st.error(f"Nepodarilo sa spojiť s databázou: {e}")
        return {}

def validate_mobile(mob):
    """Validácia slovenského mobilného formátu."""
    pattern = r'^09\d{8}$'
    return re.match(pattern, mob) is not None

# --- 3. DÁTOVÉ FUNKCIE S CACHE (Ochrana pred preťažením) ---
@st.cache_data(ttl=600)
def get_regions_cached():
    res = call_script("getRegions")
    return res.get("regions", [])

@st.cache_data(ttl=300)
def get_data_cached():
    try:
        response = requests.get(f"{SCRIPT_URL}?action=getZakazky", timeout=35)
        return pd.DataFrame(response.json())
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=300)
def get_users_cached():
    try:
        response = requests.get(f"{SCRIPT_URL}?action=getUsers", timeout=35)
        return pd.DataFrame(response.json())
    except Exception:
        return pd.DataFrame()

# --- 4. CSS ŠTÝLY ---
img_base64 = get_base64_of_bin_file("image5.png")
css_style = """
<style>
[data-testid="stAppViewContainer"] {
    background-image: url("data:image/png;base64,REPLACE_ME");
    background-size: cover;
    background-position: center;
    background-attachment: fixed;
}
[data-testid="stAppViewContainer"]::before {
    content: "";
    position: absolute;
    top: 0; left: 0; width: 100%; height: 100%;
    background: rgba(0, 0, 0, 0.75); 
    pointer-events: none;
}
[data-testid="stMainBlockContainer"] {
    max-width: 800px !important; 
    background-color: #1e1e1e !important; 
    padding: 40px !important;
    border-radius: 20px;
    box-shadow: 0 4px 25px rgba(0,0,0,0.9);
    margin-top: 50px;
    color: white !important;
}
[data-testid="stMainBlockContainer"] *, label, h1, p, div { color: white !important; }
.stMetric { background: rgba(255,255,255,0.07); padding: 15px; border-radius: 12px; border: 1px solid #444; }
input { background-color: #2b2b2b !important; color: white !important; border: 1px solid #555 !important; }
button { background-color: #3e3e3e !important; color: white !important; border-radius: 8px !important; }
div[data-testid="stExpander"] { background-color: rgba(255,255,255,0.03); border-radius: 10px; }
</style>
"""
if img_base64:
    st.markdown(css_style.replace("REPLACE_ME", img_base64), unsafe_allow_html=True)

# --- 5. LOGIKA APLIKÁCIE ---
if 'user' not in st.session_state:
    st.session_state['user'] = None

if st.session_state['user'] is None:
    st.title("💰 Zarob si s TEPUJEM.SK")
    t1, t2 = st.tabs(["Prihlásenie", "Registrácia"])
    
    with t1:
        with st.form("login_form"):
            m = st.text_input("Mobilné číslo (09XXXXXXXX)")
            h = st.text_input("Heslo", type="password")
            if st.form_submit_button("Vstúpiť do portálu"):
                if validate_mobile(m):
                    res = call_script("login", {"mobil": m, "heslo": h})
                    if res.get("status") == "success":
                        st.session_state['user'] = res
                        st.rerun()
                    else: st.error("Nesprávne prihlasovacie údaje.")
                else: st.error("Zadajte platné mobilné číslo!")

    with t2:
        with st.form("register_form"):
            pob = st.selectbox("Vyberte pobočku pre priradenie", get_regions_cached())
            meno = st.text_input("Meno")
            priezvisko = st.text_input("Priezvisko")
            mob = st.text_input("Mobil (09XXXXXXXX)")
            hes = st.text_input("Heslo", type="password")
            v_kod = st.text_input("Váš unikátny kód (pre zákazníkov)")
            if st.form_submit_button("Vytvoriť účet"):
                if not validate_mobile(mob): st.error("Mobil musí byť v tvare 09XXXXXXXX!")
                elif not all([meno, priezvisko, mob, hes, v_kod]): st.warning("Všetky polia sú povinné!")
                else:
                    res = call_script("register", {"pobocka": pob, "meno": meno, "priezvisko": priezvisko, "mobil": mob, "heslo": hes, "kod": v_kod})
                    if res.get("status") == "success": st.success("Registrácia prebehla úspešne!")
                    else: st.error("Chyba pri registrácii.")

else:
    u = st.session_state['user']
    st.sidebar.title(f"👤 {u.get('meno', 'Užívateľ')}")
    st.sidebar.info(f"Rola: {u.get('rola', 'Partner').capitalize()}")
    
    if st.sidebar.button("🔄 Aktualizovať dáta"):
        st.cache_data.clear()
        st.rerun()
    if st.sidebar.button("Odhlásiť sa"):
        st.session_state['user'] = None
        st.cache_data.clear()
        st.rerun()

    df = get_data_cached()
    users = get_users_cached()

    if df.empty:
        st.warning("V systéme zatiaľ nie sú žiadne zákazky.")
        st.stop()

    df['suma_zakazky'] = pd.to_numeric(df['suma_zakazky'], errors='coerce').fillna(0)
    df['provizia_odporucatel'] = pd.to_numeric(df['provizia_odporucatel'], errors='coerce').fillna(0)
    df['vyplatene_bool'] = df['vyplatene'].astype(str).str.strip().str.upper() == "TRUE"

    # MERGE: Pripájame dáta o partneroch VRÁTANE pobočky pre interné filtrovanie
    if not users.empty:
        u_map = users.rename(columns={'referral_code': 'kod_pouzity', 'mobil': 'mob_P', 'meno': 'meno_P', 'priezvisko': 'priez_P', 'pobocka': 'pobocka_partnera'})
        df = df.merge(u_map[['kod_pouzity', 'meno_P', 'priez_P', 'mob_P', 'pobocka_partnera']], on='kod_pouzity', how='left')

    # --- ADMIN VIEW ---
    if u['rola'] in ['admin', 'superadmin']:
        st.title(f"📊 Správa - {u.get('pobocka')}")
        
        # Interné filtrovanie: Admin vidí partnerov, ktorí spadajú pod jeho pobočku
        active_df = df if u['rola'] == 'superadmin' else df[df['pobocka_partnera'] == u['pobocka']]

        m1, m2, m3 = st.columns(3)
        m1.metric("Nové zákazky", len(active_df[active_df['suma_zakazky'] <= 0]))
        m2.metric("Na výplatu", f"{active_df[(active_df['suma_zakazky'] > 0) & (~active_df['vyplatene_bool'])]['provizia_odporucatel'].sum():.2f} €")
        m3.metric("Celkový obrat", f"{active_df['suma_zakazky'].sum():.0f} €")

        tab_n, tab_v = st.tabs(["📝 Nacenenie", "💰 Výplaty provízií"])

        with tab_n:
            nacenit = active_df[active_df['suma_zakazky'] <= 0]
            if nacenit.empty: st.success("Všetky zákazky sú nacenené.")
            else:
                for idx, r in nacenit.iterrows():
                    # Zobrazenie popisu: Mesto (zo zákazky), Kód použitý a Poznámka
                    m_val = r.get('mesto', '---')
                    k_val = r.get('kod_pouzity', '---')
                    p_val = r.get('poznamka', 'Bez poznámky')
                    
                    with st.expander(f"📍 {m_val} | Kód: {k_val} | {p_val}"):
                        st.write(f"**Partner:** {r.get('meno_P', 'Neznámy')} {r.get('priez_P', '')} ({r.get('mob_P', '-')})")
                        val = st.number_input("Suma za prácu (€)", key=f"inp_{idx}", min_value=0.0, step=1.0)
                        if st.button("Uložiť cenu", key=f"btn_{idx}"):
                            call_script("updateSuma", {"row_index": str(r['row_index']), "suma": str(val)})
                            st.cache_data.clear()
                            st.rerun()

        with tab_v:
            nevyplatene = active_df[(active_df['suma_zakazky'] > 0) & (~active_df['vyplatene_bool'])]
            if nevyplatene.empty: st.info("Žiadne provízie nečakajú na vyplatenie.")
            else:
                for k in nevyplatene['kod_pouzity'].unique():
                    p_rows = nevyplatene[nevyplatene['kod_pouzity'] == k]
                    p_label = f"{p_rows['meno_P'].iloc[0]} {p_rows['priez_P'].iloc[0]} ({p_rows['mob_P'].iloc[0]})"
                    with st.expander(f"👤 {p_label} | Suma: {p_rows['provizia_odporucatel'].sum():.2f} €"):
                        st.dataframe(p_rows[['mesto', 'poznamka', 'provizia_odporucatel']], use_container_width=True)
                        if st.button(f"Označiť ako vyplatené ({k})", key=f"pay_{k}"):
                            for _, row_to_pay in p_rows.iterrows():
                                call_script("markAsPaid", {"row_index": str(row_to_pay['row_index'])})
                            st.cache_data.clear()
                            st.rerun()

    # --- PARTNER VIEW ---
    else:
        st.title("💰 Moje Provízie")
        my_data = df[df['kod_pouzity'] == u['kod']]
        c1, c2 = st.columns(2)
        c1.metric("Zaplatené", f"{my_data[my_data['vyplatene_bool']]['provizia_odporucatel'].sum():.2f} €")
        c2.metric("Čaká na výplatu", f"{my_data[~my_data['vyplatene_bool']]['provizia_odporucatel'].sum():.2f} €")
        
        if not my_data.empty:
            st.subheader("Prehľad mojich zákaziek")
            display_df = my_data[['mesto', 'poznamka', 'provizia_odporucatel', 'vyplatene']].copy()
            display_df.columns = ['Mesto', 'Popis', 'Moja provízia (€)', 'Stav výplaty']
            st.dataframe(display_df, use_container_width=True, hide_index=True)
        else: st.info("Zatiaľ nemáte žiadne evidované zákazky.")
