"""
Unit tests for market_analysis.py - Price forecasting and market analysis.

Tests focus on the most critical failure points:
1. Date filtering and validation
2. Price adjustment logic  
3. Volatility calculation edge cases
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from energy_flexibility.core.market_analysis import (
    calculate_average_diff, 
    adjust_da_prices_for_date,
    create_price_data,
    calculate_standard_deviation
)


class TestMarketAnalysis:
    
    def test_date_filtering_and_validation(self):
        """Test date range validation and data availability - most common failure."""
        
        # Create test data with known date range
        base_date = datetime(2023, 4, 1)
        test_data = []
        
        # Generate 100 days of test data
        for day_offset in range(100):
            current_date = base_date + timedelta(days=day_offset)
            for hour in range(24):
                da_time = current_date + timedelta(hours=hour)
                for quarter in range(4):
                    ida_time = da_time + timedelta(minutes=quarter * 15)
                    test_data.append({
                        'da_time': da_time,
                        'da_prices': 50.0 + np.random.uniform(-10, 10),
                        'ida_time': ida_time,
                        'ida_prices': 52.0 + np.random.uniform(-10, 10)
                    })
        
        df = pd.DataFrame(test_data)
        delivery_date = datetime(2023, 4, 30)  # Within data range
        
        # Test successful case with sufficient data
        result = calculate_average_diff(df, delivery_date, lookback_days=20)
        assert isinstance(result, pd.Series)
        assert len(result) > 0
        assert result.index.dtype == 'object'  # Time strings like '14:15'
        
        # Test with string delivery date
        result_str = calculate_average_diff(df, "2023-04-30", lookback_days=20)
        assert isinstance(result_str, pd.Series)
        assert len(result_str) > 0
        
        # Test with delivery date outside data range (no historical data)
        early_date = datetime(2023, 1, 1)  # Before our test data
        result_empty = calculate_average_diff(df, early_date, lookback_days=90)
        # Should return empty series or handle gracefully
        assert isinstance(result_empty, pd.Series)
        
        # Test adjust_da_prices_for_date with missing delivery date
        future_date = datetime(2023, 12, 31)  # After our test data
        with pytest.raises(ValueError, match="No DA price data found"):
            # Create dummy average_diff for this test
            dummy_diff = pd.Series([1.0, 2.0], index=['14:00', '14:15'])
            adjust_da_prices_for_date(df, future_date, dummy_diff)
        
        # Test calculate_standard_deviation with no data
        with pytest.raises(ValueError, match="No IDA price data found"):
            calculate_standard_deviation(df, early_date, lookback_days=10)  # Before data range
    
    def test_price_adjustment_logic(self):
        """Test price adjustment calculations - critical for accurate forecasting."""
        
        # Create controlled test data
        delivery_date = datetime(2023, 4, 30)
        
        # Create DA prices for the delivery date (hourly)
        da_data = []
        for hour in range(24):
            da_data.append({
                'da_time': delivery_date + timedelta(hours=hour),
                'da_prices': 50.0 + hour  # Predictable pattern: 50, 51, 52, ...
            })
        
        df = pd.DataFrame(da_data)
        
        # Create historical average differences (spreads)
        spreads = {}
        for hour in range(24):
            for minute in [0, 15, 30, 45]:
                time_key = f"{hour:02d}:{minute:02d}"
                spreads[time_key] = hour * 0.5  # Predictable spread pattern
        
        average_diff = pd.Series(spreads)
        
        # Test price adjustment
        result = adjust_da_prices_for_date(df, delivery_date, average_diff)
        
        # Verify structure
        assert 'da_time' in result.columns
        assert 'da_prices' in result.columns
        assert 'adjusted_da_prices' in result.columns
        
        # Should have 96 rows (24 hours * 4 quarters)
        assert len(result) == 96
        
        # Verify adjustment logic: adjusted = original + spread
        # Check first hour (hour 0, should have spread of 0)
        first_hour_data = result[result['da_time'].dt.hour == 0]
        assert len(first_hour_data) == 4  # 4 quarters
        # All quarters should have same DA price (50.0) but different adjusted prices
        assert all(first_hour_data['da_prices'] == 50.0)
        
        # Check that spread was applied correctly
        for _, row in first_hour_data.iterrows():
            time_key = row['da_time'].strftime('%H:%M')
            expected_adjustment = spreads.get(time_key, 0)
            expected_adjusted = row['da_prices'] + expected_adjustment
            assert abs(row['adjusted_da_prices'] - expected_adjusted) < 0.001
        
        # Test with missing spreads (should default to 0)
        partial_spreads = pd.Series({'14:00': 5.0, '14:15': 3.0})  # Only 2 time slots
        result_partial = adjust_da_prices_for_date(df, delivery_date, partial_spreads)
        
        # Times with spreads should be adjusted
        adjusted_14_00 = result_partial[result_partial['da_time'].dt.strftime('%H:%M') == '14:00']
        assert len(adjusted_14_00) == 1
        assert adjusted_14_00.iloc[0]['adjusted_da_prices'] == adjusted_14_00.iloc[0]['da_prices'] + 5.0
        
        # Times without spreads should have no adjustment (spread = 0)
        unadjusted_15_00 = result_partial[result_partial['da_time'].dt.strftime('%H:%M') == '15:00']
        assert len(unadjusted_15_00) == 1
        assert unadjusted_15_00.iloc[0]['adjusted_da_prices'] == unadjusted_15_00.iloc[0]['da_prices']
        
        # Test with string delivery date
        result_str = adjust_da_prices_for_date(df, "2023-04-30", average_diff)
        assert len(result_str) == 96
    
    def test_volatility_calculation_edge_cases(self):
        """Test volatility calculations - critical for Black-Scholes option pricing."""
        
        # Create test data with controlled volatility patterns
        base_date = datetime(2023, 4, 1)
        test_data = []
        
        # Generate data with different volatility patterns by time of day
        for day_offset in range(30):  # 30 days of history
            current_date = base_date + timedelta(days=day_offset)
            for hour in range(24):
                for quarter in range(4):
                    ida_time = current_date + timedelta(hours=hour, minutes=quarter * 15)
                    
                    # Create predictable volatility: higher during peak hours
                    base_price = 50.0
                    if 8 <= hour <= 10 or 18 <= hour <= 20:  # Peak hours
                        volatility = 10.0  # High volatility
                    else:
                        volatility = 2.0   # Low volatility
                    
                    price = base_price + np.random.normal(0, volatility)
                    test_data.append({
                        'ida_time': ida_time,
                        'ida_prices': price
                    })
        
        df = pd.DataFrame(test_data)
        delivery_date = datetime(2023, 4, 30)
        
        # Test normal volatility calculation
        result = calculate_standard_deviation(df, delivery_date, lookback_days=20)
        
        assert isinstance(result, pd.Series)
        assert len(result) > 0
        assert all(result >= 0)  # Standard deviation cannot be negative
        assert not result.isna().any()  # Should not have NaN values
        
        # Verify peak hours have higher volatility than off-peak
        peak_volatilities = []
        offpeak_volatilities = []
        
        for time_str, vol in result.items():
            hour = int(time_str.split(':')[0])
            if 8 <= hour <= 10 or 18 <= hour <= 20:
                peak_volatilities.append(vol)
            else:
                offpeak_volatilities.append(vol)
        
        # Peak hours should generally have higher volatility
        if peak_volatilities and offpeak_volatilities:
            assert np.mean(peak_volatilities) > np.mean(offpeak_volatilities)
        
        # Test with identical prices (zero volatility case)
        constant_data = []
        for day_offset in range(10):
            current_date = base_date + timedelta(days=day_offset)
            for hour in range(24):
                for quarter in range(4):
                    ida_time = current_date + timedelta(hours=hour, minutes=quarter * 15)
                    constant_data.append({
                        'ida_time': ida_time,
                        'ida_prices': 50.0  # Constant price
                    })
        
        df_constant = pd.DataFrame(constant_data)
        # Use a delivery date within the data range for constant volatility test
        constant_delivery_date = datetime(2023, 4, 10)  # Within the data range (2023-04-01 to 2023-04-10)
        result_constant = calculate_standard_deviation(df_constant, constant_delivery_date, lookback_days=5)
        
        # Should handle zero volatility gracefully
        assert isinstance(result_constant, pd.Series)
        assert all(result_constant >= 0)
        assert not result_constant.isna().any()
        
        # Test with single data point per time slot
        sparse_data = []
        single_date = base_date
        for hour in range(24):
            for quarter in range(4):
                ida_time = single_date + timedelta(hours=hour, minutes=quarter * 15)
                sparse_data.append({
                    'ida_time': ida_time,
                    'ida_prices': 50.0 + hour
                })
        
        df_sparse = pd.DataFrame(sparse_data)
        # Use a delivery date within the data range for sparse data test
        sparse_delivery_date = datetime(2023, 4, 2)  # Within the single_date data range
        result_sparse = calculate_standard_deviation(df_sparse, sparse_delivery_date, lookback_days=1)
        
        # Should fill NaN values with overall standard deviation
        assert isinstance(result_sparse, pd.Series)
        assert not result_sparse.isna().any()
        assert all(result_sparse >= 0)
        
        # Test with string delivery date
        result_str = calculate_standard_deviation(df, "2023-04-30", lookback_days=20)
        assert isinstance(result_str, pd.Series)
        assert len(result_str) > 0 