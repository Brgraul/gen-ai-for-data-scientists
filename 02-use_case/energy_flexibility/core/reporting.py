"""
Reporting functions for TSO compliance and export functionality.

This module handles the generation of reports for Transmission System Operators (TSO)
and regulatory compliance, including data export to Excel files.
"""

import pandas as pd
from typing import Optional, Dict
from pathlib import Path

from .models import (
    TSOReportData, FlexibilitySchedule, Cost, Price, Power, 
    DeliveryDate, SystemParameters, EconomicParameters
)


def values_to_tso(
    operational_schedule_data: pd.DataFrame, 
    discharge_option_price: pd.Series, 
    charge_option_price: pd.Series, 
    discharge_power: Power, 
    charge_power: Power, 
    increase_discharge_price: Price, 
    decrease_discharge_price: Price, 
    decrease_charge_price: Price, 
    increase_charge_price: Price,  
    pump_prices: Price, 
    turbine_prices: Price, 
    residual_value_of_battery: Cost, 
    remaining_useful_life: float, 
    planned_operating_hour: float, 
    delivery_date: DeliveryDate, 
    output_to_tso: Optional[str]
) -> pd.DataFrame:
    """
    Generate TSO compliance report with calculated opportunity costs.
    
    Creates a comprehensive report that combines power plant operational data
    with calculated opportunity costs for regulatory compliance and billing.
    
    This function provides the required transparency for TSO operations by
    showing how flexibility constraints affect plant economics.
    
    Args:
        operational_schedule_data (pandas.DataFrame): Operational schedule with power availability for each time slot
        discharge_option_price (pandas.Series): Option price for discharge operations (€/MWh)
        charge_option_price (pandas.Series): Option price for charge operations (€/MWh)
        discharge_power (Power): Maximum discharge capacity (MW)
        charge_power (Power): Maximum charge capacity (MW)
        increase_discharge_price (Price): Cost of increasing discharge (€/MWh)
        decrease_discharge_price (Price): Cost of decreasing discharge (€/MWh)
        decrease_charge_price (Price): Cost of decreasing charge (€/MWh)
        increase_charge_price (Price): Cost of increasing charge (€/MWh)
        pump_prices (Price): Economic boundary price for charging (€/MWh)
        turbine_prices (Price): Economic boundary price for discharging (€/MWh)
        residual_value_of_battery (Cost): Current asset value (€)
        remaining_useful_life (float): Remaining asset lifetime (years)
        planned_operating_hour (float): Annual operating hours
        delivery_date (DeliveryDate): Date for delivery
        output_to_tso (Optional[str]): Output file path for TSO report
    
    Returns:
        pandas.DataFrame: TSO report with:
        - All input operational data
        - Calculated opportunity costs per time slot
        - Regulatory constants and parameters
        
    Side Effects:
        - Saves comprehensive TSO report to Excel file if output_to_tso is provided
        - Prints confirmation message with file path
        
    Notes:
        This function fulfills regulatory requirements for TSO transparency by providing
        detailed cost breakdowns that justify flexibility service pricing.
        
    Examples:
        >>> # Generate TSO report for regulatory compliance
        >>> tso_report = values_to_tso(
        ...     operational_schedule_data=schedule_df,
        ...     discharge_option_price=discharge_prices,
        ...     charge_option_price=charge_prices,
        ...     # ... other parameters
        ... )
        
    Regulatory Compliance:
        - Provides full cost transparency required by energy regulators
        - Supports TSO billing justification through detailed opportunity cost calculations
        - Maintains audit trail for flexibility service pricing
    
    Integration:
        This function integrates with the cost calculation pipeline to provide
        the final regulatory output. It combines:
        - operational_schedule_data DataFrame enhanced with opportunity cost columns
        - System parameters as regulatory constants
        - Calculated boundary prices and service costs
    """
    
    # Calculate value lost per hour (€/h)
    value_lost_per_hour = residual_value_of_battery / (remaining_useful_life * planned_operating_hour)

    # Constants DataFrame for export
    constants_df = pd.DataFrame({
        'Lieferungstag': [delivery_date],
        'Grenzpreis Turbine [Turbine boundary price] (euro/MWh)': [turbine_prices],
        'Grenzpreis Pumpe [Pump boundary price] (euro/MWh)': [pump_prices],
        'Erhöhung Turbine [Increase Discharge Price] (euro/MWh)': [increase_discharge_price],
        'Minderung Turbine [Decrease Discharge Price] (euro/MWh)': [decrease_discharge_price],
        'Minderung Pumpe [Decrease Charge Price] (euro/MWh) ': [decrease_charge_price],
        'Erhöhung Pumpe [Increase Charge Price] (euro/MWh) ': [increase_charge_price],
        'Anteiliger Werteverbrauch pro anrechenbare Betriebsstunde [Lost value per hour] (euro/h)': [value_lost_per_hour]
    })

    # Vectorized calculation of option prices
    Pmax = operational_schedule_data["Pmax"]
    Vmax = operational_schedule_data["Vmax"]

    # Calculate option prices using vectorized operations
    option_price_pump = charge_option_price.values * Pmax.values
    option_price_turb = discharge_option_price.values * Vmax.values

    # Store vectorized results in DataFrame
    operational_schedule_data['Entgangener Deckungsbeitrag für Pumpbetrieb [Opportunity price pump] (euro/h)'] = option_price_pump
    operational_schedule_data['Entgangener Deckungsbeitrag für Turbinenbetrieb [Opportunity price turbine] (euro/h)'] = option_price_turb
    operational_schedule_data['Entgangener Deckungsbeitrag total [Opportunity price total] (euro/h)'] = option_price_turb + option_price_pump

    # Select columns for export
    selected_columns = [
        'time', 
        'Entgangener Deckungsbeitrag für Turbinenbetrieb [Opportunity price turbine] (euro/h)', 
        'Entgangener Deckungsbeitrag für Pumpbetrieb [Opportunity price pump] (euro/h)', 
        'Entgangener Deckungsbeitrag total [Opportunity price total] (euro/h)'
    ]
    result_data = operational_schedule_data[selected_columns]

    # Write to Excel with multiple sheets only if output path is provided
    if output_to_tso is not None:
        # Create output directory if it doesn't exist
        output_path = Path(output_to_tso)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with pd.ExcelWriter(output_to_tso) as writer:
            constants_df.to_excel(writer, sheet_name='Andere Kosten', index=False)
            result_data.to_excel(writer, sheet_name='Opportunitätskosten', index=False)

        print(f"Exported TSO report to: {output_to_tso}")
    
    return operational_schedule_data 