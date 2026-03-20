import streamlit as st
import pandas as pd

# Nastavenie stránky
st.set_page_config(page_title="TEPUJEM - Portál", layout="centered")

# Funkcia na načítanie dát z Google Sheets (použijeme link zo Secrets)
def load_data(sheet_type="users"):
    url = st.secrets["gsheets_url_users"] if sheet_type == "users" else st.secrets["gsheets_url_zakazky"]
    csv_url = url.replace('/edit#gid=', '/export?format=csv&gid=')
    if '/edit' in csv_url:
        csv_url = csv_url.split('/edit')[0] + '/export?format=csv'
    return pd.read_csv(csv_url)

# --- STAV APLIKÁCIE (Login state) ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['user_data'] = None

# --- HLAVNÁ OBRAZOVKA (LOGIN / REGISTRÁCIA) ---
if not st.session_state['logged_in']:
    menu = ["Prihlásenie", "Registrácia nového zákazníka"]
    choice = st.sidebar.selectbox("Menu", menu)

    if choice == "Prihlásenie":
        st.subheader("Prihlásenie do profilu")
        login_id = st.text_input("Mobilné číslo alebo Login")
        password = st.text_input("Heslo", type='password')
        
        if st.button("Prihlásiť sa"):
            users_df = load_data("users")
            # Overenie (predpokladáme, že v stĺpci 'mobil' sú prihlasovacie mená)
            user = users_df[(users_df['mobil'].astype(str) == login_id) & (users_df['heslo'].astype(str) == password)]
            
            if not user.empty:
                st.session_state['logged_in'] = True
                st.session_state['user_data'] = user.iloc[0].to_dict()
                st.rerun()
            else:
                st.error("Nesprávne meno alebo heslo.")

    elif choice == "Registrácia nového zákazníka":
        st.subheader("Vytvorte si vlastný zľavový kód")
        with st.form("reg_form"):
            meno = st.text_input("Meno")
            priezvisko = st.text_input("Priezvisko")
            adresa = st.text_input("Adresa")
            mobil = st.text_input("Mobilné číslo")
            heslo = st.text_input("Zvoľte si heslo", type='password')
            navrhovany_kod = st.text_input("Váš unikátny zľavový kód (napr. PETO10)")
            
            submit = st.form_submit_button("Zaregistrovať sa")
            
            if submit:
                users_df = load_data("users")
                # Overenie, či kód už existuje
                if navrhovany_kod in users_df['referral_code'].values:
                    st.warning("Tento kód už niekto používa. Zvoľte si iný.")
                else:
                    st.success(f"Registrácia úspešná! Vaše údaje boli odoslané na spracovanie. Teraz sa môžete prihlásiť.")
                    # Tu by nasledoval zápis do Google Sheets (vyžaduje Service Account)
                    st.info("POZNÁMKA: Pre automatický zápis do tabuľky musíme prepojiť Service Account.")

# --- PROFIL PO PRIHLÁSENÍ ---
else:
    u = st.session_state['user_data']
    st.sidebar.button("Odhlásiť sa", on_click=lambda: st.session_state.update(logged_in=False))

    if u['rola'] == 'admin' or u['rola'] == 'pobocka':
        st.title(f"Admin Panel - Pobočka {u['meno']}")
        zakazky_df = load_data("zakazky")
        st.write("Prehľad všetkých zákazníkov a provízií:")
        st.dataframe(zakazky_df)
    
    else:
        st.title(f"Môj Profil: {u['meno']} {u['priezvisko']}")
        st.info(f"Váš zľavový kód: **{u['referral_code']}**")
        
        # Ukážeme zákazníkovi len jeho provízie
        zakazky_df = load_data("zakazky")
        moje_provizie = zakazky_df[zakazky_df['kod_pouzity'] == u['referral_code']]
        
        col1, col2 = st.columns(2)
        col1.metric("Počet odporúčaných zákaziek", len(moje_provizie))
        col2.metric("Zárobok celkom", f"{moje_provizie['provizia_odporucatel'].sum()} €")
        
        st.write("História vašich odporúčaní:")
        st.table(moje_provizie[['suma_zakazky', 'provizia_odporucatel']])
