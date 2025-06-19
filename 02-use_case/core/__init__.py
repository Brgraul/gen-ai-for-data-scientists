"""
Energy Flexibility Core Library

This module provides the core functionality for energy flexibility cost calculations
and optimization for pumped hydro storage systems.
"""

# Main calculator class - the primary interface
from .calculator import FlexibilityCalculator

# Configuration and models
from .config import Config
from .models import (
    # Basic types
    Price, Power, Energy, Cost, Efficiency, Volatility,
    DeliveryDate, TimeSlot, OptionPriceSeries, MarketPriceSeries,
    
    # Data classes
    MarketData, PriceData, VolatilityData, OptionPrices,
    BoundaryPrices, ProductionCosts, OptimizationResults,
    RedispatchOperationsData, FlexibilitySchedule, OpportunityCosts,
    FlexibilityConstraints, SystemParameters, EconomicParameters,
    AnalysisParameters, FlexibilityMetrics, FlexibilityResults,
    TSOReportData, ExportConfig, ValidationResults, CalculationContext
)

# Data loading and preparation
from .data_loader import load_and_prepare_data, load_as_market_data, expand_da_time

# Market analysis functions
from .market_analysis import (
    calculate_average_diff, adjust_da_prices_for_date, 
    create_price_data, calculate_standard_deviation, create_volatility_data
)

# Optimization functions
from .optimization import (
    find_optimal_boundary_prices_turbine_first, create_boundary_prices,
    calculate_flexibility_cost_prices, create_flexibility_costs
)

# Cost calculation functions
from .cost_calculation import (
    calculate_option_prices, create_option_prices,
    calculate_production_flexibility_cost, calculate_deprecation_cost,
    aggregate_costs
)

# Reporting functions
from .reporting import values_to_tso

# Version info
__version__ = "1.0.0"
__author__ = "Energy Flexibility Team"

# Public API - what gets imported with "from energy_flexibility.core import *"
__all__ = [
    # Main interface
    "FlexibilityCalculator",
    "Config",
    
    # Core types
    "Price", "Power", "Energy", "Cost", "Efficiency", "Volatility",
    "DeliveryDate", "TimeSlot", "OptionPriceSeries", "MarketPriceSeries",
    
    # Data structures
    "MarketData", "PriceData", "VolatilityData", "OptionPrices",
    "BoundaryPrices", "ProductionCosts", "OptimizationResults",
    "RedispatchOperationsData", "FlexibilitySchedule", "OpportunityCosts",
    "FlexibilityConstraints", "SystemParameters", "EconomicParameters",
    "AnalysisParameters", "FlexibilityMetrics", "FlexibilityResults",
    "TSOReportData", "ExportConfig", "ValidationResults", "CalculationContext",
    
    # Functions
    "load_and_prepare_data", "load_as_market_data", "expand_da_time",
    "calculate_average_diff", "adjust_da_prices_for_date", "create_price_data",
    "calculate_standard_deviation", "create_volatility_data",
    "find_optimal_boundary_prices_turbine_first", "create_boundary_prices",
    "calculate_flexibility_cost_prices", "create_flexibility_costs",
    "calculate_option_prices", "create_option_prices",
    "calculate_production_flexibility_cost", "calculate_deprecation_cost",
    "aggregate_costs", "values_to_tso"
] 