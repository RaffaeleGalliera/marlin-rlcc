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
          "numpy",
          "stable-baselines3",
          "sb3_contrib",
          'optuna',
          "docker",
          "netifaces",
          "pytest",
          "wandb",
          "seaborn",
          "paramiko",
          "scp"
      ],
      python_requires=">=3.8.0",
      author="Raffaele Galliera",
      author_email="rgalliera@ihmc.org",
      description="Description",
      )
