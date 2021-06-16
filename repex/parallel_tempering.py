import time

import numpy as np

from repex.thermodynamics import ThermodynamicState
import repex.replica_exchange
from repex.replica_exchange import ReplicaExchange
from repex import netcdf_io
from repex.mcmc import SamplerState

import logging
logger = logging.getLogger(__name__)

from repex.constants import kB


class ParallelTempering(ReplicaExchange):
    """Parallel tempering simulation class.

    This class provides a facility for parallel tempering simulations.  It is a subclass of ReplicaExchange, but provides
    various convenience methods and efficiency improvements for parallel tempering simulations, so should be preferred for
    this type of simulation.  In particular, the System only need be specified once, while the temperatures (or a temperature
    range) is used to automatically build a set of ThermodynamicState objects for replica-exchange.  Efficiency improvements
    make use of the fact that the reduced potentials are linear in inverse temperature.
    
    Notes
    -----
    
    For creating a new ParallelTempering simulation, we recommend the use
    of the `create_repex` function, which provides a convenient way to 
    create PT simulations across a temperature range. 
    
    """

    def __init__(self, thermodynamic_states, sampler_states=None, database=None, mpicomm=None, platform=None, parameters={}):
        self._check_self_consistency(thermodynamic_states)
        super(ParallelTempering, self).__init__(thermodynamic_states, sampler_states=sampler_states, database=database, mpicomm=mpicomm, platform=platform, parameters=parameters)

    def _check_self_consistency(self, thermodynamic_states):
        """Checks that each state is identical except for the temperature, as required for ParallelTempering."""

        for s0 in thermodynamic_states:
            for s1 in thermodynamic_states:
                if s0.pressure != s1.pressure:
                    raise(ValueError("For ParallelTempering, ThermodynamicState objects cannot have different pressures!"))


        with IgnoreBarostat(thermodynamic_states):  # Allows us to compare state equality modulo barostat temperature and RNG seed; see class definition below.
            
            for s0 in thermodynamic_states:
                for s1 in thermodynamic_states:
                    if s0.system.__getstate__() != s1.system.__getstate__():
                        raise(ValueError("For ParallelTempering, ThermodynamicState objects cannot have different systems!"))


    def _compute_energies(self):
        """Compute reduced potentials of all replicas at all states (temperatures).

        Notes
        -----

        Because only the temperatures differ among replicas, we replace 
        the generic O(N^2) replica-exchange implementation with an O(N) implementation.
        """

        start_time = time.time()
        logger.debug("Computing energies...")
                
        for replica_index in range(self.n_states):
            potential_energy = self.sampler_states[replica_index].potential_energy
            for state_index in range(self.n_states):
                # Compute reduced potential
                beta = 1.0 / (kB * self.thermodynamic_states[state_index].temperature)
                self.u_kl[replica_index,state_index] = beta * potential_energy

        end_time = time.time()
        elapsed_time = end_time - start_time
        time_per_energy = elapsed_time / float(self.n_states)
        logger.debug("Time to compute all energies %.3f s (%.3f per energy calculation).\n" % (elapsed_time, time_per_energy))


    @classmethod
    def create(cls, system, coordinates, filename, T_min=None, T_max=None, temperatures=None, n_temps=None, pressure=None, mpicomm=None, platform=None, parameters={}):
        """Create a new ParallelTempering simulation.
        
        Parameters
        ----------

        system : simtk.openmm.System
            The temperature of the system.
        coordinates : list([simtk.unit.Quantity]), shape=(n_replicas, n_atoms, 3), unit=Length
            The starting coordinates for each replica
        filename : string 
            name of NetCDF file to bind to for simulation output and checkpointing
        T_min : simtk.unit.Quantity, unit=Temperature, default=None
            The lowest temperature of the Parallel Temperature run
        T_max : simtk.unit.Quantity, unit=Temperature, default=None
            The highest temperature of the Parallel Temperature run
        n_temps : int, default=None
            The number of replicas.
        temperatures : list([simtk.unit.Quantity]), unit=Temperature
            Explicit list of each temperature to use
        pressure : simtk.unit.Quantity, unit=Pa, default=None
            If specified, perform NPT simulation at this temperature.
        mpicomm : mpi4py communicator, default=None
            MPI communicator, if parallel execution is desired.      
        parameters (dict) - Optional parameters to use for specifying simulation
            Provided keywords will be matched to object variables to replace defaults.
            
        Notes
        -----
        
        The parameters of this function are different from  ReplicaExchange.create_repex().
        The optional arguments temperatures is incompatible with (T_min, T_max, and n_temps).  
        Only one of those two groups should be specified.  
        
        If T_min, T_max, and n_temps are specified, temperatures will be exponentially
        spaced between T_min and T_max.
        """

        if temperatures is not None:
            logger.info("Using provided temperatures")
            n_temps = len(temperatures)
        elif (T_min is not None) and (T_max is not None) and (n_temps is not None):
            temperatures = [ T_min + (T_max - T_min) * (np.exp(float(i) / float(n_temps-1)) - 1.0) / (np.e - 1.0) for i in range(n_temps) ]
        else:
            raise ValueError("Either 'temperatures' or 'T_min', 'T_max', and 'n_temps' must be provided.")

        thermodynamic_states = [ ThermodynamicState(system=system, temperature=temperatures[i], pressure=pressure) for i in range(n_temps) ]
    
        coordinates = replica_exchange.validate_coordinates(coordinates, thermodynamic_states)    
    
        if mpicomm is None or (mpicomm.rank == 0):
            database = netcdf_io.NetCDFDatabase(filename, thermodynamic_states, coordinates)  # To do: eventually use factory for looking up database type via filename
        else:
            database = None
        
        sampler_states = [SamplerState(thermodynamic_states[k].system, coordinates[k], platform=platform) for k in range(len(thermodynamic_states))]
        repex = cls(thermodynamic_states, sampler_states, database, mpicomm=mpicomm, platform=platform, parameters=parameters)

        # Override title.
        repex.title = 'Parallel tempering simulation created using ParallelTempering class of repex.py on %s' % time.asctime(time.localtime())        

        repex._run_iteration_zero()
        return repex


class IgnoreBarostat(object):
    """A context manager that temporarily disables the barostat temperature
    and random seed, for testing get_state() equality.
    
    Notes
    -----

    Now we do a little hack where we temporarily set all the barostat temperatures
    and random number seeds to 1 So that the system objects can be 
    compared for equality modulo barostat temperature and RNG seed.
    Afterwards we reset the temperatures and seeds to the original values
    
    
    Examples
    --------
    
    with IgnorePressure(thermodynamic_states):
        pass
    """


    def get_num_barostats(self, state):
        """Get the number of barostats, raising an error if there are multiple."""
        forces = state.system.getForces()
        num_barostats = 0
        for f in forces:
            if f.__class__.__name__ == "MonteCarloBarostat":
                temperature = f.getTemperature()            
                seed = f.getRandomNumberSeed()
                num_barostats += 1

        if num_barostats > 1:
            raise(ValueError("Found multiple barostats!"))
        
        return num_barostats


    def get_barostat_state(self, state):
        """Return temperature and seed from the barostat."""
        
        if self.num_barostats <= 0:
            raise(ValueError("Found no barostats!"))
        
        forces = state.system.getForces()
        for f in forces:
            if f.__class__.__name__ == "MonteCarloBarostat":
                temperature = f.getTemperature()            
                seed = f.getRandomNumberSeed()
        
        return temperature, seed

    def set_barostat_state(self, state, temperature, seed):
        """Set the temperature and seed from the barostat."""
        
        if self.num_barostats <= 0:
            raise(ValueError("Found no barostats!"))
                
        forces = state.system.getForces()
        for f in forces:
            if f.__class__.__name__ == "MonteCarloBarostat":
                f.setTemperature(temperature)
                f.setRandomNumberSeed(seed)
    
    
    def __init__(self, thermodynamic_states):
        
        num_barostats = np.array([self.get_num_barostats(state) for state in thermodynamic_states])
        assert num_barostats.min() == num_barostats.max()
        self.num_barostats = num_barostats[0]
        
        self.thermodynamic_states = thermodynamic_states

    
    def __enter__(self):
        self.temperatures = []
        self.seeds = []
        if self.num_barostats > 0:
            for k, state in enumerate(self.thermodynamic_states):
                temperature, seed = self.get_barostat_state(state)
                logger.debug("Initial: State %d temperature and random seed are %s %s" % (k, temperature, seed))
                self.temperatures.append(temperature)
                self.seeds.append(seed)
                self.set_barostat_state(state, 1, 1)
                temperature, seed = self.get_barostat_state(state)
                logger.debug("Intermediate: State %d temperature and random seed are %s %s" % (k, temperature, seed))
            
            
        return self

    
    def __exit__(self, ty, val, tb):
        if self.num_barostats > 0:
            for k, state in enumerate(self.thermodynamic_states):
                temperature = self.temperatures[k]
                seed = self.seeds[k]
                self.set_barostat_state(state, temperature, seed)
                logger.debug("Final: State %d temperature and random seed are %s %s" % (k, temperature, seed))

        return False
