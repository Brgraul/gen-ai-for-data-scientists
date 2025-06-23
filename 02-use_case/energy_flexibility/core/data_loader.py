"""
Functions for loading and preparing energy market price data from parquet files.

This module handles loading price data from parquet files and preparing it
for flexibility cost calculations.
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Union
from pathlib import Path

from .models import MarketData


def load_and_prepare_data(file_path: Union[str, Path]) -> pd.DataFrame:
    """
    Load energy price data from parquet and prepare for flexibility calculations.
    
    Args:
        file_path: Parquet file with DA prices (cols 1-2), IDA prices (cols 7-8),
                   and D-1 prices (cols 9-10)
    
    Returns:
        DataFrame with columns: da_time, da_prices, ida_time, ida_prices, d1_time, d1_prices
                              All times as datetime, all prices in €/MWh
    """
    # Load parquet data (no need to skip header rows like with Excel)
    df = pd.read_parquet(file_path)
    
    # The parquet file already has clean column names from conversion
    # Rename columns to match expected names based on their position
    df.rename(columns={
        df.columns[1]: 'da_time', 
        df.columns[2]: 'da_prices', 
        df.columns[7]: 'ida_time', 
        df.columns[8]: 'ida_prices', 
        df.columns[9]: 'd1_time', 
        df.columns[10]: 'd1_prices'
    }, inplace=True)

    # Ensure datetime columns are properly typed (they should already be from parquet)
    df['da_time'] = pd.to_datetime(df['da_time'])
    df['ida_time'] = pd.to_datetime(df['ida_time'])
    df['d1_time'] = pd.to_datetime(df['d1_time'])

    return df


def load_as_market_data(file_path: Union[str, Path]) -> MarketData:
    """
    Load market data and return as structured MarketData object.
    
    Args:
        file_path: Path to parquet file with market price data
        
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
    # Vectorized approach: create all time intervals at once
    expanded_data = []
    
    # Create time offsets for 15-minute intervals
    time_offsets = pd.to_timedelta([0, 15, 30, 45], unit='min')
    
    for offset in time_offsets:
        expanded_slice = df[[time_column, price_column]].copy()
        expanded_slice['da_time'] = df[time_column] + offset
        expanded_slice['da_prices'] = df[price_column]
        expanded_data.append(expanded_slice[['da_time', 'da_prices']])
    
    # Concatenate all expanded intervals
    result = pd.concat(expanded_data, ignore_index=True)
    
    # Sort by time to maintain chronological order
    result = result.sort_values('da_time').reset_index(drop=True)
    
    # Clean time precision to minute level
    result['da_time'] = result['da_time'].dt.floor('min')
    
    return result 