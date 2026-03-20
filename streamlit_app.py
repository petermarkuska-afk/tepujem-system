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
    try:
        url = f"{SCRIPT_URL}?action={action}"
        for k, v in params.items(): url += f"&{k}={v}"
        res = requests.get(url, timeout=10).json()
        return res.get("status") == "success"
    except: return False

# --- 2. PRIHLASOVANIE ---
if st.session_state['user'] is None:
    st.title("💰 Provízny systém TEPUJEM")
    m = st.text_input("Mobil (prihlasovacie meno)").strip()
    h = st.text_input("Heslo", type="password").strip()
    if st.button("Prihlásiť sa", use_container_width=True):
        try:
            res = requests.get(f"{SCRIPT_URL}?action=login&mobil={m}&heslo={h}", timeout=15).json()
            if res.get("status") == "success":
                st.session_state['user'] = res
                st.rerun()
            else: st.error("Nesprávne údaje.")
        except: st.error("Chyba pripojenia.")

# --- 3. DASHBOARD ---
else:
    u = st.session_state['user']
    st.sidebar.title(f"👤 {u.get('meno', 'Užívateľ')}")
    st.sidebar.info(f"Región: {u.get('pobocka_id', 'Celá SR')}")
    if st.sidebar.button("Odhlásiť sa"):
        st.session_state['user'] = None
        st.rerun()

    try:
        # Načítanie dát a základné spracovanie
        resp = requests.get(f"{SCRIPT_URL}?action=getZakazky", timeout=15)
        df = pd.DataFrame(resp.json())
        if df.empty:
            st.info("Databáza je prázdna.")
            st.stop()

        for col in ['suma_zakazky', 'provizia_odporucatel']:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        
        df['vyplatene_bool'] = df['vyplatene'].astype(str).str.upper() == 'TRUE'
        df['Stav'] = df['vyplatene_bool'].apply(lambda x: "✅ Vyplatené" if x else "⏳ Čaká")

        # --- ROZHRANIE: ADMIN (Pobočka) & SUPERADMIN ---
        if u['rola'] in ['admin', 'superadmin']:
            st.title(f"📊 Správa výplat - {u.get('pobocka_id', 'Liptov')}")
            
            # Filtrovanie pre lokálneho admina
            if u['rola'] == 'admin':
                view_df = df[df['pobocka_id'] == u['pobocka_id']]
            else:
                view_df = df # Superadmin vidí všetko

            # Zoznam unikátnych partnerov, ktorí majú niečo na vyplatenie
            cakajuce_df = view_df[~view_df['vyplatene_bool']]
            
            if cakajuce_df.empty:
                st.success("Všetky provízie v tomto regióne sú vyplatené.")
            else:
                st.subheader("💳 Aktuálne požiadavky na vyplatenie")
                
                # Zoskupenie podľa partnera pre kumulatívny prehľad
                partneri = cakajuce_df.groupby('kod_pouzity').agg({
                    'provizia_odporucatel': 'sum',
                    'partner_meno': 'first'
                }).reset_index()

                for _, p in partneri.iterrows():
                    with st.expander(f"👤 {p['partner_meno']} ({p['kod_pouzity']}) - Spolu k úhrade: {p['provizia_odporucatel']:.2f} €"):
                        p_detail = cakajuce_df[cakajuce_df['kod_pouzity'] == p['kod_pouzity']]
                        
                        # Zobrazenie detailných zákaziek pre tohto partnera
                        st.table(p_detail[['poznamka', 'provizia_odporucatel', 'Stav']].rename(columns={
                            'poznamka': 'Zákazka / Kontakt',
                            'provizia_odporucatel': 'Suma'
                        }))
                        
                        if st.button(f"Označiť VŠETKO ako vyplatené pre {p['kod_pouzity']}", key=f"pay_{p['kod_pouzity']}"):
                            for idx in p_detail['row_index']:
                                call_script("markAsPaid", {"row_index": idx})
                            st.success(f"Platba pre {p['partner_meno']} bola zaevidovaná.")
                            time.sleep(1)
                            st.rerun()

            if u['rola'] == 'superadmin':
                st.divider()
                st.subheader("🌎 Globálny prehľad (všetky regióny)")
                st.dataframe(df[['pobocka_id', 'partner_meno', 'provizia_odporucatel', 'Stav', 'poznamka']], use_container_width=True)

        # --- ROZHRANIE: PARTNER (Zákazník) ---
        else:
            st.title(f"💰 Váš partnerský prehľad ({u.get('kod', '---')})")
            my_df = df[df['kod_pouzity'] == u['kod']].copy()
            
            c1, c2 = st.columns(2)
            c1.metric("Získané celkovo", f"{my_df['provizia_odporucatel'].sum():.2f} €")
            cakajuce = my_df[~my_df['vyplatene_bool']]['provizia_odporucatel'].sum()
            c2.metric("Aktuálne na vyplatenie", f"{cakajuce:.2f} €")
            
            st.subheader("Zoznam vašich odporúčaní")
            st.table(my_df[['poznamka', 'provizia_odporucatel', 'Stav']].rename(columns={
                'poznamka': 'Objednávka',
                'provizia_odporucatel': 'Získaná provízia'
            }))

    except Exception as e:
        st.error(f"Nepodarilo sa načítať dáta.")
