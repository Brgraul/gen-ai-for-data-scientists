"""
Unit tests for cost_calculation.py - Financial models and cost aggregation.

Tests focus on system robustness and real-world failure modes:
1. Option pricing under energy market stress conditions
2. Cost calculation economic monotonicity and bounds
3. End-to-end cost workflow consistency
"""

import pytest
import pandas as pd
import numpy as np
from energy_flexibility.core.cost_calculation import calculate_option_prices, aggregate_costs


class TestCostCalculation:
    
    def test_option_pricing_under_energy_market_stress_conditions(self):
        """Test option pricing under real energy market stress scenarios."""
        
        # Create test framework
        test_df = pd.DataFrame({
            'time': pd.date_range('2023-04-30', periods=10, freq='15min')
        })
        
        # Test Case 1: Negative Energy Prices (common in renewable-heavy markets)
        negative_da_prices = pd.Series([-50, -20, 10, 30, 50, 70, 90, 20, -10, -30])
        negative_expected_prices = pd.Series([-45, -15, 15, 35, 55, 75, 95, 25, -5, -25])
        volatility = pd.Series([20.0] * 10)  # Moderate volatility
        
        pump_strike = 25.0   # Above some negative prices
        turbine_strike = 40.0
        
        result_negative = calculate_option_prices(
            test_df.copy(), pump_strike, turbine_strike, volatility, 
            negative_da_prices, negative_expected_prices
        )
        
        # System robustness checks for negative prices
        assert all(result_negative['charge_option_price'] >= 0), "Option values must be non-negative even with negative energy prices"
        assert all(result_negative['discharge_option_price'] >= 0), "Option values must be non-negative even with negative energy prices"
        assert all(np.isfinite(result_negative['charge_option_price'])), "Option values must be finite, not NaN/inf"
        assert all(np.isfinite(result_negative['discharge_option_price'])), "Option values must be finite, not NaN/inf"
        
        # Test Case 2: Extreme Volatility (market crisis conditions)
        normal_prices = pd.Series([50.0] * 10)
        extreme_volatility = pd.Series([200.0] * 10)  # Crisis-level volatility
        
        result_extreme_vol = calculate_option_prices(
            test_df.copy(), pump_strike, turbine_strike, extreme_volatility,
            normal_prices, normal_prices
        )
        
        # High volatility should increase option values but remain bounded
        moderate_vol_result = calculate_option_prices(
            test_df.copy(), pump_strike, turbine_strike, pd.Series([20.0] * 10),
            normal_prices, normal_prices
        )
        
        # Higher volatility should increase option values
        assert all(result_extreme_vol['charge_option_price'] >= moderate_vol_result['charge_option_price']), \
            "Higher volatility should increase option values"
        
        # But option values should remain economically reasonable (not exceed energy value)
        max_reasonable_option_value = 500.0  # €/MWh - extreme but plausible upper bound
        assert all(result_extreme_vol['charge_option_price'] < max_reasonable_option_value), \
            "Option values should remain economically bounded even under extreme volatility"
        assert all(result_extreme_vol['discharge_option_price'] < max_reasonable_option_value), \
            "Option values should remain economically bounded even under extreme volatility"
        
        # Test Case 3: Boundary Price Inversions (should be impossible but test robustness)
        inverted_pump_strike = 60.0   # Higher than turbine strike (economically impossible)
        inverted_turbine_strike = 30.0
        
        result_inverted = calculate_option_prices(
            test_df.copy(), inverted_pump_strike, inverted_turbine_strike, volatility,
            normal_prices, normal_prices
        )
        
        # System should handle gracefully without crashing
        assert all(np.isfinite(result_inverted['charge_option_price'])), "System should handle inverted strikes gracefully"
        assert all(np.isfinite(result_inverted['discharge_option_price'])), "System should handle inverted strikes gracefully"
        
        # Test Case 4: Near-zero volatility (market calm periods)
        near_zero_volatility = pd.Series([0.001] * 10)  # Nearly zero but not exactly zero
        
        result_low_vol = calculate_option_prices(
            test_df.copy(), pump_strike, turbine_strike, near_zero_volatility,
            normal_prices, normal_prices
        )
        
        # Low volatility should give low but non-zero option values
        assert all(result_low_vol['charge_option_price'] >= 0), "Low volatility should give non-negative option values"
        assert all(result_low_vol['charge_option_price'] < 10.0), "Very low volatility should give small option values"
        
        # Test Case 5: Price-strike alignment (expected price = strike price)
        aligned_expected_prices = pd.Series([pump_strike] * 5 + [turbine_strike] * 5)
        
        result_aligned = calculate_option_prices(
            test_df.copy(), pump_strike, turbine_strike, volatility,
            normal_prices, aligned_expected_prices
        )
        
        # At-the-money options should have positive time value
        assert all(result_aligned['charge_option_price'] > 0), "At-the-money options should have positive time value"
        assert all(result_aligned['discharge_option_price'] > 0), "At-the-money options should have positive time value"
    
    def test_cost_calculation_economic_monotonicity_and_bounds(self):
        """Test economic properties and bounds of cost calculations."""
        
        # Create comprehensive test dataset with all required cost columns
        base_production_cost_turbine = 100.0
        base_production_cost_pump = 80.0
        base_opportunity_cost_turbine = 150.0
        base_opportunity_cost_pump = 120.0
        base_value_lost = 90.0
        
        test_data = pd.DataFrame({
            'time': pd.date_range('2023-04-30', periods=96, freq='15min'),
            'Erzeugungsauslage [production cost turbine] (euro)': [base_production_cost_turbine] * 96,
            'Erzeugungsauslage[production cost pump] (euro)': [base_production_cost_pump] * 96,
            'Entgangener Deckungsbeitrag für Turbinenbetrieb [Opportunity cost turbine] (euro)': [base_opportunity_cost_turbine] * 96,
            'Entgangener Deckungsbeitrag für Pumpbetrieb [Opportunity cost pump] (euro)': [base_opportunity_cost_pump] * 96,
            'Anteiliger Werteverbrauch [value_lost] (euro)': [base_value_lost] * 96
        })
        
        # Test 1: Basic cost aggregation logic
        result_base = aggregate_costs(test_data.copy(), None)
        
        expected_production_total = base_production_cost_turbine + base_production_cost_pump  # 180
        expected_opportunity_total = base_opportunity_cost_turbine + base_opportunity_cost_pump  # 270
        expected_max_opportunity_vs_value = max(expected_opportunity_total, base_value_lost)  # max(270, 90) = 270
        expected_total_cost = expected_production_total + expected_max_opportunity_vs_value  # 180 + 270 = 450
        
        assert all(result_base['total_production_costs_euro'] == expected_production_total), \
            "Production cost aggregation should sum turbine and pump costs"
        assert all(result_base['total_opportunity_costs_euro'] == expected_opportunity_total), \
            "Opportunity cost aggregation should sum turbine and pump opportunity costs"
        assert all(result_base['max_opportunity_vs_depreciation_euro'] == expected_max_opportunity_vs_value), \
            "Should take maximum of opportunity cost vs. asset depreciation"
        assert all(result_base['total_costs_per_timeslot_euro'] == expected_total_cost), \
            "Total cost should be production cost + max(opportunity cost, depreciation)"
        
        # Test 2: Economic monotonicity - higher input costs should yield higher total costs
        # Create scenario with doubled input costs
        test_data_doubled = test_data.copy()
        test_data_doubled['Erzeugungsauslage [production cost turbine] (euro)'] *= 2
        test_data_doubled['Erzeugungsauslage[production cost pump] (euro)'] *= 2
        test_data_doubled['Entgangener Deckungsbeitrag für Turbinenbetrieb [Opportunity cost turbine] (euro)'] *= 2
        test_data_doubled['Entgangener Deckungsbeitrag für Pumpbetrieb [Opportunity cost pump] (euro)'] *= 2
        test_data_doubled['Anteiliger Werteverbrauch [value_lost] (euro)'] *= 2

        result_doubled = aggregate_costs(test_data_doubled.copy(), None)

        # Doubled inputs should yield higher or equal total costs (monotonicity)
        assert all(result_doubled['total_costs_per_timeslot_euro'] >= result_base['total_costs_per_timeslot_euro']), \
            "Higher input costs should yield higher total costs (economic monotonicity)"

        # Test 3: Opportunity vs. depreciation max logic
        # Create data where opportunity cost < depreciation cost
        test_data_depreciation_high = test_data.copy()
        test_data_depreciation_high['Anteiliger Werteverbrauch [value_lost] (euro)'] = 500.0  # Higher than combined opportunity (270)

        result_depreciation = aggregate_costs(test_data_depreciation_high.copy(), None)

        assert all(result_depreciation['max_opportunity_vs_depreciation_euro'] == 500.0), \
            "Should select higher depreciation cost over opportunity cost"

        # Test 4: Mathematical relationships between aggregated components
        # Production costs should equal sum of individual production costs
        manual_production_total = (result_base['Erzeugungsauslage [production cost turbine] (euro)'] +
                                 result_base['Erzeugungsauslage[production cost pump] (euro)'])
        assert all(result_base['total_production_costs_euro'] == manual_production_total), \
            "Aggregated production costs should equal manual sum"

        # Total costs should equal production + selected opportunity/depreciation costs
        manual_total = (result_base['total_production_costs_euro'] +
                       result_base['max_opportunity_vs_depreciation_euro'])
        assert all(result_base['total_costs_per_timeslot_euro'] == manual_total), \
            "Total costs should equal production + max(opportunity, depreciation)"

        # Test 5: Non-negativity - all costs should be non-negative
        assert all(result_base['Erzeugungsauslage [production cost turbine] (euro)'] >= 0), "Production costs should be non-negative"
        assert all(result_base['total_opportunity_costs_euro'] >= 0), "Opportunity costs should be non-negative"
        assert all(result_base['total_costs_per_timeslot_euro'] >= 0), "Total costs should be non-negative"
    
    def test_end_to_end_cost_workflow_consistency(self):
        """Test complete cost calculation workflow for integration consistency."""
        
        # Test Case 1: Multi-timestep coherence across full day (96 intervals)
        # Create realistic daily pattern with varying market conditions
        times = pd.date_range('2023-04-30', periods=96, freq='15min')
        
        # Create realistic daily price and cost patterns
        daily_pattern_multiplier = []
        for i in range(96):
            hour = i // 4
            if 6 <= hour <= 9 or 18 <= hour <= 21:  # Peak hours
                daily_pattern_multiplier.append(1.5)
            elif 22 <= hour or hour <= 5:  # Off-peak hours
                daily_pattern_multiplier.append(0.7)
            else:  # Mid-day hours
                daily_pattern_multiplier.append(1.0)
        
        # Create test data with realistic daily patterns
        base_df = pd.DataFrame({'time': times})
        da_prices = pd.Series([50.0 * mult for mult in daily_pattern_multiplier])
        expected_prices = pd.Series([52.0 * mult for mult in daily_pattern_multiplier])
        volatilities = pd.Series([15.0 + 10.0 * mult for mult in daily_pattern_multiplier])  # Higher vol during peaks
        
        # Step 1: Calculate option prices
        pump_strike = 45.0
        turbine_strike = 60.0
        
        option_result = calculate_option_prices(
            base_df.copy(), pump_strike, turbine_strike, volatilities, da_prices, expected_prices
        )
        
        # Step 2: Create complete cost dataset
        flexibility_data = option_result.copy()
        
        # Add production cost columns (realistic pattern)
        flexibility_data['Erzeugungsauslage [production cost turbine] (euro)'] = [80.0 * mult for mult in daily_pattern_multiplier]
        flexibility_data['Erzeugungsauslage[production cost pump] (euro)'] = [60.0 * mult for mult in daily_pattern_multiplier]
        
        # Add opportunity cost columns (based on option prices)
        flexibility_data['Entgangener Deckungsbeitrag für Turbinenbetrieb [Opportunity cost turbine] (euro)'] = \
            flexibility_data['discharge_option_price'] * 15.0  # 15MW capacity
        flexibility_data['Entgangener Deckungsbeitrag für Pumpbetrieb [Opportunity cost pump] (euro)'] = \
            flexibility_data['charge_option_price'] * 15.0
        
        # Add asset depreciation
        flexibility_data['Anteiliger Werteverbrauch [value_lost] (euro)'] = [100.0] * 96  # Constant depreciation
        
        # Step 3: Finalize total costs
        final_result = aggregate_costs(flexibility_data, None)
        
        # Test workflow consistency
        # 1. Peak hours should generally have higher costs than off-peak
        peak_indices = [i for i, mult in enumerate(daily_pattern_multiplier) if mult == 1.5]
        offpeak_indices = [i for i, mult in enumerate(daily_pattern_multiplier) if mult == 0.7]
        
        peak_avg_cost = final_result.iloc[peak_indices]['total_costs_per_timeslot_euro'].mean()
        offpeak_avg_cost = final_result.iloc[offpeak_indices]['total_costs_per_timeslot_euro'].mean()
        
        assert peak_avg_cost > offpeak_avg_cost, \
            "Peak hour flexibility costs should generally exceed off-peak costs"
        
        # 2. Option prices should be correlated with volatility
        option_vol_correlation = np.corrcoef(
            final_result['charge_option_price'], 
            final_result['standard_deviation']
        )[0, 1]
        
        assert option_vol_correlation > 0.5, \
            "Option prices should be positively correlated with volatility"
        
        # 3. Total daily costs should be economically reasonable
        total_daily_cost = final_result['total_costs_per_timeslot_euro'].sum()
        
        # Reasonable range: €10,000 - €100,000 per day for 15MW plant flexibility services
        assert 10000 <= total_daily_cost <= 100000, \
            f"Total daily flexibility cost ({total_daily_cost:.0f}€) should be within reasonable range"
        
        # Test Case 2: Data anomaly resilience
        # Introduce realistic data anomalies
        anomaly_data = flexibility_data.copy()
        
        # Simulate missing/NaN values in some cost components
        anomaly_data.loc[10:15, 'Erzeugungsauslage [production cost turbine] (euro)'] = np.nan
        
        # Should handle gracefully (could fillna or raise appropriate error)
        try:
            anomaly_result = aggregate_costs(anomaly_data, None)
            # If it succeeds, check that results are still reasonable
            assert not anomaly_result['total_costs_per_timeslot_euro'].isna().all(), \
                "System should handle missing data gracefully"
        except Exception as e:
            # If it fails, should fail with meaningful error, not crash
            assert "production cost" in str(e).lower() or "nan" in str(e).lower(), \
                "Should fail with meaningful error message for data quality issues"
        
        # Test Case 3: Boundary price propagation consistency
        # Changes in boundary prices should propagate through to final costs
        high_strike_result = calculate_option_prices(
            base_df.copy(), 70.0, 80.0, volatilities, da_prices, expected_prices  # Higher strikes
        )
        
        low_strike_result = calculate_option_prices(
            base_df.copy(), 30.0, 40.0, volatilities, da_prices, expected_prices  # Lower strikes
        )
        
        # Different strike prices should yield different option values
        assert not np.array_equal(high_strike_result['charge_option_price'], low_strike_result['charge_option_price']), \
            "Different boundary prices should propagate to different option values"
        
        # Option value differences should be economically sensible
        avg_high_charge_option = high_strike_result['charge_option_price'].mean()
        avg_low_charge_option = low_strike_result['charge_option_price'].mean()
        
        # The relationship depends on whether strikes are in/out of money, but values should differ meaningfully
        option_difference = abs(avg_high_charge_option - avg_low_charge_option)
        assert option_difference > 1.0, \
            "Boundary price changes should result in meaningful option value differences" 