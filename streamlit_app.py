import streamlit as st
import pandas as pd
import requests

# --- KONFIGURÁCIA ---
# Použi tvoju najnovšiu URL z Google Apps Scriptu (po poslednom DEPLOY)
SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyjAB40A4smgumuldfN34harY1TkudIYTTglikbci9PvC1XLxKCUftvQulqtW65Y8-4Bg/exec"

st.set_page_config(page_title="TEPUJEM Portál", page_icon="💰", layout="wide")

if 'user' not in st.session_state:
    st.session_state['user'] = None

# --- POMOCNÉ FUNKCIE ---
def update_suma(row_index, nova_suma):
    """Odošle novú sumu do Google Scriptu"""
    try:
        url = f"{SCRIPT_URL}?action=updateSuma&row_index={row_index}&suma={nova_suma}"
        r = requests.get(url, timeout=10).json()
        return r.get("status") == "success"
    except:
        return False

# --- PRIHLASOVANIE ---
if st.session_state['user'] is None:
    st.title("💰 Provízny systém TEPUJEM")
    tab1, tab2 = st.tabs(["Prihlásenie", "Registrácia"])
    
    with tab1:
        m = st.text_input("Mobil (login)").strip()
        h = st.text_input("Heslo", type="password").strip()
        if st.button("Prihlásiť sa"):
            try:
                # Upravené: Skript teraz vracia 'pobocka_id' namiesto 'meno' pre Adminov
                r = requests.get(f"{SCRIPT_URL}?action=login&mobil={m}&heslo={h}", timeout=10).json()
                if r["status"] == "success":
                    st.session_state['user'] = r
                    st.rerun()
                else: st.error("Nesprávne údaje.")
            except: st.error("Nepodarilo sa pripojiť k databáze.")
            
    with tab2:
        with st.form("reg"):
            meno = st.text_input("Meno"); prie = st.text_input("Priezvisko")
            mob = st.text_input("Mobil"); hes = st.text_input("Heslo")
            kod = st.text_input("Váš kód (napr. JOZO10)")
            if st.form_submit_button("Vytvoriť účet"):
                requests.post(SCRIPT_URL, json={"target": "user", "meno": meno, "priezvisko": prie, "adresa": "", "mobil": mob, "heslo": hes, "referral_code": kod})
                st.success("Registrácia úspešná, teraz sa prihláste.")

# --- DASHBOARD ---
else:
    u = st.session_state['user']
    # Ak je to admin, zobrazíme názov pobočky (napr. NITRA)
    user_label = u.get('pobocka_id', u.get('meno', 'Užívateľ'))
    st.sidebar.title(f"👤 {user_label}")
    st.sidebar.write(f"Rola: {u['rola'].upper()}")
    
    if st.sidebar.button("Odhlásiť sa"):
        st.session_state['user'] = None
        st.rerun()

    try:
        res = requests.get(f"{SCRIPT_URL}?action=getZakazky", timeout=10)
        df = pd.DataFrame(res.json())
        
        if not df.empty:
            # Prevod stĺpcov na čísla
            for col in ['suma_zakazky', 'provizia_odporucatel', 'zlava_novy']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # --- A. SUPERADMIN (Peter) ---
        if u['rola'] == 'superadmin':
            st.title("🌍 Globálny prehľad (Superadmin)")
            
            # Štatistiky navrchu
            c1, c2, c3 = st.columns(3)
            c1.metric("Celkový obrat", f"{df['suma_zakazky'].sum():.2f} €")
            c2.metric("Počet zákaziek", len(df))
            c3.metric("Vyplatené provízie", f"{df['provizia_odporucatel'].sum():.2f} €")
            
            st.subheader("Detailná tabuľka všetkých pohybov")
            st.dataframe(df, use_container_width=True)

            # ZGURUPOVANIE PROVÍZIÍ PODĽA ODPORÚČATEĽOV
            st.divider()
            st.subheader("📊 Provízie podľa odporúčateľov")
            if not df.empty:
                odporucatel_df = df.groupby('kod_pouzity').agg({
                    'suma_zakazky': 'sum',
                    'provizia_odporucatel': 'sum',
                    'pobocka_id': 'count'
                }).reset_index()
                odporucatel_df.columns = ['Kód odporúčateľa', 'Obrat (€)', 'Provízia (€)', 'Počet prinesených ľudí']
                st.table(odporucatel_df)

        # --- B. ADMIN (Regionálne pobočky: NITRA, LIPTOV...) ---
        elif u['rola'] == 'admin':
            # Admin filtruje podľa svojho pobocka_id (stĺpec A v users_data)
            moje_mesto = u['pobocka_id']
            st.title(f"📍 Konzola pobočky: {moje_mesto}")
            
            f_df = df[df['pobocka_id'].astype(str) == str(moje_mesto)].copy()
            
            if f_df.empty:
                st.info("Zatiaľ nemáte pridelené žiadne objednávky.")
            else:
                # Rozdelenie na nové a vybavené
                nove = f_df[f_df['suma_zakazky'] == 0]
                vybavene = f_df[f_df['suma_zakazky'] > 0]
                
                st.subheader("📩 Nové objednávky na vybavenie")
                if nove.empty:
                    st.success("Všetky objednávky majú priradenú sumu.")
                else:
                    for i, row in nove.iterrows():
                        with st.expander(f"Objednávka: {row['kod_pouzity']} | Info: {row['poznamka']}"):
                            col_a, col_b = st.columns([2, 1])
                            nova_s = col_a.number_input(f"Zadaj sumu za tepovanie (€)", key=f"in_{i}", min_value=0.0, step=1.0)
                            if col_b.button("✅ Uložiť sumu", key=f"btn_{i}"):
                                if update_suma(row['row_index'], nova_s):
                                    st.success("Uložené!")
                                    st.rerun()
                                else:
                                    st.error("Chyba pri zápise.")

                st.subheader("✅ História vybavených zakázok")
                st.dataframe(vybavene[['kod_pouzity', 'suma_zakazky', 'provizia_odporucatel', 'poznamka']], use_container_width=True)

        # --- C. ZÁKAZNÍK (Partner) ---
        else:
            st.title(f"💰 Váš partnerský účet ({u['kod']})")
            my_df = df[df['kod_pouzity'].astype(str) == str(u['kod'])]
            
            c1, c2 = st.columns(2)
            c1.metric("Váš doterajší zárobok", f"{my_df['provizia_odporucatel'].sum():.2f} €")
            c2.metric("Počet odporúčaní", len(my_df))
            
            st.subheader("Prehľad vašich odporúčaní")
            if not my_df.empty:
                st.table(my_df[['pobocka_id', 'suma_zakazky', 'provizia_odporucatel']])
            else:
                st.info("Zatiaľ ste nikoho neodporučili. Váš kód je: " + u['kod'])

    except Exception as e:
        st.error(f"Chyba pri načítaní dát: {e}")
