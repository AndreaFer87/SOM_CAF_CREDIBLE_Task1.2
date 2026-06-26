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

delta_SOC = st.sidebar.number_input("ΔSOC (t C/ha/yr)", value=0.4)

sand = st.sidebar.number_input("% Sand", 0, 100, 20)
clay = st.sidebar.number_input("% Clay", 0, 100, 40)
silt = 100 - sand - clay

BD_ref = st.sidebar.number_input("Bulk density (g/cm3)", value=1.35)

z_eff = st.sidebar.number_input("Effective rooting depth (cm)", value=60)

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
P_flood = st.sidebar.slider("Flood damage value (€/mm)", 0.1, 1.0, 0.35)
P_erosion = st.sidebar.slider("Erosion/runoff damage (€/mm)", 0.05, 0.5, 0.15)

C_machinery = st.sidebar.number_input("Machinery cost €/h", value=25.0)
P_diesel = st.sidebar.number_input("Diesel price €/L", value=1.2)

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
    "N": 0.9,   #SOM active N pool
    "P": 0.8,  #SOM active P pool
    "S": 0.8 #SOM active S pool
}

def climate_factor_P(climate):
    return {
        "cold": 0.85,
        "temperate": 1.0,
        "warm": 1.15
    }[climate]


def climate_factor_S(climate):
    return {
        "cold": 0.9,
        "temperate": 1.0,
        "warm": 1.1
    }[climate]

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

N_min = SOM_functional * f_labile["N"]* k_minN(climate, texture) * 0.3 * 100000 * BD_ref
P_avail = SOM_functional * P_C * eta_P[texture]* 0.3 * 100000 * BD_ref * f_labile["P"]* climate_factor_P(climate)
P_avail = P_avail * (1 / (1 + clay * 0.02))  # adsorption penalty
S_avail = SOM_functional * S_C * eta_S[texture]* 0.3 * 100000 * BD_ref * f_labile["S"]* climate_factor_S(climate)


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

crop_structure_weights = {
    "winter cereals": {
        "pre_sowing": 0.8,
        "harvest": 0.6,
        "traffic_sensitivity": 0.7
    },
    "maize": {
        "pre_sowing": 0.9,
        "harvest": 0.8,
        "traffic_sensitivity": 0.85
    },
    "soybean": {
        "pre_sowing": 0.6,
        "harvest": 0.7,
        "traffic_sensitivity": 0.65
    },
    "tomato": {
        "pre_sowing": 0.85,
        "harvest": 0.95,
        "traffic_sensitivity": 0.9
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

V_N = N_min * P_N
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


# =========================
# WATER ECONOMIC VALUE (LEVEL 2)
# =========================

# 1. Flood / waterlogging damage avoidance
V_flood = Delta_INF * P_flood

# 2. Runoff + erosion proxy
# proxy: assume fraction of non-infiltrated water becomes runoff
runoff_fraction = 0.3   # literature range 0.2–0.5

Delta_runoff = Delta_INF * runoff_fraction

V_erosion = Delta_runoff * P_erosion

# 3. TOTAL WATER VALUE
V_INF = V_flood + V_erosion

V_PAW = Delta_PAW_crit * P_water

V_water = V_PAW + V_INF


# =========================
# STRUCTURE MODULE (FINAL FIXED VERSION)
# =========================

import numpy as np

# =========================
# 1. SOIL STRUCTURE EFFECT (SOM → BD)
# =========================

Delta_BD = -lambda_bd[texture] * delta_SOC
BD_new = BD_ref + Delta_BD

S_struct = BD_ref / BD_new  # scalar


# =========================
# 2. CLIMATE MOISTURE PROXY (ERA5 DAILY)
# =========================

theta_day = df["precipitation_mm"] - df["potential_evaporation_mm"]
theta_norm = theta_day / 100.0

PT_value = PT[texture]


# =========================
# 3. WORKABILITY INDEX (DAILY SERIES)
# =========================

W_index_base = 1.0 / (1 + np.exp(theta_norm - PT_value))
W_index_new  = S_struct / (1 + np.exp(theta_norm - PT_value))
W_index_clean = np.nan_to_num(np.array(W_index_new), nan=0.0)
W_index_clean = np.asarray(W_index_clean, dtype=float)


tau = 0.5


# =========================
# 4. WORKABLE DAYS (BASE + NEW)
# =========================

df["workable_base"] = W_index_base > tau
df["workable_new"]  = W_index_new > tau

W_days_base = df["workable_base"].sum() / df["date"].dt.year.nunique()
W_days_new  = df["workable_new"].sum() / df["date"].dt.year.nunique()

Delta_W_days = max(W_days_new - W_days_base, 0)


# =========================
# 5. CROP WEIGHTING (OPERATIONAL WINDOWS)
# =========================

w_pre_total = 0
w_harv_total = 0

for c in crops:
    w = crop_structure_weights[c]
    w_pre_total += w["pre_sowing"]
    w_harv_total += w["harvest"]

w_sum = w_pre_total + w_harv_total + 1e-9

w_pre = w_pre_total / w_sum
w_harv = w_harv_total / w_sum


Delta_W_pre = Delta_W_days * w_pre
Delta_W_harv = Delta_W_days * w_harv


# =========================
# 6. OPERATIONAL TRANSLATION
# =========================

H_pre = 2.0
H_harv = 2.5

F_pre = 12.0   # 👈 coerente con tuo vincolo (>10 L/ha pre-seeding)
F_harv = 8.0

H_saved = (Delta_W_pre * H_pre) + (Delta_W_harv * H_harv)
F_saved = (Delta_W_pre * F_pre) + (Delta_W_harv * F_harv)

V_structure = (H_saved * C_machinery) + (F_saved * P_diesel)

# =========================
# 7. ECONOMIC VALUE
# =========================



st.subheader("💰 VSoM Total Breakdown")

c1, c2, c3, c4 = st.columns(4)

c1.metric("V Nutrients", f"{V_nutrients:.2f} €")
c2.metric("V Water", f"{V_water:.2f} €")
c3.metric("V Structure", f"{V_structure:.2f} €")
c4.metric("SOM increase", f"{SOM_functional:.2f} % annual increase")

st.metric("TOTAL VSoM", f"{(V_nutrients + V_water + V_structure):.2f} €/ha/yr")


st.subheader("🌱 Nutrients module")

fig, ax = plt.subplots()

# =========================
# 1. MAIN MINERALIZATION BARS
# =========================
bars = ax.bar(
    ["N min", "P avail", "S avail"],
    [N_min, P_avail, S_avail],
    color=["tab:green", "tab:blue", "tab:orange"]
)

ax.set_ylabel("kg/ha/yr")
ax.set_title("SOM-driven mineralization (ΔSOC functional response)")

# =========================
# ANNOTATIONS CORRETTE
# =========================

labels = ["N min", "P avail", "S avail"]
values = [N_min, P_avail, S_avail]

for i, (label, val) in enumerate(zip(labels, values)):

    if label == "N min":
        text = f"avg Ncrop uptake:\n{N_crop:.1f}"
        color = "darkgreen"
        y_offset = -0.1
    elif label == "P avail":
        text = f"{P_avail:.1f}"
        color = "black"
        y_offset = 0.05

    else:  # S avail
        text = f"{S_avail:.1f}"
        color = "black"
        y_offset = 0.05

    ax.text(
        i,
        val * (1 + y_offset),
        text,
        ha="center",
        va="bottom",
        fontsize=8,
        fontweight="bold",
        color=color
    )

st.pyplot(fig)

# =========================
# 3. EXPLANATION BOX (IMPORTANT FOR READABILITY)
# =========================

st.info(
"""
**Interpretation**

- **N min** = SOM-driven nitrogen mineralization potential (soil supply)
- **P avail / S avail** = structurally mediated release of P and S pools
- **Ncrop uptake potential** = effective nitrogen available for crop uptake after rotation weighting and climatic adjustment

👉 Ncrop represents the *plant-available fraction* of mineralized nitrogen integrated over crop demand and phenology.
"""
)




st.subheader("💧 Water module")

fig, ax = plt.subplots()

ax.bar(
    ["ΔPAW", "ΔPAW crit", "ΔINF"],
    [Delta_PAW, Delta_PAW_crit, Delta_INF]
)

ax.set_ylabel("mm/year")

st.pyplot(fig)


st.subheader("🧱 Structure module")

fig, ax = plt.subplots()

ax.bar(
    ["H saved (€)", "F saved (€)"],
    [
        H_saved * C_machinery,
        F_saved * P_diesel
    ]
)

ax.set_ylabel("€/ha/year")

st.pyplot(fig)

st.write("Operational savings breakdown:")
st.write(f"- Machinery hours saved: {H_saved:.2f} h/ha")
st.write(f"- Diesel saved: {F_saved:.2f} L/ha")
