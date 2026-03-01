import streamlit as st
import simpy
import random
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import pandas as pd
from dataclasses import dataclass
from typing import List

# ─────────────────────────────────────────────
#  PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="DES · Piket Kantin IT Del",
    page_icon="🍱",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
#  SIMULATION ENGINE
# ─────────────────────────────────────────────
@dataclass
class Config:
    NUM_MEJA: int = 60
    MAHASISWA_PER_MEJA: int = 6
    NUM_PETUGAS_LAUK: int = 7
    NUM_PETUGAS_ANGKAT: int = 6
    NUM_PETUGAS_NASI: int = 7
    OMPRENG_PER_TRIP: int = 7
    MIN_LAUK: float = 0.5
    MAX_LAUK: float = 1.0
    MIN_ANGKAT: float = 0.33
    MAX_ANGKAT: float = 1.0
    MIN_NASI: float = 0.5
    MAX_NASI: float = 1.0
    START_HOUR: int = 7
    START_MINUTE: int = 0
    RANDOM_SEED: int = 42

    @property
    def NUM_OMPRENG(self) -> int:
        return self.NUM_MEJA * self.MAHASISWA_PER_MEJA


class PiketKantinDES:
    def __init__(self, config: Config):
        self.config = config
        self.env = simpy.Environment()
        self.staff_lauk  = simpy.Resource(self.env, capacity=config.NUM_PETUGAS_LAUK)
        self.staff_nasi  = simpy.Resource(self.env, capacity=config.NUM_PETUGAS_NASI)
        self.data_ompreng: List[dict] = []
        self.waktu_mulai  = datetime(2024, 1, 1, config.START_HOUR, config.START_MINUTE)
        self.antrian_angkat = simpy.Container(self.env, capacity=99999, init=0)
        self.angkat_events: dict = {}
        self.trip_log: List[dict] = []
        random.seed(config.RANDOM_SEED)
        np.random.seed(config.RANDOM_SEED)

    def waktu_ke_jam(self, t: float) -> datetime:
        return self.waktu_mulai + timedelta(minutes=t)

    def petugas_angkat_loop(self, petugas_id: int):
        BATCH = self.config.OMPRENG_PER_TRIP
        trip_num = 0
        while True:
            yield self.antrian_angkat.get(1)
            extra = min(self.antrian_angkat.level, BATCH - 1)
            if extra > 0:
                yield self.antrian_angkat.get(extra)
            batch_size = 1 + extra

            t_trip_mulai  = self.env.now
            durasi_angkat = random.uniform(self.config.MIN_ANGKAT, self.config.MAX_ANGKAT)
            yield self.env.timeout(durasi_angkat)
            t_trip_selesai = self.env.now

            sisa = batch_size
            for oid, info in list(self.angkat_events.items()):
                if sisa == 0:
                    break
                if not info['event'].triggered:
                    info['durasi']  = durasi_angkat
                    info['t_tiba'] = t_trip_selesai
                    info['event'].succeed()
                    sisa -= 1

            self.trip_log.append({
                'petugas_id'  : petugas_id,
                'trip'        : trip_num,
                'batch_size'  : batch_size,
                'durasi'      : durasi_angkat,
                't_mulai'     : t_trip_mulai,
                't_selesai'   : t_trip_selesai,
            })
            trip_num += 1

    def proses_ompreng(self, ompreng_id: int):
        t_start = self.env.now

        with self.staff_lauk.request() as req:
            yield req
            t_lauk_mulai   = self.env.now
            durasi_lauk    = random.uniform(self.config.MIN_LAUK, self.config.MAX_LAUK)
            yield self.env.timeout(durasi_lauk)
            t_lauk_selesai = self.env.now

        t_antri_mulai = self.env.now
        ev = self.env.event()
        self.angkat_events[ompreng_id] = {'event': ev, 'durasi': 0.0, 't_tiba': 0.0}
        yield self.antrian_angkat.put(1)
        yield ev
        durasi_angkat       = self.angkat_events[ompreng_id]['durasi']
        t_angkat_selesai    = self.angkat_events[ompreng_id]['t_tiba']
        waktu_tunggu_angkat = t_angkat_selesai - t_antri_mulai

        with self.staff_nasi.request() as req:
            yield req
            t_nasi_mulai   = self.env.now
            durasi_nasi    = random.uniform(self.config.MIN_NASI, self.config.MAX_NASI)
            yield self.env.timeout(durasi_nasi)
            t_nasi_selesai = self.env.now

        self.data_ompreng.append({
            'ompreng_id'        : ompreng_id,
            'meja'              : ompreng_id // self.config.MAHASISWA_PER_MEJA + 1,
            't_mulai'           : t_start,
            't_selesai'         : t_nasi_selesai,
            'durasi_lauk'       : durasi_lauk,
            'durasi_angkat'     : durasi_angkat,
            'tunggu_angkat'     : waktu_tunggu_angkat,
            'durasi_nasi'       : durasi_nasi,
            'total_waktu'       : t_nasi_selesai - t_start,
            'jam_selesai'       : self.waktu_ke_jam(t_nasi_selesai),
        })

    def run_simulation(self):
        for p in range(self.config.NUM_PETUGAS_ANGKAT):
            self.env.process(self.petugas_angkat_loop(p))
        for i in range(self.config.NUM_OMPRENG):
            self.env.process(self.proses_ompreng(i))
        self.env.run()
        return self.analyze_results()

    def analyze_results(self):
        if not self.data_ompreng:
            return None, None
        df = pd.DataFrame(self.data_ompreng)
        T  = df['t_selesai'].max()
        r  = {
            'total_ompreng'         : len(df),
            'total_meja'            : self.config.NUM_MEJA,
            'waktu_selesai_menit'   : T,
            'jam_selesai'           : self.waktu_ke_jam(T),
            'avg_durasi_lauk'       : df['durasi_lauk'].mean(),
            'avg_durasi_angkat'     : df['durasi_angkat'].mean(),
            'avg_tunggu_angkat'     : df['tunggu_angkat'].mean(),
            'avg_durasi_nasi'       : df['durasi_nasi'].mean(),
            'avg_total_waktu'       : df['total_waktu'].mean(),
            'max_total_waktu'       : df['total_waktu'].max(),
            'utilisasi_lauk'        : df['durasi_lauk'].sum()  / (T * self.config.NUM_PETUGAS_LAUK)   * 100,
            'utilisasi_angkat'      : sum(t['durasi'] for t in self.trip_log) / (T * self.config.NUM_PETUGAS_ANGKAT) * 100 if self.trip_log else 0,
            'utilisasi_nasi'        : df['durasi_nasi'].sum()  / (T * self.config.NUM_PETUGAS_NASI)   * 100,
            'total_trip'            : len(self.trip_log),
            'avg_batch_size'        : sum(t['batch_size'] for t in self.trip_log) / len(self.trip_log) if self.trip_log else 0,
        }
        return r, df


# ─────────────────────────────────────────────
#  SENSITIVITY
# ─────────────────────────────────────────────
def run_sensitivity(meja=60, mhs=6):
    scenarios = [
        {"label": "Baseline · 7-6-7",      "lauk": 7,  "angkat": 6,  "nasi": 7},
        {"label": "Fokus Lauk · 10-5-5",   "lauk": 10, "angkat": 5,  "nasi": 5},
        {"label": "Fokus Angkat · 5-10-5", "lauk": 5,  "angkat": 10, "nasi": 5},
        {"label": "Fokus Nasi · 5-5-10",   "lauk": 5,  "angkat": 5,  "nasi": 10},
        {"label": "Merata · 7-7-6",        "lauk": 7,  "angkat": 7,  "nasi": 6},
        {"label": "Minimal Angkat · 8-4-8","lauk": 8,  "angkat": 4,  "nasi": 8},
    ]
    rows = []
    for sc in scenarios:
        cfg = Config(NUM_MEJA=meja, MAHASISWA_PER_MEJA=mhs,
                     NUM_PETUGAS_LAUK=sc["lauk"], NUM_PETUGAS_ANGKAT=sc["angkat"],
                     NUM_PETUGAS_NASI=sc["nasi"])
        m = PiketKantinDES(cfg)
        r, _ = m.run_simulation()
        if r:
            rows.append({
                'Skenario'     : sc["label"],
                'Lauk'         : sc["lauk"],
                'Angkat'       : sc["angkat"],
                'Nasi'         : sc["nasi"],
                'Σ Petugas'    : sc["lauk"] + sc["angkat"] + sc["nasi"],
                'Jam Selesai'  : r['jam_selesai'].strftime('%H:%M'),
                'Durasi (mnt)' : round(r['waktu_selesai_menit'], 2),
                'Avg/Ompreng'  : round(r['avg_total_waktu'], 3),
                'Util Lauk %'  : round(r['utilisasi_lauk'], 1),
                'Util Angkat %': round(r['utilisasi_angkat'], 1),
                'Util Nasi %'  : round(r['utilisasi_nasi'], 1),
            })
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────
#  CHARTS — Warm Forest Theme
# ─────────────────────────────────────────────
def make_charts(df, model, results):
    cfg = model.config
    T   = df['t_selesai'].max()

    BG    = '#0f1a0e'
    PANEL = '#111e0f'
    GRID  = '#1a2c18'
    TEXT  = '#3a5030'
    LITE  = '#7a8c6a'
    C1, C2, C3 = '#c8a84b', '#6abf69', '#7eb8c9'
    WARN, DANG = '#e07b39', '#d65050'

    plt.rcParams.update({
        'figure.facecolor': BG, 'axes.facecolor': PANEL,
        'axes.edgecolor': GRID, 'axes.labelcolor': LITE,
        'xtick.color': TEXT, 'ytick.color': TEXT,
        'text.color': LITE, 'grid.color': GRID, 'grid.linewidth': 0.7,
        'font.family': 'serif',
    })

    fig = plt.figure(figsize=(16, 10), facecolor=BG)
    gs  = gridspec.GridSpec(2, 3, figure=fig,
                             left=0.06, right=0.97,
                             top=0.91, bottom=0.08,
                             hspace=0.50, wspace=0.35)

    fig.text(0.06, 0.965, 'S I M U L A T I O N   A N A L Y T I C S   R E P O R T',
             fontsize=7.5, color=TEXT, fontfamily='monospace', ha='left', va='top')
    fig.text(0.97, 0.965,
             f"n={len(df)} ompreng · seed={cfg.RANDOM_SEED} · T={T:.1f} mnt",
             fontsize=7, color=TEXT, fontfamily='monospace', ha='right', va='top')

    util_vals = [
        df['durasi_lauk'].sum()  / (T * cfg.NUM_PETUGAS_LAUK)  * 100,
        results['utilisasi_angkat'],
        df['durasi_nasi'].sum()  / (T * cfg.NUM_PETUGAS_NASI)  * 100,
    ]

    def sa(ax, title, xlabel='', ylabel=''):
        ax.set_facecolor(PANEL)
        for sp in ax.spines.values():
            sp.set_color(GRID); sp.set_linewidth(0.7)
        ax.grid(True, color=GRID, linewidth=0.7)
        ax.set_title(title, fontsize=8, color='#4a5e3a', pad=9,
                     fontfamily='monospace', loc='left')
        if xlabel: ax.set_xlabel(xlabel, fontsize=7.5, labelpad=5)
        if ylabel: ax.set_ylabel(ylabel, fontsize=7.5, labelpad=5)
        ax.tick_params(labelsize=7, length=3)

    # ① Histogram
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.hist(df['total_waktu'], bins=28, color=C1, alpha=0.15, edgecolor='none')
    ax1.hist(df['total_waktu'], bins=28, histtype='step', edgecolor=C1, linewidth=0.7, alpha=0.7)
    mv = df['total_waktu'].mean()
    ax1.axvline(mv, color=C1, linewidth=1.4, linestyle='--', alpha=0.85)
    ylim = ax1.get_ylim()
    ax1.text(mv + 0.05, ylim[1] * 0.88, f'μ = {mv:.2f}', fontsize=7, color=C1, fontfamily='monospace')
    sa(ax1, '01 / DISTRIBUSI WAKTU', 'menit', 'frekuensi')

    # ② Stacked bar
    ax2 = fig.add_subplot(gs[0, 1])
    avg_l = df['durasi_lauk'].mean()
    avg_a = df['durasi_angkat'].mean()
    avg_n = df['durasi_nasi'].mean()
    bw = 0.32
    ax2.bar(0, avg_l, bw, color=C1, alpha=0.85, label='Isi Lauk')
    ax2.bar(0, avg_a, bw, bottom=avg_l, color=C2, alpha=0.85, label='Angkat')
    ax2.bar(0, avg_n, bw, bottom=avg_l + avg_a, color=C3, alpha=0.85, label='Tambah Nasi')
    ax2.set_xticks([])
    ax2.legend(fontsize=7.5, framealpha=0, labelcolor=LITE)
    total_avg = avg_l + avg_a + avg_n
    ax2.text(0, total_avg + 0.03, f'{total_avg:.2f} mnt',
             ha='center', fontsize=8, color='#c8d4b0', fontweight='bold', fontfamily='monospace')
    sa(ax2, '02 / RATA-RATA DURASI / TAHAP', ylabel='menit')

    # ③ Scatter timeline
    ax3 = fig.add_subplot(gs[0, 2])
    sc3 = ax3.scatter(df['ompreng_id'], df['t_selesai'],
                      c=df['total_waktu'], cmap='YlOrBr', s=5, alpha=0.7, linewidths=0)
    cb = fig.colorbar(sc3, ax=ax3, pad=0.02, fraction=0.04)
    cb.ax.tick_params(labelsize=6.5, colors=TEXT)
    cb.set_label('total waktu (mnt)', fontsize=7, color=TEXT)
    sa(ax3, '03 / TIMELINE PENYELESAIAN', 'ID Ompreng', 'waktu selesai (mnt)')

    # ④ Utilisasi
    ax4 = fig.add_subplot(gs[1, 0])
    labels_u = ['Isi Lauk', 'Angkat\nOmpreng', 'Tambah\nNasi']
    colors_u  = [C1, C2, C3]
    y_pos     = [2, 1, 0]
    for y, val, color in zip(y_pos, util_vals, colors_u):
        ax4.barh(y, 100, height=0.42, color=GRID, alpha=1, zorder=1)
        ax4.barh(y, min(val, 100), height=0.42, color=color, alpha=0.82, zorder=2)
        ax4.text(min(val, 100) + 0.8, y, f'{val:.1f}%',
                 va='center', fontsize=7.5, color=color, fontfamily='monospace', fontweight='bold')
    ax4.axvline(100, color=DANG, linewidth=0.9, linestyle='--', alpha=0.5)
    ax4.set_xlim(0, 114)
    ax4.set_yticks(y_pos)
    ax4.set_yticklabels(['Nasi', 'Angkat', 'Lauk'], fontsize=8)
    sa(ax4, '04 / UTILISASI PETUGAS', 'utilisasi (%)')

    # ⑤ Avg waktu per meja
    ax5 = fig.add_subplot(gs[1, 1])
    mg = df.groupby('meja')['total_waktu'].mean().reset_index()
    ax5.fill_between(mg['meja'], mg['total_waktu'], alpha=0.12, color=C2)
    ax5.plot(mg['meja'], mg['total_waktu'], color=C2, linewidth=1.3, alpha=0.9)
    ax5.axhline(mg['total_waktu'].mean(), color=C2, linestyle='--', linewidth=0.8, alpha=0.45)
    sa(ax5, '05 / AVG WAKTU PER MEJA', 'nomor meja', 'rata-rata waktu (mnt)')

    # ⑥ Cumulative throughput
    ax6 = fig.add_subplot(gs[1, 2])
    ds  = df.sort_values('t_selesai')
    ax6.fill_between(ds['t_selesai'], range(1, len(ds) + 1), alpha=0.1, color=C3)
    ax6.plot(ds['t_selesai'], range(1, len(ds) + 1), color=C3, linewidth=1.5)
    ideal_x = np.linspace(0, T, 100)
    ideal_y = ideal_x / T * len(df)
    ax6.plot(ideal_x, ideal_y, color=WARN, linewidth=0.9, linestyle=':', alpha=0.6, label='linear ideal')
    ax6.legend(fontsize=7, framealpha=0, labelcolor=LITE)
    sa(ax6, '06 / CUMULATIVE THROUGHPUT', 'waktu (mnt)', 'ompreng selesai')

    return fig


# ─────────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div class="sb-brand">
        <div class="sb-brand-title">Piket Kantin<br>IT Del</div>
        <div class="sb-brand-sub">DES · SimPy Engine</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<span class="sb-section">🍽  Kapasitas Kantin</span>', unsafe_allow_html=True)
    num_meja     = st.slider("Jumlah Meja",      10, 120, 60, 5)
    mhs_per_meja = st.slider("Mahasiswa / Meja",  1,  10,  6)
    st.caption(f"→ Total ompreng: **{num_meja * mhs_per_meja}**")

    st.markdown('<div class="sb-div"></div>', unsafe_allow_html=True)
    st.markdown('<span class="sb-section">👷  Alokasi Petugas</span>', unsafe_allow_html=True)
    num_lauk   = st.slider("Isi Lauk",       1, 15, 7)
    num_angkat = st.slider("Angkat Ompreng", 1, 15, 6)
    num_nasi   = st.slider("Tambah Nasi",    1, 15, 7)

    st.markdown('<div class="sb-div"></div>', unsafe_allow_html=True)
    st.markdown('<span class="sb-section">📦  Kapasitas Angkut</span>', unsafe_allow_html=True)
    ompreng_per_trip = st.slider("Ompreng per Trip (1 petugas)", min_value=1, max_value=15, value=7)
    st.caption(f"→ 1 petugas angkat bawa **{ompreng_per_trip}** ompreng sekaligus")

    total_ptgs = num_lauk + num_angkat + num_nasi
    badge_cls  = "ok" if total_ptgs == 20 else ("warn" if total_ptgs < 20 else "over")
    badge_icon = "✓" if total_ptgs == 20 else ("↓" if total_ptgs < 20 else "↑")
    st.markdown(f"""
    <div class="total-badge {badge_cls}">
        {badge_icon}&nbsp; {total_ptgs} petugas
        {"· referensi ✓" if total_ptgs == 20 else "· target: 20"}
    </div>""", unsafe_allow_html=True)

    st.markdown('<div class="sb-div"></div>', unsafe_allow_html=True)
    st.markdown('<span class="sb-section">⏱  Distribusi Waktu (mnt)</span>', unsafe_allow_html=True)
    with st.expander("Isi Lauk"):
        min_lauk = st.number_input("Min", value=0.5,  step=0.05, key="ml", format="%.2f")
        max_lauk = st.number_input("Max", value=1.0,  step=0.05, key="xl", format="%.2f")
    with st.expander("Angkat Ompreng"):
        min_angkat = st.number_input("Min", value=0.33, step=0.05, key="ma", format="%.2f")
        max_angkat = st.number_input("Max", value=1.0,  step=0.05, key="xa", format="%.2f")
    with st.expander("Tambah Nasi"):
        min_nasi = st.number_input("Min", value=0.5,  step=0.05, key="mn", format="%.2f")
        max_nasi = st.number_input("Max", value=1.0,  step=0.05, key="xn", format="%.2f")

    st.markdown('<div class="sb-div"></div>', unsafe_allow_html=True)
    st.markdown('<span class="sb-section">⚙  Lainnya</span>', unsafe_allow_html=True)
    seed = st.number_input("Random Seed", value=42, step=1)

    st.markdown("<br>", unsafe_allow_html=True)
    run_btn = st.button("▶  JALANKAN SIMULASI")

# ── RUN ──
if run_btn or 'sim_results' not in st.session_state:
    with st.spinner("Menjalankan simulasi DES…"):
        cfg = Config(
            NUM_MEJA=num_meja, MAHASISWA_PER_MEJA=mhs_per_meja,
            NUM_PETUGAS_LAUK=num_lauk, NUM_PETUGAS_ANGKAT=num_angkat, NUM_PETUGAS_NASI=num_nasi,
            OMPRENG_PER_TRIP=ompreng_per_trip,
            MIN_LAUK=min_lauk, MAX_LAUK=max_lauk,
            MIN_ANGKAT=min_angkat, MAX_ANGKAT=max_angkat,
            MIN_NASI=min_nasi, MAX_NASI=max_nasi,
            RANDOM_SEED=int(seed),
        )
        model = PiketKantinDES(cfg)
        results, df = model.run_simulation()
        st.session_state.update({'sim_results': results, 'sim_df': df, 'sim_model': model})

results = st.session_state.get('sim_results')
df      = st.session_state.get('sim_df')
model   = st.session_state.get('sim_model')

if results and df is not None:
    cfg = model.config

    jam_str = results['jam_selesai'].strftime('%H:%M')
    dur_str = f"{results['waktu_selesai_menit']:.1f}"
    avg_str = f"{results['avg_total_waktu']:.2f}"

    st.markdown("<br>", unsafe_allow_html=True)
    sec_head("Visualisasi Analitik Simulasi")
    with st.spinner("Merender grafik…"):
        fig = make_charts(df, model, results)
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)

    st.markdown("<br>", unsafe_allow_html=True)
    sec_head("Analisis Sensitivitas Skenario")
    with st.expander("▸  Tampilkan perbandingan 6 skenario alokasi petugas", expanded=False):
        with st.spinner("Menjalankan 6 skenario…"):
            sens_df = run_sensitivity(meja=num_meja, mhs=mhs_per_meja)
        st.dataframe(
            sens_df.style
                .background_gradient(subset=['Durasi (mnt)', 'Avg/Ompreng'], cmap='YlOrBr')
                .background_gradient(subset=['Util Lauk %', 'Util Angkat %', 'Util Nasi %'], cmap='Greens')
                .format({'Durasi (mnt)': '{:.2f}', 'Avg/Ompreng': '{:.3f}',
                         'Util Lauk %': '{:.1f}', 'Util Angkat %': '{:.1f}', 'Util Nasi %': '{:.1f}'}),
            use_container_width=True, hide_index=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)
    sec_head("Data Mentah Simulasi")
    with st.expander("▸  Lihat tabel data per ompreng", expanded=False):
        disp = df[['ompreng_id','meja','durasi_lauk','durasi_angkat','durasi_nasi','total_waktu','jam_selesai']].copy()
        disp.columns = ['ID','Meja','Lauk (mnt)','Angkat (mnt)','Nasi (mnt)','Total (mnt)','Jam Selesai']
        disp['Jam Selesai'] = disp['Jam Selesai'].apply(lambda x: x.strftime('%H:%M:%S'))
        for c in ['Lauk (mnt)','Angkat (mnt)','Nasi (mnt)','Total (mnt)']:
            disp[c] = disp[c].round(4)
        st.dataframe(disp, use_container_width=True, hide_index=True)

# ── FOOTER ──
st.markdown("""
<div class="footer">
    Discrete Event Simulation &nbsp;·&nbsp; SimPy &nbsp;·&nbsp;
    Institut Teknologi Del &nbsp;·&nbsp; 2024–2026
</div>
""", unsafe_allow_html=True)