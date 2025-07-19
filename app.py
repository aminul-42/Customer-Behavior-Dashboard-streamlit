import streamlit as st
import pandas as pd
import plotly.express as px
import io, os, time, glob
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import pdfkit
import platform
from datetime import datetime

report_time = datetime.now().strftime('%B %d, %Y at %I:%M %p')

# ---- CLEAN OLD FILES (> 1 hour) ----
def cleanup_old_files():
    for ext in ["*.pdf"]:
        for file in glob.glob(ext):
            if time.time() - os.path.getmtime(file) > 3600:  # 1 hour
                try:
                    os.remove(file)
                except Exception as e:
                    print(f"Cleanup error: {file} — {e}")

cleanup_old_files()

# ---- PAGE CONFIG ----
st.set_page_config(page_title="Customer Dashboard", layout="wide")

# ---- LOAD CUSTOM CSS ----
with open("styles/style.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ---- LOAD DATA ----
df = pd.read_csv("data/Customer_data.csv")
df.columns = df.columns.str.strip().str.replace(r'[^\w\s]', '', regex=True).str.replace(' ', '_')

# ---- DERIVED COLUMNS ----
df['Age_Group'] = pd.cut(df['Age'], bins=[0, 25, 35, 45, 60, 100],
                         labels=['<25', '26-35', '36-45', '46-60', '60+'])
df['Spender_Type'] = pd.cut(df['Spending_Score_1100'], bins=[0, 40, 70, 100],
                            labels=['Low', 'Medium', 'High'])

# ---- SIDEBAR FILTERS ----

st.sidebar.title("🔍 Customer Filters")

gender_filter = st.sidebar.multiselect("Gender", options=df['Gender'].unique(), default=df['Gender'].unique())
profession_filter = st.sidebar.multiselect("Profession", options=df['Profession'].unique(), default=df['Profession'].unique())
age_group_filter = st.sidebar.multiselect("Age Group", options=df['Age_Group'].dropna().unique(), default=df['Age_Group'].dropna().unique())

# ---- FILTER DATA ----
df_filtered = df[
    (df['Gender'].isin(gender_filter)) &
    (df['Profession'].isin(profession_filter)) &
    (df['Age_Group'].isin(age_group_filter))
]

# ---- KPIs ----
st.title("📊 Customer Behavior Dashboard")
col1, col2, col3, col4 = st.columns(4)
col1.metric("👥 Total Customers", df_filtered['CustomerID'].nunique())
col2.metric("💰 Avg Income", f"${df_filtered['Annual_Income_'].mean():,.2f}")
col3.metric("🧾 Avg Spending Score", f"{df_filtered['Spending_Score_1100'].mean():.1f}")
col4.metric("👨‍👩‍👧‍👦 Avg Family Size", f"{df_filtered['Family_Size'].mean():.1f}")

# ---- CHARTS ----
st.markdown("## 💹 Spending Score by Age Group")
fig_age = px.bar(df_filtered, x='Age_Group', y='Spending_Score_1100', color='Gender', barmode='group')
st.plotly_chart(fig_age, use_container_width=True)

st.markdown("## 🎯 Income vs Spending Score")
fig_scatter = px.scatter(df_filtered, x='Annual_Income_', y='Spending_Score_1100', color='Profession', size='Age')
st.plotly_chart(fig_scatter, use_container_width=True)

st.markdown("## 🍰 Spender Type Breakdown")
fig_pie = px.pie(df_filtered, names='Spender_Type')
st.plotly_chart(fig_pie, use_container_width=True)

# ---- EXPORT BUTTONS ----
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

csv_data = df_filtered.to_csv(index=False).encode('utf-8')
st.download_button("⬇️ Download CSV", data=csv_data, file_name=f"filtered_customers_{timestamp}.csv", mime="text/csv")

excel_buffer = io.BytesIO()
with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
    df_filtered.to_excel(writer, index=False, sheet_name="Customers")
excel_buffer.seek(0)
st.download_button("📥 Download Excel", data=excel_buffer, file_name=f"filtered_customers_{timestamp}.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ---- TABLE ----
st.markdown("### 📋 Filtered Customer Table")
st.dataframe(df_filtered)

# ---- PDF EXPORT ----
if platform.system() == "Windows":
    config = pdfkit.configuration(wkhtmltopdf=r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe")
else:
    config = None

st.markdown("### 📄 Export Full Dashboard Report")
generate = st.button("🖨️ Generate PDF Report")

if generate:
    # Save images temporarily
    os.makedirs("images", exist_ok=True)
    fig_age_path = f"images/fig_age_{timestamp}.png"
    fig_scatter_path = f"images/fig_scatter_{timestamp}.png"
    fig_pie_path = f"images/fig_pie_{timestamp}.png"

    fig_age.write_image(fig_age_path, width=800, height=400)
    fig_scatter.write_image(fig_scatter_path, width=800, height=400)
    fig_pie.write_image(fig_pie_path, width=400, height=400)

    # HTML context
    context = {
        "total_customers": df_filtered['CustomerID'].nunique(),
        "avg_income": f"${df_filtered['Annual_Income_'].mean():,.2f}",
        "avg_score": f"{df_filtered['Spending_Score_1100'].mean():.1f}",
        "avg_family": f"{df_filtered['Family_Size'].mean():.1f}",
        "df": df_filtered,
        "fig_age_path": Path(fig_age_path).resolve().as_uri(),
        "fig_scatter_path": Path(fig_scatter_path).resolve().as_uri(),
        "fig_pie_path": Path(fig_pie_path).resolve().as_uri(),
        "report_time": report_time
       
    }

    # Load template
    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template("report.html")
    html_out = template.render(context)

    # Generate PDF
    pdf_file = f"dashboard_report_{timestamp}.pdf"
    pdfkit.from_string(html_out, pdf_file, configuration=config, options={"enable-local-file-access": ""})

    with open(pdf_file, "rb") as f:
        st.success("✅ PDF report generated successfully!")
        st.download_button("📥 Download Full Dashboard PDF", data=f, file_name=pdf_file, mime="application/pdf")

    # Optional toast effect
    st.toast("📄 Report Ready!", icon="✅")
