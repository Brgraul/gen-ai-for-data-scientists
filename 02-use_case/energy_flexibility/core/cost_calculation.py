"""
Cost calculation functions for energy flexibility cost calculations.

This module provides comprehensive cost calculation capabilities for pumped hydro
storage systems, including option pricing, production costs, and opportunity costs.
"""

import pandas as pd
import numpy as np
from typing import Optional, Tuple, List, Dict
from pathlib import Path
from .math_utils import norm_cdf, norm_pdf

from .models import (
    Price, Power, Energy, Cost, Efficiency, Volatility,
    DeliveryDate, TimeSlot, OptionPriceSeries, MarketPriceSeries,
    MarketData, PriceData, VolatilityData, OptionPrices, ProductionCosts,
    AssetValue, LifetimeYears, OperatingHours
)

def calculate_option_prices(
    market_data_df: pd.DataFrame, 
    charging_strike_price: Price, 
    discharging_strike_price: Price, 
    historical_volatilities: pd.Series, 
    day_ahead_prices: pd.Series, 
    expected_intraday_prices: pd.Series
) -> pd.DataFrame:
    """
    Calculate Black-Scholes flexibility option prices for energy storage flexibility services.
    
    Args:
        market_data_df: Market price data DataFrame
        charging_strike_price: Strike price for charging operations (€/MWh)
        discharging_strike_price: Strike price for discharging operations (€/MWh)
        historical_volatilities: Historical price volatility for each time interval
        day_ahead_prices: Day-ahead market prices (€/MWh)
        expected_intraday_prices: Expected intraday market prices (€/MWh)
    
    Returns:
        DataFrame with calculated flexibility option prices:
        - standard_deviation: Market volatility per time interval
        - charge_option_price: Charging flexibility option value (€/MWh)
        - discharge_option_price: Discharging flexibility option value (€/MWh)
    """
    # Ensure all series have consistent indices by using values only
    # This fixes the broadcasting issue when historical_volatilities has a time-based string index
    current_volatility = historical_volatilities.values
    current_volatility = np.clip(current_volatility, 0.01, None)  # Set minimum volatility threshold
    
    day_ahead_values = day_ahead_prices.values
    expected_intraday_values = expected_intraday_prices.values
    
    # Calculate Black-Scholes d parameters for both operations
    charging_moneyness_parameter = (expected_intraday_values - charging_strike_price) / current_volatility
    discharging_moneyness_parameter = (expected_intraday_values - discharging_strike_price) / current_volatility

    # Vectorized option value calculations
    # Create masks for call vs put options
    charging_call_mask = charging_strike_price > day_ahead_values
    discharging_call_mask = discharging_strike_price > day_ahead_values
    
    # Calculate charging option values
    charging_call_values = current_volatility * (
        charging_moneyness_parameter * norm_cdf(charging_moneyness_parameter) + 
        norm_pdf(charging_moneyness_parameter)
    )
    charging_put_values = current_volatility * (
        norm_pdf(charging_moneyness_parameter) - 
        charging_moneyness_parameter * norm_cdf(-charging_moneyness_parameter)
    )
    charging_option_value = np.where(charging_call_mask, charging_call_values, charging_put_values)
    
    # Calculate discharging option values
    discharging_call_values = current_volatility * (
        discharging_moneyness_parameter * norm_cdf(discharging_moneyness_parameter) + 
        norm_pdf(discharging_moneyness_parameter)
    )
    discharging_put_values = current_volatility * (
        norm_pdf(discharging_moneyness_parameter) - 
        discharging_moneyness_parameter * norm_cdf(-discharging_moneyness_parameter)
    )
    discharging_option_value = np.where(discharging_call_mask, discharging_call_values, discharging_put_values)

    # Ensure non-negative option values and add volatility premium
    charging_option_value = np.maximum(charging_option_value, 0)
    discharging_option_value = np.maximum(discharging_option_value, 0)
    
    # Add volatility premium to represent time value
    volatility_premium = current_volatility * 0.8
    charging_option_value += volatility_premium
    discharging_option_value += volatility_premium

    # Update DataFrame with calculated values
    market_data_df["standard_deviation"] = current_volatility
    market_data_df['charge_option_price'] = charging_option_value
    market_data_df['discharge_option_price'] = discharging_option_value

    return market_data_df


def create_option_prices(
    market_data_df: pd.DataFrame, 
    charging_strike_price: Price, 
    discharging_strike_price: Price, 
    historical_volatilities: pd.Series, 
    day_ahead_prices: pd.Series, 
    expected_intraday_prices: pd.Series
) -> OptionPrices:
    """
    Create structured OptionPrices object with Black-Scholes flexibility option values.
    
    Wrapper function that returns flexibility option prices in a structured format
    for TSO billing purposes.
    """
    price_data_with_options = calculate_option_prices(
        market_data_df, charging_strike_price, discharging_strike_price, historical_volatilities, day_ahead_prices, expected_intraday_prices
    )
    
    return OptionPrices(
        data=price_data_with_options,
        charge_option_price=price_data_with_options['charge_option_price'],
        discharge_option_price=price_data_with_options['discharge_option_price'],
        standard_deviation=price_data_with_options['standard_deviation'],
        volatility_premium=price_data_with_options['standard_deviation'] * 0.8  # Premium factor
    )


# Function to calculate flexibility lost and production cost
# This is the point of difference to vereinfacht version of the code (only point of difference)
def calculate_production_flexibility_cost(
    operational_schedule_data: pd.DataFrame,
    max_discharge_power_mw: Power,
    max_charge_power_mw: Power,
    discharge_option_price: OptionPriceSeries,
    charge_option_price: OptionPriceSeries,
    increase_discharge_price: Price,
    decrease_discharge_price: Price,
    decrease_charge_price: Price,
    increase_charge_price: Price
) -> pd.DataFrame:
    """
    Calculate power plant operator's costs when TSO requests redispatch operations.
    
    Computes two types of costs the operator incurs:
    1. Production costs: Direct costs of changing power output as requested by TSO
    2. Opportunity costs: Lost revenue from blocked capacity that cannot be used for market operations
    
    These costs are what the operator should invoice to the TSO for redispatch services.
    
    Args:
        operational_schedule_data: Power plant operational schedule with TSO redispatch requests
        max_discharge_power_mw: Plant's maximum discharge capacity
        max_charge_power_mw: Plant's maximum charge capacity
        discharge_option_price: Discharge flexibility option price per MWh 
        charge_option_price: Charge flexibility option price per MWh
        increase_discharge_price: Cost to increase discharge operations (€/MWh)
        decrease_discharge_price: Cost to decrease discharge operations (€/MWh)
        decrease_charge_price: Cost to decrease charge operations (€/MWh)
        increase_charge_price: Cost to increase charge operations (€/MWh)
    
    Returns:
        DataFrame with operator's costs to invoice TSO:
        - blocked_turbine_capacity_mw: Discharge capacity blocked by redispatch
        - blocked_pump_capacity_mw: Charge capacity blocked by redispatch
        - turbine_opportunity_cost_euro: Lost discharge revenue per 15-min
        - pump_opportunity_cost_euro: Lost charge revenue per 15-min
        - turbine_production_cost_euro: Direct discharge operation costs per 15-min
        - pump_production_cost_euro: Direct charge operation costs per 15-min
    """
    # Extract series for vectorized operations
    planned_power_mw = operational_schedule_data['Pt']
    redispatch_adjustment_mw = operational_schedule_data['Prd']
    adjusted_power_mw = operational_schedule_data['Pnew']
    redispatch_type = operational_schedule_data['RedispatchType']
    positive_reserved_capacity_mw = operational_schedule_data["pos_vorgehaltene_leistung"]
    negative_reserved_capacity_mw = operational_schedule_data["neg_vorgehaltene_leistung"]
    max_discharge_capacity_mw = operational_schedule_data["Pmax"]
    max_charge_capacity_mw = operational_schedule_data["Vmax"]

    # Initialize result arrays
    blocked_turbine_capacity_mw = np.zeros(len(operational_schedule_data))
    blocked_pump_capacity_mw = np.zeros(len(operational_schedule_data))
    turbine_production_cost_euro = np.zeros(len(operational_schedule_data))
    pump_production_cost_euro = np.zeros(len(operational_schedule_data))

    # Create boolean masks for different redispatch scenarios
    keine_mask = redispatch_type == "keine"
    einseitig_mask = redispatch_type == "einseitig"
    beidseitig_mask = redispatch_type == "beidseitig"
    
    # Negative redispatch scenarios
    neg_redispatch = redispatch_adjustment_mw < 0
    pos_redispatch = redispatch_adjustment_mw > 0
    
    # Power operation scenarios
    planned_pos_adjusted_pos = (planned_power_mw > 0) & (adjusted_power_mw > 0)
    planned_pos_adjusted_neg = (planned_power_mw > 0) & (adjusted_power_mw < 0)
    planned_neg_adjusted_neg = (planned_power_mw <= 0) & (adjusted_power_mw < 0)
    planned_pos_adjusted_pos_ge = (planned_power_mw >= 0) & (adjusted_power_mw > 0)
    planned_neg_adjusted_pos = (planned_power_mw < 0) & (adjusted_power_mw > 0)

    # EINSEITIG redispatch logic
    # Negative redispatch cases
    mask_eins_neg_dec_disch = einseitig_mask & neg_redispatch & planned_pos_adjusted_pos
    blocked_turbine_capacity_mw = np.where(
        mask_eins_neg_dec_disch,
        max_discharge_capacity_mw - positive_reserved_capacity_mw - np.abs(planned_power_mw + redispatch_adjustment_mw),
        blocked_turbine_capacity_mw
    )
    turbine_production_cost_euro = np.where(
        mask_eins_neg_dec_disch,
        -decrease_discharge_price * np.abs(redispatch_adjustment_mw) * 0.25,
        turbine_production_cost_euro
    )

    mask_eins_neg_disch_to_char = einseitig_mask & neg_redispatch & planned_pos_adjusted_neg
    blocked_turbine_capacity_mw = np.where(
        mask_eins_neg_disch_to_char,
        max_discharge_capacity_mw - positive_reserved_capacity_mw,
        blocked_turbine_capacity_mw
    )
    blocked_pump_capacity_mw = np.where(
        mask_eins_neg_disch_to_char,
        np.abs(adjusted_power_mw),
        blocked_pump_capacity_mw
    )
    turbine_production_cost_euro = np.where(
        mask_eins_neg_disch_to_char,
        -decrease_discharge_price * np.abs(planned_power_mw) * 0.25,
        turbine_production_cost_euro
    )
    pump_production_cost_euro = np.where(
        mask_eins_neg_disch_to_char,
        -increase_charge_price * np.abs(adjusted_power_mw) * 0.25,
        pump_production_cost_euro
    )

    mask_eins_neg_inc_char = einseitig_mask & neg_redispatch & planned_neg_adjusted_neg
    blocked_turbine_capacity_mw = np.where(
        mask_eins_neg_inc_char,
        max_discharge_capacity_mw - positive_reserved_capacity_mw,
        blocked_turbine_capacity_mw
    )
    blocked_pump_capacity_mw = np.where(
        mask_eins_neg_inc_char,
        np.abs(planned_power_mw + redispatch_adjustment_mw),
        blocked_pump_capacity_mw
    )
    pump_production_cost_euro = np.where(
        mask_eins_neg_inc_char,
        -increase_charge_price * np.abs(redispatch_adjustment_mw) * 0.25,
        pump_production_cost_euro
    )

    # Positive redispatch cases
    mask_eins_pos_inc_disch = einseitig_mask & pos_redispatch & planned_pos_adjusted_pos_ge
    blocked_turbine_capacity_mw = np.where(
        mask_eins_pos_inc_disch,
        planned_power_mw + redispatch_adjustment_mw,
        blocked_turbine_capacity_mw
    )
    blocked_pump_capacity_mw = np.where(
        mask_eins_pos_inc_disch,
        max_charge_capacity_mw - negative_reserved_capacity_mw,
        blocked_pump_capacity_mw
    )
    turbine_production_cost_euro = np.where(
        mask_eins_pos_inc_disch,
        increase_discharge_price * np.abs(redispatch_adjustment_mw) * 0.25,
        turbine_production_cost_euro
    )

    mask_eins_pos_char_to_disch = einseitig_mask & pos_redispatch & planned_neg_adjusted_pos
    blocked_turbine_capacity_mw = np.where(
        mask_eins_pos_char_to_disch,
        np.abs(adjusted_power_mw),
        blocked_turbine_capacity_mw
    )
    blocked_pump_capacity_mw = np.where(
        mask_eins_pos_char_to_disch,
        max_charge_capacity_mw - negative_reserved_capacity_mw,
        blocked_pump_capacity_mw
    )
    pump_production_cost_euro = np.where(
        mask_eins_pos_char_to_disch,
        decrease_charge_price * np.abs(planned_power_mw) * 0.25,
        pump_production_cost_euro
    )
    turbine_production_cost_euro = np.where(
        mask_eins_pos_char_to_disch,
        increase_discharge_price * np.abs(adjusted_power_mw) * 0.25,
        turbine_production_cost_euro
    )

    mask_eins_pos_dec_char = einseitig_mask & pos_redispatch & (planned_power_mw < 0) & (adjusted_power_mw < 0)
    blocked_pump_capacity_mw = np.where(
        mask_eins_pos_dec_char,
        max_charge_capacity_mw - negative_reserved_capacity_mw - np.abs(planned_power_mw + redispatch_adjustment_mw),
        blocked_pump_capacity_mw
    )
    pump_production_cost_euro = np.where(
        mask_eins_pos_dec_char,
        decrease_charge_price * np.abs(redispatch_adjustment_mw) * 0.25,
        pump_production_cost_euro
    )

    # BEIDSEITIG redispatch logic
    blocked_turbine_capacity_mw = np.where(
        beidseitig_mask,
        max_discharge_capacity_mw - positive_reserved_capacity_mw,
        blocked_turbine_capacity_mw
    )
    blocked_pump_capacity_mw = np.where(
        beidseitig_mask,
        max_charge_capacity_mw - negative_reserved_capacity_mw,
        blocked_pump_capacity_mw
    )

    # Production costs for beidseitig - negative redispatch
    mask_beid_neg_dec_disch = beidseitig_mask & neg_redispatch & planned_pos_adjusted_pos
    turbine_production_cost_euro = np.where(
        mask_beid_neg_dec_disch,
        -decrease_discharge_price * np.abs(redispatch_adjustment_mw) * 0.25,
        turbine_production_cost_euro
    )

    mask_beid_neg_disch_to_char = beidseitig_mask & neg_redispatch & planned_pos_adjusted_neg
    turbine_production_cost_euro = np.where(
        mask_beid_neg_disch_to_char,
        -decrease_discharge_price * np.abs(planned_power_mw) * 0.25,
        turbine_production_cost_euro
    )
    pump_production_cost_euro = np.where(
        mask_beid_neg_disch_to_char,
        -increase_charge_price * np.abs(adjusted_power_mw) * 0.25,
        pump_production_cost_euro
    )

    mask_beid_neg_inc_char = beidseitig_mask & neg_redispatch & planned_neg_adjusted_neg
    pump_production_cost_euro = np.where(
        mask_beid_neg_inc_char,
        -increase_charge_price * np.abs(redispatch_adjustment_mw) * 0.25,
        pump_production_cost_euro
    )

    # Production costs for beidseitig - positive redispatch
    mask_beid_pos_inc_disch = beidseitig_mask & pos_redispatch & planned_pos_adjusted_pos_ge
    turbine_production_cost_euro = np.where(
        mask_beid_pos_inc_disch,
        increase_discharge_price * np.abs(redispatch_adjustment_mw) * 0.25,
        turbine_production_cost_euro
    )

    mask_beid_pos_char_to_disch = beidseitig_mask & pos_redispatch & planned_neg_adjusted_pos
    pump_production_cost_euro = np.where(
        mask_beid_pos_char_to_disch,
        decrease_charge_price * np.abs(planned_power_mw) * 0.25,
        pump_production_cost_euro
    )
    turbine_production_cost_euro = np.where(
        mask_beid_pos_char_to_disch,
        increase_discharge_price * np.abs(adjusted_power_mw) * 0.25,
        turbine_production_cost_euro
    )

    mask_beid_pos_dec_char = beidseitig_mask & pos_redispatch & (planned_power_mw < 0) & (adjusted_power_mw < 0)
    pump_production_cost_euro = np.where(
        mask_beid_pos_dec_char,
        decrease_charge_price * np.abs(redispatch_adjustment_mw) * 0.25,
        pump_production_cost_euro
    )

    # Ensure non-negative blocked capacities
    blocked_turbine_capacity_mw = np.maximum(blocked_turbine_capacity_mw, 0)
    blocked_pump_capacity_mw = np.maximum(blocked_pump_capacity_mw, 0)
    
    # Calculate opportunity costs
    turbine_opportunity_cost_euro = blocked_turbine_capacity_mw * discharge_option_price.values * 0.25
    pump_opportunity_cost_euro = blocked_pump_capacity_mw * charge_option_price.values * 0.25
    
    # Store vectorized results in DataFrame
    operational_schedule_data['Pgesperrt_turb (MW)'] = blocked_turbine_capacity_mw
    operational_schedule_data['Pgesperrt_pump (MW)'] = blocked_pump_capacity_mw
    operational_schedule_data['Entgangener Deckungsbeitrag für Turbinenbetrieb [Opportunity cost turbine] (euro)'] = turbine_opportunity_cost_euro
    operational_schedule_data['Entgangener Deckungsbeitrag für Pumpbetrieb [Opportunity cost pump] (euro)'] = pump_opportunity_cost_euro
    operational_schedule_data['Erzeugungsauslage [production cost turbine] (euro)'] = turbine_production_cost_euro
    operational_schedule_data['Erzeugungsauslage[production cost pump] (euro)'] = pump_production_cost_euro

    return operational_schedule_data

# Function to calculate lost flexibility (opportunity cost)
def calculate_deprecation_cost(
    operational_schedule_data: pd.DataFrame,
    max_discharge_power_mw: Power,
    max_charge_power_mw: Power,
    residual_value_of_battery: AssetValue,
    remaining_useful_life: LifetimeYears,
    planned_annual_operating_hours: OperatingHours,
    average_pump_operation_prices: Price,
    average_turbine_operation_prices: Price,
    day_ahead_market_prices: MarketPriceSeries
) -> pd.DataFrame:
    """
    Calculate power plant operator's asset depreciation costs from TSO redispatch constraints.
    
    Computes additional wear-and-tear costs when TSO redispatch operations limit the plant's
    flexibility and force suboptimal asset utilization. This represents accelerated depreciation
    that the operator should invoice to the TSO.
    
    Args:
        operational_schedule_data: Power plant operational schedule with TSO redispatch constraints
        max_discharge_power_mw: Plant's maximum discharge capacity
        max_charge_power_mw: Plant's maximum charge capacity
        residual_value_of_battery: Current asset value (€)
        remaining_useful_life: Remaining operational lifetime (years)
        planned_annual_operating_hours: Annual operating hours
        average_pump_operation_prices: Average charge operation prices (€/MWh)
        average_turbine_operation_prices: Average discharge operation prices (€/MWh)
        day_ahead_market_prices: Day-ahead prices for each time interval (€/MWh)
    
    Returns:
        DataFrame with additional column:
        - asset_depreciation_cost_euro: Asset depreciation cost per 15-min interval to invoice TSO
    """
    # Calculate constants
    strike_price = (average_pump_operation_prices + average_turbine_operation_prices) / 2
    hourly_depreciation_rate = residual_value_of_battery / (remaining_useful_life * planned_annual_operating_hours)
   
    # Extract series for vectorized operations
    planned_power_mw = operational_schedule_data['Pt']
    redispatch_adjustment_mw = operational_schedule_data['Prd']
    adjusted_power_mw = operational_schedule_data['Pnew']
    redispatch_type = operational_schedule_data['RedispatchType']
    blocked_turbine_capacity_mw = operational_schedule_data['Pgesperrt_turb (MW)']
    blocked_pump_capacity_mw = operational_schedule_data['Pgesperrt_pump (MW)']
    positive_reserved_capacity_mw = operational_schedule_data["pos_vorgehaltene_leistung"]
    negative_reserved_capacity_mw = operational_schedule_data["neg_vorgehaltene_leistung"]
    max_discharge_capacity_mw = operational_schedule_data["Pmax"]
    max_charge_capacity_mw = operational_schedule_data["Vmax"]

    # Vectorized calculations
    utilized_battery_capacity_mw = (
        np.abs(planned_power_mw) + 
        np.maximum(0, positive_reserved_capacity_mw - np.maximum(0, -planned_power_mw)) + 
        np.maximum(0, negative_reserved_capacity_mw - np.maximum(0, planned_power_mw))
    )
    total_blocked_capacity_mw = blocked_turbine_capacity_mw + blocked_pump_capacity_mw

    # Initialize depreciation factor array
    depreciation_factor = np.zeros(len(operational_schedule_data))

    # Create boolean masks for different scenarios
    keine_mask = redispatch_type == "keine"
    neg_redispatch = redispatch_adjustment_mw < 0
    pos_redispatch = redispatch_adjustment_mw > 0
    
    # Power operation scenarios
    planned_pos_adjusted_pos = (planned_power_mw > 0) & (adjusted_power_mw > 0)
    planned_pos_adjusted_neg = (planned_power_mw > 0) & (adjusted_power_mw < 0)
    planned_neg_adjusted_neg = (planned_power_mw <= 0) & (adjusted_power_mw < 0)
    planned_pos_adjusted_pos_ge = (planned_power_mw >= 0) & (adjusted_power_mw > 0)
    planned_neg_adjusted_pos = (planned_power_mw < 0) & (adjusted_power_mw > 0)
    planned_neg_adjusted_neg_strict = (planned_power_mw < 0) & (adjusted_power_mw < 0)

    # Price condition masks
    quotierung_neu_neg = day_ahead_market_prices >= strike_price * 0.9
    quotierung_neu_pos = day_ahead_market_prices < strike_price * 1.1

    # Negative redispatch scenarios
    # Decreasing discharge
    mask_neg_dec_disch = ~keine_mask & neg_redispatch & planned_pos_adjusted_pos
    depreciation_factor = np.where(
        mask_neg_dec_disch & quotierung_neu_neg,
        total_blocked_capacity_mw / (total_blocked_capacity_mw + utilized_battery_capacity_mw),
        depreciation_factor
    )

    # Discharge to charge
    mask_neg_disch_to_char = ~keine_mask & neg_redispatch & planned_pos_adjusted_neg
    depreciation_factor = np.where(
        mask_neg_disch_to_char & quotierung_neu_neg,
        total_blocked_capacity_mw / (total_blocked_capacity_mw + utilized_battery_capacity_mw),
        depreciation_factor
    )
    depreciation_factor = np.where(
        mask_neg_disch_to_char & ~quotierung_neu_neg,
        np.abs(adjusted_power_mw) / max_charge_capacity_mw,
        depreciation_factor
    )

    # Increasing charge
    mask_neg_inc_char = ~keine_mask & neg_redispatch & planned_neg_adjusted_neg
    depreciation_factor = np.where(
        mask_neg_inc_char & quotierung_neu_neg,
        total_blocked_capacity_mw / (total_blocked_capacity_mw + utilized_battery_capacity_mw),
        depreciation_factor
    )
    depreciation_factor = np.where(
        mask_neg_inc_char & ~quotierung_neu_neg,
        np.abs(redispatch_adjustment_mw) / max_charge_capacity_mw,
        depreciation_factor
    )

    # Positive redispatch scenarios
    # Increasing discharge
    mask_pos_inc_disch = ~keine_mask & pos_redispatch & planned_pos_adjusted_pos_ge
    depreciation_factor = np.where(
        mask_pos_inc_disch & quotierung_neu_pos,
        total_blocked_capacity_mw / (total_blocked_capacity_mw + utilized_battery_capacity_mw),
        depreciation_factor
    )
    depreciation_factor = np.where(
        mask_pos_inc_disch & ~quotierung_neu_pos,
        np.abs(redispatch_adjustment_mw) / max_discharge_power_mw,
        depreciation_factor
    )

    # Charge to discharge
    mask_pos_char_to_disch = ~keine_mask & pos_redispatch & planned_neg_adjusted_pos
    depreciation_factor = np.where(
        mask_pos_char_to_disch & quotierung_neu_pos,
        total_blocked_capacity_mw / (total_blocked_capacity_mw + utilized_battery_capacity_mw),
        depreciation_factor
    )
    depreciation_factor = np.where(
        mask_pos_char_to_disch & ~quotierung_neu_pos,
        np.abs(adjusted_power_mw) / max_discharge_power_mw,
        depreciation_factor
    )

    # Decreasing charge
    mask_pos_dec_char = ~keine_mask & pos_redispatch & planned_neg_adjusted_neg_strict
    depreciation_factor = np.where(
        mask_pos_dec_char & quotierung_neu_pos,
        total_blocked_capacity_mw / (total_blocked_capacity_mw + utilized_battery_capacity_mw),
        depreciation_factor
    )
    # For positive decreasing charge without quotierung_neu_pos, depreciation_factor remains 0 (already initialized)

    # Calculate final depreciation cost
    asset_depreciation_cost_euro = depreciation_factor * hourly_depreciation_rate * 0.25
    
    # Store result in DataFrame
    operational_schedule_data['Anteiliger Werteverbrauch [value_lost] (euro)'] = asset_depreciation_cost_euro

    return operational_schedule_data

def aggregate_costs(operational_schedule_data: pd.DataFrame, excel_export_path: Optional[str] = None) -> pd.DataFrame:
    """
    Aggregate all power plant operator costs into final TSO invoice amounts.
    
    Combines production costs, opportunity costs, and asset depreciation costs
    into total amounts the operator should bill the TSO for redispatch services.
    
    Args:
        operational_schedule_data: Data with all calculated cost components
        excel_export_path: Optional path to export cost summary to Excel
    
    Returns:
        DataFrame with final TSO billing amounts:
        - total_production_costs_euro: Direct operational costs per 15-min
        - total_opportunity_costs_euro: Lost revenue costs per 15-min  
        - max_opportunity_vs_depreciation_euro: Higher of opportunity or depreciation costs
        - total_costs_per_timeslot_euro: Final amount to invoice TSO per 15-min
    """
    # Sum production costs for both operations
    operational_schedule_data["total_production_costs_euro"] = (
        operational_schedule_data['Erzeugungsauslage [production cost turbine] (euro)'] +
        operational_schedule_data['Erzeugungsauslage[production cost pump] (euro)']
    )

    # Sum opportunity costs for both operations
    operational_schedule_data["total_opportunity_costs_euro"] = (
        operational_schedule_data['Entgangener Deckungsbeitrag für Turbinenbetrieb [Opportunity cost turbine] (euro)'] +
        operational_schedule_data['Entgangener Deckungsbeitrag für Pumpbetrieb [Opportunity cost pump] (euro)']
    )

    # Take maximum between opportunity cost and asset depreciation
    operational_schedule_data["max_opportunity_vs_depreciation_euro"] = operational_schedule_data[[
        "total_opportunity_costs_euro",
        "Anteiliger Werteverbrauch [value_lost] (euro)"
    ]].max(axis=1)

    # Calculate total costs per time slot
    operational_schedule_data["total_costs_per_timeslot_euro"] = (
        operational_schedule_data["total_production_costs_euro"] +
        operational_schedule_data["max_opportunity_vs_depreciation_euro"]
    )

    # Export results if path provided
    if excel_export_path:
        # Create output directory if it doesn't exist
        output_path = Path(excel_export_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        export_column_names = [
            'time', 'Pt', 'Prd', 'Pnew', 'RedispatchType',
            'Pgesperrt_turb (MW)', 'Pgesperrt_pump (MW)',
            'Entgangener Deckungsbeitrag für Turbinenbetrieb [Opportunity cost turbine] (euro)',
            'Entgangener Deckungsbeitrag für Pumpbetrieb [Opportunity cost pump] (euro)',
            'Erzeugungsauslage [production cost turbine] (euro)',
            'Erzeugungsauslage[production cost pump] (euro)',
            'Anteiliger Werteverbrauch [value_lost] (euro)',
            'total_production_costs_euro',
            'total_opportunity_costs_euro',
            'max_opportunity_vs_depreciation_euro',
            'total_costs_per_timeslot_euro'
        ]
        operational_schedule_data[export_column_names].to_excel(excel_export_path, index=False)

    return operational_schedule_data 