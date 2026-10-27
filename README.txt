PHARMA LAB QC - SYNTHETIC LAKEHOUSE DATA
=====================================
Entirely fictional demonstration data. No patient data, real drug identities,
real manufacturers or real analyst identities are included. Specifications
are illustrative, not pharmacopoeial limits or clinical/regulatory guidance.

CONTENTS (data rows, excluding the header)
  compounds.csv: 1,000
  instruments.csv: 1,000
  assay_methods.csv: 3,000
  batches.csv: 3,000
  samples.csv: 12,000
  test_results.csv: 36,000
  deviations.csv: 1,894

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
