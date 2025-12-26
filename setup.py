from setuptools import setup, find_packages

setup(
    name="nrl_engine",
    version="1.0.0",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "numpy>=1.21.0",
        "pandas>=1.3.0",
        "scikit-learn>=1.0.0",
        "scipy>=1.7.0",
        "matplotlib>=3.4.0",
        "openpyxl>=3.0.0",
    ],
    entry_points={
        "console_scripts": [
            "nrl-eval=nrl_engine.run_eval:main",
        ],
    },
    author="Aaron",
    description="NRL match prediction engine with PIT-safe features and walk-forward evaluation",
)
