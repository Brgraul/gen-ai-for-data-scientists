"""
Functions for loading and preparing energy market price data from Excel files.

This module handles loading price data from Excel files and preparing it
for flexibility cost calculations.
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Union
from pathlib import Path

from .models import MarketData


def load_and_prepare_data(file_path: Union[str, Path]) -> pd.DataFrame:
    """
    Load energy price data from Excel and prepare for flexibility calculations.
    
    Args:
        file_path: Excel file with DA prices (cols 1-2), IDA prices (cols 7-8),
                   and D-1 prices (cols 9-10)
    
    Returns:
        DataFrame with columns: da_time, da_prices, ida_time, ida_prices, d1_time, d1_prices
                              All times as datetime, all prices in €/MWh
    """
    # Skip header rows and load data
    df = pd.read_excel(file_path)
    df = df.iloc[6:].reset_index(drop=True)
    
    df.rename(columns={
        df.columns[1]: 'da_time', 
        df.columns[2]: 'da_prices', 
        df.columns[7]: 'ida_time', 
        df.columns[8]: 'ida_prices', 
        df.columns[9]: 'd1_time', 
        df.columns[10]: 'd1_prices'
    }, inplace=True)

    df['da_time'] = pd.to_datetime(df['da_time'])
    df['ida_time'] = pd.to_datetime(df['ida_time'])
    df['d1_time'] = pd.to_datetime(df['d1_time'])

    return df


def load_as_market_data(file_path: Union[str, Path]) -> MarketData:
    """
    Load market data and return as structured MarketData object.
    
    Args:
        file_path: Path to Excel file with market price data
        
    Returns:
        MarketData object with structured price data
    """
    df = load_and_prepare_data(file_path)
    
    return MarketData(
        da_time=df['da_time'],
        da_prices=df['da_prices'],
        ida_time=df['ida_time'],
        ida_prices=df['ida_prices'],
        d1_time=df['d1_time'],
        d1_prices=df['d1_prices']
    )


def expand_da_time(df: pd.DataFrame, time_column: str, price_column: str) -> pd.DataFrame:
    """
    Expand hourly DA price data into 15-minute intervals.
    
    Args:
        df: Source data with hourly prices
        time_column: Name of datetime column
        price_column: Name of price column (€/MWh)
    
    Returns:
        DataFrame with expanded 15-min intervals, keeping original hourly price
    """
    expanded_da = []
    for idx, row in df.iterrows():
        base_time = row[time_column]
        base_price = row[price_column]

        # Create entries for each quarter hour (00, 15, 30, 45)
        expanded_da.append({'da_time': base_time.replace(minute=0, second=0, microsecond=0), 'da_prices': base_price})
        expanded_da.append({'da_time': base_time.replace(minute=15, second=0, microsecond=0), 'da_prices': base_price})
        expanded_da.append({'da_time': base_time.replace(minute=30, second=0, microsecond=0), 'da_prices': base_price})
        expanded_da.append({'da_time': base_time.replace(minute=45, second=0, microsecond=0), 'da_prices': base_price})

    return pd.DataFrame(expanded_da) 