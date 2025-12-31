#!/usr/bin/env python3
"""
cashrake_sim.py

Simulate CashRake campaign and output daily / weekly / monthly sheets + charts.
"""

import argparse
from datetime import datetime
import calendar
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# ---------------------------
# Parameters
# ---------------------------
START_DATE = datetime(2025, 11, 23)
MONTHS = 12

STARTING_PLAYERS = 1000
AVG_DEPOSIT = 100.0
AVG_BET = 5.0
WAGER_MULTIPLIER = 7.0

CASHBACK_RATE = 0.03
HOUSE_EDGE = 0.04
RAKEBACK_RATE = 0.20
CAP_RATE = 0.33

ACQ_COST_PER_PLAYER = 40.0
RETENTION_RATE = 0.60

GROWTH_RATES_MAP = {1: 3.0, 2: 1.5, 3: 0.5}
DEFAULT_GROWTH_AFTER = 0.35

RAKEBACK_PER_WAGER_FRAC = HOUSE_EDGE * RAKEBACK_RATE
CASHBACK_PER_WAGER_FRAC = HOUSE_EDGE * CASHBACK_RATE
TOTAL_CASHRAKE_PER_WAGER_FRAC = RAKEBACK_PER_WAGER_FRAC + CASHBACK_PER_WAGER_FRAC

EXCEL_OUT = "cashrake_output.xlsx"
PLOT_PLAYERS = "monthly_players.png"
PLOT_REVENUE = "monthly_revenue_cashrake_profit.png"

# ---------------------------
# Utility functions
# ---------------------------
def get_month_starts(start_date, months):
    first = datetime(start_date.year, start_date.month, 1)
    return [first + pd.DateOffset(months=i) for i in range(months)]

def month_days(year, month):
    return calendar.monthrange(year, month)[1]

def get_growth_for_month(idx):
    if idx in GROWTH_RATES_MAP:
        return GROWTH_RATES_MAP[idx]
    elif idx > 3:
        return DEFAULT_GROWTH_AFTER
    else:
        return GROWTH_RATES_MAP.get(idx, DEFAULT_GROWTH_AFTER)

# ---------------------------
# Core simulation
# ---------------------------
def simulate(growth_model="retained_plus_new"):
    month_starts = get_month_starts(START_DATE, MONTHS)
    rows = []
    current_players = STARTING_PLAYERS
    lifetime_deposits = 0.0
    lifetime_cap_used = 0.0

    for m_idx, mstart in enumerate(month_starts, start=1):
        growth_param = get_growth_for_month(m_idx)
        if growth_model == "retained_plus_new":
            retained = current_players * RETENTION_RATE
            new_players = current_players * growth_param
            total_players = retained + new_players
        elif growth_model == "simple_growth":
            mult = 1.0 + growth_param
            total_players = current_players * mult
            retained = current_players * RETENTION_RATE
            new_players = max(total_players - retained, 0.0)
        else:
            raise ValueError("Unknown growth_model")

        deposits = total_players * AVG_DEPOSIT
        lifetime_deposits += deposits
        lifetime_cap = lifetime_deposits * CAP_RATE
        remaining_cap_before = max(0.0, lifetime_cap - lifetime_cap_used)

        total_wagering = deposits * WAGER_MULTIPLIER
        gross_revenue = total_wagering * HOUSE_EDGE

        expected_cashback = total_wagering * CASHBACK_PER_WAGER_FRAC
        expected_rakeback = total_wagering * RAKEBACK_PER_WAGER_FRAC
        expected_total_cashrake = expected_cashback + expected_rakeback

        actual_cashrake_paid = min(expected_total_cashrake, remaining_cap_before)
        lifetime_cap_used += actual_cashrake_paid
        remaining_cap_after = max(0.0, lifetime_cap - lifetime_cap_used)

        acq_cost = new_players * ACQ_COST_PER_PLAYER
        net_profit = gross_revenue - actual_cashrake_paid - acq_cost

        rows.append({
            "month_index": m_idx,
            "month_start": mstart.date(),
            "growth_param": growth_param,
            "growth_model": growth_model,
            "retained_players": retained,
            "new_players": new_players,
            "total_players": total_players,
            "deposits": deposits,
            "lifetime_deposits": lifetime_deposits,
            "lifetime_cap": lifetime_cap,
            "remaining_cap_before": remaining_cap_before,
            "expected_cashback": expected_cashback,
            "expected_rakeback": expected_rakeback,
            "expected_total_cashrake": expected_total_cashrake,
            "actual_cashrake_paid": actual_cashrake_paid,
            "lifetime_cap_used": lifetime_cap_used,
            "remaining_cap_after": remaining_cap_after,
            "total_wagering": total_wagering,
            "gross_revenue": gross_revenue,
            "acquisition_cost": acq_cost,
            "net_profit": net_profit
        })

        current_players = total_players

    monthly_df = pd.DataFrame(rows)

    # ---------------------------
    # Daily dataframe
    # ---------------------------
    daily_list = []
    for _, r in monthly_df.iterrows():
        y = pd.to_datetime(r['month_start']).year
        m = pd.to_datetime(r['month_start']).month
        ndays = month_days(y, m)
        for d in range(1, ndays+1):
            frac = 1.0 / ndays
            daily_list.append({
                "date": datetime(y, m, d).date(),
                "month_index": r['month_index'],
                "players": r['total_players'] * frac,
                "deposits": r['deposits'] * frac,
                "total_wagering": r['total_wagering'] * frac,
                "gross_revenue": r['gross_revenue'] * frac,
                "expected_cashback": r['expected_cashback'] * frac,
                "expected_rakeback": r['expected_rakeback'] * frac,
                "expected_total_cashrake": r['expected_total_cashrake'] * frac,
                "actual_cashrake_paid": r['actual_cashrake_paid'] * frac,
                "acquisition_cost": r['acquisition_cost'] * frac,
                "net_profit": r['net_profit'] * frac
            })
    daily_df = pd.DataFrame(daily_list)

    # ---------------------------
    # Weekly aggregation (Option 1: sum numeric only)
    # ---------------------------
    daily_df['date'] = pd.to_datetime(daily_df['date'])
    daily_df['week_start'] = daily_df['date'].dt.to_period('W').apply(lambda p: p.start_time.date())

    numeric_cols = daily_df.select_dtypes(include='number').columns
    weekly_df = daily_df.groupby('week_start', as_index=False)[numeric_cols].sum()

    return monthly_df, weekly_df, daily_df

# ---------------------------
# Save to Excel & plot
# ---------------------------
def save_and_plot(monthly_df, weekly_df, daily_df):
    with pd.ExcelWriter(EXCEL_OUT, engine='openpyxl') as writer:
        monthly_df.to_excel(writer, sheet_name='monthly', index=False)
        weekly_df.to_excel(writer, sheet_name='weekly', index=False)
        daily_df.to_excel(writer, sheet_name='daily', index=False)

    print(f"Excel saved to: {EXCEL_OUT}")

   #  plt.figure(figsize=(10,6))
   #  plt.plot(monthly_df['month_start'], monthly_df['total_players'], marker='o')
   # plt.title("Monthly Total Players")
   #  plt.xlabel("Month Start")
   #  plt.ylabel("Players")
   #  plt.grid(True)
   #  plt.tight_layout()
   #  plt.savefig(PLOT_PLAYERS)
   #  print(f"Saved plot: {PLOT_PLAYERS}")

   # plt.figure(figsize=(10,6))
   #  x = pd.to_datetime(monthly_df['month_start'])
   #  plt.plot(x, monthly_df['gross_revenue'], marker='o', label='Gross Revenue')
   #  plt.plot(x, monthly_df['actual_cashrake_paid'], marker='o', label='CashRake Paid')
   #  plt.plot(x, monthly_df['net_profit'], marker='o', label='Net Profit')
   #  plt.title("Monthly Revenue, CashRake Paid, Net Profit")
   #  plt.xlabel("Month Start")
   #  plt.ylabel("USD")
   #  plt.legend()
   #  plt.grid(True)
   #  plt.tight_layout()
   #  plt.savefig(PLOT_REVENUE)
   #  print(f"Saved plot: {PLOT_REVENUE}")

# ---------------------------
# CLI
# ---------------------------
def main():
    parser = argparse.ArgumentParser(description="CashRake campaign simulator")
    parser.add_argument("--growth-model", choices=["retained_plus_new", "simple_growth"],
                        default="retained_plus_new",
                        help="Growth model to use for monthly player calculation.")
    args = parser.parse_args()

    monthly_df, weekly_df, daily_df = simulate(growth_model=args.growth_model)

    pd.set_option("display.float_format", lambda x: f"{x:,.2f}")
    print("\n--- Monthly summary (preview) ---")
    print(monthly_df[['month_index','month_start','total_players','deposits','total_wagering','gross_revenue','actual_cashrake_paid','acquisition_cost','net_profit']])

    save_and_plot(monthly_df, weekly_df, daily_df)
    print("\nDone. Excel and plots generated in current folder.")

if __name__ == "__main__":
    main()
