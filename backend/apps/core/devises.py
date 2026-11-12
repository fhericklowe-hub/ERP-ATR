"""Devises de commande. Le franc CFA n'a pas de centimes ; l'euro et le dollar en ont deux."""
from decimal import ROUND_HALF_UP, Decimal

# code : (libellé, décimales, singulier, pluriel, centième au singulier)
DEVISES = {
    "XOF": ("Franc CFA (XOF)", 0, "francs CFA", "francs CFA", ""),
    "EUR": ("Euro (EUR)", 2, "euro", "euros", "centime"),
    "USD": ("Dollar US (USD)", 2, "dollar", "dollars", "cent"),
}
CHOIX = [(code, d[0]) for code, d in DEVISES.items()]
PARITE_EURO = Decimal("655.957")  # parité fixe du franc CFA avec l'euro


def decimales(devise: str) -> int:
    return DEVISES[devise][1]


def arrondi(montant: Decimal, devise: str = "XOF") -> Decimal:
    return Decimal(montant).quantize(Decimal(1).scaleb(-decimales(devise)), rounding=ROUND_HALF_UP)


def formate(montant, devise: str = "XOF") -> str:
    """Montant avec espace pour les milliers et virgule pour les centimes : 1 234 567 ou 1 234,50."""
    return f"{arrondi(montant, devise):,}".replace(",", " ").replace(".", ",")
