"""
Forecasting Engine — Production Grade
=======================================
1. Prophet (primary) — handles seasonality, holidays, trend changepoints
2. ARIMA (secondary) — classical time-series via statsmodels
3. Linear fallback — simple trend + seasonal for when libraries unavailable

Libraries: prophet, statsmodels (ARIMA, ADF test), scikit-learn (metrics), numpy, pandas
"""
import numpy as np
import pandas as pd
from typing import Dict, Optional
from sklearn.metrics import r2_score, mean_absolute_percentage_error
import warnings, logging
warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

def forecast_prophet(df, metric="revenue", periods=12):
    """Prophet forecast with seasonality, trend changepoints, and uncertainty intervals."""
    try:
        from prophet import Prophet
    except ImportError:
        raise ImportError("prophet not installed — pip install prophet")

    time_col = "month" if "month" in df.columns else "date"
    monthly = df.groupby(time_col)[metric].sum().reset_index()
    monthly.columns = ["ds", "y"]
    monthly["ds"] = pd.to_datetime(monthly["ds"])

    model = Prophet(yearly_seasonality=True, weekly_seasonality=False, daily_seasonality=False,
                    changepoint_prior_scale=0.05, seasonality_prior_scale=10, interval_width=0.9)
    model.fit(monthly)

    future = model.make_future_dataframe(periods=periods, freq="MS")
    forecast = model.predict(future)

    hist = forecast[forecast["ds"].isin(monthly["ds"])]
    fut = forecast[~forecast["ds"].isin(monthly["ds"])]

    # In-sample metrics
    y_actual = monthly["y"].values; y_fitted = hist["yhat"].values[:len(y_actual)]
    r2 = r2_score(y_actual, y_fitted) if len(y_actual) == len(y_fitted) else None
    mape = mean_absolute_percentage_error(y_actual, y_fitted) * 100 if len(y_actual) == len(y_fitted) else None

    return {
        "method": "prophet", "metric": metric,
        "historical": {"dates": monthly["ds"].dt.strftime("%Y-%m").tolist(), "actual": monthly["y"].tolist(),
                        "fitted": y_fitted.tolist()},
        "forecast": {"dates": fut["ds"].dt.strftime("%Y-%m").tolist(),
                      "predicted": fut["yhat"].round(0).tolist(),
                      "lower": fut["yhat_lower"].round(0).tolist(),
                      "upper": fut["yhat_upper"].round(0).tolist()},
        "summary": {"historical_total": round(float(monthly["y"].sum()), 0),
                     "forecast_total": round(float(fut["yhat"].sum()), 0),
                     "yoy_pct": round((fut["yhat"].sum() - monthly["y"].sum()) / max(monthly["y"].sum(), 1) * 100, 1)},
        "diagnostics": {"r_squared": round(float(r2), 4) if r2 else None,
                         "mape": round(float(mape), 2) if mape else None,
                         "n_changepoints": len(model.changepoints)},
    }

def forecast_arima(df, metric="revenue", periods=12):
    """ARIMA forecast via statsmodels. Auto-selects order via ADF stationarity test."""
    try:
        from statsmodels.tsa.arima.model import ARIMA
        from statsmodels.tsa.stattools import adfuller
    except ImportError:
        raise ImportError("statsmodels not installed")

    time_col = "month" if "month" in df.columns else "date"
    monthly = df.groupby(time_col)[metric].sum().reset_index().sort_values(time_col)
    y = monthly[metric].values.astype(float)

    # ADF test for stationarity
    adf_result = adfuller(y)
    is_stationary = adf_result[1] < 0.05
    d = 0 if is_stationary else 1

    # Fit ARIMA(2, d, 1) — reasonable default for monthly marketing data
    model = ARIMA(y, order=(2, d, 1))
    fitted = model.fit()
    fc = np.array(fitted.forecast(steps=periods))
    y_pred = np.array(fitted.fittedvalues)

    r2 = r2_score(y[d:], y_pred[d:]) if len(y[d:]) == len(y_pred[d:]) and len(y[d:]) > 1 else None
    try:
        conf = np.array(fitted.get_forecast(steps=periods).conf_int(alpha=0.1))
        lower = np.round(conf[:, 0]).tolist()
        upper = np.round(conf[:, 1]).tolist()
    except Exception:
        lower = (fc * 0.85).round(0).tolist()
        upper = (fc * 1.15).round(0).tolist()

    return {
        "method": "arima", "order": f"({2},{d},{1})", "metric": metric,
        "historical": {"actual": y.tolist(), "fitted": y_pred.tolist()},
        "forecast": {"predicted": np.round(fc).tolist(), "lower": lower, "upper": upper},
        "summary": {"historical_total": round(float(y.sum()), 0),
                     "forecast_total": round(float(fc.sum()), 0),
                     "yoy_pct": round((fc.sum()-y.sum())/max(y.sum(),1)*100, 1)},
        "diagnostics": {"r_squared": round(float(r2), 4) if r2 else None,
                         "aic": round(float(fitted.aic), 1),
                         "bic": round(float(fitted.bic), 1),
                         "is_stationary": is_stationary, "adf_pvalue": round(float(adf_result[1]), 4)},
    }

def forecast_linear_fallback(df, metric="revenue", periods=12):
    """Simple linear trend + seasonal ratio. Fallback when Prophet/ARIMA unavailable."""
    time_col = "month" if "month" in df.columns else "date"
    monthly = df.groupby(time_col)[metric].sum().reset_index().sort_values(time_col)
    y = monthly[metric].values.astype(float); n = len(y)
    x = np.arange(n); mx, my = x.mean(), y.mean()
    num = ((x-mx)*(y-my)).sum(); den = ((x-mx)**2).sum()
    slope = num/den if den>0 else 0; intercept = my - slope*mx
    seasonal = y / np.maximum(slope*x + intercept, 1)
    fc = [max(0, (slope*(n+i)+intercept)*seasonal[i%n]) for i in range(periods)]
    y_pred = slope*x + intercept
    return {
        "method": "linear_seasonal_fallback", "metric": metric,
        "historical": {"actual": y.tolist()},
        "forecast": {"predicted": [round(f) for f in fc]},
        "summary": {"historical_total": round(float(y.sum()),0),
                     "forecast_total": round(sum(fc),0),
                     "yoy_pct": round((sum(fc)-y.sum())/max(y.sum(),1)*100,1)},
        "diagnostics": {"r_squared": round(float(r2_score(y, y_pred)), 4),
                         "warning": "Linear fallback — install prophet or statsmodels for proper forecasting"},
    }

def run_forecast(df, metric="revenue", periods=12, method="auto"):
    """Public API. Auto tries prophet → arima → linear."""
    if method == "auto":
        for fn, name in [(forecast_prophet, "prophet"), (forecast_arima, "arima")]:
            try:
                result = fn(df, metric, periods)
                logger.info(f"Forecast via {name}")
                return result
            except ImportError:
                logger.info(f"{name} not available, trying next...")
            except Exception as e:
                logger.warning(f"{name} failed: {e}")
        return forecast_linear_fallback(df, metric, periods)
    elif method == "prophet": return forecast_prophet(df, metric, periods)
    elif method == "arima": return forecast_arima(df, metric, periods)
    elif method == "linear": return forecast_linear_fallback(df, metric, periods)
    else: raise ValueError(f"Unknown method: {method}")
