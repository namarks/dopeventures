from setuptools import setup, find_packages

setup(
    name="dopetracks",
    version="0.1.2",
    author="Nick Marks",
    author_email="nmarkspdx@gmail.com",
    url="https://github.com/namarks/dopeventures",  # GitHub repo URL
    packages=find_packages(),  
    # package_dir={"": "dopetracks/dopetracks"},              # Base directory for packages
    python_requires=">=3.11.11",
    entry_points={
        "console_scripts": [
            # Add CLI commands if needed, e.g., 'dopetracks=dopetracks_summary.main:main',
        ],
    },
)
