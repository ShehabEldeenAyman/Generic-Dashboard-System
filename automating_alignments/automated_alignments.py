"""Normalize observation values between QUDT units."""

from __future__ import annotations

import argparse

from rdflib import Graph, Literal, Namespace, URIRef


QUDT = Namespace("http://qudt.org/schema/qudt/")
SOSA = Namespace("http://www.w3.org/ns/sosa/")

# Network-free definitions for common water-measurement units. Multipliers and
# offsets use the values published in QUDT's unit vocabulary and convert to the
# common reference unit for each dimensional family.
KNOWN_CONVERSIONS = {
    # Electrical conductivity (reference: S/m)
    URIRef("http://qudt.org/vocab/unit/MicroS-PER-CentiM"): (1e-4, 0.0),
    URIRef("http://qudt.org/vocab/unit/MilliS-PER-CentiM"): (1e-1, 0.0),
    URIRef("http://qudt.org/vocab/unit/S-PER-M"): (1.0, 0.0),
    URIRef("http://qudt.org/vocab/unit/MicroS-PER-M"): (1e-6, 0.0),
    URIRef("http://qudt.org/vocab/unit/MilliS-PER-M"): (1e-3, 0.0),
    # Mass concentration / density (reference: kg/m3)
    URIRef("http://qudt.org/vocab/unit/MicroGM-PER-L"): (1e-6, 0.0),
    URIRef("http://qudt.org/vocab/unit/MilliGM-PER-L"): (1e-3, 0.0),
    URIRef("http://qudt.org/vocab/unit/GM-PER-L"): (1.0, 0.0),
    URIRef("http://qudt.org/vocab/unit/GM-PER-M3"): (1e-3, 0.0),
    URIRef("http://qudt.org/vocab/unit/KiloGM-PER-M3"): (1.0, 0.0),
    # Dimensionless concentration and salinity scales
    URIRef("http://qudt.org/vocab/unit/PPB"): (1e-9, 0.0),
    URIRef("http://qudt.org/vocab/unit/PPM"): (1e-6, 0.0),
    URIRef("http://qudt.org/vocab/unit/PPTH"): (1e-3, 0.0),
    URIRef("http://qudt.org/vocab/unit/PERMILLE"): (1e-3, 0.0),
    URIRef("http://qudt.org/vocab/unit/PERCENT"): (1e-2, 0.0),
    # Water temperature (reference: kelvin)
    URIRef("http://qudt.org/vocab/unit/DEG_C"): (1.0, 273.15),
    URIRef("http://qudt.org/vocab/unit/K"): (1.0, 0.0),
}

CONVERSION_FAMILIES = {
    "electrical conductivity": frozenset(
        unit for unit in KNOWN_CONVERSIONS if "S-PER-" in str(unit)
    ),
    "mass concentration": frozenset(
        unit
        for unit in KNOWN_CONVERSIONS
        if any(token in str(unit) for token in ("GM-PER-L", "GM-PER-M3"))
    ),
    "dimensionless concentration": frozenset(
        URIRef(f"http://qudt.org/vocab/unit/{name}")
        for name in ("PPB", "PPM", "PPTH", "PERMILLE", "PERCENT")
    ),
    "temperature": frozenset(
        URIRef(f"http://qudt.org/vocab/unit/{name}") for name in ("DEG_C", "K")
    ),
}


def conversion_family(unit: URIRef) -> str | None:
    """Return the known dimensional family for a locally cached QUDT unit."""
    return next((name for name, units in CONVERSION_FAMILIES.items() if unit in units), None)


def convert_qudt_value(
    value: float,
    source_multiplier: float,
    source_offset: float,
    target_multiplier: float,
    target_offset: float,
) -> float:
    """Convert via the common SI reference represented by QUDT metadata."""
    if target_multiplier == 0:
        raise ValueError(
            "The target unit has a zero conversion multiplier and is not linearly convertible."
        )
    si_value = float(value) * source_multiplier + source_offset
    return (si_value - target_offset) / target_multiplier


def _conversion(unit: URIRef, cache: dict[URIRef, tuple[float, float]]):
    if unit in cache:
        return cache[unit]
    if unit in KNOWN_CONVERSIONS:
        cache[unit] = KNOWN_CONVERSIONS[unit]
        return cache[unit]

    unit_graph = Graph()
    unit_graph.parse(str(unit))
    multiplier = unit_graph.value(unit, QUDT.conversionMultiplier)
    offset = unit_graph.value(unit, QUDT.conversionOffset)
    if multiplier is None:
        raise ValueError(f"QUDT unit {unit} has no conversionMultiplier.")
    multiplier_value = float(multiplier)
    if multiplier_value == 0:
        raise ValueError(f"QUDT unit {unit} is not linearly convertible.")
    cache[unit] = (multiplier_value, float(offset) if offset is not None else 0.0)
    return cache[unit]


def transform_unit(graph_directory, NEW_UNIT):
    """Compatibility entry point using the corrected batch implementation."""
    return transform_unit_optimized(graph_directory, NEW_UNIT)


def transform_unit_optimized(graph_directory, NEW_UNIT):
    """Convert every SOSA observation to NEW_UNIT and serialize once.

    Previous code multiplied only by the source unit's SI multiplier. For
    µS/cm -> mS/cm that produced S/m values and then labelled them as mS/cm,
    making the stored number ten times too small. The corrected formula divides
    by the target unit's multiplier after converting through SI.
    """
    graph = Graph()
    target_unit = URIRef(NEW_UNIT)
    cache: dict[URIRef, tuple[float, float]] = {}

    try:
        graph.parse(graph_directory, format="turtle")
        print(f"Successfully loaded {len(graph)} triples.")
        target_multiplier, target_offset = _conversion(target_unit, cache)
        converted = 0

        for subject in set(graph.subjects(predicate=SOSA.hasSimpleResult)):
            source_unit = graph.value(subject, QUDT.hasUnit)
            if source_unit is None or source_unit == target_unit:
                continue
            source_unit = URIRef(source_unit)
            source_family = conversion_family(source_unit)
            target_family = conversion_family(target_unit)
            if source_family and target_family and source_family != target_family:
                raise ValueError(
                    f"Cannot convert {source_unit} ({source_family}) to "
                    f"{target_unit} ({target_family})."
                )
            source_multiplier, source_offset = _conversion(source_unit, cache)
            result = graph.value(subject, SOSA.hasSimpleResult)
            if result is None:
                continue
            new_value = convert_qudt_value(
                float(result),
                source_multiplier,
                source_offset,
                target_multiplier,
                target_offset,
            )
            graph.set((subject, SOSA.hasSimpleResult, Literal(new_value)))
            graph.set((subject, QUDT.hasUnit, target_unit))
            converted += 1

        if converted:
            graph.serialize(destination=graph_directory, format="turtle")
            message = f"Converted {converted} observations to {target_unit}."
        else:
            message = f"No transformations needed; observations already use {target_unit}."
        print(message)
        return message
    except Exception as error:
        raise RuntimeError(f"Could not normalize {graph_directory}: {error}") from error


def main():
    parser = argparse.ArgumentParser(
        description="Convert SOSA observation values to a QUDT unit."
    )
    parser.add_argument("input", help="Turtle file to update")
    parser.add_argument("target_unit", help="Target QUDT unit IRI")
    arguments = parser.parse_args()
    transform_unit_optimized(arguments.input, arguments.target_unit)


if __name__ == "__main__":
    main()
