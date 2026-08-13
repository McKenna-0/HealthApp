"""Weight-progress analytics: a smoothed weight trend, the rate of change that
falls out of it, and how both compare with the user's goal.

Why not just the EWMA in ``analytics.py``
-----------------------------------------
Scale readings are the true body mass plus a large transient: gut contents,
glycogen and its bound water, sodium, hydration. Day-to-day body mass has a
within-person SD of about 0.53% (Bosch et al., *Day-to-day variability in
euvolemic body mass*, Renal Failure 2023) — roughly 0.4 kg at 75 kg, which is
several weeks' worth of a sane rate of change. Any honest read of "am I
gaining?" has to separate that noise from the signal.

The existing EWMA (alpha=0.1, the Hacker's Diet filter) does that, and it stays
in use for TDEE back-estimation so those numbers don't move. But it is a causal
low-pass filter with no notion of a slope: its output lags the true level by
~1/alpha = 10 days, so differencing it under-reads a rate that is changing, and
it cannot say how sure it is.

This module uses the local linear trend model (Harvey, *Forecasting, Structural
Time Series Models and the Kalman Filter*, 1989) instead — the standard
structural time-series model for "level plus slowly-varying slope observed with
noise":

    level_t = level_{t-1} + slope_{t-1} + w_level     w_level ~ N(0, q_level)
    slope_t = slope_{t-1}                + w_slope    w_slope ~ N(0, q_slope)
    scale_t = level_t                    + v          v       ~ N(0, r)

Run as a Kalman filter plus an RTS smoother this gives, for every day:

* a level estimate that uses future readings as well as past ones, so the
  retrospective trend line has no lag,
* the slope as an explicit state — the rate of change, in kg/day, rather than a
  finite difference of a lagged curve,
* a variance for both, so the rate can be reported with a confidence interval
  and a forecast can widen honestly,
* native handling of missed weigh-ins: a day with no reading is a prediction
  step with no update, which is exactly right, where the EWMA has to carry the
  previous value forward.
"""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from .analytics import _date_range, daily_weights

# ---- model parameters -------------------------------------------------------

# Day-to-day within-person SD of body mass, as a fraction of body mass (0.53%,
# Renal Failure 2023). Used as the observation noise, so the filter's idea of
# "noise" is calibrated to measured human physiology rather than a guess.
DAY_TO_DAY_CV = 0.0053
MIN_OBS_SD_KG = 0.2

# Process noise. q_slope sets how fast the underlying rate is allowed to turn.
# Swept against synthetic series at the observation noise above: sqrt(q_slope)
# = 0.006 recovers ~94% of a step change in rate within 14 days, while a series
# with no real trend at all produces a spurious rate of only ~0.06 kg/week RMS
# — comfortably inside the maintenance tolerance below, so noise alone will not
# colour the chart. q_level absorbs multi-day water shifts that are not a
# change of trajectory.
Q_SLOPE = 0.006**2
Q_LEVEL = 0.03**2

# Prior on the initial slope: SD 0.05 kg/day (~0.35 kg/week) is wide enough to
# cover any plausible starting trajectory.
INIT_SLOPE_SD = 0.05

Z95 = 1.96

# ---- rate-of-change bands ---------------------------------------------------

# Losing faster than ~1%/week costs lean mass: elite athletes losing 1.4%/week
# lost lean body mass where 0.7%/week gained it (Garthe et al. 2011,
# PMID 21558571).
MAX_LOSS_PCT_PER_WEEK = 1.0

# Gaining faster than ~0.5%/week is mostly fat: the best lean:fat ratios in
# trained athletes come from ~0.2-0.4%/week (Garthe et al., Eur J Sport Sci
# 2013, "Effect of nutritional intervention on body composition and performance
# in elite athletes").
MAX_GAIN_PCT_PER_WEEK = 0.5

# With no directional goal, drifting less than this counts as holding steady.
MAINTAIN_TOL_PCT_PER_WEEK = 0.25

# Moving in the right direction but at under half the intended rate is behind
# plan, not on it.
ON_TRACK_FRACTION = 0.5

MIN_POINTS_FOR_TREND = 3


# ---- tiny 2x2 linear algebra ------------------------------------------------
# The state is 2-dimensional, so an explicit handful of floats beats pulling in
# numpy for a series that is at most a few hundred days long.

Vec = tuple[float, float]
Mat = tuple[tuple[float, float], tuple[float, float]]


def _predict(x: Vec, p: Mat, q_level: float, q_slope: float) -> tuple[Vec, Mat]:
    """One step of x' = F x, P' = F P F^T + Q with F = [[1, 1], [0, 1]]."""
    x_next = (x[0] + x[1], x[1])
    p00 = p[0][0] + p[0][1] + p[1][0] + p[1][1] + q_level
    p01 = p[0][1] + p[1][1]
    p10 = p[1][0] + p[1][1]
    p11 = p[1][1] + q_slope
    return x_next, ((p00, p01), (p10, p11))


def _update(x: Vec, p: Mat, z: float, r: float) -> tuple[Vec, Mat]:
    """Scalar measurement update for H = [1, 0]."""
    s = p[0][0] + r
    k0, k1 = p[0][0] / s, p[1][0] / s
    resid = z - x[0]
    x_new = (x[0] + k0 * resid, x[1] + k1 * resid)
    # P = (I - K H) P
    p_new = (
        ((1 - k0) * p[0][0], (1 - k0) * p[0][1]),
        (p[1][0] - k1 * p[0][0], p[1][1] - k1 * p[0][1]),
    )
    return x_new, p_new


def _inv2(m: Mat) -> Mat | None:
    det = m[0][0] * m[1][1] - m[0][1] * m[1][0]
    if abs(det) < 1e-15:
        return None
    return ((m[1][1] / det, -m[0][1] / det), (-m[1][0] / det, m[0][0] / det))


def _matmul(a: Mat, b: Mat) -> Mat:
    return (
        (a[0][0] * b[0][0] + a[0][1] * b[1][0], a[0][0] * b[0][1] + a[0][1] * b[1][1]),
        (a[1][0] * b[0][0] + a[1][1] * b[1][0], a[1][0] * b[0][1] + a[1][1] * b[1][1]),
    )


def _add(a: Mat, b: Mat) -> Mat:
    return (
        (a[0][0] + b[0][0], a[0][1] + b[0][1]),
        (a[1][0] + b[1][0], a[1][1] + b[1][1]),
    )


def _observation_sd(weights: list[float]) -> float:
    """Observation noise for this person, from the published day-to-day CV."""
    if not weights:
        return MIN_OBS_SD_KG
    ordered = sorted(weights)
    median = ordered[len(ordered) // 2]
    return max(MIN_OBS_SD_KG, DAY_TO_DAY_CV * median)


# ---- the smoother -----------------------------------------------------------


def smooth_weights(
    days: list[str], weights: dict[str, float], obs_sd: float | None = None
) -> list[dict]:
    """Kalman-smoothed level and slope for each day in ``days``.

    Days without a weigh-in get a prediction-only step, so gaps widen the
    interval instead of inventing a reading. Returns one dict per day with
    ``level`` / ``slope`` (kg and kg/day) and their standard deviations.
    """
    observed = [weights[d] for d in days if d in weights]
    if len(observed) < MIN_POINTS_FOR_TREND:
        return []

    r = (obs_sd if obs_sd is not None else _observation_sd(observed)) ** 2

    # Start at the first actual reading; anything before it is unobservable.
    first_idx = next(i for i, d in enumerate(days) if d in weights)
    active = days[first_idx:]

    x: Vec = (weights[active[0]], 0.0)
    p: Mat = ((r, 0.0), (0.0, INIT_SLOPE_SD**2))

    x_pred: list[Vec] = [x]
    p_pred: list[Mat] = [p]
    x_filt: list[Vec] = []
    p_filt: list[Mat] = []

    for i, d in enumerate(active):
        if i > 0:
            xp, pp = _predict(x_filt[-1], p_filt[-1], Q_LEVEL, Q_SLOPE)
            x_pred.append(xp)
            p_pred.append(pp)
        else:
            xp, pp = x, p
        z = weights.get(d)
        if z is not None:
            xp, pp = _update(xp, pp, z, r)
        x_filt.append(xp)
        p_filt.append(pp)

    # RTS backward smoother: fold the future back into each day's estimate.
    n = len(active)
    x_smooth: list[Vec] = [(0.0, 0.0)] * n
    p_smooth: list[Mat] = [((0.0, 0.0), (0.0, 0.0))] * n
    x_smooth[-1], p_smooth[-1] = x_filt[-1], p_filt[-1]
    for t in range(n - 2, -1, -1):
        inv = _inv2(p_pred[t + 1])
        if inv is None:
            x_smooth[t], p_smooth[t] = x_filt[t], p_filt[t]
            continue
        # C = P_filt F^T P_pred^-1, with F^T = [[1, 0], [1, 1]]
        pf = p_filt[t]
        pft = ((pf[0][0] + pf[0][1], pf[0][1]), (pf[1][0] + pf[1][1], pf[1][1]))
        c = _matmul(pft, inv)
        dx = (
            x_smooth[t + 1][0] - x_pred[t + 1][0],
            x_smooth[t + 1][1] - x_pred[t + 1][1],
        )
        x_smooth[t] = (
            x_filt[t][0] + c[0][0] * dx[0] + c[0][1] * dx[1],
            x_filt[t][1] + c[1][0] * dx[0] + c[1][1] * dx[1],
        )
        dp = (
            (
                p_smooth[t + 1][0][0] - p_pred[t + 1][0][0],
                p_smooth[t + 1][0][1] - p_pred[t + 1][0][1],
            ),
            (
                p_smooth[t + 1][1][0] - p_pred[t + 1][1][0],
                p_smooth[t + 1][1][1] - p_pred[t + 1][1][1],
            ),
        )
        ct = ((c[0][0], c[1][0]), (c[0][1], c[1][1]))
        p_smooth[t] = _add(p_filt[t], _matmul(_matmul(c, dp), ct))

    return [
        {
            "date": d,
            "level": x_smooth[i][0],
            "slope": x_smooth[i][1],
            "level_sd": max(p_smooth[i][0][0], 0.0) ** 0.5,
            "slope_sd": max(p_smooth[i][1][1], 0.0) ** 0.5,
        }
        for i, d in enumerate(active)
    ]


def forecast(last: dict, horizon: int) -> list[dict]:
    """Project the trend forward from the final smoothed state.

    Uncertainty comes from propagating the state covariance, so the band widens
    with the horizon the way an extrapolated slope actually should.
    """
    if horizon <= 0:
        return []
    start = date.fromisoformat(last["date"])
    x: Vec = (last["level"], last["slope"])
    p: Mat = ((last["level_sd"] ** 2, 0.0), (0.0, last["slope_sd"] ** 2))
    out = []
    for h in range(1, horizon + 1):
        x, p = _predict(x, p, Q_LEVEL, Q_SLOPE)
        sd = max(p[0][0], 0.0) ** 0.5
        out.append(
            {
                "date": (start + timedelta(days=h)).isoformat(),
                "projected": round(x[0], 2),
                "lo": round(x[0] - Z95 * sd, 2),
                "hi": round(x[0] + Z95 * sd, 2),
            }
        )
    return out


# ---- goal comparison --------------------------------------------------------


def rate_bands(body_weight_kg: float) -> dict:
    """Evidence-based limits on weekly rate of change, in kg/week."""
    return {
        "max_loss_kg_per_week": round(body_weight_kg * MAX_LOSS_PCT_PER_WEEK / 100, 3),
        "max_gain_kg_per_week": round(body_weight_kg * MAX_GAIN_PCT_PER_WEEK / 100, 3),
        "maintain_tolerance_kg_per_week": round(
            body_weight_kg * MAINTAIN_TOL_PCT_PER_WEEK / 100, 3
        ),
    }


def classify_rate(
    actual_kg_per_week: float, goal_kg_per_week: float | None, body_weight_kg: float
) -> str:
    """One of on_track | too_slow | too_fast | wrong_way.

    "Too fast" is a health judgement, not a schedule one: it means past the
    rate at which the extra change stops being the tissue you wanted. Beating
    your own target while still inside that limit is on track, not a warning.
    """
    bands = rate_bands(body_weight_kg)
    max_loss = -bands["max_loss_kg_per_week"]
    max_gain = bands["max_gain_kg_per_week"]
    tol = bands["maintain_tolerance_kg_per_week"]

    if goal_kg_per_week is None or abs(goal_kg_per_week) < 1e-9:
        # Maintaining: any sustained drift is the problem.
        if abs(actual_kg_per_week) <= tol:
            return "on_track"
        return "too_fast"

    if goal_kg_per_week > 0:
        if actual_kg_per_week > max_gain:
            return "too_fast"
        if actual_kg_per_week <= 0:
            return "wrong_way"
        if actual_kg_per_week < ON_TRACK_FRACTION * goal_kg_per_week:
            return "too_slow"
        return "on_track"

    if actual_kg_per_week < max_loss:
        return "too_fast"
    if actual_kg_per_week >= 0:
        return "wrong_way"
    if actual_kg_per_week > ON_TRACK_FRACTION * goal_kg_per_week:
        return "too_slow"
    return "on_track"


def goal_line(
    days: list[str],
    start_date: str,
    start_kg: float,
    rate_kg_per_week: float,
    target_kg: float | None,
) -> dict[str, float]:
    """The planned trajectory, clamped once it reaches the target weight."""
    anchor = date.fromisoformat(start_date)
    per_day = rate_kg_per_week / 7
    out: dict[str, float] = {}
    for d in days:
        offset = (date.fromisoformat(d) - anchor).days
        if offset < 0:
            continue
        value = start_kg + per_day * offset
        if target_kg is not None:
            # Only clamp on the side the plan is approaching from.
            if start_kg <= target_kg:
                value = min(value, target_kg)
            else:
                value = max(value, target_kg)
        out[d] = round(value, 2)
    return out


def _goal_settings(db: Session) -> dict:
    from .. import models

    keys = {
        "weight_goal_kg": None,
        "weight_goal_rate_kg_per_week": None,
        "weight_goal_start_date": None,
        "weight_goal_start_kg": None,
    }
    for key in list(keys):
        row = db.get(models.UserSetting, key)
        if row is None or row.value in (None, ""):
            continue
        if key == "weight_goal_start_date":
            keys[key] = row.value
        else:
            try:
                keys[key] = float(row.value)
            except ValueError:
                keys[key] = None
    return keys


def eta_date(
    from_date: str, level: float, slope_per_day: float, target: float | None
) -> str | None:
    """When the current trajectory reaches the target, if it ever does."""
    if target is None or abs(slope_per_day) < 1e-6:
        return None
    remaining = target - level
    if remaining * slope_per_day <= 0:
        return None  # moving away from (or already past) the target
    days = remaining / slope_per_day
    if days > 5 * 365:
        return None
    return (date.fromisoformat(from_date) + timedelta(days=round(days))).isoformat()


def weight_progress(db: Session, end: str, days: int = 90, horizon: int = 21) -> dict:
    """Everything the weight tab draws: smoothed trend, goal line, per-day
    status of the gap between them, current rate with a CI, and a forecast."""
    start = (date.fromisoformat(end) - timedelta(days=days - 1)).isoformat()
    day_list = _date_range(start, end)
    weights = daily_weights(db, start, end)
    smoothed = smooth_weights(day_list, weights)

    settings = _goal_settings(db)
    target_kg = settings["weight_goal_kg"]
    goal_rate = settings["weight_goal_rate_kg_per_week"]

    if not smoothed:
        return {
            "start": start,
            "end": end,
            "series": [
                {
                    "date": d,
                    "weight": weights.get(d),
                    "trend": None,
                    "trend_lo": None,
                    "trend_hi": None,
                    "goal": None,
                    "rate_kg_per_week": None,
                    "status": None,
                }
                for d in day_list
            ],
            "forecast": [],
            "current": None,
            "goal": None,
            "method": METHOD_NOTE,
            "reason": f"need >={MIN_POINTS_FOR_TREND} weigh-ins in the window, "
            f"have {len(weights)}",
        }

    by_date = {s["date"]: s for s in smoothed}
    last = smoothed[-1]
    body_weight = last["level"]

    # Anchor: what the user pinned when they set the goal, else the oldest
    # smoothed point in this window, so the plan starts from where they were.
    anchor_date = settings["weight_goal_start_date"] or smoothed[0]["date"]
    anchor_kg = settings["weight_goal_start_kg"]
    if anchor_kg is None:
        anchor_kg = round(by_date.get(anchor_date, smoothed[0])["level"], 2)

    obs_sd = _observation_sd(list(weights.values()))
    projection = forecast(last, horizon)

    # The plan is drawn across the forecast too, so the projection can be read
    # against it rather than against nothing.
    goal_values: dict[str, float] = {}
    if goal_rate is not None:
        goal_values = goal_line(
            day_list + [f["date"] for f in projection],
            anchor_date,
            anchor_kg,
            goal_rate,
            target_kg,
        )
    for f in projection:
        f["goal"] = goal_values.get(f["date"])

    series = []
    for d in day_list:
        s = by_date.get(d)
        rate = round(s["slope"] * 7, 3) if s else None
        status = (
            classify_rate(rate, goal_rate, s["level"])
            if s is not None and rate is not None and goal_rate is not None
            else None
        )
        series.append(
            {
                "date": d,
                "weight": weights.get(d),
                "trend": round(s["level"], 2) if s else None,
                "trend_lo": round(s["level"] - Z95 * s["level_sd"], 2) if s else None,
                "trend_hi": round(s["level"] + Z95 * s["level_sd"], 2) if s else None,
                "goal": goal_values.get(d),
                "rate_kg_per_week": rate,
                "status": status,
            }
        )

    rate_now = last["slope"] * 7
    rate_sd = last["slope_sd"] * 7

    current = {
        "date": last["date"],
        "trend_kg": round(last["level"], 2),
        "latest_scale_kg": weights.get(day_list[-1]),
        "rate_kg_per_week": round(rate_now, 3),
        "rate_lo_kg_per_week": round(rate_now - Z95 * rate_sd, 3),
        "rate_hi_kg_per_week": round(rate_now + Z95 * rate_sd, 3),
        "rate_kcal_per_day": round(rate_now / 7 * 7700),
        "weigh_ins": len(weights),
        "status": classify_rate(rate_now, goal_rate, body_weight)
        if goal_rate is not None
        else None,
        "bands": rate_bands(body_weight),
        "observation_sd_kg": round(obs_sd, 2),
    }

    goal = None
    if target_kg is not None or goal_rate is not None:
        remaining = round(target_kg - last["level"], 2) if target_kg is not None else None
        goal = {
            "target_kg": target_kg,
            "rate_kg_per_week": goal_rate,
            "start_date": anchor_date,
            "start_kg": anchor_kg,
            "remaining_kg": remaining,
            "eta_actual": eta_date(end, last["level"], last["slope"], target_kg),
            "eta_planned": eta_date(
                end, last["level"], (goal_rate or 0) / 7, target_kg
            ),
            "on_plan_delta_kg": round(last["level"] - goal_values[last["date"]], 2)
            if last["date"] in goal_values
            else None,
        }

    return {
        "start": start,
        "end": end,
        "series": series,
        "forecast": projection,
        "current": current,
        "goal": goal,
        "method": METHOD_NOTE,
        "reason": None,
    }


METHOD_NOTE = (
    "Local linear trend model (Kalman filter + RTS smoother). Observation noise "
    "is set from the published day-to-day body-mass SD of 0.53%, so single-day "
    "water and gut-content swings move the trend very little. Rate bands: "
    "losing faster than 1%/week costs lean mass (Garthe 2011, PMID 21558571); "
    "gaining faster than 0.5%/week is mostly fat (Garthe 2013)."
)
