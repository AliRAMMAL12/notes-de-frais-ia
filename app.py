import re
import unicodedata
from datetime import datetime

import easyocr
import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image, ImageOps

# =========================================================
# CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="GROUPE ISAGRI SERVICES - Notes de Frais IA",
    page_icon="📄",
    layout="wide",
)

# Fournisseurs connus : mot-clé -> (nom affiché, catégorie)
# Ajoute simplement une ligne pour reconnaître un nouveau fournisseur.
FOURNISSEURS = {
    "auchan": ("Auchan", "Supermarché"),
    "carrefour": ("Carrefour", "Supermarché"),
    "leclerc": ("E.Leclerc", "Supermarché"),
    "julia": ("Chez Julia", "Restaurant"),
    "goelette": ("La Goélette", "Restaurant"),
    "copains": ("Copains Comme Cochons", "Restaurant"),
}

# Mots-clés de catégorie (utilisés si le fournisseur est inconnu)
CATEGORIES = {
    "Restaurant": ["restaurant", "repas", "menu", "brasserie", "addition", "couvert"],
    "Supermarché": ["supermarche", "hypermarche", "carrefour", "leclerc", "auchan"],
    "Carburant": ["carburant", "gazole", "diesel", "sp95", "sp98", "total energies"],
    "Hôtel": ["hotel", "nuitee", "chambre"],
    "Transport": ["sncf", "billet", "peage", "autoroute", "parking", "taxi"],
}

MOTS_ALCOOL = [
    "ricard", "pastis", "grimbergen", "monbazillac", "1664", "vin", "vins",
    "biere", "bieres", "whisky", "vodka", "champagne", "rhum", "gin",
    "cognac", "cidre", "kir", "spritz", "cocktail", "armagnac", "muscat",
]
REGEX_ALCOOL = re.compile(r"\b(" + "|".join(MOTS_ALCOOL) + r")\b")

# Mots-clés du montant final, classés par priorité (3 = le plus fiable)
MOTS_MONTANT = [
    ("net a payer", 3),
    ("total ttc", 3),
    ("montant ttc", 3),
    ("a payer", 3),
    ("total carte", 3),
    ("ttc", 2),
    ("total", 2),
    ("carte", 1),
]

REGEX_MONTANT = re.compile(r"\d{1,3}(?:[ \u00a0]\d{3})*[,.]\d{2}\b|\d+[,.]\d{2}\b")
REGEX_DATE = re.compile(r"\b(\d{2})[/\-.](\d{2})[/\-.](\d{4}|\d{2})\b")

# =========================================================
# OUTILS
# =========================================================


def normaliser(texte: str) -> str:
    """Minuscules + suppression des accents pour des recherches robustes."""
    texte = unicodedata.normalize("NFKD", texte)
    return texte.encode("ascii", "ignore").decode("ascii").lower()


@st.cache_resource(show_spinner="Chargement du moteur OCR...")
def charger_ocr():
    return easyocr.Reader(["fr", "en"])


def preparer_image(octets: bytes) -> np.ndarray:
    """Corrige l'orientation (photos de téléphone), uniformise et limite la taille."""
    from io import BytesIO

    image = Image.open(BytesIO(octets))
    image = ImageOps.exif_transpose(image).convert("RGB")
    image.thumbnail((2200, 2200))  # accélère l'OCR sans perdre en lisibilité
    return np.array(image)


@st.cache_data(show_spinner=False)
def lire_facture(octets: bytes) -> str:
    """OCR mis en cache : une même image n'est jamais relue deux fois."""
    lignes = charger_ocr().readtext(preparer_image(octets), detail=0, paragraph=False)
    return "\n".join(lignes)


# =========================================================
# EXTRACTION
# =========================================================


def extraire_fournisseur(texte: str, texte_norm: str):
    """Retourne (fournisseur, categorie_deduite_ou_None)."""
    for cle, (nom, categorie) in FOURNISSEURS.items():
        if re.search(rf"\b{cle}", texte_norm):
            return nom, categorie

    # Repli : première ligne "propre" (assez de lettres, pas une date/un nombre)
    for ligne in texte.split("\n"):
        ligne = ligne.strip()
        if sum(c.isalpha() for c in ligne) >= 4 and not REGEX_DATE.search(ligne):
            return ligne.title(), None
    return "Non trouvé", None


def extraire_date(texte: str) -> str:
    """Première date valide et plausible, format JJ/MM/AAAA."""
    for jour, mois, annee in REGEX_DATE.findall(texte):
        annee = int(annee) + 2000 if len(annee) == 2 else int(annee)
        try:
            d = datetime(annee, int(mois), int(jour))
        except ValueError:
            continue
        if 2000 <= d.year <= datetime.now().year + 1:
            return d.strftime("%d/%m/%Y")
    return ""


def convertir_montants(ligne: str) -> list[float]:
    valeurs = []
    for m in REGEX_MONTANT.findall(ligne):
        try:
            valeurs.append(float(m.replace("\u00a0", "").replace(" ", "").replace(",", ".")))
        except ValueError:
            pass
    return valeurs


def extraire_montant(texte: str):
    """Retourne (montant, fiable). Gère le cas où le montant est sur la ligne suivante."""
    lignes = [normaliser(l) for l in texte.split("\n")]
    candidats = []  # (priorité, valeur)

    for i, ligne in enumerate(lignes):
        if "tva" in ligne and "ttc" not in ligne:
            continue  # on ignore les lignes de TVA seule
        for mot, priorite in MOTS_MONTANT:
            if mot in ligne:
                valeurs = convertir_montants(ligne)
                # L'OCR sépare souvent le libellé et le chiffre sur 2 lignes
                if not valeurs and i + 1 < len(lignes):
                    valeurs = convertir_montants(lignes[i + 1])
                for v in valeurs:
                    candidats.append((priorite, v))
                break

    if candidats:
        meilleure = max(p for p, _ in candidats)
        return max(v for p, v in candidats if p == meilleure), True

    # Dernier recours : plus gros montant du ticket (moins fiable)
    tous = convertir_montants(texte)
    return (max(tous), False) if tous else (0.0, False)


def extraire_categorie(texte_norm: str, categorie_fournisseur) -> str:
    if categorie_fournisseur:
        return categorie_fournisseur
    for categorie, mots in CATEGORIES.items():
        if any(mot in texte_norm for mot in mots):
            return categorie
    return "Inconnue"


def detecter_alcool(texte_norm: str) -> str:
    return "Oui" if REGEX_ALCOOL.search(texte_norm) else "Non"


def analyser(nom_fichier: str, texte: str) -> dict:
    texte_norm = normaliser(texte)
    fournisseur, cat_fournisseur = extraire_fournisseur(texte, texte_norm)
    date = extraire_date(texte)
    montant, fiable = extraire_montant(texte)

    a_verifier = (
        fournisseur == "Non trouvé" or not date or montant == 0 or not fiable
    )

    return {
        "Fichier": nom_fichier,
        "Fournisseur": fournisseur,
        "Date": date,
        "Montant (€)": montant,
        "Catégorie": extraire_categorie(texte_norm, cat_fournisseur),
        "Alcool": detecter_alcool(texte_norm),
        "Statut": "⚠️ À vérifier" if a_verifier else "✅ OK",
    }


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
        "Plafond restaurant (€)", min_value=0.0, value=25.0, step=1.0
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
    st.caption("Tu peux corriger directement les cellules si l'OCR s'est trompé.")

    df = st.data_editor(
        pd.DataFrame(donnees),
        use_container_width=True,
        hide_index=True,
        disabled=["Fichier", "Statut"],
        column_config={
            "Montant (€)": st.column_config.NumberColumn(format="%.2f €", min_value=0.0),
            "Catégorie": st.column_config.SelectboxColumn(
                options=list(CATEGORIES) + ["Inconnue"]
            ),
            "Alcool": st.column_config.SelectboxColumn(options=["Oui", "Non"]),
        },
    )

    # ---------- Contrôles ----------
    doublons = df.duplicated(
        subset=["Fournisseur", "Date", "Montant (€)"], keep=False
    ) & (df["Montant (€)"] > 0)
    depassements = (df["Catégorie"] == "Restaurant") & (df["Montant (€)"] > plafond_resto)

    # ---------- KPI ----------
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📄 Factures", len(df))
    col2.metric("💰 Total dépenses", f"{df['Montant (€)'].sum():.2f} €")
    col3.metric("🍷 Factures avec alcool", int((df["Alcool"] == "Oui").sum()))
    col4.metric("⚠️ À vérifier", int(df["Statut"].str.contains("vérifier").sum()))

    if doublons.any():
        st.warning("🔁 Doublons possibles : " + ", ".join(df.loc[doublons, "Fichier"]))
    if depassements.any():
        st.warning(
            f"💸 Dépassement du plafond restaurant ({plafond_resto:.0f} €) : "
            + ", ".join(df.loc[depassements, "Fichier"])
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
