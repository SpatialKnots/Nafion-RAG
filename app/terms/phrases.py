"""Bounded full-name surface patterns; no acronym equivalence or source repair."""
from __future__ import annotations

METHOD_PATTERN = (
    r"(?:electrochemical\s+)?impedance\s+spectroscopy|differential\s+scanning\s+calorimetry|"
    r"(?:small|wide)[ -]angle\s+(?:x[ -]ray|neutron)\s+scattering|"
    r"(?:small|wide)[ -]angle\s+x[ -]ray\s+diffraction|x[ -]ray\s+diffraction|"
    r"(?:\d+\s*[a-z]+\s+)?nmr(?:\s+(?:spectroscopy|analysis))?|"
    r"(?:\d+\s*[a-z]+\s+)?nuclear\s+magnetic\s+resonance(?:\s+spectroscopy)?|"
    r"(?:raman|fourier\s+transform\s+infrared)\s+spectroscopy|"
    r"scanning\s+electron\s+microscopy|thermogravimetric\s+analysis|"
    r"interface\s+modeling|sans\s+modeling"
)
OBJECT_PATTERN = (
    r"(?:(?:li-)?nafion(?:-\d+)?\s+(?:(?:water|commercial|blend|recast|swollen|thin|polymer|composite)\s+){0,3}"
    r"(?:membranes?|films?|dispersions?|solutions?)|"
    r"(?:solution[ -]cast|dispersion[ -]cast|cast|recast|blend|swollen|polymer|composite)\s+"
    r"(?:nafion(?:-\d+)?\s+)?(?:membranes?|films?|electrodes?)|lithium[ -]ion\s+batter(?:y|ies)|"
    r"scanning\s+electron\s+microscope)"
)
COMPONENT_PATTERN = r"(?:(?:partially\s+)?fluorinated|organic|aprotic|carbonate|binary|ternary)\s+(?:solvents?|electrolytes?|mixtures?)"
FULL_PATTERNS = {"method": METHOD_PATTERN, "object_or_material": OBJECT_PATTERN, "component": COMPONENT_PATTERN}
VERSION = "tac_full_phrase_policy_v0.1"
