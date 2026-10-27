"""Extraction des informations d'un ticket à partir du texte brut de l'OCR.

Ce module ne dépend ni de Streamlit ni d'EasyOCR : il peut donc être testé
facilement (voir test_extraction.py).
"""

import difflib
import re
import unicodedata
from datetime import datetime, timedelta

# =========================================================
# PARAMÈTRES MÉTIER (à adapter)
# =========================================================

# Fournisseurs connus : mot-clé -> (nom affiché, catégorie)
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
    "Carburant": ["carburant", "gazole", "diesel", "sp95", "sp98", "totalenergies"],
    "Hôtel": ["hotel", "nuitee", "chambre"],
    "Transport": ["sncf", "billet", "peage", "autoroute", "parking", "taxi"],
}

MOTS_ALCOOL = [
    "ricard", "pastis", "grimbergen", "monbazillac", "vin", "vins",
    "biere", "bieres", "whisky", "vodka", "champagne", "rhum", "gin",
    "cognac", "cidre", "kir", "spritz", "cocktail", "armagnac", "muscat",
    "cote du rhone", "chardonnay", "merlot", "pinot",
]
REGEX_ALCOOL = re.compile(
    r"(?<![a-z0-9])(" + "|".join(re.escape(m) for m in MOTS_ALCOOL) + r")(?![a-z0-9])"
)
REGEX_1664 = re.compile(r"(?<!\d)1664(?!\d)")  # la bière "1664"

# Mots-clés du montant final, par priorité (3 = le plus fiable)
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
LIGNES_IGNOREES = ("par couvert", "par personne", "fidelite", "cagnott")

MOIS = {
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11,
    "decembre": 12,
}

# =========================================================
# EXPRESSIONS RÉGULIÈRES
# =========================================================

# Montants : "100.90", "20,44", "1 234,56" (en évitant les n° de téléphone)
REGEX_MONTANT = re.compile(
    r"(?<![\d.,])\d+(?:[ \u00a0]\d{3})*[,.]\d{2}(?!\d|[.,]\d)"
)

# Dates : 30/09/2026 ou 30-09-2026 ; 2026-09-17 ; "30 septembre 2026" ; 30/09/26
REGEX_DMY4 = re.compile(r"(?<![\d/.\-])(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})(?!\d)")
REGEX_ISO = re.compile(r"(?<![\d/.\-])(\d{4})-(\d{2})-(\d{2})(?!\d)")
REGEX_TEXTE = re.compile(r"(?<!\d)(\d{1,2})\s+(" + "|".join(MOIS) + r")\s+(\d{4})")
REGEX_DMY2 = re.compile(r"(?<![\d/.\-])(\d{2})/(\d{2})/(\d{2})(?![\d/.\-])")


# =========================================================
# OUTILS
# =========================================================


def normaliser(texte: str) -> str:
    """Minuscules, sans accents, '×' -> 'x' (pour des recherches robustes)."""
    texte = texte.replace("×", "x")
    texte = unicodedata.normalize("NFKD", texte)
    return texte.encode("ascii", "ignore").decode("ascii").lower()


def convertir_montants(ligne: str) -> list[float]:
    valeurs = []
    for m in REGEX_MONTANT.findall(ligne):
        try:
            valeurs.append(float(m.replace("\u00a0", "").replace(" ", "").replace(",", ".")))
        except ValueError:
            pass
    return valeurs


def _montants_ligne_ou_suivante(lignes: list[str], i: int) -> list[float]:
    """Montants de la ligne i ; sinon de la ligne suivante.

    L'OCR sépare souvent le libellé ("TOTAL") et le chiffre ("100.90") sur
    deux lignes. On n'accepte la ligne suivante que si elle contient un seul
    montant et n'est pas une ligne de HT/TVA.
    """
    valeurs = convertir_montants(lignes[i])
    if valeurs or i + 1 >= len(lignes):
        return valeurs
    suivante = lignes[i + 1]
    if re.search(r"\b(ht|tva)\b", suivante):
        return []
    montants = convertir_montants(suivante)
    return montants if len(montants) == 1 else []


# =========================================================
# EXTRACTION
# =========================================================


def _fournisseur_approx(entete: str):
    """Tolère les fautes de l'OCR (ex. 'goelettf' -> 'goelette') sur les noms longs."""
    cles = [c for c in FOURNISSEURS if len(c) >= 6]
    for mot in re.findall(r"[a-z]{6,}", entete):
        proche = difflib.get_close_matches(mot, cles, n=1, cutoff=0.8)
        if proche:
            return FOURNISSEURS[proche[0]]
    return None


def extraire_fournisseur(texte: str, texte_norm: str):
    """Retourne (fournisseur, catégorie_déduite_ou_None)."""
    entete = "\n".join(texte_norm.split("\n")[:8])  # le nom est en haut du ticket

    for zone in (entete, texte_norm):
        for cle, (nom, categorie) in FOURNISSEURS.items():
            if re.search(rf"\b{cle}", zone):
                return nom, categorie

    approx = _fournisseur_approx(entete)
    if approx:
        return approx

    # Repli : première ligne "propre" (assez de lettres, pas une date)
    for ligne in texte.split("\n"):
        ligne = ligne.strip()
        if sum(c.isalpha() for c in ligne) >= 4 and not REGEX_DMY4.search(ligne):
            return ligne.title(), None
    return "Non trouvé", None


def extraire_date(texte_norm: str, aujourdhui: datetime | None = None) -> str:
    """Première date valide et plausible, au format JJ/MM/AAAA."""
    aujourdhui = aujourdhui or datetime.now()

    def valide(j, m, a):
        try:
            d = datetime(a, m, j)
        except ValueError:
            return None
        if aujourdhui.year - 5 <= d.year and d <= aujourdhui + timedelta(days=1):
            return d
        return None

    essais = [
        (REGEX_DMY4, lambda g: (int(g[0]), int(g[1]), int(g[2]))),
        (REGEX_ISO, lambda g: (int(g[2]), int(g[1]), int(g[0]))),
        (REGEX_TEXTE, lambda g: (int(g[0]), MOIS[g[1]], int(g[2]))),
        (REGEX_DMY2, lambda g: (int(g[0]), int(g[1]), 2000 + int(g[2]))),
    ]
    for regex, extraire in essais:
        for m in regex.finditer(texte_norm):
            d = valide(*extraire(m.groups()))
            if d:
                return d.strftime("%d/%m/%Y")
    return ""


def extraire_montant(texte_norm: str):
    """Retourne (montant, fiable)."""
    lignes = texte_norm.split("\n")
    candidats = []  # (priorité, valeur)

    for i, ligne in enumerate(lignes):
        if any(x in ligne for x in LIGNES_IGNOREES):
            continue
        if re.search(r"\btva\b", ligne) and "ttc" not in ligne:
            continue  # ligne de TVA seule
        for mot, priorite in MOTS_MONTANT:
            if mot in ligne:
                candidats += [(priorite, v) for v in _montants_ligne_ou_suivante(lignes, i)]
                break

    if candidats:
        meilleure = max(p for p, _ in candidats)
        return max(v for p, v in candidats if p == meilleure), True

    # Dernier recours : plus gros montant du ticket (peu fiable)
    tous = convertir_montants(texte_norm)
    return (max(tous), False) if tous else (0.0, False)


def extraire_titres_restaurant(texte_norm: str) -> float:
    """Montant payé en titres-restaurant (0 si aucun)."""
    lignes = texte_norm.split("\n")
    for i, ligne in enumerate(lignes):
        if re.search(r"(titre|ticket)s?[- ]restaurant|\b(swile|edenred|pluxee)\b", ligne):
            valeurs = _montants_ligne_ou_suivante(lignes, i)
            if valeurs:
                return max(valeurs)
    return 0.0


def extraire_convives(texte_norm: str):
    """Nombre de convives si on peut le déduire, sinon None."""
    m = re.search(r"(\d{1,2})\s*couverts?\b", texte_norm)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d{1,2})\s*x\s*\d+[.,]\d{2}\s*\n\s*menu", texte_norm)
    if m:
        return int(m.group(1))
    return None


def extraire_categorie(texte_norm: str, categorie_fournisseur) -> str:
    if categorie_fournisseur:
        return categorie_fournisseur
    for categorie, mots in CATEGORIES.items():
        if any(mot in texte_norm for mot in mots):
            return categorie
    return "Inconnue"


def detecter_alcool(texte_norm: str) -> str:
    if REGEX_ALCOOL.search(texte_norm) or REGEX_1664.search(texte_norm):
        return "Oui"
    return "Non"


def estimer_montant_alcool(texte_norm: str) -> float:
    """Somme des lignes d'articles contenant un mot d'alcool (estimation).

    Le prix est cherché sur la ligne de l'article, sinon sur les 2 lignes
    suivantes (l'OCR sépare souvent le nom et le prix), en s'arrêtant au
    prochain article ou aux lignes de total / TVA.
    """
    lignes = texte_norm.split("\n")
    utilisees = set()  # lignes de prix déjà comptées (évite les doubles comptages)
    total = 0.0

    for i, ligne in enumerate(lignes):
        if not (REGEX_ALCOOL.search(ligne) or REGEX_1664.search(ligne)):
            continue

        valeurs = convertir_montants(ligne)
        if valeurs:
            if i not in utilisees:
                utilisees.add(i)
                total += max(valeurs)
            continue

        trouves = []
        for j in range(i + 1, min(i + 3, len(lignes))):
            suivante = lignes[j]
            if re.match(r"\s*\d+\s*x\s+\S", suivante):  # nouvel article
                break
            if re.search(r"\b(total|ttc|tva|ht)\b", suivante):
                break
            if j in utilisees:
                continue
            valeurs = convertir_montants(suivante)
            if valeurs:
                trouves.append((j, max(valeurs)))
        if trouves:
            j, valeur = max(trouves, key=lambda t: t[1])
            utilisees.update(j for j, _ in trouves)
            total += valeur

    return round(total, 2)


# =========================================================
# ANALYSE COMPLÈTE D'UN TICKET
# =========================================================


def analyser(nom_fichier: str, texte: str, aujourdhui: datetime | None = None) -> dict:
    texte_norm = normaliser(texte)

    fournisseur, cat_fournisseur = extraire_fournisseur(texte, texte_norm)
    date = extraire_date(texte_norm, aujourdhui)
    montant, fiable = extraire_montant(texte_norm)
    categorie = extraire_categorie(texte_norm, cat_fournisseur)
    convives = extraire_convives(texte_norm)

    problemes, remarques = [], []
    if fournisseur == "Non trouvé":
        problemes.append("fournisseur non trouvé")
    if not date:
        problemes.append("date non trouvée")
    if montant == 0:
        problemes.append("montant non trouvé")
    elif not fiable:
        problemes.append("montant incertain")

    if categorie == "Restaurant" and convives is None:
        remarques.append("nombre de convives non détecté (1 par défaut)")
    alcool = detecter_alcool(texte_norm)
    montant_alcool = estimer_montant_alcool(texte_norm) if alcool == "Oui" else 0.0
    if montant > 0:
        montant_alcool = min(montant_alcool, montant)
    if alcool == "Oui" and montant_alcool == 0:
        remarques.append("alcool détecté mais montant non estimé")
    titres = extraire_titres_restaurant(texte_norm)
    if titres:
        remarques.append(f"payé en partie en titres-restaurant ({titres:.2f} €)")
    if re.search(r"non valable pour encaissement|duplicata", texte_norm):
        remarques.append("mention « non valable pour encaissement » / duplicata")

    return {
        "Fichier": nom_fichier,
        "Fournisseur": fournisseur,
        "Date": date,
        "Montant (€)": montant,
        "Catégorie": categorie,
        "Convives": convives or 1,
        "Alcool": alcool,
        "Alcool estimé (€)": montant_alcool,
        "Statut": "⚠️ À vérifier" if problemes else "✅ OK",
        "Remarques": " ; ".join(problemes + remarques),
    }
