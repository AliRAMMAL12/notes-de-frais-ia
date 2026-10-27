from io import BytesIO

import easyocr
import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image, ImageOps

from export_excel import exporter_excel
from extraction import CATEGORIES, analyser

try:
    import fitz  # PyMuPDF (lecture des PDF)
except ImportError:
    fitz = None

# =========================================================
# CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="GROUPE ISAGRI SERVICES - Notes de Frais IA",
    page_icon="📄",
    layout="wide",
)

MAX_PAGES_PDF = 5

# =========================================================
# LECTURE DES DOCUMENTS (images + PDF)
# =========================================================


@st.cache_resource(show_spinner="Chargement du moteur OCR...")
def charger_ocr():
    return easyocr.Reader(["fr", "en"])


def ocr_image(image: Image.Image) -> str:
    """OCR d'une image : orientation corrigée, taille limitée."""
    image = ImageOps.exif_transpose(image).convert("RGB")
    image.thumbnail((2200, 2200))
    return "\n".join(charger_ocr().readtext(np.array(image), detail=0))


@st.cache_data(show_spinner=False)
def lire_document(nom: str, octets: bytes):
    """Retourne (texte, aperçu en bytes). Mis en cache : jamais relu deux fois."""
    if not nom.lower().endswith(".pdf"):
        return ocr_image(Image.open(BytesIO(octets))), octets

    if fitz is None:
        raise RuntimeError("Lecture des PDF indisponible : ajouter 'pymupdf' à requirements.txt")

    textes, apercu = [], None
    with fitz.open(stream=octets, filetype="pdf") as pdf:
        for page in list(pdf)[:MAX_PAGES_PDF]:
            texte_page = page.get_text()
            pix = page.get_pixmap(dpi=200)
            png = pix.tobytes("png")
            apercu = apercu or png
            if len(texte_page.strip()) >= 30:
                textes.append(texte_page)  # PDF numérique : texte direct, sans OCR
            else:
                textes.append(ocr_image(Image.open(BytesIO(png))))  # PDF scanné
    return "\n".join(textes), apercu


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
    st.header("👤 Salarié")
    salarie = st.text_input("Nom du salarié (ajouté aux exports)")

fichiers = st.file_uploader(
    "Importer vos factures (photos ou PDF)",
    type=["jpg", "jpeg", "png", "pdf"],
    accept_multiple_files=True,
)

photo = None
with st.expander("📷 Prendre un ticket en photo (téléphone / webcam)"):
    photo = st.camera_input("Photographier le ticket")

sources = [(f.name, f.getvalue()) for f in fichiers]
if photo is not None:
    sources.append(("photo_camera.jpg", photo.getvalue()))

if sources:
    donnees, textes, apercus = [], {}, {}
    barre = st.progress(0.0, text="Analyse en cours...")

    for i, (nom, octets) in enumerate(sources, start=1):
        try:
            texte, apercu = lire_document(nom, octets)
            textes[nom], apercus[nom] = texte, apercu
            ligne = analyser(nom, texte)
            ligne["Validation"] = "À valider"
            donnees.append(ligne)
        except Exception as erreur:
            st.error(f"Erreur sur {nom} : {erreur}")
        barre.progress(i / len(sources), text=f"Analyse {i}/{len(sources)}")

    barre.empty()

    if not donnees:
        st.warning("Aucune facture n'a pu être analysée.")
        st.stop()

    # ---------- Tableau éditable ----------
    st.markdown("## 📊 Résultats")
    st.caption(
        "Corrige directement les cellules si besoin (montant, convives, alcool estimé, "
        "catégorie...) puis choisis le statut de validation."
    )

    colonnes = [
        "Fichier", "Fournisseur", "Date", "Montant (€)", "Catégorie", "Convives",
        "Alcool", "Alcool estimé (€)", "Statut", "Validation", "Remarques",
    ]
    df = st.data_editor(
        pd.DataFrame(donnees)[colonnes],
        use_container_width=True,
        hide_index=True,
        disabled=["Fichier", "Statut", "Remarques"],
        column_config={
            "Montant (€)": st.column_config.NumberColumn(format="%.2f €", min_value=0.0),
            "Alcool estimé (€)": st.column_config.NumberColumn(
                format="%.2f €", min_value=0.0,
                help="Estimation d'après les lignes d'articles reconnues comme alcool.",
            ),
            "Catégorie": st.column_config.SelectboxColumn(
                options=list(CATEGORIES) + ["Inconnue"]
            ),
            "Convives": st.column_config.NumberColumn(min_value=1, step=1),
            "Alcool": st.column_config.SelectboxColumn(options=["Oui", "Non"]),
            "Validation": st.column_config.SelectboxColumn(
                options=["À valider", "Validé", "Refusé"]
            ),
            "Remarques": st.column_config.TextColumn(width="large"),
        },
    )

    df["Hors alcool (€)"] = (df["Montant (€)"] - df["Alcool estimé (€)"]).clip(lower=0).round(2)

    # ---------- Contrôles ----------
    doublons = df.duplicated(
        subset=["Fournisseur", "Date", "Montant (€)"], keep=False
    ) & (df["Montant (€)"] > 0)

    par_personne = df["Montant (€)"] / df["Convives"].clip(lower=1)
    depassements = (df["Catégorie"] == "Restaurant") & (par_personne > plafond_resto)

    # ---------- KPI ----------
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("📄 Factures", len(df))
    col2.metric("💰 Total dépenses", f"{df['Montant (€)'].sum():.2f} €")
    col3.metric("✅ Total hors alcool", f"{df['Hors alcool (€)'].sum():.2f} €")
    col4.metric("🍷 Factures avec alcool", int((df["Alcool"] == "Oui").sum()))
    col5.metric("⚠️ À vérifier", int(df["Statut"].str.contains("vérifier").sum()))

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

    # ---------- Exports ----------
    export = df.copy()
    export.insert(0, "Salarié", salarie)

    c1, c2 = st.columns(2)
    c1.download_button(
        "📥 Télécharger en Excel",
        exporter_excel(export),
        file_name="notes_de_frais.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    c2.download_button(
        "📥 Télécharger en CSV",
        export.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
        file_name="notes_de_frais.csv",
        mime="text/csv",
    )

    # ---------- Détail par facture ----------
    with st.expander("🔍 Voir les images et le texte lu par l'OCR"):
        for nom, _ in sources:
            if nom in textes:
                c1, c2 = st.columns([1, 2])
                c1.image(apercus[nom], caption=nom, use_container_width=True)
                c2.text(textes[nom])
                st.markdown("---")
