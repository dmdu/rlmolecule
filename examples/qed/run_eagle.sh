""" Wrapper script to set the run_id and 
copy the config file to the output directory for a given experiment
"""

# run_id is the first parameter, config is the second
run_id="$1"
config_file="$2"

if [ "$1" == "" ]; then
    echo "Need to pass <run_id> as first argument"
    exit
fi
if [ "$2" == "" ]; then
    echo "Need to pass <config_file> as second argument"
    exit
fi

WORKING_DIR="/projects/rlmolecule/jlaw/qed/${run_id}"
mkdir -p $WORKING_DIR

# copy the config file with the rest of the results
SCRIPT_CONFIG="$WORKING_DIR/run.yaml"
cp $config_file $SCRIPT_CONFIG
# also set the run_id in the config file
sed -i "s/qed_example/$run_id/" $SCRIPT_CONFIG

echo """#!/bin/bash
#SBATCH --account=bpms
#SBATCH --time=4:00:00  
#SBATCH --job-name=$run_id
##SBATCH --mail-type=BEGIN,END,FAIL
##SBATCH --mail-user=$USER@nrel.gov
#SBATCH --output=$WORKING_DIR/%j-sbatch.out
# --- Policy Trainer ---
#SBATCH --nodes=1
#SBATCH --gres=gpu:2
# --- MCTS Rollouts ---
#SBATCH hetjob
#SBATCH -N 5


export WORKING_DIR=$WORKING_DIR
mkdir -p $WORKING_DIR
export START_POLICY_SCRIPT="\$WORKING_DIR/\$JOB/.policy.sh"
export START_ROLLOUT_SCRIPT="\$WORKING_DIR/\$JOB/.rollout.sh"
# make sure the base folder of the repo is on the python path
export PYTHONPATH="$(readlink -e ../../):\$PYTHONPATH"

cat << EOF > "\$START_POLICY_SCRIPT"
#!/bin/bash
source /nopt/nrel/apps/anaconda/5.3/etc/profile.d/conda.sh; 
conda activate /projects/rlmolecule/pstjohn/envs/tf2_gpu
python -u optimize_qed.py --train-policy --config $SCRIPT_CONFIG
EOF

cat << EOF > "\$START_ROLLOUT_SCRIPT"
#!/bin/bash
source /nopt/nrel/apps/anaconda/5.3/etc/profile.d/conda.sh; 
conda activate /projects/rlmolecule/pstjohn/envs/tf2_cpu
python -u optimize_qed.py --rollout --config $SCRIPT_CONFIG
EOF

chmod +x "\$START_POLICY_SCRIPT" "\$START_ROLLOUT_SCRIPT"

srun --pack-group=0 \
     --job-name="az-policy" \
     --output=$WORKING_DIR/%j-gpu.out \
     "\$START_POLICY_SCRIPT" &

# there are 36 cores on each eagle node.
srun --pack-group=1 \
     --ntasks-per-node=9 \
     --cpus-per-task=4 \
     --job-name="az-rollout" \
     --output=$WORKING_DIR/%j-mcts.out \
     "\$START_ROLLOUT_SCRIPT"
""" > $WORKING_DIR/.submit.sh

sbatch $WORKING_DIR/.submit.sh
