"""Infer car make, model and generation from a part's name and description.

The crawler uses this to attach scraped parts to the right generations. Returns
(make, model, generation_name) triples for `resolve_car_triples_to_ids` to resolve.
"""

import re
from typing import Optional
from uuid import UUID

from app.core.car_generations_data import CAR_GENERATIONS

AMBIGUOUS_STANDALONE_CODES: frozenset[str] = frozenset(
    {
        "GR",
        "Mk5",
        "Mk4",
        "B5",
        "B4",
        "EVO",
        "P1",
        "V10",
        "HI",
        "NA",
        "E90",
        "E92",
        "E93",
        "E9x",
        "E46",
        "E36",
        "S",
        "D2",
        "8S",
        "I",
        "II",
        "III",
        "IV",
        "V",
        "VI",
        "VII",
        "VIII",
        "IX",
        "X",
        "C4",
        "C5",
        "C6",
        "C7",
        "C8",
        "E70",
        "F40",
        "Mk6",
        "Mk7",
        "G60",
        "970",
        "G70",
        "G80",
        "G87",
        "Plaid",
        "GC",
        "HD",
        "CV",
        "CV1",
        "S1",
        "SH",
        "OS",
        "FS",
        "MD",
        "BK",
        "LX",
        "BP",
        "XT",
        "CR",
        "RL",
        "RS",
        "RU",
        "2024+",
        "308",
        "328",
        "348",
        "356",
        "928",
        "930",
        "944",
        "992",
        "997",
        "7L",
        "8L",
        "8T",
        "A5",
        "A35",
        "AD",
        "AE86",
        "B2",
        "B6",
        "B8",
        "B16",
        "B18",
        "BC",
        "BD",
        "BF",
        "BG",
        "BJ",
        "BL",
        "BM",
        "BN",
        "BR",
        "BS",
        "BT",
        "CE",
        "CT",
        "DA",
        "E30",
        "E60",
        "EG",
        "EK",
        "F15",
        "F16",
        "GD",
        "GE",
        "J1",
        "LD",
        "L30",
        "Mk1",
        "Mk2",
        "Mk3",
        "P10",
        "P11",
        "R32",
        "RA",
        "RD",
        "RE",
        "RM",
        "S14",
        "S50",
        "M30",
        "VE",
        "VF",
        "VR6",
        "T6",
        "Turbo/Shelby",
        "R/T Turbo",
        "BE/BH",
        "E36/7",
        "E36/8",
        "E36/7 E36/8",
        "V1",
        "Turbo",
        "Shelby",
        "BE",
        "BH",
        "R",
        "T",
        "7",
        "8",
        "DB5",
        "DB6",
        "DB7",
        "DB9",
        "DBS",
        "GLH",
        "GTB",
        "ZRC",
        "CXD",
        "FY",
        "RG",
        "DH",
        "RW",
        "YH",
        "GK",
        "XD",
        "JS",
        "NE",
        "CK",
        "TF",
        "JF",
        "VT",
        "SV",
        "NB",
        "NC",
        "ND",
        "SA",
        "FB",
        "FC",
        "FD",
        "JC",
        "GG",
        "GY",
        "GH",
        "GJ",
        "GL",
        "CS",
        "CJ",
        "VA",
        "VB",
        "GF",
        "GP",
        "SF",
        "SG",
        "SJ",
    }
)
"""Generation codes that must NOT fire on their own because they collide with
other tokens in scraped catalog data.

Purpose:
    Codes in this set require an adjacent make+model phrase (see PHRASE_TRIPLES
    and CAR_ALIASES in this module) to disambiguate. Bare standalone matches
    are suppressed by ``_build_phrase_triples`` to avoid false positives like
    "HI" in "HKS Hi Power" incorrectly matching Genesis G90 HI, or "NA" in
    "CTEK MXS 5.0 NA" incorrectly matching Miata NA.

Criterion for adding a code:
    - It matches a real product-name token (brand, SKU suffix, marketing phrase,
      engine code, bore/displacement figure) that creates repeated false
      positives in scraped catalog data, AND/OR
    - It is shared across multiple make/model lineages and cannot disambiguate
      without the paired make/model string.

Criterion for removing a code:
    - The colliding brand/product is retired or absent from the current retailer
      catalog, AND
    - No remaining collisions exist in representative scraped samples, AND
    - Removing the entry provably improves recall without introducing new false
      positives (verify against ``test_car_inference.py`` +
      ``test_car_inference_ambiguity.py``).

Known counterexamples:
    See ``backend/tests/test_car_inference_ambiguity.py`` for ~20+ pinned
    behaviors. Those tests assert CURRENT behavior, not CORRECTNESS. The
    ML-based rewrite (PARTS-V2-01) is explicitly deferred to v2 per
    ``.planning/REQUIREMENTS.md``.
"""


def _is_too_short_to_dispatch(component: str) -> bool:
    """Whether a slash-split generation component is too short to match on safely.

    Pure-digit components under 3 characters and pure-alpha ones under 4 are rejected,
    because they match ordinary words and SKU fragments inside product titles.
    """
    if not component:
        return True
    if component.isdigit() and len(component) < 3:
        return True
    if component.isalpha() and len(component) < 4:
        return True
    return False


def _build_phrase_triples() -> list[tuple[str, str, str, str]]:
    """Build normalised (phrase, make, model, generation_name) rows from the seed data.

    Individual slash-split components pass two filters: the explicit
    `AMBIGUOUS_STANDALONE_CODES` deny list, then `_is_too_short_to_dispatch`.
    """
    triples: list[tuple[str, str, str, str]] = []
    for make, models in CAR_GENERATIONS.items():
        for model_data in models:
            model = model_data["model"]
            for gen in model_data["generations"]:
                gen_name = gen["generation_name"]
                full = f"{make} {model} {gen_name}".lower()
                triples.append((full, make, model, gen_name))
                model_gen = f"{model} {gen_name}".lower()
                triples.append((model_gen, make, model, gen_name))
                if gen_name in AMBIGUOUS_STANDALONE_CODES:
                    continue
                components = [c.strip() for c in gen_name.split("/") if c.strip()]
                for component in components:
                    if len(component) > 6:
                        continue
                    if component in AMBIGUOUS_STANDALONE_CODES:
                        continue
                    if _is_too_short_to_dispatch(component):
                        continue
                    triples.append((component.lower(), make, model, gen_name))
    return triples


PHRASE_TRIPLES: list[tuple[str, str, str, str]] = sorted(_build_phrase_triples(), key=lambda x: -len(x[0]))


def _build_make_model_phrases() -> tuple[
    list[tuple[str, str, str]],
    list[tuple[str, str, str]],
]:
    """Build the `with_make` and `model_only` phrase lists from the seed data.

    Bare model phrases are only safe when the caller constrains `trusted_makes`.
    Both lists are sorted longest first, so `ram 2500` wins over `ram`.
    """
    with_make: list[tuple[str, str, str]] = []
    model_only: list[tuple[str, str, str]] = []
    for make, models in CAR_GENERATIONS.items():
        make_lower = make.lower()
        for model_data in models:
            model = model_data["model"]
            model_lower = model.lower()
            with_make.append((f"{make_lower} {model_lower}", make, model))
            model_only.append((model_lower, make, model))
    with_make.sort(key=lambda x: -len(x[0]))
    model_only.sort(key=lambda x: -len(x[0]))
    return with_make, model_only


_FITMENT_PHRASES_WITH_MAKE, _FITMENT_PHRASES_MODEL_ONLY = _build_make_model_phrases()


CAR_ALIASES: list[tuple[str, str, str, str]] = [
    ("mkv supra", "Toyota", "Supra", "A90"),
    ("mk5 supra", "Toyota", "Supra", "A90"),
    ("gr supra", "Toyota", "Supra", "A90"),
    ("supra gr a90", "Toyota", "Supra", "A90"),
    ("supra gr a91", "Toyota", "Supra", "A90"),
    ("supra gr 2020+", "Toyota", "Supra", "A90"),
    ("2020+ supra", "Toyota", "Supra", "A90"),
    ("2020+ toyota supra", "Toyota", "Supra", "A90"),
    ("2020 supra", "Toyota", "Supra", "A90"),
    ("supra 2020", "Toyota", "Supra", "A90"),
    ("2020 toyota supra", "Toyota", "Supra", "A90"),
    ("toyota supra 2020", "Toyota", "Supra", "A90"),
    ("a90/a91", "Toyota", "Supra", "A90"),
    ("a90 supra", "Toyota", "Supra", "A90"),
    ("a91 supra", "Toyota", "Supra", "A90"),
    ("mkv toyota supra", "Toyota", "Supra", "A90"),
    ("mkv supra gr", "Toyota", "Supra", "A90"),
    ("supra gr", "Toyota", "Supra", "A90"),
    ("20-21 toyota supra", "Toyota", "Supra", "A90"),
    ("2020-2021 toyota supra", "Toyota", "Supra", "A90"),
    ("off your supra", "Toyota", "Supra", "A90"),
    ("g82 m4", "BMW", "M4", "G82/G83"),
    ("g83 m4", "BMW", "M4", "G82/G83"),
    ("bmw g82", "BMW", "M4", "G82/G83"),
    ("m4 g82", "BMW", "M4", "G82/G83"),
    ("m4 g83", "BMW", "M4", "G82/G83"),
    ("g8x m3", "BMW", "M3", "G80"),
    ("g8x m4", "BMW", "M4", "G82/G83"),
    ("bmw g8x", "BMW", "M4", "G82/G83"),
    ("m3 g80", "BMW", "M3", "G80"),
    ("m4 g8x", "BMW", "M4", "G82/G83"),
    ("m3 g8x", "BMW", "M3", "G80"),
    ("e9x m3", "BMW", "M3", "E90/E92/E93"),
    ("e90 m3", "BMW", "M3", "E90/E92/E93"),
    ("e92 m3", "BMW", "M3", "E90/E92/E93"),
    ("e93 m3", "BMW", "M3", "E90/E92/E93"),
    ("bmw e9x m3", "BMW", "M3", "E90/E92/E93"),
    ("bmw e90 m3", "BMW", "M3", "E90/E92/E93"),
    ("bmw e92 m3", "BMW", "M3", "E90/E92/E93"),
    ("bmw e93 m3", "BMW", "M3", "E90/E92/E93"),
    ("e90/e92/e93 m3", "BMW", "M3", "E90/E92/E93"),
    ("m3 e9x", "BMW", "M3", "E90/E92/E93"),
    ("m3 e90", "BMW", "M3", "E90/E92/E93"),
    ("m3 e92", "BMW", "M3", "E90/E92/E93"),
    ("m3 e93", "BMW", "M3", "E90/E92/E93"),
    ("e91 3 series", "BMW", "3 Series", "E90/E91/E92/E93"),
    ("bmw e91", "BMW", "3 Series", "E90/E91/E92/E93"),
    ("e91 3 series xi", "BMW", "3 Series", "E90/E91/E92/E93"),
    ("3 series e91", "BMW", "3 Series", "E90/E91/E92/E93"),
    ("bmw m2 g87", "BMW", "M2", "G87"),
    ("m2 g87", "BMW", "M2", "G87"),
    ("g87 m2", "BMW", "M2", "G87"),
    ("m2 g8x", "BMW", "M2", "G87"),
    ("bmw m2", "BMW", "M2", "G87"),
    ("m3, m4 g8x", "BMW", "M3", "G80"),
    ("m3/m4 g8x", "BMW", "M3", "G80"),
    ("m3/m4 g8x", "BMW", "M4", "G82/G83"),
    ("bmw m3/m4", "BMW", "M3", "G80"),
    ("bmw m3/m4", "BMW", "M4", "G82/G83"),
    ("z4 g29", "BMW", "Z4", "G29"),
    ("bmw z4 g29", "BMW", "Z4", "G29"),
    ("g29 z4", "BMW", "Z4", "G29"),
    ("10th gen civic", "Honda", "Civic", "10th Gen"),
    ("civic 10th gen", "Honda", "Civic", "10th Gen"),
    ("10th gen", "Honda", "Civic", "10th Gen"),
    ("fk8", "Honda", "Civic Type R", "FK8"),
    ("fk8 civic", "Honda", "Civic Type R", "FK8"),
    ("fl5", "Honda", "Civic Type R", "FL5"),
    ("fl5 civic", "Honda", "Civic Type R", "FL5"),
    ("gr corolla", "Toyota", "GR Corolla", "1st Gen"),
    ("corolla gr", "Toyota", "GR Corolla", "1st Gen"),
    ("gr corolla e210", "Toyota", "GR Corolla", "1st Gen"),
    ("toyota gr corolla", "Toyota", "GR Corolla", "1st Gen"),
    ("toyota gr 86", "Toyota", "GR86", "ZN8"),
    ("gr 86", "Toyota", "GR86", "ZN8"),
    ("gr86", "Toyota", "GR86", "ZN8"),
    ("toyota gr86", "Toyota", "GR86", "ZN8"),
    ("brz/gr86", "Subaru", "BRZ", "ZC6"),
    ("brz/gr86", "Toyota", "86", "ZN6"),
    ("brz/gr86", "Subaru", "BRZ", "ZD8"),
    ("brz/gr86", "Toyota", "GR86", "ZN8"),
    ("gr86 - brz", "Toyota", "GR86", "ZN8"),
    ("gr86 - brz", "Subaru", "BRZ", "ZD8"),
    ("i4 m50", "BMW", "i4 M50", "G26"),
    ("i4 g26", "BMW", "i4 M50", "G26"),
    ("bmw i4 m50", "BMW", "i4 M50", "G26"),
    ("bmw i4 g26", "BMW", "i4 M50", "G26"),
    ("mk4 supra", "Toyota", "Supra", "A80"),
    ("mkiv supra", "Toyota", "Supra", "A80"),
    ("mkiv toyota supra", "Toyota", "Supra", "A80"),
    ("toyota supra mk4", "Toyota", "Supra", "A80"),
    ("supra mk4", "Toyota", "Supra", "A80"),
    ("a80 supra", "Toyota", "Supra", "A80"),
    ("supra a80", "Toyota", "Supra", "A80"),
    ("miata na", "Mazda", "Miata", "NA"),
    ("na miata", "Mazda", "Miata", "NA"),
    ("mx-5 na", "Mazda", "Miata", "NA"),
    ("mx5 na", "Mazda", "Miata", "NA"),
    ("mk1 miata", "Mazda", "Miata", "NA"),
    ("miata mk1", "Mazda", "Miata", "NA"),
    ("miata nb", "Mazda", "Miata", "NB"),
    ("nb miata", "Mazda", "Miata", "NB"),
    ("mx-5 nb", "Mazda", "Miata", "NB"),
    ("mx5 nb", "Mazda", "Miata", "NB"),
    ("mk2 miata", "Mazda", "Miata", "NB"),
    ("miata mk2", "Mazda", "Miata", "NB"),
    ("miata nc", "Mazda", "Miata", "NC"),
    ("nc miata", "Mazda", "Miata", "NC"),
    ("mx-5 nc", "Mazda", "Miata", "NC"),
    ("mx5 nc", "Mazda", "Miata", "NC"),
    ("mk3 miata", "Mazda", "Miata", "NC"),
    ("miata mk3", "Mazda", "Miata", "NC"),
    ("miata nd", "Mazda", "Miata", "ND"),
    ("nd miata", "Mazda", "Miata", "ND"),
    ("mx-5 nd", "Mazda", "Miata", "ND"),
    ("mx5 nd", "Mazda", "Miata", "ND"),
    ("mk4 miata", "Mazda", "Miata", "ND"),
    ("miata mk4", "Mazda", "Miata", "ND"),
    ("fb rx-7", "Mazda", "RX-7", "SA/FB"),
    ("rx-7 fb", "Mazda", "RX-7", "SA/FB"),
    ("fb rx7", "Mazda", "RX-7", "SA/FB"),
    ("rx7 fb", "Mazda", "RX-7", "SA/FB"),
    ("sa22c rx-7", "Mazda", "RX-7", "SA/FB"),
    ("1st gen rx-7", "Mazda", "RX-7", "SA/FB"),
    ("1st gen rx7", "Mazda", "RX-7", "SA/FB"),
    ("2nd gen rx-7", "Mazda", "RX-7", "FC"),
    ("2nd gen rx7", "Mazda", "RX-7", "FC"),
    ("3rd gen rx-7", "Mazda", "RX-7", "FD"),
    ("3rd gen rx7", "Mazda", "RX-7", "FD"),
    ("charger lb", "Dodge", "Charger", "LB"),
    ("dodge charger lb", "Dodge", "Charger", "LB"),
    ("huracan evo", "Lamborghini", "Huracán", "EVO"),
    ("huracán evo", "Lamborghini", "Huracán", "EVO"),
    ("genesis g90", "Genesis", "G90", "1st Gen"),
    ("g90 genesis", "Genesis", "G90", "1st Gen"),
    ("g90 hi", "Genesis", "G90", "1st Gen"),
    ("genesis g90 hi", "Genesis", "G90", "1st Gen"),
    ("g90 rs4", "Genesis", "G90", "2nd Gen"),
    ("genesis g90 rs4", "Genesis", "G90", "2nd Gen"),
    ("genesis g70", "Genesis", "G70", "RG"),
    ("genesis g70 fl", "Genesis", "G70", "RG"),
    ("genesis g80", "Genesis", "G80", "RG3"),
    ("i7 m70", "BMW", "i7 M70", "G70"),
    ("bmw i7 m70", "BMW", "i7 M70", "G70"),
    ("g80 m3", "BMW", "M3", "G80"),
    ("bmw g80 m3", "BMW", "M3", "G80"),
    ("m3 (g80)", "BMW", "M3", "G80"),
    ("m4 (g82)", "BMW", "M4", "G82/G83"),
    ("m4 (g83)", "BMW", "M4", "G82/G83"),
    ("m2 (g87)", "BMW", "M2", "G87"),
    ("golf mk4", "Volkswagen", "Golf", "Mk4"),
    ("jetta mk4", "Volkswagen", "Jetta", "Mk4"),
    ("r32 mk4", "Volkswagen", "R32", "Mk4"),
    ("vw golf mk4", "Volkswagen", "Golf", "Mk4"),
    ("vw jetta mk4", "Volkswagen", "Jetta", "Mk4"),
    ("golf mk6", "Volkswagen", "Golf", "Mk6"),
    ("golf (mk6)", "Volkswagen", "Golf", "Mk6"),
    ("gti mk6", "Volkswagen", "GTI", "Mk6"),
    ("gti (mk6)", "Volkswagen", "GTI", "Mk6"),
    ("jetta mk6", "Volkswagen", "Jetta", "Mk6"),
    ("jetta (mk6)", "Volkswagen", "Jetta", "Mk6"),
    ("golf r mk6", "Volkswagen", "Golf R", "Mk6"),
    ("vw mk6", "Volkswagen", "Golf", "Mk6"),
    ("vw golf mk6", "Volkswagen", "Golf", "Mk6"),
    ("vw gti mk6", "Volkswagen", "GTI", "Mk6"),
    ("fiesta mk6", "Ford", "Fiesta", "Mk6"),
    ("ford fiesta mk6", "Ford", "Fiesta", "Mk6"),
    ("golf mk7", "Volkswagen", "Golf", "Mk7"),
    ("golf (mk7)", "Volkswagen", "Golf", "Mk7"),
    ("gti mk7", "Volkswagen", "GTI", "Mk7"),
    ("gti (mk7)", "Volkswagen", "GTI", "Mk7"),
    ("jetta mk7", "Volkswagen", "Jetta", "Mk7"),
    ("jetta (mk7)", "Volkswagen", "Jetta", "Mk7"),
    ("golf r mk7", "Volkswagen", "Golf R", "Mk7"),
    ("golf r (mk7)", "Volkswagen", "Golf R", "Mk7"),
    ("golf mk7.5", "Volkswagen", "Golf", "Mk7"),
    ("golf (mk7.5)", "Volkswagen", "Golf", "Mk7"),
    ("gti mk7.5", "Volkswagen", "GTI", "Mk7"),
    ("gti (mk7.5)", "Volkswagen", "GTI", "Mk7"),
    ("golf r mk7.5", "Volkswagen", "Golf R", "Mk7"),
    ("vw mk7", "Volkswagen", "Golf", "Mk7"),
    ("vw golf mk7", "Volkswagen", "Golf", "Mk7"),
    ("vw gti mk7", "Volkswagen", "GTI", "Mk7"),
    ("vw golf r mk7", "Volkswagen", "Golf R", "Mk7"),
    ("fiesta mk7", "Ford", "Fiesta", "Mk7"),
    ("ford fiesta mk7", "Ford", "Fiesta", "Mk7"),
    ("fiesta st mk7", "Ford", "Fiesta ST", "Mk7"),
    ("b58 supra", "Toyota", "Supra", "A90"),
    ("supra b58", "Toyota", "Supra", "A90"),
    ("b58 m340", "BMW", "M340i", "G20/G21"),
    ("b58 m440", "BMW", "M440i", "G22/G23/G26"),
    ("b58 z4", "BMW", "Z4", "G29"),
    ("z4 b58", "BMW", "Z4", "G29"),
    ("gen 2 b58 bmw", "BMW", "M340i", "G20/G21"),
    ("g chassis gen 2 b58", "BMW", "M340i", "G20/G21"),
    ("m340i", "BMW", "M340i", "G20/G21"),
    ("m340 i", "BMW", "M340i", "G20/G21"),
    ("m340i b58", "BMW", "M340i", "G20/G21"),
    ("m440i", "BMW", "M440i", "G22/G23/G26"),
    ("m440 i", "BMW", "M440i", "G22/G23/G26"),
    ("m440i b58", "BMW", "M440i", "G22/G23/G26"),
    ("bmw m240i", "BMW", "M240i", "F22/F23"),
    ("bmw m240i", "BMW", "M240i", "G42"),
    ("m240i", "BMW", "M240i", "F22/F23"),
    ("m240i", "BMW", "M240i", "G42"),
    ("m240 i", "BMW", "M240i", "F22/F23"),
    ("m240 i", "BMW", "M240i", "G42"),
    ("bmw (g20", "BMW", "3 Series", "G20/G21"),
    ("bmw (g21", "BMW", "3 Series", "G20/G21"),
    ("g21 g22", "BMW", "4 Series", "G22/G23/G26"),
    ("bmw (g22", "BMW", "4 Series", "G22/G23/G26"),
    ("bmw (g23", "BMW", "4 Series", "G22/G23/G26"),
    ("bmw g20", "BMW", "3 Series", "G20/G21"),
    ("bmw g21", "BMW", "3 Series", "G20/G21"),
    ("bmw g22", "BMW", "4 Series", "G22/G23/G26"),
    ("bmw g23", "BMW", "4 Series", "G22/G23/G26"),
    ("r8 42", "Audi", "R8", "Mk1"),
    ("r8 type 42", "Audi", "R8", "Mk1"),
    ("audi r8 42", "Audi", "R8", "Mk1"),
    ("audi r8 type 42", "Audi", "R8", "Mk1"),
    ("42 r8", "Audi", "R8", "Mk1"),
    ("r8 4s", "Audi", "R8", "Mk2"),
    ("audi r8 4s", "Audi", "R8", "Mk2"),
    ("rs2 avant b4", "Audi", "RS2 Avant", "1st Gen"),
    ("audi rs2 b4", "Audi", "RS2 Avant", "1st Gen"),
    ("camry v10", "Toyota", "Camry", "1st Gen"),
    ("v10 camry", "Toyota", "Camry", "1st Gen"),
    ("camry v20", "Toyota", "Camry", "2nd Gen"),
    ("v20 camry", "Toyota", "Camry", "2nd Gen"),
    ("ferrari ff", "Ferrari", "FF", "1st Gen"),
    ("ff ferrari", "Ferrari", "FF", "1st Gen"),
    ("mclaren p1", "McLaren", "P1", "1st Gen"),
    ("p1 mclaren", "McLaren", "P1", "1st Gen"),
    ("bmw f12 m6", "BMW", "M6", "F12/F13/F06"),
    ("f12 m6", "BMW", "M6", "F12/F13/F06"),
    ("m6 f12", "BMW", "M6", "F12/F13/F06"),
    ("f13 m6", "BMW", "M6", "F12/F13/F06"),
    ("m6 f13", "BMW", "M6", "F12/F13/F06"),
    ("m3 ( e90 / e92", "BMW", "M3", "E90/E92/E93"),
    ("m3 ( e90", "BMW", "M3", "E90/E92/E93"),
    ("m3 ( e92", "BMW", "M3", "E90/E92/E93"),
    ("m3 ( e93", "BMW", "M3", "E90/E92/E93"),
    ("e46 m3", "BMW", "M3", "E46"),
    ("m3 e46", "BMW", "M3", "E46"),
    ("e46 3 series", "BMW", "3 Series", "E46"),
    ("3 series e46", "BMW", "3 Series", "E46"),
    ("e46 330i", "BMW", "330i", "E46"),
    ("330i e46", "BMW", "330i", "E46"),
    ("e36 m3", "BMW", "M3", "E36"),
    ("m3 e36", "BMW", "M3", "E36"),
    ("e36 3 series", "BMW", "3 Series", "E36"),
    ("3 series e36", "BMW", "3 Series", "E36"),
    ("e8x z4m", "BMW", "Z4 M", "E85/E86"),
    ("e8x z4 m", "BMW", "Z4 M", "E85/E86"),
    ("e85 z4m", "BMW", "Z4 M", "E85/E86"),
    ("e86 z4m", "BMW", "Z4 M", "E85/E86"),
    ("e85 z4 m", "BMW", "Z4 M", "E85/E86"),
    ("e86 z4 m", "BMW", "Z4 M", "E85/E86"),
    ("z4m e85", "BMW", "Z4 M", "E85/E86"),
    ("z4m e86", "BMW", "Z4 M", "E85/E86"),
    ("z4 m e85", "BMW", "Z4 M", "E85/E86"),
    ("z4 m e86", "BMW", "Z4 M", "E85/E86"),
    ("bmw z4m", "BMW", "Z4 M", "E85/E86"),
    ("e6x m6", "BMW", "M6", "E63/E64"),
    ("m6 e63", "BMW", "M6", "E63/E64"),
    ("m6 e64", "BMW", "M6", "E63/E64"),
    ("e63 m6", "BMW", "M6", "E63/E64"),
    ("e64 m6", "BMW", "M6", "E63/E64"),
    ("bmw m6 e63", "BMW", "M6", "E63/E64"),
    ("m6 (f10 / f12", "BMW", "M6", "F12/F13/F06"),
    ("m6 (f10 / f13", "BMW", "M6", "F12/F13/F06"),
    ("f80 m3", "BMW", "M3", "F80"),
    ("m3 f80", "BMW", "M3", "F80"),
    ("bmw f80 m3", "BMW", "M3", "F80"),
    ("f82 m4", "BMW", "M4", "F82/F83"),
    ("m4 f82", "BMW", "M4", "F82/F83"),
    ("bmw f82 m4", "BMW", "M4", "F82/F83"),
    ("m3 f80 / f82 m4", "BMW", "M3", "F80"),
    ("m3 f80 / f82 m4", "BMW", "M4", "F82/F83"),
    ("f8x m3", "BMW", "M3", "F80"),
    ("f8x m4", "BMW", "M4", "F82/F83"),
    ("bmw f8x", "BMW", "M4", "F82/F83"),
    ("f8x m3/m4", "BMW", "M3", "F80"),
    ("f8x m3/m4", "BMW", "M4", "F82/F83"),
    ("f8x m2c", "BMW", "M2", "F87"),
    ("f8x m3 / m4", "BMW", "M3", "F80"),
    ("f8x m3 / m4", "BMW", "M4", "F82/F83"),
    ("f97 x3m", "BMW", "X3 M", "F97"),
    ("x3m f97", "BMW", "X3 M", "F97"),
    ("bmw f97", "BMW", "X3 M", "F97"),
    ("bmw x3m", "BMW", "X3 M", "F97"),
    ("x3 m f97", "BMW", "X3 M", "F97"),
    ("f98 x4m", "BMW", "X4 M", "F98"),
    ("bmw x4m", "BMW", "X4 M", "F98"),
    ("f9x x3m", "BMW", "X3 M", "F97"),
    ("f9x x4m", "BMW", "X4 M", "F98"),
    ("f95 x5m", "BMW", "X5 M", "F95"),
    ("f96 x6m", "BMW", "X6 M", "F96"),
    ("bmw f95", "BMW", "X5 M", "F95"),
    ("x5m / x6m / xm", "BMW", "X5 M", "F95"),
    ("x5m / x6m / xm", "BMW", "X6 M", "F96"),
    ("x5m / x6m / xm", "BMW", "XM", "F95"),
    ("x5m/x6m/xm", "BMW", "X5 M", "F95"),
    ("x5m/x6m/xm", "BMW", "X6 M", "F96"),
    ("x5m/x6m/xm", "BMW", "XM", "F95"),
    ("bmw xm", "BMW", "XM", "F95"),
    ("g90 m5", "BMW", "M5", "G90/G99"),
    ("m5 g90", "BMW", "M5", "G90/G99"),
    ("g99 m5", "BMW", "M5", "G90/G99"),
    ("m5 g99", "BMW", "M5", "G90/G99"),
    ("g9x m5", "BMW", "M5", "G90/G99"),
    ("m5 g9x", "BMW", "M5", "G90/G99"),
    ("bmw g90", "BMW", "M5", "G90/G99"),
    ("bmw g99", "BMW", "M5", "G90/G99"),
    ("f9x m5", "BMW", "M5", "F90"),
    ("f9x m5/m8", "BMW", "M5", "F90"),
    ("f1x m5", "BMW", "M5", "F10"),
    ("f1x m5/m6", "BMW", "M5", "F10"),
    ("f1x m5/m6", "BMW", "M6", "F12/F13/F06"),
    ("f30 3 series", "BMW", "3 Series", "F30/F31/F34"),
    ("f30 3-series", "BMW", "3 Series", "F30/F31/F34"),
    ("f31 3 series", "BMW", "3 Series", "F30/F31/F34"),
    ("f30/f31", "BMW", "3 Series", "F30/F31/F34"),
    ("f30 / f31", "BMW", "3 Series", "F30/F31/F34"),
    ("bmw f30", "BMW", "3 Series", "F30/F31/F34"),
    ("f34 3 series gt", "BMW", "3 Series", "F30/F31/F34"),
    ("f34 gt", "BMW", "3 Series", "F30/F31/F34"),
    ("f32 4 series", "BMW", "4 Series", "F32/F33/F36"),
    ("f32 4-series", "BMW", "4 Series", "F32/F33/F36"),
    ("f33 4 series", "BMW", "4 Series", "F32/F33/F36"),
    ("f36 4 series", "BMW", "4 Series", "F32/F33/F36"),
    ("f32/f33", "BMW", "4 Series", "F32/F33/F36"),
    ("f32 / f33", "BMW", "4 Series", "F32/F33/F36"),
    ("f32 / f36", "BMW", "4 Series", "F32/F33/F36"),
    ("f32/f36", "BMW", "4 Series", "F32/F33/F36"),
    ("f32 f33 f36", "BMW", "4 Series", "F32/F33/F36"),
    ("f22 2 series", "BMW", "2 Series", "F22/F23"),
    ("f22 2-series", "BMW", "2 Series", "F22/F23"),
    ("f23 2 series", "BMW", "2 Series", "F22/F23"),
    ("f22/f23", "BMW", "2 Series", "F22/F23"),
    ("f22 / f23", "BMW", "2 Series", "F22/F23"),
    ("f22 228i", "BMW", "2 Series", "F22/F23"),
    ("f22 m235i", "BMW", "M240i", "F22/F23"),
    ("f22 m240i", "BMW", "M240i", "F22/F23"),
    ("f20 1 series", "BMW", "1 Series", "F20/F21"),
    ("f20 1-series", "BMW", "1 Series", "F20/F21"),
    ("f20/f21", "BMW", "1 Series", "F20/F21"),
    ("f20 / f21", "BMW", "1 Series", "F20/F21"),
    ("bmw f20", "BMW", "1 Series", "F20/F21"),
    ("f06 6 series", "BMW", "M6", "F12/F13/F06"),
    ("f06 m6", "BMW", "M6", "F12/F13/F06"),
    ("m6 f06", "BMW", "M6", "F12/F13/F06"),
    ("f06/f12/f13", "BMW", "M6", "F12/F13/F06"),
    ("f06 / f12 / f13", "BMW", "M6", "F12/F13/F06"),
    ("f06 / f12", "BMW", "M6", "F12/F13/F06"),
    ("f06 / f13", "BMW", "M6", "F12/F13/F06"),
    ("f12 6 series", "BMW", "6 Series", "F12/F13/F06"),
    ("f13 6 series", "BMW", "6 Series", "F12/F13/F06"),
    ("f12 / f13", "BMW", "6 Series", "F12/F13/F06"),
    ("f12 640i", "BMW", "6 Series", "F12/F13/F06"),
    ("e85 / e86", "BMW", "Z4", "E85/E86"),
    ("e85/e86", "BMW", "Z4", "E85/E86"),
    ("e85 z4", "BMW", "Z4", "E85/E86"),
    ("e86 z4", "BMW", "Z4", "E85/E86"),
    ("bmw z4 e85", "BMW", "Z4", "E85/E86"),
    ("z4 (n52)", "BMW", "Z4", "E85/E86"),
    ("e87 1 series", "BMW", "1 Series", "E81/E82/E87/E88"),
    ("e87 1-series", "BMW", "1 Series", "E81/E82/E87/E88"),
    ("bmw e87", "BMW", "1 Series", "E81/E82/E87/E88"),
    ("e88 128i", "BMW", "1 Series", "E81/E82/E87/E88"),
    ("e88 135i", "BMW", "1 Series", "E81/E82/E87/E88"),
    ("e82 128i", "BMW", "1 Series", "E81/E82/E87/E88"),
    ("e82 135i", "BMW", "1 Series", "E81/E82/E87/E88"),
    ("e82 e88 128i", "BMW", "1 Series", "E81/E82/E87/E88"),
    ("e82 e88 135i", "BMW", "1 Series", "E81/E82/E87/E88"),
    ("e82/e88 135i", "BMW", "1 Series", "E81/E82/E87/E88"),
    ("e82/e88 1 series", "BMW", "1 Series", "E81/E82/E87/E88"),
    ("e82/e88", "BMW", "1 Series", "E81/E82/E87/E88"),
    ("bmw 1 series e82", "BMW", "1 Series", "E81/E82/E87/E88"),
    ("1 series (e82)", "BMW", "1 Series", "E81/E82/E87/E88"),
    ("1 series (e88)", "BMW", "1 Series", "E81/E82/E87/E88"),
    ("e90/e91", "BMW", "3 Series", "E90/E91/E92/E93"),
    ("e90 / e91", "BMW", "3 Series", "E90/E91/E92/E93"),
    ("e91 3 series touring", "BMW", "3 Series", "E90/E91/E92/E93"),
    ("e93 328i", "BMW", "3 Series", "E90/E91/E92/E93"),
    ("e93 335i", "BMW", "3 Series", "E90/E91/E92/E93"),
    ("e93 cabrio", "BMW", "3 Series", "E90/E91/E92/E93"),
    ("e90/e92/e93 335i", "BMW", "335i", "E90/E91/E92/E93"),
    ("e92 facelift", "BMW", "3 Series", "E90/E91/E92/E93"),
    ("e93 facelift", "BMW", "3 Series", "E90/E91/E92/E93"),
    ("e36 325", "BMW", "3 Series", "E36"),
    ("e36 325i", "BMW", "3 Series", "E36"),
    ("e36 328", "BMW", "3 Series", "E36"),
    ("e36 328i", "BMW", "3 Series", "E36"),
    ("e36 318", "BMW", "3 Series", "E36"),
    ("e36 318i", "BMW", "3 Series", "E36"),
    ("e36 323", "BMW", "3 Series", "E36"),
    ("e36 323i", "BMW", "3 Series", "E36"),
    ("e36 4 door", "BMW", "3 Series", "E36"),
    ("e36 cabrio", "BMW", "3 Series", "E36"),
    ("e46 323", "BMW", "3 Series", "E46"),
    ("e46 323i", "BMW", "3 Series", "E46"),
    ("e46 325i", "BMW", "3 Series", "E46"),
    ("e46 325xi", "BMW", "3 Series", "E46"),
    ("e46 328", "BMW", "3 Series", "E46"),
    ("e46 328i", "BMW", "3 Series", "E46"),
    ("e46 330ci", "BMW", "330i", "E46"),
    ("e46 330xi", "BMW", "330i", "E46"),
    ("e46 cabrio", "BMW", "3 Series", "E46"),
    ("e46 convertible", "BMW", "3 Series", "E46"),
    ("e46 ci", "BMW", "3 Series", "E46"),
    ("e46 3-series", "BMW", "3 Series", "E46"),
    ("e46 coupe", "BMW", "3 Series", "E46"),
    ("e46 touring", "BMW", "3 Series", "E46"),
    ("e46 (not m3)", "BMW", "3 Series", "E46"),
    ("e36/e46", "BMW", "3 Series", "E36"),
    ("e36/e46", "BMW", "3 Series", "E46"),
    ("e70 x5", "BMW", "X5", "E70"),
    ("e70 x5 35d", "BMW", "X5", "E70"),
    ("e70 35d", "BMW", "X5", "E70"),
    ("bmw e70 x5", "BMW", "X5", "E70"),
    ("e53 x5", "BMW", "X5", "E53"),
    ("bmw e53", "BMW", "X5", "E53"),
    ("f15 x5", "BMW", "X5", "F15"),
    ("bmw f15", "BMW", "X5", "F15"),
    ("g05 x5", "BMW", "X5", "G05"),
    ("bmw g05", "BMW", "X5", "G05"),
    ("e83 x3", "BMW", "X3", "E83"),
    ("bmw e83", "BMW", "X3", "E83"),
    ("f25 x3", "BMW", "X3", "F25"),
    ("bmw f25", "BMW", "X3", "F25"),
    ("g01 x3", "BMW", "X3", "G01"),
    ("bmw g01", "BMW", "X3", "G01"),
    ("f26 x4", "BMW", "X4", "F26"),
    ("bmw f26", "BMW", "X4", "F26"),
    ("g02 x4", "BMW", "X4", "G02"),
    ("bmw g02", "BMW", "X4", "G02"),
    ("f16 x6", "BMW", "X6", "F16"),
    ("bmw f16", "BMW", "X6", "F16"),
    ("g06 x6", "BMW", "X6", "G06"),
    ("f15 x5 / f16 x6", "BMW", "X5", "F15"),
    ("f15 x5 / f16 x6", "BMW", "X6", "F16"),
    ("g07 x7", "BMW", "X7", "G07"),
    ("bmw g07", "BMW", "X7", "G07"),
    ("e84 x1", "BMW", "X1", "E84"),
    ("bmw e84", "BMW", "X1", "E84"),
    ("f48 x1", "BMW", "X1", "F48"),
    ("bmw f48", "BMW", "X1", "F48"),
    ("u11 x1", "BMW", "X1", "U11"),
    ("f39 x2", "BMW", "X2", "F39"),
    ("bmw f39", "BMW", "X2", "F39"),
    ("f44 2 series gran coupe", "BMW", "2 Series Gran Coupe", "F44"),
    ("f44 gran coupe", "BMW", "2 Series Gran Coupe", "F44"),
    ("f44 m235i", "BMW", "2 Series Gran Coupe", "F44"),
    ("g11 7 series", "BMW", "7 Series", "G11/G12"),
    ("g12 7 series", "BMW", "7 Series", "G11/G12"),
    ("g11/g12", "BMW", "7 Series", "G11/G12"),
    ("g11 / g12", "BMW", "7 Series", "G11/G12"),
    ("bmw g11", "BMW", "7 Series", "G11/G12"),
    ("bmw g12", "BMW", "7 Series", "G11/G12"),
    ("e38 7 series", "BMW", "7 Series", "E38"),
    ("e38 740i", "BMW", "7 Series", "E38"),
    ("e38 740il", "BMW", "7 Series", "E38"),
    ("e38 750il", "BMW", "7 Series", "E38"),
    ("bmw e38", "BMW", "7 Series", "E38"),
    ("e32 7 series", "BMW", "7 Series", "E32"),
    ("e32 750il", "BMW", "7 Series", "E32"),
    ("e32 735i", "BMW", "7 Series", "E32"),
    ("bmw e32", "BMW", "7 Series", "E32"),
    ("e23 7 series", "BMW", "7 Series", "E23"),
    ("e23 733i", "BMW", "7 Series", "E23"),
    ("e23 735i", "BMW", "7 Series", "E23"),
    ("bmw e23", "BMW", "7 Series", "E23"),
    ("e65/e66", "BMW", "7 Series", "E65/E66"),
    ("e65 / e66", "BMW", "7 Series", "E65/E66"),
    ("e65 745i", "BMW", "7 Series", "E65/E66"),
    ("e65 745li", "BMW", "7 Series", "E65/E66"),
    ("bmw e65", "BMW", "7 Series", "E65/E66"),
    ("e31 8 series", "BMW", "8 Series", "E31"),
    ("e31 840", "BMW", "8 Series", "E31"),
    ("e31 840ci", "BMW", "8 Series", "E31"),
    ("e31 850", "BMW", "8 Series", "E31"),
    ("e31 850i", "BMW", "8 Series", "E31"),
    ("e31 850ci", "BMW", "8 Series", "E31"),
    ("bmw e31", "BMW", "8 Series", "E31"),
    ("g15 8 series", "BMW", "8 Series", "G14/G15/G16"),
    ("g15 840i", "BMW", "8 Series", "G14/G15/G16"),
    ("bmw g15", "BMW", "8 Series", "G14/G15/G16"),
    ("g14 8 series", "BMW", "8 Series", "G14/G15/G16"),
    ("g16 8 series", "BMW", "8 Series", "G14/G15/G16"),
    ("g30 5 series", "BMW", "5 Series", "G30/G31"),
    ("g30 530i", "BMW", "5 Series", "G30/G31"),
    ("g30 540i", "BMW", "5 Series", "G30/G31"),
    ("e28 528e", "BMW", "5 Series", "E28"),
    ("e28 533i", "BMW", "5 Series", "E28"),
    ("e28 535i", "BMW", "5 Series", "E28"),
    ("bmw e28", "BMW", "5 Series", "E28"),
    ("e34 525i", "BMW", "5 Series", "E34"),
    ("e34 530i", "BMW", "5 Series", "E34"),
    ("e34 535i", "BMW", "5 Series", "E34"),
    ("e34 540i", "BMW", "5 Series", "E34"),
    ("e34 touring", "BMW", "5 Series", "E34"),
    ("bmw e34", "BMW", "5 Series", "E34"),
    ("e39 525i", "BMW", "5 Series", "E39"),
    ("e39 528i", "BMW", "5 Series", "E39"),
    ("e39 530i", "BMW", "5 Series", "E39"),
    ("e39 535i", "BMW", "5 Series", "E39"),
    ("e39 540i", "BMW", "5 Series", "E39"),
    ("e39 545i", "BMW", "5 Series", "E39"),
    ("e39 touring", "BMW", "5 Series", "E39"),
    ("g32 6 series gt", "BMW", "6 Series GT", "G32"),
    ("g32 640i", "BMW", "6 Series GT", "G32"),
    ("e24 635csi", "BMW", "6 Series", "E24"),
    ("e63 6 series", "BMW", "6 Series", "E63/E64"),
    ("e63 6-series", "BMW", "6 Series", "E63/E64"),
    ("e63 645i", "BMW", "6 Series", "E63/E64"),
    ("e63 650i", "BMW", "6 Series", "E63/E64"),
    ("e64 645ci", "BMW", "6 Series", "E63/E64"),
    ("bmw e63", "BMW", "6 Series", "E63/E64"),
    ("bmw e64", "BMW", "6 Series", "E63/E64"),
    ("i01 i3", "BMW", "i3", "I01"),
    ("bmw i3", "BMW", "i3", "I01"),
    ("m340", "BMW", "M340i", "G20/G21"),
    ("m440", "BMW", "M440i", "G22/G23/G26"),
    ("m240ix", "BMW", "M240i", "G42"),
    ("m340ix", "BMW", "M340i", "G20/G21"),
    ("f-chassis", "BMW", "3 Series", "F30/F31/F34"),
    ("f chassis", "BMW", "3 Series", "F30/F31/F34"),
    ("g chassis", "BMW", "3 Series", "G20/G21"),
    ("g-chassis", "BMW", "3 Series", "G20/G21"),
    ("bmw z3 e36/7", "BMW", "Z3", "E36/7 E36/8"),
    ("bmw z3 (e36/7)", "BMW", "Z3", "E36/7 E36/8"),
    ("bmw z3", "BMW", "Z3", "E36/7 E36/8"),
    ("corvette c8", "Chevrolet", "Corvette", "C8"),
    ("c8 corvette", "Chevrolet", "Corvette", "C8"),
    ("chevrolet corvette c8", "Chevrolet", "Corvette", "C8"),
    ("chevy corvette c8", "Chevrolet", "Corvette", "C8"),
    ("rs6 c8", "Audi", "RS6 Avant", "C8"),
    ("audi rs6 c8", "Audi", "RS6 Avant", "C8"),
    ("c8 rs6", "Audi", "RS6 Avant", "C8"),
    ("rs7 c8", "Audi", "RS7 Sportback", "C8"),
    ("audi rs7 c8", "Audi", "RS7 Sportback", "C8"),
    ("c8 rs7", "Audi", "RS7 Sportback", "C8"),
    ("s6 c8", "Audi", "S6", "C8"),
    ("audi s6 c8", "Audi", "S6", "C8"),
    ("s7 c8", "Audi", "S7 Sportback", "C8"),
    ("audi s7 c8", "Audi", "S7 Sportback", "C8"),
    ("c5 corvette", "Chevrolet", "Corvette", "C5"),
    ("corvette c5", "Chevrolet", "Corvette", "C5"),
    ("chevy c5", "Chevrolet", "Corvette", "C5"),
    ("chevrolet c5", "Chevrolet", "Corvette", "C5"),
    ("c5 z06", "Chevrolet", "Corvette", "C5"),
    ("rs6 c5", "Audi", "RS6 Avant", "C5"),
    ("audi rs6 c5", "Audi", "RS6 Avant", "C5"),
    ("c5 rs6", "Audi", "RS6 Avant", "C5"),
    ("s6 c5", "Audi", "S6", "C5"),
    ("audi s6 c5", "Audi", "S6", "C5"),
    ("c5 s6", "Audi", "S6", "C5"),
    ("c6 corvette", "Chevrolet", "Corvette", "C6"),
    ("corvette c6", "Chevrolet", "Corvette", "C6"),
    ("chevy c6", "Chevrolet", "Corvette", "C6"),
    ("chevrolet c6", "Chevrolet", "Corvette", "C6"),
    ("c6 z06", "Chevrolet", "Corvette", "C6"),
    ("c6 zr1", "Chevrolet", "Corvette", "C6"),
    ("rs6 c6", "Audi", "RS6 Avant", "C6"),
    ("audi rs6 c6", "Audi", "RS6 Avant", "C6"),
    ("c6 rs6", "Audi", "RS6 Avant", "C6"),
    ("s6 c6", "Audi", "S6", "C6"),
    ("audi s6 c6", "Audi", "S6", "C6"),
    ("c6 s6", "Audi", "S6", "C6"),
    ("c7 corvette", "Chevrolet", "Corvette", "C7"),
    ("corvette c7", "Chevrolet", "Corvette", "C7"),
    ("chevy c7", "Chevrolet", "Corvette", "C7"),
    ("chevrolet c7", "Chevrolet", "Corvette", "C7"),
    ("c7 z06", "Chevrolet", "Corvette", "C7"),
    ("c7 zo6", "Chevrolet", "Corvette", "C7"),
    ("c7 zr1", "Chevrolet", "Corvette", "C7"),
    ("c7/c7 z06", "Chevrolet", "Corvette", "C7"),
    ("rs6 c7", "Audi", "RS6 Avant", "C7"),
    ("audi rs6 c7", "Audi", "RS6 Avant", "C7"),
    ("c7 rs6", "Audi", "RS6 Avant", "C7"),
    ("rs7 c7", "Audi", "RS7 Sportback", "C7"),
    ("audi rs7 c7", "Audi", "RS7 Sportback", "C7"),
    ("c7 rs7", "Audi", "RS7 Sportback", "C7"),
    ("s6 c7", "Audi", "S6", "C7"),
    ("audi s6 c7", "Audi", "S6", "C7"),
    ("c7 s6", "Audi", "S6", "C7"),
    ("s7 c7", "Audi", "S7 Sportback", "C7"),
    ("audi s7 c7", "Audi", "S7 Sportback", "C7"),
    ("c7 s7", "Audi", "S7 Sportback", "C7"),
    ("bmw e70", "BMW", "X5 M", "E70"),
    ("e70 x5m", "BMW", "X5 M", "E70"),
    ("x5m e70", "BMW", "X5 M", "E70"),
    ("e70 x5 m", "BMW", "X5 M", "E70"),
    ("x5 m e70", "BMW", "X5 M", "E70"),
    ("corolla e70", "Toyota", "Corolla", "E70"),
    ("e70 corolla", "Toyota", "Corolla", "E70"),
    ("toyota e70", "Toyota", "Corolla", "E70"),
    ("ferrari f40", "Ferrari", "F40", "F40"),
    ("f40 ferrari", "Ferrari", "F40", "F40"),
    ("bmw f40", "BMW", "1 Series", "F40"),
    ("f40 bmw", "BMW", "1 Series", "F40"),
    ("bmw 1 series f40", "BMW", "1 Series", "F40"),
    ("panamera 970", "Porsche", "Panamera", "970"),
    ("970 panamera", "Porsche", "Panamera", "970"),
    ("porsche panamera 970", "Porsche", "Panamera", "970"),
    ("i5 m60", "BMW", "i5 M60", "G60"),
    ("bmw i5", "BMW", "i5 M60", "G60"),
    ("m60 i5", "BMW", "i5 M60", "G60"),
    ("bmw g60", "BMW", "i5 M60", "G60"),
    ("g60 m5", "BMW", "i5 M60", "G60"),
    ("g60 5-series", "BMW", "i5 M60", "G60"),
    ("corrado g60", "Volkswagen", "Corrado", "G60"),
    ("vw corrado", "Volkswagen", "Corrado", "G60"),
    ("volkswagen corrado", "Volkswagen", "Corrado", "G60"),
    ("992 gt3", "Porsche", "911", "992"),
    ("992.1 gt3", "Porsche", "911", "992"),
    ("992.2 gt3", "Porsche", "911", "992"),
    ("porsche 992", "Porsche", "911", "992"),
    ("porsche 991", "Porsche", "911", "991"),
    ("991 gt3", "Porsche", "911", "991"),
    ("991.1 gt3", "Porsche", "911", "991"),
    ("991.2 gt3", "Porsche", "911", "991"),
    ("991 turbo", "Porsche", "911", "991"),
    ("porsche 718", "Porsche", "718", "982"),
    ("718 boxster", "Porsche", "718", "982"),
    ("718 cayman", "Porsche", "718", "982"),
    ("718 gt4", "Porsche", "718", "982"),
    ("718 spyder", "Porsche", "718", "982"),
    ("porsche 918", "Porsche", "918 Spyder", "918 Spyder"),
    ("918 spyder", "Porsche", "918 Spyder", "918 Spyder"),
    ("porsche 918 spyder", "Porsche", "918 Spyder", "918 Spyder"),
    ("carrera gt", "Porsche", "Carrera GT", "Carrera GT"),
    ("porsche carrera gt", "Porsche", "Carrera GT", "Carrera GT"),
    ("cgt", "Porsche", "Carrera GT", "Carrera GT"),
    ("cayenne 955", "Porsche", "Cayenne", "9PA"),
    ("cayenne 957", "Porsche", "Cayenne", "9PA"),
    ("955 cayenne", "Porsche", "Cayenne", "9PA"),
    ("957 cayenne", "Porsche", "Cayenne", "9PA"),
    ("cayenne 958", "Porsche", "Cayenne", "92A"),
    ("958 cayenne", "Porsche", "Cayenne", "92A"),
    ("cayenne 9pa", "Porsche", "Cayenne", "9PA"),
    ("porsche 9pa", "Porsche", "Cayenne", "9PA"),
    ("porsche 92a", "Porsche", "Cayenne", "92A"),
    ("cayenne 9y0", "Porsche", "Cayenne", "PO536"),
    ("9y0 cayenne", "Porsche", "Cayenne", "PO536"),
    ("cayenne 2019+", "Porsche", "Cayenne", "PO536"),
    ("porsche cayenne", "Porsche", "Cayenne", "9PA"),
    ("porsche cayenne", "Porsche", "Cayenne", "92A"),
    ("2003-2008 cayenne", "Porsche", "Cayenne", "9PA"),
    ("996tt", "Porsche", "911", "996"),
    ("997tt", "Porsche", "911", "997"),
    ("996 turbo", "Porsche", "911", "996"),
    ("997 turbo", "Porsche", "911", "997"),
    ("987s", "Porsche", "Cayman", "987"),
    ("987s", "Porsche", "Boxster", "987"),
    ("tesla model 3", "Tesla", "Model 3", "Pre-Highland"),
    ("model 3 highland", "Tesla", "Model 3", "Highland"),
    ("tesla model 3 highland", "Tesla", "Model 3", "Highland"),
    ("model 3 performance", "Tesla", "Model 3", "Highland"),
    ("model 3 highland performance", "Tesla", "Model 3", "Highland"),
    ("tesla model y", "Tesla", "Model Y", "1st Gen"),
    ("model y juniper", "Tesla", "Model Y", "Juniper"),
    ("tesla model y juniper", "Tesla", "Model Y", "Juniper"),
    ("model y performance", "Tesla", "Model Y", "1st Gen"),
    ("tesla model s", "Tesla", "Model S", "Pre-Refresh"),
    ("model s plaid", "Tesla", "Model S", "Plaid"),
    ("tesla model s plaid", "Tesla", "Model S", "Plaid"),
    ("tesla model x", "Tesla", "Model X", "Pre-Refresh"),
    ("model x plaid", "Tesla", "Model X", "Plaid"),
    ("kia stinger", "Kia", "Stinger", "CK"),
    ("stinger gt", "Kia", "Stinger", "CK"),
    ("stinger ck", "Kia", "Stinger", "CK"),
    ("gr yaris", "Toyota", "GR Yaris", "1st Gen"),
    ("toyota gr yaris", "Toyota", "GR Yaris", "1st Gen"),
    ("yaris gr", "Toyota", "GR Yaris", "1st Gen"),
    ("gen 2 gr yaris", "Toyota", "GR Yaris", "2nd Gen"),
    ("2nd gen gr yaris", "Toyota", "GR Yaris", "2nd Gen"),
    ("gr yaris gen 2", "Toyota", "GR Yaris", "2nd Gen"),
    ("gr yaris 2nd gen", "Toyota", "GR Yaris", "2nd Gen"),
    ("gr yaris (gen 2)", "Toyota", "GR Yaris", "2nd Gen"),
    ("2024 gr yaris", "Toyota", "GR Yaris", "2nd Gen"),
    ("2025 gr yaris", "Toyota", "GR Yaris", "2nd Gen"),
    ("gr yaris (gen 1 & 2)", "Toyota", "GR Yaris", "2nd Gen"),
    ("gr yaris gen 1 & 2", "Toyota", "GR Yaris", "2nd Gen"),
    ("gr yaris (gen 1 and 2)", "Toyota", "GR Yaris", "2nd Gen"),
    ("gr yaris gen 1 and 2", "Toyota", "GR Yaris", "2nd Gen"),
    ("subaru brz", "Subaru", "BRZ", "ZC6"),
    ("subaru brz", "Subaru", "BRZ", "ZD8"),
    ("brz zd8", "Subaru", "BRZ", "ZD8"),
    ("zd8 brz", "Subaru", "BRZ", "ZD8"),
    ("22+ brz", "Subaru", "BRZ", "ZD8"),
    ("22+ gr86", "Toyota", "GR86", "ZN8"),
    ("2023+ g87", "BMW", "M2", "G87"),
    ("fl5 civic type r", "Honda", "Civic Type R", "FL5"),
    ("honda fl5", "Honda", "Civic Type R", "FL5"),
    ("fk8 civic type r", "Honda", "Civic Type R", "FK8"),
    ("elantra n", "Hyundai", "Elantra N", "CN7"),
    ("hyundai elantra n", "Hyundai", "Elantra N", "CN7"),
    ("elantra n pe", "Hyundai", "Elantra N", "CN7"),
    ("veloster n", "Hyundai", "Veloster", "JS"),
    ("hyundai veloster n", "Hyundai", "Veloster", "JS"),
    ("genesis gv70", "Genesis", "GV70", "JK1"),
    ("gv70", "Genesis", "GV70", "JK1"),
    ("s550", "Ford", "Mustang", "6th Gen"),
    ("mustang s550", "Ford", "Mustang", "6th Gen"),
    ("s650", "Ford", "Mustang", "7th Gen"),
    ("mustang s650", "Ford", "Mustang", "7th Gen"),
    ("s197", "Ford", "Mustang", "5th Gen"),
    ("2015-2023 mustang", "Ford", "Mustang", "6th Gen"),
    ("2015+ mustang", "Ford", "Mustang", "6th Gen"),
    ("2015-2020 mustang", "Ford", "Mustang", "6th Gen"),
    ("2024+ mustang", "Ford", "Mustang", "7th Gen"),
    ("2024 mustang", "Ford", "Mustang", "7th Gen"),
    ("fox body mustang", "Ford", "Mustang", "3rd Gen"),
    ("fox body", "Ford", "Mustang", "3rd Gen"),
    ("sn95 mustang", "Ford", "Mustang", "4th Gen"),
    ("sn95", "Ford", "Mustang", "4th Gen"),
    ("5.0 mustang", "Ford", "Mustang", "6th Gen"),
    ("gt500", "Ford", "Mustang", "5th Gen"),
    ("gt500", "Ford", "Mustang", "6th Gen"),
    ("shelby gt500", "Ford", "Mustang", "5th Gen"),
    ("shelby gt500", "Ford", "Mustang", "6th Gen"),
    ("dark horse", "Ford", "Mustang", "7th Gen"),
    ("boss 302 mustang", "Ford", "Mustang", "5th Gen"),
    ("mustang boss 302", "Ford", "Mustang", "5th Gen"),
    ("bullitt mustang", "Ford", "Mustang", "5th Gen"),
    ("mustang bullitt", "Ford", "Mustang", "5th Gen"),
    ("mach 1 mustang", "Ford", "Mustang", "5th Gen"),
    ("mustang mach 1", "Ford", "Mustang", "5th Gen"),
    ("svt cobra", "Ford", "Mustang", "4th Gen"),
    ("mustang cobra", "Ford", "Mustang", "4th Gen"),
    ("terminator cobra", "Ford", "Mustang", "4th Gen"),
    ("gt350 mustang", "Ford", "Mustang", "6th Gen"),
    ("shelby gt350", "Ford", "Mustang", "6th Gen"),
    ("mustang gt350", "Ford", "Mustang", "6th Gen"),
    ("shelby gt350r", "Ford", "Mustang", "6th Gen"),
    ("gt350r", "Ford", "Mustang", "6th Gen"),
    ("focus svt", "Ford", "Focus", "Mk1"),
    ("svt focus", "Ford", "Focus", "Mk1"),
    ("1979-2004 mustang", "Ford", "Mustang", "3rd Gen"),
    ("1979-2004 mustang", "Ford", "Mustang", "4th Gen"),
    ("1979-1993 mustang", "Ford", "Mustang", "3rd Gen"),
    ("1994-2004 mustang", "Ford", "Mustang", "4th Gen"),
    ("1996-2004 mustang", "Ford", "Mustang", "4th Gen"),
    ("1996-2004 ford mustang", "Ford", "Mustang", "4th Gen"),
    ("1999-2004 mustang", "Ford", "Mustang", "4th Gen"),
    ("1999-2004 ford mustang", "Ford", "Mustang", "4th Gen"),
    ("2001 ford mustang cobra", "Ford", "Mustang", "4th Gen"),
    ("2003-2004 ford mustang cobra", "Ford", "Mustang", "4th Gen"),
    ("2003-2004 mustang cobra", "Ford", "Mustang", "4th Gen"),
    ("2001-2004 ford cobra", "Ford", "Mustang", "4th Gen"),
    ("2002-2004 ford mustang gt", "Ford", "Mustang", "4th Gen"),
    ("2005-2010 mustang", "Ford", "Mustang", "5th Gen"),
    ("2005-2010 ford mustang", "Ford", "Mustang", "5th Gen"),
    ("2005-2014 mustang", "Ford", "Mustang", "5th Gen"),
    ("2010-2014 mustang", "Ford", "Mustang", "5th Gen"),
    ("2011-2014 mustang", "Ford", "Mustang", "5th Gen"),
    ("2011-2014 ford mustang", "Ford", "Mustang", "5th Gen"),
    ("2011-14 mustang", "Ford", "Mustang", "5th Gen"),
    ("2015-2017 mustang", "Ford", "Mustang", "6th Gen"),
    ("2015-2017 ford mustang", "Ford", "Mustang", "6th Gen"),
    ("2015-17 mustang", "Ford", "Mustang", "6th Gen"),
    ("2016+ ford mustang", "Ford", "Mustang", "6th Gen"),
    ("2018-2023 mustang", "Ford", "Mustang", "6th Gen"),
    ("2018+ ford mustang", "Ford", "Mustang", "6th Gen"),
    ("2018 ford mustang gt", "Ford", "Mustang", "6th Gen"),
    ("2015-2017 mustang gt", "Ford", "Mustang", "6th Gen"),
    ("2015-2017 mustang ecoboost", "Ford", "Mustang", "6th Gen"),
    ("2015+ mustang ecoboost", "Ford", "Mustang", "6th Gen"),
    ("2015+ ford mustang shelby gt350", "Ford", "Mustang", "6th Gen"),
    ("2016+ ford mustang shelby gt350", "Ford", "Mustang", "6th Gen"),
    ("mustang shelby gt350", "Ford", "Mustang", "6th Gen"),
    ("new edge mustang", "Ford", "Mustang", "4th Gen"),
    ("new edge", "Ford", "Mustang", "4th Gen"),
    ("s197.1 mustang", "Ford", "Mustang", "5th Gen"),
    ("s197.2 mustang", "Ford", "Mustang", "5th Gen"),
    ("s550.1 mustang", "Ford", "Mustang", "6th Gen"),
    ("s550.2 mustang", "Ford", "Mustang", "6th Gen"),
    ("1999-2004 ford svt lightning", "Ford", "F-150", "10th Gen"),
    ("ford svt lightning", "Ford", "F-150", "10th Gen"),
    ("ford bronco", "Ford", "Bronco", "6th Gen"),
    ("2021+ ford bronco", "Ford", "Bronco", "6th Gen"),
    ("2021-2025 ford bronco", "Ford", "Bronco", "6th Gen"),
    ("bronco raptor", "Ford", "Bronco", "6th Gen"),
    ("ford maverick", "Ford", "Maverick", "1st Gen"),
    ("bronco sport", "Ford", "Bronco Sport", "1st Gen"),
    ("ranger raptor", "Ford", "Ranger Raptor", "1st Gen"),
    ("ford ranger raptor", "Ford", "Ranger Raptor", "1st Gen"),
    ("2024 ford ranger raptor", "Ford", "Ranger Raptor", "1st Gen"),
    ("ranger t6", "Ford", "Ranger", "T6"),
    ("ford ranger t6", "Ford", "Ranger", "T6"),
    ("ford ranger", "Ford", "Ranger", "T6"),
    ("ford f-150", "Ford", "F-150", "13th Gen"),
    ("ford f-150", "Ford", "F-150", "14th Gen"),
    ("f-150 ecoboost raptor", "Ford", "F-150 Raptor", "3rd Gen"),
    ("f-150 raptor", "Ford", "F-150 Raptor", "3rd Gen"),
    ("fiesta st", "Ford", "Fiesta ST", "Mk7"),
    ("ford fiesta st", "Ford", "Fiesta ST", "Mk7"),
    ("2015-2020 f-150", "Ford", "F-150", "13th Gen"),
    ("2015-2020 ford f-150", "Ford", "F-150", "13th Gen"),
    ("2015+ f-150", "Ford", "F-150", "13th Gen"),
    ("2015-2022 f-150", "Ford", "F-150", "13th Gen"),
    ("2021+ f-150", "Ford", "F-150", "14th Gen"),
    ("2021-2023 f-150", "Ford", "F-150", "14th Gen"),
    ("2009-2014 f-150", "Ford", "F-150", "12th Gen"),
    ("2009-2014 ford f-150", "Ford", "F-150", "12th Gen"),
    ("2015-2020 f150", "Ford", "F-150", "13th Gen"),
    ("2021+ f150", "Ford", "F-150", "14th Gen"),
    ("evo i", "Mitsubishi", "Lancer Evolution", "I"),
    ("evo 1", "Mitsubishi", "Lancer Evolution", "I"),
    ("evo ii", "Mitsubishi", "Lancer Evolution", "II"),
    ("evo 2", "Mitsubishi", "Lancer Evolution", "II"),
    ("evo iii", "Mitsubishi", "Lancer Evolution", "III"),
    ("evo 3", "Mitsubishi", "Lancer Evolution", "III"),
    ("evo iv", "Mitsubishi", "Lancer Evolution", "IV"),
    ("evo 4", "Mitsubishi", "Lancer Evolution", "IV"),
    ("evo v", "Mitsubishi", "Lancer Evolution", "V"),
    ("evo 5", "Mitsubishi", "Lancer Evolution", "V"),
    ("evo vi", "Mitsubishi", "Lancer Evolution", "VI"),
    ("evo 6", "Mitsubishi", "Lancer Evolution", "VI"),
    ("evo vii", "Mitsubishi", "Lancer Evolution", "VII"),
    ("evo 7", "Mitsubishi", "Lancer Evolution", "VII"),
    ("evo viii", "Mitsubishi", "Lancer Evolution", "VIII"),
    ("evo 8", "Mitsubishi", "Lancer Evolution", "VIII"),
    ("mitsubishi evo viii", "Mitsubishi", "Lancer Evolution", "VIII"),
    ("lancer evo viii", "Mitsubishi", "Lancer Evolution", "VIII"),
    ("evo ix", "Mitsubishi", "Lancer Evolution", "IX"),
    ("evo 9", "Mitsubishi", "Lancer Evolution", "IX"),
    ("mitsubishi evo ix", "Mitsubishi", "Lancer Evolution", "IX"),
    ("lancer evo ix", "Mitsubishi", "Lancer Evolution", "IX"),
    ("evo x", "Mitsubishi", "Lancer Evolution", "X"),
    ("evo 10", "Mitsubishi", "Lancer Evolution", "X"),
    ("evolution x", "Mitsubishi", "Lancer Evolution", "X"),
    ("lancer evo x", "Mitsubishi", "Lancer Evolution", "X"),
    ("mitsubishi evo x", "Mitsubishi", "Lancer Evolution", "X"),
    ("08-16 mitsubishi evo", "Mitsubishi", "Lancer Evolution", "X"),
    ("08-15 mitsubishi evo", "Mitsubishi", "Lancer Evolution", "X"),
    ("2008-2015 evo x", "Mitsubishi", "Lancer Evolution", "X"),
    ("2008-2015 mitsubishi evo", "Mitsubishi", "Lancer Evolution", "X"),
    ("evo vii / viii / ix", "Mitsubishi", "Lancer Evolution", "VII"),
    ("evo vii / viii / ix", "Mitsubishi", "Lancer Evolution", "VIII"),
    ("evo vii / viii / ix", "Mitsubishi", "Lancer Evolution", "IX"),
    ("evo 7/8/9", "Mitsubishi", "Lancer Evolution", "VII"),
    ("evo 7/8/9", "Mitsubishi", "Lancer Evolution", "VIII"),
    ("evo 7/8/9", "Mitsubishi", "Lancer Evolution", "IX"),
    ("evo 7-9", "Mitsubishi", "Lancer Evolution", "VII"),
    ("evo 7-9", "Mitsubishi", "Lancer Evolution", "VIII"),
    ("evo 7-9", "Mitsubishi", "Lancer Evolution", "IX"),
    ("2008-2015 mitsubishi evo x", "Mitsubishi", "Lancer Evolution", "X"),
    ("2003-2006 mitsubishi evo 8/9", "Mitsubishi", "Lancer Evolution", "VIII"),
    ("2003-2006 mitsubishi evo 8/9", "Mitsubishi", "Lancer Evolution", "IX"),
    ("2003-2015 mitsubishi evo 8/9/x", "Mitsubishi", "Lancer Evolution", "VIII"),
    ("2003-2015 mitsubishi evo 8/9/x", "Mitsubishi", "Lancer Evolution", "IX"),
    ("2003-2015 mitsubishi evo 8/9/x", "Mitsubishi", "Lancer Evolution", "X"),
    ("evo 8 9 x", "Mitsubishi", "Lancer Evolution", "VIII"),
    ("evo 8 9 x", "Mitsubishi", "Lancer Evolution", "IX"),
    ("evo 8 9 x", "Mitsubishi", "Lancer Evolution", "X"),
    ("lancer evolution vii", "Mitsubishi", "Lancer Evolution", "VII"),
    ("lancer evolution viii", "Mitsubishi", "Lancer Evolution", "VIII"),
    ("lancer evolution ix", "Mitsubishi", "Lancer Evolution", "IX"),
    ("lancer evolution x", "Mitsubishi", "Lancer Evolution", "X"),
    ("evo viii/ix", "Mitsubishi", "Lancer Evolution", "VIII"),
    ("evo viii/ix", "Mitsubishi", "Lancer Evolution", "IX"),
    ("evo ix/x", "Mitsubishi", "Lancer Evolution", "IX"),
    ("evo ix/x", "Mitsubishi", "Lancer Evolution", "X"),
    ("evo 8/9", "Mitsubishi", "Lancer Evolution", "VIII"),
    ("evo 8/9", "Mitsubishi", "Lancer Evolution", "IX"),
    ("evo 9/10", "Mitsubishi", "Lancer Evolution", "IX"),
    ("evo 9/10", "Mitsubishi", "Lancer Evolution", "X"),
    ("cd9a", "Mitsubishi", "Lancer Evolution", "I"),
    ("ce9a", "Mitsubishi", "Lancer Evolution", "II"),
    ("ce9a", "Mitsubishi", "Lancer Evolution", "III"),
    ("cn9a", "Mitsubishi", "Lancer Evolution", "IV"),
    ("cp9a", "Mitsubishi", "Lancer Evolution", "IV"),
    ("cp9a", "Mitsubishi", "Lancer Evolution", "V"),
    ("cp9a", "Mitsubishi", "Lancer Evolution", "VI"),
    ("cp9a/cn9a", "Mitsubishi", "Lancer Evolution", "IV"),
    ("cp9a/cn9a", "Mitsubishi", "Lancer Evolution", "V"),
    ("cp9a/cn9a", "Mitsubishi", "Lancer Evolution", "VI"),
    ("ct9a", "Mitsubishi", "Lancer Evolution", "VII"),
    ("ct9a", "Mitsubishi", "Lancer Evolution", "VIII"),
    ("ct9a", "Mitsubishi", "Lancer Evolution", "IX"),
    ("cz4a", "Mitsubishi", "Lancer Evolution", "X"),
    ("4b11t", "Mitsubishi", "Lancer Evolution", "X"),
    ("4b11 evo", "Mitsubishi", "Lancer Evolution", "X"),
    ("cz4a 4b11", "Mitsubishi", "Lancer Evolution", "X"),
    ("4g63 evo", "Mitsubishi", "Lancer Evolution", "VII"),
    ("4g63 evo", "Mitsubishi", "Lancer Evolution", "VIII"),
    ("4g63 evo", "Mitsubishi", "Lancer Evolution", "IX"),
    ("mitsubishi 3000gt", "Mitsubishi", "3000GT", "1st Gen"),
    ("mitsubishi 3000gt", "Mitsubishi", "3000GT", "2nd Gen"),
    ("mitsubishi 3000gt", "Mitsubishi", "3000GT", "3rd Gen"),
    ("3000gt", "Mitsubishi", "3000GT", "1st Gen"),
    ("3000gt", "Mitsubishi", "3000GT", "2nd Gen"),
    ("3000gt", "Mitsubishi", "3000GT", "3rd Gen"),
    ("3000gt vr-4", "Mitsubishi", "3000GT", "1st Gen"),
    ("3000gt vr-4", "Mitsubishi", "3000GT", "2nd Gen"),
    ("3000gt vr-4", "Mitsubishi", "3000GT", "3rd Gen"),
    ("3000gt vr4", "Mitsubishi", "3000GT", "1st Gen"),
    ("z16a", "Mitsubishi", "3000GT", "1st Gen"),
    ("dodge stealth", "Mitsubishi", "3000GT", "1st Gen"),
    ("91-93 3000gt", "Mitsubishi", "3000GT", "1st Gen"),
    ("1991-1993 3000gt", "Mitsubishi", "3000GT", "1st Gen"),
    ("94-99 3000gt", "Mitsubishi", "3000GT", "2nd Gen"),
    ("94-99 3000gt", "Mitsubishi", "3000GT", "3rd Gen"),
    ("1994-1999 3000gt", "Mitsubishi", "3000GT", "2nd Gen"),
    ("1994-1999 3000gt", "Mitsubishi", "3000GT", "3rd Gen"),
    ("91-99 mitsubishi 3000gt", "Mitsubishi", "3000GT", "1st Gen"),
    ("91-99 mitsubishi 3000gt", "Mitsubishi", "3000GT", "2nd Gen"),
    ("91-99 mitsubishi 3000gt", "Mitsubishi", "3000GT", "3rd Gen"),
    ("2g dsm", "Mitsubishi", "Eclipse", "2nd Gen"),
    ("dsm eclipse", "Mitsubishi", "Eclipse", "1st Gen"),
    ("dsm eclipse", "Mitsubishi", "Eclipse", "2nd Gen"),
    ("dsm gsx", "Mitsubishi", "Eclipse", "2nd Gen"),
    ("1g dsm", "Mitsubishi", "Eclipse", "1st Gen"),
    ("eclipse gsx", "Mitsubishi", "Eclipse", "1st Gen"),
    ("eclipse gsx", "Mitsubishi", "Eclipse", "2nd Gen"),
    ("eclipse gs-t", "Mitsubishi", "Eclipse", "1st Gen"),
    ("eclipse gs-t", "Mitsubishi", "Eclipse", "2nd Gen"),
    ("eagle talon", "Mitsubishi", "Eclipse", "1st Gen"),
    ("eagle talon", "Mitsubishi", "Eclipse", "2nd Gen"),
    ("1996-2000 mitsubishi eclipse", "Mitsubishi", "Eclipse", "2nd Gen"),
    ("1990-1994 mitsubishi eclipse", "Mitsubishi", "Eclipse", "1st Gen"),
    ("1990-1994 eclipse", "Mitsubishi", "Eclipse", "1st Gen"),
    ("1990-1994 eclipse / talon", "Mitsubishi", "Eclipse", "1st Gen"),
    ("1990-1994 eclipse/talon", "Mitsubishi", "Eclipse", "1st Gen"),
    ("1995-1999 mitsubishi eclipse", "Mitsubishi", "Eclipse", "2nd Gen"),
    ("1995-1999 eclipse", "Mitsubishi", "Eclipse", "2nd Gen"),
    ("1995-1999 eclipse / talon", "Mitsubishi", "Eclipse", "2nd Gen"),
    ("90-94 mitsubishi eclipse", "Mitsubishi", "Eclipse", "1st Gen"),
    ("89-94 mitsubishi eclipse", "Mitsubishi", "Eclipse", "1st Gen"),
    ("95-99 mitsubishi eclipse", "Mitsubishi", "Eclipse", "2nd Gen"),
    ("18-24 mitsubishi eclipse cross", "Mitsubishi", "Eclipse Cross", "1st Gen"),
    ("mitsubishi eclipse cross", "Mitsubishi", "Eclipse Cross", "1st Gen"),
    ("96-00 mitsubishi lancer", "Mitsubishi", "Lancer", "CE"),
    ("91-99 mitsubishi galant vr4", "Mitsubishi", "Galant VR-4", "1st Gen"),
    ("galant vr-4", "Mitsubishi", "Galant VR-4", "1st Gen"),
    ("g35", "Infiniti", "G35", "V35"),
    ("infiniti g35", "Infiniti", "G35", "V35"),
    ("g35 coupe", "Infiniti", "G35", "V35"),
    ("g35 sedan", "Infiniti", "G35", "V35"),
    ("g37", "Infiniti", "G37", "V36"),
    ("infiniti g37", "Infiniti", "G37", "V36"),
    ("g37 coupe", "Infiniti", "G37", "V36"),
    ("g37 sedan", "Infiniti", "G37", "V36"),
    ("g37 ipl", "Infiniti", "G37", "V36"),
    ("q50", "Infiniti", "Q50", "V37"),
    ("infiniti q50", "Infiniti", "Q50", "V37"),
    ("q50 red sport", "Infiniti", "Q50", "V37"),
    ("q50/q60", "Infiniti", "Q50", "V37"),
    ("q50/q60", "Infiniti", "Q60", "V37"),
    ("q60", "Infiniti", "Q60", "V37"),
    ("infiniti q60", "Infiniti", "Q60", "V37"),
    ("q60 red sport", "Infiniti", "Q60", "V37"),
    ("350z", "Nissan", "350Z", "Z33"),
    ("nissan 350z", "Nissan", "350Z", "Z33"),
    ("370z", "Nissan", "370Z", "Z34"),
    ("nissan 370z", "Nissan", "370Z", "Z34"),
    ("09-20 nissan 370z", "Nissan", "370Z", "Z34"),
    ("nissan z", "Nissan", "Z", "RZ34"),
    ("2023+ nissan z", "Nissan", "Z", "RZ34"),
    ("2023 nissan z", "Nissan", "Z", "RZ34"),
    ("2024 nissan z", "Nissan", "Z", "RZ34"),
    ("rz34", "Nissan", "Z", "RZ34"),
    ("2009-2018 nissan gt-r", "Nissan", "GT-R", "R35"),
    ("2017-2019 nissan gt-r", "Nissan", "GT-R", "R35"),
    ("nissan gt-r", "Nissan", "GT-R", "R35"),
    ("gt-r r35", "Nissan", "GT-R", "R35"),
    ("r35 gt-r", "Nissan", "GT-R", "R35"),
    ("r35 gtr", "Nissan", "GT-R", "R35"),
    ("nissan gtr", "Nissan", "GT-R", "R35"),
    ("skyline r32", "Nissan", "Skyline", "R32"),
    ("skyline r33", "Nissan", "Skyline", "R33"),
    ("skyline r34", "Nissan", "Skyline", "R34"),
    ("nissan r32", "Nissan", "Skyline", "R32"),
    ("nissan r33", "Nissan", "Skyline", "R33"),
    ("nissan r34", "Nissan", "Skyline", "R34"),
    ("gt-r r32", "Nissan", "GT-R", "R32"),
    ("gt-r r33", "Nissan", "GT-R", "R33"),
    ("gt-r r34", "Nissan", "GT-R", "R34"),
    ("bnr32", "Nissan", "GT-R", "R32"),
    ("hcr32", "Nissan", "GT-R", "R32"),
    ("bcnr33", "Nissan", "GT-R", "R33"),
    ("ecr33", "Nissan", "GT-R", "R33"),
    ("bnr34", "Nissan", "GT-R", "R34"),
    ("er34", "Nissan", "GT-R", "R34"),
    ("bnr32/bcnr33/bnr34", "Nissan", "GT-R", "R32"),
    ("bnr32/bcnr33/bnr34", "Nissan", "GT-R", "R33"),
    ("bnr32/bcnr33/bnr34", "Nissan", "GT-R", "R34"),
    ("bcnr33/bnr34", "Nissan", "GT-R", "R33"),
    ("bcnr33/bnr34", "Nissan", "GT-R", "R34"),
    ("rb26", "Nissan", "GT-R", "R32"),
    ("rb26", "Nissan", "GT-R", "R33"),
    ("rb26", "Nissan", "GT-R", "R34"),
    ("rb26dett", "Nissan", "GT-R", "R32"),
    ("rb26dett", "Nissan", "GT-R", "R33"),
    ("rb26dett", "Nissan", "GT-R", "R34"),
    ("rb26/rb25/rb20", "Nissan", "GT-R", "R32"),
    ("rb26/rb25/rb20", "Nissan", "GT-R", "R33"),
    ("rb26/rb25/rb20", "Nissan", "GT-R", "R34"),
    ("vr38", "Nissan", "GT-R", "R35"),
    ("vr38dett", "Nissan", "GT-R", "R35"),
    ("93-97 nissan altima", "Nissan", "Altima", "U13"),
    ("91-94 nissan sentra", "Nissan", "Sentra", "B13"),
    ("95-99 nissan sentra", "Nissan", "Sentra", "B14"),
    ("69-74 datsun 240z", "Datsun", "240Z", "S30"),
    ("74-78 datsun 260z", "Datsun", "260Z", "S30"),
    ("75-78 datsun 280z", "Datsun", "280Z", "S30"),
    ("2010-2015 camaro", "Chevrolet", "Camaro", "5th Gen"),
    ("2010-2015 chevrolet camaro", "Chevrolet", "Camaro", "5th Gen"),
    ("2010+ camaro", "Chevrolet", "Camaro", "5th Gen"),
    ("camaro ss 2010", "Chevrolet", "Camaro", "5th Gen"),
    ("2010-14 camaro", "Chevrolet", "Camaro", "5th Gen"),
    ("2016+ camaro", "Chevrolet", "Camaro", "6th Gen"),
    ("2016-2024 camaro", "Chevrolet", "Camaro", "6th Gen"),
    ("2016-2022 camaro", "Chevrolet", "Camaro", "6th Gen"),
    ("g5 camaro", "Chevrolet", "Camaro", "5th Gen"),
    ("g6 camaro", "Chevrolet", "Camaro", "6th Gen"),
    ("camaro g5", "Chevrolet", "Camaro", "5th Gen"),
    ("camaro g6", "Chevrolet", "Camaro", "6th Gen"),
    ("g5 camaro zl1", "Chevrolet", "Camaro", "5th Gen"),
    ("g6 camaro zl1", "Chevrolet", "Camaro", "6th Gen"),
    ("g5 camaro z28", "Chevrolet", "Camaro", "5th Gen"),
    ("camaro zl1", "Chevrolet", "Camaro", "6th Gen"),
    ("camaro 1le", "Chevrolet", "Camaro", "6th Gen"),
    ("camaro z/28", "Chevrolet", "Camaro", "5th Gen"),
    ("z/28 camaro", "Chevrolet", "Camaro", "5th Gen"),
    ("10-15 camaro", "Chevrolet", "Camaro", "5th Gen"),
    ("10-15 camaro ss", "Chevrolet", "Camaro", "5th Gen"),
    ("16-24 camaro", "Chevrolet", "Camaro", "6th Gen"),
    ("82-02 camaro", "Chevrolet", "Camaro", "3rd Gen"),
    ("82-02 camaro", "Chevrolet", "Camaro", "4th Gen"),
    ("82-92 fbody", "Chevrolet", "Camaro", "3rd Gen"),
    ("2012-2015 camaro", "Chevrolet", "Camaro", "5th Gen"),
    ("2012-2015 camaro zl1", "Chevrolet", "Camaro", "5th Gen"),
    ("2017+ camaro zl1", "Chevrolet", "Camaro", "6th Gen"),
    ("camaro zl1 1le", "Chevrolet", "Camaro", "6th Gen"),
    ("1993-2001 camaro", "Chevrolet", "Camaro", "4th Gen"),
    ("1993-2001 chevrolet camaro", "Chevrolet", "Camaro", "4th Gen"),
    ("chevrolet camaro 1993-2001", "Chevrolet", "Camaro", "4th Gen"),
    ("c8 z06", "Chevrolet", "Corvette", "C8"),
    ("c8 corvette z06", "Chevrolet", "Corvette", "C8"),
    ("c8 e-ray", "Chevrolet", "Corvette", "C8"),
    ("c8 zr1", "Chevrolet", "Corvette", "C8"),
    ("97-04 corvette", "Chevrolet", "Corvette", "C5"),
    ("chevrolet corvette 2001-2004", "Chevrolet", "Corvette", "C5"),
    ("chevrolet corvette 2005-2008", "Chevrolet", "Corvette", "C6"),
    ("chevrolet corvette 2014+", "Chevrolet", "Corvette", "C7"),
    ("2001-2004 corvette c5", "Chevrolet", "Corvette", "C5"),
    ("2005-2008 corvette c6", "Chevrolet", "Corvette", "C6"),
    ("2014+ corvette c7", "Chevrolet", "Corvette", "C7"),
    ("2014+ chevrolet corvette", "Chevrolet", "Corvette", "C7"),
    ("chevy ss", "Chevrolet", "SS", "VF Series"),
    ("chevrolet ss sedan", "Chevrolet", "SS", "VF Series"),
    ("silverado 1500", "Chevrolet", "Silverado", "K2"),
    ("silverado ss", "Chevrolet", "Silverado", "GMT800"),
    ("tahoe", "Chevrolet", "Tahoe", "GMT900"),
    ("suburban", "Chevrolet", "Suburban", "GMT800"),
    ("sierra 1500", "GMC", "Sierra", "K2"),
    ("yukon denali", "GMC", "Yukon", "K2"),
    ("escalade", "Cadillac", "Escalade", "K2"),
    ("cadillac cts-v", "Cadillac", "CTS-V", "2nd Gen"),
    ("cts-v gen 2", "Cadillac", "CTS-V", "2nd Gen"),
    ("cts-v gen 3", "Cadillac", "CTS-V", "3rd Gen"),
    ("09-15 cts-v", "Cadillac", "CTS-V", "2nd Gen"),
    ("09-14 cts-v", "Cadillac", "CTS-V", "2nd Gen"),
    ("2009-14 cts-v", "Cadillac", "CTS-V", "2nd Gen"),
    ("2009-2015 cts-v", "Cadillac", "CTS-V", "2nd Gen"),
    ("2016-2019 cadillac cts-v", "Cadillac", "CTS-V", "3rd Gen"),
    ("ct5-v blackwing", "Cadillac", "CT5-V Blackwing", "1st Gen"),
    ("ct4-v blackwing", "Cadillac", "CT4-V Blackwing", "1st Gen"),
    ("holden commodore ve", "Holden", "Commodore", "VE"),
    ("pontiac g8", "Pontiac", "G8", "VE"),
    ("g8 gt", "Pontiac", "G8", "VE"),
    ("g8 gxp", "Pontiac", "G8", "VE"),
    ("pontiac gto", "Pontiac", "GTO", "Holden"),
    ("04-06 gto", "Pontiac", "GTO", "Holden"),
    ("2004-2006 gto", "Pontiac", "GTO", "Holden"),
    ("2004 gto", "Pontiac", "GTO", "Holden"),
    ("2005 gto", "Pontiac", "GTO", "Holden"),
    ("2006 gto", "Pontiac", "GTO", "Holden"),
    ("pontiac firebird", "Pontiac", "Firebird", "4th Gen"),
    ("firebird trans am", "Pontiac", "Firebird", "4th Gen"),
    ("trans am ws6", "Pontiac", "Firebird", "4th Gen"),
    ("wrx gda", "Subaru", "WRX", "GD"),
    ("wrx gdb", "Subaru", "WRX", "GD"),
    ("gda wrx", "Subaru", "WRX", "GD"),
    ("gdb wrx", "Subaru", "WRX", "GD"),
    ("gda/gdb", "Subaru", "WRX", "GD"),
    ("gda / gdb", "Subaru", "WRX", "GD"),
    ("gda-gdb", "Subaru", "WRX", "GD"),
    ("impreza wrx gda", "Subaru", "WRX", "GD"),
    ("impreza wrx gdb", "Subaru", "WRX", "GD"),
    ("impreza gda", "Subaru", "Impreza", "GD/GG"),
    ("impreza gdb", "Subaru", "Impreza", "GD/GG"),
    ("wrx grb", "Subaru", "WRX", "GR"),
    ("wrx grf", "Subaru", "WRX", "GR"),
    ("grb wrx", "Subaru", "WRX", "GR"),
    ("grf wrx", "Subaru", "WRX", "GR"),
    ("grb/grf", "Subaru", "WRX", "GR"),
    ("impreza grb", "Subaru", "Impreza", "GE/GH"),
    ("impreza gvb", "Subaru", "Impreza", "GE/GH"),
    ("gc8", "Subaru", "WRX", "GC"),
    ("gc8 wrx", "Subaru", "WRX", "GC"),
    ("wrx gc8", "Subaru", "WRX", "GC"),
    ("subaru gc8", "Subaru", "WRX", "GC"),
    ("gc wrx", "Subaru", "WRX", "GC"),
    ("impreza gc", "Subaru", "WRX", "GC"),
    ("92-00 subaru wrx", "Subaru", "WRX", "GC"),
    ("1992-2000 subaru wrx", "Subaru", "WRX", "GC"),
    ("wrx sti", "Subaru", "WRX", "GD"),
    ("wrx sti", "Subaru", "WRX", "GR"),
    ("wrx sti", "Subaru", "WRX", "VA"),
    ("subaru sti", "Subaru", "WRX", "GD"),
    ("subaru sti", "Subaru", "WRX", "GR"),
    ("subaru sti", "Subaru", "WRX", "VA"),
    ("subaru wrx sti", "Subaru", "WRX", "GD"),
    ("subaru wrx sti", "Subaru", "WRX", "GR"),
    ("subaru wrx sti", "Subaru", "WRX", "VA"),
    ("sti gd", "Subaru", "WRX", "GD"),
    ("sti gdb", "Subaru", "WRX", "GD"),
    ("sti gr", "Subaru", "WRX", "GR"),
    ("sti grb", "Subaru", "WRX", "GR"),
    ("sti va", "Subaru", "WRX", "VA"),
    ("sti vb", "Subaru", "WRX", "VB"),
    ("2004-2021 subaru sti", "Subaru", "WRX", "GD"),
    ("2004-2021 subaru sti", "Subaru", "WRX", "GR"),
    ("2004-2021 subaru sti", "Subaru", "WRX", "VA"),
    ("2004+ subaru sti", "Subaru", "WRX", "GD"),
    ("2004+ subaru sti", "Subaru", "WRX", "GR"),
    ("2004+ subaru sti", "Subaru", "WRX", "VA"),
    ("2004-2007 subaru sti", "Subaru", "WRX", "GD"),
    ("2004-2007 subaru wrx sti", "Subaru", "WRX", "GD"),
    ("2008-2014 subaru sti", "Subaru", "WRX", "GR"),
    ("2008-2021 subaru sti", "Subaru", "WRX", "GR"),
    ("2008-2021 subaru sti", "Subaru", "WRX", "VA"),
    ("2015-2021 subaru sti", "Subaru", "WRX", "VA"),
    ("2022+ subaru wrx", "Subaru", "WRX", "VB"),
    ("2022-2024 subaru wrx", "Subaru", "WRX", "VB"),
    ("honda s2000", "Honda", "S2000", "AP1"),
    ("honda s2000", "Honda", "S2000", "AP2"),
    ("s2000", "Honda", "S2000", "AP1"),
    ("s2000", "Honda", "S2000", "AP2"),
    ("2000-2003 honda s2000", "Honda", "S2000", "AP1"),
    ("2000-2003 s2000", "Honda", "S2000", "AP1"),
    ("2004-2009 honda s2000", "Honda", "S2000", "AP2"),
    ("2004-2009 s2000", "Honda", "S2000", "AP2"),
    ("8th gen civic", "Honda", "Civic", "8th Gen"),
    ("civic 8th gen", "Honda", "Civic", "8th Gen"),
    ("8th gen", "Honda", "Civic", "8th Gen"),
    ("9th gen civic", "Honda", "Civic", "9th Gen"),
    ("civic 9th gen", "Honda", "Civic", "9th Gen"),
    ("9th gen", "Honda", "Civic", "9th Gen"),
    ("11th gen civic", "Honda", "Civic", "11th Gen"),
    ("civic 11th gen", "Honda", "Civic", "11th Gen"),
    ("11th gen", "Honda", "Civic", "11th Gen"),
    ("civic 7th generation", "Honda", "Civic", "7th Gen"),
    ("honda civic 7th generation", "Honda", "Civic", "7th Gen"),
    ("7th generation civic", "Honda", "Civic", "7th Gen"),
    ("civic (7th generation)", "Honda", "Civic", "7th Gen"),
    ("civic 8th generation", "Honda", "Civic", "8th Gen"),
    ("honda civic 8th generation", "Honda", "Civic", "8th Gen"),
    ("8th generation civic", "Honda", "Civic", "8th Gen"),
    ("civic (8th generation)", "Honda", "Civic", "8th Gen"),
    ("civic 9th generation", "Honda", "Civic", "9th Gen"),
    ("honda civic 9th generation", "Honda", "Civic", "9th Gen"),
    ("9th generation civic", "Honda", "Civic", "9th Gen"),
    ("civic (9th generation)", "Honda", "Civic", "9th Gen"),
    ("civic 10th generation", "Honda", "Civic", "10th Gen"),
    ("honda civic 10th generation", "Honda", "Civic", "10th Gen"),
    ("10th generation civic", "Honda", "Civic", "10th Gen"),
    ("civic (10th generation)", "Honda", "Civic", "10th Gen"),
    ("civic 11th generation", "Honda", "Civic", "11th Gen"),
    ("honda civic 11th generation", "Honda", "Civic", "11th Gen"),
    ("civic si 2006", "Honda", "Civic", "8th Gen"),
    ("2006-2011 civic si", "Honda", "Civic", "8th Gen"),
    ("2012-2015 civic si", "Honda", "Civic", "9th Gen"),
    ("civic si 2012", "Honda", "Civic", "9th Gen"),
    ("2017-2021 civic si", "Honda", "Civic", "10th Gen"),
    ("2022+ civic si", "Honda", "Civic", "11th Gen"),
    ("2017-2021 civic hatchback", "Honda", "Civic", "10th Gen"),
    ("2016-2021 civic hatchback", "Honda", "Civic", "10th Gen"),
    ("civic hatchback 2017", "Honda", "Civic", "10th Gen"),
    ("acura tsx", "Acura", "TSX", "CL9"),
    ("acura tsx", "Acura", "TSX", "CU2"),
    ("04-08 acura tsx", "Acura", "TSX", "CL9"),
    ("09-14 acura tsx", "Acura", "TSX", "CU2"),
    ("acura rsx", "Acura", "RSX", "DC5"),
    ("acura integra rsx", "Acura", "RSX", "DC5"),
    ("02-06 acura rsx", "Acura", "RSX", "DC5"),
    ("acura tlx", "Acura", "TLX", "1st Gen"),
    ("acura tlx", "Acura", "TLX", "2nd Gen"),
    ("tlx type-s", "Acura", "TLX", "2nd Gen"),
    ("tlx type s", "Acura", "TLX", "2nd Gen"),
    ("acura tlx type-s", "Acura", "TLX", "2nd Gen"),
    ("2021+ acura tlx", "Acura", "TLX", "2nd Gen"),
    ("2021-25 acura tlx type s", "Acura", "TLX", "2nd Gen"),
    ("2015-2020 acura tlx", "Acura", "TLX", "1st Gen"),
    ("acura nsx", "Acura", "NSX", "NA1/NA2"),
    ("acura nsx", "Acura", "NSX", "NC1"),
    ("nsx na1", "Acura", "NSX", "NA1/NA2"),
    ("nsx nc1", "Acura", "NSX", "NC1"),
    ("e46 325", "BMW", "3 Series", "E46"),
    ("bmw e46 325", "BMW", "3 Series", "E46"),
    ("e46 330", "BMW", "330i", "E46"),
    ("bmw e46 330", "BMW", "330i", "E46"),
    ("s15", "Nissan", "240SX", "S15"),
    ("240sx s15", "Nissan", "240SX", "S15"),
    ("nissan s15", "Nissan", "240SX", "S15"),
    ("silvia s15", "Nissan", "240SX", "S15"),
    ("nissan silvia s15", "Nissan", "240SX", "S15"),
    ("99-02 nissan silvia", "Nissan", "240SX", "S15"),
    ("nissan 240sx", "Nissan", "240SX", "S13"),
    ("nissan 240sx", "Nissan", "240SX", "S14"),
    ("350z/g35", "Nissan", "350Z", "Z33"),
    ("350z/g35", "Infiniti", "G35", "V35"),
    ("350z / g35", "Nissan", "350Z", "Z33"),
    ("350z / g35", "Infiniti", "G35", "V35"),
    ("350z/g35/g37", "Nissan", "350Z", "Z33"),
    ("350z/g35/g37", "Infiniti", "G35", "V35"),
    ("350z/g35/g37", "Infiniti", "G37", "V36"),
    ("ev6 gt", "Kia", "EV6 GT", "CV"),
    ("kia ev6 gt", "Kia", "EV6 GT", "CV"),
    ("kia ev6", "Kia", "EV6 GT", "CV"),
    ("kona n", "Hyundai", "Kona N", "OS"),
    ("hyundai kona n", "Hyundai", "Kona N", "OS"),
    ("dodge lx", "Dodge", "Charger", "LX"),
    ("dodge lx charger", "Dodge", "Charger", "LX"),
    ("forester (sh)", "Subaru", "Forester XT", "SH"),
    ("subaru forester (sh)", "Subaru", "Forester XT", "SH"),
    ("mazda bp", "Mazda", "Mazda3", "BP"),
    ("mazda 3 bp", "Mazda", "Mazda3", "BP"),
    ("b5 audi s4", "Audi", "S4", "B5"),
    ("b5 audi rs4", "Audi", "RS4", "B5"),
    ("b5 audi a4", "Audi", "A4", "B5"),
    ("b5 audi s4/rs4", "Audi", "S4", "B5"),
    ("b5 audi s4/rs4", "Audi", "RS4", "B5"),
    ("b5 s4/rs4", "Audi", "S4", "B5"),
    ("b5 s4/rs4", "Audi", "RS4", "B5"),
    ("b5 audi a4/s4/rs4", "Audi", "A4", "B5"),
    ("b5 audi a4/s4/rs4", "Audi", "S4", "B5"),
    ("b5 audi a4/s4/rs4", "Audi", "RS4", "B5"),
    ("b5 a4/s4/rs4", "Audi", "A4", "B5"),
    ("b5 a4/s4/rs4", "Audi", "S4", "B5"),
    ("b5 a4/s4/rs4", "Audi", "RS4", "B5"),
    ("b4/b5 audi a4/s4/rs4", "Audi", "A4", "B5"),
    ("b4/b5 audi a4/s4/rs4", "Audi", "S4", "B5"),
    ("b4/b5 audi a4/s4/rs4", "Audi", "RS4", "B5"),
    ("c5 a6/allroad", "Audi", "S6", "C5"),
    ("b5 s4 & c5 a6", "Audi", "S4", "B5"),
    ("b5 s4 & c5 a6", "Audi", "S6", "C5"),
    ("2015-2021 audi rs3", "Audi", "RS3", "8V"),
    ("audi rs3 8v", "Audi", "RS3", "8V"),
    ("urs4", "Audi", "S4 (UrS4)", "C4"),
    ("ur-s4", "Audi", "S4 (UrS4)", "C4"),
    ("audi urs4", "Audi", "S4 (UrS4)", "C4"),
    ("audi ur-s4", "Audi", "S4 (UrS4)", "C4"),
    ("urs4/urs6", "Audi", "S4 (UrS4)", "C4"),
    ("urs4/urs6", "Audi", "S6", "C4"),
    ("urs4 urs6", "Audi", "S4 (UrS4)", "C4"),
    ("urs4 urs6", "Audi", "S6", "C4"),
    ("urs6", "Audi", "S6", "C4"),
    ("ur-s6", "Audi", "S6", "C4"),
    ("audi urs6", "Audi", "S6", "C4"),
    ("urquattro", "Audi", "UrQuattro", "Typ 85"),
    ("ur-quattro", "Audi", "UrQuattro", "Typ 85"),
    ("audi urquattro", "Audi", "UrQuattro", "Typ 85"),
    ("audi ur-quattro", "Audi", "UrQuattro", "Typ 85"),
    ("audi urq", "Audi", "UrQuattro", "Typ 85"),
    ("quattro typ 85", "Audi", "UrQuattro", "Typ 85"),
    ("audi 80", "Audi", "80/90", "B3"),
    ("audi 90", "Audi", "80/90", "B3"),
    ("audi b3 80", "Audi", "80/90", "B3"),
    ("audi b3 90", "Audi", "80/90", "B3"),
    ("audi b3 chassis", "Audi", "80/90", "B3"),
    ("audi b2 chassis", "Audi", "80/90", "B2"),
    ("audi b4 chassis", "Audi", "80/90", "B4"),
    ("audi 80/90", "Audi", "80/90", "B3"),
    ("audi coupe quattro", "Audi", "80/90", "B3"),
    ("coupe quattro", "Audi", "80/90", "B3"),
    ("audi small chassis", "Audi", "80/90", "B3"),
    ("audi small chassis", "Audi", "80/90", "B2"),
    ("audi vintage small chassis", "Audi", "80/90", "B2"),
    ("audi 200", "Audi", "100/200", "C3"),
    ("audi 200 quattro", "Audi", "100/200", "C3"),
    ("audi 200 20v", "Audi", "100/200", "C3"),
    ("audi 5000", "Audi", "100/200", "C3"),
    ("audi 100", "Audi", "100/200", "C4"),
    ("audi 100 quattro", "Audi", "100/200", "C4"),
    ("f-body", "Chevrolet", "Camaro", "3rd Gen"),
    ("f-body", "Chevrolet", "Camaro", "4th Gen"),
    ("f-body", "Pontiac", "Firebird", "3rd Gen"),
    ("f-body", "Pontiac", "Firebird", "4th Gen"),
    ("fbody", "Chevrolet", "Camaro", "3rd Gen"),
    ("fbody", "Chevrolet", "Camaro", "4th Gen"),
    ("fbody", "Pontiac", "Firebird", "3rd Gen"),
    ("fbody", "Pontiac", "Firebird", "4th Gen"),
    ("camaro & firebird", "Chevrolet", "Camaro", "4th Gen"),
    ("camaro & firebird", "Pontiac", "Firebird", "4th Gen"),
    ("camaro and firebird", "Chevrolet", "Camaro", "4th Gen"),
    ("camaro and firebird", "Pontiac", "Firebird", "4th Gen"),
    ("camaro/firebird", "Chevrolet", "Camaro", "4th Gen"),
    ("camaro/firebird", "Pontiac", "Firebird", "4th Gen"),
    ("na6 miata", "Mazda", "Miata", "NA"),
    ("miata na6", "Mazda", "Miata", "NA"),
    ("na6 chassis", "Mazda", "Miata", "NA"),
    ("na6", "Mazda", "Miata", "NA"),
    ("na8 miata", "Mazda", "Miata", "NA"),
    ("miata na8", "Mazda", "Miata", "NA"),
    ("na8 chassis", "Mazda", "Miata", "NA"),
    ("na8", "Mazda", "Miata", "NA"),
    ("mazdaspeed miata", "Mazda", "Miata", "NB"),
    ("mazdaspeed mx-5", "Mazda", "Miata", "NB"),
    ("mazdaspeed 6 turbo", "Mazda", "Mazda6", "GG/GY"),
    ("1.8 miata", "Mazda", "Miata", "NA"),
    ("1.8 miata", "Mazda", "Miata", "NB"),
    ("1.6 miata", "Mazda", "Miata", "NA"),
    ("miata 1.8", "Mazda", "Miata", "NA"),
    ("miata 1.8", "Mazda", "Miata", "NB"),
    ("miata 1.6", "Mazda", "Miata", "NA"),
    ("1.8 bp engine", "Mazda", "Miata", "NB"),
    ("bp engine miata", "Mazda", "Miata", "NB"),
    ("b6 miata engine", "Mazda", "Miata", "NA"),
    ("1.6 b6 engine", "Mazda", "Miata", "NA"),
    ("mazda bp engine", "Mazda", "Miata", "NB"),
    ("1990-97 miata", "Mazda", "Miata", "NA"),
    ("1994-00 miata", "Mazda", "Miata", "NA"),
    ("1994-00 miata", "Mazda", "Miata", "NB"),
    ("2001-05 miata", "Mazda", "Miata", "NB"),
    ("nb2 miata", "Mazda", "Miata", "NB"),
    ("miata nb2", "Mazda", "Miata", "NB"),
    ("nb1 miata", "Mazda", "Miata", "NB"),
    ("miata nb1", "Mazda", "Miata", "NB"),
    ("1989-2005 mazda miata", "Mazda", "Miata", "NA"),
    ("1989-2005 mazda miata", "Mazda", "Miata", "NB"),
    ("1989-2005 miata", "Mazda", "Miata", "NA"),
    ("1989-2005 miata", "Mazda", "Miata", "NB"),
    ("1994-2005 1.8 mx-5 miata", "Mazda", "Miata", "NA"),
    ("1994-2005 1.8 mx-5 miata", "Mazda", "Miata", "NB"),
    ("fd3s", "Mazda", "RX-7", "FD"),
    ("rx-7 fd3s", "Mazda", "RX-7", "FD"),
    ("rx7 fd3s", "Mazda", "RX-7", "FD"),
    ("mazda rx-7 fd3s", "Mazda", "RX-7", "FD"),
    ("fd3c", "Mazda", "RX-7", "FD"),
    ("fc3s", "Mazda", "RX-7", "FC"),
    ("rx-7 fc3s", "Mazda", "RX-7", "FC"),
    ("mazda rx-7", "Mazda", "RX-7", "FC"),
    ("mazda rx-7", "Mazda", "RX-7", "FD"),
    ("mazda rx7", "Mazda", "RX-7", "FC"),
    ("mazda rx7", "Mazda", "RX-7", "FD"),
    ("93+ mazda rx-7", "Mazda", "RX-7", "FD"),
    ("mazda rx-8", "Mazda", "RX-8", "SE3P"),
    ("rx-8", "Mazda", "RX-8", "SE3P"),
    ("rx8", "Mazda", "RX-8", "SE3P"),
    ("mazdaspeed 3", "Mazda", "Mazda3", "BK"),
    ("mazdaspeed3", "Mazda", "Mazda3", "BK"),
    ("mazdaspeed 2.0 fs turbo", "Mazda", "Mazdaspeed Protegé", "BJ"),
    ("mazda b2600", "Mazda", "B-Series Truck", "5th Gen"),
    ("2005-2007 mazdaspeed 6", "Mazda", "Mazda6", "GG/GY"),
    ("audi s2", "Audi", "S2", "B4"),
    ("s2 coupe audi", "Audi", "S2", "B4"),
    ("b4 s2", "Audi", "S2", "B4"),
    ("s2/rs2", "Audi", "S2", "B4"),
    ("s2/rs2", "Audi", "RS2 Avant", "1st Gen"),
    ("subaru wrx", "Subaru", "WRX", "GD"),
    ("subaru wrx", "Subaru", "WRX", "GR"),
    ("subaru wrx", "Subaru", "WRX", "VA"),
    ("2022+ wrx", "Subaru", "WRX", "VB"),
    ("2022-2024 wrx", "Subaru", "WRX", "VB"),
    ("2022 wrx", "Subaru", "WRX", "VB"),
    ("2023+ wrx", "Subaru", "WRX", "VB"),
    ("2024 wrx", "Subaru", "WRX", "VB"),
    ("impreza wrx", "Subaru", "WRX", "GC"),
    ("impreza wrx", "Subaru", "WRX", "GD"),
    ("subaru impreza wrx", "Subaru", "WRX", "GC"),
    ("subaru impreza wrx", "Subaru", "WRX", "GD"),
    ("impreza sti", "Subaru", "WRX", "GD"),
    ("impreza sti", "Subaru", "WRX", "GR"),
    ("subaru impreza sti", "Subaru", "WRX", "GD"),
    ("subaru impreza sti", "Subaru", "WRX", "GR"),
    ("02-07 subaru wrx", "Subaru", "WRX", "GD"),
    ("02-07 subaru impreza wrx", "Subaru", "WRX", "GD"),
    ("02-07 wrx", "Subaru", "WRX", "GD"),
    ("05-07 sti", "Subaru", "WRX", "GD"),
    ("05-07 subaru sti", "Subaru", "WRX", "GD"),
    ("05-07 subaru impreza sti", "Subaru", "WRX", "GD"),
    ("08-14 subaru wrx", "Subaru", "WRX", "GR"),
    ("08-14 subaru impreza wrx", "Subaru", "WRX", "GR"),
    ("08-14 wrx", "Subaru", "WRX", "GR"),
    ("08-14 subaru sti", "Subaru", "WRX", "GR"),
    ("08-14 subaru impreza sti", "Subaru", "WRX", "GR"),
    ("08-14 sti", "Subaru", "WRX", "GR"),
    ("08-21 sti", "Subaru", "WRX", "GR"),
    ("08-21 sti", "Subaru", "WRX", "VA"),
    ("08-21 subaru sti", "Subaru", "WRX", "GR"),
    ("08-21 subaru sti", "Subaru", "WRX", "VA"),
    ("15-21 wrx", "Subaru", "WRX", "VA"),
    ("15-21 subaru wrx", "Subaru", "WRX", "VA"),
    ("15-21 sti", "Subaru", "WRX", "VA"),
    ("15-21 subaru sti", "Subaru", "WRX", "VA"),
    ("15-21 subaru impreza sti", "Subaru", "WRX", "VA"),
    ("04-21 sti", "Subaru", "WRX", "GD"),
    ("04-21 sti", "Subaru", "WRX", "GR"),
    ("04-21 sti", "Subaru", "WRX", "VA"),
    ("04-21 subaru sti", "Subaru", "WRX", "GD"),
    ("04-21 subaru sti", "Subaru", "WRX", "GR"),
    ("04-21 subaru sti", "Subaru", "WRX", "VA"),
    ("sti gde", "Subaru", "WRX", "GD"),
    ("sti gdf", "Subaru", "WRX", "GD"),
    ("wrx gh8", "Subaru", "WRX", "GR"),
    ("wrx gh", "Subaru", "WRX", "GR"),
    ("wrx vab", "Subaru", "WRX", "VA"),
    ("wrx vaf", "Subaru", "WRX", "VA"),
    ("sti vab", "Subaru", "WRX", "VA"),
    ("sti (gde)", "Subaru", "WRX", "GD"),
    ("sti (gdf)", "Subaru", "WRX", "GD"),
    ("sti (grb)", "Subaru", "WRX", "GR"),
    ("sti (gvb)", "Subaru", "WRX", "GR"),
    ("sti (gvf)", "Subaru", "WRX", "GR"),
    ("sti (vab)", "Subaru", "WRX", "VA"),
    ("sti (vaf)", "Subaru", "WRX", "VA"),
    ("sti (vag)", "Subaru", "WRX", "VA"),
    ("gde/gdf", "Subaru", "WRX", "GD"),
    ("gvb/gvf", "Subaru", "WRX", "GR"),
    ("vab/vaf/vag", "Subaru", "WRX", "VA"),
    ("gc6", "Subaru", "WRX", "GC"),
    ("gc6/gc8", "Subaru", "WRX", "GC"),
    ("scion fr-s", "Subaru", "BRZ", "ZC6"),
    ("scion fr-s", "Toyota", "86", "ZN6"),
    ("frs/brz", "Subaru", "BRZ", "ZC6"),
    ("frs/brz", "Toyota", "86", "ZN6"),
    ("fr-s/brz", "Subaru", "BRZ", "ZC6"),
    ("fr-s/brz", "Toyota", "86", "ZN6"),
    ("2013-2016 scion fr-s", "Subaru", "BRZ", "ZC6"),
    ("2013-2016 scion fr-s", "Toyota", "86", "ZN6"),
    ("2013-2020 subaru brz", "Subaru", "BRZ", "ZC6"),
    ("2013-2024 subaru brz", "Subaru", "BRZ", "ZC6"),
    ("2013-2024 subaru brz", "Subaru", "BRZ", "ZD8"),
    ("2017-2020 toyota 86", "Toyota", "86", "ZN6"),
    ("2017-2019 toyota 86", "Toyota", "86", "ZN6"),
    ("17-20 toyota 86", "Toyota", "86", "ZN6"),
    ("2022-2024 subaru brz", "Subaru", "BRZ", "ZD8"),
    ("2002-2014 subaru wrx", "Subaru", "WRX", "GD"),
    ("2002-2014 subaru wrx", "Subaru", "WRX", "GR"),
    ("02-14 wrx", "Subaru", "WRX", "GD"),
    ("02-14 wrx", "Subaru", "WRX", "GR"),
    ("02-14 subaru wrx", "Subaru", "WRX", "GD"),
    ("02-14 subaru wrx", "Subaru", "WRX", "GR"),
    ("2015-2021 subaru wrx", "Subaru", "WRX", "VA"),
    ("2015-2021 subaru wrx / sti", "Subaru", "WRX", "VA"),
    ("2015-2021 subaru wrx/sti", "Subaru", "WRX", "VA"),
    ("2015-2021 wrx/sti", "Subaru", "WRX", "VA"),
    ("2015-2021 wrx", "Subaru", "WRX", "VA"),
    ("2008-2014 subaru wrx/sti", "Subaru", "WRX", "GR"),
    ("2008-2014 subaru wrx / sti", "Subaru", "WRX", "GR"),
    ("2008-2014 wrx/sti", "Subaru", "WRX", "GR"),
    ("2008-2014 subaru wrx", "Subaru", "WRX", "GR"),
    ("2006-2017 subaru wrx", "Subaru", "WRX", "GD"),
    ("2006-2017 subaru wrx", "Subaru", "WRX", "GR"),
    ("2006-2017 subaru wrx", "Subaru", "WRX", "VA"),
    ("02-07 subaru wrx / sti", "Subaru", "WRX", "GD"),
    ("2002-2007 subaru wrx / sti", "Subaru", "WRX", "GD"),
    ("2002-2007 wrx/sti", "Subaru", "WRX", "GD"),
    ("2002-2007 subaru wrx", "Subaru", "WRX", "GD"),
    ("2007-2021 sti", "Subaru", "WRX", "GR"),
    ("2007-2021 sti", "Subaru", "WRX", "VA"),
    ("2002-2014 wrx", "Subaru", "WRX", "GD"),
    ("2002-2014 wrx", "Subaru", "WRX", "GR"),
    ("92-01 subaru impreza wrx", "Subaru", "WRX", "GC"),
    ("92-01 impreza wrx", "Subaru", "WRX", "GC"),
    ("11-14 subaru impreza sti", "Subaru", "WRX", "GR"),
    ("08-14 impreza wrx hatchback", "Subaru", "WRX", "GR"),
    ("06-21 sti", "Subaru", "WRX", "GR"),
    ("06-21 sti", "Subaru", "WRX", "VA"),
    ("06-14 wrx", "Subaru", "WRX", "GD"),
    ("06-14 wrx", "Subaru", "WRX", "GR"),
    ("03-08 subaru forester xt", "Subaru", "Forester XT", "SG"),
    ("04-07 subaru forester xt", "Subaru", "Forester XT", "SG"),
    ("2004-2007 subaru forester xt", "Subaru", "Forester XT", "SG"),
    ("2004-2008 subaru forester xt", "Subaru", "Forester XT", "SG"),
    ("2004-07 subaru forester xt", "Subaru", "Forester XT", "SG"),
    ("2014-2018 subaru forester", "Subaru", "Forester XT", "SJ"),
    ("2009-2013 subaru forester xt", "Subaru", "Forester XT", "SH"),
    ("04-13 fxt", "Subaru", "Forester XT", "SG"),
    ("04-13 fxt", "Subaru", "Forester XT", "SH"),
    ("04-08 fxt", "Subaru", "Forester XT", "SG"),
    ("09-13 fxt", "Subaru", "Forester XT", "SH"),
    ("subaru forester xt", "Subaru", "Forester XT", "SG"),
    ("subaru forester xt", "Subaru", "Forester XT", "SH"),
    ("forester xt", "Subaru", "Forester XT", "SG"),
    ("forester xt", "Subaru", "Forester XT", "SH"),
    ("subaru ascent", "Subaru", "Ascent", "1st Gen"),
    ("05-09 subaru legacy (bl9 / bp)", "Subaru", "Legacy", "BL/BP"),
    ("subaru legacy bl9", "Subaru", "Legacy", "BL/BP"),
    ("subaru legacy bp5", "Subaru", "Legacy", "BL/BP"),
    ("95-99 subaru legacy", "Subaru", "Legacy", "BD/BG"),
    ("subaru legacy bd", "Subaru", "Legacy", "BD/BG"),
    ("subaru legacy bg", "Subaru", "Legacy", "BD/BG"),
    ("90-94 subaru legacy", "Subaru", "Legacy", "BC/BJ/BF"),
    ("10-14 subaru legacy", "Subaru", "Legacy", "BM/BR"),
    ("15-19 subaru legacy", "Subaru", "Legacy", "BN/BS"),
    ("03-06 subaru baja", "Subaru", "Baja", "BT"),
    ("16-21 subaru impreza", "Subaru", "Impreza", "GP/GJ"),
    ("17-23 subaru impreza sport", "Subaru", "Impreza", "GP/GJ"),
    ("mercedes g63", "Mercedes", "G63 AMG", "W463"),
    ("mercedes g63 amg", "Mercedes", "G63 AMG", "W463"),
    ("g63 amg", "Mercedes", "G63 AMG", "W463"),
    ("sl55 amg", "Mercedes", "SL-Class", "R230"),
    ("mercedes benz sl55 amg", "Mercedes", "SL-Class", "R230"),
    ("1996-2000 dodge viper", "Dodge", "Viper", "SR II"),
    ("1996-2000 viper", "Dodge", "Viper", "SR II"),
    ("2003-2006 dodge viper", "Dodge", "Viper", "ZB I"),
    ("2006-2008 charger", "Dodge", "Charger", "LX"),
    ("2006-2008 dodge charger", "Dodge", "Charger", "LX"),
    ("2006-2008 charger/300c/magnum", "Dodge", "Charger", "LX"),
    ("2006-2008 charger/300c", "Dodge", "Charger", "LX"),
    ("2006-2014 charger", "Dodge", "Charger", "LX"),
    ("2006-2014 charger", "Dodge", "Charger", "LD"),
    ("2009-2014 charger", "Dodge", "Charger", "LD"),
    ("2015+ charger", "Dodge", "Charger", "LD"),
    ("2015+ dodge charger", "Dodge", "Charger", "LD"),
    ("2015+ dodge charger hellcat", "Dodge", "Charger", "LD"),
    ("dodge charger hellcat", "Dodge", "Charger", "LD"),
    ("2008 challenger", "Dodge", "Challenger", "3rd Gen"),
    ("2008 dodge challenger", "Dodge", "Challenger", "3rd Gen"),
    ("2008-2014 challenger", "Dodge", "Challenger", "3rd Gen"),
    ("2008-2014 dodge challenger", "Dodge", "Challenger", "3rd Gen"),
    ("2009-2014 challenger", "Dodge", "Challenger", "3rd Gen"),
    ("2015+ challenger", "Dodge", "Challenger", "3rd Gen"),
    ("2015+ dodge challenger", "Dodge", "Challenger", "3rd Gen"),
    ("2015+ challenger hellcat", "Dodge", "Challenger", "3rd Gen"),
    ("challenger hellcat", "Dodge", "Challenger", "3rd Gen"),
    ("challenger demon", "Dodge", "Challenger", "3rd Gen"),
    ("2009-2014 challenger r/t", "Dodge", "Challenger", "3rd Gen"),
    ("2009-2014 challenger srt8", "Dodge", "Challenger", "3rd Gen"),
    ("alfa romeo 4c", "Alfa Romeo", "4C", "960"),
    ("alfa romeo giulia", "Alfa Romeo", "Giulia", "Type 952"),
    ("alfa romeo giulia quadrifoglio", "Alfa Romeo", "Giulia", "Type 952"),
    ("alfa romeo stelvio", "Alfa Romeo", "Stelvio", "Type 949"),
    ("stelvio quadrifoglio", "Alfa Romeo", "Stelvio", "Type 949"),
    ("12-16 range rover evoque", "Land Rover", "Range Rover Evoque", "L538"),
    ("12-19 range rover evoque", "Land Rover", "Range Rover Evoque", "L538"),
    ("13-15 jaguar xf", "Jaguar", "XF", "X250"),
    ("02-04 jaguar x-type", "Jaguar", "X-Type", "CF1"),
    ("saab 9-3", "Saab", "9-3", "YS3F"),
    ("volvo v40", "Volvo", "V40", "V1"),
    ("volvo s40", "Volvo", "S40", "V1"),
    ("2008-2014 smart fortwo", "Smart", "ForTwo", "W451"),
    ("12-19 fiat 500", "Fiat", "500", "312"),
    ("fiat 500 abarth", "Fiat", "500", "312"),
    ("04-08 pontiac grand prix", "Pontiac", "Grand Prix", "8th Gen"),
    ("12-15 mini coupé", "Mini", "Coupé", "R58"),
    ("mini coupé r59", "Mini", "Roadster", "R59"),
    ("v8 vantage", "Aston Martin", "Vantage", "V8 Vantage"),
    ("aston martin v8 vantage", "Aston Martin", "Vantage", "V8 Vantage"),
    ("v12 vantage", "Aston Martin", "Vantage", "V12 Vantage"),
    ("aston martin v12 vantage", "Aston Martin", "Vantage", "V12 Vantage"),
    ("aston martin vantage", "Aston Martin", "Vantage", "V8 Vantage"),
    ("aston martin vantage", "Aston Martin", "Vantage", "V12 Vantage"),
    ("00-05 toyota celica", "Toyota", "Celica", "7th Gen"),
    ("00-06 toyota celica", "Toyota", "Celica", "7th Gen"),
    ("1999-2005 toyota celica", "Toyota", "Celica", "7th Gen"),
    ("2000-2005 toyota celica", "Toyota", "Celica", "7th Gen"),
    ("90-93 toyota celica", "Toyota", "Celica", "5th Gen"),
    ("toyota celica", "Toyota", "Celica", "6th Gen"),
    ("toyota celica", "Toyota", "Celica", "7th Gen"),
    ("b48 supra", "Toyota", "Supra", "A90"),
    ("supra 2.0", "Toyota", "Supra", "A90"),
    ("supra 3.0", "Toyota", "Supra", "A90"),
    ("ae86", "Toyota", "AE86", "Zenki"),
    ("ae86", "Toyota", "AE86", "Kouki"),
    ("corolla ae86", "Toyota", "AE86", "Zenki"),
    ("corolla ae86", "Toyota", "AE86", "Kouki"),
    ("toyota corolla ae86", "Toyota", "AE86", "Zenki"),
    ("toyota corolla ae86", "Toyota", "AE86", "Kouki"),
    ("toyota ae86", "Toyota", "AE86", "Zenki"),
    ("toyota ae86", "Toyota", "AE86", "Kouki"),
    ("ae86 corolla", "Toyota", "AE86", "Zenki"),
    ("ae86 corolla", "Toyota", "AE86", "Kouki"),
    ("corolla gt-s (ae86)", "Toyota", "AE86", "Zenki"),
    ("4a-ge ae86", "Toyota", "AE86", "Zenki"),
    ("84-87 toyota corolla ae86", "Toyota", "AE86", "Zenki"),
    ("84-87 toyota corolla ae86", "Toyota", "AE86", "Kouki"),
    ("jza80", "Toyota", "Supra", "A80"),
    ("jza80 supra", "Toyota", "Supra", "A80"),
    ("supra jza80", "Toyota", "Supra", "A80"),
    ("toyota supra jza80", "Toyota", "Supra", "A80"),
    ("ma70", "Toyota", "Supra", "A70"),
    ("ma70 supra", "Toyota", "Supra", "A70"),
    ("7mgt supra", "Toyota", "Supra", "A70"),
    ("7m-gte", "Toyota", "Supra", "A70"),
    ("86-92 toyota supra", "Toyota", "Supra", "A70"),
    ("mk3 supra", "Toyota", "Supra", "A70"),
    ("supra mk3", "Toyota", "Supra", "A70"),
    ("mkiii supra", "Toyota", "Supra", "A70"),
    ("mk3 toyota supra", "Toyota", "Supra", "A70"),
    ("86-92 supra", "Toyota", "Supra", "A70"),
    ("1986-1992 toyota supra", "Toyota", "Supra", "A70"),
    ("1986-1992 supra", "Toyota", "Supra", "A70"),
    ("1993-1998 toyota supra", "Toyota", "Supra", "A80"),
    ("1993-1998 supra", "Toyota", "Supra", "A80"),
    ("mr2 spyder", "Toyota", "MR2", "W30"),
    ("toyota mr2 spyder", "Toyota", "MR2", "W30"),
    ("00-05 toyota mr2", "Toyota", "MR2", "W30"),
    ("00-07 toyota mr2", "Toyota", "MR2", "W30"),
    ("sw20", "Toyota", "MR2", "W20"),
    ("mr2 sw20", "Toyota", "MR2", "W20"),
    ("toyota mr2 sw20", "Toyota", "MR2", "W20"),
    ("sw20 mr2", "Toyota", "MR2", "W20"),
    ("aw11", "Toyota", "MR2", "W10"),
    ("mr2 aw11", "Toyota", "MR2", "W10"),
    ("toyota mr2 aw11", "Toyota", "MR2", "W10"),
    ("aw11 mr2", "Toyota", "MR2", "W10"),
    ("toyota mrs zzw30", "Toyota", "MR2", "W30"),
    ("mrs zzw30", "Toyota", "MR2", "W30"),
    ("93-97 toyota corolla", "Toyota", "Corolla", "E100"),
    ("93-02 toyota corolla", "Toyota", "Corolla", "E100"),
    ("corolla ae101", "Toyota", "Corolla", "E100"),
    ("corolla ae111", "Toyota", "Corolla", "E100"),
    ("toyota chaser", "Toyota", "Chaser", "JZX100"),
    ("toyota cressida", "Toyota", "Cressida", "MX83"),
    ("toyota cressida", "Toyota", "Cressida", "MX73"),
    ("cressida 89-92", "Toyota", "Cressida", "MX83"),
    ("cressida mx83", "Toyota", "Cressida", "MX83"),
    ("mx83 cressida", "Toyota", "Cressida", "MX83"),
    ("2jz-gte", "Toyota", "Supra", "A80"),
    ("2jzgte", "Toyota", "Supra", "A80"),
    ("1jz-gte", "Toyota", "Chaser", "JZX100"),
    ("1jzgte", "Toyota", "Chaser", "JZX100"),
    ("1jzgte vvti", "Toyota", "Chaser", "JZX100"),
    ("3s-gte", "Toyota", "MR2", "W20"),
    ("4u-gse", "Subaru", "BRZ", "ZC6"),
    ("4u-gse", "Toyota", "86", "ZN6"),
    ("02-06 nissan altima", "Nissan", "Altima", "L30"),
    ("07-12 nissan altima", "Nissan", "Altima", "L31"),
    ("07-18 nissan altima", "Nissan", "Altima", "L31"),
    ("13-18 nissan altima", "Nissan", "Altima", "L32"),
    ("nissan altima", "Nissan", "Altima", "L31"),
    ("nissan altima", "Nissan", "Altima", "L32"),
    ("00-06 nissan sentra", "Nissan", "Sentra", "B15"),
    ("07-12 nissan sentra", "Nissan", "Sentra", "B16"),
    ("13-19 nissan sentra", "Nissan", "Sentra", "B17"),
    ("nissan sentra", "Nissan", "Sentra", "B15"),
    ("nissan sentra", "Nissan", "Sentra", "B16"),
    ("00-03 nissan maxima", "Nissan", "Maxima", "A33"),
    ("04-08 nissan maxima", "Nissan", "Maxima", "A34"),
    ("09-14 nissan maxima", "Nissan", "Maxima", "A35"),
    ("07-18 nissan altima / 09-23 nissan maxima", "Nissan", "Altima", "L31"),
    ("07-18 nissan altima / 09-23 nissan maxima", "Nissan", "Maxima", "A35"),
    ("02-06 nissan altima / 04-08 nissan maxima", "Nissan", "Altima", "L30"),
    ("02-06 nissan altima / 04-08 nissan maxima", "Nissan", "Maxima", "A34"),
    ("nissan juke", "Nissan", "Juke", "F15"),
    ("10-17 nissan juke", "Nissan", "Juke", "F15"),
    ("10-17 juke", "Nissan", "Juke", "F15"),
    ("00-06 hyundai elantra", "Hyundai", "Elantra", "XD"),
    ("07-10 hyundai elantra", "Hyundai", "Elantra", "HD"),
    ("11-16 hyundai elantra", "Hyundai", "Elantra", "MD"),
    ("11-15 hyundai elantra", "Hyundai", "Elantra", "MD"),
    ("16-20 hyundai elantra", "Hyundai", "Elantra", "AD"),
    ("21-24 hyundai elantra", "Hyundai", "Elantra", "CN7"),
    ("hyundai elantra", "Hyundai", "Elantra", "MD"),
    ("hyundai elantra", "Hyundai", "Elantra", "AD"),
    ("97-99 hyundai tiburon", "Hyundai", "Tiburon", "RD1"),
    ("00-01 hyundai tiburon", "Hyundai", "Tiburon", "RD2"),
    ("03-08 hyundai tiburon", "Hyundai", "Tiburon", "GK"),
    ("hyundai tiburon", "Hyundai", "Tiburon", "GK"),
    ("10-12 hyundai genesis coupe", "Hyundai", "Genesis Coupe", "BK"),
    ("10-16 hyundai genesis coupe", "Hyundai", "Genesis Coupe", "BK"),
    ("10-16 hyundai genesis coupe", "Hyundai", "Genesis Coupe", "BK2"),
    ("13-16 hyundai genesis coupe", "Hyundai", "Genesis Coupe", "BK2"),
    ("hyundai genesis coupe", "Hyundai", "Genesis Coupe", "BK"),
    ("hyundai genesis coupe", "Hyundai", "Genesis Coupe", "BK2"),
    ("genesis coupe", "Hyundai", "Genesis Coupe", "BK"),
    ("genesis coupe", "Hyundai", "Genesis Coupe", "BK2"),
    ("genesis 2.0t", "Hyundai", "Genesis Coupe", "BK"),
    ("genesis 2.0t", "Hyundai", "Genesis Coupe", "BK2"),
    ("hyundai genesis coupe 2.0t", "Hyundai", "Genesis Coupe", "BK"),
    ("hyundai genesis coupe 2.0t", "Hyundai", "Genesis Coupe", "BK2"),
    ("hyundai genesis coupe 3.8", "Hyundai", "Genesis Coupe", "BK"),
    ("hyundai genesis coupe 3.8", "Hyundai", "Genesis Coupe", "BK2"),
    ("12-18 hyundai veloster", "Hyundai", "Veloster", "FS"),
    ("11-17 hyundai veloster", "Hyundai", "Veloster", "FS"),
    ("18-22 hyundai veloster", "Hyundai", "Veloster", "JS"),
    ("hyundai veloster", "Hyundai", "Veloster", "FS"),
    ("hyundai veloster", "Hyundai", "Veloster", "JS"),
    ("veloster turbo", "Hyundai", "Veloster", "FS"),
    ("96-98 acura tl", "Acura", "TL", "1st Gen"),
    ("98-01 acura tl", "Acura", "TL", "2nd Gen"),
    ("99-03 acura tl", "Acura", "TL", "2nd Gen"),
    ("04-08 acura tl", "Acura", "TL", "3rd Gen"),
    ("09-14 acura tl", "Acura", "TL", "4th Gen"),
    ("acura tl", "Acura", "TL", "3rd Gen"),
    ("acura tl", "Acura", "TL", "4th Gen"),
    ("07-12 acura rdx", "Acura", "RDX", "TB1/TB2"),
    ("13-18 acura rdx", "Acura", "RDX", "TB3/TB4"),
    ("2019-2021 acura rdx", "Acura", "RDX", "TC1"),
    ("2019+ acura rdx", "Acura", "RDX", "TC1"),
    ("2019 acura rdx", "Acura", "RDX", "TC1"),
    ("acura rdx", "Acura", "RDX", "TB1/TB2"),
    ("acura rdx", "Acura", "RDX", "TB3/TB4"),
    ("13-15 acura ilx", "Acura", "ILX", "DE3"),
    ("16-22 acura ilx", "Acura", "ILX", "DE3"),
    ("16-23 acura ilx", "Acura", "ILX", "DE3"),
    ("acura ilx", "Acura", "ILX", "DE3"),
    ("acura integra / rsx", "Acura", "RSX", "DC5"),
    ("acura integra/rsx", "Acura", "RSX", "DC5"),
    ("02-06 acura integra / rsx", "Acura", "RSX", "DC5"),
    ("94-01 acura integra", "Acura", "Integra", "3rd Gen"),
    ("97-01 acura integra", "Acura", "Integra", "3rd Gen"),
    ("02-06 acura integra", "Acura", "Integra", "4th Gen"),
    ("acura integra", "Acura", "Integra", "3rd Gen"),
    ("acura integra", "Acura", "Integra", "4th Gen"),
    ("acura integra type-r", "Acura", "Integra", "3rd Gen"),
    ("integra type-r", "Acura", "Integra", "3rd Gen"),
    ("2022 acura integra", "Acura", "Integra", "5th Gen"),
    ("2023 acura integra", "Acura", "Integra", "5th Gen"),
    ("2024 acura integra", "Acura", "Integra", "5th Gen"),
    ("2023+ acura integra", "Acura", "Integra", "5th Gen"),
    ("2023+ acura integra type-s", "Acura", "Integra", "5th Gen"),
    ("2024 integra type s", "Acura", "Integra", "5th Gen"),
    ("integra type s", "Acura", "Integra", "5th Gen"),
    ("90-93 acura da integra", "Acura", "Integra", "2nd Gen"),
    ("da integra", "Acura", "Integra", "2nd Gen"),
    ("acura da integra", "Acura", "Integra", "2nd Gen"),
    ("02-06 honda cr-v", "Honda", "CR-V", "RD4/RD5/RD6/RD7"),
    ("07-11 honda cr-v", "Honda", "CR-V", "RE"),
    ("12-16 honda cr-v", "Honda", "CR-V", "RM"),
    ("17-22 honda cr-v", "Honda", "CR-V", "RW"),
    ("honda cr-v", "Honda", "CR-V", "RE"),
    ("honda cr-v", "Honda", "CR-V", "RM"),
    ("16-22 honda hr-v", "Honda", "HR-V", "RU"),
    ("23-24 honda hr-v", "Honda", "HR-V", "RS"),
    ("honda hr-v", "Honda", "HR-V", "RU"),
    ("hr-v rs", "Honda", "HR-V", "RS"),
    ("honda hr-v rs", "Honda", "HR-V", "RS"),
    ("hr-v ru", "Honda", "HR-V", "RU"),
    ("honda hr-v ru", "Honda", "HR-V", "RU"),
    ("03-11 honda element", "Honda", "Element", "YH"),
    ("honda element", "Honda", "Element", "YH"),
    ("99-04 honda odyssey", "Honda", "Odyssey", "RL"),
    ("honda odyssey rl", "Honda", "Odyssey", "RL"),
    ("05-10 honda odyssey", "Honda", "Odyssey", "RL3"),
    ("11-17 honda odyssey", "Honda", "Odyssey", "RL4"),
    ("18-24 honda odyssey", "Honda", "Odyssey", "RL5"),
    ("honda odyssey", "Honda", "Odyssey", "RL3"),
    ("honda odyssey", "Honda", "Odyssey", "RL4"),
    ("10-14 honda insight", "Honda", "Insight", "2nd Gen"),
    ("honda insight", "Honda", "Insight", "2nd Gen"),
    ("07-08 honda fit", "Honda", "Fit", "1st Gen"),
    ("09-13 honda fit", "Honda", "Fit", "2nd Gen"),
    ("15-20 honda fit", "Honda", "Fit", "3rd Gen"),
    ("honda fit", "Honda", "Fit", "2nd Gen"),
    ("honda fit", "Honda", "Fit", "3rd Gen"),
    ("07-13 acura mdx", "Acura", "MDX", "2nd Gen"),
    ("14-20 acura mdx", "Acura", "MDX", "3rd Gen"),
    ("14-21 acura mdx", "Acura", "MDX", "3rd Gen"),
    ("acura mdx", "Acura", "MDX", "2nd Gen"),
    ("acura mdx", "Acura", "MDX", "3rd Gen"),
    ("14-20 acura rlx", "Acura", "RLX", "KC2"),
    ("acura rlx", "Acura", "RLX", "KC2"),
    ("96-04 acura rl", "Acura", "RL", "KA9"),
    ("05-12 acura rl", "Acura", "RL", "KB1"),
    ("acura rl", "Acura", "RL", "KA9"),
    ("acura rl", "Acura", "RL", "KB1"),
    ("01-05 honda civic", "Honda", "Civic", "7th Gen"),
    ("06-11 honda civic", "Honda", "Civic", "8th Gen"),
    ("2006-2011 honda civic", "Honda", "Civic", "8th Gen"),
    ("12-15 honda civic", "Honda", "Civic", "9th Gen"),
    ("2012-2015 honda civic", "Honda", "Civic", "9th Gen"),
    ("16-21 honda civic", "Honda", "Civic", "10th Gen"),
    ("2016-2021 honda civic", "Honda", "Civic", "10th Gen"),
    ("17-21 honda civic", "Honda", "Civic", "10th Gen"),
    ("22-24 honda civic", "Honda", "Civic", "11th Gen"),
    ("honda civic si", "Honda", "Civic", "8th Gen"),
    ("honda civic si", "Honda", "Civic", "9th Gen"),
    ("honda civic si", "Honda", "Civic", "10th Gen"),
    ("2017-2019 honda civic si", "Honda", "Civic", "10th Gen"),
    ("2017-2020 honda civic type r", "Honda", "Civic Type R", "FK8"),
    ("2017-2020 civic type r", "Honda", "Civic Type R", "FK8"),
    ("2017-2021 honda civic type r", "Honda", "Civic Type R", "FK8"),
    ("2017-2022 honda cr-v", "Honda", "CR-V", "RW"),
    ("2023+ honda cr-v", "Honda", "CR-V", "RW"),
    ("2018-2022 honda accord", "Honda", "Accord", "10th Gen"),
    ("2012-2015 honda civic si", "Honda", "Civic", "9th Gen"),
    ("2017-2021 honda civic si", "Honda", "Civic", "10th Gen"),
    ("civic fe1", "Honda", "Civic", "11th Gen"),
    ("fe1 civic", "Honda", "Civic", "11th Gen"),
    ("honda civic fe1", "Honda", "Civic", "11th Gen"),
    ("civic si fe1", "Honda", "Civic", "11th Gen"),
    ("civic (fe1)", "Honda", "Civic", "11th Gen"),
    ("fl1", "Honda", "Civic", "11th Gen"),
    ("fl2", "Honda", "Civic", "11th Gen"),
    ("civic fc", "Honda", "Civic", "10th Gen"),
    ("civic (fc)", "Honda", "Civic", "10th Gen"),
    ("fc civic", "Honda", "Civic", "10th Gen"),
    ("fk7", "Honda", "Civic", "10th Gen"),
    ("civic fk7", "Honda", "Civic", "10th Gen"),
    ("civic em", "Honda", "Civic", "7th Gen"),
    ("civic (em)", "Honda", "Civic", "7th Gen"),
    ("em1", "Honda", "Civic", "7th Gen"),
    ("em2", "Honda", "Civic", "7th Gen"),
    ("civic ep3", "Honda", "Civic Type R", "EP3"),
    ("ep3 civic", "Honda", "Civic Type R", "EP3"),
    ("ek9", "Honda", "Civic Type R", "EK9"),
    ("ek9 civic", "Honda", "Civic Type R", "EK9"),
    ("d16", "Honda", "Civic", "6th Gen"),
    ("honda civic d16", "Honda", "Civic", "6th Gen"),
    ("ej civic", "Honda", "Civic", "6th Gen"),
    ("ek civic", "Honda", "Civic", "6th Gen"),
    ("civic (ej / ek)", "Honda", "Civic", "6th Gen"),
    ("civic (ej/ek)", "Honda", "Civic", "6th Gen"),
    ("84-87 honda civic", "Honda", "Civic", "3rd Gen"),
    ("88-91 honda civic", "Honda", "Civic", "4th Gen"),
    ("92-95 honda civic", "Honda", "Civic", "5th Gen"),
    ("96-00 honda civic", "Honda", "Civic", "6th Gen"),
    ("eg civic", "Honda", "Civic", "5th Gen"),
    ("honda eg civic", "Honda", "Civic", "5th Gen"),
    ("honda ek civic", "Honda", "Civic", "6th Gen"),
    ("78-79 honda civic", "Honda", "Civic", "1st Gen"),
    ("honda civic cvcc", "Honda", "Civic", "1st Gen"),
    ("92-01 honda prelude", "Honda", "Prelude", "4th Gen"),
    ("92-01 honda prelude", "Honda", "Prelude", "5th Gen"),
    ("94-98 honda odyssey", "Honda", "Odyssey", "RA"),
    ("94-98 honda odyssey (ra1-5)", "Honda", "Odyssey", "RA"),
    ("honda odyssey ra", "Honda", "Odyssey", "RA"),
    ("03-07 honda accord", "Honda", "Accord", "7th Gen"),
    ("08-12 honda accord", "Honda", "Accord", "8th Gen"),
    ("13-17 honda accord", "Honda", "Accord", "9th Gen"),
    ("18-22 honda accord", "Honda", "Accord", "10th Gen"),
    ("90-97 honda accord", "Honda", "Accord", "4th Gen"),
    ("90-97 honda accord", "Honda", "Accord", "5th Gen"),
    ("98-02 honda accord", "Honda", "Accord", "6th Gen"),
    ("97-01 toyota camry", "Toyota", "Camry", "XV20"),
    ("02-06 toyota camry", "Toyota", "Camry", "XV30"),
    ("07-11 toyota camry", "Toyota", "Camry", "XV40"),
    ("12-17 toyota camry", "Toyota", "Camry", "XV50"),
    ("18-24 toyota camry", "Toyota", "Camry", "XV70"),
    ("toyota camry", "Toyota", "Camry", "XV40"),
    ("toyota camry", "Toyota", "Camry", "XV50"),
    ("toyota camry", "Toyota", "Camry", "XV70"),
    ("03-08 toyota corolla", "Toyota", "Corolla", "E140"),
    ("09-13 toyota corolla", "Toyota", "Corolla", "E150"),
    ("09-19 toyota corolla", "Toyota", "Corolla", "E150"),
    ("09-19 toyota corolla", "Toyota", "Corolla", "E170"),
    ("14-18 toyota corolla", "Toyota", "Corolla", "E170"),
    ("19-24 toyota corolla", "Toyota", "Corolla", "E210"),
    ("toyota corolla", "Toyota", "Corolla", "E140"),
    ("toyota corolla", "Toyota", "Corolla", "E150"),
    ("toyota corolla", "Toyota", "Corolla", "E170"),
    ("00-03 toyota prius", "Toyota", "Prius", "NHW11"),
    ("01-03 toyota prius", "Toyota", "Prius", "NHW11"),
    ("04-09 toyota prius", "Toyota", "Prius", "XW20"),
    ("10-15 toyota prius", "Toyota", "Prius", "ZVW30"),
    ("16-22 toyota prius", "Toyota", "Prius", "ZVW50"),
    ("23-24 toyota prius", "Toyota", "Prius", "ZVW60"),
    ("toyota prius", "Toyota", "Prius", "XW20"),
    ("toyota prius", "Toyota", "Prius", "ZVW30"),
    ("prius zvw30", "Toyota", "Prius", "ZVW30"),
    ("06-11 toyota yaris", "Toyota", "Yaris", "XP90"),
    ("07-11 toyota yaris", "Toyota", "Yaris", "XP90"),
    ("12-18 toyota yaris", "Toyota", "Yaris", "XP130"),
    ("12-23 toyota yaris", "Toyota", "Yaris", "XP130"),
    ("toyota yaris", "Toyota", "Yaris", "XP90"),
    ("toyota yaris", "Toyota", "Yaris", "XP130"),
    ("00-05 toyota echo", "Toyota", "Echo", "P10"),
    ("toyota echo", "Toyota", "Echo", "P10"),
    ("09-17 toyota venza", "Toyota", "Venza", "1st Gen"),
    ("toyota venza", "Toyota", "Venza", "1st Gen"),
    ("toyota venza", "Toyota", "Venza", "2nd Gen"),
    ("18-24 toyota c-hr", "Toyota", "C-HR", "AX10"),
    ("toyota c-hr", "Toyota", "C-HR", "AX10"),
    ("03-08 toyota matrix", "Toyota", "Matrix", "E130"),
    ("09-13 toyota matrix", "Toyota", "Matrix", "E150"),
    ("toyota matrix", "Toyota", "Matrix", "E130"),
    ("toyota matrix", "Toyota", "Matrix", "E150"),
    ("03-08 toyota corolla / altis / matrix", "Toyota", "Corolla", "E140"),
    ("03-08 toyota corolla / altis / matrix", "Toyota", "Matrix", "E130"),
    ("lexus is250", "Lexus", "IS", "XE20"),
    ("lexus is250", "Lexus", "IS", "XE30"),
    ("lexus is350", "Lexus", "IS", "XE20"),
    ("lexus is350", "Lexus", "IS", "XE30"),
    ("lexus is300", "Lexus", "IS", "XE10"),
    ("lexus is300", "Lexus", "IS", "XE20"),
    ("lexus is200", "Lexus", "IS", "XE10"),
    ("lexus is-f", "Lexus", "IS F", "XE20"),
    ("lexus isf", "Lexus", "IS F", "XE20"),
    ("06-13 lexus is", "Lexus", "IS", "XE20"),
    ("99-05 lexus is", "Lexus", "IS", "XE10"),
    ("14-20 lexus is", "Lexus", "IS", "XE30"),
    ("lexus gs300", "Lexus", "GS", "JZS160"),
    ("lexus gs400", "Lexus", "GS", "JZS160"),
    ("lexus gs430", "Lexus", "GS", "JZS160"),
    ("lexus gs430", "Lexus", "GS", "GRS190"),
    ("lexus gs350", "Lexus", "GS", "GRS190"),
    ("lexus gs350", "Lexus", "GS", "GRL10"),
    ("lexus gs300", "Lexus", "GS", "GRS190"),
    ("06-11 lexus gs", "Lexus", "GS", "GRS190"),
    ("12-20 lexus gs", "Lexus", "GS", "GRL10"),
    ("98-05 lexus gs", "Lexus", "GS", "JZS160"),
    ("97-05 lexus gs400", "Lexus", "GS", "JZS160"),
    ("lexus gs400 jzs161", "Lexus", "GS", "JZS160"),
    ("jzs161", "Lexus", "GS", "JZS160"),
    ("lexus is300 sxe10", "Lexus", "IS", "XE10"),
    ("is300 sxe10", "Lexus", "IS", "XE10"),
    ("sxe10", "Lexus", "IS", "XE10"),
    ("18-23 lexus is", "Lexus", "IS", "XE30"),
    ("10-15 lexus is250c", "Lexus", "IS", "XE20"),
    ("toyota is300", "Lexus", "IS", "XE10"),
    ("is300 2000-2005", "Lexus", "IS", "XE10"),
    ("2000-2005 is300", "Lexus", "IS", "XE10"),
    ("is300 1998-2005", "Lexus", "IS", "XE10"),
    ("95-00 lexus ls400", "Lexus", "LS", "UCF10"),
    ("lexus ls400", "Lexus", "LS", "UCF10"),
    ("04-09 lexus rx330", "Lexus", "RX", "XU30"),
    ("04-09 lexus rx350", "Lexus", "RX", "XU30"),
    ("00-05 mitsubishi eclipse", "Mitsubishi", "Eclipse", "3rd Gen"),
    ("06-12 mitsubishi eclipse", "Mitsubishi", "Eclipse", "4th Gen"),
    ("mitsubishi eclipse", "Mitsubishi", "Eclipse", "3rd Gen"),
    ("mitsubishi eclipse", "Mitsubishi", "Eclipse", "4th Gen"),
    ("mitsubishi lancer", "Mitsubishi", "Lancer", "CJ"),
    ("02-07 mitsubishi lancer", "Mitsubishi", "Lancer", "CS/CT"),
    ("08-17 mitsubishi lancer", "Mitsubishi", "Lancer", "CJ"),
    ("lancer gt", "Mitsubishi", "Lancer", "CJ"),
    ("lancer gts", "Mitsubishi", "Lancer", "CJ"),
    ("lancer se", "Mitsubishi", "Lancer", "CJ"),
    ("03-06 mitsubishi outlander", "Mitsubishi", "Outlander", "1st Gen"),
    ("07-13 mitsubishi outlander", "Mitsubishi", "Outlander", "2nd Gen"),
    ("14-21 mitsubishi outlander", "Mitsubishi", "Outlander", "3rd Gen"),
    ("mitsubishi outlander", "Mitsubishi", "Outlander", "2nd Gen"),
    ("mitsubishi outlander", "Mitsubishi", "Outlander", "3rd Gen"),
    ("outlander gt", "Mitsubishi", "Outlander", "3rd Gen"),
    ("mini cooper r50", "Mini", "Cooper", "R50/R52/R53"),
    ("mini cooper r52", "Mini", "Cooper", "R50/R52/R53"),
    ("mini cooper r53", "Mini", "Cooper", "R50/R52/R53"),
    ("mini r50", "Mini", "Cooper", "R50/R52/R53"),
    ("mini r53", "Mini", "Cooper", "R50/R52/R53"),
    ("02-06 mini cooper", "Mini", "Cooper", "R50/R52/R53"),
    ("mini cooper r56", "Mini", "Cooper", "R55/R56/R57/R58/R59"),
    ("mini cooper r55", "Mini", "Cooper", "R55/R56/R57/R58/R59"),
    ("mini r56", "Mini", "Cooper", "R55/R56/R57/R58/R59"),
    ("07-13 mini cooper", "Mini", "Cooper", "R55/R56/R57/R58/R59"),
    ("mini cooper f56", "Mini", "Cooper", "F55/F56/F57"),
    ("mini cooper f55", "Mini", "Cooper", "F55/F56/F57"),
    ("mini f56", "Mini", "Cooper", "F55/F56/F57"),
    ("14-24 mini cooper", "Mini", "Cooper", "F55/F56/F57"),
    ("14-23 mini cooper", "Mini", "Cooper", "F55/F56/F57"),
    ("mini countryman r60", "Mini", "Countryman", "R60"),
    ("mini r60", "Mini", "Countryman", "R60"),
    ("11-16 mini countryman", "Mini", "Countryman", "R60"),
    ("mini countryman f60", "Mini", "Countryman", "F60"),
    ("mini f60", "Mini", "Countryman", "F60"),
    ("17-23 mini countryman", "Mini", "Countryman", "F60"),
    ("04-10 volkswagen touareg", "Volkswagen", "Touareg", "7L"),
    ("04-10 vw touareg", "Volkswagen", "Touareg", "7L"),
    ("11-18 volkswagen touareg", "Volkswagen", "Touareg", "7P"),
    ("11-18 vw touareg", "Volkswagen", "Touareg", "7P"),
    ("volkswagen touareg", "Volkswagen", "Touareg", "7L"),
    ("volkswagen touareg", "Volkswagen", "Touareg", "7P"),
    ("vw touareg", "Volkswagen", "Touareg", "7L"),
    ("vw touareg", "Volkswagen", "Touareg", "7P"),
    ("touareg", "Volkswagen", "Touareg", "7L"),
    ("touareg", "Volkswagen", "Touareg", "7P"),
    ("mk5 volkswagen r32", "Volkswagen", "R32", "Mk5"),
    ("mkv volkswagen r32", "Volkswagen", "R32", "Mk5"),
    ("mk4 volkswagen r32", "Volkswagen", "R32", "Mk4"),
    ("mkiv volkswagen r32", "Volkswagen", "R32", "Mk4"),
    ("2004 volkswagen golf iv r32", "Volkswagen", "R32", "Mk4"),
    ("volkswagen golf iv r32", "Volkswagen", "R32", "Mk4"),
    ("golf iv r32 4motion", "Volkswagen", "R32", "Mk4"),
    ("volkswagen golf v r32", "Volkswagen", "R32", "Mk5"),
    ("golf v r32", "Volkswagen", "R32", "Mk5"),
    ("06-11 volkswagen passat (b6)", "Volkswagen", "Passat", "B6"),
    ("volkswagen passat b6", "Volkswagen", "Passat", "B6"),
    ("volkswagen passat b7", "Volkswagen", "Passat", "B7"),
    ("09-17 volkswagen passat cc", "Volkswagen", "Passat CC", "B6/B7"),
    ("volkswagen passat cc", "Volkswagen", "Passat CC", "B6/B7"),
    ("02-04 volkswagen passat w8", "Volkswagen", "Passat", "B5/B5.5"),
    ("passat w8", "Volkswagen", "Passat", "B5/B5.5"),
    ("passat 3bs", "Volkswagen", "Passat", "B5/B5.5"),
    ("84-97 volkswagen golf", "Volkswagen", "Golf", "Mk2"),
    ("84-97 volkswagen golf", "Volkswagen", "Golf", "Mk3"),
    ("1987-1992 vw golf", "Volkswagen", "Golf", "Mk2"),
    ("1993-1998 vw golf", "Volkswagen", "Golf", "Mk3"),
    ("1999-2005 volkswagen golf", "Volkswagen", "Golf", "Mk4"),
    ("1999-2005 vw golf/jetta", "Volkswagen", "Golf", "Mk4"),
    ("1999-2005 vw golf/jetta", "Volkswagen", "Jetta", "Mk4"),
    ("1999-2005 vw golf/jetta/beetle", "Volkswagen", "Golf", "Mk4"),
    ("1999-2005 vw golf/jetta/beetle", "Volkswagen", "Jetta", "Mk4"),
    ("00-04 subaru legacy", "Subaru", "Legacy", "BE/BH"),
    ("subaru legacy be / bh", "Subaru", "Legacy", "BE/BH"),
    ("subaru legacy be/bh", "Subaru", "Legacy", "BE/BH"),
    ("05-09 subaru legacy", "Subaru", "Legacy", "BL/BP"),
    ("subaru legacy bl / bp", "Subaru", "Legacy", "BL/BP"),
    ("subaru legacy bm9", "Subaru", "Legacy", "BM/BR"),
    ("subaru legacy bm / br", "Subaru", "Legacy", "BM/BR"),
    ("subaru legacy bn9", "Subaru", "Legacy", "BN/BS"),
    ("subaru legacy bn / bs", "Subaru", "Legacy", "BN/BS"),
    ("17-23 subaru impreza", "Subaru", "Impreza", "GP/GJ"),
    ("subaru impreza sport", "Subaru", "Impreza", "GP/GJ"),
    ("subaru impreza base", "Subaru", "Impreza", "GP/GJ"),
    ("2006-2009 legacy gt", "Subaru", "Legacy GT", "BL/BP"),
    ("2006-2009 legacy spec b", "Subaru", "Legacy GT", "BL/BP"),
    ("legacy spec b", "Subaru", "Legacy GT", "BL/BP"),
    ("legacy gt spec b", "Subaru", "Legacy GT", "BL/BP"),
    ("subaru legacy gt", "Subaru", "Legacy GT", "BL/BP"),
    ("09-14 hyundai genesis sedan", "Genesis", "G80", "DH"),
    ("15-16 hyundai genesis sedan", "Genesis", "G80", "DH"),
    ("hyundai genesis sedan", "Genesis", "G80", "DH"),
    ("subaru outback bl / bp", "Subaru", "Outback XT", "BL/BP"),
    ("subaru outback bm / br", "Subaru", "Outback XT", "BM/BR"),
    ("05-09 subaru outback", "Subaru", "Outback XT", "BL/BP"),
    ("10-14 subaru outback", "Subaru", "Outback XT", "BM/BR"),
    # --- M004/S02 corpus-derived additions ---
    # --- M004/S04 corpus-derived additions ---
    ("2023+ honda civic type r", "Honda", "Civic Type R", "FL5"),
    ("2023+ civic type r", "Honda", "Civic Type R", "FL5"),
]

_SHORT_PHRASE_MAX_LEN = 8

_AUDI_R8_42_PHRASES = ("r8 42", "42 r8", "r8 type 42", "audi r8 42", "audi r8 type 42")
_CHARGER_LB_PHRASES = ("charger lb", "dodge charger lb")


_NUMERIC_UNIT_SUFFIXES = (
    "%",
    "mm",
    "cm",
    "kph",
    "mph",
    "kw",
    "hp",
    "bhp",
    "whp",
    "nm",
    "lb",
    "lbs",
    "lb-ft",
    "ft-lb",
    "ft/lb",
    "l",
    "t",
    "tfsi",
    "tsi",
    "in",
    "ci",
    "cid",
    "cu",
    "cubic",
)


def _is_numeric_measurement_context(text_lower: str, phrase_lower: str) -> bool:
    """Whether every occurrence of a bare-numeric phrase reads as a measurement.

    A number followed by a unit, or sitting after a decimal point, is a bore or
    displacement figure rather than a chassis code, so inference must not fire on it.
    """
    if not phrase_lower.isdigit():
        return False
    if re.search(rf"[0-9][.,]{re.escape(phrase_lower)}\b", text_lower):
        return True
    pattern = re.compile(r"\b" + re.escape(phrase_lower) + r'\b\s*(["A-Za-z%\-/]+)?')
    any_match = False
    for m in pattern.finditer(text_lower):
        any_match = True
        suffix = (m.group(1) or "").lower()
        if suffix.startswith('"'):
            continue
        if not suffix.startswith(_NUMERIC_UNIT_SUFFIXES):
            return False
    return any_match


def _phrase_matches(text: str, phrase: str) -> bool:
    """Return True if phrase appears in text (case-insensitive). Word boundaries for short alphanumeric phrases."""
    if not text or not phrase:
        return False
    lower = text.lower()
    phrase_lower = phrase.lower()
    if phrase_lower not in lower:
        return False
    if len(phrase) <= _SHORT_PHRASE_MAX_LEN and phrase.replace("/", "").replace(" ", "").isalnum():
        if not re.search(r"\b" + re.escape(phrase_lower.replace("/", r"/")) + r"\b", lower):
            return False
        if phrase_lower.isdigit() and _is_numeric_measurement_context(lower, phrase_lower):
            return False
        return True
    return True


def _reject_audi_r8_42_false_positive(text: str) -> bool:
    """Return True if text likely has '42' from decimals/measurements (0.42 Mu, 4.2L) not Audi R8 type 42."""
    lower = text.lower()
    if re.search(r"[0-9.]\s*42\s*(?:mu|mm|%|whp|nm|lb)", lower):
        return True
    if re.search(r"\b0\.42\b", lower) or re.search(r"\b4\.2\s*(?:l|liter)", lower):
        return True
    return False


def _reject_charger_lb_false_positive(text: str) -> bool:
    """Return True if 'lb' is from ft-lb or lug bolt(s), not Dodge Charger LB."""
    lower = text.lower()
    if "ft-lb" in lower or "ft lb" in lower or "lug bolt" in lower or "lug bolts" in lower:
        return True
    return False


def _alias_phrase_matches(combined: str, phrase: str) -> bool:
    """Like _phrase_matches but with extra guards for known false-positive aliases."""
    if not _phrase_matches(combined, phrase):
        return False
    phrase_lower = phrase.lower()
    if phrase_lower in _AUDI_R8_42_PHRASES and _reject_audi_r8_42_false_positive(combined):
        return False
    if phrase_lower in _CHARGER_LB_PHRASES and _reject_charger_lb_false_positive(combined):
        return False
    return True


def infer_car_generations(
    name: Optional[str],
    description: Optional[str],
    product_url: Optional[str] = None,
) -> list[tuple[str, str, str]]:
    """Infer (make, model, generation_name) triples from a part's text and URL.

    Aliases come first, then phrase matches from the seed data. Year narrowing applies
    only when the text carries exactly one coherent fitment span.
    """
    name = (name or "").strip()
    description = (description or "").strip()
    url = (product_url or "").strip()
    url_normalized = re.sub(r"[-_/]+", " ", url)
    name_normalized = re.sub(r"[()]", " ", name)
    desc_normalized = re.sub(r"[()]", " ", description)
    combined = re.sub(r" {2,}", " ", f"{name_normalized} {desc_normalized} {url_normalized}").strip()
    if not combined:
        return []

    seen: set[tuple[str, str, str]] = set()
    result: list[tuple[str, str, str]] = []

    for phrase, make, model, gen_name in CAR_ALIASES:
        if (make, model, gen_name) in seen:
            continue
        if _alias_phrase_matches(combined, phrase):
            seen.add((make, model, gen_name))
            result.append((make, model, gen_name))

    for phrase, make, model, gen_name in PHRASE_TRIPLES:
        if (make, model, gen_name) in seen:
            continue
        if _phrase_matches(combined, phrase):
            seen.add((make, model, gen_name))
            result.append((make, model, gen_name))

    if not result:
        return result

    return _maybe_narrow_by_combined_year_ranges(result, combined)


import datetime as _dt

_YEAR_LO: int = 1960
_YEAR_HI_OFFSET: int = 1

_RANGE_SEP = r"\s*(?:[-–—]|to)\s*"
_YYYY_YYYY_RE = re.compile(rf"\b((?:19|20)\d{{2}})(?:\.5)?{_RANGE_SEP}((?:19|20)\d{{2}})(?:\.5)?\b")
_YYYY_YY_RE = re.compile(rf"\b((?:19|20)\d{{2}})(?:\.5)?{_RANGE_SEP}(\d{{2}})(?!\d)")
_YY_YY_RE = re.compile(rf"(?<![\d.])(\d{{2}}){_RANGE_SEP}(\d{{2}})(?!\d)")
_YYYY_PLUS_RE = re.compile(r"(?:(?<=\s)|(?<=^)|(?<=\()|(?<=MY))((?:19|20)\d{2})(?:\.5)?\s*\+")
_SINGLE_YEAR_RE = re.compile(
    r"(?:(?<=\s)|(?<=^)|(?<=\()|(?<=MY)|(?<=MY ))((?:19|20)\d{2})(?:\.5)?(?!\d)",
    re.IGNORECASE,
)


def _validate_year_range(y1: int, y2: int) -> Optional[tuple[int, int]]:
    """Return (y1, y2) clamped+ordered if plausible, else None."""
    cy = _dt.datetime.now(_dt.timezone.utc).year
    hi = cy + _YEAR_HI_OFFSET
    if not (_YEAR_LO <= y1 <= hi):
        return None
    if not (_YEAR_LO <= y2 <= hi):
        return None
    if y1 > y2:
        return None
    return (y1, y2)


def _infer_century(start_year: int, two_digit_tail: int) -> int:
    """Convert a 2-digit year tail into a 4-digit year using the start year's century.
    If the inferred year is less than start_year (e.g. start=1995, tail=04 would
    naively give 1904), bump to the next century (-> 2004)."""
    century = (start_year // 100) * 100
    candidate = century + two_digit_tail
    if candidate < start_year:
        candidate += 100
    return candidate


def _infer_yy_yy_century(yy1: int, yy2: int) -> Optional[tuple[int, int]]:
    """A 2-digit-pair like '92-95' or '08-14' needs century inference.
    Heuristic: 60-99 -> 19xx, 00-59 -> 20xx (covers MY 1960 forward; 60+ years
    of cars). Both years must satisfy plausibility individually."""

    def _y(yy: int) -> int:
        """Expand a two digit year, 60 to 99 into the 1900s and the rest into the 2000s."""
        return 1900 + yy if 60 <= yy <= 99 else 2000 + yy

    y1, y2 = _y(yy1), _y(yy2)
    return _validate_year_range(y1, y2)


def extract_year_ranges(text: Optional[str]) -> list[tuple[int, int]]:
    """Extract every plausible (start_year, end_year) range from `text`.

    A single year returns as `(Y, Y)` and `YYYY+` as `(Y, current_year + 1)`. Longer
    forms are matched and masked first so a range's start year is not re-read alone.
    """
    if not text:
        return []
    cy = _dt.datetime.now(_dt.timezone.utc).year
    open_ended_hi = cy + _YEAR_HI_OFFSET

    seen: set[tuple[int, int]] = set()
    out: list[tuple[int, int]] = []

    masked = list(text)

    def _mask(start: int, end: int) -> None:
        """Blank out a matched span so a shorter pattern cannot re-read part of it."""
        for i in range(start, end):
            masked[i] = " "

    def _emit(rng: Optional[tuple[int, int]]) -> None:
        """Record a range, ignoring None and anything already seen."""
        if rng is None:
            return
        if rng in seen:
            return
        seen.add(rng)
        out.append(rng)

    for m in _YYYY_YYYY_RE.finditer(text):
        y1, y2 = int(m.group(1)), int(m.group(2))
        _emit(_validate_year_range(y1, y2))
        _mask(m.start(), m.end())

    masked_text = "".join(masked)

    for m in _YYYY_YY_RE.finditer(masked_text):
        y1 = int(m.group(1))
        tail = int(m.group(2))
        y2 = _infer_century(y1, tail)
        _emit(_validate_year_range(y1, y2))
        _mask(m.start(), m.end())
    masked_text = "".join(masked)

    for m in _YY_YY_RE.finditer(masked_text):
        yy1 = int(m.group(1))
        yy2 = int(m.group(2))
        _emit(_infer_yy_yy_century(yy1, yy2))
        _mask(m.start(), m.end())
    masked_text = "".join(masked)

    for m in _YYYY_PLUS_RE.finditer(masked_text):
        y1 = int(m.group(1))
        _emit(_validate_year_range(y1, open_ended_hi))
        _mask(m.start(), m.end())
    masked_text = "".join(masked)

    for m in _SINGLE_YEAR_RE.finditer(masked_text):
        y = int(m.group(1))
        _emit(_validate_year_range(y, y))

    return out


def _extract_year_ranges_with_spans(
    text: Optional[str],
) -> list[tuple[tuple[int, int], int, int]]:
    """Same as extract_year_ranges, but each entry also carries (span_start,
    span_end) for the matched substring. Used by extract_fitment_candidates
    to pair year-ranges with nearby (make, model) phrase matches by distance.
    """
    if not text:
        return []
    cy = _dt.datetime.now(_dt.timezone.utc).year
    open_ended_hi = cy + _YEAR_HI_OFFSET

    seen: set[tuple[int, int]] = set()
    out: list[tuple[tuple[int, int], int, int]] = []

    masked = list(text)

    def _mask(start: int, end: int) -> None:
        """Blank out a matched span so a shorter pattern cannot re-read part of it."""
        for i in range(start, end):
            masked[i] = " "

    def _emit(rng: Optional[tuple[int, int]], span_start: int, span_end: int) -> None:
        """Record a range with its span, ignoring None and anything already seen."""
        if rng is None or rng in seen:
            return
        seen.add(rng)
        out.append((rng, span_start, span_end))

    for m in _YYYY_YYYY_RE.finditer(text):
        y1, y2 = int(m.group(1)), int(m.group(2))
        _emit(_validate_year_range(y1, y2), m.start(), m.end())
        _mask(m.start(), m.end())
    masked_text = "".join(masked)

    for m in _YYYY_YY_RE.finditer(masked_text):
        y1 = int(m.group(1))
        tail = int(m.group(2))
        y2 = _infer_century(y1, tail)
        _emit(_validate_year_range(y1, y2), m.start(), m.end())
        _mask(m.start(), m.end())
    masked_text = "".join(masked)

    for m in _YY_YY_RE.finditer(masked_text):
        yy1, yy2 = int(m.group(1)), int(m.group(2))
        _emit(_infer_yy_yy_century(yy1, yy2), m.start(), m.end())
        _mask(m.start(), m.end())
    masked_text = "".join(masked)

    for m in _YYYY_PLUS_RE.finditer(masked_text):
        y1 = int(m.group(1))
        _emit(_validate_year_range(y1, open_ended_hi), m.start(), m.end())
        _mask(m.start(), m.end())
    masked_text = "".join(masked)

    for m in _SINGLE_YEAR_RE.finditer(masked_text):
        y = int(m.group(1))
        _emit(_validate_year_range(y, y), m.start(), m.end())

    return out


class FitmentCandidate:
    """A (make, model, year_range) pair extracted from a product title.

    `year_range` is None when no year token sat near enough to the phrase to pair with
    it confidently. Equality and hashing are defined so candidates de-duplicate.
    """

    __slots__ = ("make", "model", "year_range")

    def __init__(self, make: str, model: str, year_range: Optional[tuple[int, int]]) -> None:
        """Store the make, model and optional year range."""
        self.make: str = make
        self.model: str = model
        self.year_range: Optional[tuple[int, int]] = year_range

    def __repr__(self) -> str:
        """A readable form showing all three fields."""
        return f"FitmentCandidate(make={self.make!r}, model={self.model!r}, year_range={self.year_range!r})"

    def __eq__(self, other: object) -> bool:
        """Compare all three fields, so candidates de-duplicate by value."""
        if not isinstance(other, FitmentCandidate):
            return NotImplemented
        return self.make == other.make and self.model == other.model and self.year_range == other.year_range

    def __hash__(self) -> int:
        """Hash all three fields, keeping equal candidates interchangeable in a set."""
        return hash((self.make, self.model, self.year_range))


_FITMENT_PAIR_DISTANCE: int = 50


def extract_fitment_candidates(
    title: Optional[str],
    *,
    trusted_makes: Optional[set[str]] = None,
) -> list[FitmentCandidate]:
    """Extract (make, model, year_range) candidates from a product title.

    Each matched phrase is paired with the nearest year range within
    `_FITMENT_PAIR_DISTANCE` characters, or with None when none is close enough.
    """
    if not title:
        return []
    title_lower = title.lower()

    year_spans = _extract_year_ranges_with_spans(title)

    candidates: list[FitmentCandidate] = []
    seen_keys: set[tuple[str, str, Optional[tuple[int, int]]]] = set()
    matched_spans: list[tuple[int, int]] = []

    def _try_match(phrases: list[tuple[str, str, str]]) -> None:
        """Match each phrase against the title and pair it with the nearest year range."""
        for phrase, make, model in phrases:
            if trusted_makes is not None and make not in trusted_makes:
                continue
            start = title_lower.find(phrase)
            if start == -1:
                continue
            end = start + len(phrase)
            if any(ms <= start < me or ms < end <= me for ms, me in matched_spans):
                continue
            matched_spans.append((start, end))

            paired_range: Optional[tuple[int, int]] = None
            best_dist = _FITMENT_PAIR_DISTANCE + 1
            for rng, ys, ye in year_spans:
                if ye <= start:
                    dist = start - ye
                elif ys >= end:
                    dist = ys - end
                else:
                    dist = 0
                if dist <= _FITMENT_PAIR_DISTANCE and dist < best_dist:
                    best_dist = dist
                    paired_range = rng

            key = (make, model, paired_range)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            candidates.append(FitmentCandidate(make, model, paired_range))

    _try_match(_FITMENT_PHRASES_WITH_MAKE)
    if trusted_makes is not None:
        _try_match(_FITMENT_PHRASES_MODEL_ONLY)

    candidates.sort(key=lambda c: title_lower.find(c.model.lower()))
    return candidates


def generations_for_make_model_year_range(
    make: str,
    model: str,
    year_range: tuple[int, int],
) -> list[tuple[str, str, str]]:
    """Triples whose production window overlaps `year_range`, read from the seed data.

    Database free, so adapters can call it at parse time. Use `9999` as the end year
    for an open-ended range; an unknown model or an impossible range returns empty.
    """
    y1, y2 = year_range
    if y1 > y2:
        return []
    models = CAR_GENERATIONS.get(make)
    if not models:
        return []
    out: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for model_data in models:
        if model_data["model"] != model:
            continue
        for gen in model_data["generations"]:
            gs = gen["start_year"]
            ge = gen["end_year"] if gen["end_year"] is not None else 9999
            if y1 <= ge and y2 >= gs:
                gen_name = gen["generation_name"]
                if gen_name not in seen:
                    seen.add(gen_name)
                    out.append((make, model, gen_name))
    return out


def narrow_triples_by_year_range(
    triples: list[tuple[str, str, str]],
    year_range: tuple[int, int],
) -> list[tuple[str, str, str]]:
    """Filter `triples` to those whose generation window overlaps `year_range`.

    Triples unknown to the seed data are dropped, since without a window there is no
    overlap to test. Use `9999` as the end year for an open-ended range.
    """
    y1, y2 = year_range
    if y1 > y2 or not triples:
        return []

    out: list[tuple[str, str, str]] = []
    for make, model, gen_name in triples:
        models = CAR_GENERATIONS.get(make)
        if not models:
            continue
        for model_data in models:
            if model_data["model"] != model:
                continue
            for gen in model_data["generations"]:
                if gen["generation_name"] != gen_name:
                    continue
                gs = gen["start_year"]
                ge = gen["end_year"] if gen["end_year"] is not None else 9999
                if y1 <= ge and y2 >= gs:
                    out.append((make, model, gen_name))
                break
            break
    return out


def _merge_year_ranges(
    ranges: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    """Merge overlapping or adjacent year ranges into disjoint spans, sorted by start.

    Ranges within one year of each other merge, so 2010-2014 and 2015-2018 read as one
    fitment block rather than two separate mentions.
    """
    if not ranges:
        return []
    ordered = sorted(ranges)
    merged: list[tuple[int, int]] = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end + 1:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def _maybe_narrow_by_combined_year_ranges(
    triples: list[tuple[str, str, str]],
    combined_text: str,
) -> list[tuple[str, str, str]]:
    """Narrow `triples` by the text's year ranges, but only when that is safe.

    Two or more disjoint spans mean a multi-fitment title, so narrowing is skipped;
    narrowing that would empty the result is discarded, the year being incidental.
    """
    ranges = extract_year_ranges(combined_text)
    if not ranges:
        return triples
    merged = _merge_year_ranges(ranges)
    if len(merged) != 1:
        return triples
    narrowed = narrow_triples_by_year_range(triples, merged[0])
    return narrowed if narrowed else triples


def _load_engine_platforms() -> dict:
    """Load the engine platform data and check every fitment against the seed data.

    An unknown (make, model, generation) would silently resolve to no cars at runtime,
    so this raises at import rather than letting the part fall through as universal.
    """
    import json as _json
    from importlib.resources import files as _files

    raw = _json.loads(_files("app.core").joinpath("engine_platforms_data.json").read_text(encoding="utf-8"))
    for engine_name, payload in raw.items():
        for fitment in payload.get("fitments", []):
            make = fitment["make"]
            model = fitment["model"]
            gen_name = fitment["gen_name"]
            models = CAR_GENERATIONS.get(make)
            if not models:
                raise RuntimeError(f"engine_platforms[{engine_name!r}] references unknown make {make!r}")
            model_entry = next((m for m in models if m["model"] == model), None)
            if model_entry is None:
                raise RuntimeError(
                    f"engine_platforms[{engine_name!r}] references unknown "
                    f"({make!r}, {model!r}) — model not in seed"
                )
            if not any(g["generation_name"] == gen_name for g in model_entry["generations"]):
                raise RuntimeError(
                    f"engine_platforms[{engine_name!r}] references unknown "
                    f"({make!r}, {model!r}, {gen_name!r}) — generation not in seed"
                )
    return raw


ENGINE_PLATFORMS: dict = _load_engine_platforms()

_ENGINE_PHRASE_INDEX: list[tuple[str, str]] = sorted(
    [
        (phrase.lower(), engine_name)
        for engine_name, payload in ENGINE_PLATFORMS.items()
        for phrase in payload.get("phrases", [])
    ],
    key=lambda x: -len(x[0]),
)


def infer_car_generations_via_engine(
    name: Optional[str],
    description: Optional[str] = None,
) -> list[tuple[str, str, str]]:
    """Triples for parts naming an engine platform but no make or model.

    Returns the union of each matched engine's fitment list, in the same shape as
    `infer_car_generations`, and is consulted only when that returns nothing.
    """
    if not name and not description:
        return []
    combined = re.sub(r"\s{2,}", " ", f"{name or ''} {description or ''}".lower()).strip()
    if not combined:
        return []
    matched_engines: set[str] = set()
    for phrase, engine_name in _ENGINE_PHRASE_INDEX:
        if phrase in combined:
            matched_engines.add(engine_name)
    if not matched_engines:
        return []
    seen: set[tuple[str, str, str]] = set()
    triples: list[tuple[str, str, str]] = []
    for engine_name in matched_engines:
        for fitment in ENGINE_PLATFORMS[engine_name].get("fitments", []):
            triple = (fitment["make"], fitment["model"], fitment["gen_name"])
            if triple in seen:
                continue
            seen.add(triple)
            triples.append(triple)
    return triples


def resolve_car_triples_to_ids(
    triples: list[tuple[str, str, str]],
) -> list[UUID]:
    """
    Resolve (car_make_name, car_model_name, generation_name) triples to car_generation IDs.

    Only returns IDs for car_generations that exist (CarMake + CarModel + CarGeneration with that generation_name).
    """
    if not triples:
        return []
    from app.api.dependencies.repositories import get_repositories

    repos = get_repositories()
    ids: list[UUID] = []
    seen_ids: set[UUID] = set()
    for car_make_name, car_model_name, gen_name in triples:
        car_make = repos.car_makes.get_by_name(car_make_name)
        if not car_make:
            continue
        car_model = repos.car_models.get_by_make_and_name(car_make.id, car_model_name)
        if not car_model:
            continue
        car_generation = next(
            (gen for gen in repos.car_generations.list_by_model(car_model.id) if gen.generation_name == gen_name),
            None,
        )
        if car_generation and car_generation.id not in seen_ids:
            seen_ids.add(car_generation.id)
            ids.append(car_generation.id)
    return ids
