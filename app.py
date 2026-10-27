import streamlit as st
from PIL import Image
import easyocr
import numpy as np

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

@st.cache_resource
def charger_ocr():
    return easyocr.Reader(["fr", "en"])

reader = charger_ocr()

fichiers = st.file_uploader(
    "Importer vos factures",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True
)

if fichiers:

    st.success(f"{len(fichiers)} facture(s) importée(s)")

    for fichier in fichiers:

        st.markdown("---")

        image = Image.open(fichier)

        col1, col2 = st.columns([1, 2])

        with col1:
            st.image(
                image,
                caption=fichier.name,
                use_container_width=True
            )

        with col2:

            st.subheader(f"📄 {fichier.name}")

            try:

                image_np = np.array(image)

                texte = reader.readtext(
                    image_np,
                    detail=0
                )

                st.text_area(
                    "Texte détecté",
                    "\n".join(texte),
                    height=250
                )

            except Exception as erreur:

                st.error(
                    f"Erreur OCR : {erreur}"
                )

st.markdown("---")

st.caption(
    "GROUPE ISAGRI SERVICES • Notes de Frais IA • V1.1"
)
