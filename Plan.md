# Project Plan: Soil Moisture Trio

This document outlines the development plan for the `soil-moisture-trio` project.

## Sprint Goals
1.  **Ensure Correctness & Reliability:** Implement a testing framework to validate the pipeline's output.
2.  **Improve Maintainability:** Refactor the codebase for better organization and clarity.
3.  **Integrate Real-World Data:** Identify and integrate sources for NetCDF or Cloud-Optimized GeoTIFFs (COGs).
4.  **Visualize Results:** Create an interactive map to display the classification output and the reasoning behind it.

## Phase 1: Testing & Refactoring (Internal Plumbing)

- [x] **Add Basic Testing (`pytest`):**
    - [x] Introduce `pytest` for testing.
    - [x] Create a simple test case that runs the `DryWetClassifierPipeline` with synthetic data.
- [x] **Refactor the Codebase:**
    - [x] Restructure the project by splitting `main.py` into smaller, more focused modules (`config.py`, `model.py`, `pipeline.py`).
    - [x] Update `main.py` to be a simple script for orchestrating the pipeline.
    - [x] Update tests to use the new module structure.
- [x] **Optimize Model Training:**
    - [x] Replace the PyTorch MLP with CatBoost for faster tabular training/inference.
    - [x] Expose CatBoost hyperparameters through `ClassifierConfig`.
    - [x] Update dependencies (`pyproject.toml` / `requirements.txt`) accordingly.

## Phase 2: Data & Visualization (External-Facing)

- [ ] **Integrate Real-World Data:**
    - [x] **Soil Moisture:** Integrate BoM Australian Water Outlook (AWO) data (NetCDF).
    - [x] **Temperature:** Integrate SILO `tmax` data from AWS Public Data (NetCDF).
    - [x] **VPD:** Integrate SILO `vpd` data from AWS Public Data (NetCDF).
    - [ ] **NDVI:** Integrate CSIRO MODIS-derived data (COG). (Currently using synthetic data; direct access to COG proving difficult.)
    - [ ] **NDWI:** Removed at this stage.
    - [ ] **Fire Index:** Removed at this stage.
    - [x] Retire the synthetic-data code path so the pipeline exclusively consumes the real feeds (tests now mock `_load_all_real_data` for speed).

- [x] **Develop Visualization (`folium`):**
    - [x] Create a new script to generate an interactive HTML map using `folium`.
    - [x] Display the dry/wet classification as a grid overlay.
    - [x] Add a feature where clicking on a grid cell displays a popup with the input values.
    - [x] Make visualization optional via a CLI flag (`main.py --visualize`) so the core pipeline stays lean.

## Phase 3: Decision Support & Risk Layer

- [x] **Define Risk Rubric:**
    - [x] Translate per-cell dry/wet probabilities plus thresholds into categorical risk levels suitable for management decisions (implemented via `src/soil_moisture_trio/risk.py` + `pipeline.assess_risk`).
    - [x] Document how current moisture/temperature/VPD thresholds influence each risk band (captured in `ClassifierConfig` fields and agent context).
- [ ] **Aggregate Insights:**
    - [ ] Prototype scripts/notebooks to aggregate grid predictions into regional summaries (e.g., percentage dry, hotspot detection).
    - [ ] Explore incorporating recent trends (multi-year anomalies) or ancillary datasets to contextualize risk.
- [ ] **Output Formats:**
    - [x] Provide NetCDF + JSON exports of the risk layer via `--risk-output-prefix` to unblock downstream viz/scripting.
    - [x] Add `--risk-plot-path` CLI flag to emit a publication-ready PNG of the risk layer.
    - [ ] Decide on additional delivery mechanisms (GeoJSON, NetCDF layers, simple reports) that downstream tools can consume.
    - [ ] Update README once the risk layer workflow stabilizes.
