# Soil-Property Stratification of AWRA-L Drought Output in Western Australian Agriculture: Evidence Review, SLGA Product Audit, and Minimal-Module Specification

*Research date: 12 August 2026. Product metadata verified on this date and may change; all versions/DOIs should be re-checked before build. SLGA layers are modelled digital-soil-mapping predictions with quantified uncertainty and must never be equated with observed field measurements.*

## DECISION BOX
- **Approved Release 1 properties:** SLGA **Available Water Capacity (AWC), Version 2** (DOI 10.25919/4jwj-na34) together with SLGA **Depth of Soil (DES), Version 2** (DOI 10.25919/djdn-5x77).
- **Exact reason selected:** AWC has the strongest direct mechanistic link to dryland-crop water storage in the WA wheatbelt. DES is required to cap the nominal 0–100 cm integration where mapped A- and B-horizon soil depth is shallower than 1 m. DES is not equivalent to effective crop rooting depth and does not represent chemical, physical, or crop-specific root constraints.
- **Recommended depths:** AWC at 0–5, 5–15, 15–30, 30–60, and 60–100 cm, capped by DES where mapped soil depth is shallower. Exclude 100–200 cm from the primary metric.
- **Recommended target-cell aggregation:** build one full-WA artifact on canonical AWRA-L cells derived from authoritative source coordinates, using area-weighted aggregation in Australian Albers (EPSG:3577). Operational runs select exact coordinate subsets; they do not re-harmonise SLGA. Report source coverage and mapped dispersion per full target-cell footprint.
- **Interpretive limit:** integrated AWC provides static modelled storage-capacity context. AWRA-L percentile rank plus AWC does **not** reveal current water storage in millimetres, distance from wilting, or crop-specific PAWC.
- **Stratification approach:** to be decided after the pilot and DPIRD soil-science review. If quantiles are used, they require a fixed declared reference domain and persisted cut points.
- **Confidence in recommendation:** High for an AWC-centred pilot; Moderate for DES-based profile capping; High for the operational/harmonisation design.
- **Largest unresolved scientific risk:** AWC and AWRA-L share SLGA/pedotransfer ancestry, so AWC strata are not statistically independent validation of AWRA-L. The 90 m → ~5 km change of support and national-map uncertainty also limit interpretation.

---

## 1. Executive recommendation
Stratify AWRA-L root-zone soil-moisture percentiles in WA agricultural landscapes using **SLGA AWC Version 2 together with SLGA Depth of Soil Version 2**. Convert the five nominal 0–100 cm AWC layers to a modelled storage-capacity metric in millimetres and cap layer thickness by mapped DES where the A- and B-horizon soil depth is shallower than 1 m. This provides static soil-capacity context for an AWRA-L anomaly; it does not convert percentile rank to current water storage or proximity to wilting. DES is a mapped soil-depth prediction, not effective crop rooting depth. Other candidates (texture fractions, bulk density, organic carbon, coarse fragments) act largely through AWC and should be deferred to avoid redundancy. Treat all SLGA layers as modelled predictions, retain lower/upper uncertainty scenarios, and never present them as field measurements or independent validation of AWRA-L.

## 2. Decision statement: recommended MVP properties
- **Release 1 primary metric:** DES-capped modelled 0–100 cm AWC storage capacity (mm) from SLGA AWC v2 (`AWC`, DOI 10.25919/4jwj-na34) and Depth of Soil v2 (`DES`, DOI 10.25919/djdn-5x77), with lower/upper uncertainty scenarios.
- **Required companion:** DES is used to cap nominal layer thickness and report mapped shallow-soil area. It must be labelled “Depth of Soil (A and B horizons),” not “effective rooting depth.”
- **Explicitly NOT in Release 1:** clay/sand/silt, bulk density, organic carbon, coarse fragments, salinity/sodicity/EC, hydraulic conductivity. These are deferred (Section 15).
- Soil properties are used ONLY as interpretive strata, never as new risk predictors, and the existing valid mask and risk thresholds are unchanged (scope control).

## 3. What soil properties contribute to drought interpretation
The soil-science and dryland-agronomy literature is consistent that in Mediterranean, winter-rainfall, terminal-drought environments such as the WA wheatbelt, crop water supply is dominated by the size of the soil "bucket" — plant-available water capacity (PAWC), the water held between the drained upper limit (DUL) and the crop lower limit / 15-bar lower limit (CLL/L15). Lawes, Oliver & Robertson (2009), drawing on the framework of Wong & Asseng (2006), state that "soil water supply to the crop is often closely related to the plant available soil water holding capacity (PAWC)" and that "PAWC will remain stable from year to year, and can therefore aid the interpretation of both spatial and temporal sources of yield variation" — a conclusion supported by monitoring at 17 wheatbelt sites with PAWCs of 43–131 mm over 1997–2005. GRDC-aligned PAWC guidance frames PAWC as "the size of the bucket, or how much soil water your paddock's soil can store and release," determined by DUL, CLL and bulk density, and notes it "can vary by a factor of 2 or 3."

Mechanistic roles of the candidate properties:
- **PAWC/AWC (DUL−L15):** direct measure of stored water available to roots; the master variable for drought buffering and the rate at which a moisture anomaly becomes plant stress. **Highest relevance.**
- **Mapped soil depth and effective rooting depth:** profile depth sets the vertical extent over which AWC can be integrated, while chemical, physical, and crop-specific constraints may further restrict roots. SLGA DES represents mapped A- and B-horizon depth, not effective rooting depth. **High relevance, but DES is an incomplete proxy.**
- **Texture (clay/sand/silt):** governs DUL and L15 shape; the dominant PTF predictor of AWC. Acts *through* AWC. **Mechanistically fundamental but largely redundant once AWC is used.**
- **Bulk density:** converts gravimetric to volumetric water and modulates porosity; a PTF input to AWC. **Redundant with AWC.**
- **Organic carbon:** modest positive effect on retention; a PTF input. WA cropping topsoils are typically low-SOC sands, so incremental effect is small. **Redundant/low.**
- **Coarse fragments (gravel):** reduce fine-earth volume and thus storage; important on WA ironstone-gravel soils, but the SLGA AWC/whole-earth framework partly accounts for this. **Low-moderate, mostly via AWC.**
- **Hydraulic conductivity / drainage:** govern infiltration, redistribution, waterlogging; relevant to duplex perched-water dynamics but hard to use as a simple stratifier and not released as a national SLGA hydraulic map in that form. **Contextual, deferred.**
- **Salinity/sodicity/subsoil constraints:** WA-specific yield limiters (subsoil alkalinity, sodicity, acidity, compaction) that reduce *effective* PAWC by restricting rooting. **Real but better treated as a separate constraint layer later, not folded into a storage metric.**

**Redundancy/causality conclusion:** texture, bulk density and organic carbon largely act on drought response through AWC, and the SLGA hydraulic products were built from clay, sand, silt, SOC, and bulk-density predictors. Including all of them alongside AWC would substantially repeat the same underlying signal. Mapped DES adds profile-truncation information not contained in layerwise AWC, while still falling short of effective crop rooting depth. The broad “up to ~90% variance explained” claim requires a precise primary citation before operational documentation uses it.

**Conceptual distinctions (kept explicit throughout):**
- **Drought state** = current wetness (the AWRA-L root-zone value).
- **Drought hazard** = how unusual that state is for the place and season (the percentile rank).
- **Soil-mediated vulnerability** = how soil storage capacity, mapped depth, rooting constraints, and management mediate plant response to a deficit.
- **Potential agricultural impact** = vulnerability combined with land use, crop, and management.
Soil stratification informs the third and fourth, NOT the first two.

## 4. Incremental value beyond the AWRA-L percentile rank
The AWRA-L root-zone product is "the modelled percentage of plant available water content in the top 1 m," and the drought products express this as a **location- and season-specific percentile/decile** (BoM ranks the current value against the same day-of-year over a historical reference period, e.g. 1911–2017 for the decile maps). Because the ranking is normalised per cell and per season, the **static spatial magnitude of storage capacity is deliberately removed**: a sandy cell holding ~50 mm and a loamy cell holding ~150 mm can both sit at the 10th percentile. Consequently:
- AWC supplies static modelled storage-capacity context that the percentile does not report. It can distinguish cells with different nominal soil “bucket sizes” despite equivalent percentile ranks.
- A percentile rank cannot be converted to current storage in millimetres, distance from wilting, or crop-specific extractable water using AWC alone; that would require a compatible absolute or relative AWRA-L storage state, or a validated cell-specific percentile-to-storage mapping.
- The incremental value is interpretive and must be framed as soil-capacity or vulnerability context, not a re-prediction of drought state or current plant-available water.

## 5. AWRA-L circularity / double-counting assessment
AWRA-L is parameterised with static maps of saturated hydraulic conductivity (Ksat) and **proportional available water holding capacity** (S0AWC, SsAWC, SdAWC) for its 0–10, 10–100 and 100–600 cm layers; these were updated per Vaze et al. (2018) in v6/v7, and in earlier versions were derived from ASRIS Level-4 information and from continental **clay-content mapping from the Soil and Landscape Grid of Australia** with the Dane & Puckett (1994) pedotransfer function for Ksat. Therefore:
- **Shared ancestry exists.** SLGA AWC and AWRA-L's internal AWC parameters both descend from SLGA texture/clay + PTFs. Stratifying the AWRA-L *dynamics* by SLGA AWC is therefore partially circular at the level of model parameters.
- **Percentile ranking removes static units, not all parameter influence.** Ranking each cell against its own seasonal history removes direct comparison of static capacity magnitude, but AWRA-L storage, drainage, and historical distributions remain influenced by mapped soil parameters. The degree of residual dependence has not been quantified.
- **Double-counting risk to avoid:** presenting “low percentile AND low AWC” as compounded independent drought evidence. The two are not independent measurements.
- **Expected model artefact to anticipate:** apparent relationships between AWC strata and AWRA-L behaviour are partly built in and must not be reported as external validation.
- **Defensible framing:** use AWC/DES to describe mapped soil-capacity context associated with an anomaly, not current water volume, distance from wilting, or whether the cell is in drought.

## 6. Evidence matrix
Scores: 3 = strong/high, 2 = moderate, 1 = weak/low. Evidence strength (H/M/L/U=unresolved) in brackets.

| Criterion | AWC (integrated mm) | Mapped soil depth (DES) | Texture (CLY/SND/SLT) | Bulk density (BDW) | Organic C (SOC) | Coarse fragments (CFG) | DUL−L15 (reconstructed) |
|---|---|---|---|---|---|---|---|
| Mechanistic relevance to drought | 3 [H] | 2 [H] | 3 [H] | 2 [M] | 1 [M] | 2 [M] | 3 [H] |
| Incremental value beyond percentile | 3 [H] | 2 [M] | 1 [M] | 1 [M] | 1 [M] | 1 [L] | 3 [H] |
| Relevance to SWAZ agriculture | 3 [H] | 3 [H] | 2 [H] | 1 [M] | 1 [M] | 2 [H] | 3 [H] |
| Decision-support interpretability | 3 [H] | 3 [H] | 2 [M] | 1 [L] | 2 [M] | 2 [M] | 2 [M] |
| Product maturity (SLGA) | 3 [H] (v2 2023) | 2 [M] (v2, single layer) | 3 [H] (v2) | 3 [H] (v2) | 3 [H] (v2) | 2 [M] | 2 [M] (inputs v1) |
| Spatial coverage | 3 [H] | 3 [H] | 3 [H] | 3 [H] | 3 [H] | 2 [M] | 3 [H] |
| Uncertainty availability | 3 [H] (5/95 CI) | 2 [M] | 3 [H] | 3 [H] | 3 [H] | 2 [M] | 2 [M] (covariance) |
| Defensibility of depth aggregation | 3 [H] | 3 [H] (n/a) | 2 [M] | 2 [M] | 2 [M] | 2 [M] | 3 [H] |
| Defensibility of aggregation to 5 km | 2 [M] | 2 [M] | 2 [M] | 2 [M] | 2 [M] | 2 [M] | 2 [M] |
| Redundancy w/ other candidates (3=least redundant) | 3 [H] | 3 [H] | 1 [H] | 1 [H] | 1 [H] | 2 [M] | 1 [H] (=AWC) |
| Operational/maintenance cost (3=lowest) | 3 [H] | 3 [H] | 2 [M] | 2 [M] | 2 [M] | 2 [M] | 1 [M] |
| **Indicative total** | **32** | **28** | **24** | **21** | **21** | **21** | **26** |

**Interpretation:** AWC is the clear leader; mapped DES is the best available profile-truncation complement but is not effective rooting depth. Texture/BD/SOC/CFG cluster lower mainly because they are redundant with AWC. The unweighted totals are only a transparent expert-screening aid, not a calibrated quantitative ranking. Reconstructed DUL−L15 reproduces AWC while mixing product lineages.

## 7. Current SLGA product inventory (verified 12 Aug 2026)
Source of truth: TERN Landscapes / CSIRO. SLGA products are 3 arc-second (~90 m) rasters, GlobalSoilMap-compliant, CC BY 4.0, delivered as Cloud-Optimised GeoTIFFs. Standard components per depth: **EV** (estimated value), **5** (5th-percentile lower confidence limit), **95** (95th-percentile upper confidence limit); an **EXT** extrapolation layer exists for some v2 products. Standard depths and codes: 000_005, 005_015, 015_030, 030_060, 060_100, 100_200. CRS: geographic lon/lat on GDA94/WGS84 datum (EPSG:4326; the WCS services historically expose EPSG:4283 GDA94). Continental extent per AWC v2 metadata: north −10.000416666, south −44.000416667, west 112.999583333, east 153.999583334.

Verified attribute codes and units (SLGA file-naming convention page): AWC (%), BDW/BDF (g/cm³), SOC (%), CLY/SLT/SND (%), CFG (%), DER Depth of Regolith (m), DES Depth of Soil (m), ECD (dS/m), CEC/ECE (meq/100g), PHW/PHC, NTO/PTO (%), DUL (%), L15 (%), SOF, AVP (mg/kg).

Drought-relevant products and status:
- **AWC — Available (Volumetric) Water Capacity, Version 2.** DOI **10.25919/4jwj-na34** (Searle, Somarathna & Malone 2023). Units **percent** (volumetric %); computed as DUL−L15 per layer with confidence limits from combined DUL/L15 variances; six depths + 5/95 CI; issued 2023-11-21, modified 2026-07-07; current. Metadata UUID 482301c2-b9a1-4345-b142-815f9b37890a.
- **DUL — Drained Upper Limit, Version 1.** DOI **10.25919/jnvd-3a26** (Searle & Somarathna 2022). Units percent; six depths + 5/95 CI; current (no v2 exists).
- **L15 — 15-Bar Lower Limit, Version 1.** DOI **10.25919/awp8-nv68** (Searle & Somarathna 2022). Units percent; six depths + 5/95 CI; current.
- **DES — Depth of Soil (A & B horizons), Version 2.** DOI **10.25919/djdn-5x77**; units metres; supersedes Release 1 (DOI 10.4225/08/546F540FE10AA); delivered as one 0–200 cm EV layer plus 5th/95th uncertainty layers; current. DES is mapped soil depth, not crop-specific effective rooting depth.
- **DER — Depth of Regolith, Release 2.** DOI 10.4225/08/55B835574E991 (Wilford et al. 2015). Units metres; cross-validation R²≈0.38 (weak). Depth to hard rock, not rooting depth.
- **CLY / SND / SLT — texture, Version 2**; **BDW — Bulk Density (Whole Earth), Release 2** (DOI 10.25919/gxyn-pd07); **SOC — Organic Carbon, Version 2**; **CFG — Coarse Fragments** (v2 suite). All six depths + 5/95 CI, CC BY 4.0.

**COG access:** base path `https://data.tern.org.au/model-derived/slga/NationalMaps/SoilAndLandscapeGrid/{ATTR}/{version}/`. Candidate exact identifiers and date tokens are listed in Section 8 and require authenticated live verification. **Authentication:** use the current TERN API-key method established by the live endpoint; never persist or log credentials.

**Fitness-for-purpose caveats:** SLGA is interpolated from sparse observations; CSIRO states that key functional properties such as PAWC are not accurate enough for farm-management decisions. A GRDC comparison on a northern NSW farm—not a WA validation—reported 7.8 percentage-point error and 4.9 percentage-point overprediction for 30–60 cm SLGA clay and found that SLGA missed within-paddock variability. WA coarse-fragment results provide separate evidence for that property only. Known concerns include edge artefacts, regional-model seams, and reduced accuracy at depth. AWC/DES require WA-focused review and must not be represented as paddock-scale truth.

## 8. Exact recommended product manifest

**AWC Version 2** — DOI 10.25919/4jwj-na34; units volumetric percent; date token `20210614`:

- EV: `AWC_000_005_EV_N_P_AU_TRN_N_20210614`, `AWC_005_015_EV_N_P_AU_TRN_N_20210614`, `AWC_015_030_EV_N_P_AU_TRN_N_20210614`, `AWC_030_060_EV_N_P_AU_TRN_N_20210614`, `AWC_060_100_EV_N_P_AU_TRN_N_20210614`.
- Lower: the same five identifiers with component token `05` in place of `EV`.
- Upper: the same five identifiers with component token `95` in place of `EV`.

**DES Version 2** — DOI 10.25919/djdn-5x77; units metres; date token `20190901`:

- `DES_000_200_EV_N_P_AU_TRN_C_20190901`
- `DES_000_200_05_N_P_AU_TRN_C_20190901`
- `DES_000_200_95_N_P_AU_TRN_C_20190901`

These identifiers and URLs were cross-checked against the clean `HEAD` metadata in the sibling SLGApy repository. An authenticated one-window live check must verify every pinned COG profile and URL before implementation acceptance; no runtime shorthand resolution or product substitution is allowed.

**Provenance to record for every layer:** full identifier, attribute code, product title, version, DOI, depth code, component, native resolution (3″), actual source CRS/datum, nodata, retrieval URL and timestamp, checksum, and CC BY 4.0 licence.

**Note on DUL−L15 alternative:** the official AWC v2 product *is* DUL−L15 with combined-variance CIs, so reconstructing it manually adds no expected-value information and would mix v1 DUL/L15 with the v2 AWC lineage. Recommendation: **use AWC v2 directly**; do not reconstruct. Flag as an unresolved provenance question whether AWC v2's inputs are the published DUL/L15 v1 products or an internal v2 hydraulic run.

## 9. Depth-integration recommendation
Convert per-layer volumetric AWC (%) to a millimetre storage total over 0–100 cm by **thickness-weighted summation**, never by averaging percentages:

`storage_mm(0–100) = Σ_i (AWC_i% / 100) × thickness_i`, with layer thicknesses 50, 100, 150, 300, 400 mm for the five layers (total 1000 mm).

- The result is **integrated plant-available water storage (mm)** — a physically meaningful "bucket size," directly comparable to APSoil PAWC figures and to AWRA-L's own 0–100 cm root-zone definition. For context, measured WA wheatbelt PAWC is generally in the 40–140 mm range (Lawes, Oliver & Robertson 2009; site range 43–131 mm), and national PAWC "can vary by a factor of 2 or 3."
- Do **not** simply sum or average the percent layers; a depth-weighted *mean* percent is only acceptable as a secondary descriptor, not as the storage metric.
- Cap integration at mapped DES where DES < 1 m, mirroring the official AWC “to soil depth or designated depth, whichever is shallowest” convention. This cap represents mapped A- and B-horizon depth, not effective crop rooting depth; chemical, physical, and crop-specific rooting constraints remain outside scope.
- Exclude 100–200 cm from the primary metric (outside the AWRA-L 0–100 cm root-zone signal); include it only as a separate, clearly-labelled deep-storage diagnostic if ever needed.
- Uncertainty: carry 05/95 layers through the same DES-capped thickness calculation as lower/upper scenarios. Do not claim a profile confidence level without joint bootstrap or covariance information.

## 10. Spatial harmonisation recommendation
- **Target grid:** the explicit builder derives a canonical full-WA target grid from authoritative AWRA-L latitude/longitude coordinates, validates monotonicity, spacing and cell-centre interpretation, and persists those coordinates. Do not hardcode the continental grid. Operational runs must match and subset the persisted coordinates exactly.
- **Aggregation:** area-weighted mean of the ~90 m SLGA pixels falling in each 0.05° cell. A 5 km cell contains ≈ (5000/90)² ≈ **3,000 pixels**, so the mean is well-supported where coverage is high.
- **Projection for area computation:** perform area weighting in an equal-area CRS — **Australian Albers, EPSG:3577** — rather than in geographic degrees, because 0.05° cells vary in ground area with latitude across WA; geographic-degree "areas" would bias weights.
- **Partial pixels:** weight edge pixels by their fractional overlap with the target cell (computed in EPSG:3577).
- **Resampling type:** AWC storage and depth are continuous → area-weighted mean (no nearest-neighbour, no categorical resampling). If a categorical "shallow-soil" flag is produced, aggregate it as an areal fraction, not a mode.
- **Source coverage:** compute valid mapped-soil area divided by the full AWRA-L target-cell area. Regional boundary polygons select cells at runtime and do not alter the static soil aggregation. Coastal or source-nodata cells therefore retain visibly lower coverage. Cells below the eventual reviewed threshold are unclassified for soil summaries; the threshold remains TBA.
- **Non-overlap / edge cells:** cells with zero valid soil pixels return nodata and are reported as uncovered, never interpolated.
- **Reproducibility:** fix the pixel-to-cell overlap computation and tolerances so results are deterministic; store a tolerance for floating-point area comparisons.
- **MAUP / change-of-support caveat:** aggregating 90 m model predictions to ~5 km is a change-of-support operation; the mean can misrepresent any paddock. Report mapped within-cell dispersion alongside the mean, clearly labelled as dispersion among model predictions rather than observed soil heterogeneity.

## 11. Confidence-interval and uncertainty treatment
- The **5** and **95** layers are the modelled **5th- and 95th-percentile confidence limits** of the digital-soil-mapping prediction (from 50 bootstrapped Cubist realisations), i.e. a ~90% prediction interval, NOT measurement error and NOT spatial-variability bounds.
- Legitimate uses: (a) compute an **uncertainty width** (95−5) per cell after identical depth-integration and spatial aggregation; (b) support **flagging** of high-uncertainty cells; (c) produce **group/stratum-level uncertainty summaries**; (d) **fitness-for-purpose reporting**.
- Do **not** invent numeric exclusion thresholds or "acceptable uncertainty" cut-offs; expose the width and let the soil scientist set any rule.
- Carry lower and upper layers through the same thickness and area operations as EV, but label the results **lower/upper uncertainty scenarios** and their difference an **uncertainty-width proxy**. Marginal depth-specific limits do not establish a formal integrated 90% interval without joint bootstrap realisations or covariance information.
- Always label outputs as **modelled predictions with uncertainty**, never as observed PAWC.

## 12. Proposed data contract
- **Scientific purpose:** provide a stable, uncertainty-aware soil "bucket size" (integrated 0–100 cm AWC storage, mm) on the AWRA-L 0.05° grid to interpret — not re-predict — root-zone soil-moisture percentiles for WA agricultural drought reporting.
- **Approved MVP properties:** AWC v2 plus DES v2. The primary metric is DES-capped modelled AWC storage capacity over a maximum nominal depth of 0–100 cm.
- **Exact product manifest:** as Section 8 (AWC v2 EV/05/95 × five depths; DES v2 EV/05/95 000_200).
- **Depth interpretation:** 0–100 cm root zone via five SLGA layers; 100–200 cm excluded from primary metric.
- **Units & transformations:** input AWC in volumetric percent and DES in metres; output modelled storage capacity in mm via DES-capped Σ(AWC%/100 × represented thickness).
- **Expected physical ranges:** per-layer AWC ~0–25% (volumetric); integrated 0–100 cm storage ~10–200 mm for WA agricultural soils (deep sands low tens of mm; loams/clays higher, with wheatbelt PAWC typically 40–140 mm per Lawes et al. 2009); DES 0–2 m. Values outside plausible ranges are flagged.
- **Source versioning policy:** pin exact DOI + version + COG date-stamp; AWC=v2, DES=v2, and record that DUL/L15 remain v1; no silent version upgrades.
- **Uncertainty products & use:** carry 05/95 through as lower/upper scenarios and an uncertainty-width proxy; do not label the integrated result a formal confidence interval or threshold it without review.
- **Spatial target grid:** persist a canonical full-WA AWRA-L grid derived from authoritative source coordinates; require exact coordinate matching when operational runs subset the artifact.
- **Source-to-target aggregation:** area-weighted mean in EPSG:3577; fractional edge pixels; continuous resampling.
- **Minimum source-coverage rule:** report valid mapped-soil area and coverage against full target-cell area. Boundary polygons do not redefine static soil values. The classification threshold remains TBA pending review.
- **Missing-data behaviour:** nodata preserved; uncovered cells returned as nodata + flagged; never interpolated.
- **Boundary interaction:** handle coast/edge and regional-model seams explicitly; do not fabricate values over non-soil.
- **Provenance requirements:** full product/version/DOI/depth/component/CRS/nodata/retrieval-time recorded per output.
- **Output metadata:** grid definition, CRS, transform, units, transformation formula, full-cell area, valid source area, coverage fraction, uncertainty scenarios, source manifest, and checksums.
- **Explicit non-goals:** not a soil taxonomy; not a new risk predictor; not a field-scale PAWC product; not a change to the valid mask or risk thresholds; no ML.
- **Acceptance criteria:** Section 13.
- **Unresolved questions for the soil scientist:** Section 17.

## 13. Proposed acceptance criteria
1. **Reconciliation:** classified soil strata plus an explicit `unclassified_insufficient_soil_coverage` group reconcile exactly to all valid-risk cells. Soil-classified totals alone are not expected to equal the full risk domain when coverage is insufficient.
2. **Uncovered-cell visibility:** every valid-risk cell with insufficient soil coverage is explicitly reported with valid source area, full target-cell area, and coverage fraction; it is never silently averaged or interpolated.
3. **Unit/range validation:** all outputs pass range checks (per-layer AWC %, integrated storage mm, depth m) with out-of-range values flagged.
4. **Full provenance:** each output carries product ID, version, DOI, depth codes, component, CRS, nodata, retrieval timestamp.
5. **Uncertainty reporting:** lower/upper storage scenarios and their width proxy are present for every soil-covered cell and are not mislabelled as a formal profile confidence interval.
6. **Deterministic spatial alignment:** canonical full-WA target coordinates, derived cell edges, full-cell footprints, and source overlaps are checked and reproducible; operational subsets must match persisted coordinates exactly.
7. **No silent product substitution:** a version/DOI mismatch against the pinned manifest fails the run.
8. **Risk outputs unchanged:** regression checks prove the numerical `risk_map`, `stress_index`, existing risk summary, and risk valid mask are unchanged. Whole output files need not be byte-identical when soil provenance metadata is added.

## 14. Proposed minimal-module specification (design only)
**(a) Approved product catalogue record/schema** — one immutable record per layer with fields: `full_product_id`, `property_code` (`AWC` or `DES`), `title`, `depth_code`, `units`, `component` (EV/05/95), `version`, `current_status`, `native_resolution` (3″), expected source CRS/datum, `cog_url`, citation, DOI, licence (CC BY 4.0), review bounds, nodata, checksum, and uncertainty relationship. Full IDs—not property codes—are the catalogue keys.

**(b) COG retrieval adapter responsibilities** — spatial-window reads (read only the pixels overlapping the WA bounding box / target cell, exploiting COG internal tiling); read `TERN_API_KEY` from the environment and send it as an HTTP header, never persisting or logging the credential; bounded retries with backoff and explicit failure surfacing (no silent empty reads); cache keyed on product_id+version+depth+component+window+CRS, invalidated on version/DOI change; validate CRS/profile/nodata of each fetched COG against the catalogue record; preserve nodata; capture provenance (URL, timestamp, checksum).

**(c) Harmonisation layer** — in an explicit build step, derive canonical full-WA AWRA-L cells from authoritative coordinates; reproject/compute overlaps in EPSG:3577; apply DES-capped depth integration; area-weight predictions with fractional overlaps; retain valid source area, full-cell denominator area, coverage, and mapped dispersion; return nodata+flag for non-overlap; document tolerances.

**(d) Artifact/return contract** — a versioned full-WA NetCDF containing aligned AWC/DES-derived values; lower/upper scenarios and width proxy; valid source area, full-cell area, coverage, and mapped dispersion; canonical coordinates; a separate soil valid mask; and complete provenance. The runtime loader returns exact coordinate subsets and fails on mismatch. The existing risk valid mask is never changed by this object.

**(e) Deterministic unit tests** — nodata handling; partial coverage; non-overlap; CRS mismatch; transform/grid mismatch; unexpected units/ranges; malformed metadata; missing authentication; cache separation by version; source-version change triggers cache invalidation; aggregation edge cases (single-pixel, all-nodata, straddling coast); proof existing risk outputs unchanged; plus **one** opt-in live integration test hitting a single small AWC v2 window.

**Dependencies:** declare **Rasterio** (COG windowed reads, CRS/profile/nodata) and a geometry/area library (e.g. Shapely + pyproj for EPSG:3577 overlap) as **direct** dependencies. NumPy is a direct dependency for array math. GDAL is present transitively via Rasterio and should not be declared directly unless called directly. Do not add or change any other project dependencies (scope control).

## 15. Products considered but deferred/rejected
- **Clay/Sand/Silt (CLY/SND/SLT v2):** rejected for Release 1 — dominant PTF inputs to AWC; including them double-counts. Useful later for explaining *why* a stratum has low storage (duplex sand-over-clay).
- **Bulk Density (BDW v2):** rejected — PTF input to AWC; little independent drought signal at this scale.
- **Organic Carbon (SOC v2):** rejected — small retention effect, low in WA cropping sands; PTF input.
- **Coarse Fragments (CFG):** deferred — matters on WA ironstone-gravel soils but largely captured via AWC/whole-earth; moderate mapping accuracy (overall 0.74–0.92, Holmes et al. 2021).
- **DUL and L15 (v1):** deferred as separate products — their difference *is* AWC v2; keeping them separate mixes versions.
- **Depth of Regolith (DER):** rejected as rooting-depth proxy — it is depth to hard rock (regolith), weak cross-validation (R²≈0.38), not effective soil/rooting depth.
- **EC/salinity/sodicity, Ksat:** deferred — real WA constraints (subsoil sodicity/alkalinity/acidity/compaction restrict effective PAWC) but better handled as a distinct constraint layer, not folded into a storage metric, and not released as a single national hydraulic stratifier in the required form.
- **100–200 cm AWC layer:** excluded from primary metric — outside AWRA-L 0–100 cm root-zone signal.

## 16. Scientific and operational risks
- **Shared-ancestry circularity** (Section 5): mitigate by framing AWC as impact/vulnerability context, not as an independent driver of the state, and by never presenting AWC–AWRA-L concordance as validation.
- **Change-of-support / MAUP:** 90 m → ~5 km hides fine-scale variation; report mapped within-cell dispersion and coverage without calling them observed heterogeneity.
- **Ecological inference / pseudo-replication / spatial autocorrelation:** avoid drawing paddock-level conclusions from 5 km cell means; treat neighbouring cells as spatially autocorrelated (not independent) in any downstream summary; do not count ~3,000 correlated pixels as independent samples.
- **Modelled ≠ measured:** SLGA is interpolated with acknowledged low functional-property accuracy in WA (CSIRO); never equate with field PAWC.
- **Regional-model seams / coastal artefacts:** flag cells near seams/coast.
- **Version drift:** AWC and DES identifiers/DOIs are pinned provisionally; live-verify profiles and fail on any substitution or version change.
- **Fixed-band overreach:** presenting quantile strata or agronomic PAWC bands as calibrated yield thresholds would overstate precision.

## 17. Unresolved decisions requiring DPIRD soil-science input
1. Minimum source-coverage fraction below which a cell is unclassified for soil summaries.
2. Exact analysis-footprint denominator at polygon and coastal edges.
3. Whether stratification uses fixed-reference regional quantiles or agronomically anchored bands; if quantiles are used, select and persist the reference domain and cut points. **TBA / backlog.**
4. Whether lower/upper uncertainty scenarios are sufficient for Release 1 or joint bootstrap/covariance information can support stronger propagation.
5. How DES uncertainty should affect profile capping and coverage flags.
6. Whether AWC v2 was computed from the published DUL/L15 v1 products or an internal hydraulic run.
7. Acceptable uncertainty-width reporting categories, if any.
8. External review of terminology, AWC/DES interpretation, and fitness for WA use by Karen Holmes and Dennis van Gool. **TBA.**

## 18. Recommended next implementation steps
1. **Live-verify the manifest:** use one authenticated test window to verify pinned AWC and DES URLs, profiles, units, CRS, nodata, and date tokens against TERN/CSIRO.
2. **Prototype AWC + DES:** fetch EV/05/95 for a WA test window; compute DES-capped modelled 0–100 cm AWC storage capacity and lower/upper scenarios.
3. **Build harmonisation:** derive the canonical full-WA target grid from authoritative AWRA-L coordinates; area-weight in EPSG:3577; produce valid source area, full-cell area, coverage, and mapped dispersion; require exact coordinate subsets at runtime.
4. **Persist static derived layers:** write a versioned compressed NetCDF under `data/processed/slga_awral/` plus a tracked manifest/build specification. Operational runs read this immutable derived artifact and do not refetch or recompute SLGA unless an explicit build command is run.
5. **Reconciliation + regression tests:** prove soil strata plus uncovered cells reconcile to the valid-risk domain and numerical risk outputs/valid mask remain unchanged.
6. **Soil-scientist review:** Karen Holmes and Dennis van Gool to review terminology, AWC/DES interpretation, coverage treatment, uncertainty scenarios, and eventual banding.
7. **Document fitness-for-purpose:** ship WA accuracy caveats, shared ancestry, change-of-support limitations, and uncertainty labels with the product.

**Benchmarks that would change the recommendation:** if DPIRD field/APSoil data show SLGA AWC has unacceptable bias for the SWAZ at 5 km, demote AWC to "context only" and prioritise a WA-regional PAWC layer; if effective-depth mapping proves materially independent and accurate, promote it to co-primary; if a future SLGA v3 hydraulic suite supersedes AWC v2, re-pin.

## 19. Claim-to-source evidence table
| # | Claim | Source |
|---|---|---|
| 1 | AWRA-L runs on a 0.05° (~5 km) grid; root-zone SM = % plant-available water in top 1 m | BoM Australian Water Outlook / AWRA-L; BoM drought pages |
| 2 | AWRA-L grid = 681×841, −10→−44 lat, 112→154 lon, cell-centre | AWRA-L root-zone netCDF (Zenodo 10689080) |
| 3 | AWRA-L parameterised with Ksat and proportional AWC for 0–10/10–100/100–600 cm, updated per Vaze et al. 2018 | AWRA-L v6/v7 Model Description Reports (BoM) |
| 4 | Earlier AWRA-L AWC/Ksat derived from ASRIS Level-4 + SLGA clay mapping + Dane & Puckett (1994) PTF | AWRA-L v5 (Frost) Model Description Report |
| 5 | BoM ranks soil moisture against historical reference (e.g. 1911–2017 deciles) | BoM drought / rainfall-deficiency pages |
| 6 | WA wheatbelt crop water supply closely related to PAWC; PAWC stable year-to-year; sites 43–131 mm | Lawes, Oliver & Robertson 2009 (framework of Wong & Asseng 2006), ScienceDirect S037842900900152X |
| 7 | PAWC = "size of the soil bucket"; varies by factor 2–3; drives yield/drought resilience | GRDC Estimating Plant Available Water Capacity |
| 8 | Duplex sand-over-clay: available water depends on surface texture, depth to subsoil, subsoil texture; repellence & waterlogging | soilquality.org.au Water Availability fact sheet |
| 9 | WA constraints — water repellence, surface salinity, subsoil alkalinity, low water storage, topsoil acidity, rooting depth "each restrict yield over at least 1 million hectares"; subsurface acidity ~12.6 Mha (~70%), subsurface compaction susceptibility ~13.2 Mha (~73%) | van Gool 2016, DPIRD RMTR 399 |
| 10 | "about 75% of arable land is affected by, or susceptible to, subsoil compaction... and around 50% is affected by subsoil acidity" | Geoderma 2026 (S0016706126000285), citing van Gool 2016 |
| 11 | Texture + BD + OC explain up to ~90% of wilting-point/field-capacity variance (PTF redundancy) | PTF literature (SLU/Sweden; France; NZ vis-NIR) |
| 12 | SLGA DUL/L15/AWC built by MLR pedotransfer functions from clay, sand, silt, SOC, BD | SLGA Soil Hydraulic Properties methods (aussoilsdsm.esoil.io) |
| 13 | AWC v2 = DUL−L15 per layer; CIs from combined DUL/L15 variances; summed to mm to soil depth | AWC v2 metadata (researchdata.edu.au); esoil.io hydraulic properties |
| 14 | AWC v2 DOI 10.25919/4jwj-na34, units percent, 6 depths, COG, CC BY 4.0, current | TERN/researchdata.edu.au AWC v2 record |
| 15 | DUL v1 DOI 10.25919/jnvd-3a26; L15 v1 DOI 10.25919/awp8-nv68 (current, no v2) | TERN portal; CSIRO DAP |
| 16 | DES v2 units metres, single 0–200 layer, supersedes Release 1 (10.4225/08/546F540FE10AA) | data.gov.au / esoil.io COG store |
| 17 | SLGA codes/units and file-naming (EV/5/95/EXT; depth codes) | SLGA GSM File Naming Conventions (esoil.io) |
| 18 | COG base path model-derived/slga/...; API key via header | esoil.io SLGA COG DataStore |
| 19 | CSIRO: SLGA functional-property (PAWC) accuracy "not accurate enough at scales needed for farm management decisions" | CSIRO Soil inverse modelling / Digiscape pages |
| 20 | SLGA clay 30–60 cm accuracy 7.8%, +4.9% bias vs on-farm; v2 ~90% within 90% envelope | GRDC constraint-mapping update; Malone et al. 2025 (Geoderma) |
| 21 | WA coarse-fragment DSM "overall accuracies 0.74 to 0.92 and AUC 0.79 to 0.89" | Holmes, Griffin & van Gool 2021 (Geoderma) |
| 22 | Aggregating 90 m→5 km is change-of-support/MAUP; results depend on scale/zoning | MAUP/COSP literature (Nature Index; Geoderma S0016706122000301) |
| 23 | APSoil PAWC classes illustrative (e.g. 57/90/135 mm) | Crop & Pasture Science CP21745 |
| 24 | SLGA v2 = 24 products; updated 11 + new suites incl. hydraulic; CC BY | Malone et al. 2025 (Geoderma); esoil.io |

## 20. Full bibliography (URLs/DOIs; accessed 12 Aug 2026)
- Searle R, Somarathna PDSN, Malone B (2023) SLGA Available Volumetric Water Capacity (Percent) v2. DOI 10.25919/4jwj-na34. https://researchdata.edu.au/soil-landscape-grid-version-2/2831553
- Searle R, Somarathna PDSN (2022) SLGA Drained Upper Limit v1. DOI 10.25919/jnvd-3a26. https://portal.tern.org.au/metadata/de9ddc12-b8e4-4ff2-99c4-390227a848aa
- Searle R, Somarathna PDSN (2022) SLGA 15-Bar Lower Limit v1. DOI 10.25919/awp8-nv68. https://data.csiro.au/dap/ws/v2/collections/63387
- Malone B (2023) SLGA Depth of Soil v2. DOI 10.25919/djdn-5x77 (supersedes 10.4225/08/546F540FE10AA). https://doi.org/10.25919/djdn-5x77
- Wilford J, Searle R, Thomas M, Grundy M (2015) SLGA Depth of Regolith Release 2. DOI 10.4225/08/55B835574E991. https://portal.tern.org.au/metadata/b078fbe6-daac-4b16-a733-103d758f4554
- SLGA GSM File Naming Conventions. https://esoil.io/TERNLandscapes/Public/Pages/SLGA/MetaData/ASLG_File_Naming_Conventions.html
- SLGA COG DataStore (API key). https://esoil.io/TERNLandscapes/Public/Pages/SLGA/GetData-COGSDataStore.html
- Soil Hydraulic Properties methods (Searle, Somarathna, Malone). https://aussoilsdsm.esoil.io/slga-version-2-products/soil-hydraulic-properties
- Malone BP et al. (2025) Update and expansion of the Soil and Landscape Grid of Australia. Geoderma 455:117226. https://www.sciencedirect.com/science/article/pii/S0016706125000643
- Grundy MJ et al. (2015) Soil and Landscape Grid of Australia. Soil Research. https://www.researchgate.net/publication/282817606
- AWRA-L v7 Model Description Report (BoM). https://awo.bom.gov.au/assets/notes/publications/AWRA-Lv7_Model_Description_Report.pdf
- AWRA-L v6 Model Description Report (BoM). https://awo.bom.gov.au/assets/notes/publications/AWRALv6_Model_Description_Report.pdf
- Frost AJ et al. AWRA-L v5 Model Description Report (BoM). https://awo.bom.gov.au/assets/notes/publications/Frost__Model_Description_Report.pdf
- AWRA-L root-zone soil moisture netCDF (Zenodo). https://zenodo.org/records/10689080
- BoM Drought – rainfall deficiencies & water availability. https://www.bom.gov.au/climate/drought/
- Lawes RA, Oliver YM, Robertson MJ (2009) Integrating climate and PAWC on wheat yield (framework of Wong & Asseng 2006). https://www.sciencedirect.com/science/article/abs/pii/S037842900900152X
- GRDC Estimating Plant Available Water Capacity. https://grdc.com.au/resources-and-publications/all-publications/publications/2013/05/grdc-booklet-plantavailablewater
- soilquality.org.au Water Availability fact sheet. https://www.soilquality.org.au/factsheets/water-availability
- van Gool D (2016) Identifying soil constraints that limit wheat yield in SW WA, DPIRD RMTR 399. https://library.dpird.wa.gov.au/rmtr/385/
- CSIRO Soil inverse modelling. https://www.csiro.au/en/research/natural-environment/land/soil/soil-inverse-modelling
- CSIRO Digiscape – Improving Australia's digital soil map. https://research.csiro.au/digiscape/digiscapes-projects/improving-australias-digital-soil-map/
- GRDC Constraint mapping and nowcasting of PAW (2025). https://grdc.com.au/resources-and-publications/grdc-update-papers/tab-content/grdc-update-papers/2025/02/constraint-mapping-and-nowcasting-of-plant-available-water-paw
- Holmes KW, Griffin EA, van Gool D (2021) DSM of coarse fragments in SW Australia. Geoderma. https://www.sciencedirect.com/science/article/abs/pii/S0016706121003621
- Deep amelioration of compaction and acidity (2026) Geoderma. https://www.sciencedirect.com/science/article/pii/S0016706126000285
- Crop & Pasture Science CP21745 – Water use efficiency in WA cropping. https://www.publish.csiro.au/cp/CP21745
- Optimal resolution of soil property maps / MAUP. https://www.sciencedirect.com/science/article/abs/pii/S0016706122000301
- SLGA GEE catalogue (band/unit reference). https://developers.google.com/earth-engine/datasets/catalog/CSIRO_SLGA

---
*Prepared as a scientific decision-support brief and corrected after project review. No code implemented; existing risk thresholds, weights and valid mask remain unchanged; soil properties are interpretive strata only, not new risk predictors. Exact COG availability and profiles still require authenticated live verification before build acceptance.*