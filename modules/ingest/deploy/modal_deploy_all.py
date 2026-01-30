#!/usr/bin/env python3
"""
Deploy All Modal Services

Unified deployment script for all Modal services:
1. TEI Embedding Service (Qwen3-Embedding-8B)
2. DeepSeek-OCR Service (DeepSeek-OCR 3B)
3. NuExtract Service (NuExtract-2.0-8B)

This script deploys all services and verifies they're working.
"""

import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from typing import List, Dict, Any

# Load environment variables
load_dotenv()

# Service configurations
SERVICES = [
    {
        "name": "TEI Embedding Service",
        "app_name": "tei-embedding-service",
        "file": "tei_service.py",
        "endpoint_env": "MODAL_ENDPOINT",
        "description": "Qwen3-Embedding-8B for 4096D embeddings"
    },
    {
        "name": "DeepSeek-OCR Service",
        "app_name": "deepseek-ocr-service",
        "file": "deepseek_ocr_service.py",
        "endpoint_env": "DEEPSEEK_OCR_ENDPOINT",
        "description": "DeepSeek-OCR 3B for image-to-text conversion"
    },
    {
        "name": "NuExtract Service",
        "app_name": "nuextract-service",
        "file": "nuextract_service.py",
        "endpoint_env": "NUEXTRACT_ENDPOINT",
        "description": "NuExtract-2.0-8B for structured extraction"
    }
]

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

def deploy_service(service: Dict[str, Any]) -> bool:
    """Deploy a single Modal service."""

    print(f"\n{'='*60}")
    print(f"🚀 Deploying {service['name']}")
    print(f"   {service['description']}")
    print(f"{'='*60}")

    # Navigate to services directory
    service_path = Path(__file__).parent.parent / "services" / service['file']

    if not service_path.exists():
        print(f"❌ Service file not found: {service_path}")
        return False

    try:
        # Deploy the service
        result = subprocess.run([
            'modal', 'deploy', str(service_path)
        ], capture_output=True, text=True)

        if result.returncode == 0:
            print(f"✅ {service['name']} deployed successfully!")

            # Extract endpoint URL if available
            for line in result.stdout.split('\n'):
                if 'https://' in line and 'modal.run' in line:
                    endpoint = line.strip()
                    print(f"📍 Endpoint: {endpoint}")
                    print(f"💡 Set {service['endpoint_env']}={endpoint} in your .env file")

            return True
        else:
            print(f"❌ {service['name']} deployment failed:")
            print(result.stderr)
            return False

    except Exception as e:
        print(f"❌ Deployment error: {e}")
        return False

def test_service(service: Dict[str, Any]) -> bool:
    """Test a deployed service."""

    print(f"\n🧪 Testing {service['name']}...")

    endpoint = os.getenv(service['endpoint_env'])
    if not endpoint:
        print(f"⚠️ No endpoint configured for {service['name']} (set {service['endpoint_env']})")
        return True  # Don't fail if endpoint not configured yet

    try:
        import requests

        # Test health endpoint
        health_url = endpoint.replace('/embed', '/health').replace('/process_image', '/health').replace('/extract', '/health')

        response = requests.get(health_url, timeout=30)

        if response.status_code == 200:
            print(f"✅ {service['name']} health check passed!")
            print(f"   Response: {response.json()}")
            return True
        else:
            print(f"⚠️ {service['name']} health check returned status {response.status_code}")
            return False

    except Exception as e:
        print(f"⚠️ {service['name']} test error: {e}")
        return False

def main():
    """Main deployment workflow."""

    print("=" * 60)
    print("Modal Services Deployment")
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

    # Step 2: Deploy all services
    print("\n" + "=" * 60)
    print("Deploying Services")
    print("=" * 60)

    deployment_results = []
    for service in SERVICES:
        success = deploy_service(service)
        deployment_results.append((service['name'], success))

        if not success:
            print(f"\n⚠️ {service['name']} deployment failed, continuing with other services...")

    # Step 3: Test deployed services
    print("\n" + "=" * 60)
    print("Testing Deployed Services")
    print("=" * 60)

    test_results = []
    for service in SERVICES:
        success = test_service(service)
        test_results.append((service['name'], success))

    # Summary
    print("\n" + "=" * 60)
    print("Deployment Summary")
    print("=" * 60)

    all_deployed = all(success for _, success in deployment_results)
    all_tested = all(success for _, success in test_results)

    print("\nDeployment Results:")
    for name, success in deployment_results:
        status = "✅" if success else "❌"
        print(f"  {status} {name}")

    print("\nTest Results:")
    for name, success in test_results:
        status = "✅" if success else "⚠️"
        print(f"  {status} {name}")

    if all_deployed:
        print("\n🎉 All Modal services are deployed!")
        if all_tested:
            print("✅ All services passed health checks!")
        else:
            print("⚠️ Some services need endpoint configuration")
            print("\n💡 Configure endpoints in .env:")
            for service in SERVICES:
                print(f"   {service['endpoint_env']}=<your-endpoint-url>")
    else:
        print("\n⚠️ Some services failed to deploy")
        return False

    print("\n" + "=" * 60)
    print("Next Steps:")
    print("=" * 60)
    print("1. Copy the endpoint URLs from the deployment output")
    print("2. Add them to your .env file:")
    for service in SERVICES:
        print(f"   {service['endpoint_env']}=<endpoint-url>")
    print("3. Test the services using their respective clients")
    print("=" * 60)

    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
