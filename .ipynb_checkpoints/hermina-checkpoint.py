import streamlit as st
import simpy
import random
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go

# =====================================================
# CONFIG PAGE
# =====================================================
st.set_page_config(
    page_title="Dashboard Simulasi Piket Ompreng",
    page_icon="🍱",
    layout="wide"
)

START_TIME = datetime(2024, 1, 1, 7, 0, 0)
random.seed(42)

# =====================================================
# MODEL SIMULASI
# =====================================================
class SistemPiket:
    def __init__(self, env, lauk, angkut, nasi):
        self.env = env
        self.lauk = simpy.Resource(env, lauk)
        self.angkut = simpy.Resource(env, angkut)
        self.nasi = simpy.Resource(env, nasi)
        self.data = []

    def proses(self, id_ompreng):
        mulai = self.env.now

        # ======================
        # 1. Isi Lauk
        # ======================
        with self.lauk.request() as req:
            yield req
            t = random.uniform(0.5, 1.0)
            yield self.env.timeout(t)

        # ======================
        # 2. Angkut
        # ======================
        with self.angkut.request() as req:
            yield req
            batch = random.randint(4, 7)
            t = random.uniform(0.33, 1.0)
            yield self.env.timeout(t)

        # ======================
        # 3. Isi Nasi
        # ======================
        with self.nasi.request() as req:
            yield req
            t = random.uniform(0.5, 1.0)
            yield self.env.timeout(t)

        selesai = self.env.now

        self.data.append({
            "ID": id_ompreng,
            "Mulai": mulai,
            "Selesai": selesai,
            "Durasi": selesai - mulai,
            "Jam Selesai": START_TIME + timedelta(minutes=selesai)
        })


def run_simulasi(total, lauk, angkut, nasi):
    env = simpy.Environment()
    model = SistemPiket(env, lauk, angkut, nasi)

    for i in range(total):
        env.process(model.proses(i))

    env.run()

    return pd.DataFrame(model.data)


# =====================================================
# SIDEBAR
# =====================================================
with st.sidebar:
    st.title("⚙️ Parameter")

    meja = st.number_input("Jumlah Meja", 1, 200, 60)
    mhs = st.number_input("Mahasiswa / Meja", 1, 5, 3)

    total = meja * mhs
    st.markdown(f"### Total Ompreng: **{total}**")

    st.divider()

    lauk = st.number_input("Petugas Isi Lauk", 1, 10, 3)
    angkut = st.number_input("Petugas Angkut", 1, 10, 2)
    nasi = st.number_input("Petugas Isi Nasi", 1, 10, 2)

    st.divider()

    run = st.button("🚀 Jalankan Simulasi", use_container_width=True)

# =====================================================
# HEADER
# =====================================================
st.title("🍱 Dashboard Simulasi Piket Ompreng")
st.caption("Discrete Event Simulation — Sistem Piket Kantin")

st.divider()

# =====================================================
# SIMULASI
# =====================================================
if run:

    with st.spinner("Menjalankan simulasi..."):
        df = run_simulasi(total, lauk, angkut, nasi)

    st.success("Simulasi selesai ✅")

    # =================================================
    # KPI METRICS
    # =================================================
    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Total Ompreng", len(df))
    c2.metric("Waktu Selesai Terakhir",
              f"{df['Selesai'].max():.2f} menit")
    c3.metric("Rata-rata Durasi",
              f"{df['Durasi'].mean():.2f} menit")
    c4.metric("Durasi Tercepat",
              f"{df['Durasi'].min():.2f} menit")

    st.divider()

    # =================================================
    # CHART ROW 1
    # =================================================
    col1, col2 = st.columns(2)

    # Histogram
    with col1:
        fig1 = px.histogram(
            df,
            x="Durasi",
            nbins=40,
            title="Distribusi Waktu Proses",
            template="plotly_white"
        )
        st.plotly_chart(fig1, use_container_width=True)

    # Timeline Scatter
    with col2:
        fig2 = px.scatter(
            df,
            x="Selesai",
            y="ID",
            title="Timeline Penyelesaian",
            template="plotly_white"
        )
        st.plotly_chart(fig2, use_container_width=True)

    # =================================================
    # CHART ROW 2
    # =================================================
    col3, col4 = st.columns(2)

    # Boxplot
    with col3:
        fig3 = px.box(
            df,
            y="Durasi",
            title="Boxplot Durasi Proses",
            template="plotly_white"
        )
        st.plotly_chart(fig3, use_container_width=True)

    # Penyelesaian per jam
    with col4:
        df["Jam"] = df["Jam Selesai"].dt.hour
        hourly = df.groupby("Jam").size().reset_index(name="Jumlah")

        fig4 = px.bar(
            hourly,
            x="Jam",
            y="Jumlah",
            title="Distribusi Penyelesaian per Jam",
            template="plotly_white"
        )
        st.plotly_chart(fig4, use_container_width=True)

    # =================================================
    # DATA TABLE
    # =================================================
    st.divider()
    st.subheader("📄 Data Detail Simulasi")

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )

    # Download
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "📥 Download CSV",
        csv,
        "data_simulasi_ompreng.csv",
        "text/csv",
        use_container_width=True
    )

else:
    st.info("Atur parameter di kiri lalu klik **Jalankan Simulasi** 🚀")

# =====================================================
# FOOTER
# =====================================================
st.divider()
st.caption(
    "MODSIM DES • Sistem Piket Ompreng • Streamlit Dashboard"
)
