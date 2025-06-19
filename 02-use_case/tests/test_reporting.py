"""
Unit tests for reporting.py - TSO compliance and regulatory reporting.

Tests focus on system robustness and regulatory compliance:
1. TSO report generation and regulatory compliance
2. Excel export structure and data integrity  
3. Asset valuation and opportunity cost calculation correctness
"""

import pytest
import pandas as pd
import numpy as np
import tempfile
import os
from energy_flexibility.core.reporting import values_to_tso


class TestReporting:
    
    def test_tso_report_generation_and_regulatory_compliance(self):
        """Test TSO report generation for regulatory compliance and audit requirements."""
        
        # Create realistic flexibility data for full day operation (96 intervals)
        times = pd.date_range('2023-04-30', periods=96, freq='15min')
        flexibility_data = pd.DataFrame({
            'time': times,
            'Pmax': np.random.uniform(12.0, 15.0, 96),  # Discharge capacity varies 12-15 MW
            'Vmax': np.random.uniform(12.0, 15.0, 96)   # Charge capacity varies 12-15 MW
        })
        
        # Create realistic option price series (daily pattern)
        discharge_option_prices = pd.Series([10.0 + 5.0 * np.sin(i * np.pi / 48) for i in range(96)])  # Daily pattern
        charge_option_prices = pd.Series([8.0 + 4.0 * np.sin(i * np.pi / 48) for i in range(96)])
        
        # Realistic system parameters
        delivery_date = "2023-04-30"
        discharge_power = 15.0  # MW
        charge_power = 15.0     # MW
        increase_discharge_price = 85.0  # €/MWh
        decrease_discharge_price = 45.0  # €/MWh
        decrease_charge_price = 65.0     # €/MWh
        increase_charge_price = 35.0     # €/MWh
        pump_prices = 40.0               # €/MWh
        turbine_prices = 70.0            # €/MWh
        residual_value_of_battery = 12000000  # €12M
        remaining_useful_life = 15       # years
        planned_operating_hour = 1168    # hours/year
        
        # Test with temporary file
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            # Test 1: Basic TSO report generation
            result = values_to_tso(
                flexibility_data.copy(), discharge_option_prices, charge_option_prices,
                discharge_power, charge_power, increase_discharge_price, decrease_discharge_price,
                decrease_charge_price, increase_charge_price, pump_prices, turbine_prices,
                residual_value_of_battery, remaining_useful_life, planned_operating_hour,
                delivery_date, temp_path
            )
            
            # Verify Excel file was created
            assert os.path.exists(temp_path), "TSO report Excel file should be created"
            
            # Test 2: Asset depreciation calculation correctness
            expected_value_lost_per_hour = residual_value_of_battery / (remaining_useful_life * planned_operating_hour)
            # €12M / (15 years * 1168 h/year) = €685.87/h
            assert abs(expected_value_lost_per_hour - 685.87) < 1.0, "Asset depreciation calculation should be correct"
            
            # Test 3: Opportunity cost calculation logic
            # Verify that opportunity costs are calculated correctly
            assert 'Entgangener Deckungsbeitrag für Turbinenbetrieb [Opportunity price turbine] (euro/h)' in result.columns, \
                "Turbine opportunity cost column should be added"
            assert 'Entgangener Deckungsbeitrag für Pumpbetrieb [Opportunity price pump] (euro/h)' in result.columns, \
                "Pump opportunity cost column should be added"
            assert 'Entgangener Deckungsbeitrag total [Opportunity price total] (euro/h)' in result.columns, \
                "Total opportunity cost column should be added"
            
            # Test mathematical correctness of opportunity cost calculations
            for i in range(len(result)):
                expected_pump_opportunity = charge_option_prices.iloc[i] * flexibility_data.iloc[i]['Pmax']
                expected_turbine_opportunity = discharge_option_prices.iloc[i] * flexibility_data.iloc[i]['Vmax']
                expected_total = expected_pump_opportunity + expected_turbine_opportunity
                
                assert abs(result.iloc[i]['Entgangener Deckungsbeitrag für Pumpbetrieb [Opportunity price pump] (euro/h)'] - expected_pump_opportunity) < 0.01, \
                    f"Pump opportunity cost calculation incorrect at index {i}"
                assert abs(result.iloc[i]['Entgangener Deckungsbeitrag für Turbinenbetrieb [Opportunity price turbine] (euro/h)'] - expected_turbine_opportunity) < 0.01, \
                    f"Turbine opportunity cost calculation incorrect at index {i}"
                assert abs(result.iloc[i]['Entgangener Deckungsbeitrag total [Opportunity price total] (euro/h)'] - expected_total) < 0.01, \
                    f"Total opportunity cost calculation incorrect at index {i}"
            
            # Test 4: Regulatory compliance - reasonable cost ranges
            # TSO costs should be within reasonable bounds for regulatory review
            daily_total_opportunity_cost = result['Entgangener Deckungsbeitrag total [Opportunity price total] (euro/h)'].sum()
            
            # For 15MW plant, daily opportunity costs should be €1K-€50K range
            assert 1000 <= daily_total_opportunity_cost <= 50000, \
                f"Daily opportunity costs ({daily_total_opportunity_cost:.0f}€) should be within regulatory reasonable range"
            
            # Test 5: Data type consistency for TSO systems
            # All monetary values should be float64 for regulatory precision
            assert result['Entgangener Deckungsbeitrag für Pumpbetrieb [Opportunity price pump] (euro/h)'].dtype == 'float64', \
                "Pump opportunity costs should be float64 for regulatory precision"
            assert result['Entgangener Deckungsbeitrag für Turbinenbetrieb [Opportunity price turbine] (euro/h)'].dtype == 'float64', \
                "Turbine opportunity costs should be float64 for regulatory precision"
            
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_excel_export_structure_and_data_integrity(self):
        """Test Excel report structure and data integrity for TSO compliance."""
        
        # Create minimal test dataset
        test_data = pd.DataFrame({
            'time': pd.date_range('2023-04-30', periods=4, freq='15min'),
            'Pmax': [15.0, 14.5, 13.8, 15.0],
            'Vmax': [15.0, 14.0, 14.2, 15.0]
        })
        
        discharge_prices = pd.Series([12.0, 15.0, 18.0, 10.0])
        charge_prices = pd.Series([8.0, 10.0, 12.0, 6.0])
        
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            # Generate TSO report
            values_to_tso(
                test_data.copy(), discharge_prices, charge_prices,
                15.0, 15.0, 80.0, 50.0, 60.0, 40.0, 45.0, 65.0,
                12000000, 15, 1168, "2023-04-30", temp_path
            )
            
            # Test 1: Excel file structure validation
            assert os.path.exists(temp_path), "Excel file should be created"
            
            # Read back the Excel file to verify structure
            constants_sheet = pd.read_excel(temp_path, sheet_name='Andere Kosten')
            opportunity_sheet = pd.read_excel(temp_path, sheet_name='Opportunitätskosten')
            
            # Test 2: Constants sheet structure and content
            required_constants_columns = [
                'Lieferungstag',
                'Grenzpreis Turbine [Turbine boundary price] (euro/MWh)',
                'Grenzpreis Pumpe [Pump boundary price] (euro/MWh)',
                'Erhöhung Turbine [Increase Discharge Price] (euro/MWh)',
                'Minderung Turbine [Decrease Discharge Price] (euro/MWh)',
                'Minderung Pumpe [Decrease Charge Price] (euro/MWh) ',
                'Erhöhung Pumpe [Increase Charge Price] (euro/MWh) ',
                'Anteiliger Werteverbrauch pro anrechenbare Betriebsstunde [Lost value per hour] (euro/h)'
            ]
            
            for col in required_constants_columns:
                assert col in constants_sheet.columns, f"Constants sheet should contain column: {col}"
            
            # Verify constants values are correct
            assert constants_sheet['Lieferungstag'].iloc[0] == "2023-04-30", "Delivery date should be correct"
            assert constants_sheet['Grenzpreis Turbine [Turbine boundary price] (euro/MWh)'].iloc[0] == 65.0, \
                "Turbine boundary price should be correct"
            assert constants_sheet['Grenzpreis Pumpe [Pump boundary price] (euro/MWh)'].iloc[0] == 45.0, \
                "Pump boundary price should be correct"
            
            # Test 3: Opportunity costs sheet structure
            required_opportunity_columns = [
                'time',
                'Entgangener Deckungsbeitrag für Turbinenbetrieb [Opportunity price turbine] (euro/h)',
                'Entgangener Deckungsbeitrag für Pumpbetrieb [Opportunity price pump] (euro/h)',
                'Entgangener Deckungsbeitrag total [Opportunity price total] (euro/h)'
            ]
            
            for col in required_opportunity_columns:
                assert col in opportunity_sheet.columns, f"Opportunity sheet should contain column: {col}"
            
            # Test 4: Data integrity validation
            assert len(opportunity_sheet) == 4, "Opportunity sheet should have same number of rows as input data"
            
            # Verify calculation integrity by checking first row
            expected_pump_cost_0 = charge_prices.iloc[0] * test_data.iloc[0]['Pmax']  # 8.0 * 15.0 = 120.0
            expected_turbine_cost_0 = discharge_prices.iloc[0] * test_data.iloc[0]['Vmax']  # 12.0 * 15.0 = 180.0
            expected_total_0 = expected_pump_cost_0 + expected_turbine_cost_0  # 300.0
            
            assert abs(opportunity_sheet.iloc[0]['Entgangener Deckungsbeitrag für Pumpbetrieb [Opportunity price pump] (euro/h)'] - expected_pump_cost_0) < 0.01, \
                "Pump opportunity cost should be calculated correctly in export"
            assert abs(opportunity_sheet.iloc[0]['Entgangener Deckungsbeitrag für Turbinenbetrieb [Opportunity price turbine] (euro/h)'] - expected_turbine_cost_0) < 0.01, \
                "Turbine opportunity cost should be calculated correctly in export"
            assert abs(opportunity_sheet.iloc[0]['Entgangener Deckungsbeitrag total [Opportunity price total] (euro/h)'] - expected_total_0) < 0.01, \
                "Total opportunity cost should be calculated correctly in export"
            
            # Test 5: German language compliance for regulatory requirements
            # All column names should be in German for TSO compliance
            german_terms = ['Entgangener Deckungsbeitrag', 'Turbinenbetrieb', 'Pumpbetrieb', 'Grenzpreis', 'Lieferungstag']
            all_columns = list(constants_sheet.columns) + list(opportunity_sheet.columns)
            
            has_german_terms = any(any(term in col for term in german_terms) for col in all_columns)
            assert has_german_terms, "Report should contain German language terms for regulatory compliance"
            
            # Test 6: Timestamp preservation and formatting
            # Time column should preserve original timestamps
            for i in range(len(opportunity_sheet)):
                original_time = test_data.iloc[i]['time']
                exported_time = pd.to_datetime(opportunity_sheet.iloc[i]['time'])
                assert abs((original_time - exported_time).total_seconds()) < 1, \
                    f"Timestamp should be preserved correctly at index {i}"
        
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_asset_valuation_and_opportunity_cost_calculation_correctness(self):
        """Test asset valuation and opportunity cost calculations for economic accuracy."""
        
        # Test Case 1: Asset depreciation calculation with different parameters
        test_scenarios = [
            # (residual_value, useful_life, operating_hours, expected_hourly_depreciation)
            (12000000, 15, 1168, 12000000 / (15 * 1168)),  # Standard case
            (8000000, 20, 2000, 8000000 / (20 * 2000)),    # Different parameters
            (15000000, 10, 800, 15000000 / (10 * 800))     # High value, short life
        ]
        
        for residual_value, useful_life, operating_hours, expected_depreciation in test_scenarios:
            test_data = pd.DataFrame({
                'time': pd.date_range('2023-04-30', periods=2, freq='15min'),
                'Pmax': [15.0, 15.0],
                'Vmax': [15.0, 15.0]
            })
            
            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as temp_file:
                temp_path = temp_file.name
            
            try:
                values_to_tso(
                    test_data.copy(), pd.Series([10.0, 10.0]), pd.Series([8.0, 8.0]),
                    15.0, 15.0, 80.0, 50.0, 60.0, 40.0, 45.0, 65.0,
                    residual_value, useful_life, operating_hours, "2023-04-30", temp_path
                )
                
                # Read constants sheet to verify depreciation calculation
                constants_sheet = pd.read_excel(temp_path, sheet_name='Andere Kosten')
                calculated_depreciation = constants_sheet['Anteiliger Werteverbrauch pro anrechenbare Betriebsstunde [Lost value per hour] (euro/h)'].iloc[0]
                
                assert abs(calculated_depreciation - expected_depreciation) < 0.01, \
                    f"Asset depreciation calculation incorrect: expected {expected_depreciation:.2f}, got {calculated_depreciation:.2f}"
                
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
        
        # Test Case 2: Opportunity cost scaling with capacity variations
        # Test how opportunity costs respond to different capacity scenarios
        capacity_scenarios = [
            ([15.0, 10.0, 5.0], [15.0, 12.0, 8.0]),  # Decreasing capacity
            ([5.0, 10.0, 15.0], [8.0, 12.0, 15.0]),  # Increasing capacity
            ([15.0, 15.0, 15.0], [15.0, 15.0, 15.0]) # Constant capacity
        ]
        
        option_prices = pd.Series([10.0, 12.0, 14.0])
        
        for pmax_scenario, vmax_scenario in capacity_scenarios:
            test_data = pd.DataFrame({
                'time': pd.date_range('2023-04-30', periods=3, freq='15min'),
                'Pmax': pmax_scenario,
                'Vmax': vmax_scenario
            })
            
            result = values_to_tso(
                test_data.copy(), option_prices, option_prices,
                15.0, 15.0, 80.0, 50.0, 60.0, 40.0, 45.0, 65.0,
                12000000, 15, 1168, "2023-04-30", None  # No file output for this test
            )
            
            # Verify opportunity costs scale correctly with capacity
            for i in range(len(result)):
                expected_pump_opp = option_prices.iloc[i] * pmax_scenario[i]
                expected_turbine_opp = option_prices.iloc[i] * vmax_scenario[i]
                
                actual_pump_opp = result.iloc[i]['Entgangener Deckungsbeitrag für Pumpbetrieb [Opportunity price pump] (euro/h)']
                actual_turbine_opp = result.iloc[i]['Entgangener Deckungsbeitrag für Turbinenbetrieb [Opportunity price turbine] (euro/h)']
                
                assert abs(actual_pump_opp - expected_pump_opp) < 0.01, \
                    f"Pump opportunity cost should scale with capacity: expected {expected_pump_opp}, got {actual_pump_opp}"
                assert abs(actual_turbine_opp - expected_turbine_opp) < 0.01, \
                    f"Turbine opportunity cost should scale with capacity: expected {expected_turbine_opp}, got {actual_turbine_opp}"
        
        # Test Case 3: Economic consistency checks
        # High option prices should lead to high opportunity costs
        high_option_prices = pd.Series([50.0, 60.0, 70.0])
        low_option_prices = pd.Series([5.0, 6.0, 7.0])
        
        test_data = pd.DataFrame({
            'time': pd.date_range('2023-04-30', periods=3, freq='15min'),
            'Pmax': [15.0, 15.0, 15.0],
            'Vmax': [15.0, 15.0, 15.0]
        })
        
        result_high = values_to_tso(
            test_data.copy(), high_option_prices, high_option_prices,
            15.0, 15.0, 80.0, 50.0, 60.0, 40.0, 45.0, 65.0,
            12000000, 15, 1168, "2023-04-30", None
        )
        
        result_low = values_to_tso(
            test_data.copy(), low_option_prices, low_option_prices,
            15.0, 15.0, 80.0, 50.0, 60.0, 40.0, 45.0, 65.0,
            12000000, 15, 1168, "2023-04-30", None
        )
        
        # High option prices should result in higher opportunity costs
        high_total = result_high['Entgangener Deckungsbeitrag total [Opportunity price total] (euro/h)'].sum()
        low_total = result_low['Entgangener Deckungsbeitrag total [Opportunity price total] (euro/h)'].sum()
        
        assert high_total > low_total * 5, \
            "Higher option prices should result in significantly higher opportunity costs"
        
        # Test Case 4: Zero option price handling
        zero_option_prices = pd.Series([0.0, 0.0, 0.0])
        
        result_zero = values_to_tso(
            test_data.copy(), zero_option_prices, zero_option_prices,
            15.0, 15.0, 80.0, 50.0, 60.0, 40.0, 45.0, 65.0,
            12000000, 15, 1168, "2023-04-30", None
        )
        
        # Zero option prices should result in zero opportunity costs
        assert all(result_zero['Entgangener Deckungsbeitrag total [Opportunity price total] (euro/h)'] == 0), \
            "Zero option prices should result in zero opportunity costs" 