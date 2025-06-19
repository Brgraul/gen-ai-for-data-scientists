"""
Configuration management for energy flexibility calculations.
"""

from dataclasses import dataclass
from typing import Optional
from pathlib import Path
import os

from .models import (
    Power, Efficiency, Price, Cost, DeliveryDate,
    SystemParameters, EconomicParameters, AnalysisParameters
)


@dataclass
class Config:
    """
    Configuration class for energy flexibility calculations.
    
    Centralizes all parameters needed for the flexibility cost calculation,
    providing default values for common use cases.
    """
    
    # Required parameters
    delivery_date: DeliveryDate
    prices_file: str
    schedule_file: str
    
    # Power parameters with defaults
    discharge_power: Power = Power(15.0)  # MW (turbine)
    charge_power: Power = Power(15.0)     # MW (pump)
    efficiency: Efficiency = Efficiency(0.9)        # Round-trip efficiency
    
    # Economic parameters with defaults
    network_charges: Price = Price(1.5)                    # Congestion and network charges (€/MWh)
    max_discharge_hours: float = 3.0          # Full load hours
    residual_value_of_battery: Cost = Cost(12000000.0)  # Euro
    remaining_useful_life: float = 15.0    # Years
    planned_operating_hour: float = 365 * 1.6 * 2  # Hours per year
    
    # Analysis parameters
    price_analysis_days: int = 90        # Days for historical price analysis
    volatility_analysis_days: int = 30   # Days for volatility analysis
    
    # Output configuration
    output_path: Optional[str] = None
    
    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if not os.path.exists(self.prices_file):
            raise FileNotFoundError(f"Prices file not found: {self.prices_file}")
        if not os.path.exists(self.schedule_file):
            raise FileNotFoundError(f"Schedule file not found: {self.schedule_file}")
        
        if self.efficiency <= 0 or self.efficiency > 1:
            raise ValueError("Efficiency must be between 0 and 1")
        
        if self.discharge_power <= 0:
            raise ValueError("Discharge power must be positive")
        
        if self.charge_power <= 0:
            raise ValueError("Charge power must be positive")
    
    def to_system_parameters(self) -> SystemParameters:
        """Convert config to SystemParameters model."""
        return SystemParameters(
            discharge_power=self.discharge_power,
            charge_power=self.charge_power,
            efficiency=self.efficiency,
            network_charges=self.network_charges,
            max_discharge_hours=self.max_discharge_hours,
            reservoir_capacity=Power(0.0)  # Not specified in config, default
        )
    
    def to_economic_parameters(self) -> EconomicParameters:
        """Convert config to EconomicParameters model."""
        return EconomicParameters(
            residual_value_of_battery=self.residual_value_of_battery,
            remaining_useful_life=self.remaining_useful_life,
            planned_operating_hour=self.planned_operating_hour,
            discount_rate=0.05,  # Default 5%
            inflation_rate=0.02,  # Default 2%
            tax_rate=0.25  # Default 25%
        )
    
    def to_analysis_parameters(self) -> AnalysisParameters:
        """Convert config to AnalysisParameters model."""
        return AnalysisParameters(
            price_analysis_days=self.price_analysis_days,
            volatility_analysis_days=self.volatility_analysis_days,
            minimum_volatility=Price(0.01),  # Default minimum volatility
            volatility_premium_factor=0.8,   # Default premium factor
            confidence_level=0.95  # Default 95% confidence
        )

    def to_dict(self) -> dict:
        """Convert config to dictionary for easy parameter passing."""
        return {
            'prices_file': self.prices_file,
            'schedule_file': self.schedule_file,
            'output_path': self.output_path,
            'delivery_date': self.delivery_date,
            'price_analysis_days': self.price_analysis_days,
            'volatility_analysis_days': self.volatility_analysis_days,
            'discharge_power': self.discharge_power,
            'charge_power': self.charge_power,
            'efficiency': self.efficiency,
            'network_charges': self.network_charges,
            'max_discharge_hours': self.max_discharge_hours,
            'residual_value_of_battery': self.residual_value_of_battery,
            'remaining_useful_life': self.remaining_useful_life,
            'planned_operating_hour': self.planned_operating_hour,
        } 