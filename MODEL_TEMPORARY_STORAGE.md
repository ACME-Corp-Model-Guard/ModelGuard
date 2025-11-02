# Model Temporary Storage in Lambda Functions

## What Cody's Message Means

Cody added functionality to the `Model` class to prepare it for use in Lambda functions. The key concept is **"temporary storage"** - Model objects that exist temporarily in Lambda's memory during execution, before being saved to permanent storage (DynamoDB/S3).

## The Concept: Temporary vs Permanent Storage

In Lambda functions, Model objects work in two stages:

1. **Temporary Storage (In-Memory)**: Model object exists in Lambda's execution environment
2. **Permanent Storage (DynamoDB)**: Model metadata saved to DynamoDB for persistence

## Creating Models for Temporary Storage

The process **varies depending on whether the model is new or pre-existing**:

### Scenario 1: Creating a NEW Model (Model doesn't exist in DynamoDB)

When uploading an artifact for a model that doesn't exist yet:

```python
# Create new Model object in Lambda's temporary memory
model = Model(
    name=model_name,
    model_key="",           # Will be set after S3 upload
    code_key="",            # Empty initially
    dataset_key="",         # Empty initially
    size=len(file_content), # Known from upload
    license="unknown",      # Default value
)

# At this point, model exists only in Lambda's memory (temporary)
# After processing, save to DynamoDB (permanent storage)
_save_model_to_dynamodb(model)
```

**Use Case**: First time uploading an artifact for a model name

### Scenario 2: Loading a PRE-EXISTING Model (Model already in DynamoDB)

When working with a model that already exists:

```python
# Load existing model from DynamoDB into Lambda's temporary memory
model = _load_model_from_dynamodb(model_name)

# This creates a Model object in Lambda's memory from DynamoDB data
# The model temporarily exists in Lambda, can be modified, then saved back

# Make changes (e.g., update artifact keys)
if artifact_type == "model":
    model.model_key = new_s3_key
    model.size = new_size

# Save updated model back to DynamoDB
_save_model_to_dynamodb(model)
```

**Use Case**: Uploading additional artifacts (code, dataset) for an existing model

## How It Works in `lambda_handlers.py`

Looking at the actual code (lines 536-556):

```python
# Load or create model
model = _load_model_from_dynamodb(model_name)  # Try to load existing
if model is None:
    # Create new model (temporary, in Lambda memory)
    model = Model(
        name=model_name,
        model_key="",
        code_key="",
        dataset_key="",
        size=len(file_content),
        license="unknown",
    )

# Update model with new artifact key (still temporary, in memory)
if artifact_type == "model":
    model.model_key = s3_key
    model.size = len(file_content)
elif artifact_type == "code":
    model.code_key = s3_key
elif artifact_type == "dataset":
    model.dataset_key = s3_key

# Now save to permanent storage (DynamoDB)
_save_model_to_dynamodb(model)
```

## The Pattern

1. **Check**: Does model exist in DynamoDB?
   - **Yes** → Load into temporary memory (`from_dict()` or `_load_model_from_dynamodb()`)
   - **No** → Create new Model object in temporary memory

2. **Modify**: Make changes to the Model object (still in memory)

3. **Persist**: Save to DynamoDB (`to_dict()` then `put_item()`)

## Why "Temporary Storage"?

Lambda functions are stateless and have limited execution time:

- **Model objects live only during Lambda execution** (max ~15 minutes)
- After Lambda completes, in-memory objects are destroyed
- **Permanent storage** (DynamoDB) persists across Lambda invocations
- Each Lambda invocation may load the model fresh from DynamoDB

## Example Flow

```
Lambda Invocation Starts
  ↓
Check DynamoDB: Does "bert-model" exist?
  ↓
  ├─ YES → Load from DynamoDB → Create Model in memory (temporary)
  │         Modify: model.code_key = "code/..."
  │         Save to DynamoDB
  │
  └─ NO  → Create new Model in memory (temporary)
            Set: model.name = "bert-model"
            Set: model.model_key = "model/..."
            Save to DynamoDB
  ↓
Lambda Invocation Ends (Model object destroyed, data persists in DynamoDB)
```

## Key Methods for Temporary Storage

### Creating Temporary Model Objects

```python
# New model (empty artifact keys)
model = Model(
    name="my-model",
    model_key="",
    code_key="",
    dataset_key="",
    size=0,
    license="unknown"
)

# Load existing model (from DynamoDB to temporary memory)
model = Model.from_dict(dynamodb_data)  # Convert DynamoDB format → Model object
# OR
model = _load_model_to_dynamodb(model_name)  # Helper that does the conversion
```

### Saving to Permanent Storage

```python
# Convert Model object → DynamoDB format → Save
model_dict = model.to_dict()
dynamodb.put_item(TableName=TABLE_NAME, Item=model_dict)
# OR use helper
_save_model_to_dynamodb(model)
```

## Documentation Location

Cody mentioned documenting this in **"Loop"** - this is likely:
- An internal documentation/wiki system (like Confluence, Notion, GitHub Wiki)
- A team knowledge base
- Project documentation repository

The documentation would explain when to create new vs load existing models in the storage workflow.

## Summary

**Temporary Storage** = Model objects that exist in Lambda's memory during execution  
**Permanent Storage** = Model data saved in DynamoDB  
**The Process Varies** = Create new Model vs Load existing Model from DynamoDB  

This pattern ensures:
- Models persist across Lambda invocations
- Models can be updated incrementally (upload code, then dataset, etc.)
- Data integrity (always load fresh from DynamoDB at start)

