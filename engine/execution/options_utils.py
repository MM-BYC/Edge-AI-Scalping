from datetime import date, timedelta


def occ_symbol(underlying: str, expiry: date, option_type: str, strike: float) -> str:
    """OCC option symbol, e.g. SPY240429P00500000"""
    date_str = expiry.strftime("%y%m%d")
    cp = "C" if option_type.upper() == "CALL" else "P"
    return f"{underlying}{date_str}{cp}{round(strike * 1000):08d}"


def next_weekly_expiry(min_dte: int = 7) -> date:
    """Next Friday that is at least min_dte calendar days away."""
    today = date.today()
    candidate = today + timedelta(days=1)
    while True:
        if candidate.weekday() == 4 and (candidate - today).days >= min_dte:
            return candidate
        candidate += timedelta(days=1)
