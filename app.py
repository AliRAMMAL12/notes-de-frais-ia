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
st.write("Analyse intelligente et contrôle automatisé des justificatifs")

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

    total_general = 0

    for fichier in fichiers:

        image = Image.open(fichier)

        image_np = np.array(image)

        try:

            resultat_ocr = reader.readtext(
                image_np,
                detail=0
            )

            texte = "\n".join(resultat_ocr)

            fournisseur = "Non trouvé"

            lignes = texte.split("\n")

            for ligne in lignes:

                ligne = ligne.strip()

                if len(ligne) > 3:
                    fournisseur = ligne
                    break

            dates = re.findall(
                r"\d{2}[/-]\d{2}[/-]\d{4}",
                texte
            )

            date_facture = "Non trouvée"

            if dates:
                date_facture = dates[0]

            montants = re.findall(
                r"\d+[,.]\d+",
                texte
            )

            montant = 0

            if montants:

                valeurs = [
                    float(x.replace(",", "."))
                    for x in montants
                ]

                montant = max(valeurs)

            total_general += montant

            texte_min = texte.lower()

            categorie = "Inconnue"

            if "restaurant" in texte_min or "repas" in texte_min:
                categorie = "Restaurant"

            elif "auchan" in texte_min:
                categorie = "Supermarché"

            elif "hotel" in texte_min or "hôtel" in texte_min:
                categorie = "Hôtel"

            st.markdown("---")

            st.subheader(f"📄 {fichier.name}")

            st.write(f"🏪 Fournisseur : {fournisseur}")
            st.write(f"📅 Date : {date_facture}")
            st.write(f"💰 Montant : {montant:.2f} €")
            st.write(f"📂 Catégorie : {categorie}")

        except Exception as erreur:

            st.error(
                f"Erreur d'analyse : {erreur}"
            )

    st.markdown("---")

    st.subheader("📊 Synthèse")

    st.success(
        f"💰 Total détecté : {total_general:.2f} €"
    )
