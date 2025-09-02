# UDSv4 REDCap QC Validator Documentation

## Overview

This documentation provides comprehensive coverage of the UDSv4 REDCap Quality Control Validator system. The system is designed to fetch, validate, and process REDCap data for quality control purposes in the Uniform Data Set version 4 (UDSv4) data collection framework.

## Documentation Structure

### Core System Components

1. **[Project Guidelines](guidelines.md)**
   - Comprehensive project overview and operations
   - System architecture and component relationships
   - Operational workflows and processing modes
   - Integration points and quality framework

2. **[Configuration Management System](configuration-management.md)**
   - Centralized configuration handling
   - Environment variable management
   - Validation and error handling
   - Instrument and rule mapping configuration

3. **[Data Fetching System](data-fetching-system.md)**
   - REDCap API integration
   - ETL pipeline architecture
   - Data validation and transformation
   - Filter logic and payload construction

## System Architecture

The UDSv4 QC Validator follows a modular architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                     Application Layer                       │
├─────────────────────────────────────────────────────────────┤
│  Configuration Management  │  Data Fetching & Processing   │
│  • Environment Loading     │  • REDCap API Client          │
│  • Validation System       │  • ETL Pipeline               │
│  • Path Management         │  • Data Transformation        │
│  • Instrument Mapping      │  • Filter Logic Management    │
├─────────────────────────────────────────────────────────────┤
│                     Core Libraries                          │
│  • pandas • requests • pathlib • dataclasses • json        │
├─────────────────────────────────────────────────────────────┤
│                    External Systems                         │
│  • REDCap Database • File System • Environment Variables   │
└─────────────────────────────────────────────────────────────┘
```

## Key Concepts

### Instruments vs REDCap Fields

One of the fundamental concepts in the system is the distinction between **instruments** and **REDCap database fields**:

#### What are Instruments?

Instruments in this system are logical groupings of related REDCap form variables that represent complete data collection forms or assessments. Examples include:

- `a1_participant_demographics`
- `b6_geriatric_depression_scale` 
- `c2c2t_neuropsychological_battery_scores`

#### Why Instruments Don't Appear as REDCap Variables

The instrument names themselves do not exist as variables in the REDCap database payload. Instead, they serve as organizational concepts that:

1. **Group Related Variables**: Each instrument corresponds to a set of specific REDCap variables
2. **Map to Validation Rules**: Each instrument maps to specific JSON validation rule files
3. **Track Completion Status**: Each instrument has a corresponding completion variable (e.g., `a1_participant_demographics_complete`)
4. **Enable Modular Processing**: Allow the system to process and validate related variables together

#### Purpose and Rationale

This instrument-based organization provides several critical benefits:

1. **Logical Organization**: Creates meaningful groupings of related data elements
2. **Rule Management**: Enables systematic organization of validation rules
3. **Processing Control**: Allows selective processing of complete vs incomplete forms
4. **Quality Assurance**: Facilitates instrument-level quality checks and reporting
5. **Maintenance**: Simplifies system maintenance and rule updates
6. **Auditability**: Provides clear audit trails at the form level

### Configuration-Driven Architecture

The system uses a configuration-driven approach where behavior is controlled through:

- **Environment Variables**: Secure configuration of credentials and paths
- **Instrument Lists**: Defining which forms to process
- **Processing Modes**: Controlling validation and transformation behavior
- **Filter Logic**: Determining which records to process

### ETL Pipeline Pattern

The data processing follows a clean ETL pattern:

1. **Extract**: Fetch data from REDCap using configured parameters
2. **Transform**: Apply business rules and data transformations
3. **Load**: Save processed data with consistent naming and organization

## Getting Started

### Prerequisites

- REDCap API access with appropriate permissions
- Python environment with required dependencies
- Proper configuration of environment variables

### Quick Start

1. **Configure Environment Variables**:
   ```bash
   REDCAP_API_TOKEN=your_api_token
   REDCAP_API_URL=your_redcap_url
   PROJECT_ID=your_project_id
   JSON_RULES_PATH_I=path/to/initial/rules
   JSON_RULES_PATH_I4=path/to/initial4/rules
   JSON_RULES_PATH_F=path/to/followup/rules
   ```

2. **Initialize Configuration**:
   ```python
   from src.pipeline.config_manager import get_config
   config = get_config()
   ```

3. **Run ETL Pipeline**:
   ```python
   from src.pipeline.core.fetcher import RedcapETLPipeline
   pipeline = RedcapETLPipeline(config)
   result = pipeline.run()
   ```

## System Integration

### Configuration System Integration

The configuration system provides the foundation for all other components:

- **API Credentials**: Secure management of REDCap access
- **Path Configuration**: Centralized path management for rules and output
- **Processing Parameters**: Control of validation and transformation behavior
- **Performance Settings**: Optimization parameters for large datasets

### Data Fetching Integration

The data fetching system leverages configuration for:

- **API Payload Construction**: Building REDCap API requests with proper parameters
- **Filter Logic Selection**: Choosing appropriate filtering based on processing mode
- **Instrument Processing**: Determining which instruments and variables to process
- **Output Management**: Saving data with configured naming and organization

## Common Use Cases

### Quality Control Processing

The primary use case involves processing complete REDCap visits for quality control:

1. **Fetch Complete Visits**: Retrieve visits where all instruments are marked complete
2. **Apply Business Rules**: Validate data against UDSv4 quality control rules
3. **Generate Reports**: Create quality control reports for review
4. **Track Status**: Update QC completion status in REDCap

### Data Export and Transformation

The system can also be used for general data export and transformation:

1. **Selective Export**: Export specific instruments or date ranges
2. **Data Cleaning**: Apply data cleaning and transformation rules
3. **Format Conversion**: Convert data to different formats for analysis
4. **Integration**: Prepare data for integration with other systems

### Development and Testing

The system supports development and testing workflows:

1. **Test Mode**: Safe testing without affecting production data
2. **Configuration Validation**: Validate configuration before deployment
3. **Data Validation**: Test validation rules against sample data
4. **Performance Testing**: Assess system performance with large datasets

## Security and Compliance

### Data Protection

- **Credential Security**: Secure handling of API tokens and credentials
- **Data Encryption**: Secure transmission of data between systems
- **Access Control**: Proper access controls for sensitive data
- **Audit Logging**: Comprehensive logging for compliance and debugging

### Compliance Considerations

- **HIPAA Compliance**: Appropriate handling of protected health information
- **Data Retention**: Proper data retention and disposal policies
- **Access Logging**: Detailed logging of data access and modifications
- **Validation Documentation**: Comprehensive documentation of validation rules

## Performance and Scalability

### Performance Optimization

- **Efficient Data Processing**: Optimized pandas operations for large datasets
- **Memory Management**: Careful memory management for large data volumes
- **Network Optimization**: Efficient REDCap API usage with session management
- **Concurrent Processing**: Support for parallel processing where appropriate

### Scalability Considerations

- **Data Volume**: Design for growth in data volume over time
- **User Load**: Support for multiple concurrent users
- **Processing Complexity**: Scalable validation rule processing
- **Output Management**: Efficient handling of large output files

## Monitoring and Maintenance

### System Monitoring

- **Execution Monitoring**: Track pipeline execution and performance
- **Error Monitoring**: Monitor and alert on system errors
- **Data Quality Monitoring**: Track data quality metrics over time
- **Resource Monitoring**: Monitor system resource usage

### Maintenance Procedures

- **Configuration Updates**: Procedures for updating system configuration
- **Rule Updates**: Process for updating validation rules
- **System Updates**: Procedures for system software updates
- **Backup and Recovery**: Data backup and system recovery procedures

## Support and Resources

### Documentation Resources

- [Project Guidelines](guidelines.md)
- [Configuration Management Documentation](configuration-management.md)
- [Data Fetching System Documentation](data-fetching-system.md)

### Development Resources

- Code repository with version control
- Development environment setup guides
- Testing frameworks and procedures
- Deployment documentation

### Support Channels

- Technical support for system issues
- Documentation updates and improvements
- Feature requests and enhancements
- Community support and collaboration

## Glossary

### Terms and Definitions

- **Instrument**: A logical grouping of related REDCap form variables representing a complete assessment
- **ETL**: Extract, Transform, Load - the data processing pipeline pattern
- **REDCap**: Research Electronic Data Capture - the source data system
- **UDSv4**: Uniform Data Set version 4 - the data collection framework
- **QC**: Quality Control - the validation and review process
- **PTID**: Participant ID - unique identifier for study participants
- **Filter Logic**: REDCap query syntax for selective data retrieval
- **Completion Variable**: REDCap variable indicating form completion status
- **Dynamic Rules**: Validation rules that change based on data values
- **Discriminant Variable**: Data field used to select appropriate validation rules

### Acronyms

- **API**: Application Programming Interface
- **CSV**: Comma-Separated Values
- **ETL**: Extract, Transform, Load
- **JSON**: JavaScript Object Notation
- **NACC**: National Alzheimer's Coordinating Center
- **QC**: Quality Control
- **REDCap**: Research Electronic Data Capture
- **UDS**: Uniform Data Set
- **URL**: Uniform Resource Locator
