import streamlit as st
from PIL import Image

st.set_page_config(
    page_title="GROUPE ISAGRI SERVICES - Notes de Frais IA",
    page_icon="📄",
    layout="wide"
)

st.title("📄 GROUPE ISAGRI SERVICES")
st.subheader("Notes de Frais IA")

st.write(
    "Analyse intelligente et contrôle automatisé des justificatifs"
)

st.markdown("---")

col1, col2, col3 = st.columns(3)

col1.metric("📄 Factures", "0")
col2.metric("💰 Montant Total", "0 €")
col3.metric("⚠️ Alertes", "0")

st.markdown("---")

fichiers = st.file_uploader(
    "Importer vos factures",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True
)

if fichiers:

    st.success(f"{len(fichiers)} facture(s) importée(s)")

    for fichier in fichiers:

        image = Image.open(fichier)

        st.image(
            image,
            caption=fichier.name,
            width=500
        )

st.markdown("---")

st.caption(
    "GROUPE ISAGRI SERVICES • Notes de Frais IA • V1.0"
)
