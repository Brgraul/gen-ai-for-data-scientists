"""
Cost calculation functions for energy flexibility cost calculations.

This module provides comprehensive cost calculation capabilities for pumped hydro
storage systems, including option pricing, production costs, and opportunity costs.
"""

import pandas as pd
import numpy as np
from typing import Optional, Tuple, List, Dict
from pathlib import Path
from scipy.stats import norm

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
    Calculate Black-Scholes option values for flexibility services offered to TSO.
    
    Calculates what the power plant operator should charge the TSO for providing 
    charging/discharging flexibility options.
    
    Args:
        market_data_df: Time series price data framework
        charging_strike_price: Price threshold for charging flexibility (€/MWh)
        discharging_strike_price: Price threshold for discharging flexibility (€/MWh)
        historical_volatilities: Price volatility for each 15-min interval (€/MWh)
        day_ahead_prices: Day-ahead market prices (€/MWh)
        expected_intraday_prices: Predicted intraday prices (€/MWh)
    
    Returns:
        DataFrame with option values the operator should charge TSO:
        - charge_option_price: Charging flexibility option value (€/MWh)
        - discharge_option_price: Discharging flexibility option value (€/MWh)
    """
    # Initialize result containers
    charging_option_prices = []
    discharging_option_prices = []
    time_interval_volatilities = []

    # Process each time interval
    for time_interval_index, time_interval_data in market_data_df.iterrows():
        # Set minimum volatility threshold
        current_volatility = max(historical_volatilities.iloc[time_interval_index], 0.01)
        
        # Calculate Black-Scholes d parameter for both operations
        charging_moneyness_parameter = (expected_intraday_prices.iloc[time_interval_index] - charging_strike_price) / current_volatility
        discharging_moneyness_parameter = (expected_intraday_prices.iloc[time_interval_index] - discharging_strike_price) / current_volatility

        # Calculate charging option value based on price comparison
        if charging_strike_price > day_ahead_prices.iloc[time_interval_index]:
            charging_option_value = current_volatility * (charging_moneyness_parameter * norm.cdf(charging_moneyness_parameter) + norm.pdf(charging_moneyness_parameter))  # Call option
        else:
            charging_option_value = current_volatility * (norm.pdf(charging_moneyness_parameter) - charging_moneyness_parameter * norm.cdf(-charging_moneyness_parameter))  # Put option
        
        # Calculate discharging option value based on price comparison
        if discharging_strike_price > day_ahead_prices.iloc[time_interval_index]:
            discharging_option_value = current_volatility * (discharging_moneyness_parameter * norm.cdf(discharging_moneyness_parameter) + norm.pdf(discharging_moneyness_parameter))  # Call option
        else:
            discharging_option_value = current_volatility * (norm.pdf(discharging_moneyness_parameter) - discharging_moneyness_parameter * norm.cdf(-discharging_moneyness_parameter))  # Put option

        # Ensure non-negative option values
        charging_option_value = max(charging_option_value, 0)
        discharging_option_value = max(discharging_option_value, 0)
        
        # Add volatility premium to represent time value
        volatility_premium = current_volatility * 0.8
        charging_option_value += volatility_premium
        discharging_option_value += volatility_premium

        # Store results
        charging_option_prices.append(charging_option_value)
        discharging_option_prices.append(discharging_option_value)
        time_interval_volatilities.append(current_volatility)

    # Update DataFrame with calculated values
    market_data_df["standard_deviation"] = time_interval_volatilities
    market_data_df['charge_option_price'] = charging_option_prices
    market_data_df['discharge_option_price'] = discharging_option_prices

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
    # Loop through the rows of the DataFrame (iterating over each 15-minute period)
    for time_index, time_row in operational_schedule_data.iterrows():
        planned_power_mw = time_row['Pt'] 
        redispatch_adjustment_mw = time_row['Prd']  
        adjusted_power_mw = time_row['Pnew']  
        redispatch_type = time_row['RedispatchType']  
        positive_reserved_capacity_mw = time_row["pos_vorgehaltene_leistung"]
        negative_reserved_capacity_mw = time_row["neg_vorgehaltene_leistung"]
        max_discharge_capacity_mw = time_row["Pmax"]
        max_charge_capacity_mw = time_row["Vmax"]

        # Initialize blocked capacity and cost variables
        blocked_turbine_capacity_mw = 0
        blocked_pump_capacity_mw = 0
        turbine_opportunity_cost_euro = 0
        turbine_production_cost_euro = 0
        pump_opportunity_cost_euro = 0
        pump_production_cost_euro = 0
        

        # Check the redispatch type (einseitig, beidseitig, keine)
        if redispatch_type == "keine":
            # If "keine", no flexibility is lost
            pass

        elif redispatch_type == "einseitig":
            # Limited either by higher or lower bound.
            # If "einseitig", apply the original logic
            if redispatch_adjustment_mw < 0:  # Negative Redispatch (discharge to charge logic)
                if planned_power_mw > 0 and adjusted_power_mw > 0:  # Decreasing discharge
                    blocked_turbine_capacity_mw = max_discharge_capacity_mw - positive_reserved_capacity_mw - abs(planned_power_mw + redispatch_adjustment_mw)
                    blocked_pump_capacity_mw = 0 
                    turbine_production_cost_euro = -decrease_discharge_price*abs(redispatch_adjustment_mw)*0.25
                elif planned_power_mw > 0 and adjusted_power_mw < 0:  # Discharge to charge
                    blocked_turbine_capacity_mw = max_discharge_capacity_mw - positive_reserved_capacity_mw
                    blocked_pump_capacity_mw = abs(adjusted_power_mw)
                    turbine_production_cost_euro = -decrease_discharge_price*abs(planned_power_mw)*0.25
                    pump_production_cost_euro = -increase_charge_price*abs(adjusted_power_mw)*0.25
                elif planned_power_mw <= 0 and adjusted_power_mw < 0:  # Increasing charge
                    blocked_turbine_capacity_mw = max_discharge_capacity_mw - positive_reserved_capacity_mw
                    blocked_pump_capacity_mw = abs(planned_power_mw + redispatch_adjustment_mw)
                    pump_production_cost_euro = -increase_charge_price*abs(redispatch_adjustment_mw)*0.25
                


            elif redispatch_adjustment_mw > 0:  # Positive Redispatch (charge to discharge logic)
                if planned_power_mw >= 0 and adjusted_power_mw > 0:  # Increasing discharge
                    blocked_turbine_capacity_mw = planned_power_mw + redispatch_adjustment_mw 
                    blocked_pump_capacity_mw = max_charge_capacity_mw - negative_reserved_capacity_mw 
                    turbine_production_cost_euro = increase_discharge_price*abs(redispatch_adjustment_mw)*0.25
                elif planned_power_mw < 0 and adjusted_power_mw > 0:  # Charge to discharge
                    blocked_turbine_capacity_mw = abs(adjusted_power_mw)
                    blocked_pump_capacity_mw = max_charge_capacity_mw - negative_reserved_capacity_mw
                    pump_production_cost_euro = decrease_charge_price*abs(planned_power_mw)*0.25
                    turbine_production_cost_euro = increase_discharge_price*abs(adjusted_power_mw)*0.25
                elif planned_power_mw < 0 and adjusted_power_mw < 0:  # Decreasing charge
                    blocked_turbine_capacity_mw = 0
                    blocked_pump_capacity_mw = max_charge_capacity_mw - negative_reserved_capacity_mw - abs(planned_power_mw + redispatch_adjustment_mw) 
                    pump_production_cost_euro = decrease_charge_price*abs(redispatch_adjustment_mw)*0.25

        elif redispatch_type == "beidseitig":
            # If "beidseitig", set turbine and pump to max values
            blocked_turbine_capacity_mw = max_discharge_capacity_mw - positive_reserved_capacity_mw
            blocked_pump_capacity_mw = max_charge_capacity_mw - negative_reserved_capacity_mw
            if redispatch_adjustment_mw < 0:  # Negative Redispatch (discharge to charge logic)
                if planned_power_mw > 0 and adjusted_power_mw > 0:  # Decreasing discharge
                    turbine_production_cost_euro = -decrease_discharge_price*abs(redispatch_adjustment_mw)*0.25
                elif planned_power_mw > 0 and adjusted_power_mw < 0:  # Discharge to charge
                    turbine_production_cost_euro = -decrease_discharge_price*abs(planned_power_mw)*0.25
                    pump_production_cost_euro = -increase_charge_price*abs(adjusted_power_mw)*0.25
                elif planned_power_mw <= 0 and adjusted_power_mw < 0:  # Increasing charge
                    pump_production_cost_euro = -increase_charge_price*abs(redispatch_adjustment_mw)*0.25

            elif redispatch_adjustment_mw > 0:  # Positive Redispatch (charge to discharge logic)
                if planned_power_mw >= 0 and adjusted_power_mw > 0:  # Increasing discharge
                    turbine_production_cost_euro = increase_discharge_price*abs(redispatch_adjustment_mw)*0.25
                elif planned_power_mw < 0 and adjusted_power_mw > 0:  # Charge to discharge
                    pump_production_cost_euro = decrease_charge_price*abs(planned_power_mw)*0.25
                    turbine_production_cost_euro = increase_discharge_price*abs(adjusted_power_mw)*0.25
                elif planned_power_mw < 0 and adjusted_power_mw < 0:  # Decreasing charge
                    pump_production_cost_euro = decrease_charge_price*abs(redispatch_adjustment_mw)*0.25
            
        if blocked_turbine_capacity_mw < 0:
            blocked_turbine_capacity_mw = 0
        
        if blocked_pump_capacity_mw < 0:
            blocked_pump_capacity_mw = 0
        
        turbine_opportunity_cost_euro = blocked_turbine_capacity_mw * discharge_option_price.iloc[time_index] * 0.25
        pump_opportunity_cost_euro = blocked_pump_capacity_mw * charge_option_price.iloc[time_index] * 0.25
        
        # Store values in DataFrame
        operational_schedule_data.loc[time_index, 'Pgesperrt_turb (MW)'] = blocked_turbine_capacity_mw
        operational_schedule_data.loc[time_index, 'Pgesperrt_pump (MW)'] = blocked_pump_capacity_mw
        operational_schedule_data.loc[time_index, 'Entgangener Deckungsbeitrag für Turbinenbetrieb [Opportunity cost turbine] (euro)'] = turbine_opportunity_cost_euro
        operational_schedule_data.loc[time_index, 'Entgangener Deckungsbeitrag für Pumpbetrieb [Opportunity cost pump] (euro)'] = pump_opportunity_cost_euro
        operational_schedule_data.loc[time_index, 'Erzeugungsauslage [production cost turbine] (euro)'] = turbine_production_cost_euro
        operational_schedule_data.loc[time_index, 'Erzeugungsauslage[production cost pump] (euro)'] = pump_production_cost_euro

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
    # Loop through the rows of the DataFrame (iterating over each 15-minute period)

    strike_price = (average_pump_operation_prices + average_turbine_operation_prices) / 2

    hourly_depreciation_rate = residual_value_of_battery / (remaining_useful_life * planned_annual_operating_hours)
   
    for time_index, time_row in operational_schedule_data.iterrows():
        planned_power_mw = time_row['Pt']  # Planned power of the battery (Column F)
        redispatch_adjustment_mw = time_row['Prd']  # Redispatch (Column G)
        adjusted_power_mw = time_row['Pnew']  # New power value (Column H)
        redispatch_type = time_row['RedispatchType']  # Redispatch type (Column I)
        blocked_turbine_capacity_mw = time_row['Pgesperrt_turb (MW)']
        blocked_pump_capacity_mw = time_row['Pgesperrt_pump (MW)']
        positive_reserved_capacity_mw = time_row["pos_vorgehaltene_leistung"]
        negative_reserved_capacity_mw = time_row["neg_vorgehaltene_leistung"]
        max_discharge_capacity_mw = time_row["Pmax"]
        max_charge_capacity_mw = time_row["Vmax"]

        utilized_battery_capacity_mw = 0
        depreciation_factor = 0
        utilized_battery_capacity_mw = abs(planned_power_mw) + max(0, positive_reserved_capacity_mw - max(0, (-1) * planned_power_mw)) + max(0, negative_reserved_capacity_mw - max(0, planned_power_mw))
        total_blocked_capacity_mw = blocked_turbine_capacity_mw + blocked_pump_capacity_mw

        # Check the redispatch type (einseitig, beidseitig, keine)
        if redispatch_type == "keine":
            # If "keine", no flexibility is lost
            pass

        else:
            if redispatch_adjustment_mw < 0:  # Negative Redispatch
                if planned_power_mw > 0 and adjusted_power_mw > 0:  # Decreasing discharge
                    if day_ahead_market_prices[time_index] >= strike_price * 0.9: # Quotierung_neu
                        depreciation_factor = total_blocked_capacity_mw / (total_blocked_capacity_mw + utilized_battery_capacity_mw)
                    else: # Quotierung_alt
                        depreciation_factor = 0
                elif planned_power_mw > 0 and adjusted_power_mw < 0:  # Discharge to charge
                    if day_ahead_market_prices[time_index] >= strike_price * 0.9: # Quotierung_neu
                        depreciation_factor = total_blocked_capacity_mw / (total_blocked_capacity_mw + utilized_battery_capacity_mw)
                    else: # Quotierung_alt
                        depreciation_factor = abs(adjusted_power_mw) / max_charge_power_mw
                    
                elif planned_power_mw <= 0 and adjusted_power_mw < 0:  # Increasing charge
                    if day_ahead_market_prices[time_index] >= strike_price * 0.9: # Quotierung_neu
                        depreciation_factor = total_blocked_capacity_mw / (total_blocked_capacity_mw + utilized_battery_capacity_mw)
                    else: # Quotierung_alt
                        depreciation_factor = abs(redispatch_adjustment_mw) / max_charge_power_mw


            elif redispatch_adjustment_mw > 0:  # Positive Redispatch
                if planned_power_mw >= 0 and adjusted_power_mw > 0:  # Increasing discharge
                    if day_ahead_market_prices[time_index] < strike_price * 1.1: # Quotierung_neu
                        depreciation_factor = total_blocked_capacity_mw / (total_blocked_capacity_mw + utilized_battery_capacity_mw)
                    else: # Quotierung_alt
                        depreciation_factor = abs(redispatch_adjustment_mw) / max_discharge_power_mw
                    
                elif planned_power_mw < 0 and adjusted_power_mw > 0:  # Charge to discharge
                    if day_ahead_market_prices[time_index] < strike_price * 1.1: # Quotierung_neu
                        depreciation_factor = total_blocked_capacity_mw / (total_blocked_capacity_mw + utilized_battery_capacity_mw)
                    else: # Quotierung_alt
                        depreciation_factor = abs(adjusted_power_mw) / max_discharge_power_mw
                    
                elif planned_power_mw < 0 and adjusted_power_mw < 0:  # Decreasing charge
                    if day_ahead_market_prices[time_index] < strike_price * 1.1: # Quotierung_neu
                        depreciation_factor = total_blocked_capacity_mw / (total_blocked_capacity_mw + utilized_battery_capacity_mw)
                    else: # Quotierung_alt
                        depreciation_factor = 0

       
        
        asset_depreciation_cost_euro = depreciation_factor * hourly_depreciation_rate * 0.25
        
        # Store values in DataFrame
        operational_schedule_data.loc[time_index, 'Anteiliger Werteverbrauch [value_lost] (euro)'] = asset_depreciation_cost_euro
        #redispatch_operations_data.loc[time_index, 'P_KWB (MW)' ] = utilized_battery_capacity_mw

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