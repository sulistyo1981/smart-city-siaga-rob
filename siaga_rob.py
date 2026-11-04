"""
SIAGA ROB Semarang – Sistem Peringatan Dini Banjir & Rob
=========================================================
Versi script Python untuk VS Code (diadaptasi dari notebook Google Colab).

Program unggulan Gerakan Semarang SMART (Smart Environment).

PENTING: Skor risiko (Langkah 1–7) memakai DATA SIMULASI (dummy) untuk keperluan
tugas presentasi, BUKAN data resmi BMKG, BPBD, maupun Pemerintah Kota Semarang.
Langkah 8 menampilkan DATA NYATA dari open data (Open-Meteo & BMKG) sebagai
pembanding; data nyata ini tidak dipakai untuk menghitung skor.

Cara menjalankan:
    1. pip install -r requirements.txt
    2. python siaga_rob.py
Hasil:
    - Tabel dan rekap status tampil di terminal
    - Grafik tampil di jendela baru dan disimpan ke folder "hasil/"
    - Peta, notifikasi, data CSV/JSON, dan dashboard disimpan ke folder "hasil/"
    - Dashboard dibuka di browser
"""

import functools
import http.server
import json
import os
import threading
import time
import urllib.request
import webbrowser
from datetime import datetime, timedelta, timezone

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import folium

# Folder untuk menyimpan semua hasil (grafik, peta, notifikasi)
FOLDER_HASIL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hasil")
os.makedirs(FOLDER_HASIL, exist_ok=True)

# Atur tampilan tabel pandas agar rapi di terminal
pd.set_option("display.width", 120)
pd.set_option("display.max_columns", 20)


def garis(judul):
    """Mencetak judul langkah agar output terminal mudah diikuti saat rekam video."""
    print("\n" + "=" * 70)
    print(f"  {judul}")
    print("=" * 70)


# =====================================================================
# LANGKAH 1 – DATA SIMULASI 10 KECAMATAN (DUMMY, BUKAN DATA RESMI)
# =====================================================================
def siapkan_data():
    data = {
        "kecamatan": ["Semarang Utara", "Genuk", "Tugu", "Semarang Timur", "Gayamsari",
                      "Semarang Barat", "Pedurungan", "Semarang Tengah", "Candisari", "Tembalang"],
        "curah_hujan_mm":  [120, 110,  90, 100,  95,  85,  90,  80,  70,  75],   # mm/hari
        "pasang_laut_cm":  [140, 135, 120, 100,  90,  95,  60,  70,  10,   0],   # cm di atas normal
        "penurunan_tanah": [  9,   8,   6,   5,   5,   4,   4,   3,   1, 0.5],   # cm/tahun
        # Perkiraan koordinat titik tengah kecamatan (untuk peta)
        "lat": [-6.958, -6.960, -6.975, -6.975, -6.992, -6.985, -7.005, -6.980, -7.015, -7.060],
        "lon": [110.413, 110.470, 110.345, 110.435, 110.455, 110.390, 110.480, 110.418, 110.425, 110.440],
    }
    return pd.DataFrame(data)


# =====================================================================
# LANGKAH 2 – MENGHITUNG SKOR RISIKO BANJIR (0–100)
# =====================================================================
# Batas maksimum tiap indikator (nilai di atas batas dianggap risiko penuh)
BATAS_HUJAN, BATAS_PASANG, BATAS_TANAH = 150, 150, 10
# Bobot tiap indikator (total = 100%)
BOBOT_HUJAN, BOBOT_PASANG, BOBOT_TANAH = 0.40, 0.35, 0.25


def hitung_skor(hujan, pasang, tanah):
    """Skor = (40% x hujan + 35% x pasang + 25% x penurunan tanah) x 100."""
    nilai_hujan = (hujan / BATAS_HUJAN).clip(upper=1)
    nilai_pasang = (pasang / BATAS_PASANG).clip(upper=1)
    nilai_tanah = (tanah / BATAS_TANAH).clip(upper=1)
    return ((BOBOT_HUJAN * nilai_hujan +
             BOBOT_PASANG * nilai_pasang +
             BOBOT_TANAH * nilai_tanah) * 100).round(1)


# =====================================================================
# LANGKAH 3 – MENENTUKAN STATUS KECAMATAN
# =====================================================================
WARNA_STATUS = {
    "Aman":    "#2e9e44",   # hijau
    "Waspada": "#f2c200",   # kuning
    "Siaga":   "#f07c00",   # oranye
    "Awas":    "#d62828",   # merah
}


def tentukan_status(skor):
    if skor >= 80:
        return "Awas"
    elif skor >= 60:
        return "Siaga"
    elif skor >= 40:
        return "Waspada"
    return "Aman"


# =====================================================================
# LANGKAH 4 – GRAFIK SKOR RISIKO (MATPLOTLIB)
# =====================================================================
def buat_grafik(df, kolom_skor="skor_risiko", kolom_status="status",
                judul="SIAGA ROB Semarang – Skor Risiko Banjir & Rob per Kecamatan\n(DATA SIMULASI)",
                nama_file="grafik_skor_risiko.png"):
    """Grafik batang skor risiko; dipakai untuk skor simulasi (Langkah 4) dan skor nyata (Langkah 10)."""
    fig, ax = plt.subplots(figsize=(11, 6))
    urut = df.sort_values(kolom_skor)
    bar = ax.barh(urut["kecamatan"], urut[kolom_skor], color=urut[kolom_status].map(WARNA_STATUS))

    # Tulis skor dan status di ujung setiap batang
    for b, skor, status in zip(bar, urut[kolom_skor], urut[kolom_status]):
        ax.text(b.get_width() + 1, b.get_y() + b.get_height() / 2,
                f"{skor:.0f} ({status})", va="center", fontsize=10)

    # Garis batas setiap status
    for batas, label in [(40, "Waspada"), (60, "Siaga"), (80, "Awas")]:
        ax.axvline(batas, color=WARNA_STATUS[label], linestyle="--", linewidth=1, alpha=0.7)

    ax.set_title(judul, fontsize=14, fontweight="bold")
    ax.set_xlabel("Skor Risiko (0–100)")
    ax.set_xlim(0, 105)
    ax.legend(handles=[Patch(color=w, label=s) for s, w in WARNA_STATUS.items()],
              title="Status", loc="lower right")
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()

    lokasi = os.path.join(FOLDER_HASIL, nama_file)
    fig.savefig(lokasi, dpi=150)
    print(f"🖼️  Grafik disimpan: {lokasi}")
    return fig


# =====================================================================
# LANGKAH 5 – PETA INTERAKTIF (FOLIUM)
# =====================================================================
def buat_peta(df):
    # Server ubin OSM utama memblokir file HTML lokal (403), jadi dipakai ubin OSM Humanitarian
    # (OSM France) sebagai peta utama dan Esri sebagai cadangan (bisa dipilih di panel lapisan)
    peta = folium.Map(location=[-6.99, 110.42], zoom_start=12, tiles=None)
    folium.TileLayer(
        "https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png",
        attr="&copy; OpenStreetMap contributors, tiles: Humanitarian OSM Team, OSM France",
        name="Peta OSM Humanitarian",
    ).add_to(peta)
    folium.TileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
        attr="Tiles &copy; Esri",
        name="Peta Esri (cadangan)",
    ).add_to(peta)
    lapisan_risiko = folium.FeatureGroup(name="Risiko per kecamatan (simulasi)").add_to(peta)
    lapisan_posko = folium.FeatureGroup(name="Posko pengungsian (simulasi)").add_to(peta)

    for _, baris in df.iterrows():
        info = f"""
        <b>Kec. {baris['kecamatan']}</b><br>
        Status: <b style='color:{baris['warna']}'>{baris['status'].upper()}</b><br>
        Skor risiko: {baris['skor_risiko']}<br>
        <hr style='margin:4px 0'>
        Curah hujan: {baris['curah_hujan_mm']} mm<br>
        Pasang laut: {baris['pasang_laut_cm']} cm<br>
        Penurunan tanah: {baris['penurunan_tanah']} cm/tahun<br>
        <i style='font-size:10px'>Data simulasi</i>
        """
        folium.CircleMarker(
            location=[baris["lat"], baris["lon"]],
            radius=8 + baris["skor_risiko"] / 8,        # semakin berisiko, semakin besar
            color=baris["warna"], fill=True, fill_color=baris["warna"], fill_opacity=0.75,
            popup=folium.Popup(info, max_width=250),
            tooltip=f"{baris['kecamatan']} – {baris['status']}",
        ).add_to(lapisan_risiko)

    # Posko pengungsian untuk kecamatan Siaga/Awas (lokasi simulasi, sedikit ke arah darat)
    posko = df[df["status"].isin(["Siaga", "Awas"])]
    for _, baris in posko.iterrows():
        lat, lon = baris["lat"] - 0.012, baris["lon"]
        info = f"""
        <b>Posko Pengungsian Kec. {baris['kecamatan']}</b><br>
        Kapasitas: ±200 orang<br>
        Fasilitas: dapur umum, pos kesehatan<br>
        <a href='https://www.google.com/maps/dir/?api=1&destination={lat},{lon}' target='_blank'>
        🧭 Rute ke posko (Google Maps)</a><br>
        <i style='font-size:10px'>Lokasi simulasi</i>
        """
        folium.Marker(
            location=[lat, lon],
            icon=folium.Icon(color="blue", icon="home"),
            popup=folium.Popup(info, max_width=250),
            tooltip=f"Posko – {baris['kecamatan']}",
        ).add_to(lapisan_posko)
    folium.LayerControl(collapsed=False).add_to(peta)
    peta.fit_bounds(df[["lat", "lon"]].values.tolist(), padding=(30, 30))   # semua titik terlihat
    print(f"🏠 {len(posko)} posko pengungsian (simulasi) ditambahkan untuk kecamatan Siaga/Awas")

    legenda = """
    <div style="position: fixed; bottom: 30px; left: 30px; z-index: 9999;
                background: white; padding: 10px 14px; border-radius: 8px;
                box-shadow: 0 2px 6px rgba(0,0,0,.3); font-size: 13px;">
      <b>SIAGA ROB Semarang</b><br>
      <span style="color:#d62828">●</span> Awas<br>
      <span style="color:#f07c00">●</span> Siaga<br>
      <span style="color:#f2c200">●</span> Waspada<br>
      <span style="color:#2e9e44">●</span> Aman<br>
      <span style="color:#2a81cb">⌂</span> Posko pengungsian<br>
      <i style="font-size:11px">Data simulasi</i>
    </div>
    """
    peta.get_root().html.add_child(folium.Element(legenda))

    lokasi = os.path.join(FOLDER_HASIL, "peta_siaga_rob.html")
    peta.save(lokasi)
    print(f"🗺️  Peta disimpan: {lokasi}")
    return lokasi


# =====================================================================
# LANGKAH 6 – SIMULASI NOTIFIKASI KE WARGA (SIAGA / AWAS)
# =====================================================================
TINDAKAN = {
    "Siaga": "Amankan barang berharga, dokumen, dan kendaraan ke tempat lebih tinggi. Siapkan tas siaga.",
    "Awas":  "SEGERA menuju titik pengungsian terdekat. Utamakan anak-anak, lansia, dan penyandang disabilitas.",
}


def kirim_notifikasi(df):
    waktu = datetime.now(timezone(timedelta(hours=7))).strftime("%d-%m-%Y %H:%M WIB")
    wilayah_bahaya = df[df["status"].isin(["Siaga", "Awas"])]
    print(f"📡 Ditemukan {len(wilayah_bahaya)} kecamatan berstatus Siaga/Awas. Mengirim notifikasi...\n")

    kartu_html = []
    for _, baris in wilayah_bahaya.iterrows():
        ikon = "🔴" if baris["status"] == "Awas" else "🟠"

        # Versi teks untuk terminal
        print(f"{ikon} PERINGATAN {baris['status'].upper()} – SIAGA ROB SEMARANG")
        print(f"   Warga Kec. {baris['kecamatan']}, risiko banjir & rob saat ini "
              f"{baris['status'].upper()} (skor {baris['skor_risiko']}/100).")
        print(f"   Curah hujan {baris['curah_hujan_mm']} mm | Pasang laut +{baris['pasang_laut_cm']} cm")
        print(f"   👉 {TINDAKAN[baris['status']]}")
        print(f"   Darurat: 112 | {waktu} | Pesan simulasi\n")

        # Versi HTML bergaya pesan WhatsApp untuk ditampilkan di browser
        kartu_html.append(f"""
        <div style="max-width:420px; margin:12px auto; padding:12px 14px; border-radius:12px;
                    background:#e7ffdb; border-left:6px solid {baris['warna']};
                    font-family:Arial, sans-serif; font-size:14px; color:#111;">
          <b>{ikon} PERINGATAN {baris['status'].upper()} – SIAGA ROB SEMARANG</b><br><br>
          Warga <b>Kec. {baris['kecamatan']}</b> yang kami hormati,<br>
          Risiko banjir & rob di wilayah Anda saat ini <b>{baris['status'].upper()}</b>
          (skor {baris['skor_risiko']}/100).<br><br>
          🌧️ Curah hujan: {baris['curah_hujan_mm']} mm<br>
          🌊 Pasang laut: +{baris['pasang_laut_cm']} cm<br><br>
          👉 {TINDAKAN[baris['status']]}<br><br>
          ☎️ Darurat: 112 &nbsp;|&nbsp; Info: aplikasi Lapor Wali<br>
          <span style="font-size:11px; color:#555;">{waktu} · Pesan simulasi</span>
        </div>""")

    halaman = f"""<!doctype html><html lang="id"><head><meta charset="utf-8">
    <title>Notifikasi SIAGA ROB</title></head>
    <body style="background:#0b141a; padding:20px;">
    <h2 style="color:white; text-align:center; font-family:Arial;">📱 Notifikasi Warga – SIAGA ROB Semarang</h2>
    {''.join(kartu_html)}
    </body></html>"""

    lokasi = os.path.join(FOLDER_HASIL, "notifikasi_warga.html")
    with open(lokasi, "w", encoding="utf-8") as f:
        f.write(halaman)
    print(f"✅ Notifikasi terkirim ke {len(wilayah_bahaya)} kecamatan (simulasi). Disimpan: {lokasi}")
    return lokasi


# =====================================================================
# LANGKAH 7 (BONUS) – SKENARIO HUJAN EKSTREM
# =====================================================================
def skenario_hujan(df, tambahan_hujan):
    hasil = df[["kecamatan", "skor_risiko", "status"]].copy()
    hasil["skor_baru"] = hitung_skor(df["curah_hujan_mm"] + tambahan_hujan,
                                     df["pasang_laut_cm"], df["penurunan_tanah"])
    hasil["status_baru"] = hasil["skor_baru"].apply(tentukan_status)
    hasil["berubah?"] = ["naik" if a != b else "-" for a, b in zip(hasil["status"], hasil["status_baru"])]
    print(f"🌧️ Skenario: curah hujan bertambah {tambahan_hujan} mm di semua kecamatan (DATA SIMULASI)\n")
    print(hasil.to_string(index=False))


# =====================================================================
# LANGKAH 8 – DATA NYATA HARI INI (OPEN DATA: OPEN-METEO & BMKG)
# =====================================================================
# Wilayah sekitar Semarang yang ikut dipantau (koordinat perkiraan)
WILAYAH_SEKITAR = pd.DataFrame({
    "kecamatan": ["Sayung (Demak)", "Kaliwungu (Kendal)", "Ungaran (Kab. Semarang)"],
    "lat": [-6.925, -6.958, -7.139],
    "lon": [110.515, 110.255, 110.405],
})
TITIK_LAUT = (-6.94, 110.42)   # perairan depan Pelabuhan Tanjung Emas
# Kode wilayah kelurahan (adm4) untuk prakiraan cuaca BMKG
KELURAHAN_BMKG = {
    "33.74.02.1001": "Bandarharjo, Semarang Utara",
    "33.74.05.1001": "Sembungharjo, Genuk",
}
BATAS_HUJAN_LEBAT = 50   # mm/hari, kategori hujan lebat menurut BMKG


def ambil_json(url, batas_waktu=15):
    """Mengambil data JSON dari internet (batas waktu dalam detik)."""
    permintaan = urllib.request.Request(url, headers={"User-Agent": "SIAGA-ROB-Semarang/1.0 (tugas smart city)"})
    with urllib.request.urlopen(permintaan, timeout=batas_waktu) as respons:
        return json.load(respons)


def daftar_wilayah(df):
    """10 kecamatan Kota Semarang + wilayah sekitar, lengkap dengan koordinat."""
    return pd.concat([df[["kecamatan", "lat", "lon"]].assign(kelompok="Kota Semarang"),
                      WILAYAH_SEKITAR.assign(kelompok="Sekitar Semarang")], ignore_index=True)


def ambil_hujan_nyata(df):
    """Curah hujan harian Open-Meteo: 3 hari lalu, hari ini, dan prakiraan 2 hari ke depan."""
    wilayah = daftar_wilayah(df)
    url = ("https://api.open-meteo.com/v1/forecast"
           f"?latitude={','.join(map(str, wilayah['lat']))}"
           f"&longitude={','.join(map(str, wilayah['lon']))}"
           "&daily=precipitation_sum&past_days=3&forecast_days=3&timezone=Asia%2FJakarta")
    hasil = ambil_json(url)
    hujan = [[nilai or 0 for nilai in titik["daily"]["precipitation_sum"]] for titik in hasil]
    wilayah["hujan_3hari_lalu_mm"] = [round(sum(h[:3]), 1) for h in hujan]
    wilayah["hujan_hari_ini_mm"] = [h[3] for h in hujan]
    wilayah["prakiraan_maks_mm"] = [max(h[3:]) for h in hujan]
    return wilayah.drop(columns=["lat", "lon"])


def ambil_muka_laut():
    """Prakiraan tinggi muka laut per jam (Open-Meteo Marine) di depan Tanjung Emas."""
    url = ("https://marine-api.open-meteo.com/v1/marine"
           f"?latitude={TITIK_LAUT[0]}&longitude={TITIK_LAUT[1]}"
           "&hourly=sea_level_height_msl&forecast_days=1&timezone=Asia%2FJakarta")
    data = ambil_json(url)["hourly"]
    tinggi = data["sea_level_height_msl"]
    i_puncak = tinggi.index(max(tinggi))
    return {"tertinggi_m": max(tinggi), "jam_tertinggi": data["time"][i_puncak][-5:],
            "terendah_m": min(tinggi), "tunggang_m": round(max(tinggi) - min(tinggi), 2),
            "jam": [t[-5:] for t in data["time"]], "tinggi": tinggi}


def buat_grafik_pasang(laut):
    """Grafik garis tinggi muka laut per jam hari ini (DATA NYATA) untuk melihat jam rawan rob."""
    fig, ax = plt.subplots(figsize=(11, 4))
    x = range(len(laut["tinggi"]))
    ax.plot(x, laut["tinggi"], color="#1f6fb2", linewidth=2.5, marker="o", markersize=4)
    ax.fill_between(x, laut["tinggi"], min(laut["tinggi"]) - 0.1, color="#1f6fb2", alpha=0.12)

    # Tandai puncak pasang dan jam sekarang
    i_puncak = laut["tinggi"].index(laut["tertinggi_m"])
    ax.annotate(f"Puncak pasang\n{laut['tertinggi_m']} m ({laut['jam_tertinggi']})",
                xy=(i_puncak, laut["tertinggi_m"]), xytext=(0, 18), textcoords="offset points",
                ha="center", fontsize=9, fontweight="bold", color="#0b3d5c")
    jam_sekarang = datetime.now(timezone(timedelta(hours=7))).hour
    if jam_sekarang < len(laut["tinggi"]):
        ax.axvline(jam_sekarang, color="#d62828", linestyle="--", linewidth=1.2)
        ax.text(jam_sekarang, min(laut["tinggi"]) - 0.08, " Sekarang", color="#d62828", fontsize=9)

    ax.set_xticks(list(x)[::3], laut["jam"][::3])
    ax.set_ylim(min(laut["tinggi"]) - 0.1, laut["tertinggi_m"] + 0.25)
    ax.set_title("Prakiraan Muka Laut Depan Tanjung Emas Hari Ini\n(DATA NYATA – Open-Meteo Marine, model)",
                 fontsize=13, fontweight="bold")
    ax.set_xlabel("Jam (WIB)")
    ax.set_ylabel("Tinggi muka laut (m)")
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()

    lokasi = os.path.join(FOLDER_HASIL, "grafik_pasang_laut.png")
    fig.savefig(lokasi, dpi=150)
    plt.close(fig)   # tidak ikut muncul di jendela, cukup disimpan untuk dashboard
    print(f"📈 Grafik pasang laut 24 jam disimpan: {lokasi}")


def ambil_cuaca_bmkg():
    """Prakiraan cuaca BMKG 24 jam ke depan untuk kelurahan pesisir."""
    hasil = []
    for kode, nama in KELURAHAN_BMKG.items():
        data = ambil_json(f"https://api.bmkg.go.id/publik/prakiraan-cuaca?adm4={kode}")
        ramalan = [c for hari in data["data"][0]["cuaca"] for c in hari][:8]   # 8 x 3 jam = 24 jam
        hasil.append({
            "kelurahan": nama,
            "cuaca_24_jam": ", ".join(dict.fromkeys(c["weather_desc"] for c in ramalan)),
            "hujan_24_jam_mm": round(sum(c.get("tp") or 0 for c in ramalan), 1),
        })
    return hasil


def ambil_data_nyata(df):
    print("✅ DATA NYATA dari open data (bukan simulasi). Tidak dipakai untuk skor di Langkah 2–3.\n")
    data_nyata = {"waktu": datetime.now(timezone(timedelta(hours=7))).strftime("%d-%m-%Y %H:%M WIB"),
                  "hujan": None, "laut": None, "bmkg": None}

    # Setiap sumber diambil terpisah; jika satu gagal (misal tanpa internet), yang lain tetap jalan
    try:
        data_nyata["hujan"] = ambil_hujan_nyata(df)
        print("🌧️  Curah hujan (mm) – sumber: Open-Meteo (model cuaca)")
        print(data_nyata["hujan"].to_string(index=False))
    except Exception as e:
        print(f"⚠️  Data hujan Open-Meteo tidak bisa diambil ({e})")

    try:
        laut = data_nyata["laut"] = ambil_muka_laut()
        print(f"\n🌊 Muka laut depan Tanjung Emas hari ini – sumber: Open-Meteo Marine (model)")
        print(f"   Tertinggi {laut['tertinggi_m']} m pukul {laut['jam_tertinggi']} WIB, "
              f"terendah {laut['terendah_m']} m (tunggang pasang {laut['tunggang_m']} m)")
        buat_grafik_pasang(laut)
    except Exception as e:
        print(f"⚠️  Data muka laut tidak bisa diambil ({e})")

    try:
        data_nyata["bmkg"] = ambil_cuaca_bmkg()
        print("\n🌤️  Prakiraan cuaca 24 jam – sumber: BMKG")
        for c in data_nyata["bmkg"]:
            print(f"   {c['kelurahan']}: {c['cuaca_24_jam']} | hujan ±{c['hujan_24_jam_mm']} mm")
    except Exception as e:
        print(f"⚠️  Data BMKG tidak bisa diambil ({e})")

    return data_nyata


# =====================================================================
# LANGKAH 9 – RIWAYAT DATA NYATA 2024 S.D. HARI INI (ARSIP OPEN-METEO)
# =====================================================================
TANGGAL_MULAI_RIWAYAT = "2024-01-01"   # diambil ulang dari tanggal ini sampai hari ini setiap program jalan
NAMA_BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


def ambil_riwayat_hujan(wilayah, hari_ini):
    """Curah hujan harian arsip Open-Meteo (model ERA5) untuk semua wilayah."""
    url = ("https://archive-api.open-meteo.com/v1/archive"
           f"?latitude={','.join(map(str, wilayah['lat']))}"
           f"&longitude={','.join(map(str, wilayah['lon']))}"
           f"&start_date={TANGGAL_MULAI_RIWAYAT}&end_date={hari_ini}"
           "&daily=precipitation_sum&timezone=Asia%2FJakarta")
    hasil = ambil_json(url, batas_waktu=60)
    tabel = pd.DataFrame({nama: titik["daily"]["precipitation_sum"]
                          for nama, titik in zip(wilayah["kecamatan"], hasil)},
                         index=pd.to_datetime(hasil[0]["daily"]["time"]), dtype=float)
    return tabel.dropna(how="all")   # hari terakhir bisa belum tersedia di arsip


def ambil_riwayat_laut(hari_ini):
    """Muka laut tertinggi tiap hari dari arsip per jam Open-Meteo Marine."""
    url = ("https://marine-api.open-meteo.com/v1/marine"
           f"?latitude={TITIK_LAUT[0]}&longitude={TITIK_LAUT[1]}"
           f"&start_date={TANGGAL_MULAI_RIWAYAT}&end_date={hari_ini}"
           "&hourly=sea_level_height_msl&timezone=Asia%2FJakarta")
    data = ambil_json(url, batas_waktu=60)["hourly"]
    per_jam = pd.Series(data["sea_level_height_msl"], index=pd.to_datetime(data["time"]), dtype=float)
    return per_jam.resample("D").max().dropna()


def ringkas_hujan(df, hujan):
    """Ringkasan per wilayah dan 5 hari terbasah di Kota Semarang."""
    ringkasan = pd.DataFrame(index=hujan.columns)
    for tahun in sorted(set(hujan.index.year)):
        ringkasan[f"total_{tahun}_mm"] = hujan[hujan.index.year == tahun].sum().round(0).astype(int)
    ringkasan["maks_harian_mm"] = hujan.max().round(1)
    ringkasan["tanggal_maks"] = hujan.idxmax().dt.strftime("%d-%m-%Y")
    ringkasan["hari_hujan_lebat"] = (hujan >= BATAS_HUJAN_LEBAT).sum()
    ringkasan = ringkasan.rename_axis("wilayah").reset_index()

    kota = hujan[df["kecamatan"]].mean(axis=1)   # rata-rata 10 kecamatan
    terbasah = kota.nlargest(5)
    ekstrem = pd.DataFrame({
        "tanggal": terbasah.index.strftime("%d-%m-%Y"),
        "hujan_rata_kota_mm": terbasah.round(1).values,
        "hujan_maks_kecamatan_mm": hujan.loc[terbasah.index, df["kecamatan"]].max(axis=1).round(1).values,
    })
    return kota, ringkasan, ekstrem


def bulan_puncak(harian, cara):
    """3 bulan dengan nilai rata-rata tertinggi (bulan berjalan yang belum lengkap tidak dihitung)."""
    per_bulan = getattr(harian.resample("MS"), cara)().iloc[:-1]
    rata = per_bulan.groupby(per_bulan.index.month).mean()
    return [NAMA_BULAN[b - 1] for b in rata.nlargest(3).index]


def buat_grafik_riwayat(kota, laut, periode):
    """Grafik bulanan: curah hujan rata-rata kota dan muka laut tertinggi (DATA NYATA)."""
    panel = [p for p in (kota, laut) if p is not None]
    fig, axes = plt.subplots(len(panel), 1, figsize=(12, 3.6 * len(panel)), sharex=True, squeeze=False)
    axes = list(axes[:, 0])
    i = 0
    if kota is not None:
        bulanan = kota.resample("MS").sum()
        axes[i].bar(bulanan.index, bulanan.values, width=25, align="edge", color="#1f6fb2")
        axes[i].set_ylabel("Hujan bulanan (mm)")
        axes[i].set_title("Curah hujan bulanan – rata-rata 10 kecamatan Kota Semarang", fontsize=11, loc="left")
        i += 1
    if laut is not None:
        bulanan_laut = laut.resample("MS").max()
        axes[i].plot(bulanan_laut.index, bulanan_laut.values, color="#d62828", marker="o", linewidth=2)
        axes[i].set_ylabel("Muka laut maks (m)")
        axes[i].set_title("Muka laut tertinggi tiap bulan – depan Tanjung Emas", fontsize=11, loc="left")

    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", alpha=0.3)
    acuan = kota if kota is not None else laut
    posisi = pd.date_range(acuan.index.min(), acuan.index.max(), freq="3MS")
    axes[-1].set_xticks(posisi, [f"{NAMA_BULAN[t.month - 1]}\n{t.year}" for t in posisi])
    fig.suptitle(f"Riwayat {periode} (DATA NYATA – arsip Open-Meteo, model)", fontsize=13, fontweight="bold")
    plt.tight_layout()

    lokasi = os.path.join(FOLDER_HASIL, "grafik_riwayat.png")
    fig.savefig(lokasi, dpi=150)
    plt.close(fig)
    print(f"\n📈 Grafik riwayat bulanan disimpan: {lokasi}")


def ambil_riwayat(df):
    wib = timezone(timedelta(hours=7))
    hari_ini = datetime.now(wib).strftime("%Y-%m-%d")
    awal = datetime.strptime(TANGGAL_MULAI_RIWAYAT, "%Y-%m-%d").strftime("%d-%m-%Y")
    riwayat = {"periode": f"{awal} s.d. {datetime.now(wib).strftime('%d-%m-%Y')}",
               "harian_hujan": None, "ringkasan": None, "ekstrem": None,
               "harian_laut": None, "pasang_tertinggi": None,
               "bulan_rawan_hujan": None, "bulan_rawan_rob": None}
    print(f"✅ DATA NYATA arsip {riwayat['periode']}, diambil ulang setiap program jalan. "
          "Tidak dipakai untuk skor.\n")

    kota = laut = None
    try:
        hujan = riwayat["harian_hujan"] = ambil_riwayat_hujan(daftar_wilayah(df), hari_ini)
        kota, riwayat["ringkasan"], riwayat["ekstrem"] = ringkas_hujan(df, hujan)
        print("🌧️  Ringkasan curah hujan per wilayah – sumber: arsip Open-Meteo (model ERA5)")
        print(riwayat["ringkasan"].to_string(index=False))
        print("   ℹ️  Resolusi model ±9–25 km, jadi kecamatan yang berdekatan bisa bernilai sama.")
        print("\n⛈️  5 hari terbasah di Kota Semarang (rata-rata 10 kecamatan):")
        print(riwayat["ekstrem"].to_string(index=False))
        riwayat["bulan_rawan_hujan"] = bulan_puncak(kota, "sum")
        print(f"\n📅 Bulan dengan hujan terbanyak (rata-rata): {', '.join(riwayat['bulan_rawan_hujan'])}")
    except Exception as e:
        print(f"⚠️  Riwayat hujan tidak bisa diambil ({e})")

    try:
        laut = riwayat["harian_laut"] = ambil_riwayat_laut(hari_ini)
        tertinggi = laut.nlargest(5)
        riwayat["pasang_tertinggi"] = pd.DataFrame({"tanggal": tertinggi.index.strftime("%d-%m-%Y"),
                                                    "muka_laut_maks_m": tertinggi.round(2).values})
        print("\n🌊 5 pasang laut tertinggi depan Tanjung Emas – sumber: arsip Open-Meteo Marine (model)")
        print(riwayat["pasang_tertinggi"].to_string(index=False))
        riwayat["bulan_rawan_rob"] = bulan_puncak(laut, "max")
        print(f"\n📅 Bulan dengan pasang laut tertinggi (rata-rata): {', '.join(riwayat['bulan_rawan_rob'])}")
    except Exception as e:
        print(f"⚠️  Riwayat muka laut tidak bisa diambil ({e})")

    if kota is not None or laut is not None:
        buat_grafik_riwayat(kota, laut, riwayat["periode"])
    return riwayat


# =====================================================================
# LANGKAH 10 – SKOR RISIKO BERBASIS DATA NYATA (HARI INI & SEJAK 2024)
# =====================================================================
# Seberapa terpapar rob tiap kecamatan (0 = tidak, 1 = penuh), menurut jarak ke pantai.
# Ini ASUMSI untuk tugas, bukan data resmi.
PAPARAN_ROB = {
    "Semarang Utara": 1.0, "Genuk": 1.0, "Tugu": 0.9, "Semarang Barat": 0.7, "Semarang Timur": 0.7,
    "Gayamsari": 0.6, "Semarang Tengah": 0.5, "Pedurungan": 0.4, "Candisari": 0.0, "Tembalang": 0.0,
}


def hitung_skor_nyata(df, data_nyata):
    """Skor hari ini: hujan nyata + pasang laut nyata x paparan rob + penurunan tanah (asumsi)."""
    hujan, laut = data_nyata["hujan"], data_nyata["laut"]
    hasil = df[["kecamatan", "penurunan_tanah", "status"]].rename(columns={"status": "status_simulasi"})
    hasil["hujan_nyata_mm"] = hasil["kecamatan"].map(hujan.set_index("kecamatan")["prakiraan_maks_mm"])
    hasil["pasang_nyata_cm"] = (laut["tertinggi_m"] * 100 * hasil["kecamatan"].map(PAPARAN_ROB)).round(0)
    hasil["skor_nyata"] = hitung_skor(hasil["hujan_nyata_mm"], hasil["pasang_nyata_cm"], hasil["penurunan_tanah"])
    hasil["status_nyata"] = hasil["skor_nyata"].apply(tentukan_status)
    return hasil[["kecamatan", "hujan_nyata_mm", "pasang_nyata_cm", "penurunan_tanah",
                  "skor_nyata", "status_nyata", "status_simulasi"]]


def hitung_status_riwayat(df, riwayat):
    """Skor nyata setiap hari sejak 2024, lalu dihitung berapa hari tiap status per kecamatan."""
    hujan, laut = riwayat["harian_hujan"], riwayat["harian_laut"]
    tanggal = hujan.index.intersection(laut.index)
    baris = []
    for _, k in df.iterrows():
        skor = hitung_skor(hujan.loc[tanggal, k["kecamatan"]].fillna(0),
                           laut.loc[tanggal] * 100 * PAPARAN_ROB[k["kecamatan"]],
                           pd.Series(k["penurunan_tanah"], index=tanggal))
        status = skor.apply(tentukan_status)
        baris.append({"kecamatan": k["kecamatan"],
                      **{f"hari_{s.lower()}": int((status == s).sum()) for s in ["Awas", "Siaga", "Waspada", "Aman"]},
                      "skor_maks": skor.max(), "tanggal_skor_maks": skor.idxmax().strftime("%d-%m-%Y")})
    return pd.DataFrame(baris)


def skor_data_nyata(df, data_nyata):
    print("✅ Rumus sama dengan Langkah 2, tetapi memakai DATA NYATA:")
    print("   • Hujan  : prakiraan hujan maks hari ini s.d. +2 hari (Open-Meteo)")
    print("   • Pasang : muka laut tertinggi hari ini (Open-Meteo Marine) x paparan rob kecamatan (asumsi)")
    print("   • Tanah  : penurunan tanah tetap ASUMSI (belum ada open data real-time)\n")
    data_nyata["skor_nyata"] = data_nyata["status_riwayat"] = None

    if data_nyata["hujan"] is not None and data_nyata["laut"] is not None:
        data_nyata["skor_nyata"] = hitung_skor_nyata(df, data_nyata)
        print("📡 Skor risiko HARI INI (data nyata) vs status simulasi:")
        print(data_nyata["skor_nyata"].to_string(index=False))
        hari_ini = datetime.now(timezone(timedelta(hours=7))).strftime("%d-%m-%Y")
        fig = buat_grafik(data_nyata["skor_nyata"], "skor_nyata", "status_nyata",
                          f"SIAGA ROB Semarang – Skor Risiko Banjir & Rob per Kecamatan, {hari_ini}\n"
                          "(DATA NYATA Open-Meteo + asumsi penurunan tanah & paparan rob)",
                          "grafik_skor_nyata.png")
        plt.close(fig)   # cukup disimpan untuk dashboard; jendela grafik tetap grafik Langkah 4
    else:
        print("⚠️  Skor nyata hari ini dilewati karena data hujan/pasang hari ini tidak tersedia.")

    riwayat = data_nyata["riwayat"]
    if riwayat["harian_hujan"] is not None and riwayat["harian_laut"] is not None:
        data_nyata["status_riwayat"] = hitung_status_riwayat(df, riwayat)
        print(f"\n📚 Jumlah hari per status, {riwayat['periode']} (data nyata):")
        print(data_nyata["status_riwayat"].to_string(index=False))
    else:
        print("⚠️  Status riwayat dilewati karena data riwayat tidak tersedia.")


# =====================================================================
# LANGKAH 11 – PREDIKSI 7 HARI KE DEPAN & RENCANA AKSI WALI KOTA
# =====================================================================
HARI_PREDIKSI = 7
NAMA_HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
URUTAN_STATUS = ["Aman", "Waspada", "Siaga", "Awas"]
HULU = "Ungaran (Kab. Semarang)"
# Kecamatan yang dilalui aliran sungai dari hulu; hujan lebat di hulu bisa menjadi banjir kiriman (ASUMSI)
HILIR_BANJIR_KIRIMAN = ["Semarang Barat", "Semarang Tengah", "Semarang Utara"]
TAMBAHAN_SKOR_KIRIMAN = 10

# Rencana aksi: (status minimal, pelaksana, tindakan, waktu). Diisi otomatis sesuai hasil prediksi.
RENCANA_AKSI = [
    ("Waspada", "Wali Kota", "Instruksikan seluruh OPD terkait siaga tingkat {status} untuk {wilayah}.", "Hari ini"),
    ("Waspada", "BPBD", "Pantau hujan dan pasang laut tiap 3 jam; siapkan posko dan tim reaksi cepat di {wilayah}.",
     "Mulai {h1}"),
    ("Waspada", "Dinas Pekerjaan Umum", "Uji coba rumah pompa dan pintu air, cek tanggul, bersihkan saluran di {wilayah}.",
     "Paling lambat {h1}"),
    ("Waspada", "Diskominfo", "Kirim peringatan SIAGA ROB ke warga {wilayah}: H-1 dan 3 jam sebelum puncak pasang "
     "({jam} WIB).", "{h1} & {puncak}"),
    ("Waspada", "Camat & Lurah", "Gerakkan kerja bakti saluran; data warga rentan (lansia, disabilitas, ibu hamil, balita).",
     "Sebelum {puncak}"),
    ("Siaga", "Wali Kota", "Pimpin rapat koordinasi siaga bencana bersama BPBD, Dinas PU, Dishub, Dinkes, dan Dinsos.",
     "Hari ini"),
    ("Siaga", "Dinas Pekerjaan Umum", "Operasikan pompa penuh dan tempatkan pompa portabel di {wilayah} sebelum {jam} WIB.",
     "{puncak}"),
    ("Siaga", "Dishub", "Siapkan rekayasa lalu lintas di jalan rawan genangan.", "{puncak}"),
    ("Siaga", "Dinsos & Dinkes", "Siapkan logistik, dapur umum, puskesmas siaga, dan ambulans.", "Mulai {h1}"),
    ("Awas", "Wali Kota", "Pertimbangkan penetapan status tanggap darurat dan buka posko pengungsian.", "Segera"),
    ("Awas", "BPBD bersama TNI/Polri", "Evakuasi warga rentan di {wilayah} sebelum puncak pasang.",
     "Sebelum {jam} WIB, {puncak}"),
]


def nama_tanggal(t):
    return f"{NAMA_HARI[t.weekday()]} {t.strftime('%d-%m-%Y')}"


def ambil_prakiraan(df):
    """Prakiraan hujan harian dan muka laut per jam untuk 7 hari ke depan (Open-Meteo)."""
    wilayah = daftar_wilayah(df)
    hasil = ambil_json("https://api.open-meteo.com/v1/forecast"
                       f"?latitude={','.join(map(str, wilayah['lat']))}"
                       f"&longitude={','.join(map(str, wilayah['lon']))}"
                       f"&daily=precipitation_sum&forecast_days={HARI_PREDIKSI}&timezone=Asia%2FJakarta")
    hujan = pd.DataFrame({nama: titik["daily"]["precipitation_sum"] for nama, titik in zip(wilayah["kecamatan"], hasil)},
                         index=pd.to_datetime(hasil[0]["daily"]["time"]), dtype=float).fillna(0)
    laut = ambil_json("https://marine-api.open-meteo.com/v1/marine"
                      f"?latitude={TITIK_LAUT[0]}&longitude={TITIK_LAUT[1]}"
                      f"&hourly=sea_level_height_msl&forecast_days={HARI_PREDIKSI}&timezone=Asia%2FJakarta")["hourly"]
    laut_jam = pd.Series(laut["sea_level_height_msl"], index=pd.to_datetime(laut["time"]), dtype=float).dropna()
    # Jam yang sudah lewat tidak dihitung, agar puncak pasang yang diprediksi selalu di masa depan
    sekarang = pd.Timestamp(datetime.now(timezone(timedelta(hours=7)))).tz_localize(None).floor("h")
    return hujan, laut_jam[laut_jam.index >= sekarang]


def hitung_prediksi(df, hujan, laut_jam):
    """Skor risiko tiap kecamatan per hari dengan rumus Langkah 2 dari data prakiraan."""
    laut_harian = laut_jam.resample("D").max()
    tanggal = hujan.index.intersection(laut_harian.index)
    tanah = df.set_index("kecamatan")["penurunan_tanah"]
    p = pd.DataFrame([{"tanggal": t, "kecamatan": k, "hujan_mm": hujan.at[t, k],
                       "pasang_cm": round(laut_harian[t] * 100 * PAPARAN_ROB[k]),
                       "penurunan_tanah": tanah[k],
                       "kiriman": k in HILIR_BANJIR_KIRIMAN and hujan.at[t, HULU] >= BATAS_HUJAN_LEBAT}
                      for t in tanggal for k in df["kecamatan"]])
    p["skor"] = hitung_skor(p["hujan_mm"], p["pasang_cm"], p["penurunan_tanah"])
    p.loc[p["kiriman"], "skor"] = (p.loc[p["kiriman"], "skor"] + TAMBAHAN_SKOR_KIRIMAN).clip(upper=100)
    p["status"] = p["skor"].apply(tentukan_status)

    # Ancaman utama: komponen yang paling besar menyumbang skor
    andil_hujan = BOBOT_HUJAN * (p["hujan_mm"] / BATAS_HUJAN).clip(upper=1)
    andil_pasang = BOBOT_PASANG * (p["pasang_cm"] / BATAS_PASANG).clip(upper=1)
    p["ancaman"] = ["banjir kiriman" if kiriman else ("rob" if pasang >= hujan_ else "banjir hujan")
                    for kiriman, hujan_, pasang in zip(p["kiriman"], andil_hujan, andil_pasang)]

    harian = pd.DataFrame({
        "tanggal": [nama_tanggal(t) for t in tanggal],
        "hujan_kota_mm": hujan.loc[tanggal, df["kecamatan"]].mean(axis=1).round(1).values,
        "hujan_hulu_mm": hujan.loc[tanggal, HULU].round(1).values,
        "pasang_maks_m": laut_harian[tanggal].round(2).values,
        "jam_puncak_pasang": [laut_jam[laut_jam.index.normalize() == t].idxmax().strftime("%H:%M") for t in tanggal],
        "wilayah_terdampak": [", ".join(p[(p["tanggal"] == t) & (p["status"] != "Aman")]
                                        .sort_values("skor", ascending=False)["kecamatan"]) or "–" for t in tanggal],
    })
    return p, harian


def buat_grafik_prediksi(df, hujan, laut_jam):
    """Grafik prakiraan: hujan harian (kota & hulu) dan muka laut per jam dengan puncak pasang."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7))
    label_hari = [nama_tanggal(t)[:-5] for t in hujan.index]
    x = range(len(hujan))
    kota = hujan[df["kecamatan"]].mean(axis=1)

    ax1.bar([i - 0.2 for i in x], kota, width=0.4, color="#1f6fb2", label="Rata-rata Kota Semarang")
    ax1.bar([i + 0.2 for i in x], hujan[HULU], width=0.4, color="#8fbde6", label="Hulu (Ungaran)")
    ax1.axhline(BATAS_HUJAN_LEBAT, color="#d62828", linestyle="--", linewidth=1)
    ax1.text(len(hujan) - 0.6, BATAS_HUJAN_LEBAT, "Batas hujan lebat", color="#d62828", ha="right", va="bottom", fontsize=9)
    ax1.set_xticks(list(x), label_hari)
    ax1.set_ylim(0, max(BATAS_HUJAN_LEBAT * 1.2, kota.max(), hujan[HULU].max()) * 1.15)
    ax1.set_ylabel("Hujan (mm/hari)")
    ax1.set_title("Prakiraan curah hujan harian", fontsize=11, loc="left")
    ax1.legend(loc="upper left", fontsize=9)

    ax2.plot(laut_jam.index, laut_jam.values, color="#1f6fb2", linewidth=1.8)
    puncak = list(laut_jam.groupby(laut_jam.index.normalize()).idxmax())
    ax2.scatter(puncak, laut_jam[puncak], color="#d62828", zorder=3)
    for t in puncak:
        ax2.annotate(f"{laut_jam[t]:.2f} m\n{t:%H:%M}", (t, laut_jam[t]), textcoords="offset points",
                     xytext=(0, 6), ha="center", fontsize=8)
    ax2.set_xticks(hujan.index + pd.Timedelta(hours=12), label_hari)   # label di tengah hari, sejajar batang
    ax2.set_xlim(hujan.index.min(), hujan.index.max() + pd.Timedelta(days=1))
    ax2.set_ylim(laut_jam.min() - 0.1, laut_jam.max() + 0.35)
    ax2.set_ylabel("Muka laut (m)")
    ax2.set_title("Prakiraan muka laut per jam – titik merah = puncak pasang harian", fontsize=11, loc="left")

    for ax in (ax1, ax2):
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", alpha=0.3)
    fig.suptitle(f"Prediksi {HARI_PREDIKSI} Hari ke Depan (DATA NYATA – prakiraan Open-Meteo)",
                 fontsize=13, fontweight="bold")
    plt.tight_layout()
    lokasi = os.path.join(FOLDER_HASIL, "grafik_prediksi.png")
    fig.savefig(lokasi, dpi=150)
    plt.close(fig)
    print(f"\n📈 Grafik prediksi disimpan: {lokasi}")


def buat_rencana_aksi(p, harian):
    """Rencana aksi Wali Kota & jajaran sesuai tingkat ancaman tertinggi dalam 7 hari."""
    level = max(p["status"], key=URUTAN_STATUS.index)
    if level == "Aman":
        return {"level": level, "wilayah": "",
                "ringkasan": f"Tidak ada kecamatan yang diprediksi mencapai Waspada dalam {HARI_PREDIKSI} hari ke depan.",
                "aksi": [{"pelaksana": "Wali Kota & OPD", "waktu": "Rutin",
                          "tindakan": "Lanjutkan pemeliharaan saluran dan pompa; pantau prakiraan setiap hari."}]}

    teratas = p.loc[p["skor"].idxmax()]
    t_puncak = teratas["tanggal"]
    terdampak = p[p["status"] != "Aman"]
    isi = {
        "status": level,
        "wilayah": ", ".join(terdampak.groupby("kecamatan")["skor"].max().sort_values(ascending=False).index),
        "jam": harian.loc[harian["tanggal"] == nama_tanggal(t_puncak), "jam_puncak_pasang"].iloc[0],
        "puncak": nama_tanggal(t_puncak),
        "h1": nama_tanggal(t_puncak - pd.Timedelta(days=1)),
    }
    if t_puncak == p["tanggal"].min():   # puncak jatuh hari ini: tidak ada waktu H-1
        isi["puncak"], isi["h1"] = f"hari ini ({nama_tanggal(t_puncak)})", "segera"
    elif t_puncak - pd.Timedelta(days=1) == p["tanggal"].min():
        isi["h1"] = "hari ini"
    aksi = [{"pelaksana": pelaksana, "tindakan": tindakan.format(**isi), "waktu": waktu.format(**isi)}
            for minimal, pelaksana, tindakan, waktu in RENCANA_AKSI
            if URUTAN_STATUS.index(minimal) <= URUTAN_STATUS.index(level)]
    if terdampak["kiriman"].any():
        aksi.append({"pelaksana": "BPBD & Pemkab Semarang", "waktu": isi["h1"],
                     "tindakan": "Koordinasi pantauan debit sungai dari hulu (banjir kiriman) untuk "
                                 f"{', '.join(HILIR_BANJIR_KIRIMAN)}."})
    ringkasan = (f"Puncak risiko diprediksi {isi['puncak']} di Kec. {teratas['kecamatan']} "
                 f"(skor {teratas['skor']}, {teratas['status']}, ancaman utama {teratas['ancaman']}); "
                 f"puncak pasang hari itu pukul {isi['jam']} WIB. Wilayah terdampak: {isi['wilayah']}.")
    return {"level": level, "wilayah": isi["wilayah"], "ringkasan": ringkasan, "aksi": aksi}


def prediksi_7_hari(df, data_nyata):
    print(f"✅ DATA NYATA prakiraan Open-Meteo {HARI_PREDIKSI} hari ke depan, rumus skor sama dengan Langkah 2.")
    print("   Paparan rob, penurunan tanah, dan banjir kiriman dari hulu adalah ASUMSI.\n")
    data_nyata["prediksi"] = None
    try:
        hujan, laut_jam = ambil_prakiraan(df)
    except Exception as e:
        print(f"⚠️  Prakiraan tidak bisa diambil ({e}). Langkah ini dilewati.")
        return

    per_kecamatan, harian = hitung_prediksi(df, hujan, laut_jam)
    rencana = buat_rencana_aksi(per_kecamatan, harian)
    data_nyata["prediksi"] = {"per_kecamatan": per_kecamatan, "harian": harian, "rencana": rencana}

    print("📅 Ringkasan prediksi per hari:")
    print(harian.to_string(index=False))
    matriks = per_kecamatan.pivot(index="kecamatan", columns="tanggal", values="skor").reindex(df["kecamatan"])
    matriks.columns = [nama_tanggal(t)[:-5] for t in matriks.columns]
    print("\n🧮 Prediksi skor risiko per kecamatan per hari:")
    print(matriks.to_string())
    buat_grafik_prediksi(df, hujan, laut_jam)

    print(f"\n{IKON_STATUS[rencana['level']]} {rencana['ringkasan']}")
    print(f"\n🏛️  RENCANA AKSI WALI KOTA & JAJARAN (tingkat {rencana['level']}):")
    for a in rencana["aksi"]:
        print(f"   • [{a['waktu']}] {a['pelaksana']}: {a['tindakan']}")


# =====================================================================
# LANGKAH 12 – REKOMENDASI OTOMATIS UNTUK PEMERINTAH KOTA
# =====================================================================
IKON_STATUS = {"Awas": "🔴", "Siaga": "🟠", "Waspada": "🟡", "Aman": "🟢",
               "Hujan lebat": "⛈️", "Kalender kesiapsiagaan": "📅", "Data nyata hari ini": "📡"}
REKOMENDASI = {
    "Awas": [
        "Operasikan semua rumah pompa dan kerahkan pompa portabel ke titik genangan.",
        "Buka posko pengungsian dan dapur umum; evakuasi lansia, anak-anak, dan penyandang disabilitas lebih dulu.",
        "Alihkan lalu lintas dari jalan yang tergenang.",
        "Siagakan tim SAR, ambulans, dan tenaga kesehatan.",
    ],
    "Siaga": [
        "Cek kesiapan rumah pompa, pintu air, dan tanggul; siapkan pompa cadangan.",
        "Bersihkan saluran dan gorong-gorong dari sampah.",
        "Siapkan posko dan logistik; sebarkan peringatan lewat RT/RW dan media sosial.",
    ],
    "Waspada": [
        "Pantau curah hujan dan pasang laut setiap 3 jam.",
        "Gerakkan kerja bakti normalisasi saluran.",
        "Ingatkan warga menyiapkan tas siaga.",
    ],
    "Aman": [
        "Lakukan pemeliharaan rutin saluran dan pompa.",
        "Edukasi warga tentang jalur evakuasi.",
    ],
}
REKOMENDASI_JANGKA_PANJANG = [
    "Pasang sensor IoT tinggi muka air dan pasang laut di titik rawan agar data simulasi bisa diganti data real-time.",
    "Kendalikan pengambilan air tanah untuk memperlambat penurunan tanah.",
    "Bangun kolam retensi dan sistem polder di kecamatan pesisir untuk menampung air saat hujan bersamaan dengan pasang.",
    "Perkuat tanggul pantai dan tanam mangrove sebagai sabuk hijau penahan rob.",
    "Bagikan data risiko dalam format terbuka (CSV/JSON) lewat portal Satu Data Kota Semarang.",
    "Hubungkan peringatan dini dengan kanal aduan warga (Lapor Wali) agar laporan genangan ikut terpantau.",
]


def buat_rekomendasi(df, data_nyata):
    rekomendasi = []
    for status in ["Awas", "Siaga", "Waspada", "Aman"]:
        wilayah = df.loc[df["status"] == status, "kecamatan"].tolist()
        if not wilayah:
            continue
        print(f"\n{IKON_STATUS[status]} {status.upper()} – {', '.join(wilayah)}")
        for tindakan in REKOMENDASI[status]:
            print(f"   • {tindakan}")
        rekomendasi.append({"status": status, "wilayah": wilayah, "tindakan": REKOMENDASI[status],
                            "dasar": "skor risiko (data simulasi)"})

    # Pemicu tambahan dari data nyata: prakiraan hujan lebat
    hujan = data_nyata["hujan"]
    if hujan is not None:
        lebat = hujan[hujan["prakiraan_maks_mm"] >= BATAS_HUJAN_LEBAT]["kecamatan"].tolist()
        if lebat:
            tindakan = ["Naikkan kesiapan satu tingkat di wilayah ini.",
                        "Koordinasi dengan BPBD dan pemerintah kabupaten tetangga untuk banjir kiriman."]
            print(f"\n⛈️  DATA NYATA: prakiraan hujan lebat (≥{BATAS_HUJAN_LEBAT} mm) di {', '.join(lebat)}")
            for t in tindakan:
                print(f"   • {t}")
            rekomendasi.append({"status": "Hujan lebat", "wilayah": lebat, "tindakan": tindakan,
                                "dasar": "prakiraan hujan Open-Meteo (data nyata)"})
        else:
            print(f"\n✅ DATA NYATA: tidak ada prakiraan hujan lebat (≥{BATAS_HUJAN_LEBAT} mm) "
                  "di Semarang dan sekitarnya.")

    # Status dari skor data nyata hari ini
    skor_nyata = data_nyata["skor_nyata"]
    if skor_nyata is not None:
        bahaya = skor_nyata[skor_nyata["status_nyata"].isin(["Siaga", "Awas"])]
        if len(bahaya):
            tindakan = [f"Kec. {b['kecamatan']} berstatus {b['status_nyata']} (skor nyata {b['skor_nyata']}): "
                        f"jalankan tindakan {b['status_nyata']} di atas." for _, b in bahaya.iterrows()]
            print("\n📡 DATA NYATA HARI INI:")
            for t in tindakan:
                print(f"   • {t}")
            rekomendasi.append({"status": "Data nyata hari ini", "wilayah": bahaya["kecamatan"].tolist(),
                                "tindakan": tindakan, "dasar": "skor risiko berbasis data nyata hari ini"})
        else:
            print("\n✅ DATA NYATA HARI INI: tidak ada kecamatan berstatus Siaga/Awas menurut skor nyata.")

    # Kalender kesiapsiagaan dari riwayat: bulan puncak hujan dan puncak pasang laut
    riwayat = data_nyata["riwayat"]
    tindakan = []
    if riwayat["bulan_rawan_hujan"]:
        tindakan.append(f"Puncak hujan biasanya bulan {', '.join(riwayat['bulan_rawan_hujan'])}: "
                        "bersihkan saluran dan siapkan pompa sebulan sebelumnya.")
    if riwayat["bulan_rawan_rob"]:
        tindakan.append(f"Pasang laut tertinggi biasanya bulan {', '.join(riwayat['bulan_rawan_rob'])}: "
                        "siagakan tanggul, pintu air, dan posko di kecamatan pesisir.")
    if tindakan:
        print(f"\n📅 KALENDER KESIAPSIAGAAN (riwayat {riwayat['periode']}, data nyata)")
        for t in tindakan:
            print(f"   • {t}")
        rekomendasi.append({"status": "Kalender kesiapsiagaan", "wilayah": ["Kota Semarang"], "tindakan": tindakan,
                            "dasar": f"riwayat hujan & pasang laut {riwayat['periode']} (data nyata)"})

    print("\n💡 Rekomendasi jangka panjang (gagasan smart city):")
    for t in REKOMENDASI_JANGKA_PANJANG:
        print(f"   • {t}")
    return rekomendasi


# =====================================================================
# LANGKAH 13 – EKSPOR DATA TERBUKA (CSV & JSON)
# =====================================================================
KOLOM_EKSPOR = ["kecamatan", "curah_hujan_mm", "pasang_laut_cm", "penurunan_tanah",
                "skor_risiko", "status", "lat", "lon"]


def ekspor_data(df, data_nyata, rekomendasi):
    lokasi_csv = os.path.join(FOLDER_HASIL, "skor_risiko_simulasi.csv")
    df[KOLOM_EKSPOR].to_csv(lokasi_csv, index=False)
    print(f"💾 CSV skor risiko (simulasi): {lokasi_csv}")

    if data_nyata["hujan"] is not None:
        lokasi_hujan = os.path.join(FOLDER_HASIL, "hujan_nyata_open_meteo.csv")
        data_nyata["hujan"].to_csv(lokasi_hujan, index=False)
        print(f"💾 CSV curah hujan (data nyata): {lokasi_hujan}")

    riwayat = data_nyata["riwayat"]
    if riwayat["harian_hujan"] is not None:
        lokasi = os.path.join(FOLDER_HASIL, "riwayat_hujan_harian.csv")
        riwayat["harian_hujan"].rename_axis("tanggal").to_csv(lokasi)
        print(f"💾 CSV riwayat hujan harian (data nyata): {lokasi}")
    if riwayat["harian_laut"] is not None:
        lokasi = os.path.join(FOLDER_HASIL, "riwayat_muka_laut_harian.csv")
        riwayat["harian_laut"].rename("muka_laut_maks_m").rename_axis("tanggal").to_csv(lokasi)
        print(f"💾 CSV riwayat muka laut harian (data nyata): {lokasi}")

    prediksi = data_nyata["prediksi"]
    if prediksi:
        lokasi = os.path.join(FOLDER_HASIL, "prediksi_7_hari.csv")
        prediksi["per_kecamatan"].assign(tanggal=prediksi["per_kecamatan"]["tanggal"].dt.strftime("%Y-%m-%d")) \
            .to_csv(lokasi, index=False)
        print(f"💾 CSV prediksi {HARI_PREDIKSI} hari (data nyata + asumsi): {lokasi}")

    def ke_json(tabel):
        return json.loads(tabel.to_json(orient="records")) if tabel is not None else None

    paket = {
        "judul": "SIAGA ROB Semarang – Skor Risiko Banjir & Rob",
        "keterangan": "Skor risiko memakai DATA SIMULASI untuk tugas presentasi, bukan data resmi. "
                      "Bagian data_nyata berasal dari open data Open-Meteo dan BMKG.",
        "dibuat": data_nyata["waktu"],
        "rumus": "skor = (40% hujan/150 + 35% pasang/150 + 25% penurunan_tanah/10) x 100",
        "skor_risiko_simulasi": json.loads(df[KOLOM_EKSPOR].to_json(orient="records")),
        "data_nyata": {
            "hujan_open_meteo": (json.loads(data_nyata["hujan"].to_json(orient="records"))
                                 if data_nyata["hujan"] is not None else None),
            "muka_laut_open_meteo": data_nyata["laut"],
            "cuaca_bmkg": data_nyata["bmkg"],
            "riwayat": {
                "periode": riwayat["periode"],
                "ringkasan_hujan": ke_json(riwayat["ringkasan"]),
                "hari_terbasah": ke_json(riwayat["ekstrem"]),
                "pasang_tertinggi": ke_json(riwayat["pasang_tertinggi"]),
                "bulan_rawan_hujan": riwayat["bulan_rawan_hujan"],
                "bulan_rawan_rob": riwayat["bulan_rawan_rob"],
            },
            "skor_nyata_hari_ini": ke_json(data_nyata["skor_nyata"]),
            "jumlah_hari_per_status": ke_json(data_nyata["status_riwayat"]),
            "paparan_rob_asumsi": PAPARAN_ROB,
            "prediksi_7_hari": ({"ringkasan_harian": ke_json(prediksi["harian"]), "rencana_aksi": prediksi["rencana"]}
                                if prediksi else None),
        },
        "rekomendasi": rekomendasi,
    }
    lokasi_json = os.path.join(FOLDER_HASIL, "siaga_rob_data.json")
    with open(lokasi_json, "w", encoding="utf-8") as f:
        json.dump(paket, f, ensure_ascii=False, indent=2)
    print(f"💾 JSON lengkap (simulasi + data nyata + rekomendasi): {lokasi_json}")


# =====================================================================
# LANGKAH 14 – DASHBOARD HTML DI LOCALHOST (SEMUA HASIL DALAM SATU HALAMAN)
# =====================================================================
# Alur sistem jika diterapkan nyata (rancangan, bukan sistem yang sudah berjalan)
ALUR_SISTEM = [
    ("📡", "Sumber data", "Sensor IoT muka air & pasang laut, BMKG, Open-Meteo"),
    ("🗄️", "Pusat data", "Data terkumpul di Satu Data Kota Semarang"),
    ("🧮", "Analisis", "Skor risiko 0–100 per kecamatan, diperbarui otomatis"),
    ("🚨", "Peringatan", "Notifikasi WhatsApp/SMS ke warga berstatus Siaga & Awas"),
    ("🏛️", "Aksi", "Rekomendasi tindakan untuk Pemkot, BPBD, dan warga"),
]
# Transformasi digital: cara konvensional vs dengan SIAGA ROB
TRANSFORMASI = [
    ("Info banjir menyebar dari mulut ke mulut dan media sosial",
     "Peringatan otomatis per kecamatan langsung ke ponsel warga"),
    ("Bertindak setelah air datang (reaktif)",
     "Bersiap sebelum rob datang berdasarkan prakiraan (proaktif)"),
    ("Data tersebar di banyak instansi",
     "Satu pusat data terbuka (CSV/JSON) yang bisa dipakai bersama"),
    ("Keputusan berdasarkan perkiraan petugas di lapangan",
     "Keputusan berbasis skor risiko dan rekomendasi data"),
]

def buat_dashboard(df, data_nyata, rekomendasi):
    # Kartu status: pakai skor data nyata hari ini; jika tidak tersedia (tanpa internet), kembali ke simulasi
    if data_nyata["skor_nyata"] is not None:
        sumber_status = data_nyata["skor_nyata"].rename(columns={"status_nyata": "status_kartu"})
        judul_status = ("Status kecamatan hari ini <span class='label nyata'>DATA NYATA</span> "
                        "<span class='label konsep'>+ ASUMSI</span>")
    else:
        sumber_status = df.rename(columns={"status": "status_kartu"})
        judul_status = ("Status kecamatan <span class='label simulasi'>DATA SIMULASI</span> "
                        "<span class='kecil'>⚠️ data nyata tidak tersedia</span>")
    kartu_status = ""
    for s in ["Awas", "Siaga", "Waspada", "Aman"]:
        nama = sumber_status.loc[sumber_status["status_kartu"] == s, "kecamatan"].tolist()
        kartu_status += (f"<div class='kartu' style='border-top:6px solid {WARNA_STATUS[s]}'>"
                         f"<div class='angka'>{len(nama)}</div>{IKON_STATUS[s]} {s}"
                         f"<div class='kecil'>{', '.join(nama) or '–'}</div></div>")

    # Bagian data nyata (bisa kosong jika tidak ada internet)
    bagian_nyata = ""
    if data_nyata["hujan"] is not None:
        bagian_nyata += "<h3>🌧️ Curah hujan (mm) – Open-Meteo</h3>" + data_nyata["hujan"].rename(columns={
            "kecamatan": "Wilayah", "kelompok": "Kelompok", "hujan_3hari_lalu_mm": "3 hari lalu",
            "hujan_hari_ini_mm": "Hari ini", "prakiraan_maks_mm": "Prakiraan maks (s.d. +2 hari)",
        }).to_html(index=False, classes="tabel", border=0)
    if data_nyata["laut"]:
        laut = data_nyata["laut"]
        bagian_nyata += (f"<h3>🌊 Muka laut depan Tanjung Emas – Open-Meteo Marine</h3>"
                         f"<p>Tertinggi <b>{laut['tertinggi_m']} m</b> pukul {laut['jam_tertinggi']} WIB, "
                         f"terendah {laut['terendah_m']} m (tunggang pasang {laut['tunggang_m']} m)</p>"
                         f"<img src='grafik_pasang_laut.png' alt='Grafik muka laut 24 jam'>")
    if data_nyata["bmkg"]:
        bagian_nyata += "<h3>🌤️ Prakiraan cuaca 24 jam – BMKG</h3><ul>" + "".join(
            f"<li><b>{c['kelurahan']}</b>: {c['cuaca_24_jam']} (hujan ±{c['hujan_24_jam_mm']} mm)</li>"
            for c in data_nyata["bmkg"]) + "</ul>"
    if not bagian_nyata:
        bagian_nyata = "<p>⚠️ Data nyata tidak tersedia (cek koneksi internet).</p>"

    # Bagian riwayat 2024 s.d. hari ini
    riwayat = data_nyata["riwayat"]
    bagian_riwayat = ""
    if riwayat["harian_hujan"] is not None or riwayat["harian_laut"] is not None:
        bagian_riwayat += "<img src='grafik_riwayat.png' alt='Grafik riwayat bulanan'>"
    if riwayat["ringkasan"] is not None:
        tahun_ini = datetime.now().year
        bagian_riwayat += "<h3>🌧️ Ringkasan curah hujan per wilayah – arsip Open-Meteo</h3>" + riwayat["ringkasan"].rename(
            columns=lambda k: (f"Total {k[6:10]}" + (" (s.d. hari ini)" if k[6:10] == str(tahun_ini) else "") + " (mm)")
            if k.startswith("total_") else {
                "wilayah": "Wilayah", "maks_harian_mm": "Maks harian (mm)", "tanggal_maks": "Tanggal maks",
                "hari_hujan_lebat": f"Hari hujan lebat (≥{BATAS_HUJAN_LEBAT} mm)"}.get(k, k)
        ).to_html(index=False, classes="tabel", border=0)
        bagian_riwayat += ("<p class='kecil'>Resolusi model ±9–25 km, jadi kecamatan yang berdekatan "
                           "bisa bernilai sama.</p>")
        bagian_riwayat += "<h3>⛈️ 5 hari terbasah di Kota Semarang</h3>" + riwayat["ekstrem"].rename(columns={
            "tanggal": "Tanggal", "hujan_rata_kota_mm": "Hujan rata-rata kota (mm)",
            "hujan_maks_kecamatan_mm": "Hujan maks kecamatan (mm)"}).to_html(index=False, classes="tabel", border=0)
    if riwayat["pasang_tertinggi"] is not None:
        bagian_riwayat += "<h3>🌊 5 pasang laut tertinggi – arsip Open-Meteo Marine</h3>" + riwayat[
            "pasang_tertinggi"].rename(columns={"tanggal": "Tanggal", "muka_laut_maks_m": "Muka laut maks (m)"}
                                       ).to_html(index=False, classes="tabel", border=0)
    if not bagian_riwayat:
        bagian_riwayat = "<p>⚠️ Data riwayat tidak tersedia (cek koneksi internet).</p>"

    # Grafik skor: pakai data nyata hari ini; jika tidak tersedia (tanpa internet), kembali ke simulasi
    if data_nyata["skor_nyata"] is not None:
        bagian_grafik = ("<h2>Grafik skor risiko hari ini <span class='label nyata'>DATA NYATA</span> "
                         "<span class='label konsep'>+ ASUMSI</span></h2>"
                         "<img src='grafik_skor_nyata.png' alt='Grafik skor risiko data nyata per kecamatan'>"
                         "<p class='kecil'>Hujan dan pasang laut dari Open-Meteo, diperbarui setiap program "
                         "dijalankan; penurunan tanah dan paparan rob masih asumsi.</p>")
    else:
        bagian_grafik = ("<h2>Grafik skor risiko <span class='label simulasi'>DATA SIMULASI</span></h2>"
                         "<img src='grafik_skor_risiko.png' alt='Grafik skor risiko per kecamatan'>"
                         "<p class='kecil'>⚠️ Data nyata tidak tersedia (cek koneksi internet), "
                         "jadi ditampilkan grafik simulasi.</p>")

    # Bagian skor berbasis data nyata (status diberi warna)
    def warnai(status):
        return f"<b style='color:{WARNA_STATUS[status]}'>{IKON_STATUS[status]} {status}</b>"

    bagian_skor_nyata = ""
    if data_nyata["skor_nyata"] is not None:
        bagian_skor_nyata += "<h3>📡 Hari ini</h3><table class='tabel'><tr><th>Kecamatan</th><th>Hujan (mm)</th>" \
                             "<th>Pasang (cm)</th><th>Penurunan tanah (asumsi)</th><th>Skor nyata</th>" \
                             "<th>Status nyata</th><th>Status simulasi</th></tr>" + "".join(
            f"<tr><td>{b['kecamatan']}</td><td>{b['hujan_nyata_mm']}</td><td>{b['pasang_nyata_cm']:.0f}</td>"
            f"<td>{b['penurunan_tanah']} cm/th</td><td><b>{b['skor_nyata']}</b></td>"
            f"<td>{warnai(b['status_nyata'])}</td><td>{warnai(b['status_simulasi'])}</td></tr>"
            for _, b in data_nyata["skor_nyata"].iterrows()) + "</table>"
    if data_nyata["status_riwayat"] is not None:
        bagian_skor_nyata += (f"<h3>📚 Jumlah hari per status, {riwayat['periode']}</h3><table class='tabel'>"
                              "<tr><th>Kecamatan</th>" + "".join(f"<th>{warnai(s)}</th>" for s in
                                                                 ["Awas", "Siaga", "Waspada", "Aman"])
                              + "<th>Skor tertinggi</th><th>Tanggal</th></tr>" + "".join(
            f"<tr><td>{b['kecamatan']}</td><td>{b['hari_awas']}</td><td>{b['hari_siaga']}</td>"
            f"<td>{b['hari_waspada']}</td><td>{b['hari_aman']}</td><td>{b['skor_maks']:.1f}</td>"
            f"<td>{b['tanggal_skor_maks']}</td></tr>" for _, b in data_nyata["status_riwayat"].iterrows())
                              + "</table>")
    if not bagian_skor_nyata:
        bagian_skor_nyata = "<p>⚠️ Skor nyata tidak tersedia (cek koneksi internet).</p>"

    # Bagian prediksi 7 hari & rencana aksi Wali Kota
    prediksi = data_nyata["prediksi"]
    if prediksi:
        rencana, p = prediksi["rencana"], prediksi["per_kecamatan"]
        bagian_prediksi = (f"<div class='peringatan' style='border-left:6px solid {WARNA_STATUS[rencana['level']]}'>"
                           f"<b>{IKON_STATUS[rencana['level']]} Tingkat ancaman tertinggi: {rencana['level']}</b><br>"
                           f"{rencana['ringkasan']}</div><img src='grafik_prediksi.png' alt='Grafik prediksi'>")
        bagian_prediksi += "<h3>📅 Ringkasan per hari</h3>" + prediksi["harian"].rename(columns={
            "tanggal": "Tanggal", "hujan_kota_mm": "Hujan kota (mm)", "hujan_hulu_mm": "Hujan hulu (mm)",
            "pasang_maks_m": "Pasang maks (m)", "jam_puncak_pasang": "Jam puncak pasang",
            "wilayah_terdampak": "Wilayah terdampak (Waspada ke atas)"}).to_html(index=False, classes="tabel", border=0)

        daftar_tanggal = list(dict.fromkeys(p["tanggal"]))
        matriks = "<tr><th>Kecamatan</th>" + "".join(f"<th>{nama_tanggal(t)[:-5]}</th>" for t in daftar_tanggal) + "</tr>"
        for k in df["kecamatan"]:
            matriks += f"<tr><td>{k}</td>"
            for _, b in p[p["kecamatan"] == k].iterrows():
                w = WARNA_STATUS[b["status"]]
                matriks += (f"<td style='background:{w}22; border-left:4px solid {w}' "
                            f"title='{b['status']} – ancaman {b['ancaman']}'><b>{b['skor']:.0f}</b>"
                            f"<div class='kecil'>{b['status']}<br>{b['ancaman']}</div></td>")
            matriks += "</tr>"
        bagian_prediksi += f"<h3>🧮 Skor risiko per kecamatan per hari</h3><table class='tabel'>{matriks}</table>"

        bagian_prediksi += ("<h3>🏛️ Rencana aksi Wali Kota & jajaran</h3><table class='tabel'>"
                            "<tr><th>Waktu</th><th>Pelaksana</th><th>Tindakan</th></tr>" + "".join(
            f"<tr><td>{a['waktu']}</td><td><b>{a['pelaksana']}</b></td><td>{a['tindakan']}</td></tr>"
            for a in rencana["aksi"]) + "</table>")
    else:
        bagian_prediksi = "<p>⚠️ Prakiraan tidak tersedia (cek koneksi internet).</p>"

    bagian_rekomendasi = "".join(
        f"<div class='rek'><b>{IKON_STATUS.get(r['status'], '⛈️')} {r['status']} – {', '.join(r['wilayah'])}</b>"
        f"<ul>{''.join(f'<li>{t}</li>' for t in r['tindakan'])}</ul>"
        f"<span class='kecil'>Dasar: {r['dasar']}</span></div>" for r in rekomendasi)
    bagian_rekomendasi += ("<div class='rek'><b>💡 Jangka panjang (gagasan smart city)</b><ul>"
                           + "".join(f"<li>{t}</li>" for t in REKOMENDASI_JANGKA_PANJANG) + "</ul></div>")

    bagian_alur = "<span class='panah'>➜</span>".join(
        f"<div class='tahap'><div class='ikon'>{ikon}</div><b>{judul}</b><div class='kecil'>{ket}</div></div>"
        for ikon, judul, ket in ALUR_SISTEM)
    bagian_transformasi = "".join(f"<tr><td>{lama}</td><td>{baru}</td></tr>" for lama, baru in TRANSFORMASI)

    halaman = f"""<!doctype html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dashboard SIAGA ROB</title>
<style>
  body {{ margin:0; font-family:Arial, sans-serif; background:#f2f5f8; color:#1b2733; }}
  header {{ background:#0b3d5c; color:white; padding:18px 24px; }}
  header h1 {{ margin:0 0 4px; font-size:24px; }}
  main {{ max-width:1100px; margin:0 auto; padding:16px; }}
  section {{ background:white; border-radius:10px; padding:16px 20px; margin-bottom:16px;
             box-shadow:0 1px 4px rgba(0,0,0,.1); }}
  h2 {{ margin-top:0; font-size:19px; }}
  .label {{ display:inline-block; padding:2px 8px; border-radius:4px; font-size:12px; font-weight:bold; }}
  .simulasi {{ background:#fde2e2; color:#a31515; }}
  .nyata {{ background:#dff5e3; color:#1d6b30; }}
  .konsep {{ background:#e3ecfb; color:#1f4e9c; }}
  .peringatan {{ background:#fff8e6; padding:10px 14px; border-radius:8px; margin-bottom:12px; }}
  .alur {{ display:flex; gap:8px; flex-wrap:wrap; align-items:stretch; margin-bottom:14px; }}
  .tahap {{ flex:1; min-width:140px; background:#eef5fb; border-radius:8px; padding:10px; text-align:center; }}
  .ikon {{ font-size:28px; }}
  .panah {{ align-self:center; font-size:22px; color:#0b3d5c; }}
  .baris-kartu {{ display:flex; gap:12px; flex-wrap:wrap; }}
  .kartu {{ flex:1; min-width:120px; background:#f8fafc; border-radius:8px; padding:12px; text-align:center; }}
  .angka {{ font-size:32px; font-weight:bold; }}
  img {{ max-width:100%; }}
  iframe {{ width:100%; height:480px; border:0; border-radius:8px; }}
  .tabel {{ border-collapse:collapse; width:100%; font-size:14px; }}
  .tabel th, .tabel td {{ padding:6px 8px; border-bottom:1px solid #e3e8ee; text-align:left; }}
  .tabel th {{ background:#eef3f7; }}
  .rek {{ border-left:4px solid #0b3d5c; padding:4px 12px; margin-bottom:10px; }}
  .kecil {{ font-size:12px; color:#66727f; }}
</style></head><body>
<header>
  <h1>🌊 Dashboard SIAGA ROB Semarang</h1>
  Sistem peringatan dini banjir & rob · Gerakan Semarang SMART · diperbarui {data_nyata['waktu']}
</header>
<main>
  <section>
    <h2>{judul_status}</h2>
    <div class="baris-kartu">{kartu_status}</div>
  </section>
  <section>
    <h2>Bagaimana SIAGA ROB bekerja <span class="label konsep">RANCANGAN SISTEM</span></h2>
    <div class="alur">{bagian_alur}</div>
    <p class="kecil">Di aplikasi ini skor memakai data simulasi dan open data nyata; sensor IoT adalah rancangan
    untuk tahap penerapan.</p>
    <h3>Transformasi digital</h3>
    <table class="tabel">
      <tr><th>Cara konvensional</th><th>Dengan SIAGA ROB</th></tr>
      {bagian_transformasi}
    </table>
  </section>
  <section>
    {bagian_grafik}
  </section>
  <section>
    <h2>Peta risiko & posko pengungsian <span class="label simulasi">DATA SIMULASI</span></h2>
    <iframe src="peta_siaga_rob.html" title="Peta SIAGA ROB"></iframe>
  </section>
  <section>
    <h2>Kondisi nyata hari ini <span class="label nyata">DATA NYATA · OPEN DATA</span></h2>
    {bagian_nyata}
    <p class="kecil">Data nyata hanya sebagai pembanding, tidak dipakai untuk menghitung skor.</p>
  </section>
  <section>
    <h2>Riwayat {riwayat['periode']} <span class="label nyata">DATA NYATA · OPEN DATA</span></h2>
    {bagian_riwayat}
    <p class="kecil">Data model cuaca (reanalisis ERA5), diambil ulang sampai hari ini setiap program dijalankan.</p>
  </section>
  <section>
    <h2>Skor risiko berbasis data nyata <span class="label nyata">DATA NYATA</span>
        <span class="label konsep">+ ASUMSI</span></h2>
    <p>Rumus sama dengan skor simulasi: 40% hujan + 35% pasang laut + 25% penurunan tanah.
    Hujan dan pasang laut memakai data nyata Open-Meteo; pasang dikalikan paparan rob kecamatan (asumsi
    jarak ke pantai); penurunan tanah masih asumsi karena belum ada open data real-time.</p>
    {bagian_skor_nyata}
  </section>
  <section>
    <h2>Prediksi {HARI_PREDIKSI} hari ke depan & rencana aksi <span class="label nyata">DATA NYATA · PRAKIRAAN</span>
        <span class="label konsep">+ ASUMSI</span></h2>
    {bagian_prediksi}
    <p class="kecil">Prakiraan hujan dan muka laut dari Open-Meteo, diperbarui setiap program dijalankan. Paparan rob,
    penurunan tanah, dan banjir kiriman dari hulu (Ungaran) adalah asumsi. Prakiraan makin tidak pasti untuk hari
    yang makin jauh.</p>
  </section>
  <section>
    <h2>Rekomendasi untuk Pemerintah Kota</h2>
    {bagian_rekomendasi}
  </section>
  <section>
    <h2>Notifikasi warga <span class="label simulasi">DATA SIMULASI</span></h2>
    <iframe src="notifikasi_warga.html" title="Notifikasi warga"></iframe>
  </section>
</main></body></html>"""

    lokasi = os.path.join(FOLDER_HASIL, "dashboard_siaga_rob.html")
    with open(lokasi, "w", encoding="utf-8") as f:
        f.write(halaman)
    print(f"📋 Dashboard disimpan: {lokasi}")
    return lokasi


PORT_SERVER = 8000   # dashboard dibuka di http://localhost:8000


class PenanganSenyap(http.server.SimpleHTTPRequestHandler):
    """Melayani file di folder hasil/ tanpa mencetak log setiap permintaan ke terminal."""
    def do_GET(self):
        if self.path.split("?")[0] in ("/", "/index.html"):   # alamat utama langsung ke dashboard
            self.path = "/dashboard_siaga_rob.html"
        super().do_GET()

    def log_message(self, *args):
        pass


def jalankan_server():
    """Menjalankan server lokal di latar belakang; jika port terpakai, coba port berikutnya."""
    penangan = functools.partial(PenanganSenyap, directory=FOLDER_HASIL)
    for port in range(PORT_SERVER, PORT_SERVER + 10):
        try:
            server = http.server.ThreadingHTTPServer(("localhost", port), penangan)
        except OSError:
            continue
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return server, f"http://localhost:{port}/"
    raise OSError(f"Port {PORT_SERVER}–{PORT_SERVER + 9} semuanya terpakai")


# =====================================================================
# PROGRAM UTAMA
# =====================================================================
def main():
    garis("SIAGA ROB Semarang – Sistem Peringatan Dini Banjir & Rob")
    print("⚠️  Langkah 1–7 memakai DATA SIMULASI untuk tugas presentasi, bukan data resmi.")
    print("   Langkah 8–11 memakai DATA NYATA dari open data (Open-Meteo & BMKG).")

    garis("Langkah 1 – Data simulasi 10 kecamatan")
    df = siapkan_data()
    print(df[["kecamatan", "curah_hujan_mm", "pasang_laut_cm", "penurunan_tanah"]].to_string(index=False))

    garis("Langkah 2 & 3 – Skor risiko dan status")
    df["skor_risiko"] = hitung_skor(df["curah_hujan_mm"], df["pasang_laut_cm"], df["penurunan_tanah"])
    df["status"] = df["skor_risiko"].apply(tentukan_status)
    df["warna"] = df["status"].map(WARNA_STATUS)
    df = df.sort_values("skor_risiko", ascending=False).reset_index(drop=True)
    print(df[["kecamatan", "skor_risiko", "status"]].to_string(index=False))
    print("\n📊 Rekap status kecamatan:")
    for status in ["Awas", "Siaga", "Waspada", "Aman"]:
        print(f"   {status:<8}: {(df['status'] == status).sum()} kecamatan")

    garis("Langkah 4 – Grafik skor risiko")
    buat_grafik(df)

    garis("Langkah 5 – Peta interaktif")
    buat_peta(df)

    garis("Langkah 6 – Simulasi notifikasi ke warga")
    kirim_notifikasi(df)

    garis("Langkah 7 (Bonus) – Skenario hujan ekstrem")
    skenario_hujan(df, tambahan_hujan=40)   # ubah angka 40 untuk skenario lain

    garis("Langkah 8 – Data nyata hari ini (open data Semarang & sekitarnya)")
    data_nyata = ambil_data_nyata(df)

    garis(f"Langkah 9 – Riwayat data nyata sejak {TANGGAL_MULAI_RIWAYAT[:4]} sampai hari ini")
    data_nyata["riwayat"] = ambil_riwayat(df)

    garis("Langkah 10 – Skor risiko berbasis data nyata")
    skor_data_nyata(df, data_nyata)

    garis(f"Langkah 11 – Prediksi {HARI_PREDIKSI} hari ke depan & rencana aksi Wali Kota")
    prediksi_7_hari(df, data_nyata)

    garis("Langkah 12 – Rekomendasi otomatis untuk Pemerintah Kota")
    rekomendasi = buat_rekomendasi(df, data_nyata)

    garis("Langkah 13 – Ekspor data terbuka (CSV & JSON)")
    ekspor_data(df, data_nyata, rekomendasi)

    garis("Langkah 14 – Dashboard SIAGA ROB di localhost")
    buat_dashboard(df, data_nyata, rekomendasi)
    server, alamat = jalankan_server()
    webbrowser.open(alamat)
    print(f"🌐 Dashboard berjalan di: {alamat}")

    # Tampilkan jendela grafik; server tetap hidup sampai Ctrl+C
    plt.show()
    print("\n🖥️  Server lokal tetap berjalan. Tekan Ctrl+C di terminal untuk berhenti.")
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        server.shutdown()
        print("👋 Server dihentikan.")


if __name__ == "__main__":
    main()
