import streamlit as st
import pandas as pd
import gspread

st.set_page_config(page_title="Tepujem - Provízie", layout="wide")
st.title("💰 Provízny systém TEPUJEM")

# Funkcia na načítanie dát cez verejný link (najjednoduchšia cesta)
def load_data():
    # Sem vložíš tvoj link na tabuľku, ale musí byť upravený na export
    # Ak je tvoj link https://docs.google.com/spreadsheets/d/ABC/edit, 
    # tak csv_url bude https://docs.google.com/spreadsheets/d/ABC/export?format=csv
    sheet_url = st.secrets["gsheets_url"]
    csv_url = sheet_url.replace('/edit#gid=', '/export?format=csv&gid=')
    if '/edit' in csv_url:
        csv_url = csv_url.split('/edit')[0] + '/export?format=csv'
    
    return pd.read_csv(csv_url)

# Menu pre pobočky
pobocka_list = ["Nitra", "Trnava", "Bratislava", "Super Admin"]
auth = st.sidebar.selectbox("Vyberte pobočku:", pobocka_list)

try:
    df = load_data()

    if auth == "Super Admin":
        st.subheader("Kompletný prehľad")
        st.dataframe(df)
    else:
        st.subheader(f"Zákazky: {auth}")
        # Hľadáme stĺpec pobocka_id
        col_name = 'pobocka_id' 
        if col_name in df.columns:
            filtered_df = df[df[col_name] == auth]
            st.data_editor(filtered_df)
        else:
            st.error(f"V tabuľke nevidím stĺpec '{col_name}'. Máš ho v prvom riadku?")

except Exception as e:
    st.info("Čakám na správne prepojenie s Google Sheets...")
    st.write(f"Technický detail: {e}")
