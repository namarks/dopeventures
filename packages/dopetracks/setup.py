from setuptools import setup, find_packages

setup(
    name="dopetracks_summary",
    version="0.1.0",
    author="Nick Marks",
    author_email="nmarkspdx@gmail.com",
    url="https://github.com/nmarks/dopeventures",  # GitHub repo URL
    packages=find_packages(),  # Look for packages in src/
    # package_dir={"": "dopetracks/dopetracks"},              # Base directory for packages
    install_requires=[
        Flask==3.1.0
        flask_session==0.8.0
        ipython==8.12.3
        numpy==2.2.1
        pandas==2.2.3
        python-dotenv==1.0.1
        pytypedstream==0.1.0
        Requests==2.32.3
        setuptools==75.6.0
        spotipy==2.24.0
        tqdm==4.67.1
    ],
    python_requires=">=3.11.11",

    entry_points={
        "console_scripts": [
            # Add CLI commands if needed, e.g., 'dopetracks=dopetracks_summary.main:main',
        ],
    },
)
