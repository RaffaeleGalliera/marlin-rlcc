# [WIP] Marlin - Mockets Augmented with a Reinforcement Learning Agent

## Setup

1. Run `git submodule update --init --recursive` after cloning for pulling
   JMockets submodule and its dependencies
2. Create a Python Virtual Environment and
   run `pip install -r requirements. txt` to install Python dependencies
3. If you need to generate new protobuf go to the project's root folder:
   1. `$ python3 -m grpc_tools.protoc -I. --python_out=./protos --grpc_python_out=./protos protos/congestion_control.proto`
   2. `$ mv protos/protos/* protos && rm -rf protos/protos`
4. Run `python train.py` to begin the training phase and start the Data
   Processing server (localhost:50051)
5. Follow JMockets documentation and start the application

## Troubleshooting
- JMockets is dependent on:  _jmockets-proxy, jmockets-test-harness, 
  nomads/jutil, nomads/measure_. If you have issues cloning JMockets submodules 
  recursively:
  - Check you have access to JMockets and the aforementioned 
    dependencies repositories.
  - If you do have access, but for some reason cannot HTTP login to NOMADS 
    GitLab while your SSH-key access is enabled, you can use:
    `git config --global url."ssh://git@gitn.ihmc.us:22000".insteadOf "https://gitn.ihmc.us"`