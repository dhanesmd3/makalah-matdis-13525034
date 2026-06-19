import json, math, time, itertools, os
import pandas as pd
import networkx as nx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from nba_api.stats.static import teams
from nba_api.stats.endpoints import (
    LeagueDashPlayerStats,
    TeamGameLog,
    PlayerDashPtPass,
)

# ═══════════════════════════════════════════════════════════════════════════════
# KONFIGURASI
# ═══════════════════════════════════════════════════════════════════════════════
SEASON       = "2021-22"
TEAM_ABBR    = "GSW"
INJURY_DATE  = "2022-03-16"
MIN_MINUTES  = 15.0
TOP_N        = 8          # non-Curry rotation players

PASS_DELAY   = 2.5        # detik jeda antar API call (hindari rate-limit)

# ═══════════════════════════════════════════════════════════════════════════════
# FASE 1 — ROTATION PLAYERS & PERIODE
# ═══════════════════════════════════════════════════════════════════════════════
print("=" * 65)
print("FASE 1 — ROTATION PLAYERS & PERIODE")
print("=" * 65)

gsw_team  = [t for t in teams.get_teams() if t["abbreviation"] == TEAM_ABBR][0]
TEAM_ID   = gsw_team["id"]
print(f"Tim: {gsw_team['full_name']} | ID: {TEAM_ID}")

# — Statistik pemain —
print("\nMengambil statistik pemain GSW 2021-22 ...")
time.sleep(1)
stats_raw = LeagueDashPlayerStats(
    season=SEASON,
    team_id_nullable=TEAM_ID,
    per_mode_detailed="PerGame",
    season_type_all_star="Regular Season",
).get_data_frames()[0]

stats = stats_raw[["PLAYER_ID","PLAYER_NAME","GP","MIN"]].copy()
stats.columns = ["player_id","nama_pemain","games_played","avg_minutes"]
stats = stats.sort_values("avg_minutes", ascending=False).reset_index(drop=True)

# Pisahkan Curry
curry_row  = stats[stats["nama_pemain"].str.contains("Curry", case=False)].iloc[0]
others     = stats[~stats["nama_pemain"].str.contains("Curry", case=False)]
rotation   = others[others["avg_minutes"] >= MIN_MINUTES].head(TOP_N).copy()
rotation   = rotation.reset_index(drop=True)
rotation.insert(0, "no", range(1, len(rotation)+1))

print(f"\nCurry avg minutes: {curry_row['avg_minutes']:.1f}")
print(f"\nPemain rotasi (non-Curry, avg_min >= {MIN_MINUTES}):")
print(rotation[["no","nama_pemain","avg_minutes","games_played"]].to_string(index=False))

# Tambahkan Curry ke json untuk referensi
rotation_dict = {curry_row["nama_pemain"]: str(int(curry_row["player_id"]))}
for _, r in rotation.iterrows():
    rotation_dict[r["nama_pemain"]] = str(int(r["player_id"]))

# — Game Log —
print("\nMengambil game log GSW 2021-22 ...")
time.sleep(1)
gamelog = TeamGameLog(
    team_id=TEAM_ID,
    season=SEASON,
    season_type_all_star="Regular Season",
).get_data_frames()[0]

gamelog["GAME_DATE"] = pd.to_datetime(gamelog["GAME_DATE"])
split_dt = pd.to_datetime(INJURY_DATE)
period_A = gamelog[gamelog["GAME_DATE"] < split_dt]
period_B = gamelog[gamelog["GAME_DATE"] >= split_dt]

date_A_start = period_A["GAME_DATE"].min().strftime("%Y-%m-%d")
date_A_end   = period_A["GAME_DATE"].max().strftime("%Y-%m-%d")
date_B_start = period_B["GAME_DATE"].min().strftime("%Y-%m-%d")
date_B_end   = period_B["GAME_DATE"].max().strftime("%Y-%m-%d")
n_A, n_B     = len(period_A), len(period_B)

print(f"Periode A: {date_A_start} s/d {date_A_end} → {n_A} game")
print(f"Periode B: {date_B_start} s/d {date_B_end} → {n_B} game")

# — Simpan Tabel 1 & 2 —
tabel1 = rotation[["no","nama_pemain","avg_minutes","games_played"]].copy()
tabel1.columns = ["No","Nama Pemain","Avg Menit","Games Played"]
tabel1.to_csv("tabel_1_rotation_players.csv", index=False)

tabel2 = pd.DataFrame({
    "Periode"          : ["A (Curry ada)", "B (Curry absen)"],
    "Rentang Tanggal"  : [f"{date_A_start} – {date_A_end}", f"{date_B_start} – {date_B_end}"],
    "Jumlah Game"      : [n_A, n_B],
    "date_from"        : [date_A_start, date_B_start],
    "date_to"          : [date_A_end,   date_B_end],
})
tabel2.to_csv("tabel_2_periods.csv", index=False)

with open("rotation_players.json", "w") as f:
    json.dump(rotation_dict, f, indent=2)

print("\n✓ tabel_1_rotation_players.csv")
print("✓ tabel_2_periods.csv")
print("✓ rotation_players.json")


# ═══════════════════════════════════════════════════════════════════════════════
# FASE 2 — AMBIL DATA OPERAN MENTAH (PlayerDashPtPass)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 65)
print("FASE 2 — DATA OPERAN MENTAH")
print("=" * 65)

# Daftar pemain yang akan diambil datanya:
#   Periode A: Curry + semua rotation players
#   Periode B: semua rotation players (Curry tidak main)
periods_config = {
    "A": {
        "date_from": date_A_start,
        "date_to"  : date_A_end,
        "players"  : rotation_dict,   # Curry + rotation
    },
    "B": {
        "date_from": date_B_start,
        "date_to"  : date_B_end,
        "players"  : {k: v for k, v in rotation_dict.items()
                      if "Curry" not in k},   # tanpa Curry
    },
}

def normalize_name(raw_name):
    """Konversi format 'Last, First' (dari NBA API) menjadi 'First Last'.
    Jika sudah format 'First Last' atau tidak ada koma, kembalikan apa adanya."""
    raw_name = str(raw_name).strip()
    if "," in raw_name:
        last, first = raw_name.split(",", 1)
        return f"{first.strip()} {last.strip()}"
    return raw_name

rows = []
for periode, cfg in periods_config.items():
    print(f"\nPeriode {periode} ({cfg['date_from']} s/d {cfg['date_to']}):")
    for nama, pid in cfg["players"].items():
        print(f"  Mengambil data operan {nama} ...", end=" ", flush=True)
        try:
            time.sleep(PASS_DELAY)
            pt = PlayerDashPtPass(
                player_id=int(pid),
                team_id=TEAM_ID,
                per_mode_simple="Totals",
                season=SEASON,
                season_type_all_star="Regular Season",
                date_from_nullable=cfg["date_from"],
                date_to_nullable=cfg["date_to"],
            )
            made = pt.get_data_frames()[0]   # PassesMade
            if made.empty:
                print("(kosong)")
                continue
            for _, row in made.iterrows():
                to_raw = row.get("PASS_TO", row.get("PLAYER_NAME_LAST_FIRST", ""))
                rows.append({
                    "periode"      : periode,
                    "from_player"  : nama,
                    "to_player"    : normalize_name(to_raw),
                    "total_passes" : int(row.get("PASS", row.get("FREQUENCY", 0))),
                    "total_assists": int(row.get("AST", 0)),
                })
            print(f"✓ ({len(made)} penerima)")
        except Exception as e:
            print(f"ERROR: {e}")

tabel3 = pd.DataFrame(rows)
tabel3.to_csv("tabel_3_raw_passes.csv", index=False)
print("\n✓ tabel_3_raw_passes.csv")
print(tabel3.head(10).to_string(index=False))

# ── Debug check: pastikan nama to_player cocok dengan daftar rotasi ──────────
all_rotation_names = set(rotation_dict.keys())
unmatched = sorted(set(tabel3["to_player"]) - all_rotation_names)
if unmatched:
    print(f"\n⚠ PERINGATAN: {len(unmatched)} nama penerima TIDAK COCOK dengan daftar rotasi:")
    for u in unmatched[:10]:
        print(f"    - {u!r}")
    print("  (Ini wajar untuk pemain non-rotasi yang menerima operan sesekali, "
          "tapi cek apakah ada nama rotasi yang salah ketik/format.)")
else:
    print("\n✓ Semua nama to_player cocok dengan daftar rotasi.")


# ═══════════════════════════════════════════════════════════════════════════════
# FASE 3 — NORMALISASI & KONSTRUKSI GRAF
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 65)
print("FASE 3 — NORMALISASI & KONSTRUKSI GRAF")
print("=" * 65)

if tabel3.empty:
    raise SystemExit("Tidak ada data operan. Cek koneksi ke NBA API.")

# Daftar simpul: hanya rotation players non-Curry (untuk kedua graf)
# Curry tetap menjadi simpul di G_A
rotation_names    = list(rotation["nama_pemain"])
curry_name        = curry_row["nama_pemain"]
nodes_B           = rotation_names                     # G_B: tanpa Curry
nodes_A           = [curry_name] + rotation_names      # G_A: dengan Curry

# Filter hanya edge antar pemain rotasi
def filter_edges(df, periode, node_list):
    d = df[df["periode"] == periode].copy()
    d = d[d["from_player"].isin(node_list) & d["to_player"].isin(node_list)]
    d = d[d["from_player"] != d["to_player"]]    # hapus self-loop
    return d

raw_A = filter_edges(tabel3, "A", nodes_A)
raw_B = filter_edges(tabel3, "B", nodes_B)

# Normalisasi per game
def normalize(df, n_games):
    agg = df.groupby(["from_player","to_player"], as_index=False).agg(
        total_passes=("total_passes","sum"),
        total_assists=("total_assists","sum")
    )
    agg["avg_passes_per_game"]  = (agg["total_passes"]  / n_games).round(2)
    agg["avg_assists_per_game"] = (agg["total_assists"] / n_games).round(2)
    return agg

norm_A = normalize(raw_A, n_A)
norm_B = normalize(raw_B, n_B)

norm_A.insert(0, "periode", "A")
norm_B.insert(0, "periode", "B")
tabel4 = pd.concat([norm_A, norm_B], ignore_index=True)
tabel4.to_csv("tabel_4_normalized_passes.csv", index=False)
print("✓ tabel_4_normalized_passes.csv")

# ── Threshold sisi aktif ──────────────────────────────────────────────────
# PENTING: hanya pasangan dengan avg_passes_per_game >= threshold dianggap
# "sisi aktif". Tanpa filter ini, semua pasangan otomatis terhubung dan
# density selalu 1.0 (tidak informatif untuk perbandingan A vs B).
all_weights_combined = (
    norm_A["avg_passes_per_game"].tolist() +
    norm_B["avg_passes_per_game"].tolist()
)
THRESHOLD_ACTIVE = float(np.percentile(all_weights_combined, 25)) if all_weights_combined else 1.0
print(f"\nThreshold sisi aktif (Q1 gabungan A & B): {THRESHOLD_ACTIVE:.2f} operan/game")

# Bangun DiGraph — hanya edge >= threshold yang dimasukkan
def build_graph(norm_df, node_list, thr):
    G = nx.DiGraph()
    G.add_nodes_from(node_list)
    for _, r in norm_df.iterrows():
        if (r["from_player"] in node_list and r["to_player"] in node_list
                and r["avg_passes_per_game"] >= thr):
            G.add_edge(r["from_player"], r["to_player"],
                       weight=r["avg_passes_per_game"])
    return G

G_A = build_graph(norm_A, nodes_A, THRESHOLD_ACTIVE)
G_B = build_graph(norm_B, nodes_B, THRESHOLD_ACTIVE)

print(f"G_A: {G_A.number_of_nodes()} simpul, {G_A.number_of_edges()} sisi aktif")
print(f"G_B: {G_B.number_of_nodes()} simpul, {G_B.number_of_edges()} sisi aktif")

# ── Safety check: berhenti dengan pesan jelas jika graf kosong ──────────────
if G_A.number_of_edges() == 0 or G_B.number_of_edges() == 0:
    print("\n" + "!" * 65)
    print("ERROR: Graf kosong (0 sisi aktif). Kemungkinan penyebab:")
    print("  1. Nama 'from_player'/'to_player' di tabel_3 tidak cocok dengan")
    print("     nama di daftar rotasi (cek peringatan ⚠ di atas).")
    print("  2. Threshold terlalu tinggi dibanding data yang ada.")
    print(f"     Threshold saat ini: {THRESHOLD_ACTIVE:.2f}")
    print("  Cek isi tabel_4_normalized_passes.csv secara manual untuk debug.")
    print("!" * 65)
    raise SystemExit("Dihentikan: graf kosong, lihat pesan error di atas.")

# — Visualisasi graf —
def visualize_graph(G, title, filename, curry_node=None, figsize=(10,8)):
    weights  = [G[u][v]["weight"] for u,v in G.edges()]
    max_w    = max(weights) if weights else 1

    # Ukuran node = total weighted degree
    node_strengths = dict(G.degree(weight="weight"))
    max_s = max(node_strengths.values()) if node_strengths else 1

    # Layout
    pos = nx.spring_layout(G, seed=42, k=2.5)

    fig, ax = plt.subplots(figsize=figsize)
    ax.set_facecolor("#f8f9fa")
    fig.patch.set_facecolor("#f8f9fa")

    # Warna node
    node_colors = []
    for n in G.nodes():
        if n == curry_node:
            node_colors.append("#e74c3c")   # merah untuk Curry
        else:
            node_colors.append("#2c7bb6")   # biru untuk yang lain

    node_sizes  = [300 + 1200 * (node_strengths.get(n,0) / max_s)
                   for n in G.nodes()]

    # Gambar node
    nx.draw_networkx_nodes(G, pos, ax=ax,
                           node_color=node_colors,
                           node_size=node_sizes, alpha=0.9)

    # Gambar edge (ketebalan = bobot)
    edge_widths = [0.5 + 3.5 * (w / max_w) for w in weights]
    edge_colors = ["#555555"] * len(weights)
    nx.draw_networkx_edges(G, pos, ax=ax,
                           width=edge_widths,
                           edge_color=edge_colors,
                           alpha=0.55,
                           arrows=True,
                           arrowsize=12,
                           connectionstyle="arc3,rad=0.1")

    # Label nama (singkat)
    labels = {n: n.split()[-1] for n in G.nodes()}   # pakai nama belakang
    nx.draw_networkx_labels(G, pos, labels=labels, ax=ax,
                            font_size=8, font_weight="bold")

    # Edge weight label (hanya edge besar agar tidak terlalu ramai)
    if weights:
        threshold_label = sorted(weights)[-min(15, len(weights))]
        edge_labels = {(u,v): f"{G[u][v]['weight']:.1f}"
                       for u,v in G.edges()
                       if G[u][v]["weight"] >= threshold_label}
        nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels,
                                     ax=ax, font_size=6, alpha=0.8)

    # Legend
    patches = [
        mpatches.Patch(color="#2c7bb6", label="Pemain Rotasi"),
    ]
    if curry_node:
        patches.insert(0, mpatches.Patch(color="#e74c3c", label="Stephen Curry"))
    ax.legend(handles=patches, loc="upper left", fontsize=8)

    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    ax.axis("off")
    plt.tight_layout()
    plt.savefig(filename, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"✓ {filename}")

visualize_graph(G_A,
    "Gambar 1. Jaringan Operan GSW — Periode A (Curry Bermain)",
    "gambar_1_graf_periode_A.png",
    curry_node=curry_name)

visualize_graph(G_B,
    "Gambar 2. Jaringan Operan GSW — Periode B (Curry Absen)",
    "gambar_2_graf_periode_B.png",
    curry_node=None)


# ═══════════════════════════════════════════════════════════════════════════════
# FASE 4 — DERAJAT & KEPADATAN
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 65)
print("FASE 4 — DERAJAT & KEPADATAN")
print("=" * 65)

def degree_table(G_a, G_b, node_list):
    rows = []
    for p in node_list:
        in_a  = G_a.in_degree(p)              if G_a.has_node(p) else 0
        out_a = G_a.out_degree(p)             if G_a.has_node(p) else 0
        win_a = G_a.in_degree(p, weight="weight")  if G_a.has_node(p) else 0
        wout_a= G_a.out_degree(p, weight="weight") if G_a.has_node(p) else 0
        in_b  = G_b.in_degree(p)              if G_b.has_node(p) else 0
        out_b = G_b.out_degree(p)             if G_b.has_node(p) else 0
        win_b = G_b.in_degree(p, weight="weight")  if G_b.has_node(p) else 0
        wout_b= G_b.out_degree(p, weight="weight") if G_b.has_node(p) else 0
        rows.append({
            "Nama Pemain"         : p,
            "In-Degree A"         : in_a,
            "Out-Degree A"        : out_a,
            "W.In-Degree A"       : round(win_a, 2),
            "W.Out-Degree A"      : round(wout_a, 2),
            "In-Degree B"         : in_b,
            "Out-Degree B"        : out_b,
            "W.In-Degree B"       : round(win_b, 2),
            "W.Out-Degree B"      : round(wout_b, 2),
            "Δ W.In"              : round(win_a  - win_b,  2),
            "Δ W.Out"             : round(wout_a - wout_b, 2),
        })
    return pd.DataFrame(rows)

tabel5 = degree_table(G_A, G_B, rotation_names)
tabel5.to_csv("tabel_5_degree_comparison.csv", index=False)
print("✓ tabel_5_degree_comparison.csv")
print(tabel5.to_string(index=False))

# Density
def calc_density(G):
    n = G.number_of_nodes()
    e = G.number_of_edges()
    max_e = n * (n - 1)
    d = e / max_e if max_e > 0 else 0
    return n, e, max_e, round(d, 4)

nA, eA, maxA, dA = calc_density(G_A)
nB, eB, maxB, dB = calc_density(G_B)

tabel6 = pd.DataFrame({
    "Periode"           : ["A (Curry ada)", "B (Curry absen)"],
    "n (simpul)"        : [nA, nB],
    "Max Sisi (n(n-1))" : [maxA, maxB],
    "Sisi Aktif"        : [eA, eB],
    "Density"           : [dA, dB],
})
tabel6.to_csv("tabel_6_density.csv", index=False)
print("\n✓ tabel_6_density.csv")
print(tabel6.to_string(index=False))


# ═══════════════════════════════════════════════════════════════════════════════
# FASE 5 — ANALISIS KOMBINATORIAL SEGITIGA
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 65)
print("FASE 5 — ANALISIS KOMBINATORIAL SEGITIGA")
print("=" * 65)

# Gunakan pemain rotasi non-Curry saja agar komparasi adil (n sama di A dan B)
n_rot = len(rotation_names)
C_n_3 = math.comb(n_rot, 3)
print(f"\nn (pemain rotasi non-Curry) = {n_rot}")
print(f"C({n_rot}, 3) = {C_n_3}  ← total kemungkinan segitiga")

# Gunakan threshold yang sama dengan konstruksi graf (THRESHOLD_ACTIVE) agar konsisten
threshold = THRESHOLD_ACTIVE
print(f"Threshold (Q1 bobot, sama dengan konstruksi graf): {threshold:.2f} operan/game")

def find_active_triangles(G, nodes, thr):
    """Cek setiap C(n,3): apakah ketiga pasangan punya edge >= threshold (dua arah)"""
    active = []
    for trio in itertools.combinations(nodes, 3):
        a, b, c = trio
        pairs = [(a,b),(b,a),(a,c),(c,a),(b,c),(c,b)]
        # Minimal salah satu arah tiap pasangan harus ada dan >= threshold
        def pair_connected(x, y):
            w_xy = G[x][y]["weight"] if G.has_edge(x,y) else 0
            w_yx = G[y][x]["weight"] if G.has_edge(y,x) else 0
            return max(w_xy, w_yx) >= thr
        if pair_connected(a,b) and pair_connected(a,c) and pair_connected(b,c):
            active.append(trio)
    return active

triangles_A = find_active_triangles(G_A, rotation_names, threshold)
triangles_B = find_active_triangles(G_B, rotation_names, threshold)

print(f"\nSegitiga aktif Periode A: {len(triangles_A)} / {C_n_3}")
print(f"Segitiga aktif Periode B: {len(triangles_B)} / {C_n_3}")

# Tabel 7 — daftar segitiga
rows7 = []
all_trios = set(itertools.combinations(rotation_names, 3))
for trio in all_trios:
    status_A = "AKTIF" if trio in [tuple(t) for t in triangles_A] else "tidak aktif"
    status_B = "AKTIF" if trio in [tuple(t) for t in triangles_B] else "tidak aktif"
    rows7.append({
        "Pemain 1"  : trio[0],
        "Pemain 2"  : trio[1],
        "Pemain 3"  : trio[2],
        "Status A"  : status_A,
        "Status B"  : status_B,
    })
tabel7 = pd.DataFrame(rows7)
tabel7.to_csv("tabel_7_active_triangles.csv", index=False)
print("✓ tabel_7_active_triangles.csv")

# Tabel 8 — ringkasan
rasio_A = round(len(triangles_A) / C_n_3, 4) if C_n_3 > 0 else 0
rasio_B = round(len(triangles_B) / C_n_3, 4) if C_n_3 > 0 else 0
tabel8 = pd.DataFrame({
    "Periode"          : ["A (Curry ada)", "B (Curry absen)"],
    "n"                : [n_rot, n_rot],
    "C(n,3)"           : [C_n_3, C_n_3],
    "Threshold"        : [round(threshold, 2)] * 2,
    "Segitiga Aktif"   : [len(triangles_A), len(triangles_B)],
    "Rasio Realisasi"  : [rasio_A, rasio_B],
})
tabel8.to_csv("tabel_8_combinatorial_summary.csv", index=False)
print("✓ tabel_8_combinatorial_summary.csv")
print(tabel8.to_string(index=False))


# ═══════════════════════════════════════════════════════════════════════════════
# FASE 6 — RINGKASAN INTERPRETASI
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 65)
print("FASE 6 — RINGKASAN HASIL (untuk Analisis F)")
print("=" * 65)

print(f"\n  Density G_A (Curry ada)    : {dA}")
print(f"  Density G_B (Curry absen)  : {dB}")
print(f"  → G_A {'LEBIH PADAT' if dA > dB else 'LEBIH RENGGANG'} dari G_B")

avg_win_A  = tabel5["W.In-Degree A"].mean()
avg_win_B  = tabel5["W.In-Degree B"].mean()
print(f"\n  Avg W.In-Degree non-Curry A: {avg_win_A:.2f}")
print(f"  Avg W.In-Degree non-Curry B: {avg_win_B:.2f}")
print(f"  → Pemain non-Curry menerima "
      f"{'LEBIH BANYAK' if avg_win_A > avg_win_B else 'LEBIH SEDIKIT'} "
      f"operan saat Curry ada")

print(f"\n  Rasio segitiga A: {rasio_A:.4f}")
print(f"  Rasio segitiga B: {rasio_B:.4f}")
print(f"  → Pola segitiga "
      f"{'LEBIH BANYAK' if rasio_A > rasio_B else 'LEBIH SEDIKIT'} "
      f"saat Curry ada")

consistent = (dA > dB) and (avg_win_A > avg_win_B) and (rasio_A > rasio_B)
print(f"\n  Ketiga metrik {'KONSISTEN' if consistent else 'TIDAK KONSISTEN'} "
      f"mendukung hipotesis gravitasi Curry.")

print("\n" + "=" * 65)
print("SELESAI — Semua file output tersimpan di folder ini.")
print("=" * 65)