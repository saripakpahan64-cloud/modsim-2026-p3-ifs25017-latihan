import streamlit as st
import random
import heapq

st.title("Simulasi Sistem Piket IT Del")

# ===============================
# PARAMETER INPUT
# ===============================
JUMLAH_MEJA = st.number_input("Jumlah Meja", value=60)
OMPRENG_PER_MEJA = st.number_input("Ompreng per Meja", value=3)

TOTAL_OMPRENG = JUMLAH_MEJA * OMPRENG_PER_MEJA

PETUGAS_LAUK = 2
PETUGAS_ANGKAT = 2
PETUGAS_NASI = 3

# ===============================
# FUNGSI WAKTU ACAK
# ===============================
def waktu_lauk():
    return random.randint(30, 60)

def waktu_angkat():
    return random.randint(20, 60)

def waktu_nasi():
    return random.randint(30, 60)

def kapasitas_angkat():
    return random.randint(4, 7)

# ===============================
# TOMBOL SIMULASI
# ===============================
if st.button("Jalankan Simulasi"):

    current_time = 0
    event_queue = []

    antrian_lauk = TOTAL_OMPRENG
    antrian_angkat = 0
    antrian_nasi = 0
    selesai = 0

    petugas_lauk = 0
    petugas_angkat = 0
    petugas_nasi = 0

    def schedule_event(waktu, tipe, jumlah=1):
        heapq.heappush(event_queue, (waktu, tipe, jumlah))

    # Aktifkan petugas lauk awal
    while petugas_lauk < PETUGAS_LAUK and antrian_lauk > 0:
        antrian_lauk -= 1
        petugas_lauk += 1
        schedule_event(current_time + waktu_lauk(), "lauk_selesai")

    while event_queue:
        waktu_event, tipe_event, jumlah_event = heapq.heappop(event_queue)
        current_time = waktu_event

        if tipe_event == "lauk_selesai":
            petugas_lauk -= 1
            antrian_angkat += 1

            if antrian_lauk > 0:
                antrian_lauk -= 1
                petugas_lauk += 1
                schedule_event(current_time + waktu_lauk(), "lauk_selesai")

            if antrian_angkat >= 4 and petugas_angkat < PETUGAS_ANGKAT:
                angkut = min(kapasitas_angkat(), antrian_angkat)
                antrian_angkat -= angkut
                petugas_angkat += 1
                schedule_event(current_time + waktu_angkat(), "angkat_selesai", angkut)

        elif tipe_event == "angkat_selesai":
            petugas_angkat -= 1
            antrian_nasi += jumlah_event

            while petugas_nasi < PETUGAS_NASI and antrian_nasi > 0:
                antrian_nasi -= 1
                petugas_nasi += 1
                schedule_event(current_time + waktu_nasi(), "nasi_selesai")

        elif tipe_event == "nasi_selesai":
            petugas_nasi -= 1
            selesai += 1

            if antrian_nasi > 0:
                antrian_nasi -= 1
                petugas_nasi += 1
                schedule_event(current_time + waktu_nasi(), "nasi_selesai")

        if selesai >= TOTAL_OMPRENG:
            break

    # ===============================
    # HASIL
    # ===============================
    jam_mulai = 7
    jam_selesai = jam_mulai + current_time // 3600
    menit_selesai = (current_time % 3600) // 60
    detik_selesai = current_time % 60

    st.success("Simulasi Selesai!")

    st.write("Total Ompreng:", TOTAL_OMPRENG)
    st.write("Total Waktu (detik):", current_time)
    st.write(f"Perkiraan selesai pukul {jam_selesai:02}:{menit_selesai:02}:{detik_selesai:02}")