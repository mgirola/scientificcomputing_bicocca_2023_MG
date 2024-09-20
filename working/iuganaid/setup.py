from setuptools import setup, find_packages

def read_requirements(file_path):
    with open(file_path, 'r') as file:
        return file.read().splitlines()


requirements_path = '/Users/lustrair/SynologyDrive/PhD/Corsi/ScientificComputingWithPython/scientificcomputing_bicocca_2023_MG-1/working/iuganaid/config/requirements.txt'

setup(
    name='iuganaid',
    version='0.0.1',
    description='A GUI to see pulses from a particle detector',
    author='Massimo Girola',
    license='MIT',
    packages=find_packages(),
    install_requires=read_requirements(requirements_path),
    python_requires='>=3.6'
)