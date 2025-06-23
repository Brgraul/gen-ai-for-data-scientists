"""
Optimization functions for economic boundary calculations and production cost pricing in pumped hydro storage operations.

This module handles the core optimization logic for determining optimal charging/discharging
schedules and calculating production costs for various TSO flexibility scenarios.
"""

import pandas as pd
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
    Determines optimal economic boundary prices for pumped hydro storage using a greedy turbine-first approach.
    
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

    # Tracking variables for optimization process
    total_power_generation_energy = Energy(0.0)
    total_pumping_energy = Energy(0.0)
    minimum_generation_price = None
    maximum_pumping_price = None
    any_iteration_occurred = False

    pump_index = 0
    pump_slot_remaining_capacity = pump_energy_per_slot

    # Main optimization loop: match high-price discharge with low-price charge opportunities
    for i, turbine_row in turbine_slots.iterrows():
        if total_power_generation_energy >= max_total_turbine_energy:
            break

        turbine_price = Price(turbine_row['adjusted_da_prices'])
        adjusted_turbine_price = turbine_price * efficiency  # Account for round-trip losses
        required_turbine_energy = min(turbine_energy_per_slot, max_total_turbine_energy - total_power_generation_energy)

        print(f"\n=== Turbine Slot {i+1} ===")
        print(f"Turbine price: {turbine_price} €/MWh | Max energy this slot: {required_turbine_energy} MWh")

        # Find matching pump slots for current turbine slot
        while required_turbine_energy > 0 and pump_index < len(pump_slots):
            pump_price = Price(pump_slots.loc[pump_index, 'adjusted_da_prices'])
            adjusted_pump_price = pump_price + congestion_network_charges  # Include network charges

            print(f"\n  → Considering Pump Slot {pump_index+1}")
            print(f"    Pump price: {pump_price} €/MWh ")
            

            # Check profitability
            if adjusted_turbine_price <= adjusted_pump_price:
                print(f"Pump price {pump_price} too high vs turbine value. Breaking pump loop.")
                break

            usable_turbine_energy_from_slot = pump_slot_remaining_capacity * efficiency
            energy_to_discharge = min(required_turbine_energy, usable_turbine_energy_from_slot)
            actual_pump_energy_used = energy_to_discharge / efficiency
           
            print(f"    ✅ Matching:")
            print(f"       The energy left from pump slot: {pump_slot_remaining_capacity:.3f} MWh")
            print(f"       The energy that can be discharged from slot: {usable_turbine_energy_from_slot:.3f} MWh")
            print(f"       Discharging: {energy_to_discharge:.3f} MWh → Requires pump energy: {actual_pump_energy_used:.3f} MWh")

            # Update totals
            total_power_generation_energy += energy_to_discharge
            total_pumping_energy += actual_pump_energy_used
            required_turbine_energy -= energy_to_discharge
            pump_slot_remaining_capacity -= actual_pump_energy_used

            # Update price thresholds
            minimum_generation_price = turbine_price

            # If pump slot exhausted, go to next
            if pump_slot_remaining_capacity <= 1e-6:
                maximum_pumping_price = pump_price
                pump_index += 1
                pump_slot_remaining_capacity = pump_energy_per_slot

        if required_turbine_energy > 0:
            print(f"Could not fully cover turbine slot {i+1}. Remaining energy: {required_turbine_energy:.3f} MWh")
            break  # No more affordable pump energy → stop

        any_iteration_occurred = True  # Mark that we had at least one valid iteration
    
    if not any_iteration_occurred:
        mean_price = adjusted_prices['adjusted_da_prices'].mean()
        fallback_pump_price = mean_price + ((mean_price * (1 - efficiency) + congestion_network_charges) / (1 + efficiency))
        fallback_turbine_price = mean_price - ((mean_price * (1 - efficiency) + congestion_network_charges) / (1 + efficiency))

        print("\nNo valid iterations, applying special case prices:")
        print(f"Special case turbine price: {fallback_turbine_price:.3f} euro/MWh")
        print(f"Special case pump price: {fallback_pump_price:.3f} euro/MWh")

        minimum_generation_price = Price(fallback_turbine_price)
        maximum_pumping_price = Price(fallback_pump_price)
        total_power_generation_energy = Energy(0.0)
        total_pumping_energy = Energy(0.0)

    print("\nFinal Results:")
    print(f"Minimum power generation price: {minimum_generation_price}")
    print(f"Maximum pumping price: {maximum_pumping_price}")
    print(f"Total power generation energy discharged: {total_power_generation_energy} MWh")
    print(f"Total pumping energy used: {total_pumping_energy:.3f} MWh")

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