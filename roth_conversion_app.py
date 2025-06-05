import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

st.set_page_config(page_title="Roth Conversion Calculator", layout="wide")

st.title("📊 Roth Conversion Benefits Calculator")
st.markdown("""
This tool helps you visualize the benefits of converting Traditional IRA assets to Roth IRAs over time.
You’ll see how this strategy can reduce RMDs, avoid the Widow’s Penalty, and improve estate outcomes.
""")

# Inputs (shortened for space)

# Strategy Selection
conversion_type = st.sidebar.selectbox(
    "Choose Roth Conversion Strategy",
    options=["Manual", "12% Bracket Fill", "22% Bracket Fill", "24% Bracket Fill", "Max to IRMAA Threshold"],
    index=1
)

if conversion_type == "Manual":
    conversion_amount = st.sidebar.number_input("Manual Roth Conversion Amount", min_value=0, step=1000)
elif conversion_type == "Max to IRMAA Threshold":
    bracket_target = None  # Special handling
else:
    bracket_target = conversion_type.split("%")[0] + "%"
# --- insert full input section as before ---

# Define tax brackets
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

def run_projection(strategy):
    # Widow Penalty Logic Setup
    widow_year = widow_trigger_year if 'widow_trigger_year' in globals() else 2035  # Example default
    spouse_alive = True
    # Integrates QCD and Social Security Delay logic
    trad_val, roth_val = trad_ira, roth_ira
    trad_balances, roth_balances, conversions, rmds, taxes, estate_values, irmaa_surcharges = [], [], [], [], [], [], []

    for i, year in enumerate(range(2025, 2025 + (life_expectancy - client_age))):
        current_status = filing_status
        if year >= widow_year:
            current_status = "Single"
        qcd_active = qcd_enabled and (client_age + i) >= qcd_start_age
        qcd_amount = qcd_annual_amount if qcd_active else 0
        age = client_age + i
                rmd = max(0, trad_val / 25 - qcd_amount) if age >= 73 else 0

                ss_start_age = ss_start_client + ss_delay_years if ss_delay_enabled else ss_start_client
                if year >= widow_year:
            ss_income = ss_client * 0.85  # Assume 15% reduction when one spouse dies
        else:
            ss_income = ss_client if (age >= ss_start_age) else 0

        gross_base = annual_income + other_income + rmd + ss_income
                deduction = 29200 if current_status == "MFJ" else 14600

        if strategy == "Manual":
            conversion = conversion_amount
        else:
                                    if conversion_type == "Max to IRMAA Threshold":
                irmaa_cap = 206000 if current_status == "MFJ" else 103000
                limit = irmaa_cap
            else:
                limit = bracket_limits[bracket_target] if current_status == "MFJ" else bracket_limits[bracket_target] // 2
            conversion = max(0, limit - gross_base - deduction)

        trad_val = trad_val * (1 + growth_rate) - rmd - conversion
        roth_val = roth_val * (1 + growth_rate) + conversion

        taxable_income = gross_base + conversion - deduction
                bracket = brackets_dict[current_status]
                tax = 0
        for j in range(len(bracket)):
            if j == len(bracket) - 1 or taxable_income < bracket[j+1][0]:
                tax = (taxable_income - bracket[j][0]) * bracket[j][1]
                break

        heir_tax_rate = 0.25
                irmaa_threshold = 206000 if current_status == "MFJ" else 103000
        irmaa = 0
        if taxable_income > irmaa_threshold:
            irmaa = 3000 if taxable_income < irmaa_threshold * 1.5 else 4500  # Simplified model

        estate_val = trad_val * (1 - heir_tax_rate) + roth_val

        trad_balances.append(trad_val)
        roth_balances.append(roth_val)
        conversions.append(conversion)
        rmds.append(rmd)
        taxes.append(tax)
                irmaa_surcharges.append(irmaa)
        estate_values.append(estate_val)

            ss_start_age_used = ss_start_age if ss_income > 0 else None
        ss_start_ages = [ss_start_age_used] * len(trad_balances)
        qcd_amounts = [qcd_annual_amount if qcd_enabled and (client_age + i) >= qcd_start_age else 0 for i in range(len(trad_balances))]

    return pd.DataFrame({
        "IRMAA Surcharge": irmaa_surcharges,
        "SS Income": [ss_client if (client_age + i) >= ss_start_age else 0 for i in range(len(trad_balances))],
        "QCD Offset": qcd_amounts,
        "Year": list(range(2025, 2025 + (life_expectancy - client_age))),
        "Traditional IRA": trad_balances,
        "Roth IRA": roth_balances,
        "Roth Conversion": conversions,
        "RMD": rmds,
        "Estimated Tax": taxes,
        "Net Estate to Heirs": estate_values
    })

# Placeholder for QCD Modeling Inputs
qcd_enabled = st.sidebar.checkbox("Enable QCD Modeling", value=False)
qcd_start_age = st.sidebar.number_input("QCD Start Age", min_value=70, max_value=100, value=70)
qcd_annual_amount = st.sidebar.number_input("Annual QCD Amount", value=0 if not qcd_enabled else 10000)

# Widow Modeling Inputs
spouse_age = st.sidebar.number_input("Spouse Age", min_value=50, max_value=100, value=65)
w_survives_after = st.sidebar.number_input("Years After Which Survivor Files Single", min_value=0, max_value=50, value=10)
widow_trigger_year = 2025 + w_survives_after

# Placeholder for Social Security Delay Modeling
ss_delay_enabled = st.sidebar.checkbox("Model Delayed Social Security (Client)", value=False)
ss_delay_years = st.sidebar.slider("Delay SS by (years)", 0, 5, 0) if ss_delay_enabled else 0

# 📌 Summary Metrics
st.subheader("📌 Summary Comparison Metrics")
col1, col2, col3 = st.columns(3)

strategy_tax = data_conversion['Estimated Tax'].sum()
no_conversion_tax = data_noconversion['Estimated Tax'].sum()
strategy_rmd = data_conversion['RMD'].sum()
no_conversion_rmd = data_noconversion['RMD'].sum()
strategy_estate = data_conversion['Net Estate to Heirs'].iloc[-1]
no_conversion_estate = data_noconversion['Net Estate to Heirs'].iloc[-1]
net_benefit = strategy_estate - no_conversion_estate - (strategy_tax - no_conversion_tax)

col1.metric("Total Tax (Strategy)", f"${strategy_tax:,.0f}")
col1.metric("Total RMDs (Strategy)", f"${strategy_rmd:,.0f}")
col1.metric("Final Estate (Strategy)", f"${strategy_estate:,.0f}")

col2.metric("Total Tax (No Conversion)", f"${no_conversion_tax:,.0f}")
col2.metric("Total RMDs (No Conversion)", f"${no_conversion_rmd:,.0f}")
col2.metric("Final Estate (No Conversion)", f"${no_conversion_estate:,.0f}")

col3.metric("Net Benefit of Strategy", f"${net_benefit:,.0f}", delta=f"{'+' if net_benefit >= 0 else ''}${net_benefit:,.0f}", delta_color="normal" if net_benefit >= 0 else "inverse")

# IRMAA Summary Totals
col3.metric("Total IRMAA (Strategy)", f"${data_conversion['IRMAA Surcharge'].sum():,.0f}")
col3.metric("Total IRMAA (No Conversion)", f"${data_noconversion['IRMAA Surcharge'].sum():,.0f}")

# Run scenarios

# Optional QCD modeling & Social Security delay logic can go here
data_conversion = run_projection(conversion_type)
data_noconversion = run_projection("Manual") if conversion_type != "Manual" else data_conversion.copy()
data_noconversion["Roth Conversion"] = 0

# Downloadable summary
from matplotlib import pyplot as plt
from fpdf import FPDF
import tempfile
import os
st.subheader("📄 Downloadable Summary Report")
csv_buffer = BytesIO()
data_conversion.to_csv(csv_buffer, index=False)
csv_buffer.seek(0)
st.download_button("📥 Download CSV Report (Strategy)", data=csv_buffer, file_name="roth_conversion_summary.csv", mime="text/csv")

# Charts
st.subheader("📊 Strategy Comparison Charts")
st.line_chart(pd.DataFrame({
    "Roth IRA (Strategy)": data_conversion.set_index("Year")["Roth IRA"],
    "Roth IRA (No Conversion)": data_noconversion.set_index("Year")["Roth IRA"]
}))
st.line_chart(pd.DataFrame({
    "Estimated Tax (Strategy)": data_conversion.set_index("Year")["Estimated Tax"],
    "Estimated Tax (No Conversion)": data_noconversion.set_index("Year")["Estimated Tax"]
}))
st.line_chart(pd.DataFrame({
    "Estate to Heirs (Strategy)": data_conversion.set_index("Year")["Net Estate to Heirs"],
    "Estate to Heirs (No Conversion)": data_noconversion.set_index("Year")["Net Estate to Heirs"]
}))
st.line_chart(pd.DataFrame({
    "RMD (Strategy)": data_conversion.set_index("Year")["RMD"],
    "QCD Offset": data_conversion.set_index("Year")["QCD Offset"]
}))
st.line_chart(pd.DataFrame({
    "SS Income": data_conversion.set_index("Year")["SS Income"]
}))
st.line_chart(pd.DataFrame({
    "IRMAA Surcharge": data_conversion.set_index("Year")["IRMAA Surcharge"]
}))

# PDF Report Generator
st.subheader("🖨️ Generate PDF Report")
if st.button("📄 Create PDF Report"):
    with tempfile.TemporaryDirectory() as tmpdir:
        plt.figure(figsize=(10, 5))
        plt.plot(data_conversion["Year"], data_conversion["Roth IRA"], label="Roth IRA")
        plt.plot(data_conversion["Year"], data_conversion["Traditional IRA"], label="Traditional IRA")
        plt.title("IRA Balances Over Time")
        plt.xlabel("Year")
        plt.ylabel("Balance")
        plt.legend()
        chart_path = os.path.join(tmpdir, "ira_chart.png")
        plt.savefig(chart_path)
        plt.close()

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt="Roth Conversion Summary Report", ln=True, align='C')
        pdf.ln(10)
        pdf.cell(200, 10, txt=f"Net Benefit: ${net_benefit:,.0f}", ln=True)
        pdf.cell(200, 10, txt=f"Final Estate (Strategy): ${strategy_estate:,.0f}", ln=True)
        pdf.cell(200, 10, txt=f"Final Estate (No Conversion): ${no_conversion_estate:,.0f}", ln=True)
        pdf.cell(200, 10, txt=f"Total Taxes (Strategy): ${strategy_tax:,.0f}", ln=True)
pdf.cell(200, 10, txt=f"Total IRMAA (Strategy): ${data_conversion['IRMAA Surcharge'].sum():,.0f}", ln=True)
pdf.cell(200, 10, txt=f"Total IRMAA (No Conversion): ${data_noconversion['IRMAA Surcharge'].sum():,.0f}", ln=True)
        pdf.image(chart_path, x=10, y=60, w=180)

        pdf_output = os.path.join(tmpdir, "roth_report.pdf")
        pdf.output(pdf_output)

        with open(pdf_output, "rb") as f:
            st.download_button(
                label="📥 Download PDF Report",
                data=f,
                file_name="roth_conversion_summary.pdf",
                mime="application/pdf"
            )

# Table
st.subheader("📋 Strategy Year-by-Year Breakdown")
with st.tabs(["Strategy", "No Conversion"]):
    with st.tab("Strategy"):
        st.dataframe(data_conversion.style.format("{:.2f}"))
    with st.tab("No Conversion"):
        st.dataframe(data_noconversion.style.format("{:.2f}"))
