from setuptools import setup, find_packages

setup(name='marlin',
      version='0.1',
      packages=find_packages(),
      url="",
      license="",
      install_requires=[
          "grpcio==1.51.1",
          "grpcio-tools==1.44.0",
          "protobuf==3.20.3",
          "numpy==1.22.2",
          "stable-baselines3==1.8.0",
          "sb3_contrib==1.8.0",
          'optuna==3.2.0',
          "docker==6.1.2",
          "netifaces==0.11.0",
          "huggingface_sb3",
          "huggingface_hub",
          "pytest",
          "wandb==0.15.3",
          "seaborn",
          "paramiko==3.2.0",
          "scp",
          "rpyc==5.3.1",
          "pandas"
      ],
      python_requires=">=3.8.0",
      author="Raffaele Galliera",
      author_email="rgalliera@ihmc.org",
      description="Description",
      )
