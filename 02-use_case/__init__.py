"""
Energy Flexibility Library

A comprehensive Python library for energy flexibility cost calculations
and optimization for pumped hydro storage systems.

This library provides tools for:
- Economic optimization of energy storage operations
- Flexibility service cost calculations
- Market analysis and price forecasting
- TSO regulatory reporting
- Option pricing for flexibility services

Quick Start:
    from energy_flexibility import FlexibilityCalculator, Config
    
    config = Config(
        delivery_date="2024-01-15",
        prices_file="path/to/prices.xlsx",
        schedule_file="path/to/schedule.xlsx"
    )
    
    calculator = FlexibilityCalculator(config)
    results = calculator.calculate()
"""

# Import main classes and functions from core for easy access
from .core import (
    FlexibilityCalculator, Config,
    Price, Power, Energy, Cost, Efficiency,
    MarketData, PriceData, BoundaryPrices, ProductionCosts,
    load_and_prepare_data, calculate_average_diff,
    find_optimal_boundary_prices_turbine_first,
    calculate_option_prices, calculate_production_flexibility_cost,
    values_to_tso
)

# Package metadata
__version__ = "1.0.0"
__author__ = "Energy Flexibility Team"
__description__ = "Energy flexibility cost calculations for pumped hydro storage"

# What gets imported with "from energy_flexibility import *"
__all__ = [
    # Main interface - most commonly used
    "FlexibilityCalculator",
    "Config",
    
    # Core types - commonly used
    "Price", "Power", "Energy", "Cost", "Efficiency",
    
    # Key data structures
    "MarketData", "PriceData", "BoundaryPrices", "ProductionCosts",
    
    # Key functions
    "load_and_prepare_data",
    "calculate_average_diff", 
    "find_optimal_boundary_prices_turbine_first",
    "calculate_option_prices",
    "calculate_production_flexibility_cost",
    "values_to_tso"
] 