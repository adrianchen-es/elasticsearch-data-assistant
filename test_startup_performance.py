#!/usr/bin/env python3
"""
Startup performance test script for the Elasticsearch Data Assistant backend.
Measures the time it takes for the server to start accepting requests.
"""
import time
import sys
import subprocess
import os
import requests

class StartupPerformanceTest:
    def __init__(self, container_name="elasticsearch-data-assistant-backend-1", port=8000):
        self.container_name = container_name
        self.port = port
        self.base_url = f"http://localhost:{port}"
        
    def wait_for_server(self, timeout=60):
        """Wait for server to respond to health checks"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"{self.base_url}/api/health", timeout=2)
                if response.status_code == 200:
                    return time.time() - start_time, response.json()
            except requests.exceptions.RequestException:
                pass
            
            time.sleep(0.5)
        
        return None, None
    
    def start_container(self):
        """Start the backend container"""
        print("🚀 Starting backend container...")
        try:
            # Stop existing container if running
            subprocess.run(['docker', 'stop', self.container_name], 
                         capture_output=True, check=False)
            
            # Start container
            result = subprocess.run([
                'docker-compose', '-f', '/workspaces/elasticsearch-data-assistant/docker-compose.yml',
                'up', '-d', 'backend'
            ], capture_output=True, text=True, check=True)
            
            print("✅ Container start command completed")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to start container: {e}")
            print(f"stdout: {e.stdout}")
            print(f"stderr: {e.stderr}")
            return False
    
    def stop_container(self):
        """Stop the backend container"""
        print("🛑 Stopping backend container...")
        try:
            subprocess.run([
                'docker-compose', '-f', '/workspaces/elasticsearch-data-assistant/docker-compose.yml',
                'down'
            ], capture_output=True, check=False)
            print("✅ Container stopped")
        except Exception as e:
            print(f"⚠️  Error stopping container: {e}")
    
    def test_startup_performance(self):
        """Test startup performance"""
        print("=" * 60)
        print("🔧 ELASTICSEARCH DATA ASSISTANT STARTUP PERFORMANCE TEST")
        print("=" * 60)
        
        # Start container
        container_start_time = time.time()
        if not self.start_container():
            print("❌ Failed to start container")
            return False
        
        container_start_duration = time.time() - container_start_time
        print(f"⏱️  Container start time: {container_start_duration:.2f}s")
        
        # Wait for server to be ready
        print("⏳ Waiting for server to accept requests...")
        server_ready_time, health_data = self.wait_for_server()
        
        if server_ready_time is None:
            print("❌ Server failed to start within timeout")
            self.stop_container()
            return False
        
        total_startup_time = container_start_duration + server_ready_time
        
        print("\n" + "=" * 60)
        print("📊 STARTUP PERFORMANCE RESULTS")
        print("=" * 60)
        print(f"🐳 Container start time:  {container_start_duration:.2f}s")
        print(f"⚡ Server ready time:     {server_ready_time:.2f}s")
        print(f"🏁 Total startup time:    {total_startup_time:.2f}s")
        
        if health_data:
            print(f"💚 Health status:         {health_data.get('status', 'unknown')}")
            print(f"🔧 Backend ready:         {health_data.get('backend_ready', 'unknown')}")
            
        print("\n📈 PERFORMANCE ANALYSIS:")
        if total_startup_time < 10:
            print("🚀 EXCELLENT: Very fast startup time!")
        elif total_startup_time < 20:
            print("✅ GOOD: Acceptable startup time")
        elif total_startup_time < 30:
            print("⚠️  MODERATE: Could be improved")
        else:
            print("❌ SLOW: Startup time needs optimization")
        
        # Test a few API endpoints to ensure they work
        print("\n🧪 Testing API endpoints...")
        self.test_endpoints()
        
        print("\n" + "=" * 60)
        print("✅ STARTUP PERFORMANCE TEST COMPLETED")
        print("=" * 60)
        
        # Keep container running for manual testing
        print("💡 Container is still running for manual testing.")
        print(f"   Health endpoint: {self.base_url}/api/health")
        print(f"   Chat endpoint: {self.base_url}/api/chat")
        print("   Run 'docker-compose down' to stop when done.")
        
        return True
    
    def test_endpoints(self):
        """Test key endpoints to ensure they're working"""
        endpoints = [
            ("/api/health", "Health Check"),
            ("/api/healthz", "Proxy Health Check"),
        ]
        
        for endpoint, name in endpoints:
            try:
                response = requests.get(f"{self.base_url}{endpoint}", timeout=5)
                if response.status_code == 200:
                    print(f"  ✅ {name}: OK ({response.status_code})")
                else:
                    print(f"  ⚠️  {name}: Status {response.status_code}")
            except Exception as e:
                print(f"  ❌ {name}: Failed ({e})")

def main():
    """Main function"""
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print(__doc__)
        return
    
    # Change to project directory
    project_dir = "/workspaces/elasticsearch-data-assistant"
    os.chdir(project_dir)
    
    test = StartupPerformanceTest()
    
    try:
        test.test_startup_performance()
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
        test.stop_container()
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        test.stop_container()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
