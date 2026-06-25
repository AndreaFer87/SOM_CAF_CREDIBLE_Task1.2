import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

st.set_page_config(layout="wide")
st.title("🌱 VSoM – Soil Organic Matter Value Framework")

# =========================
# INPUT SECTION
# =========================

st.sidebar.header("Soil Inputs")

SOC = st.sidebar.number_input("SOC stock (t C/ha)", value=60.0)
delta_SOC = st.sidebar.number_input("ΔSOC (t C/ha/yr)", value=0.4)

sand = st.sidebar.number_input("% Sand", 0, 100, 40)
clay = st.sidebar.number_input("% Clay", 0, 100, 20)
silt = 100 - sand - clay

BD_ref = st.sidebar.number_input("Bulk density (g/cm3)", value=1.3)

z_eff = st.sidebar.number_input("Effective rooting depth (cm)", value=30)

st.sidebar.header("Crop rotation")
crops = st.sidebar.multiselect(
    "Crop rotation",
    ["winter cereals", "maize", "soybean", "tomato"],
    default=["winter cereals", "maize"]
)

years = st.sidebar.slider(
    "Rotation length (years)",
    1, 10, 3
)


st.sidebar.header("Economic parameters")

P_N = st.sidebar.number_input("Price N (€/kg)", value=0.54)
P_P = st.sidebar.number_input("Price P2O5 (€/kg)", value=0.74)
P_S = st.sidebar.number_input("Price SO3 (€/kg)", value=1.0)

P_water = st.sidebar.number_input("Water value (€/mm)", value=0.15)
P_flood = st.sidebar.number_input("Flood damage value (€/mm)", value=0.3)

C_machinery = st.sidebar.number_input("Machinery cost €/h", value=25.0)
P_diesel = st.sidebar.number_input("Diesel price €/L", value=1.7)

# =========================
# TEXTURE PARAMETERS
# =========================

def get_usda_texture(sand, clay):

    if sand > 85 and clay < 10:
        return "sand"
    elif clay > 40:
        return "clay"
    elif sand > 43 and clay < 20:
        return "loam"
    else:
        return "clay loam"

k_SOM_map = { "sand": 1.2, "loam": 1.6, "clay loam": 2.0,"clay": 2.3 }

def k_minN(climate, texture):

    base = { "cold": 0.001, "temperate": 0.004, "warm": 0.012
    }[climate]

    texture_factor = {
        "sand": 1.2,
        "loam": 1.0,
        "clay loam": 0.9,
        "clay": 0.8
    }[texture]

    return base * texture_factor

f_labile = {
    "N": 0.03,   # 2–5% SOM active N pool
    "P": 0.005,  # 0.2–1%
    "S": 0.01
}

eta_P = {
    "sand": 0.4,
    "loam": 0.6,
    "clay loam": 0.75,
    "clay": 0.85
}

eta_S = {
    "sand": 0.5,
    "loam": 0.7,
    "clay loam": 0.8,
    "clay": 0.9
}

P_C = 0.003   # mid of 0.001–0.005
S_C = 0.0012  # mid of 0.0005–0.002

alpha = {"sand":3.0, "loam":2.5, "clay loam":2.2, "clay":2}

lambda_bd = {"sand":0.05, "loam":0.12, "clay loam":0.18, "clay":0.25}

PT = {"sand":0.2, "loam":0.3, "clay loam":0.4, "clay":0.45}

# =========================
# NUTRIENT MODULE
# =========================

texture = get_usda_texture(sand, clay)

climate = st.sidebar.selectbox(
    "Climate",
    ["cold", "temperate", "warm"],
    index=1
)

SOM_functional = delta_SOC/10/10/BD_ref/0.3 * k_SOM_map[texture] 

C_N = 10

N_min = SOM_functional * k_minN(climate, texture) * 0.3 * 100000 * BD_ref
P_avail = SOM_functional * P_C * eta_P[texture]* 0.3 * 100000 * BD_ref * f_labile["P"]
S_avail = SOM_functional * S_C * eta_S[texture]* 0.3 * 100000 * BD_ref * f_labile["S"]


# =========================
# CROP CALENDAR (NEW CORRECT STRUCTURE)
# =========================

crop_calendar = {
    "winter cereals": {"months": 10},
    "maize": {"months": 5},
    "soybean": {"months": 5},
    "tomato": {"months": 6}
}

# ONLY allowed crops come from calendar
available_crops = list(crop_calendar.keys())


U_m = {
    "winter cereals": {
        "establishment": 0.15,
        "vegetative_peak": 0.45,
        "reproductive": 0.30,
        "senescence": 0.10
    },
    "maize": {
        "establishment": 0.10,
        "vegetative_peak": 0.60,
        "reproductive": 0.25,
        "senescence": 0.05
    },
    "soybean": {
        "establishment": 0.10,
        "vegetative_peak": 0.35,
        "reproductive": 0.45,
        "senescence": 0.10
    },
    "tomato": {
        "establishment": 0.15,
        "vegetative_peak": 0.40,
        "reproductive": 0.35,
        "senescence": 0.10
    }
}

# =========================
# N CROP MODULE (SEQUENTIAL ROTATION FIX)
# =========================

import numpy as np

n_months = 12

N_monthly_base = np.ones(n_months) * (N_min / n_months)

N_total_profile = np.zeros(n_months)

t_cursor = 0  # <-- chiave: posizione nella rotazione

for c in crops:

    crop_months = int(round(crop_calendar[c]["months"]))
    intensity = crop_calendar[c].get("intensity", 1.0)

    phen = U_m[c]
    phen_weights = np.array(list(phen.values()), dtype=float)
    phen_weights = phen_weights / phen_weights.sum()

    crop_profile = np.zeros(n_months)

    # distribuzione SOLO nel blocco temporale assegnato
    for i in range(crop_months):

        global_month = (t_cursor + i) % n_months

        phase_idx = int(i / crop_months * len(phen_weights))
        phase_idx = min(phase_idx, len(phen_weights) - 1)

        crop_profile[global_month] += phen_weights[phase_idx]

    # normalizzazione interna coltura
    if crop_profile.sum() > 0:
        crop_profile /= crop_profile.sum()

    # scaling temporale reale
    crop_profile *= (crop_months / 12.0) * intensity

    # accumulo su asse temporale
    N_total_profile += N_monthly_base * crop_profile

    # avanzamento rotazione (FONDAMENTALE)
    t_cursor += crop_months

# chiusura ciclo
N_crop = N_total_profile.sum() / years

V_N = N_crop * P_N
V_P = P_avail * P_P
V_S = S_avail * P_S

V_nutrients = V_N + V_P + V_S

# =========================
# WATER MODULE
# =========================

delta_SOC_percent = delta_SOC/10/10/0.3/BD_ref

SOC_effect_layer = 10  # cm

Delta_PAW_surface = alpha[texture] * delta_SOC_percent

root_access_factor = 1 - np.exp(-z_eff / 15)

Delta_PAW = Delta_PAW_surface * root_access_factor

# =========================
# WATER MODULE (ERA5-BASED)
# =========================

from pathlib import Path
import pandas as pd

DATA_PATH = Path(__file__).parent / "data" / "era5_processed_daily_data_id_crp_103.csv"

df = pd.read_csv(DATA_PATH)
df["date"] = pd.to_datetime(df["date"])

# -------------------------
# AGGREGATION MONTHLY
# -------------------------

df["month"] = df["date"].dt.to_period("M")

monthly = df.groupby("month").agg({
    "potential_evaporation_mm": "sum",
    "precipitation_mm": "sum"
}).reset_index()

monthly["DEF"] = (monthly["potential_evaporation_mm"] - monthly["precipitation_mm"]).clip(lower=0)

# -------------------------
# f_crit (CLIMATE STRESS INDEX)
# -------------------------

def compute_f_crit(monthly_df):
    et0 = monthly_df["potential_evaporation_mm"].sum()
    deficit = monthly_df["DEF"].sum()

    return deficit / (et0 + 1e-9)

f_crit = compute_f_crit(monthly)


# crop stress relevance weighting
Delta_PAW_crit = Delta_PAW * f_crit


Ks_map = {
    "sand": 40,      # mm/h
    "loam": 20,
    "clay loam": 10,
    "clay": 5
}
Ks = Ks_map[texture]

phi_map = {
    "compacted": 0.6,
    "normal": 0.9,
    "well_structured": 1.2
}

phi = phi_map["normal"]  # oppure lo rendiamo dinamico dopo


phi_struct = {
    "sand": 1.2,
    "loam": 1.0,
    "clay loam": 0.9,
    "clay": 0.8
}

theta_infiltration = {
    "sand": 0.07,      # low sensitivity
    "loam": 0.15,      # medium
    "clay loam": 0.20,
    "clay": 0.25        # high structural response
}

t_event_default = 6  # hours (ERA5 daily proxy)
rain_threshold = 10  # mm

df["date"] = pd.to_datetime(df["date"])

# rainfall (mm/day)
df["P_k"] = df["precipitation_mm"]

# evap / not needed here but optional
df["t_k"] = t_event_default  # proxy ERA5 daily

# event filtering (only meaningful rainfall events)
events = df[df["P_k"] > rain_threshold].copy()

# intensity (not strictly needed but consistent with theory)
events["I_rain_k"] = events["P_k"] / events["t_k"]

texture_factor = phi_struct[texture]

I0 = Ks * phi

# baseline infiltration capacity (mm/h)
I0_event = I0 * texture_factor

def INF_base(Pk, tk):
    return np.minimum(I0_event * tk, Pk)


I_new_event = I0_event * (1 + theta_infiltration[texture] * delta_SOC_percent)

def INF_new(Pk, tk):
    return np.minimum(I_new_event * tk, Pk)

events["INF_base"] = events.apply(lambda r: INF_base(r["P_k"], r["t_k"]), axis=1)
events["INF_new"]  = events.apply(lambda r: INF_new(r["P_k"], r["t_k"]), axis=1)

events["Delta_INF_k"] = events["INF_new"] - events["INF_base"]
events["Delta_INF_k"] = events["Delta_INF_k"].clip(lower=0)

n_years = events["date"].dt.year.nunique()

Delta_INF = events["Delta_INF_k"].sum() / n_years

V_PAW = Delta_PAW_crit * P_water
V_INF = Delta_INF * P_flood

V_water = V_PAW + V_INF

# =========================
# STRUCTURE MODULE
# =========================

Delta_BD = -lambda_bd[texture] * delta_SOC

BD_new = BD_ref + Delta_BD

S_struct = BD_ref / BD_new

PT_value = PT[texture]

W_index = S_struct / (1 + np.exp(BD_ref - PT_value))

W_days = max(delta_SOC * 10, 0)

H_saved = W_days * 0.5
F_saved = W_days * 0.2

V_structure = (H_saved * C_machinery) + (F_saved * P_diesel)

# =========================
# TOTAL VALUE
# =========================

V_SOM = V_nutrients + V_water + V_structure

# =========================
# OUTPUT
# =========================

col1, col2, col3 = st.columns(3)

col1.metric("🌱 Nutrients Value (€)", round(V_nutrients,2))
col1.metric("N mineralisation", round(N_min,2))
col1.metric("P availability", round(P_avail,2))

col2.metric("💧 Water Value (€)", round(V_water,2))
col2.metric("ΔPAW (mm)", round(Delta_PAW,2))
col2.metric("ΔINF proxy", round(Delta_INF,2))

col3.metric("🧱 Structure Value (€)", round(V_structure,2))
col3.metric("ΔBD", round(Delta_BD,3))
col3.metric("Workability index", round(W_index,3))

st.success(f"💰 TOTAL VSoM = {round(V_SOM,2)} €/ha/year")


# =========================
# NUTRIENT OUTPUT SUMMARY
# =========================

st.subheader("🌱 Nutrient Mineralisation Summary (Rotation average)")

colA, colB, colC, colD,colE  = st.columns(5)

colA.metric("N mine (kg/ha/yr)", round(N_min, 2))
colB.metric("N crop (kg/ha/yr)", round(N_crop, 2))
colC.metric("P available (kg/ha/yr)", round(P_avail, 2))
colD.metric("S available (kg/ha/yr)", round(S_avail, 2))
colE.metric("Total nutrient value (€)", round(V_nutrients, 2))

# breakdown
total_n = N_crop + P_avail + S_avail

if total_n > 0:
    st.write("### Nutrient contribution (%)")
    st.write(f"N: {N_crop/total_n:.1%}")
    st.write(f"P: {P_avail/total_n:.1%}")
    st.write(f"S: {S_avail/total_n:.1%}")



st.subheader("📊 Crop phenology contribution")

for c in crops:
    duration = (crop_calendar[c]["months"] / 12) * crop_calendar[c]["intensity"]
    stage_sum = sum([U_m[s] for s in crop_phenology[c]])
    f_crop = stage_sum / U_m_total

    st.write(f"{c}: f_crop={round(f_crop,2)}, duration={round(duration,2)}")
# =========================
# PLOT BREAKDOWN
# =========================

fig, ax = plt.subplots()

labels = ["Nutrients", "Water", "Structure"]
values = [V_nutrients, V_water, V_structure]

ax.bar(labels, values)
ax.set_ylabel("€/ha/year")

st.pyplot(fig)
