# [WIP] MARLIN - Mockets Augmented with a Reinforcement Learning Agent

This repository contains a container-based version of MARLIN, a Soft Actor-Critic Reinforcement Learning environment for Congestion Control.

First designed to be trained and tested on real networks, the implementation included here, which is stil work in progress, substitutes the real network with [ContainerNet](https://containernet.github.io/) to deploy the containers involved in the networking process and linking them accordigly.
An example of network topology can be found in `/third_party/network_generator.py`.

## Important
A new version of the partnering protocol, i.e. Mockets, is under development along with optimizing the usage of ContainerNet.

## Setup
1. Install [ContainerNet](https://containernet.github.io/#get-started) on your hosting machine
2. Install rpyc on your hosting machine `sudo python -m pip install rpyc`
3. Run `git submodule update --init --recursive` after cloning for pulling dependencies
4. Build the Image `docker build -t marlin:0.1 .`
5. Start your ContainerNet topology (or use the default found in `third_party`) `sudo python3 network_generator.py`
6. Run the container (with local binding for dev) `docker run --gpus all --ipc=host -v /var/run/docker.sock:/var/run/docker.sock -v ${PWD}:/home/devuser/dev:Z -it --rm marlin:0.1`
7. Run `python third-party/rl-baselines3-zoo/train.py --algo sac --verbose 1 --seed 9 --env Marlin-v1 --track --wandb-project-name marlin_test-packet_reward --eval-freq 50 --eval-episodes 10 --env-kwargs delay_start:500 bandwidth_var:0.256 delay_var:125 loss_var:3 max_duration:800`


## If you are using Mockets, MGEN, and `network_generator.py`
Remember to build the respective `mgen` and `mockets` images found in their respective subfolders in `third_party` naming them `mgen:0.1` and `mockets:0.1`.

## If changing the statistics/state and you need to generate a new protobuf go to the project's root folder:
1. `python -m grpc_tools.protoc -I. --python_out=./protos --grpc_python_out=./protos protos/congestion_control.proto`
2. `mv protos/protos/* protos && rm -rf protos/protos`
