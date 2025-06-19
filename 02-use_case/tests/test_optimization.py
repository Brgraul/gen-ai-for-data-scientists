"""
Unit tests for optimization.py - Economic optimization algorithms.

Tests focus on algorithmic correctness rather than data validation:
1. Greedy optimization algorithm logic
2. Boundary price calculation edge cases  
3. Production cost pricing mathematical correctness
"""

import pytest
import pandas as pd
import numpy as np
from energy_flexibility.core.optimization import (
    find_optimal_boundary_prices_turbine_first,
    create_boundary_prices,
    calculate_flexibility_cost_prices
)
from energy_flexibility.core.models import Power, Price


class TestOptimization:
    
    def test_greedy_optimization_algorithm_logic(self):
        """Test core economic optimization algorithm - greedy matching and energy balance."""
        
        # Create controlled price scenario for testing algorithm logic
        # High prices: 100, 90, 80 (should be selected for turbine/discharge)
        # Low prices: 10, 20, 30 (should be selected for pump/charge)
        # Medium prices: 50, 60 (should determine profitability boundary)
        
        test_prices = pd.DataFrame({
            'adjusted_da_prices': [100, 90, 80, 60, 50, 40, 30, 20, 10],
            'da_time': pd.date_range('2023-04-30', periods=9, freq='15min')
        })
        
        # Test parameters
        turbine_power = Power(4.0)    # 4MW discharge capacity
        pump_power = Power(4.0)       # 4MW charge capacity  
        efficiency = 0.8              # 80% efficiency
        network_charges = Price(5.0)  # €5/MWh network charges
        max_discharge_hours = 1.5     # Max 1.5h = 6 MWh total discharge capacity
        
        turbine_boundary, pump_boundary, turbine_energy, pump_energy = find_optimal_boundary_prices_turbine_first(
            test_prices, turbine_power, pump_power, efficiency, network_charges, max_discharge_hours
        )
        
        # Test 1: Algorithm should find profitable operations
        # Highest turbine price (100) * efficiency (0.8) = 80
        # Lowest pump price (10) + network charges (5) = 15
        # Since 80 > 15, this should be profitable
        assert turbine_boundary is not None
        assert pump_boundary is not None
        assert turbine_energy > 0
        assert pump_energy > 0
        
        # Test 2: Energy balance constraint
        # pump_energy * efficiency ≈ turbine_energy (within rounding errors)
        expected_turbine_energy = pump_energy * efficiency
        assert abs(turbine_energy - expected_turbine_energy) < 0.01
        
        # Test 3: Capacity constraint enforcement
        # Total turbine energy should not exceed max_discharge_hours * turbine_power
        max_discharge_capacity = max_discharge_hours * turbine_power  # 1.5h * 4MW = 6 MWh
        assert turbine_energy <= max_discharge_capacity + 0.1  # Small tolerance for floating point
        
        # Test 4: Greedy selection logic
        # Algorithm should select highest value discharge opportunities first
        # With our prices [100, 90, 80, 60, 50, 40, 30, 20, 10] and 6 MWh capacity,
        # it should use the highest priced slots that are profitable
        assert turbine_boundary >= 60  # Should reach at least into middle-high range
        
        # Test 5: Economic feasibility boundary
        # The algorithm should stop when adjusted_turbine_price <= adjusted_pump_price
        # Check profitability constraint  
        # turbine_boundary * efficiency should be > pump_boundary + network_charges (approximately)
        profitability_gap = turbine_boundary * efficiency - (pump_boundary + network_charges)
        assert profitability_gap > -1.0  # Should be profitable or close to breakeven
    
    def test_boundary_price_calculation_edge_cases(self):
        """Test boundary price calculation under edge conditions."""
        
        # Test Case 1: No profitable operations (all prices similar)
        uniform_prices = pd.DataFrame({
            'adjusted_da_prices': [50.0] * 10,  # All prices identical
            'da_time': pd.date_range('2023-04-30', periods=10, freq='15min')
        })
        
        result_uniform = find_optimal_boundary_prices_turbine_first(
            uniform_prices, Power(4.0), Power(4.0), 0.9, Price(2.0), 2.0
        )
        
        turbine_b, pump_b, total_t, total_p = result_uniform
        
        # Should trigger special case calculation
        # When no profitable iterations: turbine < pump boundary (due to efficiency losses + network charges)
        assert turbine_b < pump_b
        assert total_t == 0  # No energy scheduled
        assert total_p == 0
        
        # Test Case 2: Capacity constraint limiting
        high_prices = pd.DataFrame({
            'adjusted_da_prices': [100.0] * 20,  # Many high-price slots
            'da_time': pd.date_range('2023-04-30', periods=20, freq='15min')
        })
        
        low_prices = pd.DataFrame({
            'adjusted_da_prices': [5.0] * 20,   # Many low-price slots  
            'da_time': pd.date_range('2023-04-30', periods=20, freq='15min')
        })
        
        # Combine high and low prices
        mixed_prices = pd.concat([high_prices, low_prices]).reset_index(drop=True)
        
        result_limited = find_optimal_boundary_prices_turbine_first(
            mixed_prices, Power(4.0), Power(4.0), 0.9, Price(1.0), 1.0  # Only 1 hour capacity
        )
        
        turbine_b2, pump_b2, total_t2, total_p2 = result_limited
        
        # Should be limited by max_discharge_hours constraint
        max_capacity = 1.0 * 4.0  # 1h * 4MW = 4 MWh
        assert total_t2 <= max_capacity + 0.01
        assert total_t2 > 0  # Should find some profitable operations
        
        # Test Case 3: Efficiency impact on profitability
        # Very low efficiency should reduce profitable opportunities
        result_low_eff = find_optimal_boundary_prices_turbine_first(
            mixed_prices, Power(4.0), Power(4.0), 0.5, Price(1.0), 2.0  # 50% efficiency
        )
        
        result_high_eff = find_optimal_boundary_prices_turbine_first(
            mixed_prices, Power(4.0), Power(4.0), 0.95, Price(1.0), 2.0  # 95% efficiency
        )
        
        # Higher efficiency should lead to more energy scheduled (more profitable operations)
        assert result_high_eff[2] >= result_low_eff[2]  # total_turbine_energy
        
        # Test Case 4: Network charges impact
        result_high_charges = find_optimal_boundary_prices_turbine_first(
            mixed_prices, Power(4.0), Power(4.0), 0.9, Price(20.0), 2.0  # High network charges
        )
        
        result_low_charges = find_optimal_boundary_prices_turbine_first(
            mixed_prices, Power(4.0), Power(4.0), 0.9, Price(0.1), 2.0   # Low network charges
        )
        
        # Lower network charges should enable more profitable operations
        assert result_low_charges[2] >= result_high_charges[2]  # total_turbine_energy
    
    def test_production_cost_pricing_mathematical_correctness(self):
        """Test TSO production cost pricing formulas for mathematical correctness."""
        
        # Create test data with known price distributions
        test_prices = pd.DataFrame({
            'adjusted_da_prices': [20, 30, 40, 50, 60, 70, 80, 90]  # Range 20-90
        })
        
        # Set boundary prices to create clear regimes
        pump_boundary = 40.0    # Prices ≤ 40 are good for pumping
        turbine_boundary = 70.0 # Prices ≥ 70 are good for turbining
        efficiency = 0.9
        network_charges = Price(2.0)
        
        result = calculate_flexibility_cost_prices(
            test_prices, network_charges, pump_boundary, turbine_boundary, efficiency
        )
        
        pturb_pos, pturb_neg, ppump_pos, ppump_neg = result
        
        # Test 1: All results should be positive prices
        assert pturb_pos > 0
        assert pturb_neg > 0  
        assert ppump_pos > 0
        assert ppump_neg > 0
        
        # Test 2: Calculate expected values manually to verify formulas
        pump_slots = test_prices[test_prices['adjusted_da_prices'] <= pump_boundary]
        turbine_slots = test_prices[test_prices['adjusted_da_prices'] >= turbine_boundary]
        
        mean_pump_price = pump_slots['adjusted_da_prices'].mean()  # Should be (20+30+40)/3 = 30
        mean_turbine_price = turbine_slots['adjusted_da_prices'].mean()  # Should be (70+80+90)/3 = 80
        middle_value = (pump_boundary + turbine_boundary) / 2  # (40+70)/2 = 55
        
        # Test mathematical formulas from the algorithm
        # Increasing discharge (TSO pays plant): max((middle+network_charges)/eff, mean_turbine)
        expected_p1a = (middle_value + network_charges) / efficiency  # (55+2)/0.9 = 63.33
        expected_p1b = mean_turbine_price  # 80
        expected_increase_discharge = max(expected_p1a, expected_p1b)  # max(63.33, 80) = 80
        
        assert abs(pturb_pos - expected_increase_discharge) < 0.1
        
        # Decreasing discharge (plant pays TSO): min((mean_pump+network_charges)/eff, middle)
        expected_p2a = (mean_pump_price + network_charges) / efficiency  # (30+2)/0.9 = 35.56
        expected_p2b = middle_value  # 55
        expected_decrease_discharge = min(expected_p2a, expected_p2b)  # min(35.56, 55) = 35.56
        
        assert abs(pturb_neg - expected_decrease_discharge) < 0.1
        
        # Decreasing charge (TSO pays plant): max(mean_turbine*eff-network_charges, middle)
        expected_p3a = mean_turbine_price * efficiency - network_charges  # 80*0.9-2 = 70
        expected_p3b = middle_value  # 55
        expected_decrease_charge = max(expected_p3a, expected_p3b)  # max(70, 55) = 70
        
        assert abs(ppump_pos - expected_decrease_charge) < 0.1
        
        # Increasing charge (plant pays TSO): min(middle*eff-network_charges, mean_pump)
        expected_p4a = middle_value * efficiency - network_charges  # 55*0.9-2 = 47.5
        expected_p4b = mean_pump_price  # 30
        expected_increase_charge = min(expected_p4a, expected_p4b)  # min(47.5, 30) = 30
        
        assert abs(ppump_neg - expected_increase_charge) < 0.1
        
        # Test 3: Economic logic consistency
        # When TSO pays plant operator (pos prices), should be >= middle value or market rates
        # When plant pays TSO (neg prices), should be <= middle value or market rates
        
        # For increasing services (TSO pays), prices should generally be higher
        assert pturb_pos >= pturb_neg  # TSO paying for more discharge > plant paying for less discharge
        assert ppump_pos >= ppump_neg  # TSO paying for less charge > plant paying for more charge
        
        # Test 4: Boundary price impacts
        # If we move boundary prices, production costs should change predictably
        result_tight = calculate_flexibility_cost_prices(
            test_prices, network_charges, 35.0, 75.0, efficiency  # Tighter boundaries
        )
        
        result_wide = calculate_flexibility_cost_prices(
            test_prices, network_charges, 45.0, 65.0, efficiency  # Wider boundaries  
        )
        
        # Different boundary prices should yield different production costs
        # (exact relationships depend on data, but results should be different)
        assert result_tight != result_wide
        
        # Test 5: Parameter sensitivity
        # Higher efficiency should generally lead to lower costs (more efficient operations)
        result_low_eff = calculate_flexibility_cost_prices(
            test_prices, network_charges, pump_boundary, turbine_boundary, 0.7
        )
        
        result_high_eff = calculate_flexibility_cost_prices(
            test_prices, network_charges, pump_boundary, turbine_boundary, 0.95
        )
        
        # At least some prices should be different with different efficiency
        assert (result_low_eff != result_high_eff) 

    def test_production_cost_calculation(self):
        """Test production cost calculation for various flexibility scenarios."""
        
        # Test setup
        test_prices = pd.DataFrame({
            'adjusted_da_prices': [20, 30, 40, 50, 60, 70, 80, 90]  # Range 20-90
        })
        
        turbine_boundary = Price(75.0)
        pump_boundary = Price(35.0) 
        efficiency = 0.9
        network_charges = Price(2.0)
        
        # Calculate production costs
        increase_discharge, decrease_discharge, decrease_charge, increase_charge = calculate_flexibility_cost_prices(
            test_prices, network_charges, pump_boundary, turbine_boundary, efficiency
        )
        
        # All costs should be positive
        assert increase_discharge > 0
        assert decrease_discharge > 0
        assert decrease_charge > 0
        assert increase_charge > 0

    def test_production_cost_edge_cases(self):
        """Test production cost calculation with edge case parameters."""
        
        test_prices = pd.DataFrame({
            'adjusted_da_prices': [20, 30, 40, 50, 60, 70, 80, 90]  # Range 20-90
        })
        
        pump_boundary = 40.0
        turbine_boundary = 70.0
        efficiency = 0.9
        network_charges = Price(2.0)
        
        # Test with very tight price boundaries
        result1 = calculate_flexibility_cost_prices(
            test_prices, network_charges, 35.0, 75.0, efficiency  # Tighter boundaries
        )
        
        # Test with very wide price boundaries  
        result2 = calculate_flexibility_cost_prices(
            test_prices, network_charges, 45.0, 65.0, efficiency  # Wider boundaries
        )
        
        # Test with different efficiency
        result3 = calculate_flexibility_cost_prices(
            test_prices, network_charges, pump_boundary, turbine_boundary, 0.7
        )
        
        result4 = calculate_flexibility_cost_prices(
            test_prices, network_charges, pump_boundary, turbine_boundary, 0.95
        )
        
        # All results should have 4 positive values
        for result in [result1, result2, result3, result4]:
            assert len(result) == 4
            assert all(price > 0 for price in result) 