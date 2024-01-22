from setuptools import setup, find_packages

setup(
    name='hbm',
    version='0.1',
    packages=find_packages(),
    install_requires=[
        # List any dependencies your script may have
    ],
    entry_points={
        'console_scripts': [
            'delineate = hbm.hydro:main',
        ],
    },
)