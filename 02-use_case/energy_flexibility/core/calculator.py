"""
Main calculator facade for energy flexibility cost calculations.

This module provides the main FlexibilityCalculator class that orchestrates
all the functionality from the various modules into a simple, unified interface.
"""

import pandas as pd
from typing import Optional, Tuple

from .config import Config
from .data_loader import load_and_prepare_data
from .market_analysis import calculate_average_diff, adjust_da_prices_for_date, calculate_standard_deviation
from .optimization import find_optimal_boundary_prices_turbine_first, calculate_flexibility_cost_prices
from .cost_calculation import calculate_option_prices, calculate_production_flexibility_cost, calculate_deprecation_cost, aggregate_costs
from .reporting import values_to_tso
from .models import (
    Price, Energy
)


class FlexibilityCalculator:
    """
    Main calculator class for energy flexibility cost calculations.
    
    This class provides a simple facade over all the complexity of the flexibility
    cost calculation process, making it easy to use while keeping all the individual
    components accessible for testing and debugging.
    """
    
    def __init__(self, config: Config) -> None:
        """
        Initialize the calculator with configuration.
        
        Args:
            config: Configuration object with all parameters
        """
        self.config = config
        self._market_data: Optional[pd.DataFrame] = None
        self._adjusted_prices: Optional[pd.DataFrame] = None
        self._boundary_prices: Optional[Tuple[Price, Price, Energy, Energy]] = None
        self._flexibility_service_costs: Optional[Tuple[Price, Price, Price, Price]] = None
        self._standard_deviations: Optional[pd.Series] = None
        self._option_prices: Optional[pd.DataFrame] = None
        self._operational_schedule_data: Optional[pd.DataFrame] = None
        
    def calculate(self) -> pd.DataFrame:
        """
        Main method that performs the complete flexibility cost calculation.
        
        This method orchestrates all the steps in the correct order:
        1. Load and prepare market data
        2. Calculate price adjustments
        3. Find optimal boundary prices
        4. Calculate flexibility service costs
        5. Calculate volatility
        6. Calculate option prices
        7. Load schedule data
        8. Generate TSO report
        9. Calculate final costs
        
        Returns:
            DataFrame with final flexibility costs
        """
        print("Starting flexibility cost calculation...")
        
        # Step 1: Load market data
        print("1. Loading market data...")
        self._market_data = self.load_market_data()
        
        # Step 2: Calculate price adjustments
        print("2. Calculating price adjustments...")
        average_diff = calculate_average_diff(
            self._market_data, 
            self.config.delivery_date, 
            lookback_days=self.config.price_analysis_days
        )
        self._adjusted_prices = adjust_da_prices_for_date(
            self._market_data, 
            self.config.delivery_date, 
            average_diff
        )
        
        # Step 3: Find boundary prices
        print("3. Finding optimal boundary prices...")
        self._boundary_prices = self.find_boundary_prices(self._adjusted_prices)
        
        # Step 4: Calculate flexibility service costs
        print("4. Calculating flexibility service costs...")
        self._flexibility_service_costs = self.calculate_flexibility_costs(
            self._adjusted_prices, 
            self._boundary_prices
        )
        
        # Step 5: Calculate market volatility
        print("5. Calculating market volatility...")
        self._standard_deviations = calculate_standard_deviation(
            self._market_data, 
            self.config.delivery_date, 
            lookback_days=self.config.volatility_analysis_days
        )
        
        # Step 6: Calculate option prices
        print("6. Calculating option prices...")
        self._option_prices = calculate_option_prices(
            market_data_df=self._adjusted_prices.copy(),
            charging_strike_price=self._boundary_prices[1],
            discharging_strike_price=self._boundary_prices[0],
            historical_volatilities=self._standard_deviations,
            day_ahead_prices=self._adjusted_prices["da_prices"],
            expected_intraday_prices=self._adjusted_prices["adjusted_da_prices"]
        )
        
        # Step 7: Load schedule data
        print("7. Loading schedule data...")
        self._operational_schedule_data = self._load_schedule_data()
       
        # Step 8: Calculate final costs
        print("8. Calculating final costs...")
        # Call the function to calculate lost flexibility
        costs_production_opportunity = calculate_production_flexibility_cost(
            self._operational_schedule_data.copy(deep=True),
            self.config.discharge_power, 
            self.config.charge_power,
            self._option_prices['discharge_option_price'],
            self._option_prices['charge_option_price'],
            self._flexibility_service_costs[0],  # increase_discharge_price
            self._flexibility_service_costs[1],  # decrease_discharge_price
            self._flexibility_service_costs[2],  # decrease_charge_price
            self._flexibility_service_costs[3]   # increase_charge_price
        )

        # Added deprecation cost due to operating the plant in a suboptimal way
        cost_deprecation = calculate_deprecation_cost(
            costs_production_opportunity, 
            self.config.discharge_power, 
            self.config.charge_power,
            self.config.residual_value_of_battery, 
            self.config.remaining_useful_life,
            self.config.planned_operating_hour,
            self._boundary_prices[1],  # pump_prices
            self._boundary_prices[0],  # turbine_prices
            day_ahead_market_prices=self._adjusted_prices["da_prices"]
        )

        aggregated_costs = aggregate_costs(
            cost_deprecation, 
            excel_export_path="output//cost_values_mit_ex_ante_kostenwerte.xlsx"
        )

        # Step 9: Generate TSO report
        print("9. Generating TSO report...")
        self._generate_tso_report()

        return aggregated_costs
    
    def load_market_data(self) -> pd.DataFrame:
        """Load and prepare market data from Excel file."""
        if self._market_data is None:
            self._market_data = load_and_prepare_data(self.config.prices_file)
        return self._market_data
        
    
    def find_boundary_prices(self, market_data: Optional[pd.DataFrame] = None) -> Tuple[Price, Price, Energy, Energy]:
        """
        Find optimal boundary prices for charging and discharging.
        
        Args:
            market_data: Optional market data, uses cached data if not provided
            
        Returns:
            Tuple of (
                minimum_generation_price: Minimum price for profitable discharge (€/MWh),
                maximum_pumping_price: Maximum price for profitable charging (€/MWh),
                total_power_generation_energy: Total planned discharge energy (MWh),
                total_pumping_energy: Total planned charging energy (MWh)
            )
        """
        if market_data is None:
            market_data = self._adjusted_prices
            
        if market_data is None:
            raise ValueError("No market data available. Call load_market_data() first.")
            
        return find_optimal_boundary_prices_turbine_first(
            adjusted_prices=market_data,
            turbine_power=self.config.discharge_power,
            pump_power=self.config.charge_power,
            efficiency=self.config.efficiency,
            congestion_network_charges=self.config.network_charges,
            max_full_load_hours=self.config.max_discharge_hours
        )
    
    def calculate_flexibility_costs(self, market_data: pd.DataFrame, boundary_prices: Tuple[Price, Price, Energy, Energy]) -> Tuple[Price, Price, Price, Price]:
        """
        Calculate costs incurred by the TSO for flexibility services depening on the comparison between the optimal operation for the battery and the market price.
        
        Args:
            market_data: Market price data
            boundary_prices: Boundary prices from optimization
            
        Returns:
            Tuple of (
                tso_pays_more_generation: Price TSO pays operator for extra electricity generation (€/MWh),
                operator_pays_less_generation: Price operator pays TSO for reducing electricity generation (€/MWh),
                tso_pays_less_pumping: Price TSO pays operator for reducing water pumping consumption (€/MWh),
                operator_pays_more_pumping: Price operator pays TSO for increasing water pumping consumption (€/MWh)
            )
        """
        turbine_price, pump_price = boundary_prices[0], boundary_prices[1]
        
        return calculate_flexibility_cost_prices(
            adjusted_prices=market_data,
            congestion_network_charges=self.config.network_charges,
            max_charg_price=pump_price,
            min_gen_price=turbine_price,
            round_trip_efficiency=self.config.efficiency
        )
    
    def _load_schedule_data(self) -> pd.DataFrame:
        """Load operational schedule data from Excel file."""
        operational_schedule_data = pd.read_excel(
            self.config.schedule_file, 
            sheet_name='intern', 
            skiprows=12
        )
        
        # Rename columns for easier access
        operational_schedule_data.rename(columns={
            operational_schedule_data.columns[0]: 'time',
            operational_schedule_data.columns[1]: 'Pmax',
            operational_schedule_data.columns[2]: 'Vmax',
            operational_schedule_data.columns[3]: 'Pt',
            operational_schedule_data.columns[4]: 'Prd',
            operational_schedule_data.columns[5]: 'Pnew',
            operational_schedule_data.columns[6]: 'RedispatchType',
            operational_schedule_data.columns[7]: 'pos_vorgehaltene_leistung',
            operational_schedule_data.columns[8]: 'neg_vorgehaltene_leistung'
        }, inplace=True)
        
        return operational_schedule_data
    
    def _generate_tso_report(self) -> None:
        """Generate TSO compliance report."""
        if self._operational_schedule_data is None or self._option_prices is None or self._flexibility_service_costs is None:
            raise ValueError("Required data not available for TSO report generation")
            
        values_to_tso(
            operational_schedule_data=self._operational_schedule_data,
            discharge_option_price=self._option_prices['discharge_option_price'],
            charge_option_price=self._option_prices['charge_option_price'],
            discharge_power=self.config.discharge_power,
            charge_power=self.config.charge_power,
            increase_discharge_price=self._flexibility_service_costs[0],
            decrease_discharge_price=self._flexibility_service_costs[1],
            decrease_charge_price=self._flexibility_service_costs[2],
            increase_charge_price=self._flexibility_service_costs[3],
            pump_prices=self._boundary_prices[1] if self._boundary_prices else Price(0.0),
            turbine_prices=self._boundary_prices[0] if self._boundary_prices else Price(0.0),
            residual_value_of_battery=self.config.residual_value_of_battery,
            remaining_useful_life=self.config.remaining_useful_life,
            planned_operating_hour=self.config.planned_operating_hour,
            delivery_date=self.config.delivery_date,
            output_to_tso=self.config.output_path
        )
    
    @property
    def market_data(self) -> Optional[pd.DataFrame]:
        """Access to loaded market data."""
        return self._market_data
    
    @property
    def adjusted_prices(self) -> Optional[pd.DataFrame]:
        """Access to adjusted price data."""
        return self._adjusted_prices
    
    @property
    def boundary_prices(self) -> Optional[Tuple[Price, Price, Energy, Energy]]:
        """Access to calculated boundary prices."""
        return self._boundary_prices
    
    @property
    def flexibility_service_costs(self) -> Optional[Tuple[Price, Price, Price, Price]]:
        """Access to calculated flexibility service costs."""
        return self._flexibility_service_costs
    
    @property
    def option_prices(self) -> Optional[pd.DataFrame]:
        """Access to calculated option prices."""
        return self._option_prices
    
    @property
    def operational_schedule_data(self) -> Optional[pd.DataFrame]:
        """Access to operational schedule data."""
        return self._operational_schedule_data 