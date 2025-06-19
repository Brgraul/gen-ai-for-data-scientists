"""
Unit tests for config.py - Configuration management.

Tests focus on the most critical failure points:
1. File validation (most common user error)
2. Parameter validation (breaks calculations)
3. Valid creation (smoke test)
"""

import pytest
import tempfile
import os
from energy_flexibility.core.config import Config
from energy_flexibility.core.models import Power, Price


class TestConfig:
    
    def test_config_file_validation(self):
        """Test file validation - the #1 user error source."""
        # Test missing prices file
        with tempfile.NamedTemporaryFile(delete=False) as temp_schedule:
            temp_schedule.write(b"dummy schedule data")
            temp_schedule_path = temp_schedule.name
        
        try:
            with pytest.raises(FileNotFoundError, match="Prices file not found"):
                Config(
                    delivery_date="2023-04-30",
                    prices_file="/nonexistent/prices.xlsx",
                    schedule_file=temp_schedule_path
                )
            
            # Test missing schedule file
            with tempfile.NamedTemporaryFile(delete=False) as temp_prices:
                temp_prices.write(b"dummy price data")
                temp_prices_path = temp_prices.name
            
            try:
                with pytest.raises(FileNotFoundError, match="Schedule file not found"):
                    Config(
                        delivery_date="2023-04-30",
                        prices_file=temp_prices_path,
                        schedule_file="/nonexistent/schedule.xls"
                    )
            finally:
                os.unlink(temp_prices_path)
        finally:
            os.unlink(temp_schedule_path)
    
    def test_config_parameter_validation(self):
        """Test critical parameter validation that breaks calculations."""
        # Create temporary files for testing
        with tempfile.NamedTemporaryFile(delete=False) as temp_prices:
            temp_prices.write(b"dummy price data")
            temp_prices_path = temp_prices.name
        
        with tempfile.NamedTemporaryFile(delete=False) as temp_schedule:
            temp_schedule.write(b"dummy schedule data")
            temp_schedule_path = temp_schedule.name
        
        try:
            # Test invalid efficiency values
            with pytest.raises(ValueError, match="Efficiency must be between 0 and 1"):
                Config(
                    delivery_date="2023-04-30",
                    prices_file=temp_prices_path,
                    schedule_file=temp_schedule_path,
                    efficiency=0.0  # Invalid: zero efficiency
                )
            
            with pytest.raises(ValueError, match="Efficiency must be between 0 and 1"):
                Config(
                    delivery_date="2023-04-30",
                    prices_file=temp_prices_path,
                    schedule_file=temp_schedule_path,
                    efficiency=-0.1  # Invalid: negative efficiency
                )
            
            with pytest.raises(ValueError, match="Efficiency must be between 0 and 1"):
                Config(
                    delivery_date="2023-04-30",
                    prices_file=temp_prices_path,
                    schedule_file=temp_schedule_path,
                    efficiency=1.1  # Invalid: efficiency > 1
                )
            
            # Test invalid power values
            with pytest.raises(ValueError, match="Discharge power must be positive"):
                Config(
                    delivery_date="2023-04-30",
                    prices_file=temp_prices_path,
                    schedule_file=temp_schedule_path,
                    discharge_power=0.0  # Invalid: zero power
                )
            
            with pytest.raises(ValueError, match="Discharge power must be positive"):
                Config(
                    delivery_date="2023-04-30",
                    prices_file=temp_prices_path,
                    schedule_file=temp_schedule_path,
                    discharge_power=-5.0  # Invalid: negative power
                )
            
            with pytest.raises(ValueError, match="Charge power must be positive"):
                Config(
                    delivery_date="2023-04-30",
                    prices_file=temp_prices_path,
                    schedule_file=temp_schedule_path,
                    charge_power=0.0  # Invalid: zero power
                )
            
            with pytest.raises(ValueError, match="Charge power must be positive"):
                Config(
                    delivery_date="2023-04-30",
                    prices_file=temp_prices_path,
                    schedule_file=temp_schedule_path,
                    charge_power=-10.0  # Invalid: negative power
                )
            
        finally:
            os.unlink(temp_prices_path)
            os.unlink(temp_schedule_path)
    
    def test_config_valid_creation(self):
        """Test valid configuration creation and defaults - smoke test."""
        # Create temporary files
        with tempfile.NamedTemporaryFile(delete=False) as temp_prices:
            temp_prices.write(b"dummy price data")
            temp_prices_path = temp_prices.name
        
        with tempfile.NamedTemporaryFile(delete=False) as temp_schedule:
            temp_schedule.write(b"dummy schedule data")
            temp_schedule_path = temp_schedule.name
        
        try:
            # Test valid creation with defaults
            config = Config(
                delivery_date="2023-04-30",
                prices_file=temp_prices_path,
                schedule_file=temp_schedule_path
            )
            
            # Verify required parameters are set
            assert config.delivery_date == "2023-04-30"
            assert config.prices_file == temp_prices_path
            assert config.schedule_file == temp_schedule_path
            
            # Verify critical defaults are correct
            assert config.discharge_power == Power(15.0)
            assert config.charge_power == Power(15.0)
            assert config.efficiency == 0.9
            assert config.network_charges == Price(1.5)
            assert config.max_discharge_hours == 3.0
            assert config.residual_value_of_battery == 12000000.0
            assert config.remaining_useful_life == 15.0
            assert config.planned_operating_hour == 1168.0
            
            # Test valid creation with custom values
            config_custom = Config(
                delivery_date="2023-05-01",
                prices_file=temp_prices_path,
                schedule_file=temp_schedule_path,
                discharge_power=20.0,
                charge_power=18.0,
                efficiency=0.85,
                network_charges=Price(2.0),
                max_discharge_hours=4.0,
                residual_value_of_battery=15000000.0,
                remaining_useful_life=12.0,
                planned_operating_hour=1200.0
            )
            
            assert config_custom.discharge_power == Power(20.0)
            assert config_custom.charge_power == Power(18.0)
            assert config_custom.efficiency == 0.85
            assert config_custom.network_charges == Price(2.0)
            assert config_custom.max_discharge_hours == 4.0
            assert config_custom.residual_value_of_battery == 15000000.0
            assert config_custom.remaining_useful_life == 12.0
            assert config_custom.planned_operating_hour == 1200.0
            
            # Test boundary efficiency values (should be valid)
            config_boundary = Config(
                delivery_date="2023-04-30",
                prices_file=temp_prices_path,
                schedule_file=temp_schedule_path,
                efficiency=1.0  # Boundary: exactly 1.0 should be valid
            )
            assert config_boundary.efficiency == 1.0
            
            config_small = Config(
                delivery_date="2023-04-30",
                prices_file=temp_prices_path,
                schedule_file=temp_schedule_path,
                efficiency=0.01  # Small but positive efficiency
            )
            assert config_small.efficiency == 0.01
            
        finally:
            os.unlink(temp_prices_path)
            os.unlink(temp_schedule_path)

    def test_default_configuration_values(self):
        """Test default configuration values."""
        # Create temporary files for testing
        with tempfile.NamedTemporaryFile(delete=False) as temp_prices:
            temp_prices.write(b"dummy price data")
            temp_prices_path = temp_prices.name
        
        with tempfile.NamedTemporaryFile(delete=False) as temp_schedule:
            temp_schedule.write(b"dummy schedule data")
            temp_schedule_path = temp_schedule.name
        
        try:
            config = Config(
                prices_file=temp_prices_path,
                schedule_file=temp_schedule_path, 
                output_path="test_output.xlsx",
                delivery_date="2023-04-30"
            )
            
            # Test default values
            assert config.price_analysis_days == 90
            assert config.volatility_analysis_days == 30
            assert config.discharge_power == Power(15.0)
            assert config.charge_power == Power(15.0)
            assert config.efficiency == 0.9
            assert config.network_charges == Price(1.5)
            assert config.max_discharge_hours == 3.0
            assert config.residual_value_of_battery == 12000000.0
            assert config.remaining_useful_life == 15.0
            assert config.planned_operating_hour == 1168.0
            
        finally:
            os.unlink(temp_prices_path)
            os.unlink(temp_schedule_path) 