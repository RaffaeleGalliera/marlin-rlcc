# [WIP] Marlin - Mockets Augmented with a Reinforcement Learning Agent

## Setup
1. Run `git submodule update --init --recursive` after cloning for pulling dependencies
2. Build the Image `docker build -t rgalliera/marlin:0.1 . `
3. Start your ContainerNet topology (or use the default found in `third_party`) `sudo python3 network_generator.py`
4. Run the container (dev mode) `docker run --gpus all --ipc=host -v ${PWD}:/home/devuser/dev:Z -it --rm rgalliera/marlin:0.1`
5. If you need to generate new protobuf go to the project's root folder:
   1. `$ python -m grpc_tools.protoc -I. --python_out=./protos --grpc_python_out=./protos protos/congestion_control.proto`
   2. `$ mv protos/protos/* protos && rm -rf protos/protos`
6. Run `python third-party/rl-baselines3-zoo/train.py --algo sac --env Marlin-v1 --track --wandb-project-name <project_name> --eval-freq 50 --eval-episodes 10`
