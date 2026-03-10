# UDSv4 REDCap QC Validator

**Production-ready Quality Control validation system for NACC UDSv4 REDCap data**

Automated data extraction, validation, and quality control for REDCap-based UDSv4 research data, ensuring compliance with NACC data quality standards.

## 🚀 Quick Start

### Prerequisites

- Python 3.11+ installed
- REDCap API credentials with UDSv4 project access
- Poetry for dependency management

### Installation

**1. Install Poetry** (if not already installed)

Windows PowerShell:
```powershell
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -
```

Linux/macOS:
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

**2. Clone and Setup**

```bash
git clone <repository-url>
cd udsv4-redcap-qc-validator
poetry install
```

**3. Configure Environment**

Copy `.env.template` to `.env` and configure:

```bash
cp .env.template .env
```

Edit `.env` with your REDCap credentials:
```env
REDCAP_API_TOKEN=your_token_here
REDCAP_API_URL=https://your-redcap-instance.org/api/
REDCAP_REPORT_ID=your_report_id
```

### Usage

**Interactive Mode** (Recommended):
```bash
poetry run udsv4-qc
```

**Command-Line Mode**:
```bash
poetry run udsv4-qc -i YOUR_INITIALS
```

**With Options**:
```bash
# Detailed reports with passed rules log
poetry run udsv4-qc -i JT -dr -ps

# Target specific participant and event  
poetry run udsv4-qc -i JT --ptid 12345 --event udsv4visit_arm_1
```

### Available Commands (Interactive Mode)

After entering your initials, you'll see:
- `run` - Run QC validation (complete visits)
- `run -dr` - Run with detailed reports
- `run -dr -ps` - Run with detailed + passed rules log
- `status` - View environment, config, and readiness
- `help` - Show command reference
- `exit` - Exit the interface

### Output

QC validation generates:
- **Error Reports**: CSV files with validation failures
- **Generation Summary**: Overview of QC run statistics
- **Validation Logs**: Detailed rule checking results (if `-ps` flag used)
- **Fetched Data**: Audit trail of REDCap data retrieved

All outputs saved to: `output/QC_CompleteVisits_<DATE>_<TIME>/`

## 📚 Documentation

Comprehensive documentation available in [`docs/`](docs/):

- [**System Architecture**](docs/README.md) - Technical overview and design
- [**Configuration Management**](docs/configuration-management.md) - Setup and customization
- [**Data Fetching System**](docs/data-fetching-system.md) - REDCap integration
- [**QC Validation Engine**](docs/qc-validation-engine.md) - Core validation logic
- [**Output Reporting**](docs/output-reporting.md) - Report generation
- [**Logging & Monitoring**](docs/logging-monitoring.md) - Audit trails

## 🛠 Development

**Run Tests**:
```bash
poetry run pytest tests/ -v
```

**Code Quality**:
```bash
poetry run ruff check src/ tests/
poetry run mypy src/
```

**Build Package**:
```bash
poetry build
```

## ⚙️ System Requirements

- **Python**: 3.11, 3.12, or 3.13
- **OS**: Windows, Linux, macOS
- **Memory**: 2GB RAM minimum
- **REDCap**: API access with export permissions

## 📋 REDCap Setup

Required REDCap instruments (available in `redcap-tools/`):
- **Quality Control Check Form** (`QualityControlCheck_2025-09-10_1403.zip`)

Import into REDCap:
1. **Project Setup** → **Online Designer**
2. Import zip file as new instrument
3. Add to all UDSv4 events
4. Configure user permissions for API access

> ⚠️ **Important**: QC Status fields are required for validation workflow and data export step.

## 🔧 Technologies

- **Python 3.11+** - Core language
- **Poetry** - Dependency management
- **REDCap API** - Data extraction
- **Cerberus** - Schema validation
- **pandas** - Data processing
- **Rich** - Enhanced CLI

## 📄 License

This project is licensed under the **Mozilla Public License 2.0** - see [LICENSE](LICENSE) file.

**Third-Party Code**: Incorporates code from [`naccdata/nacc-form-validator`](https://github.com/naccdata/nacc-form-validator) (MPL-2.0 licensed). The `nacc_form_validator/` directory is maintained as immutable external code - see [docs/external-package-policy.md](docs/external-package-policy.md).

## 🤝 Contributing

Contributions welcome! See comprehensive documentation for development guidelines:
- Development setup and workflow in [docs/README.md](docs/README.md)
- Testing requirements and coverage expectations
- Code quality standards (Ruff, mypy, pytest)

## 📞 Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Review documentation in [`docs/`](docs/)
- Check [CHANGELOG.md](CHANGELOG.md) for recent updates

---

**Version**: 1.0.0 | **Status**: Production/Stable | **By**: UNM SDCC Dev Team | **For**: NACC Alzheimer's Disease Research Center
