# [WIP] Marlin - Mockets Augmented with a Reinforcement Learning Agent

This repository contains a Work in Progress container-based version of MARLIN, a Soft Actor-Critic Reinforcement Learning agent for Congestion Control.
First designed to be trained and tested on real networks, the implementation contained here uses [ContainerNet]{https://containernet.github.io/} to deploy the containers involved in the networking process and linking them accordigly.
An example of network topology can be found in '/third_party/network_generator.py'.

## Setup
1. Install [ContainerNet]{https://containernet.github.io/#get-started}
2. Run `git submodule update --init --recursive` after cloning for pulling dependencies
3. Build the Image `docker build -t rgalliera/marlin:0.1 .`
4. Start your ContainerNet topology (or use the default found in `third_party`) `sudo python3 network_generator.py`
5. Run the container (with local binding for dev) `docker run --gpus all --ipc=host -v /var/run/docker.sock:/var/run/docker.sock -v ${PWD}:/home/devuser/dev:Z -it --rm rgalliera/marlin:0.1`
6. If you need to generate new protobuf go to the project's root folder:
   1. `$ python -m grpc_tools.protoc -I. --python_out=./protos --grpc_python_out=./protos protos/congestion_control.proto`
   2. `$ mv protos/protos/* protos && rm -rf protos/protos`
7. Run `python third-party/rl-baselines3-zoo/train.py --algo sac --env Marlin-v1 --track --wandb-project-name <project_name> --eval-freq 50 --eval-episodes 10`


## If using `network_generator.py`
Remember to build the respective `mgen` and `mockets` images found in their respective subfolders in `third_party` naming them `mgen:0.1` and `mockets:0.1`.