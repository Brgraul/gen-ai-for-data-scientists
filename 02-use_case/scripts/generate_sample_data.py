#!/usr/bin/env python3
"""
Generate sample data for pumped hydro flexibility calculations.

This script creates realistic sample data for:
1. fahrplan.xls - Pumped hydro operational schedule 
2. 20241128_Spotpreise Power_Gas.xlsx - Energy market prices

Data structure based on analysis of main.py requirements.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

# Configuration
DELIVERY_DATE = "2023-04-30"
BASE_PATH = os.path.dirname(os.path.abspath(__file__))
INPUT_PATH = os.path.join(BASE_PATH, "input")

# Ensure input directory exists
os.makedirs(INPUT_PATH, exist_ok=True)

def generate_energy_prices():
    """
    Generate realistic energy market price data for DA, IDA, and D-1 markets.
    Covers 100 days before delivery date plus delivery day itself.
    """
    print("Generating energy price data...")
    
    delivery_dt = datetime.strptime(DELIVERY_DATE, "%Y-%m-%d")
    start_date = delivery_dt - timedelta(days=100)  # 100 days history
    
    # Generate hourly timestamps for DA (Day-Ahead) market
    da_times = []
    current_time = start_date
    while current_time <= delivery_dt:
        for hour in range(24):
            da_times.append(current_time.replace(hour=hour, minute=0, second=0))
        current_time += timedelta(days=1)
    
    # Generate 15-minute timestamps for IDA (Intraday Auction) and D-1 markets
    ida_times = []
    d1_times = []
    current_time = start_date
    while current_time <= delivery_dt:
        for hour in range(24):
            for minute in [0, 15, 30, 45]:
                timestamp = current_time.replace(hour=hour, minute=minute, second=0)
                ida_times.append(timestamp)
                d1_times.append(timestamp)
        current_time += timedelta(days=1)
    
    # Generate realistic price patterns
    np.random.seed(42)  # For reproducible results
    
    # Base price with seasonal and daily patterns
    base_price = 50  # €/MWh
    
    # DA prices (hourly) - smooth daily curve
    da_prices = []
    for i, dt in enumerate(da_times):
        # Daily pattern: higher prices during peak hours (8-10, 18-20)
        hour_factor = 1.0
        if 8 <= dt.hour <= 10 or 18 <= dt.hour <= 20:
            hour_factor = 1.4  # Peak hours
        elif 22 <= dt.hour or dt.hour <= 6:
            hour_factor = 0.7  # Off-peak hours
        
        # Weekly pattern: higher on weekdays
        weekday_factor = 1.1 if dt.weekday() < 5 else 0.9
        
        # Random variation
        random_factor = 1 + np.random.normal(0, 0.2)
        
        price = base_price * hour_factor * weekday_factor * random_factor
        da_prices.append(max(0, price))  # Ensure non-negative prices
    
    # IDA prices (15-minute) - more volatile, based on DA with spreads
    ida_prices = []
    for i, dt in enumerate(ida_times):
        # Find corresponding DA price (same hour)
        da_hour = dt.replace(minute=0)
        try:
            da_idx = da_times.index(da_hour)
            base_da_price = da_prices[da_idx]
        except ValueError:
            base_da_price = base_price
        
        # IDA typically has spread vs DA
        spread = np.random.normal(0, 5)  # €/MWh spread
        volatility = np.random.normal(1, 0.15)  # Additional volatility
        
        ida_price = base_da_price * volatility + spread
        ida_prices.append(max(0, ida_price))
    
    # D-1 prices (15-minute) - between DA and IDA volatility
    d1_prices = []
    for i, dt in enumerate(d1_times):
        # Find corresponding IDA price
        try:
            ida_price = ida_prices[i]
        except IndexError:
            ida_price = base_price
        
        # D-1 usually between DA and IDA
        d1_adjustment = np.random.normal(0, 3)  # €/MWh
        d1_price = ida_price + d1_adjustment
        d1_prices.append(max(0, d1_price))
    
    # Create DataFrame with proper structure
    # Need to pad shorter lists to match the longest
    max_len = max(len(da_times), len(ida_times), len(d1_times))
    
    # Create the data structure expected by the code
    data = {
        'col_0': [''] * max_len,  # Empty column 0
        'da_time': da_times + [None] * (max_len - len(da_times)),
        'da_prices': da_prices + [None] * (max_len - len(da_prices)),
        'col_3': [''] * max_len,  # Empty columns 3-6
        'col_4': [''] * max_len,
        'col_5': [''] * max_len,
        'col_6': [''] * max_len,
        'ida_time': ida_times + [None] * (max_len - len(ida_times)),
        'ida_prices': ida_prices + [None] * (max_len - len(ida_prices)),
        'd1_time': d1_times + [None] * (max_len - len(d1_times)),
        'd1_prices': d1_prices + [None] * (max_len - len(d1_prices)),
    }
    
    df = pd.DataFrame(data)
    
    # Add header rows (first 6 rows are skipped by the code)
    header_rows = []
    for i in range(6):
        header_row = {col: f'Header_{i+1}' if i == 0 else '' for col in df.columns}
        header_rows.append(header_row)
    
    header_df = pd.DataFrame(header_rows)
    final_df = pd.concat([header_df, df], ignore_index=True)
    
    # Save to Excel
    price_file = os.path.join(INPUT_PATH, "20241128_Spotpreise Power_Gas.xlsx")
    final_df.to_excel(price_file, index=False)
    print(f"✓ Energy prices saved to: {price_file}")
    print(f"  - DA prices: {len(da_prices)} hourly values")
    print(f"  - IDA prices: {len(ida_prices)} 15-min values") 
    print(f"  - D-1 prices: {len(d1_prices)} 15-min values")
    

def generate_fahrplan():
    """
    Generate realistic pumped hydro operational schedule for delivery date.
    96 time slots (15-minute intervals) for 24 hours.
    """
    print(f"Generating pumped hydro schedule for {DELIVERY_DATE}...")
    
    delivery_dt = datetime.strptime(DELIVERY_DATE, "%Y-%m-%d")
    
    # Generate 15-minute time slots for the full day
    times = []
    for hour in range(24):
        for minute in [0, 15, 30, 45]:
            times.append(delivery_dt.replace(hour=hour, minute=minute, second=0))
    
    # System parameters (from main.py)
    MAX_DISCHARGE_POWER = 15  # MW (turbine)
    MAX_CHARGE_POWER = 15     # MW (pump)
    
    np.random.seed(123)  # For reproducible results
    
    # Generate realistic operational data
    data_rows = []
    
    for i, time_slot in enumerate(times):
        hour = time_slot.hour
        
        # Available capacities (vary by time due to maintenance, constraints)
        pmax = MAX_DISCHARGE_POWER * np.random.uniform(0.8, 1.0)  # 80-100% availability
        vmax = MAX_CHARGE_POWER * np.random.uniform(0.8, 1.0)     # 80-100% availability
        
        # Planned power (Pt) - realistic pumped hydro operation pattern
        # Typically charge at night (negative), discharge during peak (positive)
        if 23 <= hour or hour <= 6:  # Night hours - charging
            pt = -np.random.uniform(5, 12)  # Charge 5-12 MW
        elif 8 <= hour <= 10 or 18 <= hour <= 20:  # Peak hours - discharge
            pt = np.random.uniform(8, 15)   # Discharge 8-15 MW
        else:  # Off-peak hours - variable
            pt = np.random.uniform(-5, 5)   # Light operation
        
        # Redispatch (Prd) - TSO requests
        # Most time slots have no redispatch
        if np.random.random() < 0.8:  # 80% no redispatch
            prd = 0
            redispatch_type = "keine"
        else:  # 20% have redispatch
            prd = np.random.uniform(-5, 5)
            if np.random.random() < 0.6:
                redispatch_type = "einseitig"
            else:
                redispatch_type = "beidseitig"
        
        # New power (Pnew = Pt + Prd)
        pnew = pt + prd
        
        # Reserve capacities
        pos_vorgehaltene_leistung = np.random.uniform(0, 3)  # 0-3 MW positive reserves
        neg_vorgehaltene_leistung = np.random.uniform(0, 3)  # 0-3 MW negative reserves
        
        data_rows.append({
            'time': time_slot,
            'Pmax': round(pmax, 2),
            'Vmax': round(vmax, 2), 
            'Pt': round(pt, 2),
            'Prd': round(prd, 2),
            'Pnew': round(pnew, 2),
            'RedispatchType': redispatch_type,
            'pos_vorgehaltene_leistung': round(pos_vorgehaltene_leistung, 2),
            'neg_vorgehaltene_leistung': round(neg_vorgehaltene_leistung, 2)
        })
    
    df = pd.DataFrame(data_rows)
    
    # Add header rows (first 12 rows are skipped by the code)
    header_data = []
    for i in range(12):
        if i == 0:
            header_row = {col: f'Header_{col}' for col in df.columns}
        else:
            header_row = {col: '' for col in df.columns}
        header_data.append(header_row)
    
    header_df = pd.DataFrame(header_data)
    final_df = pd.concat([header_df, df], ignore_index=True)
    
    # Save to Excel with 'intern' sheet
    fahrplan_file = os.path.join(INPUT_PATH, "fahrplan.xls")
    with pd.ExcelWriter(fahrplan_file, engine='xlsxwriter') as writer:
        final_df.to_excel(writer, sheet_name='intern', index=False)
    
    print(f"✓ Fahrplan saved to: {fahrplan_file}")
    print(f"  - 96 time slots (15-minute intervals)")
    print(f"  - Planned operations: {len([r for r in data_rows if r['RedispatchType'] == 'keine'])} normal, {len([r for r in data_rows if r['RedispatchType'] != 'keine'])} redispatch")
    print(f"  - Power range: {min(df['Pt']):.1f} to {max(df['Pt']):.1f} MW")


def main():
    """Generate both sample data files."""
    print("=== Generating Sample Data for Pumped Hydro Flexibility Analysis ===")
    print(f"Delivery Date: {DELIVERY_DATE}")
    print(f"Output Directory: {INPUT_PATH}")
    print()
    
    # Generate both files
    generate_energy_prices()
    print()
    generate_fahrplan()
    
    print()
    print("=== Sample Data Generation Complete ===")
    print("Files created:")
    print(f"  - {os.path.join(INPUT_PATH, '20241128_Spotpreise Power_Gas.xlsx')}")
    print(f"  - {os.path.join(INPUT_PATH, 'fahrplan.xls')}")
    print()
    print("These files contain realistic sample data that matches the expected")
    print("data structures in main.py and can be used for testing the flexibility")
    print("cost calculation algorithms.")


if __name__ == "__main__":
    main() 