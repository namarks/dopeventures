from setuptools import setup, find_packages

setup(
    name="dopetracks_summary",
    version="0.1.0",
    packages=find_packages(where="src"),  # Look for packages in src/
    package_dir={"": "src"},              # Base directory for packages
    install_requires=[
        # Add your dependencies here
        # e.g., 'pandas', 'numpy'
    ],
    entry_points={
        "console_scripts": [
            # Add CLI commands if needed, e.g., 'dopetracks=dopetracks_summary.main:main',
        ],
    },
)
