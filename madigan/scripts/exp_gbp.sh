#!/bin/bash

# BASEPATH="../experiments/"
# 
# EXP="IQN_OU_trans_0.05_unit_0.05"
# NSTEPS=400
# 
# FROM_CONFIG=true


# including parse_yaml func
. ../parse_yaml.sh;

# parse yaml file and load variables

#experiments=( "ou_sortinoB_exp_1.0_nstep20" "ou_sortinoB_exp_1.02_nstep20" "ou_sortinoB_exp_1.05_nstep20" );
experiments=( "iqn_gbpusd_daily_priceonly_ret_lev20_unit.05_trans_.001" "iqn_gbpusd_daily_priceonly_ret_lev20_unit.05_trans_.001_dropout.4" );

for config_name in "${experiments[@]}"
do
    eval $(parse_yaml $config_name.yaml "config_")

    BASEPATH="$config_basepath"

    EXP="$config_experiment_id"
    NSTEPS="$config_train_steps"
    if [ "$1" ]; then
        NSTEPS="$1";
    fi
    CONFIGPATH="$BASEPATH"/"$EXP"

# save to local config folder
    echo Making dir ../experiments/"$EXP" "(if doesn\'t exist and copying config.yaml over)";
    mkdir -p .../experiments/"$EXP" && cp -u -p ./$config_name.yaml .../experiments/"$EXP"/config.yaml
# save to experiment folder - where data for logs/models etc are
    echo Making dir "$CONFIGPATH (if doesn\'t exist)";
    mkdir -p "$CONFIGPATH" && cp -u -p ./$config_name.yaml "$CONFIGPATH"/config.yaml

    echo attempting to train for "$NSTEPS" steps;
    python ../train.py "$CONFIGPATH"/config.yaml --nsteps "$NSTEPS"
done

