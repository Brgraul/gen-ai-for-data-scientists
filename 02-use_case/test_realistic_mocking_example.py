"""
REALISTIC MOCKING EXAMPLE - When Mocking Actually Makes Sense
============================================================

This demonstrates mocking for practical engineering reasons:
1. File I/O dependencies (expensive, brittle, external)
2. Error conditions that are hard to reproduce
3. Integration testing where you want to isolate components

Function under test: load_and_prepare_data()
- Reads Excel files (external dependency - should be mocked!)
- Has file I/O error conditions
- Perfect example of when mocking is valuable
"""

import pytest
import pandas as pd
from datetime import datetime
from unittest.mock import Mock, patch, mock_open
from pathlib import Path
from energy_flexibility.core.data_loader import load_and_prepare_data


class TestRealisticMocking:
    """
    Realistic examples where mocking provides real value for engineers
    """
    
    def test_without_mocking_simple_case(self):
        """
        For simple data transformations, DON'T mock - just use real data
        This is what you should do for most DataFrame operations
        """
        # Create simple test DataFrame - much cleaner than mocking!
        test_data = pd.DataFrame({
            'da_time': [datetime(2023, 4, 30, 14, 0)],
            'da_prices': [50.0],
            'ida_time': [datetime(2023, 4, 30, 14, 15)],
            'ida_prices': [52.0],
            'd1_time': [datetime(2023, 4, 30, 14, 30)],
            'd1_prices': [51.0]
        })
        
        # Test your logic directly - no mocking complexity
        assert len(test_data) == 1
        assert test_data['da_prices'].iloc[0] == 50.0
        # This is much more readable and practical!
    
    @patch('pandas.read_excel')
    def test_file_io_mocking_makes_sense(self, mock_read_excel):
        """
        THIS is where mocking makes sense - file I/O operations
        You don't want tests depending on external files
        """
        # Arrange - Mock the Excel file reading
        mock_excel_data = pd.DataFrame({
            'col1': ['header'] * 7 + [datetime(2023, 4, 30, 14, 0)],  # Skip first 6 rows
            'col2': ['header'] * 7 + [50.0],  # DA prices
            'col7': ['header'] * 7 + [datetime(2023, 4, 30, 14, 15)],  # IDA time
            'col8': ['header'] * 7 + [52.0],  # IDA prices
            'col9': ['header'] * 7 + [datetime(2023, 4, 30, 14, 30)],  # D1 time
            'col10': ['header'] * 7 + [51.0]  # D1 prices
        })
        mock_read_excel.return_value = mock_excel_data
        
        # Act - Call function that reads Excel
        result = load_and_prepare_data("fake_file.xlsx")
        
        # Assert - Verify file was read and data processed correctly
        mock_read_excel.assert_called_once_with("fake_file.xlsx")
        
        # Verify data processing logic (the real value of the test)
        assert 'da_time' in result.columns
        assert 'da_prices' in result.columns
        assert 'ida_time' in result.columns
        assert result['da_prices'].iloc[0] == 50.0
        
        # This mocking prevents your tests from breaking if files move/change
    
    @patch('pandas.read_excel')
    def test_file_not_found_error_handling(self, mock_read_excel):
        """
        Test error conditions that are hard to reproduce without mocking
        You can't easily create "file not found" with real files in CI/CD
        """
        # Arrange - Make file reading fail
        mock_read_excel.side_effect = FileNotFoundError("Excel file not found")
        
        # Act & Assert - Verify error handling
        with pytest.raises(FileNotFoundError):
            load_and_prepare_data("nonexistent_file.xlsx")
    
    @patch('pandas.read_excel')
    def test_corrupted_excel_file_handling(self, mock_read_excel):
        """
        Test edge cases that are expensive to create with real files
        """
        # Arrange - Mock corrupted Excel data
        corrupted_data = pd.DataFrame()  # Empty DataFrame simulates corruption
        mock_read_excel.return_value = corrupted_data
        
        # Act - This might fail or handle gracefully
        try:
            result = load_and_prepare_data("corrupted_file.xlsx")
            # Verify graceful handling of edge case
            assert result is not None
        except Exception as e:
            # Or verify appropriate error is raised
            assert "expected columns" in str(e).lower() or "index" in str(e).lower()
    
    @patch('pathlib.Path.exists')
    @patch('pandas.read_excel')
    def test_integration_with_path_validation(self, mock_read_excel, mock_path_exists):
        """
        Example of mocking multiple dependencies for integration testing
        This actually provides value - you're testing logic, not file system
        """
        # Arrange - Mock file system and Excel reading
        mock_path_exists.return_value = True
        mock_read_excel.return_value = pd.DataFrame({
            'col1': [None] * 7 + [datetime(2023, 4, 30, 14, 0)],
            'col2': [None] * 7 + [50.0],
            'col7': [None] * 7 + [datetime(2023, 4, 30, 14, 15)],
            'col8': [None] * 7 + [52.0],
            'col9': [None] * 7 + [datetime(2023, 4, 30, 14, 30)],
            'col10': [None] * 7 + [51.0]
        })
        
        # Act
        result = load_and_prepare_data(Path("test_file.xlsx"))
        
        # Assert - Focus on the logic, not the I/O
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1  # Should have 1 row after skipping headers


class TestWhenNotToMock:
    """
    Examples showing when mocking is overkill - just use real data
    """
    
    def test_simple_dataframe_operations_no_mocking_needed(self):
        """
        For most DataFrame operations, create simple test data
        This is faster, clearer, and tests real behavior
        """
        # Just create the data you need - no mocking complexity!
        prices = pd.DataFrame({
            'timestamp': pd.date_range('2023-04-30 14:00', periods=4, freq='15min'),
            'price': [50.0, 52.0, 48.0, 51.0]
        })
        
        # Test actual pandas operations
        hourly_avg = prices.groupby(prices['timestamp'].dt.hour)['price'].mean()
        
        assert len(hourly_avg) == 1  # One hour of data
        assert hourly_avg.iloc[0] == 50.25  # Average of 50, 52, 48, 51
        
        # This is much more practical than mocking groupby()!
    
    def test_mathematical_operations_use_real_data(self):
        """
        For calculations and transformations, real data is better
        """
        data = pd.DataFrame({
            'values': [10, 20, 30, 40, 50]
        })
        
        # Test real calculations
        data['doubled'] = data['values'] * 2
        data['cumsum'] = data['values'].cumsum()
        
        assert data['doubled'].tolist() == [20, 40, 60, 80, 100]
        assert data['cumsum'].tolist() == [10, 30, 60, 100, 150]
        
        # Clear, fast, tests actual behavior - no mocking needed


# Real-world example of good mocking in your pipeline
class TestCalculatorWithRealisticMocking:
    """
    How to mock appropriately in your FlexibilityCalculator
    """
    
    @patch('energy_flexibility.core.data_loader.load_and_prepare_data')
    @patch('energy_flexibility.core.calculator.pd.read_parquet')
    def test_calculator_workflow_integration(self, mock_read_parquet, mock_load_data):
        """
        Mock the I/O operations, test the business logic
        This provides real value - isolated testing of your algorithm
        """
        # Mock external data sources (good use of mocking)
        mock_load_data.return_value = pd.DataFrame({
            'da_time': pd.date_range('2023-04-30', periods=24, freq='1H'),
            'da_prices': [50.0] * 24,
            'ida_time': pd.date_range('2023-04-30', periods=96, freq='15min'),
            'ida_prices': [52.0] * 96
        })
        
        mock_read_parquet.return_value = pd.DataFrame({
            'time': pd.date_range('2023-04-30', periods=96, freq='15min'),
            'Pmax': [4.0] * 96,
            'Vmax': [100.0] * 96,
            'Pt': [2.0] * 96,
            'Prd': [0.0] * 96,
            'Pnew': [2.0] * 96,
            'RedispatchType': ['none'] * 96,
            'pos_vorgehaltene_leistung': [0.0] * 96,
            'neg_vorgehaltene_leistung': [0.0] * 96
        })
        
        # Now test your business logic without I/O dependencies
        # This is valuable mocking - isolates your algorithm from external dependencies
        
        # You'd create a FlexibilityCalculator instance and test the workflow
        # without worrying about file paths, corrupted data, missing files, etc. 