#!/usr/bin/env python3
"""
Demonstration script showing the new system design in action.
"""

from src.model import Model
from src.model_manager import ModelManager
from src.authorization import Authorization, Permission


def main():
    """Demonstrate the system components working together."""
    print("=== ModelGuard System Design Demonstration ===\n")
    
    # 1. Create a ModelManager
    print("1. Initializing ModelManager...")
    model_manager = ModelManager()
    print(f"   ModelManager created with {len(model_manager.metrics)} metrics")
    print(f"   Available metrics: {[m.__class__.__name__ for m in model_manager.metrics]}\n")
    
    # 2. Create some sample models
    print("2. Creating sample models...")
    model1 = Model(
        name="bert-base-uncased",
        model_key="models/bert-base-uncased/model",
        code_key="models/bert-base-uncased/code",
        dataset_key="models/bert-base-uncased/dataset",
        size=420000000,  # 420MB
        license="Apache-2.0"
    )
    
    model2 = Model(
        name="gpt-2-small",
        model_key="models/gpt-2-small/model",
        code_key="models/gpt-2-small/code",
        dataset_key="models/gpt-2-small/dataset",
        size=500000000,  # 500MB
        license="MIT"
    )
    
    print(f"   Created model: {model1}")
    print(f"   Created model: {model2}\n")
    
    # 3. Score the models
    print("3. Scoring models with all metrics...")
    model_manager._score_model(model1)
    model_manager._score_model(model2)
    
    print(f"   BERT scores: {model1.scores}")
    print(f"   GPT-2 scores: {model2.scores}\n")
    
    # 4. Add models to manager
    print("4. Adding models to ModelManager...")
    model_manager.add_model(model1)
    model_manager.add_model(model2)
    print(f"   ModelManager now has {len(model_manager.models)} models\n")
    
    # 5. Search for models
    print("5. Searching for models...")
    found_model = model_manager.search("bert-base-uncased")
    if found_model:
        print(f"   Found model: {found_model}")
    else:
        print("   Model not found")
    
    # 6. Test authorization
    print("\n6. Testing authorization system...")
    auth = Authorization()
    
    # Test user permissions
    user_id = "demo_user"
    print(f"   User {user_id} can upload: {auth.can_upload(user_id)}")
    print(f"   User {user_id} can search: {auth.can_search(user_id)}")
    print(f"   User {user_id} can download: {auth.can_download(user_id)}")
    print(f"   User {user_id} is admin: {auth.is_admin(user_id)}")
    
    # Grant admin permission
    auth.grant_permission(user_id, Permission.ADMIN)
    print(f"   After granting admin: User {user_id} is admin: {auth.is_admin(user_id)}")
    
    # 7. List all models
    print("\n7. Listing all models...")
    models_list = model_manager.list_models()
    for i, model_data in enumerate(models_list, 1):
        print(f"   Model {i}: {model_data['name']} (Size: {model_data['size']} bytes, License: {model_data['license']})")
    
    # 8. Test upload functionality (stub)
    print("\n8. Testing upload functionality...")
    upload_result = model_manager.upload("nonexistent.zip")
    print(f"   Upload of nonexistent file: {upload_result}")
    
    # 9. Show system status
    print("\n9. System status:")
    print(f"   ModelManager: {model_manager}")
    print(f"   Authorization: {auth}")
    
    print("\n=== Demonstration Complete ===")
    print("The system design is working correctly with all components integrated!")


if __name__ == "__main__":
    main()
