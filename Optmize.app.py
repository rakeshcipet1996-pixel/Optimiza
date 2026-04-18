import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from rectpack import newPacker
import zipfile
import os
import qrcode

from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet

st.set_page_config(layout="wide")
st.title("🏭 Manufacturing Optimization Tool")

uploaded_file = st.file_uploader("Upload Excel/CSV", type=["csv", "xlsx"])

if uploaded_file:
    df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith(".csv") else pd.read_excel(uploaded_file)

    st.subheader("📊 Data Preview")
    st.dataframe(df.head())

    # Sidebar settings
    st.sidebar.header("⚙️ Settings")
    sheet_length = st.sidebar.number_input("Sheet Length", value=2440)
    sheet_width = st.sidebar.number_input("Sheet Width", value=1220)
    blade = st.sidebar.number_input("Blade Thickness", value=3)
    rotation = st.sidebar.checkbox("Allow Rotation", True)

    if st.button("🚀 Run Tool"):

        df = df.fillna("Unknown")

        # -------- CLEAN COLUMN NAMES --------
df.columns = df.columns.str.strip()

# Show columns for debugging
st.write("Detected Columns:", df.columns.tolist())

# Try to auto-map columns
col_map = {}

for col in df.columns:
    c = col.lower()
    if "name" in c:
        col_map["Name"] = col
    elif "l1" in c or "length" in c:
        col_map["L1"] = col
    elif "w1" in c or "width" in c:
        col_map["W1"] = col

# Check if required columns exist
if len(col_map) < 3:
    st.error("❌ Required columns not found. Please ensure columns like Name, Length, Width exist.")
    st.stop()

# Rename columns safely
df = df.rename(columns={
    col_map["Name"]: "Name",
    col_map["L1"]: "L1",
    col_map["W1"]: "W1"
})

# -------- BOM --------
bom = df.groupby(["Name", "L1", "W1"]).size().reset_index(name="Qty")
st.subheader("🧾 BOM")
st.dataframe(bom)

        # -------- CUTRITE EXPORT --------
        cutrite = bom.copy()
        cutrite["Material"] = "Board"
        cutrite["Grain"] = "Yes"
        cutrite.to_csv("cutrite.csv", index=False)

        # -------- CUTTING LAYOUT --------
        packer = newPacker(rotation=rotation)

        for _, row in df.iterrows():
            try:
                packer.add_rect(int(row["L1"]) + blade, int(row["W1"]) + blade)
            except:
                continue

        for _ in range(50):
            packer.add_bin(sheet_length, sheet_width)

        packer.pack()

        fig, ax = plt.subplots()
        ax.set_xlim(0, sheet_length)
        ax.set_ylim(0, sheet_width)

        for abin in packer:
            ax.add_patch(plt.Rectangle((0, 0), sheet_length, sheet_width, fill=False))

            for rect in abin:
                ax.add_patch(plt.Rectangle((rect.x, rect.y), rect.width, rect.height))
                ax.text(rect.x, rect.y, f"{rect.width}x{rect.height}", fontsize=6)

        ax.invert_yaxis()
        st.subheader("✂️ Layout")
        st.pyplot(fig)

        # -------- PDF --------
        def generate_pdf():
            doc = SimpleDocTemplate("report.pdf", pagesize=A4)
            elements = []
            styles = getSampleStyleSheet()

            elements.append(Paragraph("Cutting Report", styles['Title']))
            elements.append(Spacer(1, 10))

            data = [["Name", "L", "W", "Qty"]]
            for _, r in bom.iterrows():
                data.append([r["Name"], r["L1"], r["W1"], r["Qty"]])

            table = Table(data)
            table.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black)]))

            elements.append(table)
            doc.build(elements)

        generate_pdf()

        # -------- QR LABELS --------
        def generate_labels():
            doc = SimpleDocTemplate("labels.pdf", pagesize=A4)
            elements = []
            styles = getSampleStyleSheet()

            for i, row in bom.iterrows():
                for q in range(int(row["Qty"])):
                    qr = qrcode.make(f"{row['Name']} {row['L1']}x{row['W1']}")
                    path = f"qr_{i}_{q}.png"
                    qr.save(path)

                    elements.append(Paragraph(f"{row['Name']} {row['L1']}x{row['W1']}", styles['Normal']))
                    elements.append(Image(path, width=80, height=80))
                    elements.append(Spacer(1, 10))

            doc.build(elements)

        generate_labels()

        # -------- ZIP --------
        zip_name = "outputs.zip"
        with zipfile.ZipFile(zip_name, "w") as z:
            z.write("cutrite.csv")
            z.write("report.pdf")
            z.write("labels.pdf")

        with open(zip_name, "rb") as f:
            st.download_button("📥 Download All Outputs", f, file_name="outputs.zip")

        st.success("✅ Process completed successfully!")
