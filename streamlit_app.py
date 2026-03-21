import streamlit as st
import pandas as pd
import requests
import base64
import re
import time

# --- KONFIGURÁCIA STRÁNKY ---
st.set_page_config(
    page_title="TEPUJEM Portál", 
    page_icon="💰", 
    layout="centered"
)

# URL na Google Apps Script (Treba skontrolovať, či je správna)
SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzLxqt5QwUvu2zha5NEOg97-7NtPLTbhMd2YQ3ORV6YRny7SvMZwBSgVQ6Zyd3u9v-IKw/exec"

# --- POMOCNÉ FUNKCIE ---
def get_base64_of_bin_file(bin_file):
    """Načíta obrázok a prevedie ho na base64 pre CSS pozadie."""
    try:
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except FileNotFoundError:
        return None

def call_script(action, params=None):
    """Univerzálna funkcia pre komunikáciu s Google Sheets cez Apps Script."""
    if params is None:
        params = {}
    params['action'] = action
    try:
        response = requests.get(SCRIPT_URL, params=params, timeout=40)
        return response.json()
    except Exception as e:
        st.error(f"Chyba pripojenia k databáze: {e}")
        return {}

def validate_mobile(mob):
    """Validácia mobilného čísla: musí začínať na 09 a mať 10 číslic."""
    pattern = r'^09\d{8}$'
    return re.match(pattern, mob) is not None

# --- CACHE FUNKCIE PRE RÝCHLOSŤ ---
@st.cache_data(ttl=300)
def get_regions():
    res = call_script("getRegions")
    return res.get("regions", [])

@st.cache_data(ttl=300)
def get_data():
    """Načíta objednávky z transactions_data."""
    try:
        data = requests.get(f"{SCRIPT_URL}?action=getZakazky").json()
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

@st.cache_data(ttl=300)
def get_users():
    """Načíta užívateľov z users_data."""
    try:
        data = requests.get(f"{SCRIPT_URL}?action=getUsers").json()
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

# --- CSS ŠTÝLY (DARK MODE PRE KARTU) ---
img_base64 = get_base64_of_bin_file("image5.png")

css_style = """
<style>
/* Pozadie celej stránky */
[data-testid="stAppViewContainer"] {
    background-image: url("data:image/png;base64,REPLACE_ME");
    background-size: cover;
    background-position: center;
    background-attachment: fixed;
}
/* Tmavá clona pre čitateľnosť */
[data-testid="stAppViewContainer"]::before {
    content: "";
    position: absolute;
    top: 0; left: 0; width: 100%; height: 100%;
    background: rgba(0, 0, 0, 0.75); 
    pointer-events: none;
}
/* Hlavná karta obsahu */
[data-testid="stMainBlockContainer"] {
    max-width: 800px !important; 
    background-color: #1e1e1e !important; 
    padding: 40px !important;
    border-radius: 20px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.8);
    margin-top: 50px;
    color: white !important;
}
/* Vynútenie bielej farby textu v karte */
[data-testid="stMainBlockContainer"] *, label, h1, p, div { color: white !important; }

/* Štýl pre vstupné polia */
input { background-color: #333333 !important; color: white !important; border: 1px solid #555 !important; }

/* Štýl pre tlačidlá */
button { background-color: #444 !important; color: white !important; border: 1px solid #666 !important; }
</style>
"""
if img_base64:
    st.markdown(css_style.replace("REPLACE_ME", img_base64), unsafe_allow_html=True)

# --- HLAVNÝ PROGRAM ---
if 'user' not in st.session_state:
    st.session_state['user'] = None

# 1. ČASŤ: PRIHLÁSENIE A REGISTRÁCIA
if st.session_state['user'] is None:
    st.title("💰 Zarob si s TEPUJEM.SK")
    st.markdown("Vitajte v portáli. Prosím prihláste sa alebo sa zaregistrujte.")
    
    tab1, tab2 = st.tabs(["Prihlásenie", "Registrácia"])
    
    with tab1:
        with st.form("login_form"):
            m = st.text_input("Mobilné číslo (formát 09XXXXXXXX)")
            h = st.text_input("Heslo", type="password")
            if st.form_submit_button("Prihlásiť sa"):
                if not validate_mobile(m):
                    st.error("Mobilné číslo musí byť v tvare 09XXXXXXXX!")
                else:
                    res = call_script("login", {"mobil": m, "heslo": h})
                    if res.get("status") == "success":
                        st.session_state['user'] = res
                        st.rerun()
                    else:
                        st.error("Zlé údaje alebo chybný mobil.")

    with tab2:
        with st.form("register_form"):
            pob = st.selectbox("Vyber si svoj región (Pobočka)", get_regions())
            meno = st.text_input("Meno")
            priezvisko = st.text_input("Priezvisko")
            adresa = st.text_input("Adresa")
            mob = st.text_input("Mobilné číslo (formát 09XXXXXXXX)")
            hes = st.text_input("Heslo", type="password")
            kod = st.text_input("Kód (vlastný unikátny kód)")
            
            if st.form_submit_button("Registrovať"):
                if not validate_mobile(mob):
                    st.error("Mobilné číslo musí byť v tvare 09XXXXXXXX!")
                elif not all([meno, priezvisko, adresa, mob, hes, kod]):
                    st.warning("Vyplň všetky polia!")
                else:
                    # Zápis do Google Sheet
                    res = call_script("register", {
                        "pobocka": pob, 
                        "meno": meno, 
                        "priezvisko": priezvisko,
                        "adresa": adresa, 
                        "mobil": mob, 
                        "heslo": hes, 
                        "kod": kod
                    })
                    if res.get("status") == "success":
                        get_users.clear() 
                        st.success("Registrácia úspešná! Teraz sa môžete prihlásiť.")
                    else:
                        st.error("Chyba pri registrácii.")

# 2. ČASŤ: DASHBOARD PO PRIHLÁSENÍ
else:
    u = st.session_state['user']
    st.sidebar.title(f"👤 {u.get('meno')}")
    if st.sidebar.button("Odhlásiť"):
        st.session_state['user'] = None
        st.rerun()

    # Načítanie dát
    df = get_data()
    users = get_users()

    if df.empty:
        st.warning("Žiadne dáta v tabuľke zákaziek.")
        st.stop()

    # Čistenie dát
    df['suma_zakazky'] = pd.to_numeric(df['suma_zakazky'], errors='coerce').fillna(0)
    df['provizia_odporucatel'] = pd.to_numeric(df['provizia_odporucatel'], errors='coerce').fillna(0)
    df['vyplatene_bool'] = df['vyplatene'].astype(str).str.strip().str.upper() == "TRUE"

    # Prepojenie užívateľov (JOIN)
    # POZOR: Tu musíme používať presné názvy z Google Sheet
    if not users.empty:
        # Pomenujeme stĺpce tak, aby sme sa vyhli konfliktom
        users_clean = users.rename(columns={
            'referral_code': 'kod_pouzity',
            'meno': 'meno', # Ponecháme pre prehľad
            'priezvisko': 'priezvisko',
            'adresa': 'adresa',
            'mobil': 'mobil_partnera'
        })
        
        # Merge - spájame podľa kódu
        df = df.merge(
            users_clean[['kod_pouzity', 'meno', 'priezvisko', 'adresa', 'mobil_partnera']], 
            on='kod_pouzity', 
            how='left'
        )

    # --- ADMIN VIEW ---
    if u['rola'] in ['admin', 'superadmin']:
        st.title(f"📊 Správa - {u.get('pobocka_id')}")
        
        # Logika viditeľnosti: Admin vidí svoje objednávky ALEBO objednávky svojich partnerov
        if u['rola'] == 'superadmin':
            active_df = df
        else:
            # Tu predpokladáme, že 'pobocka_id' v transakciách zodpovedá názvu pobočky
            # A 'pobocka' v users_data je mesto
            active_df = df[(df['pobocka_id'] == u['pobocka_id']) | (df['pobocka_partnera'] == u['pobocka_id'])]

        t1, t2 = st.tabs(["Na nacenenie", "Na vyplatenie"])

        # TAB 1: NACENENIE
        with t1:
            nac = active_df[active_df['suma_zakazky'] <= 0]
            if nac.empty:
                st.success("Máte všetko nacenené! 👍")
            else:
                for i, row in nac.iterrows():
                    # Detailné info o partnerovi
                    m = row.get('meno', 'Priama')
                    p = row.get('priezvisko', '')
                    a = row.get('adresa', '---')
                    tel = row.get('mobil_partnera', '---')
                    
                    with st.expander(f"Zákazník: {row.get('poznamka')} | Partner: {m} {p}"):
                        st.markdown(f"**Partner:** {m} {p}")
                        st.markdown(f"**Adresa:** {a}")
                        st.markdown(f"**Telefón:** {tel}")
                        
                        suma = st.number_input("Suma €", key=f"s_{i}", min_value=0.0, step=1.0)
                        if st.button("Uložiť", key=f"b_{i}"):
                            call_script("updateSuma", {"row_index": row['row_index'], "suma": suma})
                            st.rerun()

        # TAB 2: VYPLATENIE
        with t2:
            pay = active_df[(active_df['suma_zakazky'] > 0) & (~active_df['vyplatene_bool'])]
            if pay.empty:
                st.info("Nič na vyplatenie.")
            else:
                # Unikátni partneri
                partners = pay['kod_pouzity'].dropna().unique()
                for kod in partners:
                    p_data = pay[pay['kod_pouzity'] == kod]
                    m = p_data['meno'].iloc[0]
                    p = p_data['priezvisko'].iloc[0]
                    tel = p_data['mobil_partnera'].iloc[0]
                    adr = p_data['adresa'].iloc[0]
                    
                    with st.expander(f"Partner: {m} {p} | Tel: {tel} | Spolu: {p_data['provizia_odporucatel'].sum():.2f} €"):
                        st.markdown(f"**Adresa:** {adr}")
                        disp = p_data[['poznamka', 'provizia_odporucatel', 'pobocka_id']].copy()
                        disp.columns = ['Poznámka', 'Provízia', 'Mesto']
                        st.table(disp)
                        
                        if st.button("Označiť všetko ako vyplatené", key=f"pay_{kod}"):
                            for _, r in p_data.iterrows():
                                call_script("markAsPaid", {"row_index": r['row_index']})
                            st.rerun()

    # --- PARTNER VIEW ---
    else:
        st.title("💰 Môj prehľad")
        my_df = df[df['kod_pouzity'] == u['kod']]
        
        col1, col2 = st.columns(2)
        col1.metric("Zarobené celkovo", f"{my_df['provizia_odporucatel'].sum():.2f} €")
        col2.metric("Čaká na výplatu", f"{my_df[~my_df['vyplatene_bool']]['provizia_odporucatel'].sum():.2f} €")
        
        if not my_df.empty:
            display_df = my_df[['poznamka', 'provizia_odporucatel', 'vyplatene', 'pobocka_id']].copy()
            display_df.columns = ['Poznámka', 'Zárobok', 'Vyplatené', 'Mesto']
            st.table(display_df)
