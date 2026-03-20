import streamlit as st
from st_gsheets_connection import GSheetsConnection

st.set_page_config(page_title="Tepujem - Provízie", layout="wide")

st.title("💰 Provízny systém TEPUJEM")

# Pripojenie na Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# Menu pre pobočky
pobocka_list = ["Nitra", "Trnava", "Bratislava", "Super Admin"]
auth = st.sidebar.selectbox("Vyberte pobočku / Rola:", pobocka_list)

try:
    # Načítanie dát (URL vložíme neskôr do Streamlit Secrets)
    df = conn.read(spreadsheet=st.secrets["gsheets_url"], ttl=0)

    if auth == "Super Admin":
        st.subheader("Kompletný prehľad pre majiteľa")
        st.dataframe(df)
    else:
        st.subheader(f"Zákazky pre pobočku: {auth}")
        # Filter: ukážeme len riadky danej pobočky
        if 'pobocka_id' in df.columns:
            filtered_df = df[df['pobocka_id'] == auth]
            if filtered_df.empty:
                st.info("Zatiaľ žiadne zákazky pre túto pobočku.")
            else:
                st.write("Upravte sumu v tabuľke:")
                st.data_editor(filtered_df)
        else:
            st.error("V tabuľke chýba stĺpec 'pobocka_id'!")

except Exception as e:
    st.error(f"Ešte nie je nastavené prepojenie na Google Sheets. Chyba: {e}")
