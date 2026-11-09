"""Finite source alternatives with exact raw bindings and conservative guards.

These patterns retain raw source spelling and require explicit local bindings.
They do not establish scientific ownership or normalize units.
"""

from app.generation.fact_types import NUMBER

VERSION = "source_paraphrases_v0.2"
COULOMBIC_VERSION = "natural_coulombic_source_v0.1"

COULOMBIC_CONCLUSION = (
    r"coulombic efficiency of the (?P<cell>Li\|\|[A-Z][A-Za-z0-9]*) half-cells maintain "
    rf"(?P<efficiency>{NUMBER})(?P<percent>%) (?P<qualifier>or so) after charging and discharging "
    rf"for (?P<cycles>\d+) (?P<cycle_unit>times) under (?P<current>{NUMBER}) (?P<current_unit>mA cm[−–-]2) "
    rf"current density and (?P<capacity>{NUMBER}) (?P<capacity_unit>mAh cm[−–-]2) lithium deposition amount per cycle"
)

GAS_SYNTHESIS = (
    r"(?P<sample>(?-i:Li)\s+foils)\s+were\s+treated\s+with\s+(?P<gas>(?-i:O2)\s+gas)\s+at\s+temperatures\s+"
    rf"(?:(?P<from>from)|between)\s+(?P<low>{NUMBER})\s+(?P<unit>°C)\s+(?(from)to|and)\s+"
    rf"(?P<high>{NUMBER})\s+°C\s+for\s+(?P<duration>(?P<hours>{NUMBER}))\s+(?P<d_unit>hours?)\."
)
EIS_MEDIUM = (
    rf"electrolyte\s+containing\s+(?P<concentration>{NUMBER})\s+(?P<unit>(?-i:M))\s+"
    r"(?P<salt>(?-i:LiPF6))\s+in\s+(?P<solvents>(?-i:EC/DEC))\s*"
    r"\((?P<ratio>(?P<left>\d+)/(?P<right>\d+))\s+(?P<basis>by\s+volume|volume\s+ratio)\)"
)
HOLD_OBSERVATION = (
    rf"An\s+isothermal\s+treatment\s+lasting\s+(?P<days>{NUMBER})\s+(?P<d_unit>days)\s+"
    rf"was\s+(?:performed|conducted)\s+at\s+(?P<temperature>{NUMBER})\s+(?P<t_unit>[°◦]C)\.\s*"
    r"This\s+treatment\s+did\s+not\s+change\s+the\s+measured\s+(?-i:W)\s+values\."
)

PATTERNS = {"gas_synthesis": GAS_SYNTHESIS, "eis_medium": EIS_MEDIUM, "hold_observation": HOLD_OBSERVATION}
# Conservative guard for NEW alternatives only. Legacy behavior stays frozen.
PREFIX_GUARD = (
    r"\b(?:no|not|never|will|would|could|may|might|hypothetic\w*|propos\w*|plan\w*|"
    r"assum\w*|imagine|future|intend\w*|hypothes\w*)\b|"
    r"\b(?:previous|prior)\s+(?:work|stud(?:y|ies))\b|\breported\s+that\b|"
    r"\baccording\s+to\s+(?:the\s+)?literature\b|"
    r"\b(?:another|other|different)\s+(?:sample|material|experiment)\b"
)
