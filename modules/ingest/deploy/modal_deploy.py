#!/usr/bin/env python3
"""
Deploy Modal Qwen3-Embedding-8B Service

This script deploys the embedding service to Modal.com and verifies it's working.
"""

import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
def check_modal_cli():
    """Check if Modal CLI is installed and authenticated."""
    
    print("🔍 Checking Modal CLI...")
    
    try:
        result = subprocess.run(['modal', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Modal CLI version: {result.stdout.strip()}")
        else:
            print("❌ Modal CLI not found")
            print("Install it with: pip install modal")
            return False
    except FileNotFoundError:
        print("❌ Modal CLI not found")
        print("Install it with: pip install modal")
        return False
    
    # Check authentication
    try:
        result = subprocess.run(['modal', 'profile', 'list'], capture_output=True, text=True)
        if result.returncode == 0 and '•' in result.stdout:
            print("✅ Modal authentication verified")
            return True
        else:
            print("❌ Modal not authenticated")
            print("Run: modal token set")
            return False
    except Exception as e:
        print(f"⚠️ Could not verify Modal auth: {e}")
        return True  # Proceed anyway

def deploy_modal_service():
    """Deploy the Modal service."""
    
    print("🚀 Deploying Modal Qwen3-Embedding-8B service...")
    
    # Navigate to project root, then to tei_service.py
    service_path = Path(__file__).parent.parent / "tei_service.py"
    
    if not service_path.exists():
        print(f"❌ Service file not found: {service_path}")
        return False
    
    try:
        # Deploy the service
        result = subprocess.run([
            'modal', 'deploy', str(service_path)
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Modal service deployed successfully!")
            print(result.stdout)
            return True
        else:
            print("❌ Modal deployment failed:")
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"❌ Deployment error: {e}")
        return False

def test_deployment():
    """Test the deployed service."""
    
    print("🧪 Testing deployed service...")
    
    try:
        # Run the test script (in project root)
        test_script = Path(__file__).parent.parent.parent.parent / "test_modal_deployment.py"
        
        result = subprocess.run([
            sys.executable, str(test_script)
        ], capture_output=True, text=True)
        
        print(result.stdout)
        
        if result.returncode == 0:
            print("✅ Deployment test passed!")
            return True
        else:
            print("❌ Deployment test failed!")
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"❌ Test error: {e}")
        return False

def main():
    """Main deployment workflow."""
    
    print("=" * 60)
    print("Modal Qwen3-Embedding-8B Service Deployment")
    print("=" * 60)
    
    # Check environment
    modal_token_id = os.getenv('MODAL_TOKEN_ID')
    modal_token_secret = os.getenv('MODAL_TOKEN_SECRET')
    
    if not modal_token_id or not modal_token_secret:
        print("⚠️ Modal credentials not found")
        print("Make sure to set MODAL_TOKEN_ID and MODAL_TOKEN_SECRET in your .env file")
        print("You can get tokens from: https://modal.com/settings/tokens")
        return False
    
    print(f"✅ Modal credentials found (ID: {modal_token_id[:10]}...)")
    
    # Step 1: Check Modal CLI
    if not check_modal_cli():
        return False
    
    print()
    
    # Step 2: Deploy service
    if not deploy_modal_service():
        return False
    
    print()
    
    # Step 3: Test deployment
    if not test_deployment():
        return False
    
    print()
    print("=" * 60)
    print("🎉 Modal Qwen3-Embedding-8B service is ready!")
    print("You can now proceed with the Rust code ingestion pipeline.")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)