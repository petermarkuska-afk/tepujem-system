import streamlit as st
import pandas as pd

st.set_page_config(page_title="Tepujem - Provízie", layout="wide")
st.title("💰 Provízny systém TEPUJEM")

def load_data():
    sheet_url = st.secrets["gsheets_url"]
    csv_url = sheet_url.replace('/edit#gid=', '/export?format=csv&gid=')
    if '/edit' in csv_url:
        csv_url = csv_url.split('/edit')[0] + '/export?format=csv'
    return pd.read_csv(csv_url)

pobocka_list = ["Nitra", "Trnava", "Bratislava", "Super Admin"]
auth = st.sidebar.selectbox("Vyberte pobočku:", pobocka_list)

try:
    df = load_data()
    
    # Ak je tabuľka prázdna, vytvoríme aspoň prázdny DataFrame so stĺpcami
    if df.empty:
        st.info("Tabuľka je momentálne prázdna. Čakám na nové zákazky z Make.com.")
    else:
        if auth == "Super Admin":
            st.subheader("Kompletný prehľad")
            st.dataframe(df)
        else:
            st.subheader(f"Zákazky: {auth}")
            filtered_df = df[df['pobocka_id'] == auth].copy()
            
            if filtered_df.empty:
                st.write("Žiadne zákazky na spracovanie.")
            else:
                st.write("Doplňte 'suma_zakazky' a systém dopočíta provízie:")
                # EDITOR: Tu admin mení sumu
                edited_df = st.data_editor(filtered_df)
                
                # VÝPOČET: 5% z každej sumy
                if st.button("Vypočítať a pripraviť na uloženie"):
                    edited_df['provizia_zakaznik'] = edited_df['suma_zakazky'] * 0.05
                    edited_df['provizia_odporucatel'] = edited_df['suma_zakazky'] * 0.05
                    st.write("Navrhované provízie (5% + 5%):")
                    st.dataframe(edited_df)
                    st.success("Provízie boli vypočítané. Pre uloženie do Google Sheets použite 'Copy-Paste' do vašej tabuľky.")

except Exception as e:
    st.error(f"Chyba: {e}")
