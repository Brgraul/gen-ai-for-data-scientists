#!/usr/bin/env python3
"""
Example usage of the refactored Energy Flexibility Library.

This script demonstrates how to use the new modular architecture to calculate
flexibility costs for pumped hydro storage systems.
"""

import os

from energy_flexibility import FlexibilityCalculator, Config

# Base paths to match main.py structure
base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # Go up two levels to reach root
PRICES_FILE = os.path.join(base, "data", "preise.xlsx")
SCHEDULE_FILE = os.path.join(base, "data", "fahrplan.xls")
OUTPUT_PATH = os.path.join(base, "output", "output.xlsx")

def main():
    """
    Example of using the FlexibilityCalculator with the new architecture.
    """
    
    # Create configuration with required parameters matching main.py
    config = Config(
        prices_file=PRICES_FILE,
        schedule_file=SCHEDULE_FILE, 
        output_path=OUTPUT_PATH,
        delivery_date="2023-04-30",
        price_analysis_days=90,
        volatility_analysis_days=30,
        discharge_power=15.0,
        charge_power=15.0,
        efficiency=0.9,
        network_charges=1.5,
        max_discharge_hours=3,
        residual_value_of_battery=12000000.0,
        remaining_useful_life=15.0,
        planned_operating_hour=1168.0
    )
    
    # Initialize the calculator
    calculator = FlexibilityCalculator(config)
    
    # Perform complete calculation
    try:
        result = calculator.calculate()
        print(f"\nCalculation completed successfully!")
        print(f"Results saved to: {config.output_path}")
        
        # Display summary information
        print(f"\nSummary:")
        print(f"- Delivery date: {config.delivery_date}")
        print(f"- Market data points: {len(calculator.market_data) if calculator.market_data is not None else 'N/A'}")
        print(f"- Boundary prices: {calculator.boundary_prices}")
        print(f"- Flexibility service costs: {calculator.flexibility_service_costs}")
        
        # Show sample option prices
        if calculator.option_prices is not None:
            print(f"\nSample option prices (first 5 intervals):")
            print(calculator.option_prices[['da_time', 'discharge_option_price', 'charge_option_price']].head())
        
    except Exception as e:
        print(f"Error during calculation: {e}")
        return 1
    
    return 0

def demonstrate_individual_components():
    """
    Example of using individual components for testing/debugging.
    """
    print("\n" + "="*60)
    print("DEMONSTRATING INDIVIDUAL COMPONENT ACCESS")
    print("="*60)
    
    config = Config(
        prices_file=PRICES_FILE,
        schedule_file=SCHEDULE_FILE,
        delivery_date="2023-04-30"
    )
    
    calculator = FlexibilityCalculator(config)
    
    # Step-by-step calculation for debugging
    print("1. Loading market data...")
    market_data = calculator.load_market_data()
    print(f"   Loaded {len(market_data)} market data points")
    
    print("2. Calculating boundary prices...")
    # This would require the full workflow, but shows the concept
    # boundary_prices = calculator.find_boundary_prices()
    # print(f"   Boundary prices: {boundary_prices}")
    
    print("Individual component access completed!")

if __name__ == "__main__":
    print("Energy Flexibility Library - Example Usage")
    print("=" * 50)
    
    # Main calculation example
    exit_code = main()
    
    # Individual components example
    if exit_code == 0:
        demonstrate_individual_components()
    
    exit(exit_code) 