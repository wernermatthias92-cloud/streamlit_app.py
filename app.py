import streamlit as st
import pandas as pd

from system.parallel import simuliere_parallel
from system.parallel_drossel import simuliere_parallel_drossel

st.set_page_config(page_title="RO Simulator", layout="wide")

st.title("RO Membransystem Simulator (physikalisch)")

modus = st.sidebar.selectbox(
    "Modus",
    ["Ziel-Recovery", "Drosselsteuerung"]
)

# -----------------------------
# Eingaben
# -----------------------------
st.sidebar.header("Systemparameter")

n_membranes = st.sidebar.number_input("Membranen", 1, 20, 4)

p_feed = st.sidebar.number_input("Feeddruck [bar]", 1.0, 80.0, 15.0)
p_perm = st.sidebar.number_input("Permeatdruck [bar]", 0.5, 5.0, 1.0)

tds = st.sidebar.number_input("TDS [ppm]", 100, 50000, 2000)

st.sidebar.header("Membran")

area = st.sidebar.number_input("Membranfläche [m²]", 1.0, 50.0, 10.0)
test_flow = st.sidebar.number_input("Testfluss [l/h]", 100.0, 5000.0, 1500.0)
test_pressure = st.sidebar.number_input("Testdruck [bar]", 1.0, 20.0, 10.0)

A = (test_flow / 1000 / 3600) / (area * test_pressure * 1e5)

st.sidebar.header("Rohrleitungen")

d_in = st.sidebar.number_input("Zulauf Durchmesser [m]", 0.005, 0.1, 0.02)
d_out = st.sidebar.number_input("Ablauf Durchmesser [m]", 0.005, 0.1, 0.02)

L_in = st.sidebar.number_input("Zulauf Länge [m]", 0.1, 50.0, 2.0)
L_out = st.sidebar.number_input("Ablauf Länge [m]", 0.1, 50.0, 2.0)

# -----------------------------
# Simulation
# -----------------------------
if modus == "Ziel-Recovery":

    recovery_target = st.sidebar.slider("Recovery [%]", 10, 80, 50) / 100

    res = simuliere_parallel(
        n_membranes,
        p_feed,
        p_perm,
        A,
        area,
        tds,
        d_in,
        d_out,
        L_in,
        L_out,
        recovery_target
    )

else:

    d_drossel = st.sidebar.number_input("Drossel Durchmesser [m]", 0.002, 0.05, 0.01)
    L_drossel = st.sidebar.number_input("Drossel Länge [m]", 0.01, 2.0, 0.2)

    res = simuliere_parallel_drossel(
        n_membranes,
        p_feed,
        p_perm,
        A,
        area,
        tds,
        d_in,
        d_out,
        d_drossel,
        L_in,
        L_out,
        L_drossel
    )

# -----------------------------
# Ausgabe
# -----------------------------
st.header("Ergebnisse")

st.metric("Recovery", f"{res['recovery']*100:.1f} %")
st.metric("Permeat gesamt [l/h]", f"{res['Qp_total']*3600*1000:.1f}")

df = pd.DataFrame([
    {
        "Membran": i,
        "Feed [l/h]": s["Qf"]*3600*1000,
        "Permeat [l/h]": s["Qp"]*3600*1000,
        "Konzentrat [l/h]": s["Qc"]*3600*1000,
        "Druck [bar]": s["p_in"]/1e5
    }
    for i, s in enumerate(res["streams"])
])

st.dataframe(df)
