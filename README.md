# [json_analysis](https://github.com/europanite/json_analysis "json_analysis")

[![Python](https://img.shields.io/badge/python-3.9|%203.10%20|%203.11|%203.12|%203.13-blue)](https://www.python.org/)
![OS](https://img.shields.io/badge/OS-Linux%20%7C%20macOS%20%7C%20Windows-blue)

[![Python Lint](https://github.com/europanite/json_analysis/actions/workflows/lint.yml/badge.svg)](https://github.com/europanite/json_analysis/actions/workflows/lint.yml)
[![CodeQL Advanced](https://github.com/europanite/json_analysis/actions/workflows/codeql.yml/badge.svg)](https://github.com/europanite/json_analysis/actions/workflows/codeql.yml)
[![Pytest](https://github.com/europanite/json_analysis/actions/workflows/pytest.yml/badge.svg)](https://github.com/europanite/json_analysis/actions/workflows/pytest.yml)
[![pages](https://github.com/europanite/json_analysis/actions/workflows/pages/pages-build-deployment/badge.svg)](https://github.com/europanite/json_analysis/actions/workflows/pages/pages-build-deployment)

A Json Analysis Tool.

## Requirements

- Python 3.9+
- Dependencies:
    - python3-venv
    - ijson



## Usage

Run the script with default settings:
Example with custom arguments:


### 0. Create virtual environment

```bash
# create a virtual environment
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
```

### 0. Preparation
```bash
# Sample Jons Data Download 
wget -P data -c http://images.cocodataset.org/annotations/annotations_trainval2017.zip
unzip -o ./data/annotations_trainval2017.zip -d data
```

### 1. Run

```bash
# Analize
python3 ./src/analyze_structure.py \
./data/annotations/instances_train2017.json

# Extract
python3 ./src/extract_one_example.py \
./data/annotations/instances_train2017.json \
-o ./data/annotations/instances_train2017_extracted.json
```

### 2. Test

```bash
pip install -r requirements.test.txt
pytest
```

### 3. Deactivate environment

```bash
deactivate
```

---

# License
- Apache License 2.0