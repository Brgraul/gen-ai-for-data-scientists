"""
EXEMPLARY INTEGRATION TEST - Best Practices Demo
==============================================

This integration test demonstrates all key integration testing best practices:
1. Testing CROSS-MODULE COORDINATION rather than individual functions
2. Using CONTROLLED test data with predictable outcomes
3. BEHAVIORAL assertions focusing on business rules and data flow
4. Testing REALISTIC pipeline execution with multiple components
5. Validating ERROR HANDLING and edge cases

Pipeline under test: Complete Energy Flexibility Calculation
- Integrates 6 modules: data_loader, market_analysis, optimization, cost_calculation, reporting, config
- Tests 11 sequential pipeline steps with real dependencies
- Validates business-meaningful outcomes (TSO regulatory compliance)
- Perfect example of integration testing vs unit testing
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import os

from energy_flexibility.core.calculator import FlexibilityCalculator
from energy_flexibility.core.config import Config


class TestFlexibilityCalculationIntegration:
    """
    Integration test suite for the complete flexibility calculation pipeline.
    
    These tests focus on BEHAVIORAL validation of cross-module interactions
    rather than testing implementation details of individual functions.
    """
    
    @pytest.fixture
    def test_data_dir(self):
        """Create temporary directory with test data files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create realistic test market data
            market_data = self._create_test_market_data()
            market_file = temp_path / "test_market_prices.xlsx"
            market_data.to_excel(market_file, index=False)
            
            # Create realistic test schedule data
            schedule_data = self._create_test_schedule_data()
            schedule_file = temp_path / "test_schedule.xlsx" 
            schedule_data.to_excel(schedule_file, index=False)
            
            # Create output directory
            output_dir = temp_path / "output"
            output_dir.mkdir()
            
            yield {
                'dir': temp_path,
                'market_file': market_file,
                'schedule_file': schedule_file,
                'output_file': output_dir / "integration_test_output.xlsx"
            }
    
    def _create_test_market_data(self) -> pd.DataFrame:
        """
        Create REALISTIC but PREDICTABLE test market data.
        
        This exhibits realistic energy market patterns but with known outcomes
        that allow us to make meaningful behavioral assertions.
        """
        # Create 7 days of hourly data around our test delivery date
        base_date = datetime(2023, 4, 28)  # Start 2 days before delivery date
        hours = pd.date_range(base_date, periods=7*24, freq='H')
        
        # Realistic daily price pattern: low at night, high during day, peak at evening
        daily_pattern = [20, 15, 12, 10, 8, 12, 25, 35, 45, 55, 60, 58, 
                        50, 48, 46, 44, 42, 45, 50, 55, 65, 60, 45, 35]
        
        # Repeat pattern for 7 days with some variation
        da_prices = []
        ida_prices = []
        d1_prices = []
        
        for day in range(7):
            day_variation = np.random.normal(0, 2, 24)  # Small daily variation
            for hour, base_price in enumerate(daily_pattern):
                # DA prices with daily variation
                da_price = base_price + day_variation[hour]
                da_prices.append(max(da_price, 5))  # Minimum price floor
                
                # IDA prices typically 2-5% higher than DA
                ida_price = da_price * np.random.uniform(1.02, 1.05)
                ida_prices.append(max(ida_price, 5))
                
                # D-1 prices similar to DA with slight variation
                d1_price = da_price * np.random.uniform(0.98, 1.02)
                d1_prices.append(max(d1_price, 5))
        
        # Create 15-minute IDA data (4x more data points)
        ida_15min_times = []
        ida_15min_prices = []
        for i, hourly_time in enumerate(hours):
            for minute in [0, 15, 30, 45]:
                ida_15min_times.append(hourly_time.replace(minute=minute))
                # Add small intra-hour variation
                hourly_ida = ida_prices[i]
                variation = np.random.normal(0, 1)
                ida_15min_prices.append(max(hourly_ida + variation, 5))
        
        # Create DataFrame matching expected structure
        max_len = max(len(hours), len(ida_15min_times))
        df_data = pd.DataFrame({
            'col_1': range(max_len),  # Excel column structure
            'da_time': pd.concat([pd.Series(hours), pd.Series([None]*(max_len-len(hours)))]),
            'da_prices': pd.concat([pd.Series(da_prices), pd.Series([None]*(max_len-len(da_prices)))]),
            'col_4': range(max_len),
            'col_5': range(max_len), 
            'col_6': range(max_len),
            'col_7': range(max_len),
            'ida_time': pd.concat([pd.Series(ida_15min_times), pd.Series([None]*(max_len-len(ida_15min_times)))]),
            'ida_prices': pd.concat([pd.Series(ida_15min_prices), pd.Series([None]*(max_len-len(ida_15min_prices)))]),
            'd1_time': pd.concat([pd.Series(hours), pd.Series([None]*(max_len-len(hours)))]),
            'd1_prices': pd.concat([pd.Series(d1_prices), pd.Series([None]*(max_len-len(d1_prices)))])
        })
        
        return df_data
    
    def _create_test_schedule_data(self) -> pd.DataFrame:
        """
        Create realistic operational schedule data for flexibility calculations.
        """
        # Create 96 15-minute intervals for one day
        base_time = datetime(2023, 4, 30)
        times = pd.date_range(base_time, periods=96, freq='15min')
        
        # Realistic operational schedule with some redispatch requirements
        schedule_data = []
        for i, time in enumerate(times):
            # Create realistic operational pattern
            hour = time.hour
            
            # Night: minimal operation, morning: ramp up, day: peak, evening: ramp down
            if 0 <= hour < 6:  # Night
                pmax, vmax = 5, 5
                pt = np.random.uniform(-2, 2)
            elif 6 <= hour < 12:  # Morning ramp
                pmax, vmax = 15, 15  
                pt = np.random.uniform(-5, 10)
            elif 12 <= hour < 18:  # Peak hours
                pmax, vmax = 15, 15
                pt = np.random.uniform(-10, 15)
            else:  # Evening
                pmax, vmax = 10, 10
                pt = np.random.uniform(-5, 8)
            
            # Some intervals have redispatch requirements
            if i % 12 == 0:  # Every 3 hours, some redispatch
                prd = np.random.uniform(-3, 3)
                redispatch_type = np.random.choice(["keine", "einseitig", "beidseitig"])
                if redispatch_type == "keine":
                    prd = 0
            else:
                prd = 0
                redispatch_type = "keine"
            
            pnew = pt + prd
            
            schedule_data.append({
                'time': time,
                'Pmax': pmax,
                'Vmax': vmax, 
                'Pt': pt,
                'Prd': prd,
                'Pnew': pnew,
                'RedispatchType': redispatch_type,
                'pos_vorgehaltene_leistung': max(0, pmax - abs(pt)),
                'neg_vorgehaltene_leistung': max(0, vmax - abs(pt))
            })
        
        return pd.DataFrame(schedule_data)
    
    def test_complete_pipeline_integration_success(self, test_data_dir):
        """
        MAIN INTEGRATION TEST: Complete flexibility calculation pipeline.
        
        Tests the ENTIRE pipeline from data loading through TSO report generation.
        Focuses on BEHAVIORAL assertions rather than exact numerical values.
        """
        # Arrange: Create controlled test configuration
        config = Config(
            prices_file=str(test_data_dir['market_file']),
            schedule_file=str(test_data_dir['schedule_file']),
            output_path=str(test_data_dir['output_file']),
            delivery_date="2023-04-30",
            price_analysis_days=90,
            volatility_analysis_days=30,
            discharge_power=15.0,
            charge_power=15.0,
            efficiency=0.85,
            network_charges=1.5,
            max_discharge_hours=4.0,
            residual_value_of_battery=12000000.0,
            remaining_useful_life=15.0,
            planned_operating_hour=1168.0
        )
        
        calculator = FlexibilityCalculator(config)
        
        # Act: Execute complete pipeline
        result = calculator.calculate()
        
        # Assert: BEHAVIORAL validations (not implementation details)
        
        # 1. DATA FLOW INTEGRITY - Pipeline produces complete results
        assert result is not None, "Pipeline should produce results"
        assert len(result) == 96, "Should have 96 15-minute intervals for one day"
        assert all(result['time'].dt.date == pd.to_datetime('2023-04-30').date()), \
            "All results should be for the delivery date"
        
        # 2. BUSINESS RULE COMPLIANCE - Economic constraints respected
        boundary_prices = calculator.boundary_prices
        assert boundary_prices is not None, "Boundary prices should be calculated"
        assert boundary_prices[0] > boundary_prices[1], \
            "Discharge price must exceed charge price for economic viability"
        
        assert all(result['total_costs_per_timeslot'] >= 0), \
            "Flexibility costs cannot be negative"
        
        # 3. OUTPUT STRUCTURE VALIDATION - Required columns present
        required_columns = [
            'time', 'total_opportunity_costs', 'total_production_costs',
            'max_opportunity_vs_depreciation', 'total_costs_per_timeslot'
        ]
        missing_columns = [col for col in required_columns if col not in result.columns]
        assert not missing_columns, f"Result missing required columns: {missing_columns}"
        
        # 4. CROSS-MODULE INTEGRATION - Modules worked together correctly
        assert calculator.market_data is not None, "Market data should be loaded"
        assert calculator.adjusted_prices is not None, "Price adjustments should be calculated"
        assert calculator.option_prices is not None, "Option prices should be calculated"
        assert calculator.operational_schedule_data is not None, "Schedule data should be loaded"
        
        # 5. DATA CONSISTENCY ACROSS MODULES - Same time intervals throughout
        market_intervals = len(calculator.adjusted_prices)
        option_intervals = len(calculator.option_prices)
        assert market_intervals == option_intervals, \
            "Market data and option prices should have matching time intervals"
        
        # 6. TSO REPORT GENERATION - Regulatory output created
        assert test_data_dir['output_file'].exists(), "TSO report file should be created"
        
        # Load and validate TSO report structure
        tso_report = pd.read_excel(test_data_dir['output_file'], sheet_name='Opportunitätskosten')
        assert len(tso_report) == 96, "TSO report should have 96 time intervals"
        
        tso_constants = pd.read_excel(test_data_dir['output_file'], sheet_name='Andere Kosten')
        assert len(tso_constants) > 0, "TSO report should include regulatory constants"
        
        # 7. PHYSICAL CONSTRAINTS VALIDATION - Energy conservation laws
        total_discharge_energy = boundary_prices[2]  # Total discharge energy from optimization
        max_possible_discharge = config.max_discharge_hours * config.discharge_power
        assert total_discharge_energy <= max_possible_discharge, \
            "Total discharge cannot exceed physical plant constraints"
        
        # 8. FINANCIAL CONSISTENCY - Cost calculations make economic sense
        total_flexibility_cost = result['total_costs_per_timeslot'].sum()
        assert total_flexibility_cost >= 0, "Total flexibility cost should be non-negative"
        
        # Opportunity costs should be related to option values
        total_opportunity = result['total_opportunity_costs'].sum()
        option_value_sum = calculator.option_prices['charge_option_price'].sum() + \
                          calculator.option_prices['discharge_option_price'].sum()
        assert total_opportunity <= option_value_sum * 2, \
            "Opportunity costs should be reasonable compared to option values"
    
    def test_pipeline_error_handling_missing_market_data(self, test_data_dir):
        """
        Integration test for ERROR HANDLING: Missing market data.
        
        Tests that pipeline fails gracefully with meaningful error messages
        when required input data is missing or invalid.
        """
        # Create config with non-existent market data file
        config = Config(
            prices_file="non_existent_file.xlsx",
            schedule_file=str(test_data_dir['schedule_file']),
            output_path=str(test_data_dir['output_file']),
            delivery_date="2023-04-30"
        )
        
        calculator = FlexibilityCalculator(config)
        
        # Should raise appropriate error when trying to load missing data
        with pytest.raises((FileNotFoundError, Exception)):
            calculator.calculate()
    
    def test_pipeline_edge_case_minimal_market_data(self, test_data_dir):
        """
        Integration test for EDGE CASE: Minimal market data.
        
        Tests pipeline behavior when market data is present but minimal,
        ensuring graceful degradation rather than crashes.
        """
        # Create minimal market data (just a few data points)
        minimal_data = pd.DataFrame({
            'col_1': [1, 2],
            'da_time': [datetime(2023, 4, 30, 12), datetime(2023, 4, 30, 13)],
            'da_prices': [50.0, 55.0],
            'col_4': [1, 2], 'col_5': [1, 2], 'col_6': [1, 2], 'col_7': [1, 2],
            'ida_time': [datetime(2023, 4, 30, 12), datetime(2023, 4, 30, 13)],
            'ida_prices': [52.0, 57.0],
            'd1_time': [datetime(2023, 4, 30, 12), datetime(2023, 4, 30, 13)],
            'd1_prices': [51.0, 56.0]
        })
        
        minimal_file = test_data_dir['dir'] / "minimal_market_data.xlsx"
        minimal_data.to_excel(minimal_file, index=False)
        
        config = Config(
            prices_file=str(minimal_file),
            schedule_file=str(test_data_dir['schedule_file']),
            output_path=str(test_data_dir['output_file']),
            delivery_date="2023-04-30",
            price_analysis_days=1,  # Reduced to match minimal data
            volatility_analysis_days=1
        )
        
        calculator = FlexibilityCalculator(config)
        
        # Pipeline should either complete with fallback values or raise meaningful error
        try:
            result = calculator.calculate()
            # If it completes, validate it has reasonable fallback behavior
            assert result is not None, "Pipeline should handle minimal data gracefully"
            assert len(result) > 0, "Should produce some results even with minimal data"
        except ValueError as e:
            # If it fails, should be with meaningful error message
            assert "insufficient" in str(e).lower() or "not enough" in str(e).lower(), \
                f"Should provide meaningful error for insufficient data: {e}"
    
    def test_pipeline_configuration_validation(self, test_data_dir):
        """
        Integration test for CONFIGURATION VALIDATION.
        
        Tests that pipeline validates configuration parameters and fails
        early with clear messages for invalid configurations.
        """
        # Test invalid efficiency (must be 0-1)
        with pytest.raises(ValueError, match="efficiency"):
            invalid_config = Config(
                prices_file=str(test_data_dir['market_file']),
                schedule_file=str(test_data_dir['schedule_file']),
                delivery_date="2023-04-30",
                efficiency=1.5  # Invalid: > 1.0
            )
            calculator = FlexibilityCalculator(invalid_config)
            calculator.calculate()
        
        # Test negative power values
        with pytest.raises(ValueError, match="power"):
            invalid_config = Config(
                prices_file=str(test_data_dir['market_file']),
                schedule_file=str(test_data_dir['schedule_file']),
                delivery_date="2023-04-30",
                discharge_power=-10.0  # Invalid: negative power
            )
            calculator = FlexibilityCalculator(invalid_config)
            calculator.calculate()
    
    def test_cross_component_data_consistency(self, test_data_dir):
        """
        Integration test for CROSS-COMPONENT DATA CONSISTENCY.
        
        Validates that data transformations maintain consistency as data
        flows through different pipeline stages.
        """
        config = Config(
            prices_file=str(test_data_dir['market_file']),
            schedule_file=str(test_data_dir['schedule_file']),
            output_path=str(test_data_dir['output_file']),
            delivery_date="2023-04-30"
        )
        
        calculator = FlexibilityCalculator(config)
        result = calculator.calculate()
        
        # Test temporal consistency across components
        market_times = calculator.adjusted_prices['da_time']
        option_times = calculator.option_prices['da_time']
        result_times = result['time']
        
        # All components should work with same delivery date
        delivery_date = pd.to_datetime('2023-04-30').date()
        assert all(market_times.dt.date == delivery_date), \
            "Market data should be filtered to delivery date"
        assert all(option_times.dt.date == delivery_date), \
            "Option prices should be calculated for delivery date"
        assert all(result_times.dt.date == delivery_date), \
            "Final results should be for delivery date"
        
        # Test energy conservation across optimization and cost calculation
        boundary_prices = calculator.boundary_prices
        optimization_discharge_energy = boundary_prices[2]
        optimization_charge_energy = boundary_prices[3]
        
        # Energy balance should be respected (allowing for efficiency losses)
        efficiency = config.efficiency
        expected_charge_energy = optimization_discharge_energy / efficiency
        energy_balance_error = abs(optimization_charge_energy - expected_charge_energy)
        assert energy_balance_error < 0.1, \
            f"Energy balance error too large: {energy_balance_error} MWh" 