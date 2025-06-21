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
    
    def test_flexibility_cost_mathematical_correctness(self):
        """Test TSO production cost pricing formulas for mathematical correctness."""
        
        # TODO 2: Implement tests that check the mathematical correctness of the flexibility cost pricing formulas.
        # There's no correct answer, but think about logical checks that the data must fulfill.
        
        
        # === 
        # STEP 1: Arrange (Test Setup) 
        # In the test step, we should prepare the data and parameters needed to test the pricing formulas.
        # ===

        # - Create test data with a known price distribution (e.g., range 20-90)
        # These are expected as the values of a "adjusted_da_prices" column in a DataFrame

        # - Set clear boundary prices to create distinct regimes (pump ≤ X, turbine ≥ Y)
        # This are the minimum energy price that makes it worth it to turn the turbine on, 
        # and the maximum energy price we're willing to pay to run the pump (charge energy)
        
        # - Create variables for the efficiency of the plant, and the network & congestion (cnNNe) charges



        # === 
        # STEP 2: Act 
        # In the test step, we run the code that shoul be tested.
        # ===

        # Remember, this is a test for the "calculate_flexibility_cost_prices" function



        # === 
        # STEP 3: Assert
        # In the test step, we check that the output of the function matches our expectations.
        # We will have to turn each of our business and technical expectations into one (or more) assertions.
        # ===

        # Some inspiration for topics you could check: 
        # - Are all returned prices positive? (economic prices can't be negative)
        # - Does the function return exactly 4 values as expected?
        # - Are there no NaN or infinite values in the results?
        # - What happens when no prices fall in pump or turbine regimes?
        


        pass

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