#!/usr/bin/env python3
"""
Test script to create sample notifications for testing the notification system
"""
import requests
import json
from datetime import datetime, timedelta

# Backend API base URL
BASE_URL = "http://localhost:8000"

def login_and_get_token(email: str, password: str) -> str:
    """Login and get access token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": email,
        "password": password
    })
    
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        raise Exception(f"Login failed: {response.text}")

def create_notification(token: str, notification_data: dict) -> dict:
    """Create a notification"""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(f"{BASE_URL}/api/notifications/create", 
                           json=notification_data, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to create notification: {response.text}")

def get_notifications(token: str) -> list:
    """Get all notifications"""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/api/notifications/", headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to get notifications: {response.text}")

def get_notification_stats(token: str) -> dict:
    """Get notification statistics"""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/api/notifications/stats", headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to get notification stats: {response.text}")

def main():
    try:
        # Login (you'll need to create a test user first or use existing credentials)
        print("Logging in...")
        token = login_and_get_token("admin@example.com", "admin123")
        print("Login successful!")
        
        # Sample notification data
        sample_notifications = [
            {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",  # Replace with actual user ID
                "message": "Low stock alert: PCR tubes are running low",
                "title": "Inventory Alert",
                "category": "inventory",
                "priority": "high",
                "meta": {
                    "item_id": "item-123",
                    "item_name": "PCR Tubes",
                    "current_quantity": 5,
                    "threshold": 10
                }
            },
            {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "message": "Protocol execution completed successfully",
                "title": "Protocol Completed",
                "category": "protocols",
                "priority": "medium",
                "meta": {
                    "protocol_id": "protocol-456",
                    "protocol_name": "DNA Extraction",
                    "execution_time": "45 minutes",
                    "status": "completed"
                }
            },
            {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "message": "New project task assigned: Review lab safety protocols",
                "title": "Task Assigned",
                "category": "projects",
                "priority": "medium",
                "meta": {
                    "project_id": "project-789",
                    "project_name": "Lab Safety Review",
                    "task_id": "task-101",
                    "due_date": (datetime.now() + timedelta(days=7)).isoformat()
                }
            },
            {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "message": "Equipment maintenance due: Centrifuge needs calibration",
                "title": "Maintenance Due",
                "category": "equipment",
                "priority": "high",
                "meta": {
                    "equipment_id": "equip-202",
                    "equipment_name": "Centrifuge",
                    "maintenance_type": "calibration",
                    "due_date": (datetime.now() + timedelta(days=3)).isoformat()
                }
            },
            {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "message": "System backup completed successfully",
                "title": "System Update",
                "category": "system",
                "priority": "low",
                "meta": {
                    "backup_size": "2.5 GB",
                    "duration": "15 minutes",
                    "status": "completed"
                }
            }
        ]
        
        # Create notifications
        print("\nCreating sample notifications...")
        created_notifications = []
        for i, notification_data in enumerate(sample_notifications, 1):
            try:
                notification = create_notification(token, notification_data)
                created_notifications.append(notification)
                print(f"✓ Created notification {i}: {notification['title']}")
            except Exception as e:
                print(f"✗ Failed to create notification {i}: {e}")
        
        # Get all notifications
        print("\nFetching all notifications...")
        notifications = get_notifications(token)
        print(f"Total notifications: {len(notifications)}")
        
        # Get notification stats
        print("\nFetching notification statistics...")
        stats = get_notification_stats(token)
        print(f"Notification stats: {json.dumps(stats, indent=2)}")
        
        print("\n✅ Notification system test completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    main() 