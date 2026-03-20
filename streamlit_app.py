import streamlit as st
import pandas as pd
import requests
import time

# --- 1. KONFIGURÁCIA ---
SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzLxqt5QwUvu2zha5NEOg97-7NtPLTbhMd2YQ3ORV6YRny7SvMZwBSgVQ6Zyd3u9v-IKw/exec"

st.set_page_config(page_title="TEPUJEM Portál", page_icon="💰", layout="wide")

if 'user' not in st.session_state:
    st.session_state['user'] = None

def call_script(action, params):
    # Retry logika pre elimináciu nutnosti klikať dvakrát
    for _ in range(3):
        try:
            url = f"{SCRIPT_URL}?action={action}"
            for k, v in params.items(): url += f"&{k}={v}"
            res = requests.get(url, timeout=15).json()
            return res if action in ["login", "register"] else (res.get("status") == "success")
        except:
            time.sleep(1.5)
    return None

# --- 2. VSTUPNÁ OBRAZOVKA ---
if st.session_state['user'] is None:
    st.title("💰 Provízny systém TEPUJEM")
    tab1, tab2 = st.tabs(["Prihlásenie", "Registrácia nového partnera"])

    with tab1:
        m = st.text_input("Mobil (prihlasovacie meno)", key="L_MOB").strip()
        h = st.text_input("Heslo", type="password", key="L_HES").strip()
        if st.button("Prihlásiť sa", use_container_width=True):
            with st.spinner("Pripájanie..."):
                res = call_script("login", {"mobil": m, "heslo": h})
                if res and res.get("status") == "success":
                    st.session_state['user'] = res
                    st.success("Prihlásenie úspešné!")
                    time.sleep(1)
                    st.rerun()
                elif res and res.get("status") == "error":
                    st.error("Nesprávne údaje.")
                else:
                    st.error("Server neodpovedá, skúste to o moment znova.")

    with tab2:
        st.subheader("Registrácia do systému")
        # Pridaný výber pobočky, ktorý určí, ktorému Adminovi sa zákazník zobrazí
        reg_pobocka = st.selectbox("Priradiť k pobočke", ["Bratislava", "Liptov", "Iné"])
        reg_meno = st.text_input("Meno a priezvisko")
        reg_mobil = st.text_input("Mobil (ako prihlasovacie meno)")
        reg_heslo = st.text_input("Heslo (aspoň 6 znakov)", type="password")
        reg_kod = st.text_input("Váš unikátny kód (napr. JOZO10)")

        if st.button("Vytvoriť partnerský účet", use_container_width=True):
            if not reg_meno or not reg_mobil or len(reg_heslo) < 6 or not reg_kod:
                st.warning("Vyplňte prosím všetky údaje správne.")
            else:
                with st.spinner("Registrujem..."):
                    res = call_script("register", {
                        "meno": reg_meno, "mobil": reg_mobil, 
                        "heslo": reg_heslo, "kod": reg_kod, "pobocka": reg_pobocka
                    })
                    if res and res.get("status") == "success":
                        st.success(f"Registrácia pre pobočku {reg_pobocka} úspešná! Môžete sa prihlásiť.")
                    else:
                        st.error("Chyba. Mobil alebo kód už možno existuje.")

# --- 3. DASHBOARD ---
else:
    u = st.session_state['user']
    st.sidebar.title(f"👤 {u.get('meno', 'Užívateľ')}")
    st.sidebar.info(f"Rola: {u['rola'].upper()} | Región: {u.get('pobocka_id', 'LIPTOV')}")
    
    if st.sidebar.button("Odhlásiť sa", use_container_width=True):
        st.session_state['user'] = None
        st.rerun()

    try:
        resp = requests.get(f"{SCRIPT_URL}?action=getZakazky", timeout=20)
        df = pd.DataFrame(resp.json())
        
        if df.empty:
            st.info("Zatiaľ žiadne záznamy.")
            st.stop()

        df['suma_zakazky'] = pd.to_numeric(df['suma_zakazky'], errors='coerce').fillna(0.0)
        df['provizia_odporucatel'] = pd.to_numeric(df['provizia_odporucatel'], errors='coerce').fillna(0.0)
        df['vyplatene_bool'] = df['vyplatene'].astype(str).str.upper() == 'TRUE'
        df['Stav'] = df['vyplatene_bool'].apply(lambda x: "Vyplatené ✅" if x else "Čaká ⏳")

        # --- ADMIN / SUPERADMIN LOGIKA ---
        if u['rola'] in ['admin', 'superadmin']:
            st.title(f"📊 Portál správy - {u.get('pobocka_id', 'LIPTOV')}")
            
            # Tu sa deje to magické priraďovanie podľa pobočky z registrácie
            active_df = df if u['rola'] == 'superadmin' else df[df['pobocka_id'] == u['pobocka_id']]

            # 1. ČASŤ: NACENENIE
            st.subheader("📩 Nové zákazky na nacenenie")
            k_naceneniu = active_df[active_df['suma_zakazky'] <= 0]
            if not k_naceneniu.empty:
                for i, row in k_naceneniu.iterrows():
                    with st.expander(f"📍 {row['pobocka_id']} | Naceniť: {row['poznamka']}"):
                        nova_suma = st.number_input(f"Suma (€) - Kód: {row['kod_pouzity']}", key=f"s_{i}", min_value=0.0)
                        if st.button("Uložiť a vypočítať", key=f"b_{i}"):
                            if call_script("updateSuma", {"row_index": row['row_index'], "suma": nova_suma}):
                                st.rerun()
            else: st.write("Žiadne nové dopyty.")

            st.divider()

            # 2. ČASŤ: VÝPLATY PODĽA ZÍSKATEĽOV
            st.subheader("💳 Kumulatívne výplaty")
            k_vyplate = active_df[(active_df['suma_zakazky'] > 0) & (~active_df['vyplatene_bool'])]
            
            if not k_vyplate.empty:
                for p_kod in k_vyplate['kod_pouzity'].unique():
                    p_data = k_vyplate[k_vyplate['kod_pouzity'] == p_kod]
                    suma_celkom = p_data['provizia_odporucatel'].sum()
                    
                    with st.expander(f"👤 {p_data['partner_meno'].iloc[0]} ({p_kod}) | Spolu: **{suma_celkom:.2f} €**"):
                        st.table(p_data[['poznamka', 'provizia_odporucatel', 'Stav']].rename(columns={
                            'poznamka': 'Zákazník', 'provizia_odporucatel': 'Suma (€)'
                        }))
                        if st.button(f"Potvrdiť vyplatenie pre {p_kod}", key=f"all_{p_kod}"):
                            for idx in p_data['row_index']:
                                call_script("markAsPaid", {"row_index": idx})
                            st.rerun()
            else: st.success("Všetko v tomto regióne je vyplatené.")

        # --- PARTNER LOGIKA ---
        else:
            st.title(f"💰 Váš prehľad ({u.get('kod', '---')})")
            my_df = df[df['kod_pouzity'] == u['kod']].copy()
            c1, c2 = st.columns(2)
            c1.metric("Zárobok celkovo", f"{my_df['provizia_odporucatel'].sum():.2f} €")
            cakajuce = my_df[~my_df['vyplatene_bool']]['provizia_odporucatel'].sum()
            c2.metric("Na vyplatenie", f"{cakajuce:.2f} €")
            
            st.table(my_df[['poznamka', 'provizia_odporucatel', 'Stav']].rename(columns={
                'poznamka': 'Zákazka', 'provizia_odporucatel': 'Provízia', 'Stav': 'Status'
            }))

    except:
        st.error("Chyba pri načítaní dát.")
