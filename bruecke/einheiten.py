"""Einheiten der Bausteinbeschreibung -> ISQ-Größe und SI-Einheit der SysML-v2-Standardbibliothek.

Nur was hier steht, wird als Größe mit Einheit übernommen. Alles andere wird umgewandelt: Zahlwert als Real, Einheit
im doc, und der Bericht sagt es. So wird eine neue Einheit eine neue Zeile, keine Codeänderung.
"""
EINHEITEN = {
    "N": ("ISQ::force", "SI::N"),
    "Nm": ("ISQ::torque", "SI::N*SI::m"),
    "mm": ("ISQ::length", "SI::mm"),
    "m": ("ISQ::length", "SI::m"),
    "s": ("ISQ::time", "SI::s"),
    "kg": ("ISQ::mass", "SI::kg"),
    "Hz": ("ISQ::frequency", "SI::Hz"),
    "V": ("ISQ::electricPotentialDifference", "SI::V"),
    "m/s": ("ISQ::speed", "SI::m/SI::s"),
}
