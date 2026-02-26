# Motorway Design Coursework App

EN3309 Week 1 + Week 2 — Single-file Streamlit app using Ted's Spyder logic.

## Files

```
c:\Moterway design\
├── app.py           # All logic + UI (merged)
├── requirements.txt
├── README.md
└── out_motorway/    # Excel output (created on Run)
```

## Setup

```bash
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

## Features

- **Week 1**: Ground/bedrock profiles, trapezoid embankment, Craig strip Δσ, m_v/Cc consolidation
- **Week 2**: Vertical consolidation times (Tv from Uv), PVD sizing (TR from table, R, spacing)
- Sidebar inputs mirror motorway_calc variables
- Two plots: longitudinal profile, cross section at chosen chainage
- Tables: Week1 chainage, key sections, Week2 chainage, PVD summary
- Formulas (LaTeX) and worked example
- Excel export to `out_motorway/Motorway_Week1.xlsx`
