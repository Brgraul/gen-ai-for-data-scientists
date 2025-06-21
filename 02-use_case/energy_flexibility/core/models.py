"""
Type definitions and data models for the energy flexibility trading library.

This module provides comprehensive type definitions for all data structures used
throughout the energy flexibility calculations, enabling better type safety,
documentation, and IDE support.
"""

from dataclasses import dataclass
from typing import NamedTuple, NewType, Optional, Dict
from pathlib import Path
from datetime import datetime
import pandas as pd

# =============================================================================
# SECTION 1: BASIC TYPES AND PRIMITIVES
# =============================================================================

# Core financial and physical unit types
Price = NewType('Price', float)          # €/MWh - Energy prices
Power = NewType('Power', float)          # MW - Power capacity/generation
Energy = NewType('Energy', float)        # MWh - Energy quantities
Cost = NewType('Cost', float)           # € - Monetary costs
Efficiency = NewType('Efficiency', float)  # 0.0-1.0 - Round-trip efficiency
Volatility = NewType('Volatility', float)  # €/MWh - Price volatility (std dev)

# Time-based types
TimeSlot = NewType('TimeSlot', str)      # "HH:MM" - 15-minute time slots
DeliveryDate = NewType('DeliveryDate', str)  # "YYYY-MM-DD" - Delivery dates

# Specialized series types for cost calculations
OptionPriceSeries = NewType('OptionPriceSeries', pd.Series)  # Option prices over time (€/MWh)
MarketPriceSeries = NewType('MarketPriceSeries', pd.Series)  # Market prices over time (€/MWh)
RedispatchType = NewType('RedispatchType', str)  # "keine" | "einseitig" | "beidseitig"

# Asset depreciation types
AssetValue = NewType('AssetValue', float)  # € - Asset value
LifetimeYears = NewType('LifetimeYears', float)  # Years - Remaining useful life
OperatingHours = NewType('OperatingHours', float)  # Hours - Annual operating hours


# =============================================================================
# SECTION 2: TIME-SERIES DATA CLASSES
# =============================================================================

@dataclass
class MarketData:
    """
    Complete market price data loaded from Excel files.
    
    Contains historical price data from multiple markets used for
    flexibility cost calculations and price forecasting.
    """
    da_time: pd.Series      # Day-ahead market timestamps
    da_prices: pd.Series    # Day-ahead prices (€/MWh)
    ida_time: pd.Series     # Intraday auction timestamps
    ida_prices: pd.Series   # Intraday auction prices (€/MWh)
    d1_time: pd.Series      # D-1 market timestamps
    d1_prices: pd.Series    # D-1 market prices (€/MWh)


@dataclass
class PriceData:
    """
    Price data for a specific delivery period with forecasts.
    
    Enhanced day-ahead prices with intraday price predictions
    used for optimization and option pricing calculations.
    """
    da_time: pd.Series              # Original day-ahead timestamps
    da_prices: pd.Series            # Original day-ahead prices (€/MWh)
    adjusted_da_prices: pd.Series   # Forecasted intraday prices (€/MWh)


@dataclass
class VolatilityData:
    """
    Market volatility data for option pricing calculations.
    
    Contains historical price volatility patterns used in
    Black-Scholes option pricing for flexibility services.
    """
    time_slots: pd.Index        # Time slot index ("HH:MM")
    standard_deviations: pd.Series  # Volatility by time slot (€/MWh)
    overall_volatility: float   # Overall market volatility
    analysis_period_days: int   # Historical analysis period


@dataclass
class OptionPrices:
    """
    Calculated option values for flexibility services.
    
    Results from Black-Scholes option pricing methodology
    applied to energy flexibility services.
    """
    data: pd.DataFrame              # Complete DataFrame with all calculations
    charge_option_price: pd.Series  # Charging flexibility option values (€/MWh)
    discharge_option_price: pd.Series  # Discharging flexibility option values (€/MWh)
    standard_deviation: pd.Series   # Applied volatility per time slot
    volatility_premium: pd.Series   # Time value premium applied


# =============================================================================
# SECTION 3: OPTIMIZATION RESULT TYPES
# =============================================================================

@dataclass
class BoundaryPrices:
    """
    Optimal economic boundary prices from the optimization algorithm.
    
    These prices define the economic thresholds for profitable
    charging and discharging operations in pumped hydro storage.
    """
    turbine_price: Price    # Minimum price for profitable discharge (€/MWh)
    pump_price: Price       # Maximum price for profitable charge (€/MWh)
    turbine_energy: Energy  # Total planned discharge energy (MWh)
    pump_energy: Energy     # Total planned charge energy (MWh)

@dataclass
class ProductionCosts:
    """
    Production cost prices for TSO flexibility services.
    
    Defines the cost structure for different flexibility service
    scenarios based on economic optimization results.
    """
    increase_discharge: Price   # Cost for increasing discharge - TSO pays operator (€/MWh)
    decrease_discharge: Price   # Cost for decreasing discharge - operator pays TSO (€/MWh)
    decrease_charge: Price      # Cost for decreasing charge - TSO pays operator (€/MWh)
    increase_charge: Price      # Cost for increasing charge - operator pays TSO (€/MWh)


@dataclass
class OptimizationResults:
    """
    Complete results from the economic optimization process.
    
    Contains all outputs from the boundary price optimization
    and production cost calculations.
    """
    boundary_prices: BoundaryPrices
    production_costs: ProductionCosts
    optimization_iterations: int
    convergence_achieved: bool
    energy_balance_satisfied: bool


# =============================================================================
# SECTION 4: FLEXIBILITY SERVICE TYPES
# =============================================================================

@dataclass
class RedispatchOperationsData:
    """
    Complete redispatch operations DataFrame structure for cost calculations.
    
    Represents the DataFrame structure used throughout the cost calculation process,
    including input columns, intermediate calculations, and final cost outputs.
    This provides type safety for the complex DataFrame operations in cost functions.
    """
    # Input operational data columns
    time: pd.Series                                # Time stamps for each 15-min interval
    pmax: pd.Series                               # Maximum discharge capacity per interval (MW)
    vmax: pd.Series                               # Maximum charge capacity per interval (MW)
    pt: pd.Series                                 # Planned power schedule (MW, positive=discharge)
    prd: pd.Series                                # Redispatch adjustment power (MW)
    pnew: pd.Series                               # New power after redispatch (MW)
    redispatch_type: pd.Series                    # Redispatch constraint type
    pos_reserved_power: pd.Series                 # Positive reserved capacity (MW)
    neg_reserved_power: pd.Series                 # Negative reserved capacity (MW)
    
    # Calculated capacity blocking (added by cost functions)
    blocked_turbine_capacity: Optional[pd.Series] = None      # Turbine capacity blocked by redispatch (MW)
    blocked_pump_capacity: Optional[pd.Series] = None         # Pump capacity blocked by redispatch (MW)
    
    # Production cost calculations (added by cost functions)
    turbine_production_cost: Optional[pd.Series] = None       # Direct turbine operation costs (€)
    pump_production_cost: Optional[pd.Series] = None          # Direct pump operation costs (€)
    
    # Opportunity cost calculations (added by cost functions)
    turbine_opportunity_cost: Optional[pd.Series] = None      # Lost turbine revenue (€)
    pump_opportunity_cost: Optional[pd.Series] = None         # Lost pump revenue (€)
    
    # Asset depreciation calculations (added by cost functions)
    asset_depreciation_cost: Optional[pd.Series] = None       # Asset wear/depreciation costs (€)
    
    # Final aggregated costs (added by finalize function)
    total_production_costs: Optional[pd.Series] = None        # Sum of production costs (€)
    total_opportunity_costs: Optional[pd.Series] = None       # Sum of opportunity costs (€)
    max_opportunity_vs_depreciation: Optional[pd.Series] = None  # Max(opportunity, depreciation) (€)
    total_costs_per_timeslot: Optional[pd.Series] = None      # Final cost per 15-min interval (€)


@dataclass
class FlexibilitySchedule:
    """
    Operational flexibility schedule data from TSO planning.
    
    Contains the detailed operational plan with power capacities
    and redispatch requirements for each 15-minute interval.
    """
    time: pd.Series                 # Time stamps for each interval
    pmax: pd.Series                 # Maximum discharge capacity (MW)
    vmax: pd.Series                 # Maximum charge capacity (MW)
    pt: pd.Series                   # Actual turbine power (MW)
    prd: pd.Series                  # Redispatch power (MW)
    pnew: pd.Series                 # New schedule power (MW)
    redispatch_type: pd.Series      # Type of redispatch operation
    pos_reserved_power: pd.Series   # Positive reserved power (MW)
    neg_reserved_power: pd.Series   # Negative reserved power (MW)


@dataclass
class OpportunityCosts:
    """
    Calculated opportunity costs for flexibility services.
    
    Contains all cost components for providing flexibility services,
    including opportunity costs, production costs, and asset depreciation.
    """
    # Opportunity cost components
    turbine_opportunity: pd.Series      # Turbine opportunity cost (€)
    pump_opportunity: pd.Series         # Pump opportunity cost (€)
    total_opportunity: pd.Series        # Total opportunity cost (€)
    
    # Production cost components
    production_turbine: pd.Series       # Turbine production cost (€)
    production_pump: pd.Series          # Pump production cost (€)
    total_production: pd.Series         # Total production cost (€)
    
    # Asset depreciation
    value_lost: pd.Series              # Asset value depreciation (€)
    
    # Final cost calculations
    max_opportunity_vs_depreciation: pd.Series  # Max(opportunity, depreciation) (€)
    total_costs: pd.Series             # Final total costs per time slot (€)


@dataclass
class FlexibilityConstraints:
    """
    Technical and operational constraints for flexibility services.
    
    Defines the physical and operational limits that constrain
    the flexibility service provision.
    """
    max_discharge_power: Power      # Maximum turbine capacity (MW)
    max_charge_power: Power         # Maximum pump capacity (MW)
    min_reservoir_level: float      # Minimum water level (%)
    max_reservoir_level: float      # Maximum water level (%)
    ramp_rate_up: Power            # Maximum power increase rate (MW/min)
    ramp_rate_down: Power          # Maximum power decrease rate (MW/min)
    minimum_downtime: int          # Minimum offline time (minutes)
    startup_cost: Cost             # Cost of starting up (€)


# =============================================================================
# SECTION 5: CONFIGURATION AND SYSTEM PARAMETERS
# =============================================================================

@dataclass
class SystemParameters:
    """
    Physical system parameters for pumped hydro storage.
    
    Contains all technical specifications and operational
    parameters for the pumped storage facility.
    """
    discharge_power: Power      # Maximum turbine power (MW)
    charge_power: Power         # Maximum pump power (MW)
    efficiency: Efficiency      # Round-trip efficiency (0.0-1.0)
    network_charges: Price      # Network charges (€/MWh)
    max_discharge_hours: float  # Maximum full load discharge hours
    reservoir_capacity: Energy # Total energy storage capacity (MWh)


@dataclass
class EconomicParameters:
    """
    Economic and financial parameters for cost calculations.
    
    Contains financial metrics used for asset valuation
    and opportunity cost calculations.
    """
    residual_value_of_battery: Cost     # Current asset value (€)
    remaining_useful_life: float        # Remaining operational years
    planned_operating_hour: float       # Annual planned operating hours
    discount_rate: float               # Financial discount rate (%)
    inflation_rate: float              # Expected inflation rate (%)
    tax_rate: float                    # Corporate tax rate (%)


@dataclass
class AnalysisParameters:
    """
    Parameters controlling the analysis methodology.
    
    Defines the historical analysis periods and calculation
    parameters used in the flexibility cost calculations.
    """
    price_analysis_days: int           # Days for price difference analysis
    volatility_analysis_days: int      # Days for volatility calculation
    minimum_volatility: Volatility     # Minimum volatility threshold (€/MWh)
    volatility_premium_factor: float   # Volatility premium multiplier
    confidence_level: float            # Statistical confidence level (%)


# =============================================================================
# SECTION 6: CALCULATION RESULTS
# =============================================================================

@dataclass
class FlexibilityMetrics:
    """
    Key performance metrics from flexibility calculations.
    
    Summary statistics and key indicators derived from
    the complete flexibility cost analysis.
    """
    total_flexibility_cost: Cost           # Total cost of flexibility services (€)
    average_option_value: Price            # Average option value (€/MWh)
    peak_option_value: Price               # Maximum option value (€/MWh)
    total_opportunity_cost: Cost           # Total opportunity cost (€)
    total_production_cost: Cost            # Total production cost (€)
    asset_depreciation_cost: Cost          # Total asset depreciation (€)
    cost_per_mwh_flexibility: Price        # Unit cost of flexibility (€/MWh)


@dataclass
class VolatilityAnalysis:
    """
    Detailed volatility analysis results.
    
    Contains comprehensive volatility patterns and statistics
    used for option pricing and risk assessment.
    """
    hourly_volatility: Dict[str, Volatility]   # Volatility by hour of day
    daily_volatility_trend: pd.Series          # Daily volatility evolution
    peak_volatility_periods: pd.DataFrame      # High volatility time periods
    volatility_correlation: pd.DataFrame       # Cross-time correlations
    volatility_forecast_accuracy: float        # Forecast quality metric


@dataclass
class FlexibilityResults:
    """
    Complete flexibility calculation results.
    
    Comprehensive container for all results from the flexibility
    cost calculation process, ready for reporting and analysis.
    """
    # Input data
    market_data: MarketData
    adjusted_prices: PriceData
    flexibility_schedule: FlexibilitySchedule
    
    # Calculation results
    boundary_prices: BoundaryPrices
    production_costs: ProductionCosts
    option_prices: OptionPrices
    opportunity_costs: OpportunityCosts
    
    # Analysis results
    flexibility_metrics: FlexibilityMetrics
    volatility_analysis: VolatilityAnalysis
    
    # Metadata
    calculation_timestamp: datetime
    delivery_date: DeliveryDate
    analysis_parameters: AnalysisParameters


# =============================================================================
# SECTION 7: REPORTING AND EXPORT TYPES
# =============================================================================

@dataclass
class TSOReportData:
    """
    Data structure for TSO regulatory reporting.
    
    Contains all data elements required for Transmission System
    Operator regulatory compliance and transparency reporting.
    """
    # Report metadata
    delivery_date: DeliveryDate
    report_generation_date: datetime
    facility_id: str
    operator_name: str
    
    # Constants and parameters
    constants: pd.DataFrame             # System parameters and boundary prices
    system_parameters: SystemParameters
    economic_parameters: EconomicParameters
    
    # Time-series data
    opportunity_costs: pd.DataFrame     # Detailed opportunity costs by time slot
    production_costs: pd.DataFrame      # Production cost breakdown
    flexibility_schedule: pd.DataFrame  # Operational schedule data
    
    # Summary metrics
    total_flexibility_cost: Cost
    cost_breakdown: Dict[str, Cost]


@dataclass
class ExportConfig:
    """
    Configuration for data export and reporting.
    
    Controls what data gets exported and in what format
    for different stakeholders and regulatory requirements.
    """
    # Output paths
    output_path: Optional[Path]
    tso_report_path: Optional[Path]
    detailed_analysis_path: Optional[Path]
    
    # Export options
    export_tso_report: bool = True
    export_detailed_costs: bool = False
    export_market_analysis: bool = False
    export_volatility_analysis: bool = False
    include_debug_data: bool = False
    
    # Format options
    decimal_precision: int = 2
    use_german_labels: bool = True
    include_formulas: bool = False


@dataclass
class ValidationResults:
    """
    Results from data validation and quality checks.
    
    Contains validation status and any issues found
    during the calculation process.
    """
    is_valid: bool
    validation_errors: list[str]
    validation_warnings: list[str]
    data_quality_score: float          # 0.0-1.0 quality metric
    missing_data_periods: pd.DataFrame  # Time periods with missing data
    outlier_prices: pd.DataFrame        # Detected price outliers
    consistency_checks: Dict[str, bool]  # Various consistency validations


@dataclass
class CalculationContext:
    """
    Context information for the flexibility calculation.
    
    Provides metadata and configuration context for
    traceability and reproducibility of calculations.
    """
    calculation_id: str
    user_id: Optional[str]
    configuration_hash: str             # Hash of input configuration
    software_version: str
    calculation_start_time: datetime
    calculation_end_time: Optional[datetime]
    computation_time_seconds: Optional[float]
    
    # Input file metadata
    prices_file_path: Path
    prices_file_modified: datetime
    schedule_file_path: Path
    schedule_file_modified: datetime
    
    # Calculation parameters used
    system_parameters: SystemParameters
    economic_parameters: EconomicParameters
    analysis_parameters: AnalysisParameters


@dataclass
class FlexibilityParameters:
    """Parameters for flexibility cost calculation."""
    
    # Plant specifications
    discharge_power: Power         # Maximum discharge power (MW)
    charge_power: Power           # Maximum charge power (MW)
    efficiency: float             # Round-trip efficiency (0-1)
    network_charges: Price        # Network charges (€/MWh)
    max_discharge_hours: float    # Maximum full load discharge hours
    
    # Financial parameters
    residual_value_of_battery: float    # Battery residual value (€)
    remaining_useful_life: float        # Remaining useful life (years)
    planned_operating_hour: float       # Planned operating hours per year 