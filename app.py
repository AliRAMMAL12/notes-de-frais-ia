import streamlit as st
from PIL import Image
import pytesseract

# Configuration Tesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Configuration page
st.set_page_config(
    page_title="GROUPE ISAGRI SERVICES - Notes de Frais IA",
    page_icon="📄",
    layout="wide"
)

# Titre
st.title("📄 GROUPE ISAGRI SERVICES")

st.subheader("Notes de Frais IA")

st.write(
    "Analyse intelligente et contrôle automatisé des justificatifs"
)

st.markdown("---")

# Statistiques
col1, col2, col3 = st.columns(3)

col1.metric("📄 Factures", "0")
col2.metric("💰 Montant Total", "0 €")
col3.metric("⚠️ Alertes", "0")

st.markdown("---")

# Upload
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

        st.image(image, width=400)

        try:

            image_ocr = image.resize(
                (image.width * 2, image.height * 2)
            )

            image_ocr = image_ocr.convert("L")

            texte = pytesseract.image_to_string(image_ocr)

            st.text_area(
                f"OCR - {fichier.name}",
                texte,
                height=250
            )

        except Exception as erreur:

            st.error(f"Erreur OCR : {erreur}")

st.markdown("---")

st.caption("GROUPE ISAGRI SERVICES • Notes de Frais IA • V1")