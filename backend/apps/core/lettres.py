"""Écriture d'un montant entier en toutes lettres, en français."""

UNITES = ["zéro", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix", "onze", "douze",
          "treize", "quatorze", "quinze", "seize", "dix-sept", "dix-huit", "dix-neuf"]
DIZAINES = {20: "vingt", 30: "trente", 40: "quarante", 50: "cinquante", 60: "soixante"}


def _moins_de_cent(n: int) -> str:
    if n < 20:
        return UNITES[n]
    if n < 70:
        d, u = n - n % 10, n % 10
        if u == 0:
            return DIZAINES[d]
        return f"{DIZAINES[d]} et un" if u == 1 else f"{DIZAINES[d]}-{UNITES[u]}"
    if n < 80:
        return "soixante et onze" if n == 71 else f"soixante-{UNITES[n - 60]}"
    if n == 80:
        return "quatre-vingts"
    return f"quatre-vingt-{UNITES[n - 80]}"


def _moins_de_mille(n: int) -> str:
    c, r = divmod(n, 100)
    if c == 0:
        return _moins_de_cent(r)
    debut = "cent" if c == 1 else f"{UNITES[c]} cent"
    if r == 0:
        return debut + ("s" if c > 1 else "")
    return f"{debut} {_moins_de_cent(r)}"


def _invariable(texte: str) -> str:
    """Devant « mille », « cents » et « quatre-vingts » perdent leur s."""
    return texte[:-1] if texte.endswith(("cents", "vingts")) else texte


def en_lettres(n: int) -> str:
    if n < 0:
        return "moins " + en_lettres(-n)
    if n < 1000:
        return _moins_de_mille(n)
    parties = []
    milliards, n = divmod(n, 10**9)
    millions, n = divmod(n, 10**6)
    milliers, reste = divmod(n, 1000)
    if milliards:
        parties.append(f"{_moins_de_mille(milliards)} milliard{'s' if milliards > 1 else ''}")
    if millions:
        parties.append(f"{_moins_de_mille(millions)} million{'s' if millions > 1 else ''}")
    if milliers:
        parties.append("mille" if milliers == 1 else f"{_invariable(_moins_de_mille(milliers))} mille")
    if reste:
        parties.append(_moins_de_mille(reste))
    return " ".join(parties)


def montant_en_lettres(montant, devise: str = "francs CFA") -> str:
    entier = int(round(montant))
    liaison = " de " if entier and entier % 10**6 == 0 else " "
    return f"{en_lettres(entier)}{liaison}{devise}".upper()
