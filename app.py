from io import BytesIO

import easyocr
import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image, ImageOps

from extraction import CATEGORIES, analyser

# =========================================================
# CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="GROUPE ISAGRI SERVICES - Notes de Frais IA",
    page_icon="📄",
    layout="wide",
)

# =========================================================
# OCR
# =========================================================


@st.cache_resource(show_spinner="Chargement du moteur OCR...")
def charger_ocr():
    return easyocr.Reader(["fr", "en"])


def preparer_image(octets: bytes) -> np.ndarray:
    """Corrige l'orientation (photos de téléphone) et limite la taille."""
    image = Image.open(BytesIO(octets))
    image = ImageOps.exif_transpose(image).convert("RGB")
    image.thumbnail((2200, 2200))
    return np.array(image)


@st.cache_data(show_spinner=False)
def lire_facture(octets: bytes) -> str:
    """OCR mis en cache : une même image n'est jamais relue deux fois."""
    lignes = charger_ocr().readtext(preparer_image(octets), detail=0)
    return "\n".join(lignes)


# =========================================================
# INTERFACE
# =========================================================

st.title("📄 GROUPE ISAGRI SERVICES")
st.subheader("Notes de Frais IA")
st.write("Analyse intelligente et contrôle automatisé des justificatifs")
st.markdown("---")

with st.sidebar:
    st.header("⚙️ Règles de contrôle")
    plafond_resto = st.number_input(
        "Plafond restaurant par personne (€)", min_value=0.0, value=25.0, step=1.0
    )

fichiers = st.file_uploader(
    "Importer vos factures",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True,
)

if fichiers:
    donnees, textes = [], {}
    barre = st.progress(0.0, text="Analyse en cours...")

    for i, fichier in enumerate(fichiers, start=1):
        try:
            texte = lire_facture(fichier.getvalue())
            textes[fichier.name] = texte
            donnees.append(analyser(fichier.name, texte))
        except Exception as erreur:
            st.error(f"Erreur sur {fichier.name} : {erreur}")
        barre.progress(i / len(fichiers), text=f"Analyse {i}/{len(fichiers)}")

    barre.empty()

    if not donnees:
        st.warning("Aucune facture n'a pu être analysée.")
        st.stop()

    # ---------- Tableau éditable ----------
    st.markdown("## 📊 Résultats")
    st.caption("Tu peux corriger directement les cellules (montant, convives, catégorie...).")

    df = st.data_editor(
        pd.DataFrame(donnees),
        use_container_width=True,
        hide_index=True,
        disabled=["Fichier", "Statut", "Remarques"],
        column_config={
            "Montant (€)": st.column_config.NumberColumn(format="%.2f €", min_value=0.0),
            "Catégorie": st.column_config.SelectboxColumn(
                options=list(CATEGORIES) + ["Inconnue"]
            ),
            "Convives": st.column_config.NumberColumn(min_value=1, step=1),
            "Alcool": st.column_config.SelectboxColumn(options=["Oui", "Non"]),
            "Remarques": st.column_config.TextColumn(width="large"),
        },
    )

    # ---------- Contrôles ----------
    doublons = df.duplicated(
        subset=["Fournisseur", "Date", "Montant (€)"], keep=False
    ) & (df["Montant (€)"] > 0)

    par_personne = df["Montant (€)"] / df["Convives"].clip(lower=1)
    depassements = (df["Catégorie"] == "Restaurant") & (par_personne > plafond_resto)

    # ---------- KPI ----------
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📄 Factures", len(df))
    col2.metric("💰 Total dépenses", f"{df['Montant (€)'].sum():.2f} €")
    col3.metric("🍷 Factures avec alcool", int((df["Alcool"] == "Oui").sum()))
    col4.metric("⚠️ À vérifier", int(df["Statut"].str.contains("vérifier").sum()))

    if doublons.any():
        st.warning("🔁 Doublons possibles : " + ", ".join(df.loc[doublons, "Fichier"]))
    if depassements.any():
        details = [
            f"{df.at[i, 'Fournisseur']} ({par_personne[i]:.2f} €/pers.)"
            for i in df.index[depassements]
        ]
        st.warning(
            f"💸 Plafond restaurant dépassé ({plafond_resto:.0f} €/pers.) : "
            + ", ".join(details)
        )

    # ---------- Graphique ----------
    st.markdown("### Dépenses par catégorie")
    st.bar_chart(df.groupby("Catégorie")["Montant (€)"].sum())

    # ---------- Export ----------
    st.download_button(
        "📥 Télécharger en CSV (Excel)",
        df.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
        file_name="notes_de_frais.csv",
        mime="text/csv",
    )

    # ---------- Détail par facture ----------
    with st.expander("🔍 Voir les images et le texte lu par l'OCR"):
        for fichier in fichiers:
            if fichier.name in textes:
                c1, c2 = st.columns([1, 2])
                c1.image(fichier, caption=fichier.name, use_container_width=True)
                c2.text(textes[fichier.name])
                st.markdown("---")
