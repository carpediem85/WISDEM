import openmdao.api as om
import numpy as np

from ..model.Manager import Manager
from ..model.DefaultMasterInputDict import DefaultMasterInputDict
from .OpenMDAODataframeCache import OpenMDAODataframeCache
from .WeatherWindowCSVReader import read_weather_window

# Read in default sheets for project data
default_project_data = OpenMDAODataframeCache.read_all_sheets_from_xlsx('foundation_validation_ge15')
default_components_data = default_project_data["components"]


class LandBOSSE(om.Group):
    def initialize(self):
        self.options.declare('topLevelFlag', default=False)

    def setup(self):
        # Define all input variables from all models
        myIndeps = om.IndepVarComp()

        myIndeps.add_output('plant_turbine_spacing', 7)
        myIndeps.add_output('plant_row_spacing', 7)

        myIndeps.add_output('commissioning_pct', 0.01)
        myIndeps.add_output('decommissioning_pct', 0.15)

        # Inputs for automatic component list generation of blades
        # A default of -1.0 for any of these inputs means that the
        # default value loaded above should be used. All blades are
        # assumed to be the same.

        myIndeps.add_output('blade_drag_coefficient', -1.0)                # Unitless
        myIndeps.add_output('blade_lever_arm', -1.0, units='m')
        myIndeps.add_output('blade_install_cycle_time', -1.0)              # Units are hours, but disallowed in OMDAO
        myIndeps.add_output('blade_offload_hook_height', -1.0, units='m')
        myIndeps.add_output('blade_offload_cycle_time', -1.0)              # Units are hours, but disallowed in OMDAO
        myIndeps.add_output('blade_drag_multiplier', -1.0)                 # Unitless

        self.add_subsystem('myIndeps', myIndeps, promotes=['*'])

        if self.options['topLevelFlag']:
            sharedIndeps = om.IndepVarComp()
            sharedIndeps.add_output('hub_height', 0.0, units='m')
            sharedIndeps.add_output('foundation_height', 0.0, units='m')
            sharedIndeps.add_output('blade_mass', 0.0, units='kg')
            sharedIndeps.add_output('nacelle_mass', 0.0, units='kg')
            sharedIndeps.add_output('tower_mass', 0.0, units='kg')
            self.add_subsystem('sharedIndeps', sharedIndeps, promotes=['*'])
        self.add_subsystem('landbosse', LandBOSSE_API(), promotes=['*'])


class LandBOSSE_API(om.ExplicitComponent):
    def setup(self):
        self.setup_inputs()
        self.setup_outputs()
        self.setup_discrete_outputs()
        self.setup_discrete_inputs_that_are_not_dataframes()
        self.setup_discrete_inputs_that_are_dataframes()

    def setup_inputs(self):
        """
        This method sets up the inputs.
        """
        self.add_input('crane_breakdown_fraction', val=0.0,
                       desc='0 means the crane is never broken down. 1 means it is broken down every turbine.')

        self.add_input('construct_duration', val=9, desc='Total project construction time (months)')
        self.add_input('hub_height_meters', val=80, units='m', desc='Hub height m')
        self.add_input('rotor_diameter_m', val=77, units='m', desc='Rotor diameter m')
        self.add_input('wind_shear_exponent', val=0.2, desc='Wind shear exponent')
        self.add_input('turbine_rating_MW', val=1.5, units='MW', desc='Turbine rating MW')
        self.add_input('num_turbines', val=100, desc='Number of turbines in project')
        self.add_input('fuel_cost_usd_per_gal', val=1.0, desc='Fuel cost USD/gal')

        self.add_input('breakpoint_between_base_and_topping_percent', val=70,
                       desc='Breakpoint between base and topping (percent)')

        # Could not place units in rate_of_deliveries
        self.add_input('rate_of_deliveries', val=10, desc='Rate of deliveries (turbines per week)')

        # Could not place units in turbine_spacing_rotor_diameters
        # indeps.add_output('turbine_spacing_rotor_diameters', units='rotor diameters', desc='Turbine spacing (times rotor diameter)', val=4)
        self.add_input('turbine_spacing_rotor_diameters', desc='Turbine spacing (times rotor diameter)', val=4)

        self.add_input('depth', units='m', desc='Foundation depth m', val=2.36)
        self.add_input('rated_thrust_N', units='N', desc='Rated Thrust (N)', val=5.89e5)

        # Can't set units
        # indeps.add_output('bearing_pressure_n_m2', units='n/m2', desc='Bearing Pressure (n/m2)', val=191521)
        self.add_input('bearing_pressure_n_m2', desc='Bearing Pressure (n/m2)', val=191521)

        self.add_input('gust_velocity_m_per_s', units='m/s', desc='50-year Gust Velocity (m/s)', val=59.5)
        self.add_input('road_length_adder_m', units='m', desc='Road length adder (m)', val=5000)

        # Can't set units
        self.add_input('fraction_new_roads',
                       desc='Percent of roads that will be constructed (0.0 - 1.0)', val=0.33)

        self.add_input('road_quality', desc='Road Quality (0-1)', val=0.6)
        self.add_input('line_frequency_hz', units='Hz', desc='Line Frequency (Hz)', val=60)

        # Can't set units
        self.add_input('row_spacing_rotor_diameters',
                       desc='Row spacing (times rotor diameter)', val=4)

        self.add_input(
            'user_defined_distance_to_grid_connection',
            desc='Flag for user-defined home run trench length (True or False)',
            val=False
        )

        self.add_input('trench_len_to_substation_km', units='km',
                       desc='Combined Homerun Trench Length to Substation (km)', val=50)
        self.add_input('distance_to_interconnect_mi', units='mi', desc='Distance to interconnect (miles)', val=5)
        self.add_input('interconnect_voltage_kV', units='kV', desc='Interconnect Voltage (kV)', val=130)
        self.add_input('new_switchyard', desc='New Switchyard (True or False)', val=True)
        self.add_input('critical_speed_non_erection_wind_delays_m_per_s', units='m/s',
                       desc='Non-Erection Wind Delay Critical Speed (m/s)', val=15)
        self.add_input('critical_height_non_erection_wind_delays_m', units='m',
                       desc='Non-Erection Wind Delay Critical Height (m)', val=10)
        self.add_input('road_width_ft', units='ft', desc='Road width (ft)', val=20)
        self.add_input('road_thickness', desc='Road thickness (in)', val=8)
        self.add_input('crane_width', units='m', desc='Crane width (m)', val=12.2)
        self.add_input('num_hwy_permits', desc='Number of highway permits', val=10)
        self.add_input('num_access_roads', desc='Number of access roads', val=2)
        self.add_input('overtime_multiplier', desc='Overtime multiplier', val=1.4)
        self.add_input('markup_contingency', desc='Markup contingency', val=0.03)
        self.add_input('markup_warranty_management', desc='Markup warranty management', val=0.0002)
        self.add_input('markup_sales_and_use_tax', desc='Markup sales and use tax', val=0)
        self.add_input('markup_overhead', desc='Markup overhead', val=0.05)
        self.add_input('markup_profit_margin', desc='Markup profit margin', val=0.05)
        self.add_input('Mass tonne', val=(1.,), desc='', units='t')
        self.add_input('development_labor_cost_usd', val=1e6, desc='The cost of labor in the development phase',
                       units='USD')

        self.add_input('commissioning_pct', 0.01)
        self.add_input('decommissioning_pct', 0.15)

    def setup_discrete_inputs_that_are_not_dataframes(self):
        """
        This method sets up the discrete inputs that aren't dataframes.
        The dataframes need to be handled differently because the way
        they will get their default data is different.
        """
        self.add_discrete_input('user_defined_home_run_trench', val=1,
                                desc='Flag for user-defined home run trench length (0 = no; 1 = yes)')

        self.add_discrete_input(
            'allow_same_flag',
            val=False,
            desc='Allow same crane for base and topping (True or False)',
        )

        self.add_discrete_input(
            'hour_day',
            desc="Dictionary of normal and long hours for construction in a day in the form of {'long': 24, 'normal': 10}",
            val={'long': 24, 'normal': 10}
        )

        self.add_discrete_input(
            'time_construct',
            desc='One of the keys in the hour_day dictionary to specify how many hours per day construction happens.',
            val='normal'
        )

    def setup_discrete_inputs_that_are_dataframes(self):
        """
        This sets up the default inputs that are dataframes. They are separate
        because they hold the project data and the way we need to hold their
        data is different. They have defaults loaded at the top of the file
        which can be overridden outside by setting the properties listed
        below.
        """

        self.add_discrete_input('site_facility_building_area_df',
                                val=default_project_data['site_facility_building_area'],
                                desc='site_facility_building_area DataFrame')

        self.add_discrete_input('components',
                                val=default_project_data['components'],
                                desc='Dataframe of components for tower, blade, nacelle')

        self.add_discrete_input('crane_specs',
                                val=default_project_data['crane_specs'],
                                desc='Dataframe of specifications of cranes')

        self.add_discrete_input('weather_window',
                                val=read_weather_window(default_project_data['weather_window']),
                                desc='Dataframe of wind toolkit data')

        self.add_discrete_input('crew',
                                val=default_project_data['crew'],
                                desc='Dataframe of crew configurations')

        self.add_discrete_input('crew_price',
                                val=default_project_data['crew_price'],
                                desc='Dataframe of costs per hour for each type of worker.')

        self.add_discrete_input('equip',
                                val=default_project_data['equip'],
                                desc='Collections of equipment to perform erection operations.')

        self.add_discrete_input('equip_price',
                                val=default_project_data['equip_price'],
                                desc='Prices for various type of equipment.')

        self.add_discrete_input('rsmeans',
                                val=default_project_data['rsmeans'],
                                desc='RSMeans price data')

        self.add_discrete_input('cable_specs',
                                val=default_project_data['cable_specs'],
                                desc='cable specs for collection system')

        self.add_discrete_input('material_price',
                                val=default_project_data['material_price'],
                                desc='Prices of materials for foundations and roads')

        self.add_discrete_input('project_data',
                                val=default_project_data,
                                desc='Dictionary of all dataframes of data')

    def setup_outputs(self):
        """
        This method sets up the continuous outputs. This is where total costs
        and installation times go.

        To see how cost totals are calculated see, the compute_total_bos_costs
        method below.
        """
        self.add_output('bos_capex', 0.0, units='USD',
                        desc='Total BOS CAPEX not including commissioning or decommissioning.')
        self.add_output('bos_capex_kW', 0.0, units='USD/kW',
                        desc='Total BOS CAPEX per kW not including commissioning or decommissioning.')
        self.add_output('total_capex', 0.0, units='USD',
                        desc='Total BOS CAPEX including commissioning and decommissioning.')
        self.add_output('total_capex_kW', 0.0, units='USD/kW',
                        desc='Total BOS CAPEX per kW including commissioning and decommissioning.')
        self.add_output('installation_capex', 0.0, units='USD',
                        desc='Total foundation and erection installation cost.')
        self.add_output('installation_capex_kW', 0.0, units='USD',
                        desc='Total foundation and erection installation cost per kW.')
        self.add_output('installation_time_months', 0.0,
                        desc='Total balance of system installation time (months).')

    def setup_discrete_outputs(self):
        """
        This method sets up discrete outputs.
        """
        self.add_discrete_output(
            'landbosse_costs_by_module_type_operation',
            desc='The costs by module, type and operation',
            val=None
        )

        self.add_discrete_output(
            'landbosse_details_by_module',
            desc='The details from the run of LandBOSSE. This includes some costs, but mostly other things',
            val=None
        )

        # OUTPUTS, SPECIFIC

        self.add_discrete_output(
            'erection_crane_choice',
            desc='The crane choices for erection.',
            val=None
        )

        self.add_discrete_output(
            'erection_component_name_topvbase',
            desc='List of components and whether they are a topping or base operation',
            val=None
        )

    def compute(self, inputs, outputs, discrete_inputs=None, discrete_outputs=None):
        """
        This runs the ErectionCost module using the inputs and outputs into and
        out of this module.

        Note: inputs, discrete_inputs are not dictionaries. They do support
        [] notation. inputs is of class 'openmdao.vectors.default_vector.DefaultVector'
        discrete_inputs is of class openmdao.core.component._DictValues. Other than
        [] brackets, they do not behave like dictionaries. See the following
        documentation for details.

        http://openmdao.org/twodocs/versions/latest/_srcdocs/packages/vectors/default_vector.html
        https://mdolab.github.io/OpenAeroStruct/_modules/openmdao/core/component.html

        Parameters
        ----------
        inputs : openmdao.vectors.default_vector.DefaultVector
            A dictionary-like object with NumPy arrays that hold float
            inputs. Note that since these are NumPy arrays, they
            need indexing to pull out simple float64 values.

        outputs : openmdao.vectors.default_vector.DefaultVector
            A dictionary-like object to store outputs.

        discrete_inputs : openmdao.core.component._DictValues
            A dictionary-like with the non-numeric inputs (like
            pandas.DataFrame)

        discrete_outputs : openmdao.core.component._DictValues
            A dictionary-like for non-numeric outputs (like
            pandas.DataFrame)
        """

        # Put the inputs together and run all the modules
        master_output_dict = dict()
        master_input_dict = self.prepare_master_input_dictionary(inputs, discrete_inputs)
        manager = Manager(master_input_dict, master_output_dict)
        result = manager.execute_landbosse('WISDEM')

        # Check if everything executed correctly
        if result != 0:
            raise Exception("LandBOSSE didn't execute correctly")

        # Gather the cost and detail outputs

        costs_by_module_type_operation = self.gather_costs_from_master_output_dict(master_output_dict)
        discrete_outputs['landbosse_costs_by_module_type_operation'] = costs_by_module_type_operation

        details = self.gather_details_from_master_output_dict(master_output_dict)
        discrete_outputs['landbosse_details_by_module'] = details

        # Now get specific outputs. These have been refactored to methods that work
        # with each module so as to keep this method as compact as possible.
        self.gather_specific_erection_outputs(master_output_dict, outputs, discrete_outputs)

        # Compute the total BOS costs
        self.compute_total_bos_costs(costs_by_module_type_operation, master_output_dict, inputs, outputs)

    def prepare_master_input_dictionary(self, inputs, discrete_inputs):
        """
        This prepares a master input dictionary by applying all the necessary
        modifications to the inputs.

        Parameters
        ----------
        inputs : openmdao.vectors.default_vector.DefaultVector
            A dictionary-like object with NumPy arrays that hold float
            inputs. Note that since these are NumPy arrays, they
            need indexing to pull out simple float64 values.

        discrete_inputs : openmdao.core.component._DictValues
            A dictionary-like with the non-numeric inputs (like
            pandas.DataFrame)

        Returns
        -------
        dict
            The prepared master input to go to the Manager.
        """
        inputs_dict = {key: inputs[key][0] for key in inputs.keys()}
        discrete_inputs_dict = {key: value for key, value in discrete_inputs.items()}
        incomplete_input_dict = {**inputs_dict, **discrete_inputs_dict}

        # Modify the component data if it is needed
        self.modify_component_lists(inputs, discrete_inputs)

        # FoundationCost needs to have all the component data split into separate
        # NumPy arrays.
        incomplete_input_dict['component_data'] = discrete_inputs['components']
        for component in incomplete_input_dict['component_data'].keys():
            incomplete_input_dict[component] = np.array(incomplete_input_dict['component_data'][component])

        # These are aliases because parts of the code call the same thing by
        # difference names.
        incomplete_input_dict['crew_cost'] = discrete_inputs['crew_price']
        incomplete_input_dict['cable_specs_pd'] = discrete_inputs['cable_specs']

        # read in RSMeans per diem:
        crew_cost = discrete_inputs['crew_price']
        crew_cost = crew_cost.set_index("Labor type ID", drop=False)
        incomplete_input_dict['rsmeans_per_diem'] = crew_cost.loc['RSMeans', 'Per diem USD per day']

        # Calculate project size in megawatts
        incomplete_input_dict['project_size_megawatts'] = float(inputs['num_turbines'] * inputs['turbine_rating_MW'])

        defaults = DefaultMasterInputDict()
        master_input_dict = defaults.populate_input_dict(incomplete_input_dict)

        return master_input_dict

    def gather_costs_from_master_output_dict(self, master_output_dict):
        """
        This method extract all the cost_by_module_type_operation lists for
        output in an Excel file.

        It finds values for the keys ending in '_module_type_operation'. It
        then concatenates them together so they can be easily written to
        a .csv or .xlsx

        On every row, it includes the:
            Rotor diameter m
            Turbine rating MW
            Number of turbines

        This enables easy mapping of new columns if need be. The columns have
        spaces in the names so that they can be easily written to a user-friendly
        output.

        Parameters
        ----------
        runs_dict : dict
            Values are the names of the projects. Keys are the lists of
            dictionaries that are lines for the .csv

        Returns
        -------
        list
            List of dicts to write to the .csv.
        """
        line_items = []

        # Gather the lists of costs
        cost_lists = [value for key, value in master_output_dict.items() if key.endswith('_module_type_operation')]

        # Flatten the list of lists that is the result of the gathering
        for cost_list in cost_lists:
            line_items.extend(cost_list)

        # Filter out the keys needed and rename them to meaningful values
        final_costs = []
        for line_item in line_items:
            item = {
                'Module': line_item['module'],
                'Type of cost': line_item['type_of_cost'],
                'Cost / kW': line_item['usd_per_kw_per_project'],
                'Cost / project': line_item['cost_per_project'],
                'Cost / turbine': line_item['cost_per_turbine'],
                'Number of turbines': line_item['num_turbines'],
                'Rotor diameter (m)': line_item['rotor_diameter_m'],
                'Turbine rating (MW)': line_item['turbine_rating_MW'],
                'Project ID with serial': line_item['project_id_with_serial']
            }
            final_costs.append(item)

        return final_costs

    def gather_details_from_master_output_dict(self, master_output_dict):
        """
        This extracts the detail lists from all the modules to output
        the detailed non-cost data from the model run.

        Parameters
        ----------
        master_output_dict : dict
            The master output dict with the finished module output in it.

        Returns
        -------
        list
            List of dicts with detailed data.
        """
        line_items = []

        # Gather the lists of costs
        details_lists = [value for key, value in master_output_dict.items() if key.endswith('_csv')]

        # Flatten the list of lists
        for details_list in details_lists:
            line_items.extend(details_list)

        return line_items

    def gather_specific_erection_outputs(self, master_output_dict, outputs, discrete_outputs):
        """
        This method gathers specific outputs from the ErectionCost module and places
        them on the outputs.

        The method does not return anything. Rather, it places the outputs directly
        on the continuous of discrete outputs.

        Parameters
        ----------
        master_output_dict: dict
            The master output dictionary out of LandBOSSE

        outputs : openmdao.vectors.default_vector.DefaultVector
            A dictionary-like object to store outputs.

        discrete_outputs : openmdao.core.component._DictValues
            A dictionary-like for non-numeric outputs (like
            pandas.DataFrame)
        """
        discrete_outputs['erection_crane_choice'] = master_output_dict['crane_choice']
        discrete_outputs['erection_component_name_topvbase'] = master_output_dict['component_name_topvbase']

    def compute_total_bos_costs(self, costs_by_module_type_operation, master_output_dict, inputs, outputs):
        """
        This computes the total BOS costs from the master output dictionary
        and places them on the necessary outputs.

        Parameters
        ----------
        costs_by_module_type_operation: List[Dict[str, Any]]
            The lists of costs by module, type and operation.

        master_output_dict: Dict[str, Any]
            The master output dictionary from the run. Used to obtain the
            construction time,

        outputs : openmdao.vectors.default_vector.DefaultVector
            The outputs in which to place the results of the computations
        """
        bos_per_kw = 0.0
        bos_per_project = 0.0
        installation_per_project = 0.0
        installation_per_kW = 0.0

        for row in costs_by_module_type_operation:
            bos_per_kw += row['Cost / kW']
            bos_per_project += row['Cost / project']
            if row['Module'] in ['ErectionCost', 'FoundationCost']:
                installation_per_project += row['Cost / project']
                installation_per_kW += row['Cost / kW']

        commissioning_pct = inputs['commissioning_pct']
        decommissioning_pct = inputs['decommissioning_pct']

        commissioning_per_project = bos_per_project * commissioning_pct
        decomissioning_per_project = bos_per_project * decommissioning_pct
        commissioning_per_kW = bos_per_kw * commissioning_pct
        decomissioning_per_kW = bos_per_kw * decommissioning_pct

        outputs['total_capex_kW'] = \
            np.round(bos_per_kw + commissioning_per_kW + decomissioning_per_kW, 0)
        outputs['total_capex'] = \
            np.round(bos_per_project + commissioning_per_project + decomissioning_per_project, 0)
        outputs['bos_capex'] = round(bos_per_project, 0)
        outputs['bos_capex_kW'] = round(bos_per_kw, 0)
        outputs['installation_capex'] = round(installation_per_project, 0)
        outputs['installation_capex_kW'] = round(installation_per_kW, 0)

        actual_construction_months = master_output_dict['actual_construction_months']
        outputs['installation_time_months'] = round(actual_construction_months, 0)

    # assumes $25k per tower section, 30m max length, 80t max section mass

    def modify_component_lists(self, inputs, discrete_inputs):
        """
        This method modifies the previously loaded default component lists with
        data about blades, tower sections, if they have been provided as input
        to the component.

        It only modifies the project component data if default data for the proper
        inputs have been overridden.

        The default blade data is assumed to be the first component that begins
        with the word "Blade"

        This should take mass from the tower in WISDEM. Ideally, this should have
        an input for transportable tower 4.3, large diameter steel tower LDST 6.2m, or
        unconstrained key stone tower. Or give warnings about the boundaries
        that we assume.

        Parameters
        ----------
        inputs : openmdao.vectors.default_vector.DefaultVector
            A dictionary-like object with NumPy arrays that hold float
            inputs. Note that since these are NumPy arrays, they
            need indexing to pull out simple float64 values.

        discrete_inputs : openmdao.core.component._DictValues
            A dictionary-like with the non-numeric inputs (like
            pandas.DataFrame)
        """
        # myIndeps.add_output('blade_drag_coefficient', -1.0)  # Unitless
        # myIndeps.add_output('blade_lever_arm', -1.0, units='m')
        # myIndeps.add_output('blade_install_cycle_time', -1.0, units='hr')
        # myIndeps.add_output('blade_offload_hook_height', -1.0, units='m')
        # myIndeps.add_output('blade_offload_cycle_time', -1.0, units='hr')
        # myIndeps.add_output('blade_drag_multiplier', -1.0)  # Unitless

        components = discrete_inputs['components']

        # Another way would be to look at topLevelFlag

        if inputs['blade_drag_coefficient'] != -1:
            blades = components[components['Component'].str.startswith('Blade')]
            default_blade = blades.iloc[0]
            print(default_blade)
        else:
            print('Blade modifications unspecifed')
