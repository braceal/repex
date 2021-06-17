#!/bin/bash
#SBATCH --exclusive
#SBATCH --gres=gpu:1
#SBATCH -A lambda
#SBATCH -J repex
#SBATCH -t 00:10:00

set -x
rankspernode=2 #4
totalranks=$(( ${SLURM_NNODES} * ${rankspernode} ))

# Run repex
srun -l -u --wait=30 -N ${SLURM_NNODES} -n ${totalranks} -c $(( 40 / ${rankspernode} )) --cpu_bind=cores --mpi=pmi2 ./bin/lambda_run.sh
