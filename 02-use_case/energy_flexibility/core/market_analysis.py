"""
Market analysis functions for price forecasting and market calculations.
Handles price forecasting, spread calculations, and volatility analysis for energy markets.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Union

from .data_loader import expand_da_time
from .models import PriceData, VolatilityData, DeliveryDate


def calculate_average_diff(market_data_df: pd.DataFrame, delivery_date: Union[str, datetime], lookback_days: int = 90) -> pd.Series:
    """
    Calculate historical average price differences between Intraday Auction (IDA) and Day-Ahead (DA) markets.
    
    Args:
        market_data_df: Dataset with ida_time, ida_prices, da_time, da_prices columns
        delivery_date: Target delivery date ("YYYY-MM-DD" if string)
        lookback_days: Historical lookback period in days (default: 90)
    
    Returns:
        Time-indexed (HH:MM) average price differences between IDA and DA
    """
    if isinstance(delivery_date, str):
        delivery_date = datetime.strptime(delivery_date, "%Y-%m-%d")
    
    historical_start_date = delivery_date - timedelta(days=lookback_days)

    # Filter data for analysis period
    ida_historical_data = market_data_df[
        (market_data_df['ida_time'] >= historical_start_date) & 
        (market_data_df['ida_time'] < delivery_date)
    ].copy()

    da_historical_data = market_data_df[
        (market_data_df['da_time'] >= historical_start_date) & 
        (market_data_df['da_time'] < delivery_date)
    ].copy()

    # Return zero differences if insufficient data
    if ida_historical_data.empty or da_historical_data.empty:
        fifteen_min_time_slots = [f"{hour:02d}:{minute:02d}" 
                     for hour in range(24) 
                     for minute in [0, 15, 30, 45]]
        return pd.Series(0.0, index=fifteen_min_time_slots)

    # Expand DA prices to 15-min intervals and normalize timestamps
    fifteen_min_da_data = expand_da_time(da_historical_data, 'da_time', 'da_prices')
    if fifteen_min_da_data.empty:
        fifteen_min_time_slots = [f"{hour:02d}:{minute:02d}" 
                     for hour in range(24) 
                     for minute in [0, 15, 30, 45]]
        return pd.Series(0.0, index=fifteen_min_time_slots)

    ida_historical_data['ida_time'] = ida_historical_data['ida_time'].dt.floor('15min')
    fifteen_min_da_data['da_time'] = fifteen_min_da_data['da_time'].dt.floor('15min')

    # Calculate average price differences per time slot
    ida_da_merged_data = pd.merge(
        fifteen_min_da_data,
        ida_historical_data[['ida_time', 'ida_prices']],
        left_on='da_time',
        right_on='ida_time',
        how='left'
    )
    ida_da_merged_data['ida_da_price_spread'] = ida_da_merged_data['ida_prices'] - ida_da_merged_data['da_prices']
    ida_da_merged_data['time_slot'] = ida_da_merged_data['da_time'].dt.strftime('%H:%M')
    
    return ida_da_merged_data.groupby('time_slot')['ida_da_price_spread'].mean()


def adjust_da_prices_for_date(market_data_df: pd.DataFrame, delivery_date: Union[str, datetime], historical_ida_da_spread: pd.Series) -> pd.DataFrame:
    """
    Adjust Day-Ahead prices to predict Intraday Auction prices for a specific date.
    
    Args:
        market_data_df: Dataset with da_time and da_prices columns
        delivery_date: Target delivery date ("YYYY-MM-DD" if string)
        historical_ida_da_spread: Historical average price differences by time-of-day
    
    Returns:
        DataFrame containing da_time, da_prices, and adjusted_da_prices columns
    """
    if isinstance(delivery_date, str):
        delivery_date = datetime.strptime(delivery_date, "%Y-%m-%d")
    
    # Get DA prices for delivery date
    delivery_day_da_prices = market_data_df[market_data_df['da_time'].dt.date == delivery_date.date()].copy()
    if delivery_day_da_prices.empty:
        raise ValueError(f"No DA price data found for delivery date: {delivery_date}")
    
    # Expand to 15-min intervals and apply adjustments
    fifteen_min_delivery_prices = expand_da_time(delivery_day_da_prices, 'da_time', 'da_prices')
    fifteen_min_delivery_prices['time_slot'] = fifteen_min_delivery_prices['da_time'].dt.strftime('%H:%M')
    fifteen_min_delivery_prices['adjusted_da_prices'] = fifteen_min_delivery_prices.apply(
        lambda row: row['da_prices'] + historical_ida_da_spread.get(row['time_slot'], 0), 
        axis=1
    )
    
    return fifteen_min_delivery_prices[['da_time', 'da_prices', 'adjusted_da_prices']]


def create_price_data(market_data_df: pd.DataFrame, delivery_date: Union[str, datetime], historical_ida_da_spread: pd.Series) -> PriceData:
    """
    Create a structured PriceData object with adjusted prices.
    
    Args:
        market_data_df: Dataset with da_time and da_prices columns
        delivery_date: Target delivery date
        historical_ida_da_spread: Historical average price differences
        
    Returns:
        PriceData object with structured price information
    """
    adjusted_price_data = adjust_da_prices_for_date(market_data_df, delivery_date, historical_ida_da_spread)
    
    return PriceData(
        da_time=adjusted_price_data['da_time'],
        da_prices=adjusted_price_data['da_prices'],
        adjusted_da_prices=adjusted_price_data['adjusted_da_prices']
    )


def calculate_standard_deviation(market_data_df: pd.DataFrame, delivery_day: Union[str, datetime], lookback_days: int = 30) -> pd.Series:
    """
    Calculate price volatility (standard deviation) for option pricing and risk assessment.
    
    Args:
        market_data_df: Dataset with ida_time and ida_prices columns
        delivery_day: Target delivery date ("YYYY-MM-DD" if string)
        lookback_days: Historical lookback period in days (default: 30)
    
    Returns:
        Time-indexed (HH:MM) price standard deviations
    """
    if isinstance(delivery_day, str):
        delivery_day = datetime.strptime(delivery_day, "%Y-%m-%d")
    
    # Filter historical data
    volatility_analysis_start = delivery_day - timedelta(days=lookback_days)
    ida_volatility_data = market_data_df[
        (market_data_df['ida_time'] >= volatility_analysis_start) & 
        (market_data_df['ida_time'] < delivery_day)
    ].copy()
    
    if ida_volatility_data.empty:
        raise ValueError(f"No IDA price data found for the specified period: {volatility_analysis_start} to {delivery_day}")
    
    # Calculate standard deviation per time slot
    ida_volatility_data['ida_time'] = ida_volatility_data['ida_time'].dt.floor('15min')
    ida_volatility_data['time_slot'] = ida_volatility_data['ida_time'].dt.strftime('%H:%M')
    time_slot_volatility = ida_volatility_data.groupby('time_slot')['ida_prices'].std()
    
    # Handle edge cases with sensible defaults
    fallback_volatility = ida_volatility_data['ida_prices'].std() or 10.0  # Default fallback volatility
    time_slot_volatility = time_slot_volatility.fillna(fallback_volatility)
    time_slot_volatility = time_slot_volatility.replace(0.0, 1.0)  # Minimum volatility for constant prices
    
    return time_slot_volatility


def create_volatility_data(market_data_df: pd.DataFrame, delivery_day: Union[str, datetime], lookback_days: int = 30) -> VolatilityData:
    """
    Create a structured VolatilityData object with comprehensive volatility analysis.
    
    Args:
        market_data_df: Dataset with ida_time and ida_prices columns
        delivery_day: Target delivery date
        lookback_days: Historical lookback period in days
        
    Returns:
        VolatilityData object with structured volatility information
    """
    time_slot_volatility = calculate_standard_deviation(market_data_df, delivery_day, lookback_days)
    dataset_overall_volatility = market_data_df['ida_prices'].std() if not market_data_df.empty else 10.0
    
    return VolatilityData(
        time_slots=time_slot_volatility.index,
        standard_deviations=time_slot_volatility,
        overall_volatility=dataset_overall_volatility,
        analysis_period_days=lookback_days
    ) 