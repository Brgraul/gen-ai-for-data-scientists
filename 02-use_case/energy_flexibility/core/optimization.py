"""
Optimization functions for economic boundary calculations and production cost pricing in pumped hydro storage operations.

This module handles the core optimization logic for determining optimal charging/discharging
schedules and calculating production costs for various TSO flexibility scenarios.
"""

import pandas as pd
import numpy as np
from typing import Tuple

from .models import BoundaryPrices, ProductionCosts, Power, Price, Energy, Efficiency

def find_optimal_boundary_prices_turbine_first(
    adjusted_prices: pd.DataFrame, 
    turbine_power: Power, 
    pump_power: Power, 
    efficiency: Efficiency, 
    congestion_network_charges: Price, 
    max_full_load_hours: float
) -> Tuple[Price, Price, Energy, Energy]:
    """
    Determines optimal economic boundary prices for pumped hydro storage using a vectorized turbine-first approach.
    
    Args:
        adjusted_prices: Intraday prices with columns:
            - adjusted_da_prices: Forecasted prices (€/MWh)
            - da_time: Timestamps
        turbine_power: Maximum discharge power capacity (MW)
        pump_power: Maximum charging power capacity (MW)
        efficiency: Round-trip energy efficiency (0.0-1.0)
        congestion_network_charges: Congestion and network charges (€/MWh)
        max_full_load_hours: Maximum full-load discharge hours
    
    Returns:
        tuple: (
            minimum_generation_price: Minimum price for profitable discharge (€/MWh),
            maximum_pumping_price: Maximum price for profitable charging (€/MWh),
            total_power_generation_energy: Total planned discharge energy (MWh),
            total_pumping_energy: Total planned charging energy (MWh)
        )
    """
    
    # Initialize energy constraints per 15-min slot
    slot_duration_h = 0.25  # 15 min slots
    turbine_energy_per_slot = turbine_power * slot_duration_h  # MWh
    pump_energy_per_slot = pump_power * slot_duration_h        # MWh
    max_total_turbine_energy = max_full_load_hours * turbine_power  # max discharge time

    # Sort slots by price to optimize profit: discharge at high prices, charge at low prices
    turbine_slots = adjusted_prices.sort_values(by='adjusted_da_prices', ascending=False).reset_index(drop=True)
    pump_slots = adjusted_prices.sort_values(by='adjusted_da_prices', ascending=True).reset_index(drop=True)

    # Vectorized approach: calculate all profitable combinations at once
    turbine_prices = turbine_slots['adjusted_da_prices'].values
    pump_prices = pump_slots['adjusted_da_prices'].values
    
    # Calculate adjusted prices for profitability check
    adjusted_turbine_prices = turbine_prices * efficiency
    adjusted_pump_prices = pump_prices + congestion_network_charges
    
    # Find maximum number of turbine slots we can use (energy constraint)
    max_turbine_slots = int(np.ceil(max_total_turbine_energy / turbine_energy_per_slot))
    max_turbine_slots = min(max_turbine_slots, len(turbine_slots))
    
    # Vectorized profitability matrix: turbine vs pump combinations
    # Broadcasting to create all possible combinations
    turbine_prices_matrix = adjusted_turbine_prices[:max_turbine_slots, np.newaxis]
    pump_prices_matrix = adjusted_pump_prices[np.newaxis, :]
    
    # Create profitability mask
    profitable_mask = turbine_prices_matrix > pump_prices_matrix
    
    # Find the optimal matching using vectorized operations
    total_power_generation_energy = Energy(0.0)
    total_pumping_energy = Energy(0.0)
    minimum_generation_price = None
    maximum_pumping_price = None
    
    # Track remaining pump capacity across slots
    pump_remaining_capacity = np.full(len(pump_slots), pump_energy_per_slot)
    
    # Process turbine slots in order (highest price first)
    for turbine_idx in range(max_turbine_slots):
        if total_power_generation_energy >= max_total_turbine_energy:
            break
            
        turbine_price = Price(turbine_prices[turbine_idx])
        required_turbine_energy = min(
            turbine_energy_per_slot, 
            max_total_turbine_energy - total_power_generation_energy
        )
        
        # Find profitable pump slots using vectorized operations
        profitable_pumps = profitable_mask[turbine_idx]
        available_capacity = pump_remaining_capacity > 1e-6
        valid_pumps = profitable_pumps & available_capacity
        
        if not np.any(valid_pumps):
            break  # No more profitable pump slots
        
        # Get valid pump indices sorted by price (lowest first)
        valid_pump_indices = np.where(valid_pumps)[0]
        
        # Match energy requirements with available pump capacity
        remaining_demand = required_turbine_energy
        
        for pump_idx in valid_pump_indices:
            if remaining_demand <= 1e-6:
                break
                
            available_pump_energy = pump_remaining_capacity[pump_idx]
            usable_turbine_energy = available_pump_energy * efficiency
            
            energy_to_discharge = min(remaining_demand, usable_turbine_energy)
            actual_pump_energy_used = energy_to_discharge / efficiency
            
            # Update totals
            total_power_generation_energy += energy_to_discharge
            total_pumping_energy += actual_pump_energy_used
            remaining_demand -= energy_to_discharge
            pump_remaining_capacity[pump_idx] -= actual_pump_energy_used
            
            # Update price thresholds
            minimum_generation_price = turbine_price
            if pump_remaining_capacity[pump_idx] <= 1e-6:
                maximum_pumping_price = Price(pump_prices[pump_idx])
        
        if remaining_demand > 1e-6:
            break  # Could not satisfy energy requirement
    
    # Handle case where no iterations occurred
    if minimum_generation_price is None:
        mean_price = adjusted_prices['adjusted_da_prices'].mean()
        fallback_pump_price = mean_price + ((mean_price * (1 - efficiency) + congestion_network_charges) / (1 + efficiency))
        fallback_turbine_price = mean_price - ((mean_price * (1 - efficiency) + congestion_network_charges) / (1 + efficiency))
        
        minimum_generation_price = Price(fallback_turbine_price)
        maximum_pumping_price = Price(fallback_pump_price)
        total_power_generation_energy = Energy(0.0)
        total_pumping_energy = Energy(0.0)

    return Price(minimum_generation_price), Price(maximum_pumping_price), total_power_generation_energy, total_pumping_energy


def create_boundary_prices(
    adjusted_prices: pd.DataFrame, 
    turbine_power: Power, 
    pump_power: Power, 
    efficiency: Efficiency, 
    congestion_network_charges: Price, 
    max_full_load_hours: float
) -> BoundaryPrices:
    """
    Create a structured BoundaryPrices object from optimization results.
    
    Args:
        adjusted_prices: Market price data
        turbine_power: Maximum discharge power capacity (MW)
        pump_power: Maximum charging power capacity (MW)
        efficiency: Round-trip energy efficiency
        congestion_network_charges: Congestion and network charges (€/MWh)
        max_full_load_hours: Maximum full-load discharge hours
        
    Returns:
        BoundaryPrices object with optimization results
    """
    turbine_price, pump_price, turbine_energy, pump_energy = find_optimal_boundary_prices_turbine_first(
        adjusted_prices, turbine_power, pump_power, efficiency, congestion_network_charges, max_full_load_hours
    )
    
    return BoundaryPrices(
        turbine_price=turbine_price,
        pump_price=pump_price,
        turbine_energy=turbine_energy,
        pump_energy=pump_energy
    )


def calculate_flexibility_cost_prices(
    adjusted_prices: pd.DataFrame, 
    congestion_network_charges: Price, 
    max_charg_price: Price, 
    min_gen_price: Price, 
    round_trip_efficiency: Efficiency
) -> Tuple[Price, Price, Price, Price]:
    """
    Calculates production cost prices for TSO flexibility services in pumped hydro storage.
    
    The operator provides all flexibility services TO the TSO as the service customer.
    Payment direction varies: TSO pays for services that primarily benefit the grid, operator pays for services that primarily benefit the plant.

    Args:
        adjusted_prices: Market prices with 'adjusted_da_prices' column (€/MWh)
        congestion_network_charges: Congestion and network charges (€/MWh)
        max_charg_price: Maximum price for profitable charging (€/MWh) E.g. max hourly price for operating the pump
        min_gen_price: Minimum price for profitable discharging (€/MWh) E.g. min hourly price for operating the turbine
        round_trip_efficiency: Round-trip efficiency (0.0-1.0)

    Returns:
        tuple: (
            tso_pays_more_generation: Price TSO pays operator for extra electricity generation (€/MWh),
            operator_pays_less_generation: Price operator pays TSO for reducing electricity generation (€/MWh),
            tso_pays_less_pumping: Price TSO pays operator for reducing water pumping consumption (€/MWh),
            operator_pays_more_pumping: Price operator pays TSO for increasing water pumping consumption (€/MWh)
        )
    """
    # Identify economically viable slots and calculate mean prices
    pump_slots = adjusted_prices[adjusted_prices['adjusted_da_prices'] <= max_charg_price]
    mean_pump_price = pump_slots['adjusted_da_prices'].mean()

    turbine_slots = adjusted_prices[adjusted_prices['adjusted_da_prices'] >= min_gen_price]
    mean_turbine_price = turbine_slots['adjusted_da_prices'].mean()

    # Calculate neutral price point between charging and discharging
    neutral_price_midpoint = (max_charg_price + min_gen_price) / 2

    # Calculate component prices for each flexibility scenario
    # Each service has two pricing approaches: technical cost-based vs market-based
    
    # SERVICE 1: TSO requests MORE electricity generation (TSO PAYS operator)
    # TSO benefits: gets extra power for grid balancing
    # Operator sacrifices: uses stored water suboptimally
    increase_generation_technical_cost = (neutral_price_midpoint + congestion_network_charges) / round_trip_efficiency
    increase_generation_market_price = mean_turbine_price
    
    # SERVICE 2: TSO requests LESS electricity generation (OPERATOR PAYS TSO)
    # Operator benefits: conserves water for higher-priced periods
    # TSO sacrifices: loses planned generation capacity
    decrease_generation_technical_cost = (mean_pump_price + congestion_network_charges) / round_trip_efficiency
    decrease_generation_market_price = neutral_price_midpoint
    
    # SERVICE 3: TSO requests LESS water pumping (TSO PAYS operator)
    # TSO benefits: reduces grid consumption/load
    # Operator sacrifices: stores less energy for future use
    reduce_pumping_technical_cost = mean_turbine_price * round_trip_efficiency - congestion_network_charges
    reduce_pumping_market_price = neutral_price_midpoint
    
    # SERVICE 4: TSO requests MORE water pumping (OPERATOR PAYS TSO)
    # Operator benefits: gets to store more potentially valuable energy
    # TSO sacrifices: accepts higher grid consumption
    increase_pumping_technical_cost = neutral_price_midpoint * round_trip_efficiency - congestion_network_charges
    increase_pumping_market_price = mean_pump_price
    
    # Determine final prices for each flexibility service
    # TSO-pays services: use max() to ensure fair compensation to operator
    # Operator-pays services: use min() to ensure reasonable cost to operator
    
    tso_pays_more_generation = Price(round(max(increase_generation_technical_cost, increase_generation_market_price), 2))  # TSO pays operator for extra generation
    operator_pays_less_generation = Price(round(min(decrease_generation_technical_cost, decrease_generation_market_price), 2))  # Operator pays TSO for reduced generation
    tso_pays_less_pumping = Price(round(max(reduce_pumping_technical_cost, reduce_pumping_market_price), 2))  # TSO pays operator for reduced pumping
    operator_pays_more_pumping = Price(round(min(increase_pumping_technical_cost, increase_pumping_market_price), 2))  # Operator pays TSO for extra pumping

    return tso_pays_more_generation, operator_pays_less_generation, tso_pays_less_pumping, operator_pays_more_pumping


def create_flexibility_costs(
    adjusted_prices: pd.DataFrame, 
    congestion_network_charges: Price, 
    max_charg_price: Price, 
    min_gen_price: Price, 
    round_trip_efficiency: Efficiency
) -> ProductionCosts:
    """
    Create a structured ProductionCosts object from calculation results.
    
    Args:
        adjusted_prices: Market price data
        congestion_network_charges: Congestion and network charges
        max_charg_price: Maximum price for profitable charging (€/MWh) E.g. max hourly price for operating the pump
        min_gen_price: Minimum price for profitable discharging (€/MWh) E.g. min hourly price for operating the turbine
        round_trip_efficiency: Round-trip efficiency
        
    Returns:
        ProductionCosts object with structured cost data
    """
    tso_pays_more_generation, operator_pays_less_generation, tso_pays_less_pumping, operator_pays_more_pumping = calculate_flexibility_cost_prices(
        adjusted_prices, congestion_network_charges, max_charg_price, min_gen_price, round_trip_efficiency
    )
    
    return ProductionCosts(
        increase_discharge=tso_pays_more_generation,
        decrease_discharge=operator_pays_less_generation,
        decrease_charge=tso_pays_less_pumping,
        increase_charge=operator_pays_more_pumping
    ) 