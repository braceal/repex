from repex.thermodynamics import ThermodynamicState
from repex.replica_exchange import ReplicaExchange

import logging
logger = logging.getLogger(__name__)


class HamiltonianExchange(ReplicaExchange):
    """Hamiltonian exchange simulation facility.

    HamiltonianExchange provides an implementation of a Hamiltonian exchange simulation based on the ReplicaExchange class.
    It provides several convenience classes and efficiency improvements, and should be preferentially used for Hamiltonian
    exchange simulations over ReplicaExchange when possible.
    
    Notes
    -----
    
    To create a new HamiltonianExchange object, use the `create_repex()`
    class method.  
    
    """

    def __init__(self, thermodynamic_states, sampler_states=None, database=None, mpicomm=None, platform=None, parameters={}):
        self._check_self_consistency(thermodynamic_states)
        super(HamiltonianExchange, self).__init__(thermodynamic_states, sampler_states=sampler_states, database=database, mpicomm=mpicomm, platform=platform, parameters=parameters)

    def _check_self_consistency(self, thermodynamic_states):
        """Checks that each state has the same temperature and pressure, as required for HamiltonianExchange."""
        
        for s0 in thermodynamic_states:
            for s1 in thermodynamic_states:
                if s0.pressure != s1.pressure:
                    raise(ValueError("For HamiltonianExchange, ThermodynamicState objects cannot have different pressures!"))

        for s0 in thermodynamic_states:
            for s1 in thermodynamic_states:
                if s0.temperature != s1.temperature:
                    raise(ValueError("For HamiltonianExchange, ThermodynamicState objects cannot have different temperatures!"))


    @classmethod
    def create(cls, reference_state, systems, coordinates, filename, mpicomm=None, platform=None, parameters={}):
        """Create a new Hamiltonian exchange simulation object.

        Parameters
        ----------

        temperature : simtk.unit.Quantity, optional, units compatible with simtk.unit.kelvin
            The temperature of the system.

        reference_state : ThermodynamicState
            reference state containing all thermodynamic parameters 
            except the system, which will be replaced by 'systems'
        systems : list([simt.openmm.System])
            list of systems to simulate (one per replica)
        coordinates : simtk.unit.Quantity, shape=(n_atoms, 3), unit=Length
            coordinates (or a list of coordinates objects) for initial 
            assignment of replicas (will be used in round-robin assignment)
        filename : string 
            name of NetCDF file to bind to for simulation output and checkpointing
        mpicomm : mpi4py communicator, default=None
            MPI communicator, if parallel execution is desired.      
        kwargs (dict) - Optional parameters to use for specifying simulation
            Provided keywords will be matched to object variables to replace defaults.
            
        Notes
        -----
        
        The parameters of this function are different from  ReplicaExchange.create_repex().

        """
      
        thermodynamic_states = [ ThermodynamicState(system=system, temperature=reference_state.temperature, pressure=reference_state.pressure) for system in systems ]
        return super(cls, HamiltonianExchange).create(thermodynamic_states, coordinates, filename, mpicomm=mpicomm, platform=platform, parameters=parameters)
