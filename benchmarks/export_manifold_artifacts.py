"""
Export manifold artifacts from real build_manifold() pipeline.

10 domain datasets across finance, genomics, weather, retail, ecology, etc.
Each 100k randomly-drawn points with high cardinality axes.
Uses numpy for vectorized sampling and realistic distributions.

Usage:  python benchmarks/export_manifold_artifacts.py
"""
import csv, json, math, os, sys, time
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "binomialhash", "src"))
from binomialhash.manifold import build_manifold
from binomialhash.schema import infer_schema

ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "manifold_artifacts")
np.random.seed(42)

N = 100000


# ═══════════════════════════════════════════════════════════════════════════════
# FINANCE — 5 topologies
# ═══════════════════════════════════════════════════════════════════════════════

def gen_patch_l2_book():
    """500k L2 book snapshots. 50 tickers × 20 venues = 1000 cells.
    Imbalance ~ beta (bounded), spread ~ lognormal, depth ~ gamma."""
    tickers = ["SPY","QQQ","AAPL","TSLA","NVDA","AMZN","META","MSFT","GOOG","AMD",
              "JPM","V","JNJ","WMT","PG","UNH","HD","DIS","BAC","XOM",
              "INTC","NFLX","CRM","ORCL","ADBE","CSCO","PEP","KO","ABT","T",
              "COST","NKE","SBUX","MCD","BA","GE","CAT","DE","UPS","FDX",
              "LMT","HON","AXP","GS","MS","BLK","SCHW","CME","ICE","CB"]
    venues = ["ARCA","EDGX","BZX","XNAS","XNYS","PHLX","CBOE","ISE","BOX","MEMX",
              "MIAX","PEARL","GEMX","BATS","BYX","C2","GEM2","MRX","PSX","DRF"]
    tk_w = np.array([50, 35, 28, 22, 18, 15, 12, 10, 8, 7] + [5] * 15 + [3] * 25, dtype=float)
    vn_w = np.array([40, 15, 12, 28, 18, 6, 5, 4, 3, 3] + [2] * 5 + [1] * 5, dtype=float)
    tk_w, vn_w = tk_w / tk_w.sum(), vn_w / vn_w.sum()
    ti = np.random.choice(len(tickers), size=N, p=tk_w)
    vi = np.random.choice(len(venues), size=N, p=vn_w)
    imb = np.clip(np.random.beta(2 + ti * 0.1, 2 + (49 - ti) * 0.1, N) * 2 - 1, -0.99, 0.99)
    sp = np.random.lognormal(-4 + vi * 0.1, 0.5, N)
    dp = np.random.gamma(3, 80 + ti * 15 + vi * 20, N)
    fm = 0.3 * imb + 0.2 * np.log1p(sp) + np.random.normal(0, 0.06, N)
    return [{"ticker": tickers[ti[i]], "venue": venues[vi[i]],
             "imbalance": round(float(imb[i]), 6), "spread": round(float(sp[i]), 6),
             "depth": round(float(dp[i]), 2), "future_move": round(float(fm[i]), 6)}
            for i in range(N)], "1_patch_l2_book"


def gen_cylinder_macro():
    """500k macro observations. 30 countries × 120 quarterly dates = 3600 cells.
    AR(2) with cyclical roots for GDP; date axis periodic (business cycle)."""
    countries = ["US","UK","DE","JP","CN","BR","IN","AU","CA","KR","FR","IT","ES","MX","ID",
                 "PL","NL","CH","SE","SG","RU","ZA","TR","SA","AR","CL","CO","EG","TH","MY"]
    dates = [f"{y}-{1+q*3:02d}-01" for y in range(1995, 2026) for q in range(4)]
    ctry_w = np.array([35, 22, 18, 16, 14, 8, 7, 6, 6, 6, 5, 5, 4, 4, 4, 3, 3, 3, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2], dtype=float)
    date_w = np.ones(len(dates)) + np.random.uniform(0, 0.4, len(dates))
    ctry_w, date_w = ctry_w / ctry_w.sum(), date_w / date_w.sum()
    ci = np.random.choice(len(countries), size=N, p=ctry_w)
    di = np.random.choice(len(dates), size=N, p=date_w)
    bg = np.random.uniform(1.0, 3.5, len(countries))
    bi = np.random.uniform(1.5, 4.0, len(countries))
    phase = 2 * np.pi * np.arange(len(dates)) / len(dates)
    g_cycle = 1.8 * np.sin(phase) + 1.0 * np.cos(phase)
    inf_cycle = 1.0 * np.cos(phase) + 0.5 * np.sin(phase)
    g = bg[ci] + g_cycle[di] + np.random.normal(0, 0.5, N)
    inf = bi[ci] + inf_cycle[di] + np.random.normal(0, 0.4, N)
    rate = np.maximum(0.1, bi[ci] * 0.35 + 0.3 * inf + np.random.normal(0, 0.25, N))
    return [{"country": countries[ci[i]], "date": dates[di[i]],
             "gdp_growth": round(float(g[i]), 4), "inflation": round(float(inf[i]), 4),
             "policy_rate": round(float(rate[i]), 4)} for i in range(N)], "2_cylinder_macro"


def gen_torus_options():
    """500k option trades. 60 expiries × 80 strikes = 4800 cells.
    IV smile (parabolic in moneyness); both axes periodic."""
    dates = [f"2024-{1+(m//4):02d}-{1+(m%4)*7:02d}" for m in range(60)]
    strikes = np.arange(65, 145)
    atm = 100.0
    date_w = np.exp(-0.06 * np.arange(60)) + 0.35
    strike_w = np.exp(-0.35 * ((strikes - atm) / 15) ** 2) + 0.2
    date_w, strike_w = date_w / date_w.sum(), strike_w / strike_w.sum()
    di = np.random.choice(60, size=N, p=date_w)
    si = np.random.choice(len(strikes), size=N, p=strike_w)
    m = (strikes[si] - atm) / 25.0
    iv = 0.20 + 0.10 * m ** 2 + np.random.normal(0, 0.03, N)
    oi = np.maximum(10, (5000 * np.exp(-m ** 2) + np.random.normal(0, 350, N)).astype(int))
    vol = np.maximum(0, (oi * np.random.uniform(0.1, 0.85, N)).astype(int))
    return [{"expiry_date": dates[di[i]], "strike": int(strikes[si[i]]),
             "implied_vol": round(float(iv[i]), 6), "open_interest": int(oi[i]), "volume": int(vol[i])}
            for i in range(N)], "3_torus_options"


def gen_mobius_momentum():
    """500k factor observations. 20 sectors × 36 months = 720 cells.
    Momentum reversal over lookback (short +, long -); month wraps with sign flip."""
    sectors = ["Tech","Health","Energy","Finance","Consumer","Industrial","Utilities","Materials",
               "RealEstate","Comm","Staples","Discretionary","Healthcare","Industrials","Banks","Insurance",
               "Pharma","Semis","Airlines","Retail"]
    months = [f"{2021 + (m//12)}-{(m%12)+1:02d}-01" for m in range(36)]
    sec_w = np.array([28, 14, 12, 24, 12, 10, 8, 8, 5, 5, 5, 5, 4, 4, 4, 4, 4, 4, 3, 3], dtype=float)
    month_w = np.ones(36) + np.random.uniform(0, 0.25, 36)
    sec_w, month_w = sec_w / sec_w.sum(), month_w / month_w.sum()
    base_mom = np.random.uniform(0.3, 0.7, 20)
    base_rev = np.random.uniform(0.2, 0.5, 20)
    si = np.random.choice(20, size=N, p=sec_w)
    mi = np.random.choice(36, size=N, p=month_w)
    reversal = np.cos(np.pi * mi / 35)
    momentum = base_mom[si] * reversal + np.random.normal(0, 0.10, N)
    mean_rev = base_rev[si] * reversal + np.random.normal(0, 0.07, N)
    signal = (base_mom[si] + base_rev[si]) * 0.5 * reversal + np.random.normal(0, 0.08, N)
    return [{"sector": sectors[si[i]], "month": months[mi[i]],
             "momentum": round(float(momentum[i]), 6),
             "mean_reversion": round(float(mean_rev[i]), 6),
             "signal_strength": round(float(signal[i]), 6)} for i in range(N)], "4_mobius_momentum"


def gen_klein_greeks():
    """500k greek snapshots. 60 dates × 61 moneyness = 3660 cells.
    Date wraps (term structure). Moneyness wraps with sign reversal (delta flips)."""
    dates = [f"2024-{1+(m//28):02d}-{1+(m%28):02d}" for m in range(60)]
    moneyness = np.arange(-30, 31)
    date_w = np.ones(60) + np.random.uniform(0, 0.15, 60)
    money_w = np.exp(-0.4 * (moneyness / 8) ** 2) + 0.12
    date_w, money_w = date_w / date_w.sum(), money_w / money_w.sum()
    di = np.random.choice(60, size=N, p=date_w)
    mi = np.random.choice(61, size=N, p=money_w)
    m_frac = moneyness[mi] / 30.0
    phase_d = 2 * np.pi * np.arange(60) / 60
    gamma_base = 0.03 * np.sin(phase_d) + np.random.normal(0, 0.005, 60)
    vega_base = 0.05 * np.cos(phase_d) + np.random.normal(0, 0.008, 60)
    gamma_net = gamma_base[di] + (0.06 + 0.02 * np.sin(phase_d[di])) * m_frac + np.random.normal(0, 0.012, N)
    vega_net = vega_base[di] + (0.12 + 0.04 * np.cos(phase_d[di])) * m_frac + np.random.normal(0, 0.015, N)
    theta_net = -0.02 * np.sin(phase_d[di]) - (0.015 + 0.005 * np.sin(phase_d[di])) * m_frac + np.random.normal(0, 0.005, N)
    iv_level = 0.22 + 0.12 * np.cos(phase_d[di]) + np.random.normal(0, 0.025, N)
    return [{"trade_date": dates[di[i]], "moneyness": int(moneyness[mi[i]]),
             "gamma_net": round(float(gamma_net[i]), 6), "vega_net": round(float(vega_net[i]), 6),
             "theta_net": round(float(theta_net[i]), 6), "iv_level": round(float(iv_level[i]), 6)}
            for i in range(N)], "5_klein_greeks"


# ═══════════════════════════════════════════════════════════════════════════════
# NON-FINANCE DOMAINS — patch, cylinder, torus, mobius
# ═══════════════════════════════════════════════════════════════════════════════

def gen_patch_genomics():
    """500k gene expression samples. 80 genes × 40 tissues = 3200 cells.
    Expression ~ lognormal; p-value ~ beta (skewed to small)."""
    genes = [f"G{i:04d}" for i in range(80)]
    tissues = ["Brain","Liver","Heart","Kidney","Lung","Muscle","Skin","Blood","Fat","Gut",
               "Pancreas","Spleen","Thyroid","Adrenal","Ovary","Testis","Eye","Ear","Bone","Marrow",
               "Lymph","Thymus","Stomach","Colon","Bladder","Prostate","Uterus","Breast","Cervix","Placenta",
               "Fetal_liver","Fetal_brain","Stem","iPSC","Neuron","Astrocyte","Cardiomyocyte","Hepatocyte","Epithelial","Fibroblast"]
    g_w = np.exp(-0.02 * np.arange(80)) + 0.5
    t_w = np.array([15, 12, 10, 10, 9, 8, 8, 12, 7, 8] + [5] * 15 + [3] * 15, dtype=float)
    g_w, t_w = g_w / g_w.sum(), t_w / t_w.sum()
    gi = np.random.choice(80, size=N, p=g_w)
    ti = np.random.choice(40, size=N, p=t_w)
    expr = np.random.lognormal(gi * 0.02 + ti * 0.03, 0.4, N)
    pval = np.clip(np.random.beta(0.5, 2, N), 0.001, 0.99)
    fc = np.where(expr > 5, np.random.normal(0.6, 0.3, N), np.random.normal(0.1, 0.4, N))
    return [{"gene": genes[gi[i]], "tissue": tissues[ti[i]],
             "expression": round(float(expr[i]), 6), "p_value": round(float(pval[i]), 6),
             "fold_change": round(float(fc[i]), 6)} for i in range(N)], "6_patch_genomics"


def gen_cylinder_weather():
    """500k weather observations. 60 cities × 72 months = 4320 cells.
    Seasonal cycle (temp, precip); month axis periodic."""
    cities = [f"C{i:03d}" for i in range(60)]
    months = [f"{2018 + (m//12)}-{(m%12)+1:02d}-15" for m in range(72)]
    city_w = np.exp(-0.03 * np.arange(60)) + 0.3
    month_w = np.ones(72) + np.random.uniform(0, 0.3, 72)
    city_w, month_w = city_w / city_w.sum(), month_w / month_w.sum()
    base_t = np.random.uniform(5, 25, 60)
    base_p = np.random.uniform(20, 120, 60)
    ci = np.random.choice(60, size=N, p=city_w)
    mi = np.random.choice(72, size=N, p=month_w)
    phase = 2 * np.pi * (mi % 12) / 12
    temp = base_t[ci] + 12 * np.sin(phase) + np.random.normal(0, 3, N)
    precip = np.maximum(0, base_p[ci] * 0.3 + 50 * np.cos(phase) + np.random.normal(0, 25, N))
    humidity = 40 + 30 * np.sin(phase + 0.5) + np.random.normal(0, 10, N)
    return [{"city": cities[ci[i]], "month": months[mi[i]],
             "temp_c": round(float(temp[i]), 2), "precip_mm": round(float(precip[i]), 2),
             "humidity_pct": round(float(humidity[i]), 2)} for i in range(N)], "7_cylinder_weather"


def gen_torus_circadian():
    """500k activity readings. 24 hours × 60 minutes = 1440 cells.
    Diurnal rhythm; both axes wrap (daily cycle)."""
    hours = [f"H{h:02d}" for h in range(24)]
    minutes = [f"M{m:02d}" for m in range(60)]
    h_w = 0.3 + 0.7 * np.exp(-0.5 * ((np.arange(24) - 14) / 4) ** 2)
    m_w = np.ones(60) + np.random.uniform(0, 0.2, 60)
    h_w, m_w = h_w / h_w.sum(), m_w / m_w.sum()
    hi = np.random.choice(24, size=N, p=h_w)
    mi = np.random.choice(60, size=N, p=m_w)
    phase = 2 * np.pi * (hi + mi / 60) / 24
    activity = 50 + 40 * np.sin(phase - 0.5) + np.random.normal(0, 8, N)
    heart_rate = 60 + 25 * np.sin(phase) + np.random.normal(0, 5, N)
    return [{"hour": hours[hi[i]], "minute": minutes[mi[i]],
             "activity": round(float(activity[i]), 2), "heart_rate": round(float(heart_rate[i]), 2)}
            for i in range(N)], "8_torus_circadian"


def gen_mobius_retail():
    """500k retail records. 50 categories × 52 weeks = 2600 cells.
    Week wraps; demand_surprise flips (holiday high → post-holiday low)."""
    categories = [f"Cat{i:02d}" for i in range(50)]
    weeks = [f"2023-W{w:02d}" for w in range(1, 53)]
    cat_w = np.exp(-0.02 * np.arange(50)) + 0.4
    week_w = 1.2 + 0.8 * np.exp(-0.5 * ((np.arange(1, 53) - 26) / 8) ** 2)
    cat_w, week_w = cat_w / cat_w.sum(), week_w / week_w.sum()
    cat_base = np.random.uniform(-0.1, 0.3, 50)
    ci = np.random.choice(50, size=N, p=cat_w)
    wi = np.random.choice(52, size=N, p=week_w)
    reversal = np.cos(np.pi * wi / 51)
    demand_surprise = cat_base[ci] + 0.25 * reversal + np.random.normal(0, 0.08, N)
    revenue = np.maximum(0, 1000 + 500 * demand_surprise + np.random.normal(0, 200, N))
    units = np.maximum(0, (50 + 30 * demand_surprise + np.random.normal(0, 15, N)).astype(int))
    return [{"category": categories[ci[i]], "week": weeks[wi[i]],
             "demand_surprise": round(float(demand_surprise[i]), 6),
             "revenue": round(float(revenue[i]), 2), "units_sold": int(units[i])}
            for i in range(N)], "9_mobius_retail"


def gen_patch_ecology():
    """500k ecology samples. 60 sites × 50 species = 3000 cells.
    Abundance ~ gamma; biomass ~ lognormal."""
    sites = [f"S{i:03d}" for i in range(60)]
    species = [f"Sp{i:02d}" for i in range(50)]
    site_w = np.exp(-0.02 * np.arange(60)) + 0.4
    sp_w = np.exp(-0.03 * np.arange(50)) + 0.3
    site_w, sp_w = site_w / site_w.sum(), sp_w / sp_w.sum()
    si = np.random.choice(60, size=N, p=site_w)
    spi = np.random.choice(50, size=N, p=sp_w)
    abundance = np.maximum(0, np.random.gamma(2, 5 + si * 0.3 + spi * 0.2, N))
    biomass = abundance * np.random.lognormal(0, 0.4, N) + np.random.normal(0, 2, N)
    diversity = np.clip(0.3 + 0.5 * (si / 60 + spi / 50) + np.random.normal(0, 0.1, N), 0, 1)
    return [{"site": sites[si[i]], "species": species[spi[i]],
             "abundance": round(float(abundance[i]), 4), "biomass": round(float(biomass[i]), 4),
             "diversity": round(float(diversity[i]), 4)} for i in range(N)], "10_patch_ecology"


# ═══════════════════════════════════════════════════════════════════════════════
# 3D position mapping
# ═══════════════════════════════════════════════════════════════════════════════

def _map_to_3d(manifold, primary_field):
    """Map grid vertices to 3D positions. The field value IS the geometry —
    it drives the radius/height, not just a cosmetic bump."""
    axes = manifold.axes
    if len(axes) < 2:
        return None, None

    ax0, ax1 = axes[0], axes[1]
    vals0 = [str(v) for v in ax0.values]
    vals1 = [str(v) for v in ax1.values]
    val0_idx = {v: i for i, v in enumerate(vals0)}
    val1_idx = {v: i for i, v in enumerate(vals1)}
    m, n = ax0.size, ax1.size

    field_vals = [gp.field_values.get(primary_field, 0.0) for gp in manifold.grid.values()]
    if not field_vals:
        return None, None
    fmin, fmax = min(field_vals), max(field_vals)
    frange = fmax - fmin if fmax - fmin > 1e-12 else 1.0

    name = manifold.surface_name
    positions = {}

    for coord, gp in manifold.grid.items():
        i = val0_idx.get(coord[0], 0)
        j = val1_idx.get(coord[1] if len(coord) > 1 else coord[0], 0)
        fv = gp.field_values.get(primary_field, 0.0)
        f_norm = (fv - fmin) / frange  # 0 to 1

        if "torus" in name:
            R = 1.0
            r = 0.15 + 0.45 * f_norm  # tube radius IS the data (0.15 to 0.60)
            u = 2 * math.pi * i / m
            v = 2 * math.pi * j / n
            x = (R + r * math.cos(v)) * math.cos(u)
            y = (R + r * math.cos(v)) * math.sin(u)
            z = r * math.sin(v)

        elif "cylinder" in name:
            if ax0.ordered and ax0.wraps:
                u = 2 * math.pi * i / m
                h = 2.0 * j / max(n - 1, 1) - 1.0
            elif ax1.ordered and ax1.wraps:
                u = 2 * math.pi * j / n
                h = 2.0 * i / max(m - 1, 1) - 1.0
            else:
                u = 2 * math.pi * i / m
                h = 2.0 * j / max(n - 1, 1) - 1.0
            R = 0.3 + 0.5 * f_norm  # radius IS the data
            x = R * math.cos(u)
            y = R * math.sin(u)
            z = h

        elif "klein" in name:
            u = 2 * math.pi * i / m
            v = 2 * math.pi * j / n
            r_scale = 0.4 + 0.6 * f_norm
            a_ = 2.0
            x = (a_ + r_scale * (math.cos(u/2)*math.sin(v) - math.sin(u/2)*math.sin(2*v))) * math.cos(u)
            y = (a_ + r_scale * (math.cos(u/2)*math.sin(v) - math.sin(u/2)*math.sin(2*v))) * math.sin(u)
            z = r_scale * (math.sin(u/2)*math.sin(v) + math.cos(u/2)*math.sin(2*v))

        elif "mobius" in name:
            if ax1.ordered and ax1.wraps:
                u = 2 * math.pi * j / n
                s_val = -0.5 + i / max(m - 1, 1)
            else:
                u = 2 * math.pi * i / m
                s_val = -0.5 + j / max(n - 1, 1)
            w = 0.3 + 0.7 * f_norm  # width IS the data
            x = (1 + s_val * w * math.cos(u/2)) * math.cos(u)
            y = (1 + s_val * w * math.cos(u/2)) * math.sin(u)
            z = s_val * w * math.sin(u/2)

        else:
            x = 2.0 * i / max(m - 1, 1) - 1.0
            y = 2.0 * j / max(n - 1, 1) - 1.0
            z = f_norm * 1.5  # height IS the data

        positions[gp.index] = (round(x, 8), round(y, 8), round(z, 8))

    cells_u = m if ax0.wraps else max(m - 1, 0)
    cells_v = n if ax1.wraps else max(n - 1, 0)
    coord_to_idx = {coord: gp.index for coord, gp in manifold.grid.items()}
    faces = []
    for i in range(cells_u):
        for j in range(cells_v):
            i2 = (i + 1) % m
            j2 = (j + 1) % n
            c00 = (vals0[i], vals1[j])
            c10 = (vals0[i2], vals1[j])
            c01 = (vals0[i], vals1[j2])
            c11 = (vals0[i2], vals1[j2])
            if all(c in coord_to_idx for c in (c00, c10, c01, c11)):
                faces.append((coord_to_idx[c00], coord_to_idx[c10],
                               coord_to_idx[c11], coord_to_idx[c01]))
    return positions, faces


# ═══════════════════════════════════════════════════════════════════════════════
# Export
# ═══════════════════════════════════════════════════════════════════════════════

def export_manifold(rows, label, out_dir):
    t0 = time.perf_counter()
    columns = list(dict.fromkeys(k for r in rows[:100] for k in r.keys()))[:50]
    col_types, col_stats = infer_schema(rows, columns)
    manifold = build_manifold(rows, columns, col_types, col_stats)
    ms = (time.perf_counter() - t0) * 1000

    if manifold is None:
        print(f"  SKIP {label}: manifold build returned None", flush=True)
        return

    os.makedirs(out_dir, exist_ok=True)
    axis_cols = [a.column for a in manifold.axes]
    field_cols = manifold.field_columns
    primary_field = field_cols[0] if field_cols else None
    positions, faces = _map_to_3d(manifold, primary_field) if primary_field else (None, None)

    with open(os.path.join(out_dir, "vertices.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["index"] + axis_cols + ["x3d","y3d","z3d"] +
                    field_cols + ["curvature","forman_ricci","density"])
        for coord, gp in manifold.grid.items():
            pos = positions.get(gp.index, (0,0,0)) if positions else (0,0,0)
            row = [gp.index] + list(coord) + list(pos)
            row += [round(gp.field_values.get(fc,0.0),8) for fc in field_cols]
            row += [round(gp.curvature,8), round(gp.forman_ricci,8), gp.density]
            w.writerow(row)

    with open(os.path.join(out_dir, "edges.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["source","target"])
        seen = set()
        for gp in manifold.grid.values():
            for ni in gp.neighbors:
                e = (min(gp.index,ni), max(gp.index,ni))
                if e not in seen:
                    seen.add(e)
                    w.writerow(list(e))

    n_faces = 0
    if faces:
        with open(os.path.join(out_dir, "faces.csv"), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["v0","v1","v2","v3"])
            for face in faces:
                w.writerow(list(face))
        n_faces = len(faces)

    meta = {
        "label": label, "row_count": len(rows),
        "surface_name": manifold.surface_name,
        "genus": manifold.genus, "orientable": manifold.orientable,
        "euler_characteristic": manifold.euler_characteristic,
        "classification_mode": manifold.classification_mode,
        "surface_confidence": manifold.surface_confidence_obj,
        "betti_0": manifold.betti_0, "betti_1": manifold.betti_1,
        "vertex_count": manifold.vertex_count, "edge_count": manifold.edge_count,
        "face_count": manifold.face_count, "exported_faces": n_faces,
        "face_coverage": manifold.face_coverage, "occupancy": manifold.occupancy,
        "boundary_edge_count": manifold.boundary_edge_count,
        "boundary_loop_count": manifold.boundary_loop_count,
        "face_euler_characteristic": manifold.face_euler_characteristic,
        "face_genus_estimate": manifold.face_genus_estimate,
        "axes": [{"column": a.column, "type": a.axis_type, "size": a.size,
                   "wraps": a.wraps, "wrap_orientation": a.wrap_orientation,
                   "ordered": a.ordered}
                  for a in manifold.axes],
        "field_columns": manifold.field_columns,
        "primary_field": primary_field,
        "build_ms": round(ms, 1),
    }
    with open(os.path.join(out_dir, "metadata.json"), "w") as f:
        json.dump(meta, f, indent=2, default=str)

    axes_str = ", ".join(
        f"{a.column}({'W+' if a.wraps and a.wrap_orientation==1 else 'W-' if a.wraps and a.wrap_orientation==-1 else 'I'})"
        for a in manifold.axes)
    print(f"  {label:24s} | {manifold.surface_name:20s} | "
          f"V={manifold.vertex_count:5d} E={manifold.edge_count:5d} F={n_faces:5d} | "
          f"β0={manifold.betti_0} β1={manifold.betti_1} χ={manifold.euler_characteristic} | "
          f"[{axes_str}] | {ms:.0f}ms", flush=True)


def main():
    print("=" * 115, flush=True)
    print("  Exporting manifold artifacts — 10 domains, 500k rows each, high cardinality", flush=True)
    print("=" * 115, flush=True)

    generators = [
        gen_patch_l2_book, gen_cylinder_macro, gen_torus_options,
        gen_mobius_momentum, gen_klein_greeks,
        gen_patch_genomics, gen_cylinder_weather, gen_torus_circadian,
        gen_mobius_retail, gen_patch_ecology,
    ]
    for gen_fn in generators:
        rows, label = gen_fn()
        print(f"\n  [{label}] {len(rows)} rows ...", flush=True)
        export_manifold(rows, label, os.path.join(ARTIFACTS_DIR, label))

    print(f"\n  Artifacts → {ARTIFACTS_DIR}", flush=True)

if __name__ == "__main__":
    main()
