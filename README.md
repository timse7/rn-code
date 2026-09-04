# RN Code
Code for my computer networks (Rechnernetze) lecture at University of Klagenfurt (https://itec.aau.at/)

The examples are plain Python scripts, each runnable on its own.

## Setup

```bash
make venv                 # create .venv and install dependencies
source .venv/bin/activate
```

Or without `make`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

## Usage

```bash
python foo.py             # run a single example
make format               # auto-format and fix imports (ruff)
make lint                 # style and error checks (ruff)
make clean                # remove caches and build artifacts
```

## Contents

| File | Description |
|------|-------------|
| _tbd_ | _tbd_ |
