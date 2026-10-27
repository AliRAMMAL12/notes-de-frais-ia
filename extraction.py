"""Tests de l'extraction sur le texte des 4 tickets réels.

Le texte ci-dessous est la retranscription de ce que l'OCR lit (une "ligne" par
zone de texte, dans l'ordre de lecture, libellé et montant souvent séparés).

Lancer :  python test_extraction.py      (ou)      pytest test_extraction.py
"""

from datetime import datetime

from extraction import analyser

AUJOURDHUI = datetime(2026, 10, 27)

COPAINS = """RESTAURANT
COPAINS COMNE COCHONS
26 RUE NEUVE
35500 VITRE
SIRET 8000762000014
12:15
30-09-2026
0032007
5x 20.18
MENU COMPLET AM 100.90
TOTAL
100.90
CARTE1
100.90
TVA2 10%
9.17
TL-TVA
9.17
TL-HT
91.73
TL-TTC
100.90
BONNE JOURNEE
REVENEZ NOUS VISITER"""

AUCHAN = """Auchan.fr
DARDILLY
Portes de Lyon - RN6 - Lieu dit la Garde..
69570 Dardilly
04.37.49.11.11
Vous avez été accueilli par SCO
Le 30 septembre 2026 à 18:12:56
Caisse : 134
Ticket : 8867
Hôte(sse) : 459
*STAND BOULANGERIE
1,45
*DISCO GRAND FORMAT
5,36
*CRISTALINE EAU DE ..
0,20
SIGNAL DENT SEL CAM..
2,97
Total
20,44 €
TVA%
TVA
Net
Brut
5,50
0,92
16,55
17,47
20,00
0,50
2,47
2,97
Brut
1,42
19,02
20,44
Reçu
TITRE RESTAURANT DE..
17,47
Reçu
CARTE BANCAIRE
2,97
TOT. ARTICLES ELIGIBLES TR
17,47
TOT. PAIEMENTS PAR TR
17,47
7 Articles
Avec votre carte de fidélité Auchan
vous auriez cagnotté :1,32 Euros
Nouveau scan correct"""

JULIA = """Chez Julia
168 Boulevard Massena
75013 PARIS
France
SIREN : 991749649
TVA : FR66991749649
Siret : 99174964900018
NAF : 56.30Z
Vente
Caisse enregistreuse N° : HA2CYDZ7
Type de document : Ticket
Commande N° : 33212
Numéro du reçu : TIK:17156/
b44466cd99afd614/7498
2026-09-17 22:52:57
Produit(s)
EUR
3x Ricard
13,50 A
(3×4,50)
1x Grimbergen blonde ou blanche -
5,50 A
25cl
(1×5,50)
1x Monbazillac ( Château
5,00 A
Beautrand )
(1×5,00)
1x 1664 - 25cl
5,20 A
(1×5,20)
1x Julia
17,00 B
(1×17,00)
1x Palerma
16,00 B
(1×16,00)
1x 75cl Côte du Rhône ( Les 3
22,00 A
garçons )
2x Espresso
5,20 B
(2×2,60)
Total TTC
89,40
89,40
Autres
TOTAL
HT : 77,39
TVA : 12,00
TTC : 89,40
Récapitulatif de TVA
B-10.0% de 38,20
A-20.0% de 51,20
Effectué par : Khaled
Version : FLATPAY POS v1.1.2609140 (587)"""

GOELETTE = """LA GOÉLETTE
57 quai François 1er, 76470 Le Tréport
France
Tél : 02 35 86 11 71 -
95103499000014 - 5610A - FR41951034990
19/09/2026 14:58
2 couverts
Salle - 3
Gérant
QTE DÉNOMINATION / PRIX UNITAIRE
TOTAL
2
Repas
79,20 €
39,60 €
Carte de crédit
79,20 €
HT
TVA
TTC
TVA 10% (10%)
34,73 €
3,47 €
38,20 €
TVA 20% (20%)
34,17 €
6,83 €
41,00 €
Total
68,90 €
10,30 €
79,20 €
Total par couvert
39,60 €
Total
79,20 €
2 couverts, 1 lignes, vendu par
Gérant(031d), le 2026-09-19 14:58:34 sur
la caisse 9050, version 12.3.1
Justificatif non valable pour encaissement n°
44
Ticket original n° 9050 - 2671
Système de caisse certifié LNE
Merci de votre visite et à bientôt"""

# (fournisseur, date, montant, catégorie, convives, alcool, alcool estimé €)
# Julia : 3 Ricard 13,50 + Grimbergen 5,50 + Monbazillac 5,00 + 1664 5,20
#         + Côte du Rhône 22,00 = 51,20 (les cocktails "Julia"/"Palerma" ne sont
#         pas reconnus comme alcool : c'est une estimation, modifiable dans l'appli)
ATTENDU = {
    "copains": ("Copains Comme Cochons", "30/09/2026", 100.90, "Restaurant", 5, "Non", 0.0),
    "auchan": ("Auchan", "30/09/2026", 20.44, "Supermarché", 1, "Non", 0.0),
    "julia": ("Chez Julia", "17/09/2026", 89.40, "Restaurant", 1, "Oui", 51.20),
    "goelette": ("La Goélette", "19/09/2026", 79.20, "Restaurant", 2, "Non", 0.0),
}
TEXTES = {"copains": COPAINS, "auchan": AUCHAN, "julia": JULIA, "goelette": GOELETTE}


def test_tickets():
    echecs = 0
    for nom, texte in TEXTES.items():
        r = analyser(nom, texte, AUJOURDHUI)
        obtenu = (r["Fournisseur"], r["Date"], r["Montant (€)"],
                  r["Catégorie"], r["Convives"], r["Alcool"], r["Alcool estimé (€)"])
        ok = obtenu == ATTENDU[nom]
        echecs += not ok
        print(f"{'OK ' if ok else 'KO '} {nom:9} {obtenu}")
        if not ok:
            print(f"      attendu : {ATTENDU[nom]}")
        print(f"      statut  : {r['Statut']} | {r['Remarques']}")
    assert echecs == 0, f"{echecs} ticket(s) mal analysé(s)"


def test_fournisseur_mal_lu_par_l_ocr():
    r = analyser("x", "LA GOELETTF\n12/09/2026\nTotal\n10,00 €", AUJOURDHUI)
    assert r["Fournisseur"] == "La Goélette", r["Fournisseur"]


def test_alcool_pas_de_double_comptage():
    texte = "Restaurant\n12/09/2026\n1x Vin rouge\nCote du rhone\n22,00 A\nTotal TTC\n22,00"
    r = analyser("x", texte, AUJOURDHUI)
    assert r["Alcool estimé (€)"] == 22.0, r["Alcool estimé (€)"]


if __name__ == "__main__":
    test_tickets()
    test_fournisseur_mal_lu_par_l_ocr()
    test_alcool_pas_de_double_comptage()
    print("\nTous les tests passent ✅")
