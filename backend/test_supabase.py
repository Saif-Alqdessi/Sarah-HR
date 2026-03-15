"""Test Supabase connection"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("🔍 Testing Supabase Connection\n")

# Check if variables are loaded
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")

print(f"SUPABASE_URL: {supabase_url}")
print(f"SUPABASE_KEY: {supabase_key[:20]}..." if supabase_key else "SUPABASE_KEY: NOT SET")

if not supabase_url or not supabase_key:
    print("\n❌ ERROR: Supabase credentials not found in .env file")
    print("Please create a .env file in the backend directory with:")
    print("  SUPABASE_URL=https://your-project.supabase.co")
    print("  SUPABASE_KEY=your-anon-key-here")
    exit(1)

# Try to connect
print("\n🔌 Attempting to connect to Supabase...")

try:
    from supabase import create_client
    
    supabase = create_client(supabase_url, supabase_key)
    
    # Try a simple query
    result = supabase.table("candidates").select("id, full_name").limit(1).execute()
    
    print("✅ Connection successful!")
    
    if result.data:
        print(f"✅ Found {len(result.data)} candidate(s)")
        print(f"   Example: {result.data[0]}")
    else:
        print("⚠️ No candidates found in database (table is empty)")
    
except Exception as e:
    print(f"❌ Connection failed: {e}")
    print("\nPossible issues:")
    print("1. Wrong SUPABASE_URL or SUPABASE_KEY")
    print("2. Supabase project is paused/inactive")
    print("3. Network/firewall blocking the connection")
    print("4. Table 'candidates' doesn't exist")