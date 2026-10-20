"""
BinomialHash — JSON Data Manifolds (realistic simulated data)

4 manifolds from 4 domains:
  1. Options chain (500 contracts) → deformed torus
  2. Order book (100 levels) → folded ribbon
  3. Genomics VCF (200 variants) → saddle with ridges
  4. Multi-sector equities (15 stocks) → connected lobed surface
"""

import numpy as np
from scipy.interpolate import RegularGridInterpolator
import plotly.graph_objects as go
from plotly.io import to_html

np.random.seed(42)
DARK = "rgb(10,10,30)"


# ═══════════════════════════════════════════════════════════════════════════════
# 1. OPTIONS CHAIN → DEFORMED TORUS
# ═══════════════════════════════════════════════════════════════════════════════

def build_options_torus():
    strikes = np.arange(170, 230, 2.5)  # 24 strikes
    n_s = len(strikes)
    atm = 200.0

    call_bid = np.maximum(atm - strikes, 0.5) * np.exp(-0.02 * np.abs(strikes - atm)) + np.random.normal(0, 0.3, n_s)
    call_bid = np.maximum(call_bid, 0.05)
    put_bid = np.maximum(strikes - atm, 0.5) * np.exp(-0.02 * np.abs(strikes - atm)) + np.random.normal(0, 0.3, n_s)
    put_bid = np.maximum(put_bid, 0.05)

    call_vol = 800 + 15000 * np.exp(-0.01 * (strikes - atm) ** 2) + np.random.poisson(500, n_s)
    put_vol = 600 + 12000 * np.exp(-0.01 * (strikes - atm) ** 2) + np.random.poisson(400, n_s)

    call_iv = 0.20 + 0.08 * ((strikes - atm) / 20) ** 2 + np.random.normal(0, 0.005, n_s)
    put_iv = 0.21 + 0.09 * ((strikes - atm) / 20) ** 2 + np.random.normal(0, 0.005, n_s)

    vol_grid = np.column_stack([call_vol, put_vol])
    vol_norm = vol_grid - vol_grid.mean()
    vol_norm = vol_norm / np.abs(vol_norm).max()

    iv_grid = np.column_stack([call_iv, put_iv])
    iv_norm = iv_grid - iv_grid.mean()
    iv_norm = iv_norm / np.abs(iv_norm).max()

    res = 120
    theta = np.linspace(0, 2 * np.pi, res)
    phi = np.linspace(0, 2 * np.pi, res)

    theta_data = np.linspace(0, 2 * np.pi, n_s, endpoint=False)
    phi_data = np.array([0, np.pi])

    vn_ext = np.zeros((n_s + 1, 3))
    vn_ext[:n_s, :2] = vol_norm
    vn_ext[:n_s, 2] = vol_norm[:, 0]
    vn_ext[n_s, :] = vn_ext[0, :]
    theta_ext = np.append(theta_data, 2 * np.pi)
    phi_ext = np.array([0, np.pi, 2 * np.pi])

    interp = RegularGridInterpolator((theta_ext, phi_ext), vn_ext, method="linear",
                                      bounds_error=False, fill_value=0)
    THETA, PHI = np.meshgrid(theta, phi)
    pts = np.column_stack([THETA.ravel(), PHI.ravel()])
    DEFORM = interp(pts).reshape(THETA.shape)

    R, r = 4.0, 1.5
    r_local = r + DEFORM * 0.9 * r
    X = (R + r_local * np.cos(PHI)) * np.cos(THETA)
    Y = (R + r_local * np.cos(PHI)) * np.sin(THETA)
    Z = r_local * np.sin(PHI)

    fig = go.Figure()
    fig.add_trace(go.Surface(
        x=X, y=Y, z=Z, surfacecolor=DEFORM,
        colorscale="Inferno", opacity=0.88,
        colorbar=dict(title="Volume", len=0.5, x=0.9),
        contours=dict(
            x=dict(show=True, color="rgba(255,255,255,0.08)", width=1),
            y=dict(show=True, color="rgba(255,255,255,0.08)", width=1),
        ),
        lighting=dict(ambient=0.4, diffuse=0.6, specular=0.3, roughness=0.5),
    ))

    for i in range(0, n_s, 3):
        for j, (typ, phi_v) in enumerate([("C", 0), ("P", np.pi)]):
            t = theta_data[i]
            v = vol_norm[i, j]
            rl = r + v * 0.9 * r
            px = (R + rl * np.cos(phi_v)) * np.cos(t)
            py = (R + rl * np.cos(phi_v)) * np.sin(t)
            pz = rl * np.sin(phi_v)
            fig.add_trace(go.Scatter3d(
                x=[px], y=[py], z=[pz], mode="markers+text",
                marker=dict(size=3, color="white"),
                text=[f"{typ}{strikes[i]:.0f}"],
                textfont=dict(size=7, color="rgba(255,255,255,0.7)"),
                textposition="top center", showlegend=False, hoverinfo="text",
                hovertext=f"{typ} {strikes[i]:.0f}<br>vol={vol_grid[i,j]:.0f}<br>iv={iv_grid[i,j]:.3f}",
            ))

    fig.update_layout(
        title="Options Chain (24 strikes × call/put) → Deformed Torus<br>"
              "<sub>θ = strike around ring | φ = call/put around tube | "
              "ATM volume BULGES the surface outward | Wings PINCH inward</sub>",
        scene=dict(
            xaxis=dict(visible=False), yaxis=dict(visible=False), zaxis=dict(visible=False),
            camera=dict(eye=dict(x=1.6, y=0.9, z=0.7)), bgcolor=DARK,
        ),
        width=950, height=750, paper_bgcolor=DARK, font=dict(color="white"),
    )
    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# 2. ORDER BOOK → FOLDED RIBBON (bids fold under, asks fold over)
# ═══════════════════════════════════════════════════════════════════════════════

def build_orderbook_ribbon():
    mid = 195.50
    levels = 50

    bid_prices = mid - 0.01 * np.arange(1, levels + 1) - np.random.exponential(0.02, levels)
    ask_prices = mid + 0.01 * np.arange(1, levels + 1) + np.random.exponential(0.02, levels)
    bid_sizes = np.random.lognormal(5, 1.5, levels).astype(int)
    ask_sizes = np.random.lognormal(5, 1.5, levels).astype(int)

    bid_sizes[3] = 50000
    ask_sizes[5] = 45000

    all_prices = np.concatenate([bid_prices[::-1], ask_prices])
    all_sizes = np.concatenate([bid_sizes[::-1], ask_sizes])
    all_sides = np.concatenate([np.ones(levels) * -1, np.ones(levels)])
    n = len(all_prices)

    cum_bid = np.cumsum(bid_sizes)
    cum_ask = np.cumsum(ask_sizes)
    all_cum = np.concatenate([cum_bid[::-1], cum_ask])

    size_norm = all_sizes / all_sizes.max()

    u = np.linspace(0, 2 * np.pi, n)
    v = np.linspace(0, 2 * np.pi, 40)
    U, V = np.meshgrid(u, v)

    R_base = 3.0
    width = 0.3

    deform = np.zeros_like(U)
    for k in range(n):
        weight = np.exp(-((U - u[k]) ** 2) / 0.02)
        deform += size_norm[k] * weight * 0.8

    side_signal = np.zeros(n)
    side_signal[:levels] = -1
    side_signal[levels:] = 1
    side_interp = np.interp(U[0, :], u, side_signal)
    SIDE = np.tile(side_interp, (U.shape[0], 1))

    r_tube = width + deform * 0.5
    twist = SIDE * 0.3

    X = (R_base + r_tube * np.cos(V + twist)) * np.cos(U)
    Y = (R_base + r_tube * np.cos(V + twist)) * np.sin(U)
    Z = r_tube * np.sin(V + twist)

    fig = go.Figure()
    fig.add_trace(go.Surface(
        x=X, y=Y, z=Z, surfacecolor=deform,
        colorscale="Plasma", opacity=0.85,
        colorbar=dict(title="Order Size", len=0.5, x=0.9),
        lighting=dict(ambient=0.4, diffuse=0.6, specular=0.3),
    ))

    for k in [0, levels - 1, levels, 2 * levels - 1, 3, levels + 5]:
        if k >= n:
            continue
        t = u[k]
        rl = width + size_norm[k] * 0.8 * 0.5
        side = "BID" if k < levels else "ASK"
        px = (R_base + rl) * np.cos(t)
        py = (R_base + rl) * np.sin(t)
        pz = 0
        fig.add_trace(go.Scatter3d(
            x=[px], y=[py], z=[pz], mode="markers+text",
            marker=dict(size=4, color="lime" if side == "BID" else "red"),
            text=[f"{side} {all_prices[k]:.2f}"],
            textfont=dict(size=8, color="white"), textposition="top center",
            showlegend=False, hoverinfo="text",
            hovertext=f"{side} {all_prices[k]:.2f}<br>size={all_sizes[k]}<br>cum={all_cum[k]}",
        ))

    fig.update_layout(
        title="Order Book (50 bid + 50 ask levels) → Twisted Ribbon<br>"
              "<sub>Position on ring = price level | Tube thickness = order size | "
              "Twist = bid/ask side | Large orders BULGE the ribbon</sub>",
        scene=dict(
            xaxis=dict(visible=False), yaxis=dict(visible=False), zaxis=dict(visible=False),
            camera=dict(eye=dict(x=1.5, y=1.2, z=0.9)), bgcolor=DARK,
        ),
        width=950, height=750, paper_bgcolor=DARK, font=dict(color="white"),
    )
    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# 3. GENOMICS VCF → SADDLE WITH RIDGES
# ═══════════════════════════════════════════════════════════════════════════════

def build_genomics_saddle():
    n = 200
    is_good = np.random.random(n) > 0.25

    qual = np.where(is_good, np.random.uniform(60, 99, n), np.random.uniform(5, 50, n))
    dp = np.where(is_good, np.random.uniform(30, 300, n), np.random.uniform(3, 25, n))
    af = np.where(is_good, np.random.uniform(0.15, 0.55, n), np.random.uniform(0.01, 0.15, n))
    mq = np.where(is_good, np.random.uniform(50, 60, n), np.random.uniform(15, 45, n))
    fs = np.where(is_good, np.random.exponential(1.0, n), np.random.exponential(10.0, n))

    u = np.linspace(-3, 3, 100)
    v = np.linspace(-3, 3, 100)
    U, V = np.meshgrid(u, v)

    Z = 0.3 * (U ** 2 - V ** 2)

    qual_norm = (qual - qual.min()) / (qual.max() - qual.min()) * 6 - 3
    af_norm = (af - af.min()) / (af.max() - af.min()) * 6 - 3
    dp_norm = dp / dp.max()

    for k in range(n):
        bump = dp_norm[k] * 2.0 * np.exp(-((U - qual_norm[k]) ** 2 + (V - af_norm[k]) ** 2) / 0.4)
        Z += bump

    fig = go.Figure()
    fig.add_trace(go.Surface(
        x=U, y=V, z=Z, colorscale="Earth", opacity=0.75,
        colorbar=dict(title="Elevation", len=0.5, x=0.9),
        contours=dict(z=dict(show=True, highlightcolor="white", highlightwidth=2,
                              color="rgba(255,255,255,0.1)")),
        lighting=dict(ambient=0.35, diffuse=0.6, specular=0.4, roughness=0.3),
    ))

    sample_idx = np.random.choice(n, 40, replace=False)
    for k in sample_idx:
        qz = 0.3 * (qual_norm[k] ** 2 - af_norm[k] ** 2) + dp_norm[k] * 2.0 + 0.3
        color = "lime" if qual[k] >= 60 else "orange" if qual[k] >= 30 else "red"
        fig.add_trace(go.Scatter3d(
            x=[qual_norm[k]], y=[af_norm[k]], z=[qz],
            mode="markers", marker=dict(size=3, color=color, opacity=0.8),
            showlegend=False, hoverinfo="text",
            hovertext=f"qual={qual[k]:.0f}<br>AF={af[k]:.3f}<br>DP={dp[k]:.0f}<br>MQ={mq[k]:.0f}<br>FS={fs[k]:.1f}",
        ))

    fig.update_layout(
        title="Genomics VCF (200 variants) → Hyperbolic Saddle<br>"
              "<sub>Quality → x-axis | Allele Freq → y-axis | Coverage bumps the surface | "
              "Green = PASS (ridge) | Red = filtered (valleys)</sub>",
        scene=dict(
            xaxis=dict(title="← Low Qual — High Qual →"),
            yaxis=dict(title="← Rare — Common →"),
            zaxis=dict(title="Coverage elevation"),
            camera=dict(eye=dict(x=1.6, y=-1.8, z=1.0)), bgcolor=DARK,
        ),
        width=950, height=750, paper_bgcolor=DARK, font=dict(color="white"),
    )
    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# 4. MULTI-SECTOR → CONNECTED LOBED SURFACE
# ═══════════════════════════════════════════════════════════════════════════════

def build_sector_connected():
    sectors = {
        "Tech":   {"tickers": ["AAPL","MSFT","NVDA","GOOGL","META"], "vol": [50,35,45,28,32], "pe": [33,37,65,25,28], "beta": [1.2,1.1,1.7,1.0,1.3]},
        "Health": {"tickers": ["JNJ","UNH","PFE","LLY","ABBV"],     "vol": [8,4,30,12,15],    "pe": [15,22,12,45,20], "beta": [0.5,0.7,0.6,0.8,0.7]},
        "Energy": {"tickers": ["XOM","CVX","COP","SLB","EOG"],      "vol": [22,12,9,8,7],     "pe": [11,13,10,18,9],  "beta": [0.9,0.8,1.0,1.2,1.1]},
    }
    n_sectors = len(sectors)
    sector_names = list(sectors.keys())

    res_u = 120
    res_v = 60
    u = np.linspace(0, 2 * np.pi, res_u)
    v = np.linspace(0, np.pi, res_v)
    U, V = np.meshgrid(u, v)

    R_base = 1.0

    bumps = np.zeros_like(U)
    for si, sname in enumerate(sector_names):
        angle = 2 * np.pi * si / n_sectors
        vols = np.array(sectors[sname]["vol"], dtype=float)
        vol_norm = vols / 50.0

        lobe_theta = angle
        lobe_weight = 2.5 * np.exp(-2.0 * ((U - lobe_theta) ** 2))
        lobe_weight += 2.5 * np.exp(-2.0 * ((U - lobe_theta + 2 * np.pi) ** 2))
        lobe_weight += 2.5 * np.exp(-2.0 * ((U - lobe_theta - 2 * np.pi) ** 2))

        for ki, vol in enumerate(vol_norm):
            stock_phi = np.pi * (ki + 1) / (len(vols) + 1)
            stock_bump = vol * 0.8 * np.exp(-3.0 * (V - stock_phi) ** 2)
            bumps += lobe_weight * stock_bump

    r_surface = R_base + bumps
    X = r_surface * np.sin(V) * np.cos(U)
    Y = r_surface * np.sin(V) * np.sin(U)
    Z = r_surface * np.cos(V)

    fig = go.Figure()
    fig.add_trace(go.Surface(
        x=X, y=Y, z=Z, surfacecolor=bumps,
        colorscale="Viridis", opacity=0.85,
        colorbar=dict(title="Volume<br>deformation", len=0.5, x=0.9),
        lighting=dict(ambient=0.35, diffuse=0.6, specular=0.4, roughness=0.3),
    ))

    for si, sname in enumerate(sector_names):
        angle = 2 * np.pi * si / n_sectors
        vols = sectors[sname]["vol"]
        tickers = sectors[sname]["tickers"]

        for ki, (ticker, vol) in enumerate(zip(tickers, vols)):
            phi_stock = np.pi * (ki + 1) / (len(vols) + 1)
            vol_n = vol / 50.0
            r_pt = R_base + vol_n * 2.0 + 0.3
            px = r_pt * np.sin(phi_stock) * np.cos(angle)
            py = r_pt * np.sin(phi_stock) * np.sin(angle)
            pz = r_pt * np.cos(phi_stock)
            fig.add_trace(go.Scatter3d(
                x=[px], y=[py], z=[pz], mode="markers+text",
                marker=dict(size=4, color="white"),
                text=[ticker], textfont=dict(size=8, color="white"),
                textposition="top center", showlegend=False, hoverinfo="text",
                hovertext=f"{ticker} ({sname})<br>vol={vol}M<br>PE={sectors[sname]['pe'][ki]}<br>β={sectors[sname]['beta'][ki]}",
            ))

        label_r = R_base + 3.5
        lx = label_r * np.sin(np.pi / 2) * np.cos(angle)
        ly = label_r * np.sin(np.pi / 2) * np.sin(angle)
        fig.add_trace(go.Scatter3d(
            x=[lx], y=[ly], z=[0], mode="text",
            text=[f"<b>{sname}</b>"], textfont=dict(size=12, color="white"),
            showlegend=False, hoverinfo="skip",
        ))

    fig.update_layout(
        title="Multi-Sector Equities (15 stocks) → Connected Lobed Sphere<br>"
              "<sub>ONE surface — sectors are lobes on a shared sphere | "
              "Lobe size = sector volume | Individual bumps = stock volumes</sub>",
        scene=dict(
            xaxis=dict(visible=False), yaxis=dict(visible=False), zaxis=dict(visible=False),
            camera=dict(eye=dict(x=1.8, y=0.8, z=0.6)), bgcolor=DARK,
        ),
        width=950, height=750, paper_bgcolor=DARK, font=dict(color="white"),
    )
    return fig


# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Building manifolds...")
    figs = [
        ("torus", build_options_torus()),
        ("ribbon", build_orderbook_ribbon()),
        ("saddle", build_genomics_saddle()),
        ("sphere", build_sector_connected()),
    ]

    html = [
        "<html><head><title>BinomialHash — Data Manifolds</title></head>",
        f"<body style='background:{DARK}; color:white; font-family:sans-serif'>",
        "<h1 style='text-align:center; padding:30px 0 5px'>BinomialHash — Data Manifolds</h1>",
        "<p style='text-align:center; color:#aaa; max-width:700px; margin:auto; padding-bottom:20px'>"
        "Each dataset's dimensional structure determines a base surface. "
        "Field values DEFORM that surface — peaks, ridges, and valleys ARE the data. "
        "The agent navigates this shape.</p>",
    ]

    for i, (name, fig) in enumerate(figs):
        html.append(to_html(fig, full_html=False, include_plotlyjs="cdn" if i == 0 else False))
        html.append("<div style='height:20px'></div>")
        print(f"  {name} done")

    html.append("</body></html>")
    out = "benchmarks/json_manifold_shapes.html"
    with open(out, "w") as f:
        f.write("\n".join(html))
    print(f"Saved to {out}")
