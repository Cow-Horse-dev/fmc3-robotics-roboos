import time
import sys
from fourier_aurora_client import AuroraClient

DOMAIN_ID = 123
ROBOT_NAME = "gr2"

def test_connection():
    print(f"🔄 Attempting to connect to robot '{ROBOT_NAME}' on domain {DOMAIN_ID}...")

    try:
        client = AuroraClient.get_instance(domain_id=DOMAIN_ID, robot_name=ROBOT_NAME)
        print("✅ Client instance created.")
    except Exception as e:
        print(f"❌ Failed to create client: {e}")
        return

    print("⏳ Waiting 3 seconds for discovery...")
    time.sleep(3)

    try:
        # Try to read state
        pos = client.get_group_state("right_manipulator")
        print(f"📊 Current Right Arm Position: {pos}")

        if pos is None:
            print("⚠️  Position is None. Robot might not be publishing state.")
            print("   Possible causes:")
            print("   1. Network interface mismatch (DDS is using the wrong WiFi/Ethernet adapter)")
            print("   2. Robot is powered off")
            print("   3. Firewall blocking UDP multicast")
        else:
            # Check if values are all zeros (common issue with uninitialized DDS)
            if all(v == 0.0 for v in pos):
                print("⚠️  Position is all zeros. This often indicates no actual data received.")
            else:
                print("✅ Valid data received! Connection is working.")

    except Exception as e:
        print(f"❌ Error reading state: {e}")

if __name__ == "__main__":
    test_connection()