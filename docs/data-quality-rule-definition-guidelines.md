# Data Quality Rule Definition Guidelines

## Table of Contents

- [Data Quality Rule Definition Guidelines](#data-quality-rule-definition-guidelines)
  - [Table of Contents](#table-of-contents)
  - [Introduction](#introduction)
  - [Validation Rules](#validation-rules)
  - [Custom Rules Defined for UDS](#custom-rules-defined-for-uds)
    - [compare\_with](#compare_with)
    - [compare\_age](#compare_age)
    - [compatibility](#compatibility)
    - [logic](#logic)
    - [temporalrules](#temporalrules)
    - [check\_adcid](#check_adcid)
    - [compute\_gds](#compute_gds)
    - [rxnorm](#rxnorm)
    - [score\_variables](#score_variables)

## Introduction

The form validator uses QC rules defined as JSON or YAML data objects to check data, based on [Cerberus](https://docs.python-cerberus.org/). In a nutshell:

* Validation schemas are dictionaries of key-value pairs which can be specified using YAML or JSON formats
* Rule definitions are organized by forms. For each form, a YAML or JSON file lists the validation rules for the fields in that form (NACC uses JSON)
* Data records collected (converted to Python `dict`) will be evaluated against the validation schema

**Example:**

<table>
<tr>
<th>YAML Rule Definition</th>
<th>JSON Rule Definition</th>
<th>When Validating</th>
</tr>
<tr>
<td style="vertical-align:top;">
<pre><code>ptid:
  type: integer
  required: true
birthmo:
  type: integer
  required: true
  min: 1
  max: 12
</code></pre>
</td>
<td style="vertical-align:top;">
<pre><code>{
    "ptid": {
        "type": "integer",
        "required": true
    },
    "birthmo": {
        "type": "integer",
        "required": true,
        "min": 1,
        "max": 12
    }
}
</code></pre>
</td>
<td style="vertical-align:top;">
<pre><code>{"ptid": 101, "birthmo": 12}    # passes
{"ptid": 102, "birthmo": 15}    # fails
{"ptid": 103}                   # fails
</code></pre>
</td>
</tr>
</table>

## Validation Rules

Check the full list of built-in Cerberus rules [here](https://docs.python-cerberus.org/validation-rules.html).

Keywords frequently used in UDS rules are described in the table below:

<table width="100%">
<tr>
<th>Keyword</th>
<th>Description</th>
<th width="50%">Example</th>
</tr>
<tr>
<td style="vertical-align:top;"><code>allowed</code></td>
<td style="vertical-align:top;">Specify the list of allowed values. Validation will fail if any other value is given in the data record.</td>
<td style="vertical-align:top;">
<pre><code>schema = {
    "limit": {
        "type": "integer",
        "allowed": [-1, 10, 100]
    }
}

data = {"limit": 10}    # passes
data = {"limit": 20}    # fails
</code></pre>
</td>
</tr>
<tr>
<td style="vertical-align:top;"><code>forbidden</code></td>
<td style="vertical-align:top;">Specify the list of forbidden values. Validation will fail if values in this list are included in the record.</td>
<td style="vertical-align:top;">
<pre><code>schema = {
    "user": {
        "type": "string",
        "forbidden": ["viewer", "editor"]
    }
}

data = {"user": "admin"}    # passes
data = {"user": "viewer"}   # fails
</code></pre>
</td>
</tr>
<tr>
<td style="vertical-align:top;"><code>min</code>, <code>max</code></td>
<td style="vertical-align:top;">Minimum and maximum value allowed (only applicable to object types which support comparison operations like integers or floats). Each keyword can be used independently. Use together to define a range.</td>
<td style="vertical-align:top;">
<pre><code>schema = {
    "length": {
        "type": "float",
        "min": 10.5,
        "max": 20.5
    }
}

data = {"length": 14}       # passes
data = {"length": 20.8}     # fails
</code></pre>
</td>
</tr>
<tr>
<td style="vertical-align:top;"><code>nullable</code></td>
<td style="vertical-align:top;">If set to "true", the field value is allowed to be empty. This rule will be checked on every field, regardless of if it's defined or not. The rule's constraints defaults it to "false". In other words, if neither `nullable` nor `required` are set, the field is required.</td>
<td style="vertical-align:top;">
<pre><code>schema = {
    "country": {
        "type": "string",
        "nullable": True
    }
}

data = {"country": "USA"}   # passes
data = {"country": ""}      # passes

schema = {
    "country": {
        "type": "string"
    }
}

data = {"country": ""}      # fails
</code></pre>
</td>
</tr>
<tr>
<td style="vertical-align:top;"><code>required</code></td>
<td style="vertical-align:top;">If set to "true", the field is mandatory. Validation will fail when it is missing.</td>
<td style="vertical-align:top;">
<pre><code>schema = {
    "name": {
        "type": "string",
        "required": True
    },
    "age": {
        "type": "integer",
        "nullable": True
    }
}

data = {"name": "Steve", "age": 50}     # passes
data = {"name": "Debby"}                # passes
data = {"age": 40}                      # fails
</code></pre>
</td>
</tr>
<tr>
<td style="vertical-align:top;"><code>type</code></td>
<td style="vertical-align:top;">Data type allowed for the value. See the <a href="https://docs.python-cerberus.org/validation-rules.html">Cerberus documentation for the list of type names</a>. If multiple types are allowed, you can specify the types as a list.</td>
<td style="vertical-align:top;">
<pre><code>schema = {
    "limit": {
        "type": "integer"
    }
}

data = {"limit": 10}        # passes
data = {"limit": 11.5}      # fails

schema = {
    "limit": {
        "type": ["integer", "float"]
    }
}

data = {"limit": 10}        # passes
data = {"limit": 11.5}      # passes
data = {"limit": "one"}     # fails
</code></pre>
</td>
</tr>
<tr>
<td style="vertical-align:top;"><code>anyof</code></td>
<td style="vertical-align:top;">Allows to define different sets of rules to validate against, supplied in a list of dicts. Field will be considered valid if any of the provided constraints validates the field.</td>
<td style="vertical-align:top;">
<pre><code>schema = {
    "age": {
        "type": "integer",
        "anyof": [
            {
                "min": 0,
                "max": 120
            },
            {
                "allowed": [999]
            }
        ]
    }
}

data = {"age": 40}      # passes
data = {"age": 999}     # passes
data = {"age": 200}     # fails
</code></pre>
</td>
</tr>
<tr>
<td style="vertical-align:top;"><code>regex</code></td>
<td style="vertical-align:top;">Regex to validate against; only valid for string values.</td>
<td style="vertical-align:top;">
<pre><code>schema = {
    "email": {
        "type": "string",
        "regex": "^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    }
}

data = {"email": "john@example.com"}            # passes
data = {"email": "john_at_example_dot_com"}     # fails
</code></pre>
</td>
</tr>
</table>

## Custom Rules Defined for UDS

These are defined in the `NACCValidator` class.

### compare_with

Used to validate the field based on comparison with another field, with optional adjustments.

* `comparator`: The comparison expression; can be one of `[">", "<", ">=", "<=", "==", "!="]`
* `base`: The field or value to compare to
* `adjustment`: The adjustment to make to the base expression, if any. If specified, `op` must also be provided 
* `op`: The operation to make the adjustment for; can be one of `["+", "-", "*", "/", "abs"]`. If specified, `adjustment` must also be provided
    * Follows the formula `field {comparator} base {op} adjustment`, e.g. `field <= base + adjustment`
    * For `abs`, it instead follows the formula `abs(field - base) {comparator} adjustment`, e.g. `abs(field - base) <= adjustment`
    * See examples below for more details
* `previous_record`: Optional boolean - if True, will search for `base` in the previous record and make the comparison against that
* `ignore_empty`: Optional boolean - if comparing to previous record(s), set this to True to ignore records where the specified `base` is empty
    * If this is set to True, the validation will _ignore_ cases when a previous record was not found (e.g. pass through validation without errors)

The value to compare to (`base`) can be another field in the schema OR a special keywords either related to the current date (i.e. the exact time/date at time of validation) or a previous record

* `current_date`: Compare to the current date
* `current_year`: Compare to the current year
* `current_month`: Compare to the current month
* `current_day`: Compare to the current day

The rule definition for `compare_with` should follow the following format:

```json
{
    "field_name": {
        "compare_with": {
            "comparator": "comparator, one of >, <, >=, <=, ==, !=",
            "base": "field or value to compare field_name to",
            "adjustment": "(optional) the adjustment field or value",
            "op": "(optional) operation, one of +, -, *, /, abs",
            "previous_record": "(optional) boolean, whether or not to compare to base in the previous record",
            "ignore_empty": "(optional) boolean, whether or not to ignore previous records where this field is empty"
        }
}
```

**Example:**

`birthyr <= current_year - 15`, e.g. `birthyr` must be at least 15 years prior to the current year.

<table>
<tr>
<th>YAML Rule Definition</th>
<th>JSON Rule Definition</th>
<th>When Validating</th>
</tr>
<tr>
<td style="vertical-align:top;">
<pre><code>birthyr:
  type: integer
  required: true
  compare_with:
    comparator: <=
    base: current_year
    adjustment: 15
    op: "-"
</code></pre>
</td>
<td style="vertical-align:top;">
<pre><code>{
    "birthyr": {
        "type": "integer",
        "required": true,
        "compare_with": {
            "comparator": "<=",
            "base": "current_year",
            "adjustment": 15,
            "op": "-"
        }
    }
}
</code></pre>
</td>
<td style="vertical-align:top;">
<pre><code>{"birthyr": 1995}   # passes
{"birthyr": 2030}   # fails until 2045
</code></pre>
</td>
</tr>
</table>

**Absolute Value Example**

`abs(waist1 - waist2) <= 0.5`, e.g. the difference between `waist1` and `waist2` cannot be more than 0.5

<table>
<tr>
<th>YAML Rule Definition</th>
<th>JSON Rule Definition</th>
<th>When Validating</th>
</tr>
<tr>
<td style="vertical-align:top;">
<pre><code>waist1:
  type: float
  required: true
  compare_with:
    comparator: <=
    base: waist2
    adjustment: 0.5
    op: abs
waist2:
  type: float
  required: true
</code></pre>
</td>
<td style="vertical-align:top;">
<pre><code>{
        "waist1": {
            "type": "float",
            "required": true,
            "compare_with": {
                "comparator": "<=",
                "base": "waist2",
                "op": "abs",
                "adjustment": 0.5
            }
        },
        "waist2": {
            "type": "float",
            "required": true
        }
    }
</code></pre>
</td>
<td style="vertical-align:top;">
<pre><code>{'waist1': 5, 'waist2': 5.25}   # passes
{'waist1': 5, 'waist2': 4.4}    # fails
</code></pre>
</td>
</tr>
</table>

### compare_age

Used to compare ages. Takes the following parameters:

* `comparator`: The comparison expression; can be one of `[">", "<", ">=", "<=", "==", "!="]`
* `birth_year`: The birth year (or year the age should start)
* `birth_month`: The birth month (or month the age should start) - optional, defaults to 1 (first month year
* `birth_day`: The birth day (or day the age should start) - optional, defaults to 1 (first day of year)
* `compare_to`: Variable name, integer, or list of variable names/integers to compare the field's age to

Age is calculated by combining and converting the `birth_*` fields into a date, and then calculating the age at the field (assuming the field's value is also a valid date). The exact calculation is `age = (field_value - birth_date).days / 365.25`. This result must then satisfy the comparison formula against the `compare_to` field, e.g. `age <= compare_to`. 

Additional things to note:

* This rule only supports being defined under `date` fields or `string` fields with `formatting: date`
* Only `birth_year` is required, but specifying the month and date allows the comparison to be more fine-grained
* Currently this does NOT support the same special date keywords used in `compare_with` (`current_date`, `current_year`, etc.)

The rule definition for `compare_age` should follow the following format:

```json
{
    "field_name": {
        "compare_age": {
            "comparator": "comparator, one of >, <, >=, <=, ==, !=",
            "birth_year": "the birth year (or year the age should start)",
            "birth_month": "the birth month (or month the age should start) - optional, defaults to 1 (first month year)",
            "birth_day": "the birth day (or day the age should start) - optional, defaults to 1 (first day of year)",
            "compare_to": "variable name, integer, or list of variable names/integers to compare to"
        }
    }
}
```

**Example:**

`age at frmdate >= behage`

<table>
<tr>
<th>YAML Rule Definition</th>
<th>JSON Rule Definition</th>
<th>When Validating</th>
</tr>
<tr>
<td style="vertical-align:top;">
<pre><code>frmdate:
  type: string
  formatting: date
  compare_age:
    comparator: ">="
    birth_year: birthyr
    birth_month: birthmo
    compare_to: behage
birthmo:
  type: integer
  min: 1
  max: 12
birthyr:
  type: integer
behage:
  type: integer
</code></pre>
</td>
<td style="vertical-align:top;">
<pre><code>{
    "frmdate": {
        "type": "string",
        "formatting": "date",
        "compare_age": {
            "comparator": ">=",
            "birth_year": "birthyr",
            "birth_month": "birthmo",
            "compare_to": "behage"
        }
    },
    "birthmo": {
        "type": "integer",
        "min": 1,
        "max": 12
    },
    "birthyr": {
        "type": "integer"
    },
    "behage": {
        "type": "integer"
    }
}
</code></pre>
</td>
<td style="vertical-align:top;">
<pre><code>{'frmdate': '2024/02/02', 'birthmo': 6, 'birthyr': 1950, 'behage': 50}  # passes
{'frmdate': '2024/02/02', 'birthmo': 1, 'birthyr': 2024, 'behage': 50}  # fails
</code></pre>
</td>
</tr>
</table>


### compatibility

Used to specify the list of compatibility (if-then-else) constraints for a given field with other fields within the form or across multiple forms. A field will only pass validation if none of the compatibility constraints are violated.

Each constraint specifies `if`, `then`, and (optionally) `else` attributes to allow the validation of a set of fields/subschemas based on the outcome of other fields/subschemas (i.e. when the schema(s) defined under `if` evaluates to true for a given record, then the schema(s) specified under `then` will be evaluated).

Each `if/then/else` attribute can have several fields which need to be satisifed, with the `*_op` attribute specifying the boolean operation in which to compare the different fields. For example, if `if_op = or`, then as long as _any_ of the fields satsify their schema, the `then` attribute will be evaluated. The default `*_op` is `and`.

The rule definition for `compatibility` follows the following format:

```json
{
    "<field_name>": {
        "compatibility": [
            {
                "if": {
                    "<field_name>": "subschema to be satisifed"
                },
                "then": {
                    "<field_name>": "subschema to be satisifed"
                }
            },
            {
                "if_op": "and",
                "then_op": "or",
                "else_op": "or",

                "if": {
                    "<field_name>": "subschema to be satisifed",
                    "<field_name>": "subschema to be satisifed"
                },
                "then": {
                    "<field_name>": "subschema to be satisifed",
                    "<field_name>": "subschema to be satisifed"
                },
                "else": {
                    "<field_name>": "subschema to be satisifed",
                    "<field_name>": "subschema to be satisifed"
                }
            }
        ]
    }
}
```

One additional nuance is the evaluation against `None`/null values. Because Cerberus always evaluates `"nullable": False` by default, the application of a subschema in this case must explicitly set `"nullable": True` if the attributes evaluate or result in null values. For example

```python
# if case: If PARENTVAR is blank or 88, then VAR1 must be blank
"if": {
    "parentvar": {
        "nullable": True,  # <--- external nullable flag for the if clause
        "anyof": [
            {
                "nullable": True,
                "filled": False
            },
            {
                "allowed": [88]
            }
        ]
    }
},
"then": {
    "var1": {
        "nullable": True,
        "filled": False}
}

# then case: if PARENTVAR is blank, then the following must be blank: var1, var2, var3
"if": {
    "parentvar": {
        "nullable": True,
        "filled": False
    }
},
"then": {
    "var1": {
        "nullable": True,  # <--- nullable flag for the then clause
        "logic": {
            "formula": {
                "and": [
                    {"==": [None, {"var": "var1"}]},
                    {"==": [None, {"var": "var2"}]},
                    {"==": [None, {"var": "var3"}]}
                ]
            }
        }
    }
}
```

**Examples:**

If field `incntmod` (primary contact mode with participant) is 6, then field `incntmdx` (specify primary contact mode with participant) cannot be blank. 

<table>
<tr>
<th>YAML Rule Definition</th>
<th>JSON Rule Definition</th>
<th>When Validating</th>
</tr>
<tr>
<td style="vertical-align:top;">
<pre><code>incntmod:
type: integer
  required: true
incntmdx:
  type: integer
  nullable: true
  compatibility:
    - if:
      incntmod:
        allowed:
          - 6
      then:
        nullable: false
</code></pre>
</td>
<td style="vertical-align:top;">
<pre><code>{
    "incntmod": {
        "type": "integer",
        "required": true
    },
    "incntmdx": {
        "type": "integer",
        "nullable": true,
        "compatibility": [
            {
                "if": {
                    "incntmod": {
                        "allowed": [6]
                    }
                },
                "then": {
                    "nullable": false
                }
            }
        ]
    }
}
</code></pre>
</td>
<td style="vertical-align:top;">
<pre><code>{"incntmod": 1, "incntmdx": None}   # passes
{"incntmod": 6, "incntmdx": 1}      # passes
{"incntmod": 6, "incntmdx": None}   # fails
</code></pre>
</td>
</tr>
</table>

This rule can also be used to define the "if not, then" case. For this, we use `forbidden` instead of `allowed`.

So if field `incntmod` (primary contact mode with participant) is NOT 6, then field `incntmdx` (specify primary contact mode with participant) must be blank.

<table>
<tr>
<th>YAML Rule Definition</th>
<th>JSON Rule Definition</th>
<th>When Validating</th>
</tr>
<tr>
<td style="vertical-align:top;">
<pre><code>incntmod:
  type: integer
  required: true
incntmdx:
  type: string
  nullable: true
  compatibility:
    - if: null
      incntmod:
        forbidden:
          - 6
      then:
        nullable: true
        filled: false
</code></pre>
</td>
<td style="vertical-align:top;">
<pre><code>{
    "incntmod": {
        "type": "integer",
        "required": true
    },
    "incntmdx": {
        "type": "string",
        "nullable": true,
        "compatibility": [
            {
                "if": {
                    "incntmod": {
                        "forbidden": [6]
                    }
                },
                "then": {
                    "nullable": true,
                    "filled": false
                }
            }
        ]
    }
}
</code></pre>
</td>
<td style="vertical-align:top;">
<pre><code>{"incntmod": 1, "incntmdx": None}   # passes
{"incntmod": 6, "incntmdx": 1}      # fails
{"incntmod": 6, "incntmdx": None}   # passes
{"incntmod": 1, "incntmdx": 1}      # fails
</code></pre>
</td>
</tr>
</table>


### logic

Used to specify a mathematical formula/expression to validate against, and utilizes [json-logic-py](https://github.com/nadirizr/json-logic-py) (saved as `json_logic.py`). This rule overlaps with `compare_with`, but allows for comparison between multiple fields as well as more complex, nested mathematical expressions. That being said, it does not account for the same special keywords like `current_year`.

* `formula`: The mathematical formula/expression to apply; see the `operations` dict in `json_logic.py` to see the full list of available operators. Each operator expects differently formatted arguments
* `errormsg`: A custom message to supply if validation fails. This key is optional; if not provided the error message will simply be `value {value} does not satisify the specified formula`

The rule definition for `logic` should follow the following format:

```json
{
    "<field_name>": {
        "logic": {
            "formula": {
                "operator": "list of arguments for the operator"
            },
            "errormsg": "<optional error message to supply if validation fails>"
        }
}
```

**Example:**

One of `var1`, `var2`, or `var3` must be `1`.

<table>
<tr>
<th>YAML Rule Definition</th>
<th>JSON Rule Definition</th>
<th>When Validating</th>
</tr>
<tr>
<td style="vertical-align:top;">
<pre><code>var1:
  type: integer
  nullable: true
var2:
  type: integer
  nullable: true
var3:
  type: integer
  nullable: true
  logic:
    formula:
      or:
        - ==:
          - 1
          - var: var1
        - ==:
          - 1
          - var: var2
        - ==:
          - 1
          - var: var3
</code></pre>
</td>
<td style="vertical-align:top;">
<pre><code>{
    "var1": {
        "type": "integer",
        "nullable": true,
    },
    "var2": {
        "type": "integer",
        "nullable": true,
    },
    "var3": {
        "type": "integer",
        "nullable": true,
        "logic": {
            "formula": {
                "or": [
                    {
                        "==": [1, {"var": "var1"}]
                    },
                    {
                        "==": [1, {"var": "var2"}]
                    },
                    {
                        "==": [1, {"var": "var3"}]
                    }
                ]
            }
        }
    }
}
</code></pre>
</td>
<td style="vertical-align:top;">
<pre><code>{"var1": 1, "var2": 1, "var3": 1}            # passes
{"var1": 1, "var2": None, "var3": None}      # passes
{"var1": None, "var2": None, "var3": None}   # fails
</code></pre>
</td>
</tr>
</table>

#### Custom Operations

The validator also has custom operators in addition to the ones provided by json-logic-py:

| Operator | Arguments | Description |
| -------- | --------- | ----------- |
| `count` | `[var1, var2, var3...]` | Counts how many valid variables are in the list, ignoring null and 0 values |
| `count_exact` | `[base, var1, var2, var3, ...]` | Counts how many values in the list equal the base. The first value is always considered the base, and the rest of the list is compared to it, so this operator requires at least 2 items. |


### temporalrules

Used to specify the list of checks to be performed against the previous visit for the same participant.

Each constraint specifies `previous` and `current` attributes. If conditions specified under the `previous` subschema are satisfied by the previous visit record, then the current visit record must satisfy the conditions specified under `current` subschema.

Each constraint also has optional fields that can be set:

* Each `previous/current` attribute can have several fields which need to be satisifed, so an optional `*_op` attribute can be used to specify the boolean operation in which to compare the different fields. For example, if `prev_op = or`, then as long as _any_ of the fields satsify their schema, the `current` attribute will be evaluated. The default `*_op` is `and`.
* `ignore_empty`: Takes a string or list of strings denoting fields that cannot be empty. When grabbing the previous record, the validator will grab the first previous record where _all_ specified fields are non-empty.
    * If no record is found that satisfies all fields being non-empty, the validator will _ignore_ the check (e.g. pass through validation without errors)
* `swap_order`: If set to True, it will swap the order of operations, evluating the `current` subschema first, then the `previous` subschema

> **NOTE**: To validate `temporalrules`, the validator should have a `Datastore` instance which will be used to retrieve the previous visit record(s) for the participant. 

The rule definition for `temporalrules` should follow the following format:

```json
{
    "<parent_field_name>": {
        "temporalrules": [
            {
                "previous": {
                    "<field_name>": "subschema to be satisfied for the previous record"
                },
                "current": {
                    "<field_name>": "subschema to be satisfied for the current record, will be evaluated if the previous subschema is satisfied"
                }
            },            {
                "ignore_empty": ["<field_name_1>", "<field_name_2>"],
                "prev_op": "or",
                "previous": {
                    "<field_name_1>": "subschema to be satisfied for the previous record",
                    "<field_name_2>": "subschema to be satisfied for the previous record"
                },
                "current": {
                    "<field_name>": "subschema to be satisfied for the current record, will be evaluated if either of the previous subschemas are satisfied"
                }
            },
            {
                "swap_order": true,
                "previous": {
                    "<field_name>": "subschema to be satisfied for the previous record, will be evaluated if the current subschema is satisfied"
                },
                "current": {
                    "<field_name>": "subschema to be satisfied for the current record"
                }
            }

        ]
    }
}
```

**Example:**

If field `taxes` (difficulty with taxes, business, and other papers) is 0 (normal) at a previous visit, then `taxes` cannot be 8 (not applicable/never did) at the follow-up visit.

<table>
<tr>
<th>YAML Rule Definition</th>
<th>JSON Rule Definition</th>
<th>When Validating</th>
</tr>
<tr>
<td style="vertical-align:top;">
<pre><code>taxes:
  type: integer
  temporalrules:
    - previous:
      taxes:
        allowed:
          - 0
      current:
        taxes:
          forbidden:
            - 8
</code></pre>
</td>
<td style="vertical-align:top;">
<pre><code>{
    "taxes": {
        "type": "integer",
        "temporalrules": [            
            {
                "previous": {
                    "taxes": {
                        "allowed": [0]
                    }
                },
                "current": {
                    "taxes": {
                        "forbidden": [8]
                    }
                }
            }
        ]
    }
}
</code></pre>
</td>
<td style="vertical-align:top;">
<pre><code># assume this record already exists
# {"visit_date": 1, "taxes": 0}

{"visit_date": 2, "taxes": 1}   # passes
{"visit_date": 2, "taxes": 8}   # fails
</code></pre>
</td>
</tr>
</table>

### check_adcid

Used to check whether a specified ADCID is valid.

This validation is implemented using the `function` rule with custom `check_adcid` function in the NACCValidator. The rule definition should be in the following format:

```json
{
    "<adcid_variable>": {
        "function": {
            "name": "check_adcid",
            "args": {"own": "<bool, whether to validate against own ADCID or list of current ADCIDs; defaults to True>"}
        }
    }
}
```

> **NOTE**: To validate `check_adcid`, the validator should have a `Datastore` instance which implements the `is_valid_adcid` function (which should have access to center's ADCID and the list of current ADCIDs).

**Example:**

The `adcid` must match the center's own ADCID, whereas `oldadcid` should be a valid ADCID in the current ADCIDs list. 

<table>
<tr>
<th>YAML Rule Definition</th>
<th>JSON Rule Definition</th>
<th>When Validating</th>
</tr>
<tr>
<td style="vertical-align:top;">
<pre><code>adcid:
  type: integer
  function:
    name: check_adcid
oldadcid:
  type: integer
  function:
    name: check_adcid
    args:
      own: false
</code></pre>
</td>
<td style="vertical-align:top;">
<pre><code>{
    "adcid": {
        "type": "integer",
        "function": {
            "name": "check_adcid"
        }
    },
    "oldadcid": {
        "type": "integer",
        "function": {
            "name": "check_adcid",
            "args": {"own": False}
    }
}
</code></pre>
</td>
<td style="vertical-align:top;">
<pre><code># assume the center's own ADCID is 0, and ADCIDs 0-5 inclusive are valid

{"adcid": 0, "oldadcid": 5}   # passes
{"adcid": 2, "oldadcid": 5}   # fails
{"adcid": 0, "oldadcid": 9}   # fails
</code></pre>
</td>
</tr>
</table>

### compute_gds

Custom rule defined to validate the Geriatric Depression Scale (GDS) score computation. Only be used for validating the `gds` field in UDS Form B6.

The rule definition for `compute_gds` should follow the following format:

```json
{
    "gds": {
        "compute_gds": ["list of fields used in GDS score computation"]
    }
}
```

### rxnorm

Custom rule defined to check whether a given Drug ID is valid RXCUI code.

This function uses the `check_with` rule from Cerberus. The rule definition should be in the following format:

```json
{
    "<rxnormid variable>": {
        "check_with": "rxnorm"
    }
}
```
> **NOTE**: To validate `rxnorm`, the validator should have a `Datastore` instance which implements the `is_valid_rxcui` function which will check if the given rxnormid value is a valid RXCUI code

### score_variables

Custom rule that scores the number of correct or incorrect variables based on a mode and scoring key.

This validation is implemented using the `function` rule with custom `score_variables` function in the NACCValidator. The rule definition should be in the following format:

```json
{
    "<score_variable>": {
        "function": {
            "name": "score_variables",
            "args": {
                "mode": "'correct' or 'incorrect'",
                "scoring_key": {
                    "var1": "correct_value_1",
                    "var2": "correct_value_2",
                    "...etc"
                },
                "logic": {
                    "...same as logic formula"
                },
                "calc_var_name": "(optional) name of the variable to store calculation under; defaults to __total_sum"
            }
        }
    }
}
```

* `mode`: Either `correct` or `incorrect`; if `correct`, will count the number of _correct_ variables, and if `incorrect` will count the number of _incorrect_ variables
* `scoring_key`: Dict representing the scoring key; maps each variable involved in the scoring function to its correct value
* `logic`: Logic to perform on the `calc_var_name` once calculated; same schema as the [logic](#logic) rule defined earlier
* `calc_var_name`: (Optional) Name of the variable to store the calculation under; defaults to `__total_sum`. This variable MUST be unique to your record or else the validator will throw an error

This function looks at all variables defined in the `scoring_key` and counts the number that are correct if the mode is `correct` or incorrect if the mode is `incorrect`. It stores this result in the variable defined by `calc_var_name` (defaults to `__total_sum`, note the double underscore for uniqueness) that can then be used inside the `logic` formula to compare against.

If any of the fields in `scoring_key` are missing or invalid, then validation is skipped and this rule "passes" by default. Otherwise validation succeeds if `calc_var_name` satisfies the given formula, else it fails.

**Example:**

`total` must match the total number of correct variables defined under `scoring_key`.

<table>
<tr>
<th>YAML Rule Definition</th>
<th>JSON Rule Definition</th>
<th>When Validating</th>
</tr>
<tr>
<td style="vertical-align:top;">
<pre><code>total:
  type: integer
  required: true
  function:
    name: score_variables
    args:
      mode: correct
      scoring_key:
        val1: 1
        val2: 2
        val3: 3
      logic:
        formula:
          "==":
          - var: total
          - var: __total_sum
val1:
  type: integer
  nullable: true
val2:
  type: integer
  nullable: true
val3:
  type: integer
  nullable: true
</code></pre>
</td>
<td style="vertical-align:top;">
<pre><code>{
    "total": {
        "type": "integer",
        "required": true,
        "function": {
            "name": "score_variables",
            "args": {
                "mode": "correct",
                "scoring_key": {
                    "val1": 1,
                    "val2": 2,
                    "val3": 3
                },
                "logic": {
                    "formula": {
                        "==": [
                            {
                                "var": "total"
                            },
                            {
                                "var": "__total_sum"
                            }
                        ]
                    }
                }
            }
        }
    },
    "val1": {
        "type": "integer",
        "nullable": true
    },
    "val2": {
        "type": "integer",
        "nullable": true
    },
    "val3": {
        "type": "integer",
        "nullable": true
    }
}
</code></pre>
</td>
<td style="vertical-align:top;">
<pre><code>
{'total': 3, 'val1': 1, 'val2': 2, 'val3': 3}   # passes
{'total': 5}                                    # passes
{'total': 10, 'val1': 1, 'val2': 2, 'val3': 3}  # fails
</code></pre>
</td>
</tr>
</table>
