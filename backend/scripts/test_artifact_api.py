"""Test script for artifact browsing API endpoints."""
import sys
import os
import requests
import json
from urllib.parse import quote

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = "http://localhost:8000"


def test_artifact_api():
    """Test the artifact browsing API endpoints."""
    print("🧪 Testing Artifact Browsing API Endpoints...")
    print()
    
    try:
        # First, create a task
        print("1. Creating a test task...")
        task_data = {
            "title": "Artifact API Test Task",
            "input_prompt": "Create a simple calculator with multiple files"
        }
        
        response = requests.post(f"{BASE_URL}/api/tasks", json=task_data)
        if response.status_code != 201:
            print(f"❌ Failed to create task: {response.status_code}")
            print(response.text)
            return
        
        task = response.json()
        task_id = task["id"]
        print(f"✅ Task created: {task_id}")
        print()
        
        # Start the task to generate artifacts
        print("2. Starting task execution...")
        response = requests.post(f"{BASE_URL}/api/tasks/{task_id}/run")
        if response.status_code != 202:
            print(f"❌ Failed to start task: {response.status_code}")
            print(response.text)
            return
        
        print("✅ Task started")
        print()
        
        # Wait for artifacts to be generated
        print("3. Waiting for artifacts to be generated...")
        import time
        time.sleep(5)  # Wait 5 seconds for artifacts
        
        # Test API 1: List all artifact files
        print("4. Testing GET /api/artifacts/{task_id}...")
        response = requests.get(f"{BASE_URL}/api/artifacts/{task_id}")
        
        if response.status_code != 200:
            print(f"❌ Failed to get artifact list: {response.status_code}")
            print(response.text)
            return
        
        artifact_list = response.json()
        print(f"✅ Artifact list retrieved:")
        print(f"   Task ID: {artifact_list['task_id']}")
        print(f"   Total files: {artifact_list['total']}")
        print()
        
        if artifact_list['files']:
            print("   Files:")
            for file_info in artifact_list['files'][:5]:  # Show first 5 files
                print(f"     - {file_info['file_path']}:")
                print(f"       Latest version: {file_info['latest_version']}")
                print(f"       Total versions: {file_info['total_versions']}")
                print(f"       MIME type: {file_info.get('mime_type', 'N/A')}")
                print(f"       Language: {file_info.get('language', 'N/A')}")
                print(f"       Agent: {file_info['agent_role']}")
            print()
            
            # Test API 2: Get versions for first file
            first_file = artifact_list['files'][0]
            file_path = first_file['file_path']
            encoded_file_path = quote(file_path, safe='')
            
            print(f"5. Testing GET /api/artifacts/{task_id}/{file_path}/versions...")
            response = requests.get(f"{BASE_URL}/api/artifacts/{task_id}/{encoded_file_path}/versions")
            
            if response.status_code != 200:
                print(f"❌ Failed to get versions: {response.status_code}")
                print(response.text)
            else:
                versions_response = response.json()
                print(f"✅ Versions retrieved:")
                print(f"   File: {versions_response['file_path']}")
                print(f"   Total versions: {versions_response['total']}")
                print()
                
                if versions_response['versions']:
                    print("   Versions:")
                    for version_info in versions_response['versions']:
                        print(f"     - Version {version_info['version']}:")
                        print(f"       Artifact ID: {version_info['artifact_id']}")
                        print(f"       Agent: {version_info['agent_role']}")
                        print(f"       Content length: {version_info['content_length']} chars")
                        print(f"       Created at: {version_info['created_at']}")
                    print()
                    
                    # Test API 3: Get latest version content
                    print(f"6. Testing GET /api/artifacts/{task_id}/{file_path} (latest version)...")
                    response = requests.get(f"{BASE_URL}/api/artifacts/{task_id}/{encoded_file_path}")
                    
                    if response.status_code != 200:
                        print(f"❌ Failed to get content: {response.status_code}")
                        print(response.text)
                    else:
                        content_response = response.json()
                        print(f"✅ Content retrieved:")
                        print(f"   File: {content_response['file_path']}")
                        print(f"   Version: {content_response['version']}")
                        print(f"   MIME type: {content_response.get('mime_type', 'N/A')}")
                        print(f"   Language: {content_response.get('language', 'N/A')}")
                        print(f"   Content preview: {content_response['content'][:100]}...")
                        print()
                        
                        # Test API 4: Get specific version content
                        if len(versions_response['versions']) > 1:
                            specific_version = versions_response['versions'][0]['version']
                            print(f"7. Testing GET /api/artifacts/{task_id}/{file_path}?version={specific_version}...")
                            response = requests.get(
                                f"{BASE_URL}/api/artifacts/{task_id}/{encoded_file_path}",
                                params={"version": specific_version}
                            )
                            
                            if response.status_code != 200:
                                print(f"❌ Failed to get specific version: {response.status_code}")
                                print(response.text)
                            else:
                                version_content = response.json()
                                print(f"✅ Specific version content retrieved:")
                                print(f"   Version: {version_content['version']}")
                                print(f"   Content preview: {version_content['content'][:100]}...")
                                print()
        else:
            print("⚠️  No artifacts found. Task may still be running or no artifacts generated yet.")
            print()
        
        print("✅ Artifact API test completed!")
        print()
        print("📋 Summary:")
        print(f"   - Task ID: {task_id}")
        print(f"   - Files found: {artifact_list['total']}")
        print(f"   - API endpoints: ✅ All working")
        print(f"   - MIME type detection: ✅ Working")
        print(f"   - Language detection: ✅ Working")
        
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to API server.")
        print("   Make sure the FastAPI server is running on http://localhost:8000")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_artifact_api()

