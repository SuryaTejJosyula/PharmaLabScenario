"""Generate and validate a deterministic, entirely synthetic pharma QC dataset."""

import csv
import hashlib
import json
import random
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parent
SEED = 20261027
RNG = random.Random(SEED)
TABLES = {}
PRIMARY_KEYS = {}


def register(name, key, rows):
    TABLES[name] = rows
    PRIMARY_KEYS[name] = key


def ident(prefix, number):
    return f"{prefix}{number:06d}"


sites = [f"SITE{i:03d}" for i in range(1, 21)]
areas = ["Oncology", "Immunology", "Cardiometabolic", "Neuroscience", "AntiInfective"]
compounds = []
for i in range(1, 1001):
    compounds.append({
        "compound_id": ident("CMP", i),
        "compound_name": f"Synthetic Candidate {i:04d}",
        "therapeutic_area": areas[(i - 1) % len(areas)],
        "modality": "SmallMolecule",
        "dosage_form": "Tablet" if i % 2 else "Capsule",
        "nominal_strength_mg": RNG.choice([5, 10, 25, 50, 100, 200]),
        "development_stage": RNG.choice(["Phase1", "Phase2", "Phase3"]),
        "storage_condition": "ControlledRoomTemperature",
        "storage_temperature_min_c": 20,
        "storage_temperature_max_c": 25,
    })
register("compounds", "compound_id", compounds)

instruments = []
instrument_pools = {}
for site in sites:
    for technique in ["HPLC", "DissolutionUV"]:
        pool = []
        for _ in range(25):
            instrument = {
                "instrument_id": ident("INS", len(instruments) + 1),
                "instrument_name": f"{site}-{technique}-{len(pool) + 1:02d}",
                "lab_site_id": site,
                "technique": technique,
                "manufacturer": "Synthetic Lab Systems",
                "model": "QC-H100" if technique == "HPLC" else "QC-D200",
                "commissioned_date": "2024-01-01",
                "calibration_interval_days": 180,
            }
            instruments.append(instrument)
            pool.append(instrument["instrument_id"])
        instrument_pools[site, technique] = pool
register("instruments", "instrument_id", instruments)

test_specs = [
    ("Assay", "HPLC", "percent_label_claim", 95.0, 105.0, 100.0, 1.4),
    ("TotalImpurities", "HPLC", "percent_area", 0.0, 0.5, 0.18, 0.07),
    ("Dissolution30Min", "DissolutionUV", "percent_label_claim", 80.0, 100.0, 94.0, 2.0),
]
methods = []
for compound in compounds:
    for test, technique, unit, lower, upper, _, _ in test_specs:
        methods.append({
            "method_id": ident("MTH", len(methods) + 1),
            "compound_id": compound["compound_id"],
            "method_name": f"{compound['compound_id']}-{test}-v1",
            "method_version": 1,
            "test_type": test,
            "required_technique": technique,
            "result_unit": unit,
            "specification_lower": lower,
            "specification_upper": upper,
            "specification_rule": "InclusiveRange",
            "method_status": "Validated",
            "effective_date": "2024-12-01",
        })
register("assay_methods", "method_id", methods)

batches, samples, results, deviations = [], [], [], []
for compound_index, compound in enumerate(compounds):
    compound_methods = methods[compound_index * 3:compound_index * 3 + 3]
    for batch_number in range(3):
        batch_id = ident("BAT", len(batches) + 1)
        manufactured = date(2025, 1, 1) + timedelta(days=RNG.randrange(600))
        site = sites[(compound_index + batch_number) % len(sites)]
        batch = {
            "batch_id": batch_id,
            "compound_id": compound["compound_id"],
            "batch_number": f"SYN-{batch_id}",
            "lab_site_id": site,
            "manufactured_date": manufactured.isoformat(),
            "expiry_date": (manufactured + timedelta(days=730)).isoformat(),
            "batch_size_units": RNG.choice([10000, 25000, 50000, 100000]),
            "batch_purpose": "ClinicalSupply",
            "batch_status": "Released",
        }
        batches.append(batch)
        batch_deviations = []
        for sample_index, location in enumerate(["Beginning", "Middle", "End", "Composite"]):
            sample_id = ident("SMP", len(samples) + 1)
            collected = manufactured + timedelta(days=sample_index + 1)
            received = collected + timedelta(days=1)
            samples.append({
                "sample_id": sample_id,
                "batch_id": batch_id,
                "sample_type": "FinishedProduct",
                "sampling_location": location,
                "collected_date": collected.isoformat(),
                "received_date": received.isoformat(),
                "quantity_units": 120,
                "container_type": "AmberGlassBottle",
                "sample_status": "TestingComplete",
            })
            for method, spec in zip(compound_methods, test_specs):
                result_number = len(results) + 1
                result_id = ident("RES", result_number)
                failed = result_number % 19 == 0
                lower, upper, mean, stddev = spec[3:]
                if failed:
                    if method["test_type"] == "Assay":
                        value = RNG.uniform(90, 94.9) if result_number % 2 else RNG.uniform(105.1, 110)
                    elif method["test_type"] == "TotalImpurities":
                        value = RNG.uniform(0.55, 1.2)
                    else:
                        value = RNG.uniform(60, 79.9)
                else:
                    value = min(upper, max(lower, RNG.gauss(mean, stddev)))
                tested = received + timedelta(days=RNG.randint(1, 3))
                calibrated = tested - timedelta(days=RNG.randint(1, 120))
                results.append({
                    "result_id": result_id,
                    "sample_id": sample_id,
                    "method_id": method["method_id"],
                    "instrument_id": RNG.choice(instrument_pools[site, method["required_technique"]]),
                    "tested_date": tested.isoformat(),
                    "analyst_code": f"ANL-{site}-{RNG.randint(1, 15):02d}",
                    "measured_value": round(value, 3),
                    "result_unit": method["result_unit"],
                    "result_status": "Fail" if failed else "Pass",
                    "instrument_last_calibrated_date": calibrated.isoformat(),
                    "instrument_calibration_due_date": (calibrated + timedelta(days=180)).isoformat(),
                    "replicate_number": 1,
                })
                if failed:
                    deviation_number = len(deviations) + 1
                    is_open = deviation_number % 4 == 0
                    deviations.append({
                        "deviation_id": ident("DEV", deviation_number),
                        "result_id": result_id,
                        "deviation_type": "OutOfSpecification",
                        "severity": "Critical" if method["test_type"] == "TotalImpurities" else "Major",
                        "opened_date": tested.isoformat(),
                        "closed_date": "" if is_open else (tested + timedelta(days=RNG.randint(7, 28))).isoformat(),
                        "investigation_status": "InProgress" if is_open else "Closed",
                        "root_cause_category": "UnderInvestigation" if is_open else RNG.choice([
                            "ProcessVariability", "BlendNonuniformity", "MaterialVariability",
                        ]),
                        "corrective_action": "InvestigationPending" if is_open else "ManufacturingProcessReview",
                        "disposition": "Pending" if is_open else "BatchRejected",
                    })
                    batch_deviations.append(deviations[-1])
        if batch_deviations:
            batch["batch_status"] = (
                "OnHold" if any(d["investigation_status"] == "InProgress" for d in batch_deviations)
                else "Rejected"
            )
register("batches", "batch_id", batches)
register("samples", "sample_id", samples)
register("test_results", "result_id", results)
register("deviations", "deviation_id", deviations)

relationships = [
    ("batches", "compound_id", "compounds", "hasBatch", "one-to-many"),
    ("assay_methods", "compound_id", "compounds", "hasValidatedMethod", "one-to-many"),
    ("samples", "batch_id", "batches", "hasSample", "one-to-many"),
    ("test_results", "sample_id", "samples", "hasTestResult", "one-to-many"),
    ("test_results", "method_id", "assay_methods", "producesResult", "one-to-many"),
    ("test_results", "instrument_id", "instruments", "generatedResult", "one-to-many"),
    ("deviations", "result_id", "test_results", "hasDeviation", "one-to-zero-or-one"),
]

# Validate the persisted CSVs rather than only the generation objects.
for name, rows in TABLES.items():
    with (ROOT / f"{name}.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

loaded = {}
for name in TABLES:
    with (ROOT / f"{name}.csv").open(newline="", encoding="utf-8") as handle:
        loaded[name] = list(csv.DictReader(handle))


def require(condition, message):
    if not condition:
        raise ValueError(message)


indexes = {}
for name, rows in loaded.items():
    pk = PRIMARY_KEYS[name]
    require(len(rows) >= 1000, f"{name}: fewer than 1000 data rows")
    require(all(row[pk] for row in rows), f"{name}: missing primary key")
    indexes[name] = {row[pk]: row for row in rows}
    require(len(indexes[name]) == len(rows), f"{name}: duplicate primary key")
    require(all(None not in row and None not in row.values() for row in rows), f"{name}: malformed CSV")
    require(all(value != "" for row in rows for key, value in row.items()
                if not (name == "deviations" and key == "closed_date")), f"{name}: unexpected null")

for child, fk, parent, _, _ in relationships:
    require(all(row[fk] in indexes[parent] for row in loaded[child]), f"{child}.{fk}: orphan foreign key")
    require({row[fk] for row in loaded[child]} == set(indexes[parent]) or child == "deviations",
            f"{parent}: unused parent entities")

deviation_by_result = {row["result_id"]: row for row in loaded["deviations"]}
require(len(deviation_by_result) == len(loaded["deviations"]), "Multiple deviations for one result")
batch_deviations = {key: [] for key in indexes["batches"]}
for row in loaded["test_results"]:
    sample = indexes["samples"][row["sample_id"]]
    batch = indexes["batches"][sample["batch_id"]]
    method = indexes["assay_methods"][row["method_id"]]
    instrument = indexes["instruments"][row["instrument_id"]]
    require(method["compound_id"] == batch["compound_id"], "Method/compound mismatch")
    require(instrument["lab_site_id"] == batch["lab_site_id"], "Instrument/site mismatch")
    require(instrument["technique"] == method["required_technique"], "Instrument/technique mismatch")
    require(row["result_unit"] == method["result_unit"], "Result/unit mismatch")
    require(method["effective_date"] <= row["tested_date"], "Method not yet effective")
    require(instrument["commissioned_date"] <= row["instrument_last_calibrated_date"], "Calibration predates commissioning")
    require(batch["manufactured_date"] <= sample["collected_date"] <= sample["received_date"]
            <= row["tested_date"] < batch["expiry_date"], "Invalid sample chronology")
    require(row["instrument_last_calibrated_date"] <= row["tested_date"]
            <= row["instrument_calibration_due_date"], "Calibration invalid on test date")
    require((date.fromisoformat(row["instrument_calibration_due_date"])
             - date.fromisoformat(row["instrument_last_calibrated_date"])).days
            == int(instrument["calibration_interval_days"]), "Calibration interval mismatch")
    passed = float(method["specification_lower"]) <= float(row["measured_value"]) <= float(method["specification_upper"])
    require((row["result_status"] == "Pass") == passed, "Incorrect pass/fail")
    require((row["result_id"] in deviation_by_result) == (not passed), "Deviation/failure mismatch")
    if not passed:
        deviation = deviation_by_result[row["result_id"]]
        require(row["tested_date"] <= deviation["opened_date"], "Deviation precedes test")
        require((deviation["closed_date"] == "") == (deviation["investigation_status"] == "InProgress"),
                "Invalid deviation closure")
        require(not deviation["closed_date"] or deviation["opened_date"] <= deviation["closed_date"],
                "Closure precedes opening")
        require(not deviation["closed_date"] or deviation["closed_date"] <= "2026-10-27",
                "Closure after snapshot date")
        batch_deviations[batch["batch_id"]].append(deviation)

for batch_id, linked in batch_deviations.items():
    expected = "Released" if not linked else (
        "OnHold" if any(d["investigation_status"] == "InProgress" for d in linked) else "Rejected"
    )
    require(indexes["batches"][batch_id]["batch_status"] == expected, "Invalid batch disposition")
require(all(count == 3 for count in Counter(r["compound_id"] for r in loaded["batches"]).values()),
        "Expected three batches per compound")
require(all(count == 4 for count in Counter(r["batch_id"] for r in loaded["samples"]).values()),
        "Expected four samples per batch")
require(all(count == 3 for count in Counter(r["sample_id"] for r in loaded["test_results"]).values()),
        "Expected three tests per sample")
require(len({(r["sample_id"], r["method_id"]) for r in loaded["test_results"]})
        == len(loaded["test_results"]), "Duplicate sample/method tests")

descriptions = {
    "compounds": "Fictional small-molecule candidates, each modeled as one oral formulation.",
    "batches": "Clinical-supply manufacturing batches and their QC disposition.",
    "samples": "Finished-product samples at beginning, middle, end and composite locations.",
    "instruments": "Analytical instruments across a synthetic network of 20 laboratory sites.",
    "assay_methods": "Three compound-specific validated methods per candidate formulation.",
    "test_results": "One final quantitative result per sample and method; no retests.",
    "deviations": "One investigation per failed result; closed OOS investigations reject the batch.",
}


def data_type(column, value):
    if column.endswith("_date"):
        return "DATE"
    if isinstance(value, int):
        return "BIGINT"
    if isinstance(value, float):
        return "DECIMAL(12,3)"
    return "STRING"


model = {
    "dataset": "Synthetic pharmaceutical quality-control laboratory",
    "snapshot_date": "2026-10-27",
    "seed": SEED,
    "synthetic": True,
    "format": {"encoding": "UTF-8", "delimiter": ",", "header": True,
               "date_format": "yyyy-MM-dd", "null_representation": ""},
    "entities": [
        {
            "table": name, "file": f"{name}.csv", "primary_key": PRIMARY_KEYS[name],
            "row_count": len(rows), "description": descriptions[name],
            "columns": [
                {"name": column, "lakehouse_type": data_type(column, value),
                 "nullable": name == "deviations" and column == "closed_date"}
                for column, value in rows[0].items()
            ],
        }
        for name, rows in TABLES.items()
    ],
    "relationships": [
        {
            "from_entity": parent, "from_key": PRIMARY_KEYS[parent], "relationship": verb,
            "to_entity": child, "to_foreign_key": fk, "cardinality": cardinality,
            "required_child_reference": True,
        }
        for child, fk, parent, verb, cardinality in relationships
    ],
    "attributes_not_separate_entities": ["lab_site_id", "analyst_code"],
    "warning": "Demonstration only. Not medical advice, regulatory evidence, or real product specifications.",
}
(ROOT / "ontology_model.json").write_text(json.dumps(model, indent=2) + "\n", encoding="utf-8")

report = {
    "status": "PASS",
    "validated_from": "Persisted CSV files",
    "row_counts": {name: len(rows) for name, rows in loaded.items()},
    "total_data_rows": sum(len(rows) for rows in loaded.values()),
    "foreign_key_relationships_validated": len(relationships),
    "orphan_foreign_keys": 0,
    "duplicate_primary_keys": 0,
    "result_status_counts": dict(Counter(r["result_status"] for r in loaded["test_results"])),
    "batch_status_counts": dict(Counter(r["batch_status"] for r in loaded["batches"])),
    "checks": [
        "At least 1000 data rows in every CSV; unique non-null primary keys",
        "CSV row shape and required values; all seven foreign-key relationships",
        "Parent coverage; unique optional deviation per result",
        "Compound-specific methods; instrument technique and laboratory site alignment",
        "Result units and numeric specification-based pass/fail consistency",
        "Manufacturing, collection, receipt, test, expiry and investigation chronology",
        "Method effectiveness, commissioning and calibration validity on test date",
        "Every failed result has exactly one deviation; no passing result has a deviation",
        "Batch disposition reconciles to open/closed investigations",
        "Three batches per compound, four samples per batch, three distinct tests per sample",
    ],
    "sha256": {f"{name}.csv": hashlib.sha256((ROOT / f"{name}.csv").read_bytes()).hexdigest()
               for name in loaded},
}
(ROOT / "validation_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

readme = """PHARMA LAB QC - SYNTHETIC LAKEHOUSE DATA
=====================================
Entirely fictional demonstration data. No patient data, real drug identities,
real manufacturers or real analyst identities are included. Specifications
are illustrative, not pharmacopoeial limits or clinical/regulatory guidance.

CONTENTS (data rows, excluding the header)
"""
for name, rows in TABLES.items():
    readme += f"  {name}.csv: {len(rows):,}\n"
readme += """
MODEL
  Compounds --hasBatch--> Batches --hasSample--> Samples
  Compounds --hasValidatedMethod--> AssayMethods
  Samples --hasTestResult--> TestResults
  AssayMethods --producesResult--> TestResults
  Instruments --generatedResult--> TestResults
  TestResults --hasDeviation--> Deviations

All edges are one-to-many except TestResults to Deviations, which is optional
one-to-one. Each child has exactly one parent for each listed foreign key.
ontology_model.json contains exact join keys, column types, nullability,
entity descriptions and suggested ontology relationship names. It is a
descriptive mapping guide, not an importable Fabric ontology definition.

FABRIC LAKEHOUSE INGESTION
1. Upload only the seven CSV files to Files/pharma_lab_qc in your Lakehouse.
2. Load each CSV to a Delta table using its filename without the extension.
   Use header=true, delimiter=comma, UTF-8 encoding and yyyy-MM-dd dates.
3. Keep all identifiers as STRING; cast numeric/date columns using the types
   in ontology_model.json. An empty closed_date means NULL, not a default date.
4. Build ontology entities from the seven tables using their primary keys,
   then configure the relationships using ontology_model.json.
5. CSVs do not enforce primary/foreign keys; preserve the supplied keys when
   loading and transforming tables. None of the files has been uploaded.

SCENARIO AND ASSUMPTIONS
- Snapshot: 2026-10-27. Manufacturing starts 2025-01-01.
- 1,000 candidate formulations; three batches and three methods per compound.
- Four finished-product samples per batch; all samples have three final tests:
  assay, total impurities and dissolution at 30 minutes.
- Assay/impurity methods use HPLC; dissolution uses DissolutionUV instruments.
- 1,000 instruments represent a large 20-site network, not one physical lab.
- lab_site_id and analyst_code are descriptive attributes, not missing entity
  tables. Sites and analysts could be modeled as separate entities later.
- Synthetic numerical results include deliberately injected OOS outcomes
  (every nineteenth result) to enable investigations and quality analytics.
  This rate is a demo mechanism, NOT an industry failure-rate estimate.
- Specifications apply inclusively to the reported, rounded measured_value.
- Each failed result has one OOS deviation. Passing results have none.
- A batch with any open deviation is OnHold; with only closed deviations it
  is Rejected; with no deviations it is Released. No retest/invalidated-result,
  stability-timepoint, release-date or real GMP workflow is modeled.
- Calibration fields on results describe validity at test time; they are not
  a complete calibration event history. Instrument availability is not modeled.
- Units: percent_label_claim and percent_area are percent values (100 = 100%),
  strengths are mg, storage temperatures are Celsius, quantities are units.

EXAMPLE ONTOLOGY QUESTIONS
- Which compounds have rejected batches with critical impurity deviations?
- Which instruments produced failing assay results at a particular site?
- Which batches remain on hold because investigations are still open?
- Trace a deviation back through result, sample, batch and compound, and
  identify the method and instrument that generated the result.

VALIDATION AND REPRODUCIBILITY
validation_report.json records validation checks, actual row counts and CSV
SHA-256 hashes. Checks run against files read back from disk.
Run `python generate_data.py` to reproduce this fixed dataset with seed
20261027. This overwrites the generated CSVs, metadata, report and ZIP here.
The ZIP contains the seven CSVs, mapping, report, this guide and generator.
"""
(ROOT / "README.txt").write_text(readme, encoding="utf-8")

with ZipFile(ROOT / "pharma_lab_lakehouse.zip", "w", ZIP_DEFLATED) as archive:
    for name in [*(f"{table}.csv" for table in TABLES), "ontology_model.json",
                 "validation_report.json", "README.txt", "generate_data.py"]:
        archive.write(ROOT / name, arcname=name)

print(json.dumps(report, indent=2))
print(f"Created: {ROOT / 'pharma_lab_lakehouse.zip'}")
