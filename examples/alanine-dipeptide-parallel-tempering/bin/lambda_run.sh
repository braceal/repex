#!/bin/bash
#set -Eeuo pipefail
set -x

# SLURM settings
export WORLD_SIZE=$(( ${SLURM_TASKS_PER_NODE} * ${SLURM_NNODES} ))
export RANK=${SLURM_PROCID}
#export LOCAL_RANK=$(( ${SLURM_PROCID} % ${SLURM_TASKS_PER_NODE} ))
export LOCAL_RANK=$(( ${SLURM_PROCID} % $(echo ${SLURM_TASKS_PER_NODE} |awk '{split($1,a,"("); print a[1]}') ))
export MASTER_PORT=29500
export MASTER_ADDR=${SLURM_LAUNCH_NODE_IPADDR}

echo ${SLURM_PROCID} ${SLURM_TASKS_PER_NODE} ${LOCAL_RANK}

# Determine gpu
gpu=$(( 2 * ${LOCAL_RANK} ))

# Launch code
python ./simulate-implicit.py # TODO: might need to pass in GPU?
