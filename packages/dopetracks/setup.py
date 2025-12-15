from setuptools import setup, find_packages

setup(
    name="dopetracks",
    version="0.1.0",
    author="Nick Marks",
    author_email="nmarkspdx@gmail.com",
    url="https://github.com/namarks/dopeventures",  # GitHub repo URL
    packages=find_packages(where="."),
    package_dir={"": "."},  # Package is at packages/dopetracks/
    install_requires=[
        "fastapi>=0.104.0",
        "uvicorn[standard]>=0.24.0",
        "pandas>=2.0.0",
        "numpy>=1.24.0",
        "spotipy>=2.22.0",
        "python-dotenv>=1.0.0",
        "requests>=2.31.0",
        "typedstream>=0.3.0",
        "tqdm>=4.65.0",
        "python-multipart>=0.0.6",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "ipython>=8.0.0",
        ],
        "flask": [
            "flask>=2.3.0",
            "flask-session>=0.5.0",
        ]
    },
    python_requires=">=3.9",
    # Entry point removed - use start_multiuser.py instead
)
