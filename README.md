# Analisis Komparatif Graf dan Kombinatorika terhadap Struktur Jaringan Operan Tim Bola Basket

**Efek Steph Curry pada Motion Offense Golden State Warriors**

Makalah Tugas IF1220 Matematika Diskrit — Semester II Tahun Akademik 2025/2026
Program Studi Teknik Informatika, Sekolah Teknik Elektro dan Informatika, Institut Teknologi Bandung

**Penulis:** Dhanesworo Muhammad Datiputro — 13525034

---

## Deskripsi Singkat

Penelitian ini menggunakan **teori graf berarah berbobot** dan **kombinatorika** untuk menguji secara kuantitatif fenomena "gravitasi pemain" dalam bola basket — klaim bahwa kehadiran Stephen Curry di lapangan mengubah struktur jaringan operan tim Golden State Warriors, meskipun ia tidak selalu menjadi pemegang bola.

Setiap pemain direpresentasikan sebagai simpul, dan operan antar pemain sebagai sisi berarah berbobot. Studi kasus menggunakan data resmi NBA Stats API musim 2021/2022, dibagi menjadi:

- **Periode A** — Curry bermain (69 pertandingan)
- **Periode B** — Curry absen karena cedera (13 pertandingan)

Metrik yang dibandingkan: derajat masuk/keluar berbobot, kepadatan graf (*density*), dan rasio realisasi "segitiga operan" menggunakan kombinasi C(n,3).

> **Catatan:** Hasil penelitian ini **tidak mendukung** hipotesis gravitasi sebagaimana dirumuskan di awal — density kedua periode identik (0,75), dan beberapa metrik justru lebih tinggi pada Periode B. Temuan ini dijelaskan lebih lanjut di bagian Analisis dan Kesimpulan makalah sebagai pergeseran peran distribusi bola ke pemain lain (Jordan Poole), bukan penurunan struktur jaringan tim.

---

## Isi Repository

```
.
├── makalah_gsw_full_FIXED.py     # Script utama pengambilan & pengolahan data
├── 13525034_Dhanesworo Muhammad Datiputro_Analisis Komparatif Graf dan Kombinatorika terhadap Struktur Jaringan Operan Tim Bola Basket Efek Steph Curry pada Motion Offense Golden State Warriors.pdf          # Makalah final (lihat juga versi .docx)
├── 13525034_Dhanesworo Muhammad Datiputro_Analisis Komparatif Graf dan Kombinatorika terhadap Struktur Jaringan Operan Tim Bola Basket Efek Steph Curry pada Motion Offense Golden State Warriors.docx
├── tabel_1_rotation_players.csv   # Daftar pemain rotasi
├── tabel_2_periods.csv            # Ringkasan periode penelitian
├── tabel_3_raw_passes.csv         # Edge list mentah (data operan asli)
├── tabel_4_normalized_passes.csv  # Edge list ternormalisasi (operan/game)
├── tabel_5_degree_comparison.csv  # Perbandingan derajat berbobot pemain
├── tabel_6_density.csv            # Perbandingan kepadatan graf G_A & G_B
├── tabel_7_active_triangles.csv   # Status segitiga operan tiap kombinasi
├── tabel_8_combinatorial_summary.csv  # Ringkasan analisis kombinatorial
├── gambar_1_graf_periode_A.png    # Visualisasi graf Periode A
├── gambar_2_graf_periode_B.png    # Visualisasi graf Periode B
└── README.md
```

---

## Cara Menjalankan Program

### 1. Persyaratan

- Python 3.9 atau lebih baru
- Koneksi internet (untuk mengambil data dari NBA Stats API)

### 2. Instalasi Dependency

```bash
pip install nba_api pandas networkx matplotlib numpy
```

### 3. Jalankan Script

```bash
python makalah_gsw_full_FIXED2.py
```

Program akan berjalan melalui 6 fase secara otomatis:

| Fase | Proses |
|------|--------|
| 1 | Menentukan pemain rotasi & membagi periode berdasarkan tanggal cedera Curry |
| 2 | Mengambil data operan mentah tiap pemain via `PlayerDashPtPass` |
| 3 | Normalisasi data + konstruksi graf berarah berbobot (G_A, G_B) |
| 4 | Menghitung derajat masuk/keluar dan kepadatan graf |
| 5 | Analisis kombinatorial — menghitung C(n,3) dan segitiga operan aktif |
| 6 | Mencetak ringkasan perbandingan akhir ke terminal |

**Estimasi waktu jalan:** 2–5 menit, tergantung kecepatan respons NBA API (terdapat jeda antar pemanggilan untuk menghindari *rate limit*).

### 4. Output

Semua file `tabel_*.csv` dan `gambar_*.png` di repository ini adalah hasil langsung dari menjalankan script di atas — bukan data simulasi. Menjalankan ulang script akan menimpa file-file tersebut dengan hasil baru (nilai dapat sedikit berbeda jika dijalankan pada musim/tanggal yang berbeda atau jika NBA API memperbarui datanya).

---

## Metodologi Singkat

- **Sumber data:** [`nba_api`](https://github.com/swar/nba_api) — *unofficial Python client* untuk NBA Stats API resmi.
- **Threshold sisi aktif:** ditentukan menggunakan kuartil pertama (Q1) dari distribusi seluruh bobot operan pada kedua periode, agar graf tidak otomatis "penuh" (density = 1) untuk seluruh pasangan pemain yang pernah saling mengoper sekali pun.
- **Kombinatorika:** jumlah seluruh kemungkinan kelompok tiga pemain dihitung dengan `math.comb(n, 3)`, kemudian setiap kombinasi diperiksa menggunakan `itertools.combinations` untuk menentukan status "segitiga aktif".

Penjelasan lengkap rumus, asumsi, dan interpretasi hasil dapat dibaca pada `Makalah_GSW_FINAL.pdf`.

---

## Referensi

Daftar referensi lengkap tersedia di bagian akhir makalah. Sumber utama data: [NBA Stats API](https://www.nba.com/stats) melalui library [`nba_api`](https://github.com/swar/nba_api).

---

## Lisensi & Pernyataan

Repository ini dibuat untuk keperluan Tugas Makalah IF1220 Matematika Diskrit, ITB. Seluruh isi makalah merupakan karya asli penulis sebagaimana dinyatakan pada bagian Pernyataan di akhir dokumen.
