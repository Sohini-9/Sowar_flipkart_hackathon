# 🚦 Event-Driven Congestion Intelligence System (ED-CIS)

An end-to-end **traffic incident intelligence and congestion forecasting platform** built for **Flipkart GRiD / Bengaluru Traffic Hackathon – Theme 2**.

This project transforms historical traffic incident logs into **real-time operational decisions** using machine learning, congestion scoring, forecasting, and rule-based resource planning.

---

## 📌 Problem Statement

Traditional congestion forecasting requires:

- Vehicle speed
- Traffic density
- Queue lengths
- Travel time data
- Deployment records

However, the provided dataset contained only **traffic incident logs**.

This system bridges that gap by combining:

- Historical incident patterns
- Real traffic ETA calibration
- Machine learning
- Forecasting
- Explainable decision rules

to generate **live congestion intelligence**.

---

## 🎯 Objectives

- Predict traffic disruption severity
- Estimate road closure probability
- Forecast future incident volumes
- Recommend operational response:
  - Officer deployment
  - Barricade requirements
  - Diversion priority

---

# 🏗️ System Architecture

```text
M1 → M2 → M3
             ↓
      M4a → M4b → M4c
             ↓
            M5
             ↓
            M6
             ↓
            M7
```

---

# ⚙️ Pipeline Modules

## M1 — Data Ingestion
- Load raw incident dataset
- Parse timestamps
- Clean invalid records
- Generate helper fields

**Output**
```text
clean_incidents.csv
```

---

## M2 — Feature Engineering
- Corridor reconstruction
- Feature encoding
- Signal generation
- Police station lookup

**Models**
- Random Forest
- KNN Ensemble

**Output**
```text
feature_matrix.csv
cis_signal_tables.json
corridor_model.pkl
```

---

## M3 — Traffic Calibration (TGCF)

Integrates external traffic estimates.

### Traffic Growth Correction Factor

```text
TGCF = Vehicles(2023–24) / Vehicles(2026)
TGCF = 115 / 128
TGCF = 0.898
```

Uses:
- MapMyIndia / Mappls APIs
- Distance Matrix
- ETA Calibration
- Response caching

**Output**
```text
eta_baselines.json
```

---

## M4a — Road Closure Prediction

Predicts probability of road closure.

### Models
- Extra Trees
- Random Forest

**Output**
```text
closure_model_bundle.pkl
```

---

## M4b — Congestion Impact Scorer (CIS)

Computes:

```text
CIS Score (0–10)
```

Inputs:
- Cause
- Time
- Corridor
- Traffic ETA
- Escalation signals

Model:
- XGBoost Regressor

**Output**
```text
cis_scores.csv
scorer_model.pkl
```

---

## M4c — Incident Forecasting

Forecasts:

```text
Expected incidents per corridor
```

Model:
- Prophet

Output:
```text
forecast.json
```

---

## M5 — Inference Engine

Processes live traffic events.

Input:
```json
{
  "latitude": 12.98,
  "longitude": 77.59,
  "event_cause": "accident",
  "priority": "HIGH"
}
```

Returns:
- Closure prediction
- Congestion score
- Forecast context

---

## M6 — Resource Recommendation Engine

Generates:

- Officer count
- Barricades
- Diversion strategy

---

## M7 — Dashboard Server

Interactive dashboard with:

- Live prediction
- Heatmaps
- Historical insights
- Forecast visualization

---

# 🧠 ML Models Used

| Module | Model |
|--------|-------|
| M2 | Random Forest + KNN |
| M4a | Extra Trees + Random Forest |
| M4b | XGBoost |
| M4c | Prophet |

---


# 📈 Outputs

- Congestion Impact Score
- Closure Probability
- Incident Forecast
- Resource Deployment Plan
- Dashboard Visualization

---

# 🔍 Key Highlights

✅ End-to-End ML Pipeline  
✅ Explainable Predictions  
✅ Real Traffic Calibration  
✅ Forecasting + Decision Intelligence  
✅ Modular Architecture  
✅ Dashboard Ready  

---

# 👨‍💻 Author

Pushkeshwar Singh And Sohini Chaudhuri

---


