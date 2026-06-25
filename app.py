import streamlit as st
import numpy as np
import matplotlib.pyplot as plt

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

st.sidebar.header("Climate / Water")

f_crit = st.sidebar.slider("f_crit (0-1)", 0.0, 1.0, 0.6)

I0 = st.sidebar.number_input("I0 infiltration capacity", value=10.0)

st.sidebar.header("Economic parameters")

P_N = st.sidebar.number_input("Price N (€/kg)", value=1.2)
P_P = st.sidebar.number_input("Price P2O5 (€/kg)", value=2.5)
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

    base = { "cold": 0.04, "temperate": 0.07, "warm": 0.12
    }[climate]

    texture_factor = {
        "sand": 1.2,
        "loam": 1.0,
        "clay loam": 0.9,
        "clay": 0.8
    }[texture]

    return base * texture_factor


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

alpha = {"sand":1.2, "loam":2.0, "clay loam":2.5, "clay":3.0}

lambda_bd = {"sand":0.05, "loam":0.12, "clay loam":0.18, "clay":0.25}

theta_infiltration = {"sand":0.3, "loam":0.4, "clay loam":0.5, "clay":0.6}

PT = {"sand":0.2, "loam":0.3, "clay loam":0.4, "clay":0.45}

# =========================
# NUTRIENT MODULE
# =========================

SOM_functional = SOC * k_SOM_map

C_N = 10

N_min = SOM_functional * (1/10) * k_minN(climate, texture)
P_avail = SOM_functional * P_C * eta_P[texture]
S_avail = SOM_functional * S_C * eta_S[texture]

N_crop = 0

for c in crops:
    stages = f_crop.get(c, [])
    for s in stages:
        N_crop += N_min * U_m[s]


V_N = N_crop * P_N
V_P = P_avail * P_P
V_S = S_avail * P_S

V_nutrients = V_N + V_P + V_S

# =========================
# WATER MODULE
# =========================

Delta_PAW = alpha[texture] * (z_eff/10) * delta_SOC
Delta_PAW_crit = Delta_PAW * f_crit

I_new = I0 * (1 + theta_infiltration[texture] * delta_SOC)

Delta_INF = (I_new - I0) * 50  # proxy aggregation

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

W_days = Delta_SOC_days = delta_SOC * 10

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
# PLOT BREAKDOWN
# =========================

fig, ax = plt.subplots()

labels = ["Nutrients", "Water", "Structure"]
values = [V_nutrients, V_water, V_structure]

ax.bar(labels, values)
ax.set_ylabel("€/ha/year")

st.pyplot(fig)
