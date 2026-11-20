# AquaSense AI: A Review-Gated IoT Platform for Prototype Water-Level Monitoring and Formula-Assisted Water-Quality Screening

**P. N. Santhosh Reddy, Pavan Kumar M. N., Pradeep G., Sandasani Karthik, and Jaysri**  
Department of Computer Science and Engineering (Artificial Intelligence and Machine Learning), Sai Vidya Institute of Technology, Bengaluru, Karnataka, India

## Abstract

Groundwater monitoring commonly separates water-level observations from water-quality records, making validation, review, and interpretation difficult for field operators. This paper presents AquaSense AI, a web-based prototype that combines an ESP32 ultrasonic water-level node, manual water-quality entry, review-controlled data management, map-based site selection, and transparent analytical summaries. Device and user observations are validated, stored with timestamps and site context, and held for review before they become eligible for official analytics and reports. The active water-quality workflow uses four parameters—pH, total dissolved solids, turbidity, and temperature—and applies a documented equal-weight screening formula. A tree-ensemble model is used only when its feature order, units, ranges, and artifact metadata satisfy the inference contract; otherwise, the formula result is retained. A separate five-parameter Random Forest experiment using pH, electrical conductivity, TDS, hardness, and chloride is reported as an offline comparative profile and is not part of the active four-parameter sensor workflow. The groundwater component provides a labelled short-horizon trend baseline from recent observations. It is not presented as a calibrated depletion forecast. The prototype demonstrates an integrated and auditable monitoring workflow, but the reported classification scores measure agreement with formula-generated labels rather than laboratory-confirmed potability or groundwater safety.

**Index Terms—** groundwater monitoring, ESP32, IoT, water-quality screening, human-in-the-loop validation, machine learning, trend baseline.

## I. Introduction

Groundwater supports domestic, agricultural, and industrial activity, but monitoring practices often treat quantity and quality as separate tasks. Water levels may be recorded by field instruments while chemistry is entered from manual or laboratory observations. These records can be difficult to associate with a station, location, timestamp, device, or review decision.

AquaSense AI addresses this integration problem through a prototype platform that combines serial ESP32 measurements, manual water-quality observations, station mapping, a relational backend, review workflows, and analytical summaries. The system is designed as a monitoring and screening aid. It does not certify water as potable, detect all contaminants, or establish regional groundwater depletion.

The main contributions are: (1) a review-gated architecture for device and manual observations; (2) an active four-parameter water-quality screening workflow with explicit units, limits, and inference validation; (3) a prototype serial bridge for near-real-time ESP32 distance readings; (4) a transparent seven-day trend baseline for demonstration-level water-level analysis; and (5) an explicit separation between deployed functionality and offline experimental model profiles.

## II. Related Background

Water-quality indices compress several measurements into an interpretable score. Classical index methods use guideline limits, parameter weights, and aggregation rules. Such methods are useful for screening, but their results depend on the selected limits, units, weights, and missing-value policy. Machine-learning models can approximate nonlinear relationships, but their evaluation is meaningful only when labels are independent and representative of the intended deployment population.

Groundwater-level forecasting additionally requires sufficiently long and reliable time series. A short sequence of readings from a prototype container or a single station cannot support claims about regional aquifer depletion. Therefore, AquaSense AI labels its short-horizon output as a trend baseline and reports the limitations of the available evidence.

## III. System Architecture

AquaSense AI consists of a React and TypeScript frontend, a FastAPI backend, SQLAlchemy data models, PostgreSQL in deployment, SQLite for local development, a serial bridge, model artifacts, and report-generation services. Leaflet is used for map interaction and OpenStreetMap-compatible geocoding services are used for location search and area identification.

The data path is:

1. A device packet or manual observation enters the ingestion interface.
2. Authentication, schema, range, timestamp, duplicate, and stale-data checks are applied.
3. The record is stored with source, timestamp, station, location, and validation metadata.
4. Device and user observations remain pending until an administrator reviews them.
5. Only approved records enter official dashboard analytics and reports.

Pending device readings may appear in a clearly labelled live operational panel. These readings are excluded from approved analytics, official reports, and model-training data until review.

### A. Prototype Hardware and Serial Path

The prototype node uses an ESP32, an ultrasonic distance sensor, and a 128×64 SSD1306 OLED. The firmware uses GPIO 5 for trigger, GPIO 18 for echo, I²C SDA on GPIO 21, I²C SCL on GPIO 22, and display address 0x3C. The electrical protection of the echo line must be verified for the actual hardware assembly; this paper does not assume safe voltage levels without that verification.

At startup, the firmware collects multiple distance samples and uses a median reference after rejecting invalid and excessively dispersed readings. Each cycle collects additional samples, rejects invalid values, and smooths the estimated height. The board sends newline-delimited JSON through USB serial at 115200 baud. The prototype firmware does not contain Wi-Fi code and does not measure pH, TDS, turbidity, or temperature.

A Python bridge detects supported USB serial adapters, reads the JSON stream, adds the UTC receipt timestamp, attaches the device key, and forwards packets to the backend. The bridge reconnects after USB removal and reinsertion. Because the ESP32 is connected by USB, the computer running the bridge must remain powered on and connected for live cloud updates.

### B. Review and Access Control

Passwords are stored as salted scrypt hashes. Authentication uses a server-side session cookie and a separate CSRF token for state-changing requests. Administrator routes are protected on the backend. User submissions and assigned device data are owner-scoped. Device readings remain pending until an administrator reviews them. Review decisions and correction requests are recorded in the audit trail.

## IV. Active Four-Parameter Water-Quality Screening

The active screening workflow accepts pH, TDS, turbidity, and temperature. The configuration stores each parameter's unit, precision, valid range, and standard reference limits. The frontend and backend use the same parameter order and validate the inference vector before model execution.

For TDS, turbidity, and temperature, the deviation score is:

\[
q_i = 100\frac{|v_i-v_{ideal,i}|}{s_i}
\]

For pH, the deviation is zero within the 6.5–8.5 band and increases outside that band. Each component is capped at 250. The project-defined score is the equal-weight mean:

\[
Q = \frac{q_{pH}+q_{TDS}+q_{turbidity}+q_{temperature}}{4}
\]

The screening classes are Excellent for Q ≤ 25, Good for Q ≤ 50, Poor for Q ≤ 75, Very Poor for Q ≤ 100, and Unsuitable for Q > 100. These classes are project-defined screening labels. They are not regulatory potability classes.

The application may use the trained four-parameter tree model when the artifact is available and its contract matches the configured features, order, units, and valid ranges. Otherwise, the deterministic formula remains the fallback. Model probabilities are not described as calibrated confidence.

The system explicitly states that four parameters cannot identify bacteriological contamination, nitrate, fluoride, hardness, heavy metals, pesticides, or every other health-relevant contaminant. Laboratory testing remains necessary for health-critical decisions.

## V. Offline Five-Parameter Comparative Profile

An independent offline experiment used pH, EC, TDS, total hardness, and chloride from Central Ground Water Board chemistry records. This profile is not used by the active four-parameter sensor workflow because the prototype does not measure all five variables.

The offline profile is included to document model experimentation and feature-contract separation. Its labels are also generated by a project-defined formula. Consequently, its accuracy and macro-F1 measure agreement with that formula rather than laboratory-confirmed safety. Samples with missing required features were excluded according to the experiment's preprocessing script. The exact dataset years, access date, preprocessing script, and artifact checksum must accompany any reproducibility package.

## VI. Model Evaluation Protocol

The four-parameter development experiment compared logistic regression, Random Forest, Extra Trees, and XGBoost using stratified five-fold cross-validation and out-of-fold predictions. Macro-F1 was used as the primary selection metric so that minority classes were not hidden by weighted averages. The development table contained 300 complete records, with class imbalance in the two rare classes.

The reported scores are development results only. Because the labels are formula-generated and the records are not independently laboratory-labelled, they must not be interpreted as potability accuracy. Random cross-validation can also produce optimistic estimates when records from the same station or time period are distributed across training and validation folds. Future evaluation must use station-separated and time-separated test sets.

## VII. Groundwater-Level Trend Baseline

The prototype water-level path is based on ultrasonic distance and a startup reference. Therefore, its percentage is relative to the calibrated reference and is not an absolute aquifer-storage measurement. The prototype has been demonstrated using a container or tank and has not been independently validated against a borewell instrument.

For a sequence of recent observations, the baseline computes a linear change per observation and projects it over a short horizon. The seven-day output is labelled a transparent trend projection. It is not a trained LSTM, TFT, or regional groundwater forecast. Depletion-risk thresholds are configurable alert boundaries applied to the monitored reference scale; they do not represent universal groundwater standards.

## VIII. Results and Software Verification

The application integrates device ingestion, manual submissions, map-based site selection, review queues, approval states, water-quality screening, live monitoring, history, reports, and administrative controls. Backend tests cover validation, model metadata, serial parsing, upload handling, rate limiting, session handling, access control, review operations, and account deletion. The frontend production build completes successfully.

The current evidence does not include a long-duration field trial, independent sensor comparison, laboratory-labelled water-quality test set, station-separated model evaluation, or validated regional depletion forecast. These are evidence gaps rather than failures to be hidden.

## IX. Limitations

1. The active four-parameter model is evaluated against formula-generated labels.
2. The five-parameter model is an offline comparative profile and is not compatible with the current four-parameter hardware path.
3. The development dataset is small and its provenance must be documented before publication.
4. Random cross-validation may overestimate performance on unseen stations and future periods.
5. The ESP32 prototype measures distance only; water-quality parameters are entered manually or supplied from external sources.
6. Startup calibration makes the level percentage relative to the initial reference.
7. The prototype has not been validated against an independent borewell water-level instrument.
8. The seven-day projection is a linear baseline and has no calibrated uncertainty.
9. Pending live readings are operationally visible but are excluded from official analytics until approval.
10. Email delivery, physical deployment, TLS configuration, and long-term backup operations depend on deployment configuration and provider availability.

## X. Conclusion and Future Work

AquaSense AI demonstrates an integrated, review-controlled workflow for prototype water-level monitoring and formula-assisted water-quality screening. Its strongest contribution is the combination of device ingestion, manual records, site context, validation, administrator review, and transparent evidence boundaries in one platform.

The current results do not establish laboratory-grade water-quality prediction or regional groundwater-depletion forecasting. Future work will collect paired sensor and laboratory observations, document dataset provenance, use station- and time-separated evaluation, compare against persistence and seasonal baselines, validate the ultrasonic node against an independent instrument, add compatible quality sensors, calibrate model probabilities, and conduct a multi-station field trial.

## References

[1] R. K. Horton, “An index number system for rating water quality,” *J. Water Pollution Control Federation*, vol. 37, no. 3, pp. 300–306, 1965.  
[2] R. M. Brown *et al.*, “A water quality index—do we dare?,” *Water & Sewage Works*, vol. 117, no. 10, pp. 339–343, 1970.  
[3] Bureau of Indian Standards, *Drinking Water—Specification*, IS 10500:2012, New Delhi, India.  
[4] World Health Organization, *Guidelines for Drinking-water Quality*, 4th ed., Geneva, Switzerland, 2022.  
[5] T. Chen and C. Guestrin, “XGBoost: A scalable tree boosting system,” in *Proc. KDD*, 2016, pp. 785–794.  
[6] L. Breiman, “Random forests,” *Machine Learning*, vol. 45, no. 1, pp. 5–32, 2001.  
[7] P. Geurts, D. Ernst, and L. Wehenkel, “Extremely randomized trees,” *Machine Learning*, vol. 63, no. 1, pp. 3–42, 2006.  
[8] F. Pedregosa *et al.*, “Scikit-learn: Machine learning in Python,” *JMLR*, vol. 12, pp. 2825–2830, 2011.  
[9] S. Hochreiter and J. Schmidhuber, “Long short-term memory,” *Neural Computation*, vol. 9, no. 8, pp. 1735–1780, 1997.
