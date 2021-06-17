"""
Example illustrating the parallel tempering facility of repex.

This example loads the PDB file for a terminally-blocked alanine peptide and parameterizes it
using the amber10 collection of forcefield parameters.

"""

#=============================================================================================
# TURN DEBUG LOGGING ON
#=============================================================================================

import logging
logging.basicConfig(level=logging.DEBUG)

#=============================================================================================
# RUN PARALLEL TEMPERING SIMULATION
#=============================================================================================

import os
import mpi4py
mpi4py.rc.initialize = False
from mpi4py import MPI  # noqa

print("setup mpi")
# init mpi4py:
MPI.Init_thread()
# get communicator: duplicate from comm world
mpicomm = MPI.COMM_WORLD.Dup()
# now match ranks between the mpi comm and the nccl comm
os.environ["WORLD_SIZE"] = str(mpicomm.Get_size())
os.environ["RANK"] = str(mpicomm.Get_rank())
print(os.environ["WORLD_SIZE"])
print("rank",os.environ["RANK"])


output_filename = "new_repex.nc" #"repex.nc" # name of NetCDF file to store simulation output

# If simulation file already exists, try to resume.
import os.path
resume = False
if os.path.exists(output_filename):
    resume = True

if resume:
    try:
        print("Attempting to resume existing simulation...")
        import repex
        simulation = repex.resume(output_filename)
        
        # Extend the simulation by a few iterations.
        niterations_to_extend = 10
        simulation.extend(niterations_to_extend)    

    except Exception as e:
        print("Could not resume existing simulation due to exception:")
        print(e)
        print("")
        resume = False

if not resume:
    print("Starting new simulation...")

    # Set parallel tempering parameters
    from simtk import unit
    # Temperatures will be exponentially (geometrically) spaced by default
    T_min = 273.0 * unit.kelvin # minimum temperature for parallel tempering ladder
    T_max = 600.0 * unit.kelvin # maximum temperature for parallel tempering ladder
    n_temps = 10 # number of temperatures

    collision_rate = 20.0 / unit.picosecond # collision rate for Langevin dynamics
    timestep = 2.0 * unit.femtosecond # timestep for Langevin dynamics
    
    # Load forcefield.
    from simtk.openmm import app
    forcefield = app.ForceField("amber10.xml", "amber10_obc.xml")

    # Load PDB file.
    pdb_filename = 'alanine-dipeptide.pdb'
    pdb = app.PDBFile(pdb_filename)

    # Create a model containing all atoms from PDB file.
    model = app.modeller.Modeller(pdb.topology, pdb.positions)

    # Create OpenMM system and retrieve atomic positions.
    system = forcefield.createSystem(model.topology, nonbondedMethod=app.NoCutoff, constraints=app.HBonds)
    replica_positions = [model.positions for i in range(n_temps)] # number of replica positions as input must match number of replicas

    # Create parallel tempering simulation object.
    import repex
   

    #mpicomm = repex.dummympi.DummyMPIComm()
    parameters = {"number_of_iterations" : 10}
    parameters = {"collision_rate" : collision_rate}
    from repex import ParallelTempering
    simulation = ParallelTempering.create(system, replica_positions, output_filename, T_min=T_min, T_max=T_max, n_temps=n_temps, mpicomm=mpicomm, parameters=parameters)

    # Run the parallel tempering simulation.
    simulation.run()

