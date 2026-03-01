import simpy
import random
from datetime import datetime, timedelta

# ==========================
# PARAMETER SISTEM
# ==========================
JUMLAH_MEJA = 60
MAHASISWA_PER_MEJA = 3
TOTAL_OMPRENG = JUMLAH_MEJA * MAHASISWA_PER_MEJA

PETUGAS_LAUK = 2
PETUGAS_ANGKAT = 2
PETUGAS_NASI = 3

random.seed(42)

# ==========================
# FUNGSI JAM SELESAI
# ==========================
def hitung_jam_selesai(durasi_detik):
    jam_mulai = datetime.strptime("07:00", "%H:%M")
    jam_selesai = jam_mulai + timedelta(seconds=durasi_detik)
    return jam_selesai.strftime("%H:%M:%S")

# ==========================
# PROSES 1: ISI LAUK
# ==========================
def isi_lauk(env, ompreng_id, resource_lauk, queue_angkat):
    with resource_lauk.request() as req:
        yield req
        waktu = random.uniform(30, 60)
        yield env.timeout(waktu)
        yield queue_angkat.put(ompreng_id)

# ==========================
# PROSES 2: ANGKAT (BATCH 4–7)
# ==========================
def angkat_ompreng(env, resource_angkat, queue_angkat, queue_nasi, total_selesai):
    while total_selesai["lauk"] < TOTAL_OMPRENG or len(queue_angkat.items) > 0:
        
        if len(queue_angkat.items) == 0:
            yield env.timeout(1)
            continue
        
        batch_size = random.randint(4, 7)
        batch = []
        
        while len(batch) < batch_size and len(queue_angkat.items) > 0:
            ompreng = yield queue_angkat.get()
            batch.append(ompreng)
        
        with resource_angkat.request() as req:
            yield req
            waktu = random.uniform(20, 60)
            yield env.timeout(waktu)
            
            for item in batch:
                yield queue_nasi.put(item)

# ==========================
# PROSES 3: TAMBAH NASI
# ==========================
def tambah_nasi(env, resource_nasi, queue_nasi, selesai_counter):
    while len(selesai_counter) < TOTAL_OMPRENG:
        
        if len(queue_nasi.items) == 0:
            yield env.timeout(1)
            continue
        
        ompreng = yield queue_nasi.get()
        
        with resource_nasi.request() as req:
            yield req
            waktu = random.uniform(30, 60)
            yield env.timeout(waktu)
            selesai_counter.append(1)

# ==========================
# SIMULASI UTAMA
# ==========================
def run_simulation():
    env = simpy.Environment()

    resource_lauk = simpy.Resource(env, capacity=PETUGAS_LAUK)
    resource_angkat = simpy.Resource(env, capacity=PETUGAS_ANGKAT)
    resource_nasi = simpy.Resource(env, capacity=PETUGAS_NASI)

    queue_angkat = simpy.Store(env)
    queue_nasi = simpy.Store(env)

    selesai_counter = []
    total_selesai = {"lauk": 0}

    # Jalankan proses angkat
    for _ in range(PETUGAS_ANGKAT):
        env.process(angkat_ompreng(env, resource_angkat, queue_angkat, queue_nasi, total_selesai))

    # Jalankan proses nasi
    for _ in range(PETUGAS_NASI):
        env.process(tambah_nasi(env, resource_nasi, queue_nasi, selesai_counter))

    # Buat semua ompreng
    for i in range(TOTAL_OMPRENG):
        env.process(isi_lauk(env, i, resource_lauk, queue_angkat))
        total_selesai["lauk"] += 1

    # Jalankan sampai selesai
    env.run()

    durasi_total = env.now
    jam_selesai = hitung_jam_selesai(durasi_total)

    print("=================================")
    print("SIMULASI SISTEM PIKET IT DEL")
    print("=================================")
    print("Total Meja        :", JUMLAH_MEJA)
    print("Total Ompreng     :", TOTAL_OMPRENG)
    print("Total Petugas     :", PETUGAS_LAUK + PETUGAS_ANGKAT + PETUGAS_NASI)
    print("---------------------------------")
    print("Durasi Total      :", round(durasi_total/60, 2), "menit")
    print("Jam Mulai         : 07:00:00 WIB")
    print("Jam Selesai       :", jam_selesai, "WIB")
    print("=================================")

# ==========================
# RUN
# ==========================
run_simulation()