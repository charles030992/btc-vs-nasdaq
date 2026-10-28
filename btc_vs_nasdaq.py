"""BTC vs QQQ (Nasdaq-100): rentabilidad, riesgo y drawdown con datos de Yahoo Finance.

Uso:
    python btc_vs_nasdaq.py [--start 2017-01-01] [--risk-free 0.0] [--output-dir output] [--show]

BTC cotiza los 365 días del año y QQQ solo los días de bolsa. Para comparar ambos en
igualdad de condiciones, la muestra se alinea en las fechas comunes (días de bolsa) y
todas las métricas se calculan sobre esa misma muestra:

- CAGR: en tiempo natural (años entre la primera y la última fecha), igual para los dos.
- Volatilidad y Sharpe: se anualizan con el número real de observaciones por año de la
  muestra alineada (unas 251), no con 365 para BTC y 252 para QQQ.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

TICKERS = {"BTC": "BTC-USD", "QQQ": "QQQ"}


def download_prices(start):
    """Cierres ajustados de BTC y QQQ, alineados en las fechas comunes."""
    import yfinance as yf

    raw = yf.download(list(TICKERS.values()), start=start, auto_adjust=True, progress=False)["Close"]
    prices = raw[list(TICKERS.values())].rename(columns={v: k for k, v in TICKERS.items()})
    prices.columns.name = None
    return align_prices(prices)


def align_prices(prices):
    """Se queda solo con las fechas en las que cotizan todos los activos."""
    return prices.dropna()


def normalized_index(prices):
    """Valor de 1 invertido al inicio (empieza exactamente en 1)."""
    return prices / prices.iloc[0]


def drawdown(index):
    return index / index.cummax() - 1


def calendar_years(prices):
    return (prices.index[-1] - prices.index[0]).days / 365.25


def sharpe_label(risk_free):
    return f"Sharpe (rf={risk_free:.1%})"


def compute_metrics(prices, risk_free=0.0):
    """Métricas por activo, todas sobre la misma muestra y el mismo calendario."""
    returns = prices.pct_change().dropna()
    index = normalized_index(prices)
    years = calendar_years(prices)
    periods = len(returns) / years  # observaciones reales por año natural

    cagr = index.iloc[-1] ** (1 / years) - 1
    vol = returns.std() * np.sqrt(periods)
    sharpe = (returns.mean() * periods - risk_free) / vol

    return pd.DataFrame(
        {
            "CAGR": cagr,
            "Vol (ann.)": vol,
            "Max Drawdown": drawdown(index).min(),
            "Total Return": index.iloc[-1] - 1,
            sharpe_label(risk_free): sharpe,
        }
    )


def plot_comparison(prices, path, show=False):
    import matplotlib.pyplot as plt

    index = normalized_index(prices)
    dd = drawdown(index)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

    for col in index.columns:
        ax1.plot(index[col], label=col)
    ax1.set_yscale("log")
    ax1.set_title("BTC vs QQQ - Normalized Performance (Log Scale)")
    ax1.legend()

    for col in dd.columns:
        ax2.plot(dd[col], label=f"{col} DD")
    ax2.set_title("Drawdowns")
    ax2.legend()

    plt.tight_layout()
    plt.savefig(path)
    if show:
        plt.show()
    plt.close(fig)


def export_excel(prices, metrics, path):
    returns = prices.pct_change().dropna()
    index = normalized_index(prices)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        prices.to_excel(writer, sheet_name="Prices")
        returns.to_excel(writer, sheet_name="Returns")
        index.to_excel(writer, sheet_name="Index")
        drawdown(index).to_excel(writer, sheet_name="Drawdown")
        metrics.to_excel(writer, sheet_name="Metrics")


def main():
    parser = argparse.ArgumentParser(description="BTC vs QQQ: rentabilidad, riesgo y drawdown")
    parser.add_argument("--start", default="2017-01-01", help="fecha de inicio (YYYY-MM-DD)")
    parser.add_argument("--risk-free", type=float, default=0.0, help="tasa libre de riesgo anual, p. ej. 0.03")
    parser.add_argument("--output-dir", default="output", help="carpeta de salida (png y xlsx)")
    parser.add_argument("--show", action="store_true", help="mostrar el gráfico en pantalla")
    args = parser.parse_args()

    prices = download_prices(args.start)
    metrics = compute_metrics(prices, args.risk_free)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    plot_comparison(prices, out_dir / "btc_vs_qqq.png", show=args.show)
    export_excel(prices, metrics, out_dir / "btc_vs_qqq_report.xlsx")

    print(f"Periodo: {prices.index[0].date()} -> {prices.index[-1].date()} "
          f"({calendar_years(prices):.2f} años, {len(prices)} observaciones)\n")
    formatters = {col: (lambda x: f"{x:,.1%}") for col in metrics.columns}
    formatters[sharpe_label(args.risk_free)] = lambda x: f"{x:.2f}"
    print(metrics.to_string(formatters=formatters))
    print(f"\nSalida en: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
