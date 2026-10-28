import unittest

import numpy as np
import pandas as pd

from btc_vs_nasdaq import (
    align_prices,
    calendar_years,
    compute_metrics,
    drawdown,
    normalized_index,
    sharpe_label,
)

TRADING_DAYS = pd.bdate_range("2020-01-01", "2024-12-31")  # ~5 años, solo días de bolsa


def growing_series(annual_growth, dates=TRADING_DAYS):
    """Serie que crece exactamente `annual_growth` por año natural, a cualquier frecuencia."""
    years = (dates - dates[0]).days / 365.25
    return pd.Series(100 * (1 + annual_growth) ** years, index=dates)


class AlignmentTests(unittest.TestCase):
    def test_keeps_only_dates_where_all_assets_trade(self):
        week = pd.date_range("2024-01-01", "2024-01-07")  # lunes a domingo
        btc = pd.Series(range(7), index=week, dtype=float)  # cotiza los 7 días
        qqq = pd.Series(range(5), index=week[:5], dtype=float).reindex(week)  # fines de semana NaN
        aligned = align_prices(pd.DataFrame({"BTC": btc, "QQQ": qqq}))
        self.assertEqual(len(aligned), 5)
        self.assertFalse(aligned.isna().any().any())


class CagrTests(unittest.TestCase):
    def test_cagr_uses_calendar_time_not_a_fixed_periods_count(self):
        # Regresión: dividir len(muestra) entre 365 en una muestra de días de bolsa (~251/año)
        # daba ~0,69 de los años reales y disparaba el CAGR (aquí, ~14 % en lugar de 10 %).
        prices = pd.DataFrame({"A": growing_series(0.10), "B": growing_series(0.25)})
        metrics = compute_metrics(prices)
        self.assertAlmostEqual(metrics.loc["A", "CAGR"], 0.10, places=3)
        self.assertAlmostEqual(metrics.loc["B", "CAGR"], 0.25, places=3)

    def test_same_growth_gives_the_same_cagr_regardless_of_sampling(self):
        daily = growing_series(0.20, pd.date_range("2020-01-01", "2024-12-31"))  # 7 días/semana
        weekdays = growing_series(0.20)  # solo días de bolsa
        cagr_daily = compute_metrics(pd.DataFrame({"A": daily})).loc["A", "CAGR"]
        cagr_weekdays = compute_metrics(pd.DataFrame({"A": weekdays})).loc["A", "CAGR"]
        self.assertAlmostEqual(cagr_daily, cagr_weekdays, places=3)


class VolatilityAndSharpeTests(unittest.TestCase):
    def setUp(self):
        # Rendimientos alternando +1 % / -1 % en cada día de bolsa.
        steps = np.where(np.arange(len(TRADING_DAYS) - 1) % 2 == 0, 1.01, 0.99)
        values = np.concatenate([[100.0], 100 * np.cumprod(steps)])
        self.prices = pd.DataFrame({"A": values}, index=TRADING_DAYS)

    def test_volatility_is_annualized_with_the_real_sampling_frequency(self):
        vol = compute_metrics(self.prices).loc["A", "Vol (ann.)"]
        # 1 % diario * raíz de ~261 observaciones/año
        self.assertTrue(0.15 < vol < 0.17, vol)

    def test_risk_free_rate_lowers_sharpe_by_rf_over_vol(self):
        base = compute_metrics(self.prices, risk_free=0.0)
        with_rf = compute_metrics(self.prices, risk_free=0.03)
        vol = base.loc["A", "Vol (ann.)"]
        self.assertAlmostEqual(
            base.loc["A", sharpe_label(0.0)] - with_rf.loc["A", sharpe_label(0.03)],
            0.03 / vol,
            places=9,
        )


class DrawdownTests(unittest.TestCase):
    def test_max_drawdown_is_the_worst_fall_from_a_peak(self):
        dates = pd.bdate_range("2024-01-01", periods=4)
        prices = pd.DataFrame({"A": [100.0, 120.0, 60.0, 90.0]}, index=dates)
        self.assertAlmostEqual(drawdown(normalized_index(prices))["A"].min(), -0.5)
        self.assertAlmostEqual(compute_metrics(prices).loc["A", "Max Drawdown"], -0.5)

    def test_total_return_and_index_start_at_one(self):
        dates = pd.bdate_range("2024-01-01", periods=3)
        prices = pd.DataFrame({"A": [50.0, 75.0, 100.0]}, index=dates)
        self.assertEqual(normalized_index(prices).iloc[0, 0], 1.0)
        self.assertAlmostEqual(compute_metrics(prices).loc["A", "Total Return"], 1.0)

    def test_calendar_years(self):
        dates = pd.DatetimeIndex(["2020-01-01", "2021-01-01"])
        prices = pd.DataFrame({"A": [1.0, 2.0]}, index=dates)
        self.assertAlmostEqual(calendar_years(prices), 366 / 365.25)


if __name__ == "__main__":
    unittest.main()
