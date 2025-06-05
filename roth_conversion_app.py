import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from matplotlib import pyplot as plt
from fpdf import FPDF
import tempfile
import os

st.set_page_config(page_title="Roth Conversion Calculator", layout="wide")

st.title("📊 Roth Conversion Benefits Calculator")
st.markdown("""
This tool helps you visualize the benefits of converting Traditional IRA assets to Roth IRAs over time.
You’ll see how this strategy can reduce RMDs, avoid the Widow’s Penalty, and improve estate outcomes.
""")

# --- Required Inputs ---
filing_status = st.sidebar.selectbox("Filing Status", ["MFJ", "Single"])
trad_ira = st.sidebar.number_input("Traditional IRA Balance", value=500000)
roth_ira = st.sidebar.number_input("Roth IRA Balance", value=100000)
client_age = st.sidebar.number_input("Client Current Age", min_value=50, max_value=100, value=65)
life_expectancy = st.sidebar.number_input("Life Expectancy", min_value=70, max_value=100, value=90)
annual_income = st.sidebar.number_input("Annual Earned Income", value=20000)
other_income = st.sidebar.number_input("Other Annual Taxable Income", value=10000)
ss_client = st.sidebar.number_input("Annual Social Security (Client)", value=25000)
ss_start_client = st.sidebar.number_input("Client SS Start Age", min_value=62, max_value=70, value=67)
growth_rate = st.sidebar.slider("Growth Rate (%)", 0.0, 10.0, 6.0) / 100

# Strategy Selection
conversion_type = st.sidebar.selectbox(
    "Choose Roth Conversion Strategy",
    options=["Manual", "12% Bracket Fill", "22% Bracket Fill", "24% Bracket Fill", "Max to IRMAA Threshold"],
    index=1
)

if conversion_type == "Manual":
    conversion_amount = st.sidebar.number_input("Manual Roth Conversion Amount", min_value=0, step=1000)
elif conversion_type == "Max to IRMAA Threshold":
    bracket_target = None
else:
    bracket_target = conversion_type.split("%")[0] + "%"

# QCD
qcd_enabled = st.sidebar.checkbox("Enable QCD Modeling", value=False)
qcd_start_age = st.sidebar.number_input("QCD Start Age", min_value=70, max_value=100, value=70)
qcd_annual_amount = st.sidebar.number_input("Annual QCD Amount", value=10000 if qcd_enabled else 0)

# Widow Penalty
spouse_age = st.sidebar.number_input("Spouse Age", min_value=50, max_value=100, value=65)
w_survives_after = st.sidebar.number_input("Years After Which Survivor Files Single", min_value=0, max_value=50, value=10)
widow_trigger_year = 2025 + w_survives_after

# Social Security Delay
ss_delay_enabled = st.sidebar.checkbox("Model Delayed Social Security (Client)", value=False)
ss_delay_years = st.sidebar.slider("Delay SS by (years)", 0, 5, 0) if ss_delay_enabled else 0

# Tax brackets and limits
brackets_dict = {
    "MFJ": [(0, 0.10), (23200, 0.12), (94300, 0.22), (201050, 0.24), (383900, 0.32)],
    "Single": [(0, 0.10), (11600, 0.12), (47150, 0.22), (100525, 0.24), (191950, 0.32)]
}

bracket_limits = {
    "12%": 94300 if filing_status == "MFJ" else 47150,
    "22%": 201050 if filing_status == "MFJ" else 100525,
    "24%": 383900 if filing_status == "MFJ" else 191950,
    "32%": 600000 if filing_status == "MFJ" else 300000
}

# Main projection function
def run_projection(strategy):
    trad_val, roth_val = trad_ira, roth_ira
    trad_balances, roth_balances, conversions, rmds, taxes, estate_values, irmaa_surcharges = [], [], [], [], [], [], []

    for i, year in enumerate(range(2025, 2025 + (life_expectancy - client_age))):
        age = client_age + i
        current_status = "Single" if year >= widow_trigger_year else filing_status

        # RMD
        rmd = max(0, trad_val / 25 - qcd_annual_amount) if age >= 73 else 0

        # Social Security Income
        ss_start_age = ss_start_client + ss_delay_years if ss_delay_enabled else ss_start_client
        if year >= widow_trigger_year:
            ss_income = ss_client * 0.85  # Widowed = less SS
        else:
            ss_income = ss_client if age >= ss_start_age else 0

        gross_base = annual_income + other_income + rmd + ss_income
        deduction = 29200 if current_status == "MFJ" else 14600

        if strategy == "Manual":
            conversion = conversion_amount
        else:
            if conversion_type == "Max to IRMAA Threshold":
                limit = 206000 if current_status == "MFJ" else 103000
            else:
                limit = bracket_limits[bracket_target]
            conversion = max(0, limit - gross_base - deduction)

        # Account growth
        trad_val = trad_val * (1 + growth_rate) - rmd - conversion
        roth_val = roth_val * (1 + growth_rate) + conversion

        # Taxes
        taxable_income = gross_base + conversion - deduction
        tax = 0
        for j in range(len(brackets_dict[current_status])):
            lower, rate = brackets_dict[current_status][j]
            upper = brackets_dict[current_status][j + 1][0] if j + 1 < len(brackets_dict[current_status]) else float("inf")
            if taxable_income > lower:
                taxed = min(taxable_income, upper) - lower
                tax += taxed * rate

        # IRMAA
        irmaa_threshold = 206000 if current_status == "MFJ" else 103000
        irmaa = 0
        if taxable_income > irmaa_threshold:
            irmaa = 3000 if taxable_income < irmaa_threshold * 1.5 else 4500

        # Estate Value
        heir_tax_rate = 0.25
        estate_val = trad_val * (1 - heir_tax_rate) + roth_val

        trad_balances.append(trad_val)
        roth_balances.append(roth_val)
        conversions.append(conversion)
        rmds.append(rmd)
        taxes.append(tax)
        irmaa_surcharges.append(irmaa)
        estate_values.append(estate_val)

    return pd.DataFrame({
        "Year": list(range(2025, 2025 + (life_expectancy - client_age))),
        "Traditional IRA": trad_balances,
        "Roth IRA": roth_balances,
        "Roth Conversion": conversions,
        "RMD": rmds,
        "Estimated Tax": taxes,
        "IRMAA Surcharge": irmaa_surcharges,
        "Net Estate to Heirs": estate_values
    })

# Run scenarios
data_conversion = run_projection(conversion_type)
data_noconversion = run_projection("Manual") if conversion_type != "Manual" else data_conversion.copy()
data_noconversion["Roth Conversion"] = 0

# Summary Metrics
st.subheader("📌 Summary Comparison Metrics")
col1, col2, col3 = st.columns(3)

strategy_tax = data_conversion['Estimated Tax'].sum()
no_conversion_tax = data_noconversion['Estimated Tax'].sum()
strategy_estate = data_conversion['Net Estate to Heirs'].iloc[-1]
no_conversion_estate = data_noconversion['Net Estate to Heirs'].iloc[-1]
strategy_rmd = data_conversion['RMD'].sum()
no_conversion_rmd = data_noconversion['RMD'].sum()
net_benefit = strategy_estate - no_conversion_estate - (strategy_tax - no_conversion_tax)

col1.metric("Total Tax (Strategy)", f"${strategy_tax:,.0f}")
col1.metric("Total RMDs (Strategy)", f"${strategy_rmd:,.0f}")
col1.metric("Final Estate (Strategy)", f"${strategy_estate:,.0f}")

col2.metric("Total Tax (No Conversion)", f"${no_conversion_tax:,.0f}")
col2.metric("Total RMDs (No Conversion)", f"${no_conversion_rmd:,.0f}")
col2.metric("Final Estate (No Conversion)", f"${no_conversion_estate:,.0f}")

col3.metric("Net Benefit of Strategy", f"${net_benefit:,.0f}", delta=f"${net_benefit:,.0f}")
col3.metric("Total IRMAA (Strategy)", f"${data_conversion['IRMAA Surcharge'].sum():,.0f}")
col3.metric("Total IRMAA (No Conversion)", f"${data_noconversion['IRMAA Surcharge'].sum():,.0f}")

# Downloadable Summary
st.subheader("📄 Downloadable Summary Report")
csv_buffer = BytesIO()
data_conversion.to_csv(csv_buffer, index=False)
csv_buffer.seek(0)
st.download_button("📥 Download CSV Report (Strategy)", data=csv_buffer, file_name="roth_conversion_summary.csv", mime="text/csv")

# Charts
st.subheader("📊 Strategy Comparison Charts")
st.line_chart(data_conversion.set_index("Year")[["Roth IRA", "Traditional IRA"]])
st.line_chart(data_conversion.set_index("Year")[["Estimated Tax", "RMD"]])
st.line_chart(data_conversion.set_index("Year")[["Net Estate to Heirs"]])
st.line_chart(data_conversion.set_index("Year")[["IRMAA Surcharge"]])

# Table
st.subheader("📋 Strategy Year-by-Year Breakdown")
tab1, tab2 = st.tabs(["Strategy", "No Conversion"])
with tab1:
    st.dataframe(data_conversion.style.format("{:.2f}"))
with tab2:
    st.dataframe(data_noconversion.style.format("{:.2f}"))
