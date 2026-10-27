import streamlit as st
from PIL import Image
import easyocr
import numpy as np
import re

st.set_page_config(
    page_title="Notes de Frais IA",
    page_icon="📄",
    layout="wide"
)

st.title("📄 Notes de Frais IA")

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

            image_np = np.array(image)

            resultats = reader.readtext(
                image_np,
                detail=0
            )

            texte = "\n".join(resultats)

            st.subheader("📄 Résultat OCR")

            st.text_area(
                "Texte détecté",
                texte,
                height=200
            )

            # ANALYSE

            montants = re.findall(
                r"\d+[,.]\d+",
                texte
            )

            dates = re.findall(
                r"\d{2}[/-]\d{2}[/-]\d{4}",
                texte
            )

            fournisseur = "Non trouvé"

            lignes = texte.split("\n")

            for ligne in lignes:

                ligne = ligne.strip()

                if len(ligne) > 3:
                    fournisseur = ligne
                    break

            st.subheader("📊 Analyse")

            st.write(
                f"🏪 Fournisseur : {fournisseur}"
            )

            if dates:
                st.write(
                    f"📅 Date : {dates[0]}"
                )

            if montants:

                montant_max = max(
                    [
                        float(
                            x.replace(",", ".")
                        )
                        for x in montants
                    ]
                )

                st.write(
                    f"💰 Montant détecté : {montant_max} €"
                )
